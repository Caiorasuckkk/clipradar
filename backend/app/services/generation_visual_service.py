from __future__ import annotations

import re
import uuid
from typing import Any

from app.services.generation_workspace_service import get_project, update_project


VISUAL_TYPES = {"broll", "image", "text_card", "screenshot", "placeholder"}
VISUAL_SOURCES = {"local", "pexels", "generated", "manual", "placeholder"}
LICENSE_LANES = {"safe", "review", "restricted", "unknown"}
VISUAL_STATUSES = {"suggestion", "selected", "missing", "ready", "rejected"}


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
    seed_items: list[dict[str, Any]] = []

    for index, beat in enumerate(beats, start=1):
        line_index = min(index - 1, max(0, len(lines) - 1)) if lines else index - 1
        line = lines[line_index] if 0 <= line_index < len(lines) else str(beat.get("content") or "")
        seed_items.append(
            _visual_item(
                order=index,
                script_line_index=line_index,
                story_beat_id=str(beat.get("beat_id") or f"beat_{index}"),
                beat_role=str(beat.get("role") or ""),
                script_line=line,
                context=str(beat.get("content") or ""),
                project=project,
            )
        )

    if not seed_items:
        for index, line in enumerate(lines[:10], start=1):
            seed_items.append(
                _visual_item(
                    order=index,
                    script_line_index=index - 1,
                    story_beat_id="",
                    beat_role=_role_for_order(index),
                    script_line=line,
                    context=visual_context[(index - 1) % len(visual_context)] if visual_context else "",
                    project=project,
                )
            )

    if not seed_items:
        for index, context in enumerate(visual_context[:6], start=1):
            seed_items.append(
                _visual_item(
                    order=index,
                    script_line_index=index - 1,
                    story_beat_id="",
                    beat_role=_role_for_order(index),
                    script_line=context,
                    context=context,
                    project=project,
                )
            )

    if not seed_items:
        seed_items.append(
            _visual_item(
                order=1,
                script_line_index=0,
                story_beat_id="",
                beat_role="hook",
                script_line=str(project.get("title") or project.get("idea") or "tema principal"),
                context=str(project.get("niche") or ""),
                project=project,
            )
        )

    return _apply_timeline(seed_items, duration)


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
) -> dict[str, Any]:
    query = _query_for(script_line, context, project)
    lane = _license_lane({"query": query, "type": _type_for(query), "source": "placeholder"})
    return normalize_visual_item(
        {
            "order": order,
            "script_line_index": script_line_index,
            "story_beat_id": story_beat_id,
            "beat_role": beat_role,
            "type": _type_for(query),
            "query": query,
            "description": _description_for(script_line, context, beat_role, project),
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


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize(value: str) -> str:
    table = str.maketrans("áàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ", "aaaaeeioooucAAAAEEIOOOUC")
    return _clean(value).lower().translate(table)


def _contains_any(value: str, needles: list[str]) -> bool:
    normalized = _normalize(value)
    return any(_normalize(needle) in normalized for needle in needles)
