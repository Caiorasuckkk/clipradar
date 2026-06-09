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
    parser.add_argument("--no-candidate-limit", action="store_true")
    parser.add_argument("--max-candidates-per-video")
    parser.add_argument("--min-ranking-score", type=float, default=6.0)
    parser.add_argument("--min-source-score", type=float, default=0.0)
    parser.add_argument("--min-duration", type=float, default=25.0)
    parser.add_argument("--max-duration", type=float, default=120.0)
    parser.add_argument("--quality-threshold", type=float, default=6.0)
    parser.add_argument("--dedup-overlap", type=float, default=0.65)
    args = parser.parse_args()

    video_ids = _video_ids(args.video_id)
    reviews = load_candidate_reviews()
    raw_items: list[dict[str, Any]] = []
    for path in sorted(config.STORAGE_CLIPS_DIR.glob("*_clips.json")):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        video_id = str(payload.get("video_id") or path.name.replace("_clips.json", ""))
        if video_ids and video_id not in video_ids:
            continue
        raw_items.extend(_items_from_payload(payload, video_id, "clips", reviews))
        if args.include_diagnostics:
            raw_items.extend(_items_from_payload(payload, video_id, "diagnostic_candidates", reviews))

    filtered_items = _quality_filter_items(
        raw_items,
        min_ranking_score=args.min_ranking_score,
        min_source_score=args.min_source_score,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        quality_threshold=args.quality_threshold,
    )
    deduped_items, duplicates_removed = _dedupe_items(filtered_items, args.dedup_overlap)
    items = _limit_per_video(
        deduped_items,
        max_candidates_per_video=args.max_candidates_per_video,
        no_candidate_limit=args.no_candidate_limit,
    )
    if args.limit is not None:
        items = items[: max(0, args.limit)]
    stats_by_video = _stats_by_video(
        raw_items,
        filtered_items,
        deduped_items,
        items,
        no_candidate_limit=args.no_candidate_limit,
    )

    config.STORAGE_CANDIDATE_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    existing_payload = _load_json(QUEUE_PATH) if QUEUE_PATH.exists() and not args.overwrite else {}
    existing_items = (
        existing_payload.get("items", [])
        if isinstance(existing_payload, dict) and isinstance(existing_payload.get("items"), list)
        else []
    )
    duplicate_candidate_ids_removed = _duplicate_candidate_id_count(
        [item for item in existing_items if isinstance(item, dict)] + items
    ) if existing_items and not args.overwrite else 0
    if existing_items and not args.overwrite:
        items = _merge_existing_items(existing_items, items)

    exported_at = datetime.utcnow().isoformat()
    payload = {
        "generated_at": exported_at,
        "exported_at": exported_at,
        "video_id_filter": args.video_id,
        "include_diagnostics": bool(args.include_diagnostics),
        "no_candidate_limit": bool(args.no_candidate_limit),
        "max_candidates_per_video": args.max_candidates_per_video,
        "min_ranking_score": args.min_ranking_score,
        "min_source_score": args.min_source_score,
        "min_duration": args.min_duration,
        "max_duration": args.max_duration,
        "quality_threshold": args.quality_threshold,
        "dedup_overlap": args.dedup_overlap,
        "candidates_raw": len(raw_items),
        "candidates_after_quality_filter": len(filtered_items),
        "candidates_after_dedup": len(deduped_items),
        "duplicates_removed": duplicates_removed,
        "candidates_dropped_by_quality": max(0, len(raw_items) - len(filtered_items)),
        "candidates_dropped_by_dedupe": duplicates_removed,
        "candidates_dropped_by_limit": max(0, len(deduped_items) - len(items)),
        "duplicate_candidate_ids_removed": duplicate_candidate_ids_removed,
        "duplicates_removed_from_cache": max(0, len(existing_items) + len(selected_items) - len(items)) if existing_items and not args.overwrite else 0,
        "duplicates_removed_from_new_processing": duplicates_removed,
        "items_count": len(items),
        "merged_existing": bool(existing_items and not args.overwrite),
        "existing_items_count": len(existing_items),
        "stats_by_video": stats_by_video,
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
    print(f"candidates_raw: {len(raw_items)}")
    print(f"candidates_after_quality_filter: {len(filtered_items)}")
    print(f"candidates_after_dedup: {len(deduped_items)}")
    print(f"duplicates_removed: {duplicates_removed}")
    print(f"candidates_dropped_by_quality: {max(0, len(raw_items) - len(filtered_items))}")
    print(f"candidates_dropped_by_dedupe: {duplicates_removed}")
    print(f"candidates_dropped_by_limit: {max(0, len(deduped_items) - len(items))}")
    print(f"duplicate_candidate_ids_removed: {duplicate_candidate_ids_removed}")
    print(f"duplicates_removed_from_cache: {payload['duplicates_removed_from_cache']}")
    print(f"duplicates_removed_from_new_processing: {payload['duplicates_removed_from_new_processing']}")
    print(f"candidates: {len(items)}")
    print(f"merged_existing: {bool(existing_items and not args.overwrite)}")
    print(f"existing_items_count: {len(existing_items)}")
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
                "score": clip.get("score") or clip.get("ranking_quality_score"),
                "text": clip.get("text", ""),
                "source_quality_score": payload.get("source_quality_score") or analysis.get("source_quality_score"),
                "source_quality_tier": payload.get("source_quality_tier") or analysis.get("source_quality_tier"),
                "youtube_url": _youtube_url(payload, video_id, final_start or start),
                "output_preview_filename": output_preview_filename,
                "already_reviewed": bool(review),
                "current_candidate_review": review,
                "raw_thought_units_count": analysis.get("raw_thought_units_count"),
                "selection_limit_applied": analysis.get("selection_limit_applied"),
                "top_n_applied": analysis.get("top_n_applied"),
                "no_candidate_limit_enabled": analysis.get("no_candidate_limit_enabled"),
            }
        )
    return items


def _quality_filter_items(
    items: list[dict[str, Any]],
    min_ranking_score: float,
    min_source_score: float,
    min_duration: float,
    max_duration: float,
    quality_threshold: float,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        ranking = _candidate_score(item)
        source = _to_float(item.get("source_quality_score"))
        duration = _to_float(item.get("duration_seconds"))
        if ranking < max(min_ranking_score, quality_threshold):
            continue
        if source and source < min_source_score:
            continue
        if duration < min_duration or duration > max_duration:
            continue
        filtered.append({**item, "quality_score": round(ranking, 2)})
    return sorted(filtered, key=_candidate_sort_key, reverse=True)


def _dedupe_items(items: list[dict[str, Any]], overlap_threshold: float) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    removed = 0
    for item in sorted(items, key=_candidate_sort_key, reverse=True):
        duplicate = next(
            (
                other
                for other in kept
                if str(other.get("video_id") or "") == str(item.get("video_id") or "")
                and _overlap_ratio(item, other) >= overlap_threshold
            ),
            None,
        )
        if duplicate:
            removed += 1
            continue
        kept.append(item)
    return kept, removed


def _limit_per_video(
    items: list[dict[str, Any]],
    max_candidates_per_video: str | None,
    no_candidate_limit: bool,
) -> list[dict[str, Any]]:
    if no_candidate_limit or str(max_candidates_per_video or "").lower() == "unlimited":
        return items
    if not max_candidates_per_video:
        return items
    try:
        limit = int(max_candidates_per_video)
    except ValueError:
        return items
    if limit <= 0:
        return []
    counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for item in items:
        video_id = str(item.get("video_id") or "")
        current = counts.get(video_id, 0)
        if current >= limit:
            continue
        counts[video_id] = current + 1
        selected.append(item)
    return selected


def _merge_existing_items(existing_items: list[Any], new_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in existing_items:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or "")
        if candidate_id:
            merged[candidate_id] = item
    for item in new_items:
        candidate_id = str(item.get("candidate_id") or "")
        if candidate_id:
            merged[candidate_id] = item
    return list(merged.values())


def _duplicate_candidate_id_count(items: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    duplicates = 0
    for item in items:
        candidate_id = str(item.get("candidate_id") or "")
        if not candidate_id:
            continue
        if candidate_id in seen:
            duplicates += 1
        seen.add(candidate_id)
    return duplicates


def _stats_by_video(
    raw_items: list[dict[str, Any]],
    filtered_items: list[dict[str, Any]],
    deduped_items: list[dict[str, Any]],
    final_items: list[dict[str, Any]],
    no_candidate_limit: bool,
) -> list[dict[str, Any]]:
    video_ids = sorted(
        {
            str(item.get("video_id") or "")
            for group in (raw_items, filtered_items, deduped_items, final_items)
            for item in group
            if item.get("video_id")
        }
    )
    stats: list[dict[str, Any]] = []
    for video_id in video_ids:
        raw = [item for item in raw_items if item.get("video_id") == video_id]
        filtered = [item for item in filtered_items if item.get("video_id") == video_id]
        deduped = [item for item in deduped_items if item.get("video_id") == video_id]
        final = [item for item in final_items if item.get("video_id") == video_id]
        stats.append(
            {
                "video_id": video_id,
                "title": str((raw[0] if raw else {}).get("video_title") or video_id),
                "candidates_raw": len(raw),
                "candidates_after_filter": len(filtered),
                "candidates_after_dedup": len(deduped),
                "candidates_exported": len(final),
                "duplicates_removed": max(0, len(filtered) - len(deduped)),
                "candidates_dropped_by_quality": max(0, len(raw) - len(filtered)),
                "candidates_dropped_by_dedupe": max(0, len(filtered) - len(deduped)),
                "candidates_dropped_by_limit": max(0, len(deduped) - len(final)),
                "raw_thought_units_count": (raw[0] if raw else {}).get("raw_thought_units_count") or len(raw),
                "selection_limit_applied": (raw[0] if raw else {}).get("selection_limit_applied")
                or ("unlimited" if no_candidate_limit else None),
                "top_n_applied": (raw[0] if raw else {}).get("top_n_applied"),
                "no_candidate_limit_enabled": (
                    (raw[0] if raw else {}).get("no_candidate_limit_enabled")
                    if (raw[0] if raw else {}).get("no_candidate_limit_enabled") is not None
                    else no_candidate_limit
                ),
            }
        )
    return stats


def _candidate_sort_key(item: dict[str, Any]) -> tuple[float, float, float]:
    return (
        _candidate_score(item),
        _to_float(item.get("source_quality_score")),
        -_to_float(item.get("rank")),
    )


def _candidate_score(item: dict[str, Any]) -> float:
    return max(
        _to_float(item.get("ranking_quality_score")),
        _to_float(item.get("score")),
        _to_float(item.get("quality_score")),
    )


def _overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
    start = max(_to_float(left.get("start_seconds")), _to_float(right.get("start_seconds")))
    end = min(_to_float(left.get("end_seconds")), _to_float(right.get("end_seconds")))
    overlap = max(0.0, end - start)
    left_duration = max(1.0, _to_float(left.get("duration_seconds")))
    right_duration = max(1.0, _to_float(right.get("duration_seconds")))
    return overlap / min(left_duration, right_duration)


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
