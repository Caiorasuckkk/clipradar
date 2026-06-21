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
from app.services.generation_llm_provider_service import sanitize_narration_lines
from app.services.generation_script_quality_service import score_generation_script
from app.services.generation_watchability_service import (
    content_format_label,
    normalize_content_format,
    score_watchability,
)


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
    duration_preset: str = "",
    tone: str = "curioso",
    language: str = "pt-BR",
    force_research: bool = False,
    provider: str = "auto",
    script_depth: str = "normal",
    narrative_style: str = "",
    content_format: str = "manual_topic",
    extra_context: str = "",
    opportunity_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return generate_engine_script(
        idea=idea,
        niche=niche,
        topic=topic,
        duration_seconds=duration_seconds,
        duration_preset=duration_preset,
        tone=tone,
        language=language,
        force_research=force_research,
        provider_override=provider,
        script_depth=script_depth,
        narrative_style=narrative_style,
        content_format=content_format,
        extra_context=extra_context,
        opportunity_data=opportunity_data or {},
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
        "requested_duration_seconds": payload.get("requested_duration_seconds"),
        "duration_seconds": payload.get("duration_seconds"),
        "narrative_plan": payload.get("narrative_plan"),
        "story_beats": payload.get("story_beats"),
        "depth_score": payload.get("depth_score"),
        "narrative_score": payload.get("narrative_score"),
        "retention_score": payload.get("retention_score"),
        "content_format": payload.get("content_format"),
        "creation_mode": payload.get("creation_mode"),
        "opportunity_data": payload.get("opportunity_data"),
        "concrete_promise": payload.get("concrete_promise"),
        "viewer_reason_to_watch": payload.get("viewer_reason_to_watch"),
    }
    quality = score_generation_script(quality_payload)
    watchability = score_watchability({**payload, **quality_payload})
    creation_mode = _creation_mode(payload.get("creation_mode"))
    content_format = normalize_content_format(payload.get("content_format"), creation_mode)
    return {
        "project_id": str(payload.get("project_id") or f"gen_{uuid.uuid4().hex[:12]}"),
        "title": _clean(payload.get("title")) or "Projeto sem título",
        "niche": _clean(payload.get("niche")),
        "language": _clean(payload.get("language")) or "pt-BR",
        "tone": _clean(payload.get("tone")) or "curioso",
        "status": _status(payload.get("status")),
        "idea": _clean(payload.get("idea")),
        "creation_mode": _creation_mode(payload.get("creation_mode")),
        "creation_mode_label": _creation_mode_label(payload.get("creation_mode"), payload.get("creation_mode_label")),
        "input_topic": _clean(payload.get("input_topic")),
        "input_idea": _clean(payload.get("input_idea")),
        "input_script": _clean_multiline(payload.get("input_script")),
        "input_niche": _clean(payload.get("input_niche")),
        "input_language": _clean(payload.get("input_language")) or _clean(payload.get("language")) or "pt-BR",
        "input_tone": _clean(payload.get("input_tone")) or _clean(payload.get("tone")) or "curioso",
        "input_created_at": _clean(payload.get("input_created_at")) or str(payload.get("created_at") or _now()),
        "opportunity_data": payload.get("opportunity_data") if isinstance(payload.get("opportunity_data"), dict) else {},
        "script_import_status": _script_import_status(payload.get("script_import_status")),
        "creation_warnings": _string_list(payload.get("creation_warnings")),
        "content_format": content_format,
        "content_format_label": _clean(payload.get("content_format_label")) or content_format_label(content_format),
        "concrete_promise": _clean(payload.get("concrete_promise")) or watchability["concrete_promise"],
        "viewer_reason_to_watch": _clean(payload.get("viewer_reason_to_watch")) or watchability["viewer_reason_to_watch"],
        "watchability_score": _float_or_none(payload.get("watchability_score"))
        if payload.get("watchability_score") is not None
        else watchability["watchability_score"],
        "needs_more_context": _bool(payload.get("needs_more_context")) or watchability["needs_more_context"],
        "missing_context_fields": _string_list(payload.get("missing_context_fields"))
        or watchability["missing_context_fields"],
        "opportunity_script_repair_applied": _bool(payload.get("opportunity_script_repair_applied")),
        "opportunity_script_repair_reason": _clean(payload.get("opportunity_script_repair_reason")),
        "extra_context": _clean_multiline(payload.get("extra_context")),
        "watchability_positive_signals": _string_list(payload.get("watchability_positive_signals"))
        or watchability["watchability_positive_signals"],
        "watchability_negative_signals": _string_list(payload.get("watchability_negative_signals"))
        or watchability["watchability_negative_signals"],
        "hook": _clean(payload.get("hook")),
        "script_lines": sanitize_narration_lines(
            payload.get("script_lines"), payload.get("cta")
        ),
        "cta": _clean(payload.get("cta")),
        "hashtags": _string_list(payload.get("hashtags")),
        "visual_context": _string_list(payload.get("visual_context")),
        "factual_brief": payload.get("factual_brief") if isinstance(payload.get("factual_brief"), dict) else {},
        "research_brief": payload.get("research_brief") if isinstance(payload.get("research_brief"), dict) else {},
        "research_cache_hit": _bool(payload.get("research_cache_hit")),
        "source_urls": _string_list(payload.get("source_urls")),
        "source_titles": _string_list(payload.get("source_titles")),
        "grounding_used": _bool(payload.get("grounding_used")),
        "grounding_available": _bool(payload.get("grounding_available")),
        "search_queries": _string_list(payload.get("search_queries")),
        "factual_grounding_used": _bool(payload.get("factual_grounding_used")),
        "factual_grounding_confidence": _clean(payload.get("factual_grounding_confidence")) or "low",
        "specificity_score": _float_or_none(payload.get("specificity_score")),
        "script_depth": _clean(payload.get("script_depth")) or "normal",
        "script_depth_label": _clean(payload.get("script_depth_label")) or "Normal",
        "narrative_style": _clean(payload.get("narrative_style")) or "dramatic",
        "narrative_style_label": _clean(payload.get("narrative_style_label")) or "Dramático",
        "narrative_plan": payload.get("narrative_plan") if isinstance(payload.get("narrative_plan"), dict) else {},
        "story_beats": payload.get("story_beats") if isinstance(payload.get("story_beats"), list) else [],
        "claim_evidence_pairs": payload.get("claim_evidence_pairs")
        if isinstance(payload.get("claim_evidence_pairs"), list)
        else [],
        "depth_score": _float_or_none(payload.get("depth_score")),
        "narrative_score": _float_or_none(payload.get("narrative_score")),
        "retention_score": _float_or_none(payload.get("retention_score")),
        "shallow_script_detected": _bool(payload.get("shallow_script_detected")),
        "narrative_repair_applied": _bool(payload.get("narrative_repair_applied")),
        "narrative_repair_reason": _clean(payload.get("narrative_repair_reason")),
        "requested_duration_seconds": _float_or_none(payload.get("requested_duration_seconds")),
        "duration_preset_label": _clean(payload.get("duration_preset_label")),
        "script_word_count": _int(payload.get("script_word_count")),
        "narration_word_count": _int(payload.get("narration_word_count")),
        "narration_text_preview": _clean(payload.get("narration_text_preview")),
        "force_research_used": _bool(payload.get("force_research_used")),
        "llm_call_count": _int(payload.get("llm_call_count")),
        "research_call_count": _int(payload.get("research_call_count")),
        "script_call_count": _int(payload.get("script_call_count")),
        "last_llm_error": _clean(payload.get("last_llm_error")),
        "last_llm_provider": _clean(payload.get("last_llm_provider")),
        "last_llm_model": _clean(payload.get("last_llm_model")),
        "engine_mode": _engine_mode(payload.get("engine_mode")),
        "provider": _provider(payload.get("provider")),
        "fallback_used": _bool(payload.get("fallback_used")),
        "fact_check_notes": _string_list(payload.get("fact_check_notes")),
        "estimated_duration_seconds": _float_or_none(payload.get("estimated_duration_seconds")),
        "voice_style": _clean(payload.get("voice_style")),
        "pacing": _clean(payload.get("pacing")),
        "script_quality_score": _float_or_none(payload.get("script_quality_score")) or quality["script_quality_score"],
        "script_quality_tier": _clean(payload.get("script_quality_tier")) or quality["script_quality_tier"],
        "script_quality_score_heuristic": _float_or_none(payload.get("script_quality_score_heuristic")),
        "script_quality_tier_heuristic": _clean(payload.get("script_quality_tier_heuristic")),
        "judge_used": _bool(payload.get("judge_used")),
        "judge_overall": _float_or_none(payload.get("judge_overall")),
        "judge_tier": _clean(payload.get("judge_tier")),
        "judge_verdict": _clean(payload.get("judge_verdict")),
        "judge_hook_score": _float_or_none(payload.get("judge_hook_score")),
        "judge_retention_score": _float_or_none(payload.get("judge_retention_score")),
        "judge_specificity_score": _float_or_none(payload.get("judge_specificity_score")),
        "judge_naturalness_score": _float_or_none(payload.get("judge_naturalness_score")),
        "judge_strengths": _string_list(payload.get("judge_strengths")),
        "judge_weaknesses": _string_list(payload.get("judge_weaknesses")),
        "judge_critique": _clean(payload.get("judge_critique")),
        "judge_suggested_hook": _clean(payload.get("judge_suggested_hook")),
        "judge_rewrites_applied": _int(payload.get("judge_rewrites_applied")),
        "judge_model": _clean(payload.get("judge_model")),
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
        "visual_status": _visual_status(payload.get("visual_status")),
        "visual_items": _visual_items(payload.get("visual_items")),
        "voice_status": _voice_status(payload.get("voice_status")),
        "voice_name": _clean(payload.get("voice_name")),
        "voice_provider": _clean(payload.get("voice_provider")),
        "voice_rate": _clean(payload.get("voice_rate")),
        "voice_pitch": _clean(payload.get("voice_pitch")),
        "voice_audio_path": _clean(payload.get("voice_audio_path")),
        "voice_audio_url": _clean(payload.get("voice_audio_url")),
        "voice_words_path": _clean(payload.get("voice_words_path")),
        "voice_word_count": _int(payload.get("voice_word_count")),
        "voice_captions_path": _clean(payload.get("voice_captions_path")),
        "voice_caption_count": _int(payload.get("voice_caption_count")),
        "voice_words_source": _clean(payload.get("voice_words_source")),
        "narration_text": _clean_multiline(payload.get("narration_text")),
        "narration_style": _clean(payload.get("narration_style")),
        "narration_style_label": _clean(payload.get("narration_style_label")),
        "narration_polished_by": _clean(payload.get("narration_polished_by")),
        "voice_duration_seconds": _float_or_none(payload.get("voice_duration_seconds")),
        "voice_generated_at": _clean(payload.get("voice_generated_at")),
        "voice_error": _clean(payload.get("voice_error")),
        "voice_outdated": _bool(payload.get("voice_outdated")),
        "render_status": _render_status(payload.get("render_status")),
        "render_job_id": _clean(payload.get("render_job_id")),
        "render_video_path": _clean(payload.get("render_video_path")),
        "render_video_url": _clean(payload.get("render_video_url")),
        "render_thumbnail_path": _clean(payload.get("render_thumbnail_path")),
        "render_thumbnail_url": _clean(payload.get("render_thumbnail_url")),
        "render_duration_seconds": _float_or_none(payload.get("render_duration_seconds")),
        "render_segment_count": _int(payload.get("render_segment_count")),
        "render_width": _int(payload.get("render_width")),
        "render_height": _int(payload.get("render_height")),
        "render_generated_at": _clean(payload.get("render_generated_at")),
        "render_error": _clean(payload.get("render_error")),
        "visual_fallback_used": _bool(payload.get("visual_fallback_used")),
        "visual_fallback_reason": _clean(payload.get("visual_fallback_reason")),
        "auto_status": _clean(payload.get("auto_status")),
        "auto_job_id": _clean(payload.get("auto_job_id")),
        "auto_error": _clean(payload.get("auto_error")),
        # Bilingual "generate once": clone projects point back to their base project.
        "bilingual_parent": _clean(payload.get("bilingual_parent")),
        "bilingual_base_language": _clean(payload.get("bilingual_base_language")),
        "persona": _clean(payload.get("persona")),
        "persona_label": _clean(payload.get("persona_label")),
        "scriptwriter": _clean_multiline(payload.get("scriptwriter")),
        "music_mood": _clean(payload.get("music_mood")),
        "visual_style": _clean(payload.get("visual_style")),
        "posted_platform": _clean(payload.get("posted_platform")),
        "posted_url": _clean(payload.get("posted_url")),
        "posted_video_id": _clean(payload.get("posted_video_id")),
        "posted_at": _clean(payload.get("posted_at")),
        "posted_notes": _clean_multiline(payload.get("posted_notes")),
        "metric_views": _int(payload.get("metric_views")),
        "metric_likes": _int(payload.get("metric_likes")),
        "metric_comments": _int(payload.get("metric_comments")),
        "metric_retention": _float_or_none(payload.get("metric_retention")),
        "metric_ctr": _float_or_none(payload.get("metric_ctr")),
        "metrics_updated_at": _clean(payload.get("metrics_updated_at")),
        "publish_titles": _string_list(payload.get("publish_titles")),
        "publish_description": _clean_multiline(payload.get("publish_description")),
        "publish_hashtags": _string_list(payload.get("publish_hashtags")),
        "publish_best_times": _clean_multiline(payload.get("publish_best_times")),
        "publish_generated_at": _clean(payload.get("publish_generated_at")),
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
    return text if text in {"idea", "script", "ready_for_voice", "ready_for_visual", "ready_for_render", "rendered", "archived"} else "idea"


def _render_status(value: object) -> str:
    text = str(value or "none").strip().lower()
    return text if text in {"none", "queued", "rendering", "ready", "failed", "cancelled", "stale"} else "none"


def _visual_status(value: object) -> str:
    text = str(value or "none")
    return text if text in {"none", "draft", "ready", "failed"} else "none"


def _creation_mode(value: object) -> str:
    text = str(value or "legacy").strip().lower()
    return text if text in {"opportunity", "manual_idea", "ready_script", "legacy"} else "legacy"


def _creation_mode_label(value: object, label: object = "") -> str:
    explicit = _clean(label)
    if explicit:
        return explicit
    return {
        "opportunity": "Em alta",
        "manual_idea": "Minha ideia",
        "ready_script": "Roteiro pronto",
        "legacy": "Legado",
    }[_creation_mode(value)]


def _script_import_status(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"parsed", "needs_review", "failed"} else ""


def _visual_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            items.append(item)
    return items


def _engine_mode(value: object) -> str:
    text = str(value or "local").strip().lower()
    return text if text in {"local", "canal_dark"} else "local"


def _provider(value: object) -> str:
    text = str(value or "none").strip().lower()
    return text if text in {"none", "gemini", "openai"} else "none"


def _voice_status(value: object) -> str:
    text = str(value or "none")
    return text if text in {"none", "generating", "ready", "failed"} else "none"


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim"}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_multiline(value: object) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(value or "").splitlines()]
    return "\n".join(line for line in lines if line)


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


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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
