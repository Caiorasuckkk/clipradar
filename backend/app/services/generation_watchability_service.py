from __future__ import annotations

import re
from typing import Any


FORMAT_LABELS = {
    "match_preview": "Pré-jogo",
    "player_watchlist": "Jogadores para ficar de olho",
    "top_list": "Top lista",
    "news_context": "Contexto de notícia",
    "explainer": "Explicativo",
    "curiosity": "Curiosidade",
    "documentary": "Documentário",
    "ready_script": "Roteiro pronto",
    "manual_topic": "Tema manual",
}

UNRELATED_LEGENDS = ["pelé", "pele", "maradona", "ronaldo fenômeno", "ronaldo fenomeno", "cruyff", "beckenbauer"]
ABSTRACT_PHRASES = [
    "genialidade que acende",
    "momentos de pura explosão",
    "momentos de pura explosao",
    "decisividade define um legado",
    "quem serão os próximos",
    "quem serao os proximos",
]


def normalize_content_format(value: object, creation_mode: str = "") -> str:
    text = str(value or "").strip().lower()
    aliases = {"preview": "match_preview", "player_watchlist": "player_watchlist"}
    text = aliases.get(text, text)
    if text in FORMAT_LABELS:
        return text
    if creation_mode == "ready_script":
        return "ready_script"
    if creation_mode == "opportunity":
        return "news_context"
    return "manual_topic"


def content_format_label(value: object, creation_mode: str = "") -> str:
    return FORMAT_LABELS[normalize_content_format(value, creation_mode)]


def infer_content_format(topic: str, niche: str = "", creation_mode: str = "") -> str:
    text = _normalize(f"{topic} {niche}")
    if creation_mode == "ready_script":
        return "ready_script"
    if any(term in text for term in ["jogadores", "nomes para ficar", "quem pode decidir"]):
        return "player_watchlist"
    if any(term in text for term in [" x ", "jogo", "partida", "pre jogo", "estreia"]):
        return "match_preview"
    if any(term in text for term in ["top ", "lista", "melhores", "curiosidades"]):
        return "top_list"
    if any(term in text for term in ["hoje", "noticia", "notícia", "agora", "esta semana"]):
        return "news_context"
    if creation_mode == "opportunity":
        return "news_context"
    return "manual_topic"


def context_from_text(text: str) -> dict[str, Any]:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    teams: list[str] = []
    match = re.search(r"([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][\wÀ-ÿ .'-]{1,35})\s+[xX×]\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][\wÀ-ÿ .'-]{1,35})", clean)
    if match:
        teams = [match.group(1).strip(" ,.-"), match.group(2).strip(" ,.-")]
    people = _named_people(clean, teams)
    event_name = " x ".join(teams) if len(teams) >= 2 else ""
    return {
        "event_name": event_name,
        "event_type": "match" if event_name else "",
        "teams": teams,
        "people": people,
        "key_players": [{"name": name, "team": "", "why_matters": "", "role": ""} for name in people],
    }


def enrich_opportunity_context(item: dict[str, Any]) -> dict[str, Any]:
    merged_text = " ".join(
        str(item.get(key) or "")
        for key in ["title", "topic", "angle", "why_now", "suggested_hook", "extra_context"]
    )
    parsed = context_from_text(merged_text)
    content_format = normalize_content_format(
        item.get("content_format") or item.get("content_type") or infer_content_format(merged_text, str(item.get("niche") or ""), "opportunity"),
        "opportunity",
    )
    teams = _strings(item.get("teams")) or parsed["teams"]
    people = _strings(item.get("people")) or parsed["people"]
    key_players = _key_players(item.get("key_players"))
    if not key_players and people:
        key_players = [{"name": person, "team": "", "why_matters": "", "role": ""} for person in people]
    event_name = _clean(item.get("event_name")) or parsed["event_name"]
    concrete_promise = _clean(item.get("concrete_promise"))
    viewer_reason = _clean(item.get("viewer_reason_to_watch"))
    if not concrete_promise:
        if content_format == "player_watchlist" and event_name:
            concrete_promise = f"Mostrar os nomes que podem decidir {event_name}."
        elif content_format == "match_preview" and event_name:
            concrete_promise = f"Explicar o fator que pode decidir {event_name}."
    if not viewer_reason and event_name:
        viewer_reason = f"Entender o que observar em {event_name} antes da bola rolar."
    missing: list[str] = []
    if content_format in {"player_watchlist", "match_preview"}:
        if not event_name:
            missing.append("event_name")
        if len(teams) < 2:
            missing.append("teams")
    if content_format == "player_watchlist" and len(key_players) < 2:
        missing.append("key_players")
    if not concrete_promise:
        missing.append("concrete_promise")
    return {
        **item,
        "event_name": event_name,
        "event_type": _clean(item.get("event_type")) or ("match" if event_name else ""),
        "teams": teams,
        "people": people,
        "key_players": key_players,
        "competition": _clean(item.get("competition")),
        "concrete_promise": concrete_promise,
        "viewer_reason_to_watch": viewer_reason,
        "suggested_video_angle": _clean(item.get("suggested_video_angle")) or _clean(item.get("angle")),
        "content_format": content_format,
        "content_format_label": content_format_label(content_format),
        "missing_context_fields": list(dict.fromkeys(missing)),
        "needs_more_context": bool(missing),
    }


def opportunity_research_brief(opportunity: dict[str, Any], base_brief: dict[str, Any] | None = None) -> dict[str, Any]:
    data = enrich_opportunity_context(opportunity)
    players = data["key_players"]
    return {
        **(base_brief or {}),
        "subject": data.get("event_name") or data.get("title") or data.get("topic"),
        "topic": data.get("topic") or data.get("title"),
        "event_name": data["event_name"],
        "event_type": data["event_type"],
        "teams": data["teams"],
        "competition": data["competition"],
        "date_context": data.get("event_date") or data.get("freshness") or "",
        "key_players": players,
        "why_each_player_matters": [
            {"name": player["name"], "why_matters": player["why_matters"]} for player in players
        ],
        "tactical_or_story_angle": data["suggested_video_angle"],
        "why_now": data.get("why_now") or "",
        "concrete_promise": data["concrete_promise"],
        "viewer_reason_to_watch": data["viewer_reason_to_watch"],
        "content_format": data["content_format"],
        "missing_context_fields": data["missing_context_fields"],
        "risk_notes": ["Não inventar jogadores ou contexto atual sem fonte."] if data["needs_more_context"] else [],
        "source_urls": _strings(data.get("source_urls")) or _strings((base_brief or {}).get("source_urls")),
        "source_titles": _strings(data.get("source_titles")) or _strings((base_brief or {}).get("source_titles")),
        "confidence": "low" if data["needs_more_context"] else str(data.get("confidence") or "medium"),
    }


def build_format_script(content_format: str, context: dict[str, Any], duration_seconds: int = 60) -> dict[str, Any] | None:
    data = enrich_opportunity_context(context)
    fmt = normalize_content_format(content_format, "opportunity")
    event = data["event_name"]
    teams = data["teams"]
    players = data["key_players"]
    if fmt == "player_watchlist" and event and len(players) >= 2:
        chosen = players[:3]
        count = len(chosen)
        why_now = str(data.get("why_now") or "há um detalhe que pode mudar a partida").rstrip(" .")
        lines = [f"Esse não é só mais um confronto: {why_now}."]
        for index, player in enumerate(chosen):
            name = player["name"]
            reason = player["why_matters"] or player["role"] or "pode desequilibrar no momento em que o jogo abrir espaços"
            if index == 0:
                lines.append(f"O primeiro nome é {name}. Ele importa porque {reason}.")
            elif index == 1:
                lines.append(f"Do outro lado, {name} pode desequilibrar porque {reason}.")
            else:
                lines.append(f"O terceiro nome é {name}, principalmente porque {reason}.")
        lines.extend([
            f"O detalhe é que {event} pode ser decidido menos pela posse e mais por quem aproveitar o primeiro espaço.",
            "Se um desses nomes aparecer no momento certo, o jogo muda.",
        ])
        return {
            "title": data.get("suggested_video_title") or f"{count} jogadores para ficar de olho em {event}",
            "hook": f"Hoje tem {event}, e {count} jogadores podem mudar completamente esse jogo.",
            "script_lines": lines,
            "cta": "Qual deles você acha que decide?",
            "estimated_duration_seconds": duration_seconds,
        }
    if fmt in {"match_preview", "player_watchlist"} and event and len(teams) >= 2:
        names = ", ".join(player["name"] for player in players[:2])
        lines = [
            f"De um lado, {teams[0]} chega com um desafio claro. Do outro, {teams[1]} precisa responder.",
            f"O ponto mais importante é {data.get('suggested_video_angle') or 'quem consegue controlar os espaços decisivos'}.",
        ]
        if names:
            lines.append(f"E é aqui que nomes como {names} entram.")
        lines.extend([
            f"Se uma das equipes controlar esse fator, {event} pode mudar rápido.",
            "Talento individual pode decidir, mas a estratégia cria o momento da decisão.",
        ])
        return {
            "title": data.get("suggested_video_title") or f"O que observar em {event}",
            "hook": f"{event} não é só um jogo; é um teste para quem consegue controlar o ponto decisivo.",
            "script_lines": lines,
            "cta": "Você acha que esse jogo será decidido por talento individual ou estratégia?",
            "estimated_duration_seconds": duration_seconds,
            "content_format": "match_preview",
        }
    return None


def score_watchability(payload: dict[str, Any]) -> dict[str, Any]:
    fmt = normalize_content_format(payload.get("content_format"), str(payload.get("creation_mode") or ""))
    brief = payload.get("research_brief") if isinstance(payload.get("research_brief"), dict) else {}
    context = enrich_opportunity_context(
        {**dict(payload.get("opportunity_data") or {}), **brief, **payload}
    )
    text = _normalize(" ".join([_clean(payload.get("title")), _clean(payload.get("hook")), *_strings(payload.get("script_lines"))]))
    score = 3.0
    positive: list[str] = []
    negative: list[str] = []
    promise = _clean(payload.get("concrete_promise")) or context["concrete_promise"]
    reason = _clean(payload.get("viewer_reason_to_watch")) or context["viewer_reason_to_watch"]
    if promise:
        score += 1.2; positive.append("concrete_promise_present")
    else:
        negative.append("no_clear_promise")
    if context["event_name"] and _normalize(context["event_name"]) in text:
        score += 1.4; positive.append("event_context_present")
    elif fmt in {"player_watchlist", "match_preview"}:
        negative.append("missing_event_context")
    player_names = [player["name"] for player in context["key_players"] if player["name"]]
    current_hits = [name for name in player_names if _normalize(name) in text]
    if current_hits:
        score += 1.4; positive.extend(["current_entities_present", "specific_names_present"])
    elif fmt == "player_watchlist":
        negative.append("missing_current_players")
    if reason:
        score += 0.8; positive.append("viewer_reason_clear")
    else:
        negative.append("no_viewer_payoff")
    hook = _clean(payload.get("hook"))
    if promise and len(hook) >= 25 and (context["event_name"] or any(char.isdigit() for char in hook)):
        score += 1.0; positive.append("strong_first_3_seconds")
    if fmt in {"player_watchlist", "match_preview", "top_list", "news_context"}:
        score += 0.5; positive.append("format_matches_topic")
    generic = any(phrase in text for phrase in ABSTRACT_PHRASES)
    legends = [legend for legend in UNRELATED_LEGENDS if legend in text and legend not in _normalize(context.get("event_name"))]
    if generic:
        score -= 2.0; negative.extend(["abstract_language_overuse", "generic_sports_essay"])
    if legends:
        score -= 2.0; negative.append("historical_legends_unrelated")
    if fmt == "player_watchlist" and (not context["event_name"] or not current_hits):
        score = min(score, 3.8)
        negative.extend(["generic_sports_essay", "topic_not_answered"])
    score = max(0.0, min(10.0, round(score, 1)))
    if score >= 7.0:
        positive.append("not_generic")
    return {
        "content_format": fmt,
        "content_format_label": content_format_label(fmt),
        "concrete_promise": promise,
        "viewer_reason_to_watch": reason,
        "watchability_score": score,
        "needs_more_context": bool(context["missing_context_fields"]),
        "missing_context_fields": context["missing_context_fields"],
        "watchability_positive_signals": list(dict.fromkeys(positive)),
        "watchability_negative_signals": list(dict.fromkeys(negative)),
    }


def repair_generic_opportunity_script(
    project: dict[str, Any],
    research_brief: dict[str, Any],
    opportunity_data: dict[str, Any],
) -> dict[str, Any]:
    context = enrich_opportunity_context({**opportunity_data, **research_brief, **project})
    repaired = build_format_script(context["content_format"], context, int(project.get("requested_duration_seconds") or 60))
    if repaired:
        return {
            **project,
            **repaired,
            "content_format": repaired.get("content_format") or context["content_format"],
            "opportunity_script_repair_applied": True,
            "opportunity_script_repair_reason": "generic_opportunity_rewritten_with_concrete_context",
            "needs_more_context": False,
        }
    return {
        **project,
        "needs_more_context": True,
        "missing_context_fields": context["missing_context_fields"],
        "opportunity_script_repair_applied": False,
        "opportunity_script_repair_reason": "missing_event_and_players_for_watchlist",
    }


def _key_players(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    players: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict) and _clean(item.get("name")):
            players.append({
                "name": _clean(item.get("name")),
                "team": _clean(item.get("team")),
                "why_matters": _clean(item.get("why_matters")),
                "role": _clean(item.get("role")),
            })
        elif _clean(item):
            players.append({"name": _clean(item), "team": "", "why_matters": "", "role": ""})
    return players


def _named_people(text: str, teams: list[str]) -> list[str]:
    excluded = {_normalize(team) for team in teams}
    candidates = re.findall(r"\b[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][a-záàãâéêíóôõúç]+(?:\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][a-záàãâéêíóôõúç]+){1,2}\b", text)
    return [name for name in dict.fromkeys(candidates) if _normalize(name) not in excluded][:8]


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    return [text] if text else []


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize(value: object) -> str:
    return _clean(value).lower().translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
