from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.generation_engine_service import (
    generate_engine_ideas,
    generate_engine_script,
)
from app.services.generation_script_quality_service import score_generation_script


PROJECTS_PATH = config.STORAGE_GENERATION_DIR / "projects.json"

NICHE_ANGLES: dict[str, list[str]] = {
    "curiosidades": ["o detalhe que muda tudo", "a história pouco contada", "o erro que quase ninguém percebe"],
    "negócios": ["a decisão que separa amadores de profissionais", "o custo invisível", "a virada de estratégia"],
    "negocios": ["a decisão que separa amadores de profissionais", "o custo invisível", "a virada de estratégia"],
    "futebol": ["a escolha que dividiu a torcida", "o bastidor que explica a polêmica", "o detalhe tático ignorado"],
    "tecnologia": ["a mudança silenciosa", "o risco escondido", "a oportunidade antes da massa"],
    "política": ["o impacto prático da decisão", "a disputa por trás do discurso", "o ponto que ficou fora do debate"],
    "politica": ["o impacto prático da decisão", "a disputa por trás do discurso", "o ponto que ficou fora do debate"],
    "história": ["a versão que você não aprendeu", "o detalhe humano do evento", "a decisão que mudou o rumo"],
    "historia": ["a versão que você não aprendeu", "o detalhe humano do evento", "a decisão que mudou o rumo"],
    "true crime": ["o sinal ignorado", "a contradição no caso", "o detalhe que reacendeu a dúvida"],
    "saúde": ["o hábito simples que muita gente subestima", "o mito que confunde as pessoas", "a rotina que muda o resultado"],
    "saude": ["o hábito simples que muita gente subestima", "o mito que confunde as pessoas", "a rotina que muda o resultado"],
    "finanças": ["o erro que drena dinheiro", "a decisão pequena com efeito grande", "a regra que poucos seguem"],
    "financas": ["o erro que drena dinheiro", "a decisão pequena com efeito grande", "a regra que poucos seguem"],
}

TONE_WORDS: dict[str, dict[str, str]] = {
    "polêmico": {"hook": "Isso vai dividir opiniões", "cta": "Comenta se você concorda ou não."},
    "polemico": {"hook": "Isso vai dividir opiniões", "cta": "Comenta se você concorda ou não."},
    "curioso": {"hook": "Pouca gente percebe esse detalhe", "cta": "Salva para lembrar depois."},
    "didático": {"hook": "Entenda isso em menos de um minuto", "cta": "Compartilha com alguém que precisa ver isso."},
    "didatico": {"hook": "Entenda isso em menos de um minuto", "cta": "Compartilha com alguém que precisa ver isso."},
    "sério": {"hook": "Esse ponto merece atenção", "cta": "Vale acompanhar os próximos desdobramentos."},
    "serio": {"hook": "Esse ponto merece atenção", "cta": "Vale acompanhar os próximos desdobramentos."},
    "leve": {"hook": "Olha que detalhe interessante", "cta": "Me diz qual parte você achou mais curiosa."},
}


def list_projects() -> list[dict[str, Any]]:
    return sorted(_load_projects(), key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def get_project(project_id: str) -> dict[str, Any] | None:
    for project in _load_projects():
        if str(project.get("project_id") or "") == project_id:
            return project
    return None


def create_project(payload: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    project = _normalize_project(
        {
            **payload,
            "project_id": payload.get("project_id") or f"gen_{uuid.uuid4().hex[:12]}",
            "created_at": payload.get("created_at") or now,
            "updated_at": now,
        }
    )
    projects = [item for item in _load_projects() if item.get("project_id") != project["project_id"]]
    projects.append(project)
    _save_projects(projects)
    return project


def update_project(project_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    projects = _load_projects()
    updated: dict[str, Any] | None = None
    next_projects: list[dict[str, Any]] = []
    for project in projects:
        if str(project.get("project_id") or "") != project_id:
            next_projects.append(project)
            continue
        updated = _normalize_project({**project, **payload, "project_id": project_id, "updated_at": _now()})
        next_projects.append(updated)
    if updated is None:
        return None
    _save_projects(next_projects)
    return updated


def delete_project(project_id: str) -> bool:
    projects = _load_projects()
    next_projects = [item for item in projects if str(item.get("project_id") or "") != project_id]
    if len(next_projects) == len(projects):
        return False
    _save_projects(next_projects)
    return True


def generate_ideas(niche: str, topic: str = "", language: str = "pt-BR", tone: str = "curioso") -> list[dict[str, Any]]:
    return generate_engine_ideas(niche=niche, topic=topic, language=language, tone=tone)


def generate_script(
    idea: str,
    niche: str = "",
    topic: str = "",
    duration_seconds: int = 45,
    tone: str = "curioso",
    language: str = "pt-BR",
) -> dict[str, Any]:
    return generate_engine_script(
        idea=idea,
        niche=niche,
        topic=topic,
        duration_seconds=duration_seconds,
        tone=tone,
        language=language,
    )


def _normalize_project(payload: dict[str, Any]) -> dict[str, Any]:
    quality_payload = {
        "title": payload.get("title"),
        "hook": payload.get("hook"),
        "script_lines": payload.get("script_lines"),
        "cta": payload.get("cta"),
        "hashtags": payload.get("hashtags"),
        "visual_context": payload.get("visual_context"),
        "fact_check_notes": payload.get("fact_check_notes"),
        "factual_brief": payload.get("factual_brief"),
        "estimated_duration_seconds": payload.get("estimated_duration_seconds"),
    }
    quality = score_generation_script(quality_payload)
    return {
        "project_id": str(payload.get("project_id") or f"gen_{uuid.uuid4().hex[:12]}"),
        "title": _clean(payload.get("title")) or "Projeto sem título",
        "niche": _clean(payload.get("niche")),
        "language": _clean(payload.get("language")) or "pt-BR",
        "tone": _clean(payload.get("tone")) or "curioso",
        "status": _status(payload.get("status")),
        "idea": _clean(payload.get("idea")),
        "hook": _clean(payload.get("hook")),
        "script_lines": _string_list(payload.get("script_lines")),
        "cta": _clean(payload.get("cta")),
        "hashtags": _string_list(payload.get("hashtags")),
        "visual_context": _string_list(payload.get("visual_context")),
        "factual_brief": payload.get("factual_brief") if isinstance(payload.get("factual_brief"), dict) else {},
        "factual_grounding_used": _bool(payload.get("factual_grounding_used")),
        "factual_grounding_confidence": _clean(payload.get("factual_grounding_confidence")) or "low",
        "specificity_score": _float_or_none(payload.get("specificity_score")),
        "engine_mode": _engine_mode(payload.get("engine_mode")),
        "provider": _provider(payload.get("provider")),
        "fallback_used": _bool(payload.get("fallback_used")),
        "fact_check_notes": _string_list(payload.get("fact_check_notes")),
        "estimated_duration_seconds": _float_or_none(payload.get("estimated_duration_seconds")),
        "voice_style": _clean(payload.get("voice_style")),
        "pacing": _clean(payload.get("pacing")),
        "script_quality_score": _float_or_none(payload.get("script_quality_score")) or quality["script_quality_score"],
        "script_quality_tier": _clean(payload.get("script_quality_tier")) or quality["script_quality_tier"],
        "script_positive_signals": _string_list(payload.get("script_positive_signals"))
        or quality["script_positive_signals"],
        "script_negative_signals": _string_list(payload.get("script_negative_signals"))
        or quality["script_negative_signals"],
        "script_reject_reason": _clean(payload.get("script_reject_reason"))
        or quality["script_reject_reason"],
        "script_repair_applied": _bool(payload.get("script_repair_applied")),
        "script_repair_reason": _clean(payload.get("script_repair_reason")),
        "guardrail_status": _clean(payload.get("guardrail_status")),
        "guardrail_risks": _string_list(payload.get("guardrail_risks")),
        "disclosure_recommended": _bool(payload.get("disclosure_recommended")),
        "fact_check_required": _bool(payload.get("fact_check_required")),
        "copyright_review_required": _bool(payload.get("copyright_review_required")),
        "platform_notes": _string_list(payload.get("platform_notes")),
        "voice_status": _voice_status(payload.get("voice_status")),
        "voice_name": _clean(payload.get("voice_name")),
        "voice_provider": _clean(payload.get("voice_provider")),
        "voice_rate": _clean(payload.get("voice_rate")),
        "voice_pitch": _clean(payload.get("voice_pitch")),
        "voice_audio_path": _clean(payload.get("voice_audio_path")),
        "voice_audio_url": _clean(payload.get("voice_audio_url")),
        "voice_duration_seconds": _float_or_none(payload.get("voice_duration_seconds")),
        "voice_generated_at": _clean(payload.get("voice_generated_at")),
        "voice_error": _clean(payload.get("voice_error")),
        "created_at": str(payload.get("created_at") or _now()),
        "updated_at": str(payload.get("updated_at") or _now()),
    }


def _load_projects() -> list[dict[str, Any]]:
    if not PROJECTS_PATH.exists():
        return []
    try:
        with PROJECTS_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return []
    if isinstance(payload, dict):
        items = payload.get("projects", [])
    else:
        items = payload
    if not isinstance(items, list):
        return []
    return [_normalize_project(item) for item in items if isinstance(item, dict)]


def _save_projects(projects: list[dict[str, Any]]) -> None:
    PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROJECTS_PATH.open("w", encoding="utf-8") as file:
        json.dump({"projects": projects}, file, ensure_ascii=False, indent=2)


def _status(value: object) -> str:
    text = str(value or "idea")
    return text if text in {"idea", "script", "ready_for_voice", "ready_for_visual", "ready_for_render", "archived"} else "idea"


def _engine_mode(value: object) -> str:
    text = str(value or "local").strip().lower()
    return text if text in {"local", "canal_dark"} else "local"


def _provider(value: object) -> str:
    text = str(value or "none").strip().lower()
    return text if text in {"none", "gemini"} else "none"


def _voice_status(value: object) -> str:
    text = str(value or "none")
    return text if text in {"none", "generating", "ready", "failed"} else "none"


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim"}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize(value: str) -> str:
    return _clean(value).lower()


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    if not text:
        return []
    return [_clean(item) for item in re.split(r"[,;\n]+", text) if _clean(item)]


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _default_topic(niche: str) -> str:
    defaults = {
        "futebol": "uma decisão que mudou o jogo",
        "negócios": "uma estratégia que pouca gente usa",
        "negocios": "uma estratégia que pouca gente usa",
        "finanças": "um erro comum com dinheiro",
        "financas": "um erro comum com dinheiro",
        "tecnologia": "uma mudança que já começou",
    }
    return defaults.get(_normalize(niche), f"um tema de {niche}")


def _generic_angles() -> list[str]:
    return ["o antes e depois", "a pergunta que prende atenção", "o lado ignorado da história"]


def _why_it_works(niche: str, angle: str, tone: str) -> str:
    return f"Combina {niche} com {angle}, criando curiosidade rápida e espaço para opinião em tom {tone}."


def _risk_level(niche: str, tone: str) -> str:
    if niche in {"política", "politica", "true crime", "saúde", "saude"}:
        return "medium"
    if tone in {"polêmico", "polemico"}:
        return "medium"
    return "low"


def _hashtags(niche: str, topic: str, language: str) -> list[str]:
    base = [_hashtag(niche), _hashtag(topic), "#shorts"]
    if str(language).lower().startswith("pt"):
        base.append("#brasil")
    return list(dict.fromkeys(item for item in base if item != "#"))


def _hashtag(value: str) -> str:
    text = re.sub(r"[^A-Za-zÀ-ÿ0-9]+", "", value.title())
    return f"#{text}" if text else "#darkflow"


def _visual_context(niche: str, idea: str) -> list[str]:
    return [
        f"Imagem principal relacionada a {niche}.",
        "Texto curto na tela com a pergunta central.",
        f"B-roll genérico que represente: {idea}.",
        "Cortes rápidos entre contexto, contraste e conclusão.",
    ]


def _title_from_idea(idea: str) -> str:
    title = idea.split(":")[0].strip() or idea
    return title[:90]


def _now() -> str:
    return datetime.utcnow().isoformat()
