"""One-shot auto-generation pipeline.

The user provides only a theme, a caption/voice language and a narration speed;
this service runs the whole chain in the background — script -> visuals -> voice
-> render — with no manual visual selection or approval. It is a single
``generation_autopilot`` job that drives the early steps and then hands off to
the existing ``generation_render`` job.
"""
from __future__ import annotations

import re
from typing import Any

from app import config
from app.services import job_queue_service
from app.services.job_queue_service import JobCancelled, JobContext
from app.services.generation_engine_service import generate_engine_script
from app.services.generation_render_service import request_render, get_render_status
from app.services.generation_visual_service import suggest_visuals_for_project
from app.services.generation_voice_service import generate_voice_for_project
from app.services.generation_personas import get_persona
from app.services.generation_workspace_service import (
    create_project,
    get_project,
    update_project,
)


JOB_TYPE = "generation_autopilot"

# Caption/voice language -> default edge-tts voice. Invalid names fall back
# safely inside generate_voice_for_project, so this only needs to be close.
# OpenAI TTS is multilingual, so the same voice works across languages. Falls
# back to edge-tts (Thalita) automatically if OpenAI TTS is unavailable.
_DEFAULT_VOICE_BY_LANG: dict[str, str] = {
    "pt": "openai:onyx",
    "en": "openai:onyx",
    "es": "openai:onyx",
}

# Friendly speed presets -> edge-tts rate. A raw rate string also works.
_SPEED_PRESETS: dict[str, str] = {
    "lento": "-7%",
    "slow": "-7%",
    "normal": "-2%",
    "rapido": "+8%",
    "rápido": "+8%",
    "fast": "+10%",
}

# auto_status values the pre-render steps move through.
_PRE_RENDER = {"queued", "scripting", "visuals", "voice"}


def start_auto_generation(
    theme: str,
    language: str = "pt-BR",
    speed: str = "normal",
    voice: str = "",
    niche: str = "",
    tone: str = "curioso",
    duration_seconds: int = 60,
    narrative_style: str = "",
    persona: str = "",
) -> dict[str, Any]:
    """Create the project and enqueue the full auto pipeline. A persona/studio
    fills the scriptwriter voice, niche, tone, style, voice, music and visuals;
    explicit args override it. Returns handles."""
    theme = re.sub(r"\s+", " ", str(theme or "")).strip()
    if not theme:
        raise ValueError("theme_required")

    p = get_persona(persona) if persona else None
    language = (language or "pt-BR").strip() or "pt-BR"
    resolved_niche = (niche or "").strip() or (p.get("niche") if p else "") or _infer_niche(theme)
    resolved_tone = (p.get("tone") if p else "") or tone or "curioso"
    resolved_style = (narrative_style or "").strip() or (p.get("narrative_style") if p else "")
    resolved_voice = (voice or "").strip() or (p.get("voice") if p else "")
    resolved_speed = speed if (speed and speed != "normal") else (p.get("speed") if p else speed)
    scriptwriter = p.get("scriptwriter") if p else ""
    music_mood = p.get("music_mood") if p else ""
    visual_style = p.get("visual_style") if p else ""

    project = create_project(
        {
            "title": theme[:90],
            "idea": theme,
            "input_topic": theme,
            "input_idea": theme,
            "niche": resolved_niche,
            "language": language,
            "tone": resolved_tone,
            "creation_mode": "manual_idea",
            "status": "idea",
            "auto_status": "queued",
            "persona": (persona or "").strip().lower() if p else "",
            "persona_label": p.get("label") if p else "",
            "scriptwriter": scriptwriter or "",
            "music_mood": music_mood or "",
            "visual_style": visual_style or "",
        }
    )
    project_id = str(project["project_id"])

    job = job_queue_service.enqueue(
        JOB_TYPE,
        payload={
            "project_id": project_id,
            "theme": theme,
            "language": language,
            "voice": resolved_voice,
            "voice_rate": _resolve_rate(resolved_speed),
            "niche": resolved_niche,
            "tone": resolved_tone,
            "duration_seconds": int(duration_seconds or 60),
            "narrative_style": resolved_style,
            "scriptwriter": scriptwriter or "",
        },
        project_id=project_id,
    )
    update_project(
        project_id,
        {**(get_project(project_id) or {}), "auto_status": "queued", "auto_job_id": job.get("id"), "auto_error": ""},
    )
    return {"project_id": project_id, "job_id": job.get("id"), "auto_status": "queued"}


def get_auto_status(project_id: str) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    auto = str(project.get("auto_status") or "queued")
    render = get_render_status(project_id) or {}
    render_status = str(project.get("render_status") or "none")
    render_progress = float(render.get("progress") or 0.0)

    # Before hand-off the autopilot owns the status; after that the render job does.
    if auto in _PRE_RENDER:
        status = auto
        progress = {"queued": 0.05, "scripting": 0.2, "visuals": 0.45, "voice": 0.65}.get(auto, 0.05)
    elif auto == "failed":
        status, progress = "failed", 0.0
    elif auto == "cancelled":
        status, progress = "cancelled", 0.0
    else:  # rendering hand-off
        if render_status == "ready":
            status, progress = "ready", 1.0
        elif render_status in {"failed"}:
            status, progress = "failed", render_progress
        elif render_status in {"cancelled"}:
            status, progress = "cancelled", render_progress
        else:
            status, progress = "rendering", 0.7 + 0.3 * render_progress

    degraded, warning = _degraded_warning(project)
    return {
        "project_id": project_id,
        "status": status,
        "auto_status": auto,
        "render_status": render_status,
        "progress": round(progress, 2),
        "title": project.get("title"),
        "script_quality_score": project.get("script_quality_score"),
        "script_quality_tier": project.get("script_quality_tier"),
        "degraded": degraded,
        "warning": warning,
        "video_url": f"/generation/projects/{project_id}/render/video" if status == "ready" else "",
        "error": project.get("auto_error") or project.get("render_error") or "",
    }


def _degraded_warning(project: dict[str, Any]) -> tuple[bool, str]:
    """Flag videos produced while the AI was unavailable (quota/outage)."""
    last_error = str(project.get("last_llm_error") or "").lower()
    quota_hit = any(marker in last_error for marker in ["429", "resource_exhausted", "quota"])
    used_fallback = bool(project.get("fallback_used"))
    visuals = project.get("visual_items") or []
    visuals_degraded = bool(visuals) and not any(v.get("llm_queries") for v in visuals if isinstance(v, dict))
    if quota_hit or used_fallback:
        return True, (
            "IA indisponível (quota do Gemini esgotada ou instável): roteiro/visuais "
            "gerados em modo degradado. Regenere quando a quota voltar para qualidade total."
        )
    if visuals_degraded:
        return True, "Visuais gerados sem o matching por IA (fallback). Re-sugira os visuais para melhorar."
    return False, ""


# ---------------------------------------------------------------------------
# Job handler
# ---------------------------------------------------------------------------

def _handle_autopilot(ctx: JobContext) -> dict[str, Any]:
    payload = ctx.payload
    project_id = str(payload.get("project_id") or "")
    theme = str(payload.get("theme") or "")
    language = str(payload.get("language") or "pt-BR")
    niche = str(payload.get("niche") or "")
    tone = str(payload.get("tone") or "curioso")
    duration = int(payload.get("duration_seconds") or 60)
    narrative_style = str(payload.get("narrative_style") or "")
    scriptwriter = str(payload.get("scriptwriter") or "")
    voice = str(payload.get("voice") or "") or _DEFAULT_VOICE_BY_LANG.get(_lang_key(language), "pt-BR-AntonioNeural")
    voice_rate = str(payload.get("voice_rate") or "-6%")

    try:
        # 1. Script (research + narrative + judge/rewrite all happen inside).
        ctx.check_cancelled()
        _set_auto(project_id, "scripting", progress=0.1, ctx=ctx)
        script = generate_engine_script(
            idea=theme,
            niche=niche,
            topic=theme,
            duration_seconds=duration,
            tone=tone,
            language=language,
            narrative_style=narrative_style,
            scriptwriter=scriptwriter,
        )
        project = get_project(project_id) or {}
        update_project(project_id, {**project, **script, "idea": theme, "status": "script", "auto_status": "scripting"})

        # Hard quality gate: only accept scripts the judge scored >= the minimum.
        # (Skip when the judge didn't run — e.g. AI quota — so we don't block on a
        # missing score; that case is already flagged as degraded.)
        min_score = float(config.GENERATION_MIN_ACCEPT_SCORE)
        score = script.get("script_quality_score")
        if script.get("judge_used") and score is not None and float(score) < min_score:
            _set_auto(
                project_id,
                "failed",
                error=(
                    f"Roteiro não atingiu a qualidade mínima ({float(score):.1f} < {min_score:.0f}). "
                    "Tente outro ângulo/tema, ou ajuste GENERATION_MIN_ACCEPT_SCORE."
                ),
            )
            return {"project_id": project_id, "auto_status": "failed", "reason": "below_min_score"}

        # 2. Visuals (LLM stock queries; no manual selection).
        ctx.check_cancelled()
        _set_auto(project_id, "visuals", progress=0.4, ctx=ctx)
        suggest_visuals_for_project(project_id)

        # 3. Voice (chosen language + speed).
        ctx.check_cancelled()
        _set_auto(project_id, "voice", progress=0.6, ctx=ctx)
        generate_voice_for_project(project_id, voice=voice, rate=voice_rate, pitch="+0Hz")

        # 4. Render — enqueues the render job (fallback always on so it never blocks).
        ctx.check_cancelled()
        _set_auto(project_id, "rendering", progress=0.8, ctx=ctx)
        request_render(project_id, overwrite=True, allow_visual_fallback=True, force=True)
        return {"project_id": project_id, "auto_status": "rendering"}
    except JobCancelled:
        _set_auto(project_id, "cancelled")
        raise
    except Exception as error:  # noqa: BLE001 - surface failure to the project
        _set_auto(project_id, "failed", error=str(error))
        raise


def _set_auto(project_id: str, status: str, progress: float | None = None, error: str = "", ctx: JobContext | None = None) -> None:
    project = get_project(project_id)
    if project:
        update_project(project_id, {**project, "auto_status": status, "auto_error": error})
    if ctx is not None and progress is not None:
        ctx.set_progress(progress, status)


def _resolve_rate(speed: str) -> str:
    text = re.sub(r"\s+", "", str(speed or "")).strip()
    if not text:
        return "-6%"
    key = text.lower()
    if key in _SPEED_PRESETS:
        return _SPEED_PRESETS[key]
    # Accept a raw edge-tts rate like "-10%" / "+5%".
    if re.fullmatch(r"[+-]?\d{1,3}%", text):
        return text if text[0] in "+-" else f"+{text}"
    return "-6%"


def _lang_key(language: str) -> str:
    return str(language or "").strip().lower()[:2]


def _infer_niche(theme: str) -> str:
    text = _strip_accents(theme.lower())
    table = [
        ("futebol", ["futebol", "copa", "brasileirao", "premier league", "champions", "jogo", "gol", "selecao", "campeonato"]),
        ("história", ["historia", "imperio", "guerra", "antigo", "seculo", "civilizacao", "rei", "faraó", "farao"]),
        ("true crime", ["crime", "assassinato", "misterio", "investigacao", "caso", "desaparecimento"]),
        ("tecnologia", ["tecnologia", "ia ", "intelig", "robo", "app", "tech", "computador"]),
        ("finanças", ["dinheiro", "financ", "investiment", "economia", "bolsa", "cripto"]),
    ]
    for niche, terms in table:
        if any(term in text for term in terms):
            return niche
    return "curiosidades"


def _strip_accents(value: str) -> str:
    mapping = str.maketrans("áàãâéêíóôõúüç", "aaaaeeiooouuc")
    return str(value or "").translate(mapping)


job_queue_service.register_handler(JOB_TYPE, _handle_autopilot)
