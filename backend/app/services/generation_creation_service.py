from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.services.generation_narrative_quality_service import (
    claim_evidence_pairs_from_brief,
    generate_narrative_plan,
    score_narrative_quality,
)
from app.services.generation_opportunity_service import normalize_opportunity
from app.services.generation_script_quality_service import score_generation_script
from app.services.generation_visual_service import suggest_visuals_for_project
from app.services.generation_voice_service import VoiceGenerationError, generate_voice_for_project
from app.services.generation_workspace_service import create_project, generate_script, get_project, update_project


def create_project_from_idea(
    idea: str,
    niche: str = "",
    language: str = "pt-BR",
    tone: str = "curioso",
    duration_seconds: int = 90,
    script_depth: str = "normal",
    narrative_style: str = "dramatic",
    auto_generate_script: bool = True,
    auto_generate_voice: bool = False,
    auto_suggest_visuals: bool = False,
    force_research: bool = False,
    content_format: str = "manual_topic",
    extra_context: str = "",
) -> dict[str, Any]:
    created_at = _now()
    base = {
        "title": _title_from_input(idea),
        "idea": idea,
        "niche": niche,
        "language": language,
        "tone": tone,
        "status": "idea",
        "creation_mode": "manual_idea",
        "creation_mode_label": "Minha ideia",
        "input_topic": idea,
        "input_idea": idea,
        "input_script": "",
        "input_niche": niche,
        "input_language": language,
        "input_tone": tone,
        "input_created_at": created_at,
        "requested_duration_seconds": duration_seconds,
        "script_depth": script_depth,
        "narrative_style": narrative_style,
        "content_format": content_format,
        "extra_context": extra_context,
    }
    if auto_generate_script:
        script = generate_script(
            idea=idea,
            niche=niche,
            topic=idea,
            duration_seconds=duration_seconds,
            tone=tone,
            language=language,
            force_research=force_research,
            script_depth=script_depth,
            narrative_style=narrative_style,
            content_format=content_format,
            extra_context=extra_context,
        )
        base.update(script)
        base.update({"idea": idea, "status": "ready_for_voice"})
    project = create_project(base)
    return _run_optional_steps(project, auto_generate_voice, auto_suggest_visuals)


def create_project_from_script(
    script: str,
    title: str = "",
    niche: str = "",
    language: str = "pt-BR",
    tone: str = "curioso",
    duration_seconds: int = 90,
    auto_generate_voice: bool = False,
    auto_suggest_visuals: bool = True,
) -> dict[str, Any]:
    parsed = parse_ready_script(script, title, niche, language, tone, duration_seconds)
    project = create_project(parsed)
    return _run_optional_steps(project, auto_generate_voice, auto_suggest_visuals)


def parse_ready_script(
    script: str,
    title: str,
    niche: str,
    language: str,
    tone: str,
    duration_seconds: int,
) -> dict[str, Any]:
    original = str(script or "").strip()
    units = _script_units(original)
    hook = units[0] if units else ""
    cta = units[-1] if len(units) > 2 and _looks_like_cta(units[-1]) else ""
    body_end = -1 if cta else None
    lines = units[1:body_end]
    if not lines and len(units) > 1:
        lines = units[1:]
    if not lines and hook:
        lines = [hook]
        hook = ""

    words = re.findall(r"\b[\wÀ-ÿ]+\b", original)
    estimated = max(1, round(len(words) / 2.45))
    if not original:
        import_status = "failed"
        warnings = ["Não foi possível identificar texto no roteiro enviado."]
    elif len(words) >= 40 and len(units) >= 3:
        import_status = "parsed"
        warnings = []
    else:
        import_status = "needs_review"
        warnings = ["Seu roteiro foi importado, mas talvez precise revisão."]
    research_brief = _brief_from_ready_script(original, title, niche)
    narrative_plan = generate_narrative_plan(
        research_brief=research_brief,
        duration_seconds=duration_seconds or estimated,
        script_depth="normal",
        narrative_style="dramatic",
    )
    visual_context = _visual_context_from_script(units, niche)
    payload: dict[str, Any] = {
        "title": title.strip() or _title_from_input(hook or original),
        "idea": title.strip() or _title_from_input(original),
        "niche": niche,
        "language": language,
        "tone": tone or "curioso",
        "status": "ready_for_voice",
        "creation_mode": "ready_script",
        "creation_mode_label": "Roteiro pronto",
        "input_topic": title,
        "input_idea": title,
        "input_script": original,
        "input_niche": niche,
        "input_language": language,
        "input_tone": tone,
        "input_created_at": _now(),
        "script_import_status": import_status,
        "content_format": "ready_script",
        "content_format_label": "Roteiro pronto",
        "creation_warnings": warnings,
        "hook": hook,
        "script_lines": lines,
        "cta": cta,
        "hashtags": [],
        "visual_context": visual_context,
        "fact_check_notes": _fact_check_notes(original),
        "factual_brief": research_brief,
        "research_brief": research_brief,
        "narrative_plan": narrative_plan,
        "story_beats": narrative_plan.get("story_beats", []),
        "claim_evidence_pairs": claim_evidence_pairs_from_brief(research_brief, narrative_plan),
        "requested_duration_seconds": duration_seconds,
        "estimated_duration_seconds": estimated,
        "narration_word_count": len(words),
        "script_word_count": len(re.findall(r"\b[\wÀ-ÿ]+\b", " ".join(lines))),
        "narration_text_preview": original[:280],
        "script_depth": "normal",
        "script_depth_label": "Normal",
        "narrative_style": "dramatic",
        "narrative_style_label": "Dramático",
        "provider": "none",
        "engine_mode": "local",
        "fallback_used": True,
    }
    quality = score_generation_script(payload)
    narrative_quality = score_narrative_quality(payload)
    payload.update(quality)
    payload.update(
        {
            "depth_score": narrative_quality["depth_score"],
            "narrative_score": narrative_quality["narrative_score"],
            "retention_score": narrative_quality["retention_score"],
            "shallow_script_detected": narrative_quality["shallow_script_detected"],
            "script_positive_signals": list(
                dict.fromkeys(quality["script_positive_signals"] + narrative_quality["script_positive_signals"])
            ),
            "script_negative_signals": list(
                dict.fromkeys(quality["script_negative_signals"] + narrative_quality["script_negative_signals"])
            ),
        }
    )
    return payload


def create_project_from_opportunity(
    opportunity: dict[str, Any],
    duration_seconds: int = 90,
    script_depth: str = "normal",
    narrative_style: str = "documentary",
    auto_generate_script: bool = True,
    auto_generate_voice: bool = False,
    auto_suggest_visuals: bool = False,
    force_research: bool = False,
    extra_context: str = "",
) -> dict[str, Any]:
    opportunity_payload = dict(opportunity)
    if extra_context:
        opportunity_payload["extra_context"] = extra_context
    normalized = normalize_opportunity(
        opportunity_payload,
        niche=str(opportunity.get("niche") or ""),
        time_window=str(opportunity.get("freshness") or "week"),
        provider=str(opportunity.get("provider") or "local"),
    )
    idea = " — ".join(
        part for part in [normalized["topic"], normalized["angle"], normalized["why_now"]] if part
    )
    base = {
        "title": normalized["suggested_video_title"] or normalized["title"],
        "idea": idea or normalized["title"],
        "niche": normalized["niche"],
        "language": str(opportunity.get("language") or "pt-BR"),
        "tone": str(opportunity.get("tone") or "curioso"),
        "status": "idea",
        "creation_mode": "opportunity",
        "creation_mode_label": "Em alta",
        "input_topic": normalized["topic"],
        "input_idea": idea,
        "input_script": "",
        "input_niche": normalized["niche"],
        "input_language": str(opportunity.get("language") or "pt-BR"),
        "input_tone": str(opportunity.get("tone") or "curioso"),
        "input_created_at": _now(),
        "opportunity_data": normalized,
        "requested_duration_seconds": duration_seconds,
        "script_depth": script_depth,
        "narrative_style": narrative_style,
        "content_format": normalized["content_format"],
        "content_format_label": normalized["content_format_label"],
        "concrete_promise": normalized["concrete_promise"],
        "viewer_reason_to_watch": normalized["viewer_reason_to_watch"],
        "needs_more_context": normalized["needs_more_context"],
        "missing_context_fields": normalized["missing_context_fields"],
        "extra_context": extra_context,
        "creation_warnings": (
            ["Essa oportunidade precisa de mais contexto para gerar um vídeo bom."]
            if normalized["needs_more_context"]
            else []
        ),
    }
    if auto_generate_script:
        generated = generate_script(
            idea=idea or normalized["title"],
            niche=normalized["niche"],
            topic=normalized["topic"] or normalized["title"],
            duration_seconds=duration_seconds,
            tone=base["tone"],
            language=base["language"],
            force_research=force_research,
            script_depth=script_depth,
            narrative_style=narrative_style,
            content_format=normalized["content_format"],
            extra_context=extra_context,
            opportunity_data=normalized,
        )
        generated["source_urls"] = list(
            dict.fromkeys([*(generated.get("source_urls") or []), *normalized["source_urls"]])
        )
        generated["source_titles"] = list(
            dict.fromkeys([*(generated.get("source_titles") or []), *normalized["source_titles"]])
        )
        for brief_key in ("research_brief", "factual_brief"):
            brief = dict(generated.get(brief_key) or {})
            brief.update(
                {
                    "topic": normalized["topic"] or normalized["title"],
                    "why_now": normalized["why_now"],
                    "angle": normalized["angle"],
                    "source_urls": generated["source_urls"],
                    "source_titles": generated["source_titles"],
                    "confidence": normalized["confidence"],
                }
            )
            generated[brief_key] = brief
        base.update(generated)
        base.update({"idea": idea or normalized["title"], "status": "ready_for_voice"})
    project = create_project(base)
    return _run_optional_steps(project, auto_generate_voice, auto_suggest_visuals)


def create_projects_from_opportunities_batch(
    opportunities: list[dict[str, Any]],
    duration_seconds: int = 90,
    script_depth: str = "normal",
    narrative_style: str = "documentary",
    auto_generate_script: bool = True,
    auto_generate_voice: bool = False,
    auto_suggest_visuals: bool = False,
    max_projects: int = 3,
) -> list[dict[str, Any]]:
    limit = max(1, min(5, int(max_projects or 3)))
    return [
        create_project_from_opportunity(
            opportunity=item,
            duration_seconds=duration_seconds,
            script_depth=script_depth,
            narrative_style=narrative_style,
            auto_generate_script=auto_generate_script,
            auto_generate_voice=auto_generate_voice,
            auto_suggest_visuals=auto_suggest_visuals,
        )
        for item in opportunities[:limit]
        if isinstance(item, dict)
    ]


def _run_optional_steps(
    project: dict[str, Any],
    auto_generate_voice: bool,
    auto_suggest_visuals: bool,
) -> dict[str, Any]:
    current = project
    warnings = list(current.get("creation_warnings") or [])
    if auto_generate_voice and current.get("script_lines"):
        try:
            result = generate_voice_for_project(
                current["project_id"],
                voice="pt-BR-AntonioNeural",
            )
            current = result.get("project") or current
        except VoiceGenerationError as error:
            warnings.append(error.message)
    if auto_suggest_visuals and current.get("script_lines"):
        current = suggest_visuals_for_project(current["project_id"]) or current
    if warnings:
        current = update_project(
            current["project_id"],
            {**current, "creation_warnings": warnings},
        ) or current
    return get_project(current["project_id"]) or current


def _script_units(script: str) -> list[str]:
    paragraphs = [re.sub(r"\s+", " ", line).strip() for line in script.splitlines() if line.strip()]
    if len(paragraphs) >= 3:
        return paragraphs
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", script).strip())
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _looks_like_cta(line: str) -> bool:
    normalized = line.lower()
    return line.strip().endswith("?") or any(
        marker in normalized for marker in ["comenta", "compartilha", "salva", "segue", "o que você acha"]
    )


def _brief_from_ready_script(script: str, title: str, niche: str) -> dict[str, Any]:
    units = _script_units(script)
    return {
        "subject": title or (units[0] if units else "Roteiro importado"),
        "topic": title or (units[0] if units else niche),
        "summary": " ".join(units[:2]),
        "key_entities": _capitalized_entities(script),
        "key_facts": units[:6],
        "timeline": units[:6],
        "conflict": units[1] if len(units) > 1 else "",
        "consequence": units[-2] if len(units) > 2 else "",
        "emotional_angle": "Impacto humano e consequência do tema apresentado.",
        "confidence": "low",
        "source_urls": [],
        "source_titles": [],
        "fact_check_notes": _fact_check_notes(script),
        "grounding_used": False,
    }


def _visual_context_from_script(units: list[str], niche: str) -> list[str]:
    contexts = [f"B-roll vertical para: {unit}" for unit in units[:6]]
    if not contexts:
        contexts = [f"B-roll faceless relacionado a {niche or 'tema principal'}"]
    return contexts


def _fact_check_notes(script: str) -> list[str]:
    notes: list[str] = []
    if re.search(r"\b(18|19|20)\d{2}\b", script):
        notes.append("Confirmar datas citadas no roteiro importado.")
    if re.search(r"\b\d+(?:[.,]\d+)?%\b", script):
        notes.append("Confirmar percentuais e dados numéricos.")
    if any(term in script.lower() for term in ["provou", "causou", "sempre", "nunca", "único motivo"]):
        notes.append("Revisar afirmações absolutas e separar fato de interpretação.")
    return notes


def _capitalized_entities(script: str) -> list[str]:
    items = re.findall(r"\b[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][\wÀ-ÿ-]{2,}(?:\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][\wÀ-ÿ-]{2,})*", script)
    return list(dict.fromkeys(items[:10]))


def _title_from_input(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    first = re.split(r"[.!?\n]", text)[0].strip()
    return (first or "Novo projeto de geração")[:90]


def _now() -> str:
    return datetime.utcnow().isoformat()
