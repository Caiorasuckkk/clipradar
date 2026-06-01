from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, validator

from app import config


router = APIRouter()

VALID_REVIEW_STATUSES = {"approved", "rejected", "needs_adjustment"}
REVIEWS_PATH = config.STORAGE_REVIEWS_DIR / "rendered_clip_reviews.json"


class RenderedClipReviewPayload(BaseModel):
    status: str
    rating: int = Field(..., ge=1, le=5)
    reason: str = Field(..., min_length=1)
    notes: str = ""
    ideal_start_seconds: float | None = None
    ideal_end_seconds: float | None = None

    @validator("status")
    def validate_status(cls, value: str) -> str:
        if value not in VALID_REVIEW_STATUSES:
            allowed = ", ".join(sorted(VALID_REVIEW_STATUSES))
            raise ValueError(f"status deve ser um de: {allowed}")
        return value

    @validator("reason")
    def validate_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason é obrigatório")
        return stripped


@router.get("/review/clips")
def list_review_clips(
    min_rating: float = Query(0),
    include_reviewed: bool = Query(True),
    video_id: str | None = Query(None),
) -> dict[str, Any]:
    clips = _load_rendered_clips()
    filtered = _filter_clips(
        clips,
        min_rating=min_rating,
        include_reviewed=include_reviewed,
        video_id=video_id,
    )
    return {"clips": filtered, "count": len(filtered)}


@router.get("/review/clips/next")
def get_next_review_clip(
    min_rating: float = Query(4),
    include_reviewed: bool = Query(False),
    video_id: str | None = Query(None),
) -> dict[str, Any]:
    clips = _filter_clips(
        _load_rendered_clips(),
        min_rating=min_rating,
        include_reviewed=include_reviewed,
        video_id=video_id,
    )
    if not clips:
        return {"message": "no_pending_clips", "clip": None}
    return {"message": "ok", "clip": clips[0]}


@router.get("/review/clips/{clip_id}")
def get_review_clip(clip_id: str) -> dict[str, Any]:
    clip = _find_clip_by_id(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="clip_not_found")
    return clip


@router.post("/review/clips/{clip_id}")
def save_review_clip(clip_id: str, payload: RenderedClipReviewPayload) -> dict[str, Any]:
    clip = _find_clip_by_id(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="clip_not_found")

    reviews = _load_reviews()
    now = datetime.utcnow().isoformat()
    previous = reviews.get(clip_id, {})
    review = {
        "clip_id": clip_id,
        "video_id": clip.get("video_id"),
        "output_filename": clip.get("output_filename"),
        "status": payload.status,
        "rating": payload.rating,
        "reason": payload.reason,
        "notes": payload.notes,
        "ideal_start_seconds": payload.ideal_start_seconds,
        "ideal_end_seconds": payload.ideal_end_seconds,
        "created_at": previous.get("created_at") or now,
        "reviewed_at": previous.get("reviewed_at") or now,
        "updated_at": now if previous else None,
    }
    reviews[clip_id] = review
    _save_reviews(reviews)
    return {"message": "review_saved", "review": review}


@router.get("/review/summary")
def review_summary() -> dict[str, Any]:
    clips = _load_rendered_clips()
    reviews = _load_reviews()
    clip_ids = {clip["clip_id"] for clip in clips}
    active_reviews = [
        review for clip_id, review in reviews.items() if clip_id in clip_ids and isinstance(review, dict)
    ]
    status_counts = Counter(str(review.get("status") or "") for review in active_reviews)
    ratings = [
        float(review.get("rating"))
        for review in active_reviews
        if _is_number(review.get("rating"))
    ]
    return {
        "total_exported": len(clips),
        "total_reviewed": len(active_reviews),
        "pending": max(0, len(clips) - len(active_reviews)),
        "approved": status_counts.get("approved", 0),
        "rejected": status_counts.get("rejected", 0),
        "needs_adjustment": status_counts.get("needs_adjustment", 0),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "count_by_reason": dict(Counter(str(review.get("reason") or "") for review in active_reviews)),
    }


@router.get("/exports/{filename}")
def serve_export(filename: str) -> FileResponse:
    if not _is_safe_export_filename(filename):
        raise HTTPException(status_code=404, detail="export_not_found")
    path = (config.STORAGE_EXPORTS_DIR / filename).resolve()
    exports_dir = config.STORAGE_EXPORTS_DIR.resolve()
    if path.parent != exports_dir or not path.exists() or path.suffix.lower() != ".mp4":
        raise HTTPException(status_code=404, detail="export_not_found")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


def _load_rendered_clips() -> list[dict[str, Any]]:
    reviews = _load_reviews()
    plan_items = _items_by_output_filename(_load_latest_items("approved_clips_plan_*.json"))
    render_items = _items_by_output_filename(_load_latest_items("render_report_*.json"))
    clips: list[dict[str, Any]] = []

    for path in sorted(config.STORAGE_EXPORTS_DIR.glob("*.mp4"), key=lambda item: item.name.lower()):
        plan_item = plan_items.get(path.name, {})
        render_item = render_items.get(path.name, {})
        clip_id = path.stem
        current_review = reviews.get(clip_id)
        merged = _clip_payload(path, clip_id, plan_item, render_item, current_review)
        clips.append(merged)

    return clips


def _clip_payload(
    path: Path,
    clip_id: str,
    plan_item: dict[str, Any],
    render_item: dict[str, Any],
    current_review: dict[str, Any] | None,
) -> dict[str, Any]:
    video_id, rank = _parse_clip_id(clip_id)
    output_filename = path.name
    final_start = _first_value(
        plan_item.get("final_start_seconds"),
        render_item.get("final_start"),
        plan_item.get("start_seconds"),
        render_item.get("start"),
    )
    final_end = _first_value(
        plan_item.get("final_end_seconds"),
        render_item.get("final_end"),
        plan_item.get("end_seconds"),
        render_item.get("end"),
    )
    duration = _first_value(
        plan_item.get("final_duration_seconds"),
        render_item.get("duration"),
        plan_item.get("duration_seconds"),
    )
    return {
        "clip_id": clip_id,
        "video_id": plan_item.get("video_id") or render_item.get("video_id") or video_id,
        "video_title": plan_item.get("video_title") or render_item.get("title") or "",
        "rank": plan_item.get("rank") or render_item.get("rank") or rank,
        "review_rating": plan_item.get("review_rating") or render_item.get("rating"),
        "review_reason": plan_item.get("review_reason") or render_item.get("reason") or "",
        "source_quality_score": plan_item.get("source_quality_score"),
        "source_quality_tier": plan_item.get("source_quality_tier"),
        "start_seconds": _first_value(plan_item.get("start_seconds"), render_item.get("start")),
        "end_seconds": _first_value(plan_item.get("end_seconds"), render_item.get("end")),
        "final_start_seconds": final_start,
        "final_end_seconds": final_end,
        "duration_seconds": duration,
        "youtube_url": plan_item.get("youtube_url") or "",
        "output_filename": output_filename,
        "video_url": f"/exports/{output_filename}",
        "file_size_bytes": path.stat().st_size,
        "already_reviewed": bool(current_review),
        "current_review": current_review,
    }


def _load_latest_items(pattern: str) -> list[dict[str, Any]]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    paths = sorted(reports_dir.glob(pattern))
    if not paths:
        return []
    payload = _load_json(paths[-1])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "clips", "approved_clips", "plan", "approved", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _items_by_output_filename(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        filename = _output_filename_from_item(item)
        if filename:
            indexed[filename] = item
    return indexed


def _output_filename_from_item(item: dict[str, Any]) -> str:
    output_filename = item.get("output_filename")
    if output_filename:
        return Path(str(output_filename)).name
    output_path = item.get("output_path")
    if output_path:
        return Path(str(output_path)).name
    return ""


def _find_clip_by_id(clip_id: str) -> dict[str, Any] | None:
    if not _is_safe_clip_id(clip_id):
        return None
    for clip in _load_rendered_clips():
        if clip["clip_id"] == clip_id:
            return clip
    return None


def _filter_clips(
    clips: list[dict[str, Any]],
    min_rating: float,
    include_reviewed: bool,
    video_id: str | None,
) -> list[dict[str, Any]]:
    filtered = []
    for clip in clips:
        if video_id and clip.get("video_id") != video_id:
            continue
        if _to_float(clip.get("review_rating")) < min_rating:
            continue
        if not include_reviewed and clip.get("already_reviewed"):
            continue
        filtered.append(clip)
    return filtered


def _load_reviews() -> dict[str, dict[str, Any]]:
    payload = _load_json(REVIEWS_PATH)
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items() if isinstance(value, dict)}
    return {}


def _save_reviews(reviews: dict[str, dict[str, Any]]) -> None:
    config.STORAGE_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    with REVIEWS_PATH.open("w", encoding="utf-8") as file:
        json.dump(reviews, file, ensure_ascii=False, indent=2)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _parse_clip_id(clip_id: str) -> tuple[str, int | None]:
    video_id = clip_id.split("__", 1)[0]
    match = re.search(r"__rank_(\d+)", clip_id)
    return video_id, int(match.group(1)) if match else None


def _is_safe_clip_id(clip_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+(?:__[A-Za-z0-9._-]+)*", clip_id))


def _is_safe_export_filename(filename: str) -> bool:
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+\.mp4", filename))


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
