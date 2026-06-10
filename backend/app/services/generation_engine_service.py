from __future__ import annotations

import json
import re
from typing import Any

import requests

from app import config
from app.services.generation_factual_grounding_service import (
    generate_factual_brief,
    repair_generic_script_with_brief,
    validate_specificity,
)
from app.services.generation_script_quality_service import (
    score_generation_script,
    validate_script_is_narration,
)


VALID_MODES = {"local", "canal_dark"}
VALID_PROVIDERS = {"none", "gemini"}

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
    has_gemini_key = bool(config.GEMINI_API_KEY)
    external_available = provider == "gemini" and has_gemini_key
    return {
        "engine_mode": mode,
        "provider": provider,
        "configured_engine": config.GENERATION_ENGINE,
        "configured_provider": config.GENERATION_AI_PROVIDER,
        "external_ai_available": external_available,
        "fallback_available": True,
        "require_external_ai": config.GENERATION_REQUIRE_EXTERNAL_AI,
        "gemini_configured": has_gemini_key,
        "gemini_model": config.GENERATION_GEMINI_MODEL,
        "features": CANAL_DARK_FEATURES if mode == "canal_dark" else ["local_templates"],
    }


def generate_engine_ideas(
    niche: str,
    topic: str = "",
    language: str = "pt-BR",
    tone: str = "curioso",
) -> list[dict[str, Any]]:
    mode = _engine_mode()
    provider = _provider()
    if mode == "canal_dark" and provider == "gemini" and config.GEMINI_API_KEY:
        try:
            return _ideas_with_gemini(niche, topic, language, tone)
        except Exception:
            if config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise
            return _local_ideas(niche, topic, language, tone, mode, provider, fallback_used=True)
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
    tone: str = "curioso",
    language: str = "pt-BR",
) -> dict[str, Any]:
    mode = _engine_mode()
    provider = _provider()
    factual_brief = generate_factual_brief(
        niche=niche,
        topic=topic or idea,
        idea=idea,
        language=language,
    )
    if mode == "canal_dark" and provider == "gemini" and config.GEMINI_API_KEY:
        try:
            return _script_with_gemini(idea, niche, topic, duration_seconds, tone, language, factual_brief)
        except Exception:
            if config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise
            return _local_script(idea, niche, topic, duration_seconds, tone, language, mode, provider, True, factual_brief)
    if mode == "canal_dark" and config.GENERATION_REQUIRE_EXTERNAL_AI:
        raise RuntimeError("external_generation_ai_unavailable")
    return _local_script(
        idea=idea,
        niche=niche,
        topic=topic,
        duration_seconds=duration_seconds,
        tone=tone,
        language=language,
        mode=mode,
        provider=provider,
        fallback_used=mode == "canal_dark" and provider != "none",
        factual_brief=factual_brief,
    )


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
) -> dict[str, Any]:
    idea_text = _clean(idea or topic) or "Uma ideia para explicar de forma simples"
    niche_label = _clean(niche) or "geral"
    normalized_niche = _normalize(niche_label)
    seconds = max(20, min(90, int(duration_seconds or 45)))
    grounded = (
        repair_generic_script_with_brief(factual_brief, tone=tone, duration_seconds=seconds)
        if factual_brief.get("confidence") != "low"
        else {}
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
        "factual_grounding_used": factual_brief.get("confidence") != "low",
        "factual_grounding_confidence": factual_brief.get("confidence", "low"),
        "specificity_score": 0.0,
        "estimated_duration_seconds": seconds,
        "duration_seconds": seconds,
        "voice_style": _voice_style(tone),
        "pacing": "rápido, com pausas curtas depois do hook",
        "engine_mode": mode,
        "provider": provider,
        "fallback_used": fallback_used,
        "niche": niche_label,
        "language": language or "pt-BR",
        "tone": tone or "curioso",
        "status": "script",
        "script_repair_applied": False,
        "script_repair_reason": "",
    }
    return _finalize_script_payload(payload, idea_text, niche_label, tone)


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
) -> dict[str, Any]:
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
        factual_brief=payload.get("factual_brief") if isinstance(payload.get("factual_brief"), dict) else {},
        topic=idea,
    )
    if not specificity["is_specific"] and payload.get("factual_brief", {}).get("confidence") != "low":
        repaired = repair_generic_script_with_brief(
            factual_brief=payload["factual_brief"],
            tone=tone,
            duration_seconds=int(payload.get("estimated_duration_seconds") or 45),
        )
        payload.update(repaired)
        payload["script_repair_applied"] = True
        payload["script_repair_reason"] = "generic_script_without_specific_facts"
        specificity = validate_specificity(
            script_lines=payload.get("script_lines"),
            factual_brief=payload.get("factual_brief"),
            topic=idea,
        )
    payload["specificity_score"] = specificity["specificity_score"]
    payload["factual_grounding_used"] = "factual_grounding_used" in specificity["positive_signals"]
    positives = list(payload.get("script_positive_signals") or []) + specificity["positive_signals"]
    negatives = list(payload.get("script_negative_signals") or []) + specificity["negative_signals"]
    payload.update(score_generation_script(payload))
    positives += list(payload.get("script_positive_signals") or [])
    negatives += list(payload.get("script_negative_signals") or [])
    payload["script_positive_signals"] = list(dict.fromkeys(positives))
    payload["script_negative_signals"] = list(dict.fromkeys(negatives))
    if payload.get("script_repair_applied"):
        negatives = list(payload.get("script_negative_signals") or [])
        negatives.append("script_repair_applied")
        payload["script_negative_signals"] = list(dict.fromkeys(negatives))
    return payload


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
