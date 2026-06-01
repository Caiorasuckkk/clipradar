from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.candidate_review_service import QUEUE_PATH, load_candidate_reviews


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--include-diagnostics", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    video_ids = _video_ids(args.video_id)
    reviews = load_candidate_reviews()
    items: list[dict[str, Any]] = []
    for path in sorted(config.STORAGE_CLIPS_DIR.glob("*_clips.json")):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        video_id = str(payload.get("video_id") or path.name.replace("_clips.json", ""))
        if video_ids and video_id not in video_ids:
            continue
        items.extend(_items_from_payload(payload, video_id, "clips", reviews))
        if args.include_diagnostics:
            items.extend(_items_from_payload(payload, video_id, "diagnostic_candidates", reviews))

    if args.limit is not None:
        items = items[: max(0, args.limit)]

    config.STORAGE_CANDIDATE_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    if QUEUE_PATH.exists() and not args.overwrite:
        print("EXPORT CANDIDATE REVIEW QUEUE")
        print(f"Queue já existe: {QUEUE_PATH}")
        print("Use --overwrite para recriar.")
        return

    exported_at = datetime.utcnow().isoformat()
    payload = {
        "generated_at": exported_at,
        "exported_at": exported_at,
        "video_id_filter": args.video_id,
        "include_diagnostics": bool(args.include_diagnostics),
        "items_count": len(items),
        "items": items,
    }
    _write_json(QUEUE_PATH, payload)
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"candidate_review_queue_{timestamp}.json"
    md_path = reports_dir / f"candidate_review_queue_{timestamp}.md"
    _write_json(json_path, payload)
    md_path.write_text(_markdown_report(payload), encoding="utf-8")

    print("EXPORT CANDIDATE REVIEW QUEUE")
    print(f"candidates: {len(items)}")
    print(f"queue: {QUEUE_PATH}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


def _items_from_payload(
    payload: dict[str, Any],
    video_id: str,
    source_collection: str,
    reviews: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    analysis = payload.get("analysis_summary") or {}
    for index, clip in enumerate(payload.get(source_collection, []) or [], start=1):
        if not isinstance(clip, dict):
            continue
        rank = int(clip.get("rank") or index)
        start = _to_float(clip.get("start_seconds"))
        end = _to_float(clip.get("end_seconds"))
        final_start = _first(clip.get("final_start_seconds"), clip.get("suggested_trim_start_seconds"))
        final_end = _first(clip.get("final_end_seconds"), clip.get("suggested_trim_end_seconds"))
        candidate_id = _candidate_id(video_id, source_collection, rank, final_start or start, final_end or end)
        review = reviews.get(candidate_id)
        output_preview_filename = f"{_slug(candidate_id)}.mp4"
        items.append(
            {
                "candidate_id": candidate_id,
                "video_id": video_id,
                "video_title": payload.get("video_title", ""),
                "source_collection": source_collection,
                "rank": rank,
                "start_seconds": start,
                "end_seconds": end,
                "final_start_seconds": _to_float(final_start) if final_start is not None else None,
                "final_end_seconds": _to_float(final_end) if final_end is not None else None,
                "duration_seconds": _to_float(clip.get("duration_seconds")) or max(0.0, end - start),
                "reason": clip.get("review_reason") or clip.get("reason") or clip.get("selected_boundary_reason") or "",
                "ranking_quality_score": clip.get("ranking_quality_score") or clip.get("score"),
                "ranking_quality_tier": clip.get("ranking_quality_tier"),
                "source_quality_score": payload.get("source_quality_score") or analysis.get("source_quality_score"),
                "source_quality_tier": payload.get("source_quality_tier") or analysis.get("source_quality_tier"),
                "youtube_url": _youtube_url(payload, video_id, final_start or start),
                "output_preview_filename": output_preview_filename,
                "already_reviewed": bool(review),
                "current_candidate_review": review,
            }
        )
    return items


def _candidate_id(video_id: str, source_collection: str, rank: int, start: object, end: object) -> str:
    return f"{video_id}__candidate_{source_collection}_{rank}_{int(round(_to_float(start)))}_{int(round(_to_float(end)))}"


def _youtube_url(payload: dict[str, Any], video_id: str, start_seconds: object) -> str:
    base_url = str(payload.get("url") or f"https://www.youtube.com/watch?v={video_id}")
    if re.search(r"[?&]t=", base_url):
        return base_url
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}t={int(_to_float(start_seconds))}s"


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = ["# Candidate Review Queue", "", f"Items: {payload['items_count']}", ""]
    for item in payload["items"]:
        lines.extend(
            [
                f"## {item['candidate_id']}",
                "",
                f"Video: {item['video_title']}",
                f"Collection: {item['source_collection']}",
                f"Rank: {item['rank']}",
                f"Time: {item['start_seconds']} - {item['end_seconds']}",
                f"Preview: {item['output_preview_filename']}",
                "",
            ]
        )
    return "\n".join(lines)


def _video_ids(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _to_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _slug(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or "candidate"


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
