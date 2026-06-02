from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from app import config
from app.services.candidate_preview_validation_service import validate_candidate_preview


QUEUE_PATH = config.STORAGE_CANDIDATE_QUEUE_DIR / "candidate_review_queue.json"
REVIEWS_PATH = config.STORAGE_CANDIDATE_REVIEWS_DIR / "candidate_clip_reviews.json"


def load_candidate_queue() -> list[dict[str, Any]]:
    payload = _load_json(QUEUE_PATH)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    reviews = load_candidate_reviews()
    merged: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or "")
        review = reviews.get(candidate_id)
        enriched = dict(item)
        enriched["already_reviewed"] = bool(review)
        enriched["current_candidate_review"] = review
        enriched["candidate_review_status"] = review.get("status") if review else None
        enriched["candidate_review_rating"] = review.get("rating") if review else None
        enriched["candidate_review_reason"] = review.get("reason") if review else None
        enriched["candidate_review_notes"] = review.get("notes") if review else None
        enriched.update(preview_status_for_candidate(enriched))
        merged.append(enriched)
    return merged


def preview_status_for_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    filename = str(candidate.get("output_preview_filename") or "")
    path = config.STORAGE_CANDIDATE_PREVIEWS_DIR / filename if filename else None
    validation = validate_candidate_preview(path) if path else None
    exists = bool(validation and validation.valid)
    invalid = bool(validation and path and path.exists() and not validation.valid)
    return {
        "preview_exists": exists,
        "preview_path": str(path) if path else "",
        "preview_url": f"/candidate_previews/{filename}" if filename else "",
        "preview_missing": not exists,
        "preview_invalid": invalid,
        "preview_validation_error": validation.error_message if validation else "",
    }


def filter_candidate_clips(
    clips: list[dict[str, Any]],
    status: str,
    video_id: str | None = None,
    include_missing_previews: bool = False,
) -> list[dict[str, Any]]:
    if status not in {"pending", "reviewed", "approved", "rejected", "all"}:
        status = "pending"
    filtered: list[dict[str, Any]] = []
    for clip in clips:
        if video_id and str(clip.get("video_id") or "") != video_id:
            continue
        if not include_missing_previews and not clip.get("preview_exists"):
            continue
        reviewed = bool(clip.get("already_reviewed"))
        review_status = str(clip.get("candidate_review_status") or "")
        if status == "pending" and reviewed:
            continue
        if status == "reviewed" and not reviewed:
            continue
        if status == "approved" and review_status != "approved":
            continue
        if status == "rejected" and review_status != "rejected":
            continue
        filtered.append(clip)
    return filtered


def candidate_summary() -> dict[str, Any]:
    clips = load_candidate_queue()
    preview_ready = sum(1 for clip in clips if clip.get("preview_exists"))
    missing_preview = sum(1 for clip in clips if not clip.get("preview_exists"))
    reviews = [
        clip["current_candidate_review"]
        for clip in clips
        if isinstance(clip.get("current_candidate_review"), dict)
    ]
    status_counts = Counter(str(review.get("status") or "") for review in reviews)
    ratings = [
        float(review.get("rating"))
        for review in reviews
        if _is_number(review.get("rating"))
    ]
    return {
        "total_candidates": len(clips),
        "preview_ready": preview_ready,
        "missing_preview": missing_preview,
        "reviewed": len(reviews),
        "pending": max(0, len(clips) - len(reviews)),
        "approved": status_counts.get("approved", 0),
        "rejected": status_counts.get("rejected", 0),
        "needs_adjustment": status_counts.get("needs_adjustment", 0),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "count_by_reason": dict(Counter(str(review.get("reason") or "") for review in reviews)),
    }


def load_candidate_reviews() -> dict[str, dict[str, Any]]:
    payload = _load_json(REVIEWS_PATH)
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items() if isinstance(value, dict)}
    return {}


def save_candidate_reviews(reviews: dict[str, dict[str, Any]]) -> None:
    config.STORAGE_CANDIDATE_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    with REVIEWS_PATH.open("w", encoding="utf-8") as file:
        json.dump(reviews, file, ensure_ascii=False, indent=2)


def is_safe_candidate_id(candidate_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+(?:__[A-Za-z0-9._-]+)*", candidate_id))


def is_safe_preview_filename(filename: str) -> bool:
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+\.mp4", filename))


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
