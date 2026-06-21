"""One-shot auto-generation pipeline.

The user provides only a theme, a caption/voice language and a narration speed;
this service runs the whole chain in the background — script -> visuals -> voice
-> render — with no manual visual selection or approval. It is a single
``generation_autopilot`` job that drives the early steps and then hands off to
the existing ``generation_render`` job.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from app import config
from app.services import job_queue_service
from app.services.job_queue_service import JobCancelled, JobContext
from app.services.generation_engine_service import generate_engine_script
from app.services.generation_llm_provider_service import translate_script_fields
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
# Clone job: same theme/research/visuals as a finished base project, only re-narrated
# and re-captioned in another language (the bilingual "generate once" flow).
JOB_TYPE_TRANSLATE = "generation_autopilot_translate"

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


def _resolve_voice(persona_obj: dict[str, Any] | None, language: str, explicit_voice: str) -> str:
    """Voice for a language: explicit pick wins; else persona's voice; for non-PT the
    cloned (PT-trained) voice is replaced by the native-language voice (persona
    voice_en or GENERATION_ENGLISH_VOICE)."""
    voice = (explicit_voice or "").strip() or (persona_obj.get("voice") if persona_obj else "") or ""
    if language.strip().lower()[:2] != "pt" and not (explicit_voice or "").strip():
        en_voice = (persona_obj.get("voice_en") if persona_obj else "") or config.GENERATION_ENGLISH_VOICE
        if en_voice:
            voice = en_voice
    return voice


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
    also_languages: list[str] | None = None,
) -> dict[str, Any]:
    """Create the project and enqueue the full auto pipeline. A persona/studio
    fills the scriptwriter voice, niche, tone, style, voice, music and visuals;
    explicit args override it. Returns handles.

    ``also_languages`` (the bilingual "generate once" flow): after this base video
    is built, clone jobs translate the SAME script and reuse the SAME visuals to
    produce one extra video per language — only narration + captions are redone."""
    theme = re.sub(r"\s+", " ", str(theme or "")).strip()
    if not theme:
        raise ValueError("theme_required")

    p = get_persona(persona) if persona else None
    language = (language or "pt-BR").strip() or "pt-BR"
    resolved_niche = (niche or "").strip() or (p.get("niche") if p else "") or _infer_niche(theme)
    resolved_tone = (p.get("tone") if p else "") or tone or "curioso"
    resolved_style = (narrative_style or "").strip() or (p.get("narrative_style") if p else "")
    resolved_voice = _resolve_voice(p, language, voice)
    resolved_speed = speed if (speed and speed != "normal") else (p.get("speed") if p else speed)
    # Extra languages to clone after the base finishes (dedupe, drop the base lang).
    extra_languages = [
        lang.strip() for lang in (also_languages or [])
        if lang.strip() and lang.strip().lower()[:2] != language.strip().lower()[:2]
    ]
    seen_extra: set[str] = set()
    extra_languages = [l for l in extra_languages if not (l in seen_extra or seen_extra.add(l))]
    scriptwriter = p.get("scriptwriter") if p else ""
    music_mood = p.get("music_mood") if p else ""
    visual_style = p.get("visual_style") if p else ""
    persona_id = (persona or "").strip().lower() if p else ""

    base_fields = {
        "idea": theme,
        "input_topic": theme,
        "input_idea": theme,
        "niche": resolved_niche,
        "tone": resolved_tone,
        "creation_mode": "manual_idea",
        "persona": persona_id,
        "persona_label": p.get("label") if p else "",
        "scriptwriter": scriptwriter or "",
        "music_mood": music_mood or "",
        "visual_style": visual_style or "",
    }

    project = create_project(
        {**base_fields, "title": theme[:90], "language": language, "status": "idea", "auto_status": "queued"}
    )
    project_id = str(project["project_id"])

    # Placeholder projects for the extra languages so the UI gets a stable project_id
    # per language immediately. They sit "queued" until the base finishes and the clone
    # job fills them in (translated script + reused visuals).
    clone_targets: list[dict[str, str]] = []
    for extra in extra_languages:
        placeholder = create_project(
            {
                **base_fields,
                "title": theme[:90],
                "language": extra,
                "status": "idea",
                "auto_status": "queued",
                "bilingual_parent": project_id,
                "bilingual_base_language": language,
            }
        )
        clone_targets.append({"language": extra, "project_id": str(placeholder["project_id"])})

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
            # carried so the base job can spawn translated clones when it finishes
            "clone_targets": clone_targets,
            "persona": persona_id,
            "speed": resolved_speed or "",
        },
        project_id=project_id,
    )
    update_project(
        project_id,
        {**(get_project(project_id) or {}), "auto_status": "queued", "auto_job_id": job.get("id"), "auto_error": ""},
    )
    return {
        "project_id": project_id,
        "job_id": job.get("id"),
        "auto_status": "queued",
        "clones": clone_targets,
    }


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
            _fail_clone_placeholders(payload, "Vídeo base não atingiu a qualidade mínima.")
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
        #    request_render resolves + PERSISTS the visual media before returning, so
        #    after this the base project's visual_items are ready to be reused.
        ctx.check_cancelled()
        _set_auto(project_id, "rendering", progress=0.8, ctx=ctx)
        request_render(project_id, overwrite=True, allow_visual_fallback=True, force=True)

        # 5. Bilingual "generate once": clone the finished base into the extra
        #    languages — same research + same visuals, only re-narrated/re-captioned.
        clones = _enqueue_translation_clones(project_id, payload)
        return {"project_id": project_id, "auto_status": "rendering", "clones": clones}
    except JobCancelled:
        _set_auto(project_id, "cancelled")
        _fail_clone_placeholders(payload, "Vídeo base cancelado.", status="cancelled")
        raise
    except Exception as error:  # noqa: BLE001 - surface failure to the project
        _set_auto(project_id, "failed", error=str(error))
        _fail_clone_placeholders(payload, f"Vídeo base falhou: {error}")
        raise


def _fail_clone_placeholders(base_payload: dict[str, Any], error: str, status: str = "failed") -> None:
    """When the base video doesn't reach render, the pre-created clone placeholders
    can't be filled — mark them failed/cancelled so they don't sit 'queued' forever."""
    for target in (base_payload.get("clone_targets") or []):
        child_id = str(target.get("project_id") or "").strip() if isinstance(target, dict) else ""
        if child_id and get_project(child_id):
            _set_auto(child_id, status, error=error)


def _enqueue_translation_clones(base_project_id: str, base_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """For each extra language, enqueue a clone job that translates the base script and
    reuses its (already resolved) visuals into the pre-created placeholder project.
    Best-effort: a failure here never breaks the base video."""
    targets = [t for t in (base_payload.get("clone_targets") or []) if isinstance(t, dict)]
    if not targets:
        return []
    persona = str(base_payload.get("persona") or "")
    speed = str(base_payload.get("speed") or "")
    clones: list[dict[str, Any]] = []
    for target in targets:
        language = str(target.get("language") or "").strip()
        child_id = str(target.get("project_id") or "").strip()
        if not language or not child_id:
            continue
        try:
            job = job_queue_service.enqueue(
                JOB_TYPE_TRANSLATE,
                payload={
                    "base_project_id": base_project_id,
                    "child_project_id": child_id,
                    "language": language,
                    "persona": persona,
                    "speed": speed,
                },
                project_id=child_id,
            )
            clones.append({"language": language, "project_id": child_id, "job_id": job.get("id")})
        except Exception as error:  # noqa: BLE001 - clone is best-effort
            clones.append({"language": language, "project_id": child_id, "error": str(error)})
    return clones


def _handle_autopilot_translate(ctx: JobContext) -> dict[str, Any]:
    """Build one extra-language video from a finished base project: same research and
    same visuals, only the narration and captions are redone in the target language."""
    payload = ctx.payload
    base_project_id = str(payload.get("base_project_id") or "")
    child_id = str(payload.get("child_project_id") or "")
    language = str(payload.get("language") or "en-US")
    persona = str(payload.get("persona") or "")
    speed = str(payload.get("speed") or "")

    base = get_project(base_project_id)
    if not base:
        raise RuntimeError(f"base_project_not_found: {base_project_id}")
    if not (base.get("script_lines") or base.get("hook")):
        raise RuntimeError("base_project_has_no_script")
    if not child_id or not get_project(child_id):
        raise RuntimeError(f"clone_placeholder_not_found: {child_id}")

    # 1. Translate the narration-bearing fields (1 cheap LLM call). Visuals are reused.
    translated = translate_script_fields(
        {
            "title": base.get("title"),
            "hook": base.get("hook"),
            "script_lines": base.get("script_lines"),
            "cta": base.get("cta"),
        },
        target_language=language,
        source_language=str(base.get("language") or ""),
    )

    # 2. Fill the placeholder with a copy of the base, overriding language + translated
    #    text. visual_items are copied verbatim (with their resolved media_path), so the
    #    render reuses the same images — no stock/Wikipedia/Flux calls are repeated.
    seed = copy.deepcopy(base)
    for drop in (
        "project_id", "created_at", "updated_at",
        "auto_job_id", "auto_error",
        "render_status", "render_job_id", "render_error",
        "render_video_path", "render_video_url", "render_thumbnail_path",
        "render_thumbnail_url", "render_generated_at",
        "voice_audio_path", "voice_audio_url", "voice_words_path", "voice_words",
        "voice_captions_path", "voice_generated_at", "voice_status", "voice_error",
        "narration_text", "narration_text_preview",
        "publish_titles", "publish_description", "publish_hashtags",
        "publish_best_times", "publish_generated_at",
    ):
        seed.pop(drop, None)
    seed.update(
        {
            "language": language,
            "title": (translated.get("title") or base.get("title") or "")[:90],
            "hook": translated.get("hook") or "",
            "script_lines": translated.get("script_lines") or [],
            "cta": translated.get("cta") or "",
            "status": "script",
            "auto_status": "voice",
            "bilingual_parent": base_project_id,
            "bilingual_base_language": str(base.get("language") or ""),
        }
    )
    update_project(child_id, {**(get_project(child_id) or {}), **seed})

    try:
        # 3. Voice in the target language (native voice for non-PT) + speed.
        p = get_persona(persona) if persona else None
        voice = _resolve_voice(p, language, "") or _DEFAULT_VOICE_BY_LANG.get(
            _lang_key(language), "pt-BR-AntonioNeural"
        )
        voice_rate = _resolve_rate(speed or (p.get("speed") if p else "") or "")
        ctx.check_cancelled()
        _set_auto(child_id, "voice", progress=0.5, ctx=ctx)
        generate_voice_for_project(child_id, voice=voice, rate=voice_rate, pitch="+0Hz")

        # 4. Render — reuses the copied visuals (media already resolved).
        ctx.check_cancelled()
        _set_auto(child_id, "rendering", progress=0.8, ctx=ctx)
        request_render(child_id, overwrite=True, allow_visual_fallback=True, force=True)
        return {"project_id": child_id, "base_project_id": base_project_id, "language": language, "auto_status": "rendering"}
    except JobCancelled:
        _set_auto(child_id, "cancelled")
        raise
    except Exception as error:  # noqa: BLE001 - surface failure to the child project
        _set_auto(child_id, "failed", error=str(error))
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
job_queue_service.register_handler(JOB_TYPE_TRANSLATE, _handle_autopilot_translate)
