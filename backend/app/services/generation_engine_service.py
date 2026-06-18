from __future__ import annotations

import json
import re
from typing import Any

import requests

from app import config
from app.services.generation_factual_grounding_service import (
    repair_generic_script_with_brief,
    validate_specificity,
)
from app.services.generation_llm_provider_service import (
    generate_ideas as provider_generate_ideas,
    generate_narrative_plan as provider_generate_narrative_plan,
    generate_research_brief as provider_generate_research_brief,
    generate_script_from_research as provider_generate_script_from_research,
    get_provider_status,
    sanitize_narration_lines,
)
from app.services.generation_narrative_quality_service import (
    build_script_from_narrative_plan,
    claim_evidence_pairs_from_brief,
    generate_narrative_plan as local_generate_narrative_plan,
    narrative_style_label,
    normalize_narrative_style,
    normalize_script_depth,
    repair_shallow_script_with_narrative_plan,
    score_narrative_quality,
    script_depth_label,
)
from app.services.generation_script_judge_service import evaluate_and_improve
from app.services.generation_script_quality_service import (
    score_generation_script,
    validate_script_is_narration,
)
from app.services.generation_watchability_service import (
    build_format_script,
    context_from_text,
    enrich_opportunity_context,
    normalize_content_format,
    opportunity_research_brief,
    repair_generic_opportunity_script,
    score_watchability,
)


VALID_MODES = {"local", "canal_dark"}
VALID_PROVIDERS = {"none", "gemini", "openai"}

CANAL_DARK_FEATURES = [
    "trend_scout_criteria",
    "hook_first_script",
    "visual_context",
    "fact_check_notes",
    "guardrail_ready_metadata",
]


def engine_status() -> dict[str, Any]:
    mode = _engine_mode()
    provider = _provider()
    provider_status = get_provider_status()
    external_available = provider in {"gemini", "openai"} and bool(provider_status.get("external_available"))
    return {
        "engine_mode": mode,
        "provider": provider,
        "configured_engine": config.GENERATION_ENGINE,
        "configured_provider": config.GENERATION_AI_PROVIDER,
        "external_ai_available": external_available,
        "gemini_available": bool(provider_status["gemini_available"]),
        "grounding_enabled": bool(provider_status["grounding_enabled"]),
        "grounding_supported": provider_status["grounding_supported"],
        "fallback_available": True,
        "require_external_ai": config.GENERATION_REQUIRE_EXTERNAL_AI,
        "gemini_configured": bool(provider_status["gemini_configured"]),
        "gemini_model": config.GEMINI_SCRIPT_MODEL,
        "models": provider_status["models"],
        "limits": provider_status["limits"],
        "features": {
            "ideas": True,
            "research_brief": True,
            "scripts": True,
            "voice": True,
            "visual_planning": False,
            "render": False,
            "publishing": False,
        },
        "feature_names": CANAL_DARK_FEATURES if mode == "canal_dark" else ["local_templates"],
    }


def generate_engine_ideas(
    niche: str,
    topic: str = "",
    language: str = "pt-BR",
    tone: str = "curioso",
) -> list[dict[str, Any]]:
    mode = _engine_mode()
    provider = _provider()
    if mode == "canal_dark" and provider in {"gemini", "openai"}:
        return provider_generate_ideas(
            niche=niche,
            topic=topic,
            language=language,
            tone=tone,
            local_fallback=lambda: _local_ideas(
                niche, topic, language, tone, mode, provider, fallback_used=True
            ),
        )
    if mode == "canal_dark" and config.GENERATION_REQUIRE_EXTERNAL_AI:
        raise RuntimeError("external_generation_ai_unavailable")
    return _local_ideas(
        niche=niche,
        topic=topic,
        language=language,
        tone=tone,
        mode=mode,
        provider=provider,
        fallback_used=mode == "canal_dark" and provider != "none",
    )


def generate_engine_script(
    idea: str,
    niche: str = "",
    topic: str = "",
    duration_seconds: int = 45,
    duration_preset: str = "",
    tone: str = "curioso",
    language: str = "pt-BR",
    force_research: bool = False,
    provider_override: str = "auto",
    script_depth: str = "normal",
    narrative_style: str = "",
    content_format: str = "manual_topic",
    extra_context: str = "",
    opportunity_data: dict[str, Any] | None = None,
    scriptwriter: str = "",
) -> dict[str, Any]:
    mode = _engine_mode()
    if provider_override == "auto":
        provider = _provider()
    elif provider_override in {"gemini", "openai"}:
        provider = provider_override
    else:
        provider = "none"
    duration = _normalize_duration(duration_seconds, duration_preset)
    depth = normalize_script_depth(script_depth)
    style = normalize_narrative_style(narrative_style, tone=tone)
    parsed_context = context_from_text(extra_context)
    opportunity_seed = dict(opportunity_data or {})
    for key, value in parsed_context.items():
        if value:
            opportunity_seed[key] = value
    opportunity = enrich_opportunity_context(opportunity_seed)
    fmt = normalize_content_format(content_format or opportunity.get("content_format"), "opportunity" if opportunity_data else "")
    research_topic = " — ".join(part for part in [topic or idea, extra_context] if _clean(part))
    factual_brief = provider_generate_research_brief(
        niche=niche,
        topic=research_topic,
        language=language,
        tone=tone,
        force_research=force_research,
        provider_override=provider_override,
    )
    if opportunity_data:
        factual_brief = opportunity_research_brief(opportunity, factual_brief)
    elif extra_context:
        factual_brief.update(context_from_text(extra_context))
        factual_brief["extra_context"] = extra_context
        factual_brief["content_format"] = fmt
    narrative_plan = provider_generate_narrative_plan(
        research_brief=factual_brief,
        duration_seconds=duration,
        script_depth=depth,
        narrative_style=style,
        provider_override=provider_override,
        local_fallback=lambda: local_generate_narrative_plan(factual_brief, duration, depth, style),
    )
    if mode == "canal_dark" and provider in {"gemini", "openai"}:
        def _build_gemini_script(critique: str = "") -> dict[str, Any]:
            payload = provider_generate_script_from_research(
                research_brief=factual_brief,
                narrative_plan=narrative_plan,
                niche=niche,
                topic=topic or idea,
                duration_seconds=duration,
                tone=tone,
                language=language,
                script_depth=depth,
                narrative_style=style,
                local_fallback=lambda: _local_script(
                    idea, niche, topic, duration, tone, language, mode, provider, True, factual_brief, narrative_plan, depth, style
                ),
                provider_override=provider_override,
                critique=critique,
                scriptwriter=scriptwriter,
            )
            payload.setdefault("factual_brief", factual_brief)
            payload.setdefault("research_brief", factual_brief)
            payload.setdefault("fact_check_notes", factual_brief.get("fact_check_notes", []))
            payload.setdefault("estimated_duration_seconds", duration)
            payload.setdefault("duration_seconds", duration)
            payload["requested_duration_seconds"] = duration
            payload["duration_preset_label"] = _duration_label(duration)
            payload["force_research_used"] = bool(force_research)
            _apply_narrative_metadata(payload, narrative_plan, factual_brief, depth, style)
            payload.setdefault("voice_style", _voice_style(tone))
            payload.setdefault("pacing", "narrativo, direto e com pausas curtas")
            payload.setdefault("niche", _clean(niche) or "geral")
            payload.setdefault("language", language or "pt-BR")
            payload.setdefault("tone", tone or "curioso")
            payload.setdefault("status", "script")
            payload.setdefault("script_repair_applied", False)
            payload.setdefault("script_repair_reason", "")
            payload.update(
                {
                    "content_format": fmt,
                    "extra_context": extra_context,
                    "opportunity_data": opportunity if opportunity_data else {},
                    "concrete_promise": opportunity.get("concrete_promise", ""),
                    "viewer_reason_to_watch": opportunity.get("viewer_reason_to_watch", ""),
                }
            )
            return _finalize_script_payload(payload, topic or idea, niche, tone, depth, style)

        payload = _build_gemini_script()
        return evaluate_and_improve(
            payload,
            regenerate=_build_gemini_script,
            provider_override=provider_override,
        )
    if mode == "canal_dark" and config.GENERATION_REQUIRE_EXTERNAL_AI:
        raise RuntimeError("external_generation_ai_unavailable")
    payload = _local_script(
        idea=idea,
        niche=niche,
        topic=topic,
        duration_seconds=duration,
        tone=tone,
        language=language,
        mode=mode,
        provider=provider,
        fallback_used=mode == "canal_dark" and provider != "none",
        factual_brief=factual_brief,
        narrative_plan=narrative_plan,
        script_depth=depth,
        narrative_style=style,
    )
    payload.update(
        {
            "content_format": fmt,
            "extra_context": extra_context,
            "opportunity_data": opportunity if opportunity_data else {},
            "concrete_promise": opportunity.get("concrete_promise", ""),
            "viewer_reason_to_watch": opportunity.get("viewer_reason_to_watch", ""),
        }
    )
    template = build_format_script(fmt, {**opportunity, **factual_brief, "extra_context": extra_context}, duration)
    if template:
        payload.update(template)
    return _finalize_script_payload(payload, topic or idea, niche, tone, depth, style)


def _local_ideas(
    niche: str,
    topic: str,
    language: str,
    tone: str,
    mode: str,
    provider: str,
    fallback_used: bool,
) -> list[dict[str, Any]]:
    niche_label = _clean(niche) or "curiosidades"
    topic_label = _clean(topic) or _default_topic(niche_label)
    normalized_niche = _normalize(niche_label)
    angles = _angles_for(normalized_niche)
    emotion = _emotion_for(tone, normalized_niche)
    ideas: list[dict[str, Any]] = []
    for index, angle in enumerate(angles, start=1):
        title = f"{topic_label}: {angle}"
        curiosity_gap = _curiosity_gap(topic_label, angle)
        fact_check_needed = normalized_niche in {"politica", "política", "saude", "saúde", "true crime"}
        ideas.append(
            {
                "idea_id": f"idea_{index}",
                "title": title,
                "niche": niche_label,
                "topic": topic_label,
                "angle": angle,
                "hook": _hook_for(topic_label, angle, tone),
                "why_it_might_work": _why_it_works(niche_label, angle, tone),
                "target_emotion": emotion,
                "curiosity_gap": curiosity_gap,
                "risk_level": "medium" if fact_check_needed or _normalize(tone) in {"polemico", "polêmico"} else "low",
                "fact_check_needed": fact_check_needed,
                "suggested_hashtags": _hashtags(niche_label, topic_label, language),
                "visual_direction": _visual_direction(niche_label, topic_label, angle),
                "engine_mode": mode,
                "provider": provider,
                "fallback_used": fallback_used,
                "language": language or "pt-BR",
                "tone": tone or "curioso",
            }
        )
    return ideas[:6]


def _local_script(
    idea: str,
    niche: str,
    topic: str,
    duration_seconds: int,
    tone: str,
    language: str,
    mode: str,
    provider: str,
    fallback_used: bool,
    factual_brief: dict[str, Any],
    narrative_plan: dict[str, Any],
    script_depth: str = "normal",
    narrative_style: str = "dramatic",
) -> dict[str, Any]:
    idea_text = _clean(idea or topic) or "Uma ideia para explicar de forma simples"
    niche_label = _clean(niche) or "geral"
    normalized_niche = _normalize(niche_label)
    seconds = _normalize_duration(duration_seconds)
    grounded = build_script_from_narrative_plan(
        research_brief=factual_brief,
        narrative_plan=narrative_plan,
        duration_seconds=seconds,
        script_depth=script_depth,
        narrative_style=narrative_style,
    )
    hook = _clean(grounded.get("hook")) or _script_hook(idea_text, tone)
    lines = _list(grounded.get("script_lines")) or _script_lines(
        idea_text, niche_label, seconds, tone, factual_brief
    )
    fact_notes = _fact_notes(normalized_niche, lines)
    fact_notes = list(dict.fromkeys(fact_notes + [str(item) for item in factual_brief.get("fact_check_notes", [])]))
    payload: dict[str, Any] = {
        "title": _clean(grounded.get("title")) or _title_from_idea(idea_text),
        "hook": hook,
        "script_lines": lines,
        "cta": _cta_for(tone),
        "hashtags": _hashtags(niche_label, idea_text, language),
        "visual_context": _list(grounded.get("visual_context")) or _visual_context(niche_label, idea_text),
        "fact_check_notes": fact_notes,
        "factual_brief": factual_brief,
        "research_brief": factual_brief,
        "factual_grounding_used": factual_brief.get("confidence") != "low",
        "factual_grounding_confidence": factual_brief.get("confidence", "low"),
        "specificity_score": 0.0,
        "research_cache_hit": bool(factual_brief.get("research_cache_hit")),
        "source_urls": _list(factual_brief.get("source_urls")),
        "source_titles": _list(factual_brief.get("source_titles")),
        "search_queries": _list(factual_brief.get("search_queries")),
        "grounding_used": bool(factual_brief.get("grounding_used")),
        "grounding_available": bool(factual_brief.get("grounding_available")),
        "grounding_warning": _clean(factual_brief.get("grounding_warning")),
        "llm_call_count": int(factual_brief.get("research_call_count") or 0),
        "research_call_count": int(factual_brief.get("research_call_count") or 0),
        "script_call_count": 0,
        "last_llm_error": _clean(factual_brief.get("last_llm_error")),
        "last_llm_provider": _clean(factual_brief.get("last_llm_provider")) or provider,
        "last_llm_model": _clean(factual_brief.get("last_llm_model")),
        "estimated_duration_seconds": seconds,
        "duration_seconds": seconds,
        "requested_duration_seconds": seconds,
        "duration_preset_label": _duration_label(seconds),
        "force_research_used": bool(factual_brief.get("force_research_used")),
        "voice_style": _voice_style(tone),
        "pacing": "rápido, com pausas curtas depois do hook",
        "engine_mode": mode,
        "provider": provider,
        "fallback_used": fallback_used or provider == "none",
        "niche": niche_label,
        "language": language or "pt-BR",
        "tone": tone or "curioso",
        "status": "script",
        "script_repair_applied": False,
        "script_repair_reason": "",
    }
    _apply_narrative_metadata(payload, narrative_plan, factual_brief, script_depth, narrative_style)
    return _finalize_script_payload(payload, idea_text, niche_label, tone, script_depth, narrative_style)


def _ideas_with_gemini(niche: str, topic: str, language: str, tone: str) -> list[dict[str, Any]]:
    prompt = (
        "Você é um trend scout de shorts faceless. Gere 6 ideias em JSON array, "
        "com idea_id,title,niche,topic,angle,hook,why_it_might_work,target_emotion,"
        "curiosity_gap,risk_level,fact_check_needed,suggested_hashtags,visual_direction. "
        "Evite temas genéricos e use um ângulo específico, fact-checkable e com hook forte.\n"
        f"Nicho: {niche}\nTema: {topic}\nIdioma: {language}\nTom: {tone}"
    )
    items = _gemini_json(prompt)
    if not isinstance(items, list):
        raise ValueError("gemini_ideas_not_list")
    ideas: list[dict[str, Any]] = []
    for index, item in enumerate(items[:6], start=1):
        if not isinstance(item, dict):
            continue
        ideas.append(
            {
                **item,
                "idea_id": str(item.get("idea_id") or f"idea_{index}"),
                "engine_mode": "canal_dark",
                "provider": "gemini",
                "fallback_used": False,
                "suggested_hashtags": _list(item.get("suggested_hashtags")),
            }
        )
    if not ideas:
        raise ValueError("gemini_ideas_empty")
    return ideas


def _script_with_gemini(
    idea: str,
    niche: str,
    topic: str,
    duration_seconds: int,
    tone: str,
    language: str,
    factual_brief: dict[str, Any],
) -> dict[str, Any]:
    prompt = (
        "Você é um roteirista de shorts faceless. Responda somente JSON object com "
        "title,hook,script_lines,cta,hashtags,visual_context,fact_check_notes,factual_brief,"
        "estimated_duration_seconds,voice_style,pacing. Estrutura: hook em até 3s, "
        "Antes de escrever, use este factual_brief como base concreta e inclua fatos reais "
        "do brief no roteiro. Não gere roteiro abstrato. Não escreva 'um detalhe escondido' "
        "sem dizer qual é o detalhe. Não escreva 'uma consequência enorme' sem dizer qual "
        "consequência. "
        "contexto, insight inesperado, takeaway e CTA. script_lines deve conter SOMENTE "
        "frases finais de narração, exatamente como o narrador falaria no vídeo. Não escreva "
        "instruções de roteiro dentro de script_lines. Não escreva análise sobre o tema. "
        "Nunca use em script_lines frases como use uma imagem, mostre, feche com, explique, "
        "fale sobre, a ideia é, o roteiro deve, o tema parece ou a virada é. Instruções "
        "visuais devem ir apenas em visual_context. Fact-check deve ir apenas em "
        "fact_check_notes. Marque claims duvidosos em fact_check_notes.\n"
        f"Ideia: {idea}\nTema: {topic}\nNicho: {niche}\nDuração alvo: {duration_seconds}s\n"
        f"Factual brief: {json.dumps(factual_brief, ensure_ascii=False)}\n"
        f"Idioma: {language}\nTom: {tone}"
    )
    payload = _gemini_json(prompt)
    if not isinstance(payload, dict):
        raise ValueError("gemini_script_not_object")
    normalized = {
        "title": _clean(payload.get("title")) or _title_from_idea(idea),
        "hook": _clean(payload.get("hook")),
        "script_lines": _list(payload.get("script_lines") or payload.get("lines")),
        "cta": _clean(payload.get("cta")),
        "hashtags": _list(payload.get("hashtags")),
        "visual_context": _list(payload.get("visual_context")),
        "fact_check_notes": _list(payload.get("fact_check_notes")),
        "factual_brief": payload.get("factual_brief") if isinstance(payload.get("factual_brief"), dict) else factual_brief,
        "factual_grounding_used": True,
        "factual_grounding_confidence": factual_brief.get("confidence", "low"),
        "specificity_score": 0.0,
        "estimated_duration_seconds": int(payload.get("estimated_duration_seconds") or duration_seconds),
        "duration_seconds": int(payload.get("estimated_duration_seconds") or duration_seconds),
        "voice_style": _clean(payload.get("voice_style")) or _voice_style(tone),
        "pacing": _clean(payload.get("pacing")) or "rápido, com pausas curtas",
        "engine_mode": "canal_dark",
        "provider": "gemini",
        "fallback_used": False,
        "niche": _clean(niche) or "geral",
        "language": language or "pt-BR",
        "tone": tone or "curioso",
        "status": "script",
        "script_repair_applied": False,
        "script_repair_reason": "",
    }
    validation = validate_script_is_narration(normalized["script_lines"])
    if not validation["is_narration_ready"]:
        normalized["fallback_used"] = True
    return _finalize_script_payload(normalized, idea, niche, tone)


def _finalize_script_payload(
    payload: dict[str, Any],
    idea: str,
    niche: str,
    tone: str,
    script_depth: str = "normal",
    narrative_style: str = "dramatic",
) -> dict[str, Any]:
    depth = normalize_script_depth(payload.get("script_depth") or script_depth)
    style = normalize_narrative_style(payload.get("narrative_style") or narrative_style, tone=tone)
    factual_brief = payload.get("factual_brief") if isinstance(payload.get("factual_brief"), dict) else {}
    narrative_plan = payload.get("narrative_plan") if isinstance(payload.get("narrative_plan"), dict) else {}
    if not narrative_plan:
        narrative_plan = local_generate_narrative_plan(
            factual_brief,
            int(payload.get("requested_duration_seconds") or payload.get("estimated_duration_seconds") or 60),
            depth,
            style,
        )
    _apply_narrative_metadata(payload, narrative_plan, factual_brief, depth, style)
    # A real LLM script (OpenAI/Gemini) carries its own quality; the template
    # repairs below were built for the no-LLM fallback era and overwrite good,
    # simple narration with dense summary text. Skip them for LLM scripts and
    # let the prompt + LLM judge/rewrite loop handle quality instead.
    is_llm = payload.get("provider") in {"openai", "gemini"} and not payload.get("fallback_used")
    validation = validate_script_is_narration(payload.get("script_lines"))
    if not validation["is_narration_ready"]:
        repaired = repair_meta_script_to_narration(
            idea=idea,
            niche=niche,
            tone=tone,
            duration_seconds=int(payload.get("estimated_duration_seconds") or 45),
        )
        payload.update(repaired)
        payload["script_repair_applied"] = True
        reasons = list(validation.get("meta_hits") or []) + list(validation.get("instructional_hits") or [])
        payload["script_repair_reason"] = ", ".join(reasons[:5]) or "not_narration_ready"
    specificity = validate_specificity(
        script_lines=payload.get("script_lines"),
        factual_brief=factual_brief,
        topic=idea,
    )
    if not specificity["is_specific"] and factual_brief.get("confidence") != "low" and not is_llm:
        repaired = repair_generic_script_with_brief(
            factual_brief=factual_brief,
            tone=tone,
            duration_seconds=int(payload.get("estimated_duration_seconds") or 45),
        )
        payload.update(repaired)
        payload["script_repair_applied"] = True
        payload["script_repair_reason"] = "generic_script_without_specific_facts"
        specificity = validate_specificity(
            script_lines=payload.get("script_lines"),
            factual_brief=factual_brief,
            topic=idea,
        )
    payload["specificity_score"] = specificity["specificity_score"]
    payload["factual_grounding_used"] = "factual_grounding_used" in specificity["positive_signals"]
    positives = list(payload.get("script_positive_signals") or []) + specificity["positive_signals"]
    negatives = list(payload.get("script_negative_signals") or []) + specificity["negative_signals"]
    _add_duration_metadata(payload)
    requested_duration = _normalize_duration(payload.get("requested_duration_seconds"))
    if (
        factual_brief.get("confidence") != "low"
        and not is_llm
        and float(payload.get("estimated_duration_seconds") or 0) < requested_duration * 0.65
    ):
        repaired = repair_generic_script_with_brief(
            factual_brief=factual_brief,
            tone=tone,
            duration_seconds=requested_duration,
        )
        payload.update(repaired)
        payload["script_repair_applied"] = True
        payload["script_repair_reason"] = "duration_too_short_for_preset"
        specificity = validate_specificity(
            script_lines=payload.get("script_lines"),
            factual_brief=factual_brief,
            topic=idea,
        )
        payload["specificity_score"] = specificity["specificity_score"]
        positives += specificity["positive_signals"]
        negatives += specificity["negative_signals"]
        _add_duration_metadata(payload)
    narrative_quality = score_narrative_quality(payload)
    if narrative_quality["shallow_script_detected"] and factual_brief.get("confidence") != "low" and not is_llm:
        repaired = repair_shallow_script_with_narrative_plan(
            script=payload,
            research_brief=factual_brief,
            narrative_plan=narrative_plan,
            duration_seconds=requested_duration,
            script_depth=depth,
            narrative_style=style,
        )
        payload.update(repaired)
        payload["script_repair_applied"] = True
        payload["script_repair_reason"] = "shallow_script_rewritten_with_narrative_plan"
        payload["narrative_repair_applied"] = True
        payload["narrative_repair_reason"] = "shallow_script_rewritten_with_narrative_plan"
        _apply_narrative_metadata(payload, narrative_plan, factual_brief, depth, style)
        _add_duration_metadata(payload)
        narrative_quality = score_narrative_quality(payload)
    payload.update(score_generation_script(payload))
    payload.update(
        {
            "depth_score": narrative_quality["depth_score"],
            "narrative_score": narrative_quality["narrative_score"],
            "retention_score": narrative_quality["retention_score"],
            "shallow_script_detected": narrative_quality["shallow_script_detected"],
        }
    )
    positives += list(payload.get("script_positive_signals") or [])
    positives += narrative_quality["script_positive_signals"]
    negatives += list(payload.get("script_negative_signals") or [])
    negatives += narrative_quality["script_negative_signals"]
    payload["script_positive_signals"] = list(dict.fromkeys(positives))
    payload["script_negative_signals"] = list(dict.fromkeys(negatives))
    if payload.get("shallow_script_detected"):
        payload["script_quality_tier"] = "good" if payload.get("script_quality_score", 0) >= 6.5 else payload.get("script_quality_tier")
        payload["script_quality_score"] = min(float(payload.get("script_quality_score") or 0), 7.9)
    if payload.get("script_repair_applied"):
        negatives = list(payload.get("script_negative_signals") or [])
        negatives.append("script_repair_applied")
        payload["script_negative_signals"] = list(dict.fromkeys(negatives))
    watchability = score_watchability(payload)
    if (
        watchability["content_format"] in {"player_watchlist", "match_preview"}
        and watchability["watchability_score"] < 6.0
        and not is_llm
    ):
        payload = repair_generic_opportunity_script(
            payload,
            factual_brief,
            dict(payload.get("opportunity_data") or {}),
        )
        watchability = score_watchability(payload)
    payload.update(watchability)
    if (
        watchability["content_format"]
        in {"player_watchlist", "match_preview", "news_context", "top_list"}
        and watchability["watchability_score"] < 6.0
    ):
        payload["shallow_script_detected"] = True
        payload["script_quality_score"] = min(float(payload.get("script_quality_score") or 0), 6.4)
        payload["script_quality_tier"] = "average" if payload["script_quality_score"] >= 5 else "weak"
        payload["script_negative_signals"] = list(
            dict.fromkeys(
                [
                    *list(payload.get("script_negative_signals") or []),
                    *watchability["watchability_negative_signals"],
                ]
            )
        )
    # Final safety net: flatten any object/dict that a repair step left inside
    # script_lines (e.g. {factual, interpretation} from the narrative plan) and
    # drop a closing line that just duplicates the CTA.
    payload["script_lines"] = sanitize_narration_lines(
        payload.get("script_lines"), payload.get("cta")
    )
    return payload


def _apply_narrative_metadata(
    payload: dict[str, Any],
    narrative_plan: dict[str, Any],
    factual_brief: dict[str, Any],
    script_depth: str,
    narrative_style: str,
) -> None:
    depth = normalize_script_depth(script_depth)
    style = normalize_narrative_style(narrative_style)
    payload["script_depth"] = depth
    payload["script_depth_label"] = script_depth_label(depth)
    payload["narrative_style"] = style
    payload["narrative_style_label"] = narrative_style_label(style)
    payload["narrative_plan"] = narrative_plan if isinstance(narrative_plan, dict) else {}
    payload["story_beats"] = list(payload["narrative_plan"].get("story_beats") or [])
    payload["claim_evidence_pairs"] = claim_evidence_pairs_from_brief(factual_brief, payload["narrative_plan"])
    payload.setdefault("narrative_repair_applied", False)
    payload.setdefault("narrative_repair_reason", "")


def repair_meta_script_to_narration(
    idea: str,
    niche: str,
    tone: str = "curioso",
    duration_seconds: int = 45,
) -> dict[str, Any]:
    idea_text = _clean(idea) or _default_topic(niche or "geral")
    niche_label = _clean(niche) or "geral"
    topic = _topic_from_idea(idea_text)
    title = _narrative_title(topic, niche_label)
    hook = _script_hook(topic, tone)
    lines = _narration_lines(topic, niche_label, duration_seconds, tone)
    return {
        "title": title,
        "hook": hook,
        "script_lines": lines,
        "visual_context": _visual_context(niche_label, topic),
        "fact_check_notes": _fact_notes(_normalize(niche_label), lines),
        "estimated_duration_seconds": max(20, min(90, int(duration_seconds or 45))),
        "duration_seconds": max(20, min(90, int(duration_seconds or 45))),
        "voice_style": _voice_style(tone),
        "pacing": "narrativo, direto e com pausas dramáticas curtas",
    }


def _gemini_json(prompt: str) -> Any:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GENERATION_GEMINI_MODEL}:generateContent"
    )
    response = requests.post(
        url,
        params={"key": config.GEMINI_API_KEY},
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if match:
        text = match.group(1)
    return json.loads(text)


def _engine_mode() -> str:
    mode = config.GENERATION_ENGINE if config.GENERATION_ENGINE in VALID_MODES else "local"
    return mode


def _provider() -> str:
    provider = config.GENERATION_AI_PROVIDER
    return provider if provider in VALID_PROVIDERS else "none"


def _angles_for(niche: str) -> list[str]:
    by_niche = {
        "futebol": [
            "o detalhe de bastidor que muda a leitura do jogo",
            "a decisão que parece errada até você ver o contexto",
            "o personagem secundário que explica a polêmica",
            "o custo invisível de uma escolha técnica",
            "a fala que entregou mais do que parecia",
            "o erro que a torcida percebeu antes da comissão",
        ],
        "negocios": [
            "a escolha pequena que virou vantagem competitiva",
            "o custo invisível que quase ninguém calcula",
            "a estratégia simples que parece contraintuitiva",
            "o bastidor de dinheiro que muda a narrativa",
            "a decisão de timing que separou os vencedores",
            "o erro operacional que virou lição",
        ],
        "negócios": [
            "a escolha pequena que virou vantagem competitiva",
            "o custo invisível que quase ninguém calcula",
            "a estratégia simples que parece contraintuitiva",
            "o bastidor de dinheiro que muda a narrativa",
            "a decisão de timing que separou os vencedores",
            "o erro operacional que virou lição",
        ],
    }
    return by_niche.get(
        niche,
        [
            "o detalhe pouco contado que muda a história",
            "a pergunta que todo mundo faz, mas quase ninguém responde bem",
            "o contraste entre a versão popular e o que aconteceu",
            "o sinal ignorado antes da virada",
            "a decisão humana por trás do resultado",
            "a curiosidade que parece pequena, mas explica tudo",
        ],
    )


def _hook_for(topic: str, angle: str, tone: str) -> str:
    if _normalize(tone) in {"polemico", "polêmico"}:
        return f"Isso sobre {topic.lower()} vai dividir opiniões: {angle}."
    return f"Pouca gente percebe isso sobre {topic.lower()}: {angle}."


def _script_hook(idea: str, tone: str) -> str:
    if _is_world_cup_brazil(idea):
        return "Jogar uma Copa em casa parece uma vantagem... mas pode virar uma pressão impossível."
    if _normalize(tone) in {"polemico", "polêmico"}:
        return f"Isso aqui sobre {idea.lower()} não é tão óbvio quanto parece."
    if _normalize(tone) in {"dramatico", "dramático"}:
        return f"{idea} parece só uma história conhecida... até você perceber o peso por trás dela."
    return f"Tem um detalhe em {idea.lower()} que quase ninguém percebe."


def _script_lines(idea: str, niche: str, duration: int, tone: str, factual_brief: dict[str, Any]) -> list[str]:
    topic = _topic_from_idea(idea)
    return _narration_lines(topic, niche, duration, tone, factual_brief)


def _narration_lines(topic: str, niche: str, duration: int, tone: str, factual_brief: dict[str, Any]) -> list[str]:
    if factual_brief.get("confidence") != "low":
        repaired = repair_generic_script_with_brief(factual_brief, tone=tone, duration_seconds=duration)
        return list(repaired.get("script_lines") or [])
    if _is_world_cup_brazil(topic):
        lines = [
            "Quando a Copa do Mundo acontece no Brasil, não é só futebol.",
            "Cada jogo vira uma cobrança nacional.",
            "A torcida não espera apenas uma vitória. Ela espera uma confirmação de identidade.",
            "O problema é que essa pressão muda tudo: o jogador não entra em campo só para competir.",
            "Ele entra carregando a expectativa de milhões de pessoas.",
            "E quando algo dá errado, a derrota parece maior do que o placar.",
            "Parece uma ferida coletiva.",
            "Então fica a pergunta: jogar em casa ajuda... ou pesa ainda mais?",
        ]
        return lines if duration >= 40 else lines[:5] + [lines[-1]]
    lowered = topic.lower()
    lines = [
        f"Todo mundo olha para {lowered} como se a resposta fosse simples.",
        "Mas quase sempre existe um detalhe escondido no meio da história.",
        "Esse detalhe muda a forma como a gente entende o que aconteceu.",
        "Porque uma decisão pequena pode criar uma consequência enorme.",
        "E quando a consequência aparece, parece que tudo aconteceu de repente.",
        "Só que nada disso nasce do nada.",
        "No fim, a pergunta é simples: esse detalhe muda a história para você?",
    ]
    if _normalize(tone) in {"dramatico", "dramático"}:
        lines[1] = "Mas por trás da versão conhecida existe uma pressão que quase ninguém enxerga."
        lines[4] = "Quando essa pressão aparece, o resultado parece muito maior do que o placar."
    if _normalize(niche) == "futebol":
        lines[3] = "No futebol, uma decisão pequena pode mudar o clima de um jogo inteiro."
    return lines if duration >= 40 else lines[:5]


def _fact_notes(niche: str, lines: list[str]) -> list[str]:
    notes: list[str] = []
    if niche in {"politica", "política", "saude", "saúde", "true crime", "crime"}:
        notes.append("Revisar nomes, datas e afirmações factuais antes de renderizar.")
    if any("Copa do Mundo" in line or "Brasil" in line for line in lines):
        notes.append("Conferir contexto histórico e evitar citar partidas ou datas sem fonte.")
    if any("fonte" in line.lower() or "dado" in line.lower() for line in lines):
        notes.append("Substituir placeholders por fonte confiável no roteiro final.")
    return notes


def _curiosity_gap(topic: str, angle: str) -> str:
    return f"O público sabe o tema ({topic}), mas não sabe por que {angle} importa."


def _visual_direction(niche: str, topic: str, angle: str) -> str:
    return f"Visual faceless com b-roll de {niche}, cortes rápidos, destaque para {topic} e clima de descoberta sobre {angle}."


def _visual_context(niche: str, idea: str) -> list[str]:
    if _is_world_cup_brazil(idea):
        return [
            "Torcida brasileira em estádio lotado",
            "Jogadores entrando em campo sob pressão",
            "Close em bandeira do Brasil e arquibancada",
            "Imagem dramática de estádio após derrota",
        ]
    return [
        f"B-roll faceless relacionado a {niche}",
        f"Imagem simbólica para representar {idea}",
        "Cortes entre detalhe, consequência e reação do público",
        "Evitar rostos reais sem licença, marcas em destaque e imagens sensacionalistas",
    ]


def _why_it_works(niche: str, angle: str, tone: str) -> str:
    return f"Combina {niche} com um ângulo específico ({angle}), cria curiosidade e abre espaço para comentário em tom {tone}."


def _emotion_for(tone: str, niche: str) -> str:
    if _normalize(tone) in {"polemico", "polêmico"}:
        return "discordância"
    if niche in {"true crime", "crime"}:
        return "tensão"
    if _normalize(tone) in {"didatico", "didático"}:
        return "clareza"
    return "curiosidade"


def _risk_level(niche: str) -> str:
    return "medium" if niche in {"politica", "política", "saude", "saúde", "true crime", "crime"} else "low"


def _voice_style(tone: str) -> str:
    normalized = _normalize(tone)
    if normalized in {"serio", "sério"}:
        return "grave, claro e contido"
    if normalized in {"polemico", "polêmico"}:
        return "direto, firme e provocativo"
    return "curioso, próximo e com energia controlada"


def _cta_for(tone: str) -> str:
    if _normalize(tone) in {"polemico", "polêmico"}:
        return "Comenta se você concorda ou se acha que tem outro lado."
    return "Salva esse corte e comenta qual detalhe você não tinha percebido."


def _hashtags(niche: str, topic: str, language: str) -> list[str]:
    base = [_hashtag(niche), _hashtag(topic), "#shorts"]
    if str(language).lower().startswith("pt"):
        base.append("#brasil")
    return list(dict.fromkeys(item for item in base if item != "#"))


def _hashtag(value: str) -> str:
    text = re.sub(r"[^A-Za-zÀ-ÿ0-9]+", "", value.title())
    return f"#{text}" if text else "#darkflow"


def _default_topic(niche: str) -> str:
    defaults = {
        "futebol": "uma decisão que mudou o jogo",
        "negocios": "uma estratégia que pouca gente usa",
        "negócios": "uma estratégia que pouca gente usa",
        "financas": "um erro comum com dinheiro",
        "finanças": "um erro comum com dinheiro",
        "tecnologia": "uma mudança que já começou",
    }
    return defaults.get(_normalize(niche), f"um tema de {niche}")


def _title_from_idea(idea: str) -> str:
    topic = _topic_from_idea(idea)
    title = _narrative_title(topic, "")
    return title[:90]


def _topic_from_idea(idea: str) -> str:
    text = re.sub(r"^isso aqui sobre\s+", "", _clean(idea), flags=re.I)
    text = re.sub(r"^um tema de\s+", "", text, flags=re.I)
    return text.split(":")[0].strip() or text or "essa história"


def _narrative_title(topic: str, niche: str) -> str:
    if _is_world_cup_brazil(topic):
        return "O peso invisível de uma Copa no Brasil"
    if _normalize(niche) == "futebol":
        return f"O detalhe que muda {topic}"
    return f"O detalhe invisível de {topic}"


def _is_world_cup_brazil(value: str) -> bool:
    normalized = _normalize(value)
    return ("copa do mundo" in normalized or "copa" in normalized) and "brasil" in normalized


def _normalize_duration(duration_seconds: int | float | str | None, duration_preset: str = "") -> int:
    preset = str(duration_preset or "").strip().lower()
    if preset in {"60", "60s", "curto"}:
        return 60
    if preset in {"90", "90s", "1m30", "medio", "médio"}:
        return 90
    if preset in {"120", "120s", "2m", "longo"}:
        return 120
    try:
        value = int(float(duration_seconds or 60))
    except (TypeError, ValueError):
        value = 60
    return min((60, 90, 120), key=lambda option: abs(option - value))


def _duration_label(duration_seconds: int | float | str | None) -> str:
    duration = _normalize_duration(duration_seconds)
    return {60: "60s", 90: "1m30", 120: "2m"}[duration]


def _add_duration_metadata(payload: dict[str, Any]) -> None:
    requested = _normalize_duration(
        payload.get("requested_duration_seconds") or payload.get("duration_seconds") or payload.get("estimated_duration_seconds")
    )
    lines = [str(line or "").strip() for line in payload.get("script_lines") or [] if str(line or "").strip()]
    hook = _clean(payload.get("hook"))
    cta = _clean(payload.get("cta"))
    narration_text = " ".join(item for item in [hook, *lines, cta] if item).strip()
    script_text = " ".join(lines)
    narration_words = re.findall(r"\b[\wÀ-ÿ]+\b", narration_text)
    script_words = re.findall(r"\b[\wÀ-ÿ]+\b", script_text)
    estimated = round(max(1, len(narration_words)) / 2.45)
    payload["requested_duration_seconds"] = requested
    payload["duration_preset_label"] = _duration_label(requested)
    payload["script_word_count"] = len(script_words)
    payload["narration_word_count"] = len(narration_words)
    payload["narration_text_preview"] = narration_text[:280]
    payload["estimated_duration_seconds"] = estimated


def _list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    if not text:
        return []
    return [_clean(item) for item in re.split(r"[,;\n]+", text) if _clean(item)]


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize(value: str) -> str:
    return _clean(value).lower()
