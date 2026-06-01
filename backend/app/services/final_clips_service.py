from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


FINAL_REVIEWS_PATH = config.STORAGE_FINAL_REVIEWS_DIR / "final_clip_reviews.json"


def load_final_clips(include_duration: bool = True) -> list[dict[str, Any]]:
    plan_items = _items_by_output_filename(_load_latest_items("approved_clips_plan_*.json"))
    rendered_reviews = load_rendered_reviews()
    final_reviews = load_final_reviews()
    exported_at = datetime.utcnow().isoformat()
    clips: list[dict[str, Any]] = []
    for path in sorted(config.STORAGE_FINAL_EXPORTS_DIR.glob("*.mp4"), key=lambda item: item.name.lower()):
        final_clip_id = path.stem
        clip_id = _clip_id_from_final_filename(path.name)
        source_export_filename = f"{clip_id}.mp4"
        vertical_filename = f"{clip_id}__vertical.mp4"
        plan_item = plan_items.get(source_export_filename, {})
        rendered_review = rendered_reviews.get(clip_id, {})
        final_review = final_reviews.get(final_clip_id)
        clips.append(
            _final_clip_payload(
                path=path,
                final_clip_id=final_clip_id,
                clip_id=clip_id,
                source_export_filename=source_export_filename,
                vertical_filename=vertical_filename,
                plan_item=plan_item,
                rendered_review=rendered_review,
                final_review=final_review,
                exported_at=exported_at,
                include_duration=include_duration,
            )
        )
    return clips


def final_summary() -> dict[str, Any]:
    clips = load_final_clips(include_duration=False)
    reviews = [
        clip["current_final_review"]
        for clip in clips
        if isinstance(clip.get("current_final_review"), dict)
    ]
    status_counts = Counter(str(review.get("status") or "") for review in reviews)
    ratings = [
        float(review.get("rating"))
        for review in reviews
        if _is_number(review.get("rating"))
    ]
    return {
        "total_final": len(clips),
        "reviewed": len(reviews),
        "pending": max(0, len(clips) - len(reviews)),
        "ready_to_post": status_counts.get("ready_to_post", 0),
        "do_not_post": status_counts.get("do_not_post", 0),
        "needs_edit": status_counts.get("needs_edit", 0),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "count_by_reason": dict(Counter(str(review.get("reason") or "") for review in reviews)),
    }


def filter_final_clips(clips: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    if status not in {"pending", "reviewed", "ready", "rejected", "all"}:
        status = "pending"
    filtered: list[dict[str, Any]] = []
    for clip in clips:
        reviewed = bool(clip.get("already_reviewed"))
        review_status = str(clip.get("final_review_status") or "")
        if status == "pending" and reviewed:
            continue
        if status == "reviewed" and not reviewed:
            continue
        if status == "ready" and review_status != "ready_to_post":
            continue
        if status == "rejected" and review_status != "do_not_post":
            continue
        filtered.append(clip)
    return filtered


def load_final_reviews() -> dict[str, dict[str, Any]]:
    payload = _load_json(FINAL_REVIEWS_PATH)
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items() if isinstance(value, dict)}
    return {}


def save_final_reviews(reviews: dict[str, dict[str, Any]]) -> None:
    config.STORAGE_FINAL_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    with FINAL_REVIEWS_PATH.open("w", encoding="utf-8") as file:
        json.dump(reviews, file, ensure_ascii=False, indent=2)


def load_rendered_reviews() -> dict[str, dict[str, Any]]:
    path = config.STORAGE_REVIEWS_DIR / "rendered_clip_reviews.json"
    payload = _load_json(path)
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items() if isinstance(value, dict)}
    return {}


def _final_clip_payload(
    path: Path,
    final_clip_id: str,
    clip_id: str,
    source_export_filename: str,
    vertical_filename: str,
    plan_item: dict[str, Any],
    rendered_review: dict[str, Any],
    final_review: dict[str, Any] | None,
    exported_at: str,
    include_duration: bool,
) -> dict[str, Any]:
    video_id, rank = _parse_clip_id(clip_id)
    review_status = str(final_review.get("status") or "") if final_review else ""
    duration_seconds = _first_value(plan_item.get("final_duration_seconds"), plan_item.get("duration_seconds"))
    final_duration_seconds = _probe_duration(path) if include_duration else None
    return {
        "final_clip_id": final_clip_id,
        "clip_id": clip_id,
        "video_id": str(plan_item.get("video_id") or rendered_review.get("video_id") or video_id),
        "video_title": str(plan_item.get("video_title") or ""),
        "original_youtube_url": str(plan_item.get("youtube_url") or ""),
        "final_filename": path.name,
        "final_path": str(path),
        "final_url_local": f"/final_exports/{path.name}",
        "source_export_filename": source_export_filename,
        "vertical_filename": vertical_filename,
        "rank": plan_item.get("rank") or rank,
        "rating": _first_value(rendered_review.get("rating"), plan_item.get("review_rating")),
        "reason": _first_value(rendered_review.get("reason"), plan_item.get("review_reason"), ""),
        "review_status": rendered_review.get("status") or plan_item.get("review_status"),
        "review_rating": _first_value(rendered_review.get("rating"), plan_item.get("review_rating")),
        "review_reason": _first_value(rendered_review.get("reason"), plan_item.get("review_reason"), ""),
        "review_notes": _first_value(rendered_review.get("notes"), plan_item.get("review_notes"), ""),
        "start_seconds": _first_value(plan_item.get("final_start_seconds"), plan_item.get("start_seconds")),
        "end_seconds": _first_value(plan_item.get("final_end_seconds"), plan_item.get("end_seconds")),
        "duration_seconds": duration_seconds,
        "final_duration_seconds": _first_value(final_duration_seconds, duration_seconds),
        "file_size_bytes": path.stat().st_size if path.exists() else None,
        "ready_to_post": review_status == "ready_to_post",
        "post_status": review_status or "pending_final_review",
        "created_at": _first_value(plan_item.get("created_at"), rendered_review.get("created_at")),
        "exported_at": exported_at,
        "already_reviewed": bool(final_review),
        "current_final_review": final_review,
        "final_review_status": review_status or None,
        "final_review_rating": final_review.get("rating") if final_review else None,
        "final_review_reason": final_review.get("reason") if final_review else None,
        "final_review_notes": final_review.get("notes") if final_review else None,
        "final_reviewed_at": final_review.get("reviewed_at") if final_review else None,
    }


def _clip_id_from_final_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = stem.removesuffix("__final")
    stem = stem.removesuffix("__vertical")
    return stem


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
        output_filename = item.get("output_filename")
        if output_filename:
            indexed[Path(str(output_filename)).name] = item
    return indexed


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _parse_clip_id(clip_id: str) -> tuple[str, int | None]:
    video_id = clip_id.split("__", 1)[0]
    match = re.search(r"__rank_(\d+)", clip_id)
    return video_id, int(match.group(1)) if match else None


def _probe_duration(input_path: Path) -> float | None:
    if not input_path.exists():
        return None
    command = [
        _ffprobe_executable(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    try:
        return round(float((completed.stdout or "").strip()), 2)
    except (TypeError, ValueError):
        return None


def _ffprobe_executable() -> str:
    found = shutil.which("ffprobe")
    if found:
        return found
    found_ffmpeg = shutil.which("ffmpeg")
    if found_ffmpeg:
        candidate = Path(found_ffmpeg).with_name(Path(found_ffmpeg).name.replace("ffmpeg", "ffprobe", 1))
        if candidate.exists():
            return str(candidate)
    try:
        import imageio_ffmpeg

        ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
        candidate = ffmpeg_path.with_name(ffmpeg_path.name.replace("ffmpeg", "ffprobe", 1))
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass
    return "ffprobe"


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
