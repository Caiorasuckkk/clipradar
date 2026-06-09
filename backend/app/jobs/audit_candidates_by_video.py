from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from statistics import mean
from typing import Any

from app.services.candidate_review_service import QUEUE_PATH, load_candidate_queue


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    queue_payload = _load_queue_payload()
    export_stats = {
        str(item.get("video_id") or ""): item
        for item in queue_payload.get("stats_by_video", [])
        if isinstance(item, dict)
    }
    candidates = load_candidate_queue()
    if args.video_id:
        candidates = [item for item in candidates if str(item.get("video_id") or "") == args.video_id]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[str(item.get("video_id") or "")].append(item)

    videos: list[dict[str, Any]] = []
    for video_id in sorted(grouped):
        items = grouped[video_id]
        reviews = [
            item.get("current_candidate_review")
            for item in items
            if isinstance(item.get("current_candidate_review"), dict)
        ]
        scores = [_candidate_score(item) for item in items if _candidate_score(item) > 0]
        status_counts: dict[str, int] = defaultdict(int)
        for review in reviews:
            status_counts[str(review.get("status") or "")] += 1
        exported = export_stats.get(video_id, {})
        videos.append(
            {
                "video_id": video_id,
                "video_title": str(items[0].get("video_title") or exported.get("title") or video_id),
                "candidates_raw": exported.get("candidates_raw"),
                "candidates_after_filter": exported.get("candidates_after_filter"),
                "candidates_after_dedup": exported.get("candidates_after_dedup"),
                "duplicates_removed": exported.get("duplicates_removed"),
                "candidates_dropped_by_quality": exported.get("candidates_dropped_by_quality"),
                "candidates_dropped_by_dedupe": exported.get("candidates_dropped_by_dedupe"),
                "candidates_dropped_by_limit": exported.get("candidates_dropped_by_limit"),
                "raw_thought_units_count": exported.get("raw_thought_units_count"),
                "selection_limit_applied": exported.get("selection_limit_applied"),
                "top_n_applied": exported.get("top_n_applied"),
                "no_candidate_limit_enabled": exported.get("no_candidate_limit_enabled"),
                "candidates_exported": len(items),
                "preview_ready": sum(1 for item in items if item.get("preview_exists")),
                "preview_missing": sum(1 for item in items if not item.get("preview_exists")),
                "reviewed": len(reviews),
                "pending": max(0, len(items) - len(reviews)),
                "approved": status_counts.get("approved", 0),
                "rejected": status_counts.get("rejected", 0),
                "needs_adjustment": status_counts.get("needs_adjustment", 0),
                "average_quality_score": round(mean(scores), 2) if scores else None,
                "max_quality_score": round(max(scores), 2) if scores else None,
            }
        )

    approved_total = sum(item["approved"] for item in videos)
    reviewed_total = sum(item["reviewed"] for item in videos)
    total_candidates = sum(item["candidates_exported"] for item in videos)
    videos_requested = len(_video_ids(str(queue_payload.get("video_id_filter") or ""))) or len(export_stats)
    payload = {
        "queue_path": str(QUEUE_PATH),
        "generated_at": queue_payload.get("generated_at"),
        "videos_requested": videos_requested,
        "videos_processed": len(export_stats) or len(videos),
        "videos_with_candidates": sum(1 for item in videos if item["candidates_exported"] > 0),
        "raw_candidates_total": sum(_int_or_zero(item["candidates_raw"]) for item in videos),
        "candidates_after_quality": sum(_int_or_zero(item["candidates_after_filter"]) for item in videos),
        "candidates_after_dedupe": sum(_int_or_zero(item["candidates_after_dedup"]) for item in videos),
        "total_videos": len(videos),
        "total_candidates": total_candidates,
        "preview_ready": sum(item["preview_ready"] for item in videos),
        "preview_missing": sum(item["preview_missing"] for item in videos),
        "average_candidates_per_video": round(total_candidates / len(videos), 2) if videos else 0,
        "approval_rate": round(approved_total / reviewed_total, 4) if reviewed_total else None,
        "videos": videos,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("AUDIT CANDIDATES BY VIDEO")
    print(f"videos_requested: {payload['videos_requested']}")
    print(f"videos_processed: {payload['videos_processed']}")
    print(f"videos_with_candidates: {payload['videos_with_candidates']}")
    print(f"videos: {payload['total_videos']}")
    print(f"candidates: {payload['total_candidates']}")
    print(f"raw_candidates_total: {payload['raw_candidates_total']}")
    print(f"candidates_after_quality: {payload['candidates_after_quality']}")
    print(f"candidates_after_dedupe: {payload['candidates_after_dedupe']}")
    print(f"preview_ready: {payload['preview_ready']}")
    print(f"preview_missing: {payload['preview_missing']}")
    print(f"average_candidates_per_video: {payload['average_candidates_per_video']}")
    print(f"approval_rate: {payload['approval_rate']}")
    print("")
    for item in videos:
        print(f"- {item['video_id']} | {item['candidates_exported']} candidates | ready {item['preview_ready']} | missing {item['preview_missing']}")
        print(
            "  "
            f"raw={item['candidates_raw']} "
            f"filter={item['candidates_after_filter']} "
            f"dedup={item['candidates_after_dedup']} "
            f"dupes={item['duplicates_removed']} "
            f"avg={item['average_quality_score']} max={item['max_quality_score']}"
        )
        print(
            "  "
            f"thought_units={item['raw_thought_units_count']} "
            f"selection_limit={item['selection_limit_applied']} "
            f"top_n={item['top_n_applied']} "
            f"no_limit={item['no_candidate_limit_enabled']}"
        )
        print(
            "  "
            f"dropped_quality={item['candidates_dropped_by_quality']} "
            f"dropped_dedupe={item['candidates_dropped_by_dedupe']} "
            f"dropped_limit={item['candidates_dropped_by_limit']}"
        )
        print(
            "  "
            f"pending={item['pending']} approved={item['approved']} "
            f"rejected={item['rejected']} needs_adjustment={item['needs_adjustment']}"
        )


def _load_queue_payload() -> dict[str, Any]:
    try:
        with QUEUE_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _candidate_score(item: dict[str, Any]) -> float:
    return max(
        _to_float(item.get("quality_score")),
        _to_float(item.get("ranking_quality_score")),
        _to_float(item.get("score")),
    )


def _video_ids(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _to_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
