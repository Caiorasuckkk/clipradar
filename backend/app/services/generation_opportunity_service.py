from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import date
from typing import Any

from app import config
from app.services.generation_llm_provider_service import safe_json_parse
from app.services.generation_watchability_service import enrich_opportunity_context


def search_opportunities(
    niche: str,
    language: str = "pt-BR",
    region: str = "BR",
    time_window: str = "week",
    query: str = "",
    count: int = 5,
    provider: str = "auto",
    use_grounding: bool = True,
) -> dict[str, Any]:
    limit = max(1, min(10, int(count or 5)))
    requested_provider = str(provider or "auto").lower()
    can_use_gemini = (
        requested_provider in {"auto", "gemini"}
        and bool(config.GEMINI_API_KEY)
        and _module_available("google.genai")
    )
    if can_use_gemini:
        try:
            opportunities, grounding_used = search_opportunities_with_gemini(
                niche=niche,
                language=language,
                region=region,
                time_window=time_window,
                query=query,
                count=limit,
                use_grounding=use_grounding,
            )
            return {
                "provider": "gemini",
                "fallback_used": False,
                "grounding_used": grounding_used,
                "opportunities": opportunities,
            }
        except Exception as error:
            if requested_provider == "gemini" and config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise RuntimeError(f"gemini_opportunities_failed: {error}") from error
    return {
        "provider": "local",
        "fallback_used": True,
        "grounding_used": False,
        "opportunities": search_opportunities_local_fallback(
            niche=niche,
            language=language,
            region=region,
            time_window=time_window,
            query=query,
            count=limit,
        ),
    }


def search_opportunities_with_gemini(
    niche: str,
    language: str,
    region: str,
    time_window: str,
    query: str,
    count: int,
    use_grounding: bool,
) -> tuple[list[dict[str, Any]], bool]:
    from google import genai  # type: ignore

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = _opportunity_prompt(niche, language, region, time_window, query, count)
    kwargs: dict[str, Any] = {}
    grounding_used = False
    if use_grounding and config.GENERATION_USE_WEB_GROUNDING:
        try:
            from google.genai import types  # type: ignore

            kwargs["config"] = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
            grounding_used = True
        except Exception:
            grounding_used = False
    response = client.models.generate_content(
        model=config.GEMINI_RESEARCH_MODEL,
        contents=prompt,
        **kwargs,
    )
    payload = safe_json_parse(str(getattr(response, "text", "") or ""))
    items = payload.get("opportunities", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("gemini_opportunities_not_list")
    opportunities = [
        normalize_opportunity(item, niche=niche, time_window=time_window, provider="gemini")
        for item in items[:count]
        if isinstance(item, dict)
    ]
    if not opportunities:
        raise ValueError("gemini_opportunities_empty")
    return opportunities, grounding_used


def search_opportunities_local_fallback(
    niche: str,
    language: str,
    region: str,
    time_window: str,
    query: str,
    count: int,
) -> list[dict[str, Any]]:
    niche_label = str(niche or "curiosidades").strip()
    query_label = str(query or "").strip()
    themes = _local_themes(niche_label, query_label)
    items: list[dict[str, Any]] = []
    for index, theme in enumerate(themes[:count], start=1):
        title, angle, content_type = theme
        conservative_today = time_window == "today"
        items.append(
            normalize_opportunity(
                {
                    "opportunity_id": f"opp_local_{uuid.uuid4().hex[:10]}",
                    "title": title,
                    "niche": niche_label,
                    "topic": query_label or title,
                    "event_date": str(date.today()) if conservative_today else "",
                    "freshness": "today" if conservative_today else ("evergreen" if time_window == "evergreen" else "recent"),
                    "why_now": (
                        "Sugestão exploratória para checar nos assuntos do dia; confirme o evento antes de publicar."
                        if conservative_today
                        else "Tema recorrente com bom potencial para vídeo curto contextual."
                    ),
                    "angle": angle,
                    "suggested_video_title": title,
                    "suggested_hook": f"Tem um detalhe sobre {title.lower()} que muda a leitura do tema.",
                    "target_emotion": "curiosidade",
                    "curiosity_gap": "O público conhece o assunto, mas não o contexto ou a consequência.",
                    "content_type": content_type,
                    "content_format": content_type,
                    "event_name": "",
                    "event_type": "",
                    "teams": [],
                    "people": [],
                    "key_players": [],
                    "competition": "",
                    "concrete_promise": "",
                    "viewer_reason_to_watch": "",
                    "suggested_video_angle": angle,
                    "source_urls": [],
                    "source_titles": [],
                    "confidence": "low" if conservative_today else "medium",
                    "risk_level": "medium" if conservative_today else "low",
                    "fact_check_needed": True,
                    "region": region,
                    "language": language,
                },
                niche=niche_label,
                time_window=time_window,
                provider="local",
            )
        )
    return items


def normalize_opportunity(
    item: dict[str, Any],
    niche: str = "",
    time_window: str = "week",
    provider: str = "local",
) -> dict[str, Any]:
    urls = _strings(item.get("source_urls"))
    confidence = str(item.get("confidence") or "").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium" if urls else "low"
    if time_window == "today" and not urls:
        confidence = "low"
    risk = str(item.get("risk_level") or "low").lower()
    if risk not in {"low", "medium", "high"}:
        risk = "medium"
    freshness = str(item.get("freshness") or time_window).lower()
    if freshness not in {"today", "recent", "evergreen"}:
        freshness = "recent"
    normalized = {
        "opportunity_id": str(item.get("opportunity_id") or f"opp_{uuid.uuid4().hex[:12]}"),
        "title": str(item.get("title") or item.get("topic") or "Oportunidade de conteúdo").strip(),
        "niche": str(item.get("niche") or niche or "geral").strip(),
        "topic": str(item.get("topic") or item.get("title") or "").strip(),
        "event_date": str(item.get("event_date") or "").strip(),
        "freshness": freshness,
        "why_now": str(item.get("why_now") or "Tema com potencial de contexto e curiosidade.").strip(),
        "angle": str(item.get("angle") or "o contexto que muda a leitura").strip(),
        "suggested_video_title": str(item.get("suggested_video_title") or item.get("title") or "").strip(),
        "suggested_hook": str(item.get("suggested_hook") or "").strip(),
        "target_emotion": str(item.get("target_emotion") or "curiosidade").strip(),
        "curiosity_gap": str(item.get("curiosity_gap") or "").strip(),
        "content_type": str(item.get("content_type") or "explainer").strip(),
        "source_urls": urls,
        "source_titles": _strings(item.get("source_titles")),
        "confidence": confidence,
        "risk_level": risk,
        "fact_check_needed": bool(item.get("fact_check_needed", not bool(urls))),
        "provider": provider,
    }
    normalized.update(
        {
            "event_name": str(item.get("event_name") or "").strip(),
            "event_type": str(item.get("event_type") or "").strip(),
            "teams": _strings(item.get("teams")),
            "people": _strings(item.get("people")),
            "key_players": item.get("key_players") if isinstance(item.get("key_players"), list) else [],
            "competition": str(item.get("competition") or "").strip(),
            "concrete_promise": str(item.get("concrete_promise") or "").strip(),
            "viewer_reason_to_watch": str(item.get("viewer_reason_to_watch") or "").strip(),
            "suggested_video_angle": str(item.get("suggested_video_angle") or item.get("angle") or "").strip(),
            "content_format": str(item.get("content_format") or item.get("content_type") or "").strip(),
            "missing_context_fields": _strings(item.get("missing_context_fields")),
            "needs_more_context": bool(item.get("needs_more_context")),
        }
    )
    enriched = enrich_opportunity_context(normalized)
    if enriched["needs_more_context"]:
        enriched["confidence"] = "low"
        enriched["fact_check_needed"] = True
    return enriched


def create_project_from_opportunity(**kwargs: Any) -> dict[str, Any]:
    from app.services.generation_creation_service import (
        create_project_from_opportunity as create,
    )

    return create(**kwargs)


def create_projects_from_opportunities_batch(**kwargs: Any) -> list[dict[str, Any]]:
    from app.services.generation_creation_service import (
        create_projects_from_opportunities_batch as create_batch,
    )

    return create_batch(**kwargs)


def _opportunity_prompt(niche: str, language: str, region: str, time_window: str, query: str, count: int) -> str:
    return (
        "Identifique oportunidades para vídeos curtos/faceless. Retorne somente JSON válido com "
        "uma chave opportunities contendo uma lista. Cada item deve ter: opportunity_id,title,niche,"
        "topic,event_date,freshness,why_now,angle,suggested_video_title,suggested_hook,target_emotion,"
        "curiosity_gap,content_type,content_format,event_name,event_type,teams,people,key_players,competition,"
        "concrete_promise,viewer_reason_to_watch,suggested_video_angle,missing_context_fields,source_urls,"
        "source_titles,confidence,risk_level,fact_check_needed. key_players deve conter name,team,why_matters,role. "
        "Separe fato de sugestão. Não invente evento atual. Para assunto de hoje sem fonte, use "
        "confidence=low, fact_check_needed=true e missing_context_fields. Explique por que o tema importa agora. "
        "Para futebol atual, nomeie o jogo, competição, times e jogadores atuais confirmados. Não cite Pelé, "
        "Maradona, Ronaldo, Cruyff, Beckenbauer ou Messi sem relação direta com o evento. Proíba texto abstrato "
        "sobre genialidade, explosão ou legado. A oportunidade deve prometer algo concreto que o espectador aprende."
        f"\nNicho: {niche}\nIdioma: {language}\nRegião: {region}\nJanela: {time_window}"
        f"\nBusca: {query}\nQuantidade máxima: {count}"
    )


def _local_themes(niche: str, query: str) -> list[tuple[str, str, str]]:
    normalized = niche.lower()
    if "fut" in normalized:
        if any(term in query.lower() for term in ["jogador", "nomes", "quem pode decidir"]):
            return [
                (query or "Jogadores que podem mudar o jogo", "nomes atuais e motivos concretos para acompanhar", "player_watchlist"),
                ("O contexto do confronto", "o que observar antes do apito inicial", "match_preview"),
                ("O fator que pode decidir a partida", "uma explicação tática curta", "match_preview"),
            ]
        return [
            (query or "O contexto do jogo que está chamando atenção", "o que observar antes do apito inicial", "preview"),
            ("Jogadores que podem mudar a partida", "nomes e funções para acompanhar", "top_list"),
            ("A história por trás do confronto", "rivalidade, momento e pressão", "news_context"),
            ("O detalhe tático que pode decidir o jogo", "uma explicação simples para o público", "explainer"),
            ("O que a estreia pode revelar", "expectativa versus realidade", "curiosity"),
        ]
    if "tecn" in normalized:
        return [
            (query or "A mudança tecnológica que merece atenção", "impacto prático no dia a dia", "explainer"),
            ("O recurso que parece pequeno, mas muda o uso", "benefício e risco escondido", "curiosity"),
            ("O que esta tendência realmente resolve", "separar novidade de utilidade", "news_context"),
        ]
    if "hist" in normalized:
        return [
            (query or "A história pouco contada por trás de um grande evento", "detalhe humano e consequência", "curiosity"),
            ("O erro que mudou o rumo da história", "causa, virada e consequência", "explainer"),
            ("Cinco curiosidades que dão contexto ao passado", "lista com narrativa e fatos verificáveis", "top_list"),
        ]
    return [
        (query or f"Uma oportunidade em {niche}", "o detalhe pouco percebido", "curiosity"),
        (f"O contexto que explica {niche}", "causas e consequências", "explainer"),
        (f"O que vale acompanhar em {niche}", "sinais e perguntas para o público", "news_context"),
    ]


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, AttributeError):
        return False
