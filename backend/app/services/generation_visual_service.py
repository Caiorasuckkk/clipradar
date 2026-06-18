from __future__ import annotations

import re
import uuid
from typing import Any

from app import config
from app.services.generation_visual_query_service import build_llm_visual_plan
from app.services.generation_workspace_service import get_project, update_project


VISUAL_TYPES = {"broll", "image", "text_card", "screenshot", "placeholder"}
VISUAL_SOURCES = {"local", "pexels", "wikimedia", "pixabay", "openverse", "met", "generated", "manual", "placeholder"}
LICENSE_LANES = {"safe", "pexels", "wikimedia", "pixabay", "openverse", "public_domain", "review", "restricted", "unknown"}
VISUAL_STATUSES = {"suggestion", "selected", "missing", "needs_asset", "downloaded", "ready", "rejected"}


def suggest_visuals_for_project(project_id: str) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    return update_visual_items(project_id, suggest_visuals_from_script(project))


def suggest_visuals_from_script(project: dict[str, Any]) -> list[dict[str, Any]]:
    lines = _string_list(project.get("script_lines"))
    beats = [item for item in project.get("story_beats") or [] if isinstance(item, dict)]
    visual_context = _string_list(project.get("visual_context"))
    duration = _duration(project)

    # Build a flat spec list first: (line, context, beat_role, story_beat_id, line_index).
    specs: list[tuple[str, str, str, str, int]] = []
    if beats:
        for index, beat in enumerate(beats, start=1):
            line_index = min(index - 1, max(0, len(lines) - 1)) if lines else index - 1
            line = lines[line_index] if 0 <= line_index < len(lines) else str(beat.get("content") or "")
            specs.append((line, str(beat.get("content") or ""), str(beat.get("role") or ""),
                          str(beat.get("beat_id") or f"beat_{index}"), line_index))
    elif lines:
        for index, line in enumerate(lines[:10], start=1):
            ctx = visual_context[(index - 1) % len(visual_context)] if visual_context else ""
            specs.append((line, ctx, _role_for_order(index), "", index - 1))
    elif visual_context:
        for index, context in enumerate(visual_context[:6], start=1):
            specs.append((context, context, _role_for_order(index), "", index - 1))
    else:
        specs.append((str(project.get("title") or project.get("idea") or "tema principal"),
                      str(project.get("niche") or ""), "hook", "", 0))

    # One batched LLM call maps each beat to generic English stock queries.
    plan = build_llm_visual_plan(project, [spec[0] for spec in specs], [spec[1] for spec in specs])

    seed_items: list[dict[str, Any]] = []
    for order, (line, context, beat_role, story_beat_id, line_index) in enumerate(specs, start=1):
        entry = plan[order - 1] if plan and order - 1 < len(plan) and isinstance(plan[order - 1], dict) else None
        seed_items.append(
            _visual_item(
                order=order,
                script_line_index=line_index,
                story_beat_id=story_beat_id,
                beat_role=beat_role,
                script_line=line,
                context=context,
                project=project,
                llm_entry=entry,
            )
        )

    # Biography safety net: for a "quem foi X / vida de X" video, make the generic
    # scenes show the PERSON (real free photos) instead of a generic stand-in
    # (e.g. "kid playing soccer" for young Messi).
    person = _main_person(project)
    if person:
        for item in seed_items:
            if item.get("scene_kind") != "specific" and not str(item.get("wiki_subject") or "").strip():
                item["wiki_subject"] = person
                item["scene_kind"] = "specific"

    return _apply_timeline(_densify(seed_items, duration), duration)


def _main_person(project: dict[str, Any]) -> str:
    """Extract the central person/subject for biographical videos ('quem foi X',
    'história de X'). Empty when the topic isn't about a specific subject."""
    pattern = re.compile(
        r"(?:quem foi|quem e|quem é|quem s[aã]o|hist[oó]ria d[eoa]|a vida d[eoa]|"
        r"biografia d[eoa]|who was|who is)\s+(.+)",
        re.IGNORECASE,
    )
    for text in (str(project.get("idea") or ""), str(project.get("title") or "")):
        match = pattern.search(text)
        if not match:
            continue
        name = re.split(r"[?.!:,\n]", match.group(1))[0].strip()
        name = re.sub(r"^(o |a |os |as |the )", "", name, flags=re.IGNORECASE).strip()
        if 0 < len(name.split()) <= 4:
            return name
    return ""


def _densify(items: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    """Split each scene into several shorter cuts (more images per video).

    Aims for one image roughly every GENERATION_SECONDS_PER_VISUAL seconds, each
    copy using a different query so the b-roll varies (asset dedup keeps media
    distinct). Capped at GENERATION_MAX_VISUALS.
    """
    if not items:
        return items
    seconds_per = max(2.0, float(config.GENERATION_SECONDS_PER_VISUAL))
    max_total = max(len(items), int(config.GENERATION_MAX_VISUALS))
    slot = max(1.0, max(10.0, duration) / len(items))
    copies = max(1, round(slot / seconds_per))
    expanded: list[dict[str, Any]] = []
    for item in items:
        queries = [q for q in (item.get("llm_queries") or []) if str(q).strip()] or [item.get("query")]
        for k in range(copies):
            clone = dict(item)
            clone["visual_id"] = ""  # force a fresh id on normalize
            clone["query"] = queries[k % len(queries)] or item.get("query")
            expanded.append(clone)
            if len(expanded) >= max_total:
                return expanded
    return expanded


def update_visual_items(project_id: str, visual_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    items = _normalize_visual_items(visual_items, _duration(project))
    return update_project(
        project_id,
        {
            **project,
            "visual_status": "draft" if items else "none",
            "visual_items": items,
            "status": "ready_for_visual" if project.get("status") not in {"archived", "ready_for_render"} else project.get("status"),
            **_stale_render(project),
        },
    )


def add_visual_item(project_id: str, item: dict[str, Any]) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    items = list(project.get("visual_items") or [])
    item = {**item, "order": int(item.get("order") or len(items) + 1)}
    items.append(item)
    return update_visual_items(project_id, items)


def remove_visual_item(project_id: str, visual_id: str) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    items = [item for item in project.get("visual_items") or [] if str(item.get("visual_id") or "") != visual_id]
    return update_visual_items(project_id, items)


def mark_visual_item_selected(project_id: str, visual_id: str) -> dict[str, Any] | None:
    return _set_item_status(project_id, visual_id, "selected")


def reject_visual_item(project_id: str, visual_id: str) -> dict[str, Any] | None:
    return _set_item_status(project_id, visual_id, "rejected")


def mark_visuals_ready(project_id: str) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    items = []
    for item in project.get("visual_items") or []:
        if not isinstance(item, dict):
            continue
        next_item = dict(item)
        if next_item.get("status") == "selected":
            next_item["status"] = "ready"
        items.append(next_item)
    return update_project(
        project_id,
        {
            **project,
            "visual_status": "ready",
            "visual_items": _normalize_visual_items(items, _duration(project)),
            "status": "ready_for_render",
            **_stale_render(project),
        },
    )


def normalize_visual_item(item: dict[str, Any], order: int = 1) -> dict[str, Any]:
    lane = _license_lane(item)
    return {
        "visual_id": _clean(item.get("visual_id")) or f"vis_{uuid.uuid4().hex[:10]}",
        "order": int(item.get("order") or order),
        "script_line_index": int(item.get("script_line_index") or 0),
        "story_beat_id": _clean(item.get("story_beat_id")),
        "beat_role": _clean(item.get("beat_role")),
        "type": _choice(item.get("type"), VISUAL_TYPES, "placeholder"),
        "query": _clean(item.get("query")),
        "llm_queries": _string_list_field(item.get("llm_queries")),
        "scene_en": _clean(item.get("scene_en")),
        "wiki_subject": _clean(item.get("wiki_subject")),
        "scene_kind": _clean(item.get("scene_kind")),
        "description": _clean(item.get("description")),
        "suggested_prompt": _clean(item.get("suggested_prompt")),
        "source": _choice(item.get("source"), VISUAL_SOURCES, "placeholder"),
        "license_lane": lane,
        "media_url": _clean(item.get("media_url")),
        "thumbnail_url": _clean(item.get("thumbnail_url")),
        "media_path": _clean(item.get("media_path")),
        "duration_seconds": _float(item.get("duration_seconds")),
        "start_at_seconds": _float(item.get("start_at_seconds")),
        "end_at_seconds": _float(item.get("end_at_seconds")),
        "status": _choice(item.get("status"), VISUAL_STATUSES, "suggestion"),
        "notes": _clean(item.get("notes")),
        "risk_notes": _clean(item.get("risk_notes")) or _risk_notes(str(item.get("query") or ""), lane),
        "fallback_visual": _bool_value(item.get("fallback_visual")),
        "asset_error": _clean(item.get("asset_error")),
        "media_type": _clean(item.get("media_type")),
        "search_queries_attempted": _string_list_field(item.get("search_queries_attempted")),
        "selected_asset_score": _float(item.get("selected_asset_score")),
        "selected_asset_reason": _clean(item.get("selected_asset_reason")),
        "selected_query": _clean(item.get("selected_query")),
        "source_credit": _clean(item.get("source_credit")),
    }


def _set_item_status(project_id: str, visual_id: str, status: str) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    items: list[dict[str, Any]] = []
    for item in project.get("visual_items") or []:
        if not isinstance(item, dict):
            continue
        next_item = dict(item)
        if str(next_item.get("visual_id") or "") == visual_id:
            next_item["status"] = status
        items.append(next_item)
    return update_visual_items(project_id, items)


def _normalize_visual_items(items: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    normalized = [normalize_visual_item(item, index) for index, item in enumerate(items, start=1) if isinstance(item, dict)]
    return _apply_timeline(normalized, duration)


def _apply_timeline(items: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if not items:
        return []
    total = max(10.0, duration)
    slot = total / len(items)
    next_items: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        start = round(index * slot, 2)
        end = round(total if index == len(items) - 1 else (index + 1) * slot, 2)
        next_items.append(
            {
                **item,
                "order": index + 1,
                "start_at_seconds": start,
                "end_at_seconds": end,
                "duration_seconds": round(max(1.0, end - start), 2),
            }
        )
    return next_items


def _visual_item(
    order: int,
    script_line_index: int,
    story_beat_id: str,
    beat_role: str,
    script_line: str,
    context: str,
    project: dict[str, Any],
    llm_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    llm_queries = [str(q).strip() for q in (llm_entry or {}).get("queries") or [] if str(q).strip()]
    scene_en = str((llm_entry or {}).get("scene") or "").strip()
    wiki_subject = str((llm_entry or {}).get("subject") or "").strip()
    scene_kind = str((llm_entry or {}).get("kind") or "").strip().lower()
    # Prefer the LLM's scene-aware query; fall back to the dictionary builder.
    query = llm_queries[0] if llm_queries else _query_for(script_line, context, project)
    item_type = str((llm_entry or {}).get("type") or "").strip().lower() or _type_for(query)
    lane = _license_lane({"query": query, "type": item_type, "source": "placeholder"})
    return normalize_visual_item(
        {
            "order": order,
            "script_line_index": script_line_index,
            "story_beat_id": story_beat_id,
            "beat_role": beat_role,
            "type": item_type if item_type in VISUAL_TYPES else _type_for(query),
            "query": query,
            "llm_queries": llm_queries,
            "scene_en": scene_en,
            "wiki_subject": wiki_subject,
            "scene_kind": scene_kind,
            "description": scene_en or _description_for(script_line, context, beat_role, project),
            "suggested_prompt": f"Visual 9:16 faceless para: {script_line or context}",
            "source": "placeholder",
            "license_lane": lane,
            "status": "suggestion",
            "risk_notes": _risk_notes(query, lane),
        },
        order=order,
    )


def _query_for(script_line: str, context: str, project: dict[str, Any]) -> str:
    base = " ".join(
        [
            script_line,
            context,
            str(project.get("title") or ""),
            str(project.get("niche") or ""),
        ]
    )
    words = re.findall(r"[A-Za-zÀ-ÿ0-9x]+", base)
    stop = {"todo", "mundo", "como", "para", "sobre", "isso", "essa", "esse", "quando", "porque", "uma", "com", "sem"}
    terms = [word for word in words if len(word) > 2 and word.lower() not in stop]
    query = " ".join(dict.fromkeys(terms[:10]))
    if not query:
        query = str(project.get("title") or project.get("idea") or "b-roll abstrato")
    if _contains_any(query, ["neymar", "brasil", "colômbia", "colombia", "alemanha", "copa"]):
        return f"{query} estádio torcida futebol documentário"
    return f"{query} cinematic vertical b-roll"


def _description_for(script_line: str, context: str, beat_role: str, project: dict[str, Any]) -> str:
    topic = str(project.get("title") or project.get("idea") or "tema")
    if beat_role:
        return f"Visual para o beat {beat_role}: {context or script_line or topic}"
    return f"Imagem de apoio para: {script_line or context or topic}"


def _type_for(query: str) -> str:
    normalized = _normalize(query)
    if _contains_any(normalized, ["screenshot", "print", "site", "app"]):
        return "screenshot"
    if _contains_any(normalized, ["neymar", "jogador", "lesao", "lesão", "foto"]):
        return "image"
    return "broll"


def _license_lane(item: dict[str, Any]) -> str:
    source = str(item.get("source") or "").lower()
    media_type = str(item.get("type") or "").lower()
    query = _normalize(str(item.get("query") or item.get("description") or ""))
    if source == "pexels":
        return "pexels"
    if source == "wikimedia":
        return "wikimedia"
    if source == "pixabay":
        return "pixabay"
    if source == "openverse":
        return "openverse"
    if source == "met":
        return "public_domain"
    if source == "generated":
        return "safe"
    if media_type == "screenshot":
        return "review"
    if _contains_any(query, ["trailer", "gameplay", "transmissao completa", "transmissão completa", "logo"]):
        return "restricted"
    if _contains_any(query, ["neymar", "zuniga", "zuñiga", "copa", "futebol", "jogador", "celebridade", "politico", "político"]):
        return "review"
    lane = str(item.get("license_lane") or "").lower()
    return lane if lane in LICENSE_LANES else "unknown"


def _risk_notes(query: str, lane: str) -> str:
    if lane == "restricted":
        return "Possível mídia protegida ou marca como foco; evite sem licença."
    if lane == "review":
        return "Revisar direitos de imagem, transmissão, pessoa pública ou evento real."
    return ""


def _duration(project: dict[str, Any]) -> float:
    for key in ["requested_duration_seconds", "estimated_duration_seconds", "duration_seconds"]:
        try:
            value = float(project.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 60.0


def _role_for_order(index: int) -> str:
    return ["hook", "context", "tension", "hidden_detail", "turning_point", "consequence", "reflection", "cta"][
        min(index - 1, 7)
    ]


def _choice(value: object, valid: set[str], fallback: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in valid else fallback


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    return [text] if text else []


def _float(value: object) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim"}


def _stale_render(project: dict[str, Any]) -> dict[str, Any]:
    """Visual changes invalidate any existing render (Part 4)."""
    if str(project.get("render_status") or "") in {"ready", "queued", "rendering"}:
        return {"render_status": "stale"}
    return {}


def _string_list_field(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    return []


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize(value: str) -> str:
    table = str.maketrans("áàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ", "aaaaeeioooucAAAAEEIOOOUC")
    return _clean(value).lower().translate(table)


def _contains_any(value: str, needles: list[str]) -> bool:
    normalized = _normalize(value)
    return any(_normalize(needle) in normalized for needle in needles)
