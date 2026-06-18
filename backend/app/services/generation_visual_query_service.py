"""Smart visual search queries for Pexels (0.5.53, Part 3).

Each visual item gets 2-4 short, specific, English queries built from entities
and a visual concept — not the whole Portuguese script line. This makes the
b-roll actually match the narrated beat instead of returning random clips.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.generation_llm_provider_service import generate_visual_queries


# Portuguese -> English visual concepts (longest keys matched first).
PT_EN_TERMS: dict[str, str] = {
    "antigo egito": "ancient egypt",
    "egito antigo": "ancient egypt",
    "piramides de gize": "giza pyramids",
    "pirâmides de gizé": "giza pyramids",
    "piramides": "pyramids egypt",
    "pirâmides": "pyramids egypt",
    "hieroglifos": "egyptian hieroglyphics",
    "hieróglifos": "egyptian hieroglyphics",
    "cleopatra": "cleopatra egypt",
    "cleópatra": "cleopatra egypt",
    "farao": "pharaoh egypt",
    "faraó": "pharaoh egypt",
    "nilo": "nile river egypt",
    "deserto": "desert dunes",
    "egito": "egypt",
    "copa do mundo": "soccer world cup",
    "estadio": "soccer stadium crowd",
    "estádio": "soccer stadium crowd",
    "futebol": "soccer",
    "neymar": "soccer stadium night",
    "brasil": "brazil flag",
    "imperio romano": "ancient rome",
    "império romano": "ancient rome",
    "roma antiga": "ancient rome colosseum",
    "romano": "roman empire ruins",
    "roma": "rome italy",
    "guerra": "war battlefield",
    "oceano": "ocean waves aerial",
    "espaco": "outer space galaxy",
    "espaço": "outer space galaxy",
    "dinheiro": "money cash finance",
    "tecnologia": "technology circuit",
    "cidade": "city skyline night",
    "natureza": "nature landscape aerial",
    "historia": "old history archive",
    "história": "old history archive",
    "misterio": "dark mystery fog",
    "mistério": "dark mystery fog",
}

NICHE_EN: dict[str, str] = {
    "futebol": "soccer stadium",
    "historia": "ancient history",
    "história": "ancient history",
    "curiosidades": "abstract cinematic background",
    "tecnologia": "technology abstract",
    "negocios": "business office city",
    "negócios": "business office city",
    "financas": "money finance chart",
    "finanças": "money finance chart",
    "true crime": "dark crime scene night",
    "saude": "health wellness lifestyle",
    "saúde": "health wellness lifestyle",
    "politica": "government building flags",
    "política": "government building flags",
}

VISUAL_MODIFIERS = ["cinematic", "aerial view", "slow motion", "close up"]
_STOPWORDS = {
    "que", "com", "sem", "uma", "para", "por", "dos", "das", "como", "mais", "muito",
    "isso", "esse", "essa", "sobre", "quando", "porque", "todo", "mundo", "anos", "ano",
    "the", "and", "for", "with", "que", "uns", "foi", "era", "ele", "ela",
}


def build_search_queries(item: dict[str, Any], project: dict[str, Any], max_queries: int = 4) -> list[str]:
    # Prefer LLM-generated queries (they match the narrated beat); keep the
    # dictionary-built queries as a safety net appended after them.
    llm_queries = [q for q in _string_list_any(item.get("llm_queries")) if q]
    if llm_queries:
        niche_subject = NICHE_EN.get(_normalize(str(project.get("niche") or "")), "")
        fallback = [_compose(niche_subject, "cinematic")] if niche_subject else []
        return _dedupe(llm_queries + fallback, max_queries)

    subjects = _subjects(item, project)
    niche_subject = NICHE_EN.get(_normalize(str(project.get("niche") or "")), "")

    queries: list[str] = []
    primary = subjects[0] if subjects else niche_subject or "cinematic background"

    # 1) primary subject, cinematic
    queries.append(_compose(primary, "cinematic"))
    # 2) primary + secondary subject or a modifier
    if len(subjects) > 1:
        queries.append(_compose(subjects[0], subjects[1]))
    else:
        queries.append(_compose(primary, "aerial view"))
    # 3) a different angle on the primary
    queries.append(_compose(primary, _modifier_for(item)))
    # 4) niche/general safety net
    if niche_subject:
        queries.append(_compose(niche_subject, "cinematic"))

    return _dedupe(queries, max_queries)


def build_llm_visual_plan(
    project: dict[str, Any],
    script_lines: list[str],
    contexts: list[str],
) -> list[dict[str, Any]] | None:
    """One batched LLM call mapping each beat to stock queries. None if unavailable."""
    brief = project.get("research_brief") if isinstance(project.get("research_brief"), dict) else {}
    if not brief:
        brief = project.get("factual_brief") if isinstance(project.get("factual_brief"), dict) else {}
    return generate_visual_queries(
        script_lines=script_lines,
        contexts=contexts,
        niche=str(project.get("niche") or ""),
        title=str(project.get("title") or project.get("idea") or ""),
        language=str(project.get("language") or "pt-BR"),
        research_brief=brief or {},
    )


def _string_list_any(value: object) -> list[str]:
    if isinstance(value, list):
        return [re.sub(r"\s+", " ", str(item)).strip() for item in value if str(item).strip()]
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return [text] if text else []


# ---------------------------------------------------------------------------

def _subjects(item: dict[str, Any], project: dict[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    # Prefer research entities — they are concrete and specific.
    brief = project.get("research_brief") if isinstance(project.get("research_brief"), dict) else {}
    entities = brief.get("key_entities") if isinstance(brief, dict) else None
    candidate_text = " ".join(
        [
            str(item.get("query") or ""),
            str(item.get("description") or ""),
            str(item.get("suggested_prompt") or ""),
            str(project.get("title") or ""),
            str(project.get("idea") or ""),
        ]
    )
    if isinstance(entities, list):
        candidate_text += " " + " ".join(str(e or "") for e in entities)

    normalized = _normalize(candidate_text)
    for term in sorted(PT_EN_TERMS, key=len, reverse=True):
        if term in normalized:
            english = PT_EN_TERMS[term]
            key = english.split()[0]
            if key not in seen:
                found.append(english)
                seen.add(key)
        if len(found) >= 3:
            break

    if not found:
        # Fall back to raw keywords (English-ish words pass through to Pexels).
        for word in re.findall(r"[A-Za-z]{4,}", candidate_text):
            low = word.lower()
            if low in _STOPWORDS or low in seen:
                continue
            found.append(low)
            seen.add(low)
            if len(found) >= 2:
                break
    return found


def _modifier_for(item: dict[str, Any]) -> str:
    role = _normalize(str(item.get("beat_role") or ""))
    order = int(_safe(item.get("order")) or 0)
    if role in {"hook", "tension"}:
        return "close up"
    if role in {"context", "consequence"}:
        return "aerial view"
    return VISUAL_MODIFIERS[order % len(VISUAL_MODIFIERS)]


def _compose(*parts: str) -> str:
    words: list[str] = []
    for part in parts:
        for token in str(part or "").split():
            low = token.lower()
            if low and low not in words:
                words.append(low)
    return " ".join(words[:4]).strip()


def _dedupe(queries: list[str], limit: int) -> list[str]:
    out: list[str] = []
    for query in queries:
        cleaned = re.sub(r"\s+", " ", query).strip()
        if cleaned and cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def _normalize(value: str) -> str:
    table = str.maketrans("áàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ", "aaaaeeiooouucAAAAEEIOOOUUC")
    return re.sub(r"\s+", " ", str(value or "")).lower().translate(table).strip()


def _safe(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
