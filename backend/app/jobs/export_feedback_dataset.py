from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


REVIEWED_STATUSES = {"approved", "rejected", "needs_adjustment"}
RENDERED_REVIEWS_PATH = config.STORAGE_REVIEWS_DIR / "rendered_clip_reviews.json"


def main() -> None:
    configure_output()
    include_rendered_reviews = "--no-rendered-reviews" not in sys.argv
    reviewed = [
        item
        for item in _iter_clips()
        if item["clip"].get("review_status", "pending_review") in REVIEWED_STATUSES
    ]
    reviewed.sort(
        key=lambda item: (
            str(item["clip"].get("reviewed_at") or ""),
            item["video_id"],
            int(item["clip"].get("rank") or 0),
        )
    )
    terminal_records = [_dataset_record(item) for item in reviewed]
    rendered_records = (
        _rendered_review_records()
        if include_rendered_reviews
        else []
    )
    records = terminal_records + rendered_records

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    config.STORAGE_TRENDS_DIR.parent.joinpath("reports").mkdir(parents=True, exist_ok=True)
    json_path = config.STORAGE_TRENDS_DIR.parent / "reports" / f"feedback_dataset_{timestamp}.json"
    md_path = config.STORAGE_TRENDS_DIR.parent / "reports" / f"feedback_dataset_{timestamp}.md"

    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "clips_count": len(records),
        "terminal_reviews_count": len(terminal_records),
        "rendered_reviews_count": len(rendered_records),
        "included_statuses": sorted(REVIEWED_STATUSES),
        "clips": records,
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))

    print("EXPORT FEEDBACK DATASET")
    print(f"clips revisados incluídos: {len(records)}")
    print(f"terminal reviews: {len(terminal_records)}")
    print(f"rendered app reviews: {len(rendered_records)}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print("pending_review incluídos: 0")


def _dataset_record(item: dict[str, Any]) -> dict[str, Any]:
    payload = item["payload"]
    clip = item["clip"]
    return {
        "video_id": item["video_id"],
        "source_collection": item["source_collection"],
        "feedback_origin": "terminal_review",
        "video_title": payload.get("video_title", ""),
        "channel_name": payload.get("channel_name", ""),
        "url": payload.get("url", ""),
        "rank": clip.get("rank"),
        "start_seconds": clip.get("start_seconds"),
        "end_seconds": clip.get("end_seconds"),
        "score": clip.get("score"),
        "text": clip.get("text", ""),
        "first_sentence": clip.get("first_sentence", ""),
        "review_status": clip.get("review_status", "pending_review"),
        "review_rating": clip.get("review_rating"),
        "review_reason": clip.get("review_reason", ""),
        "review_notes": clip.get("review_notes", ""),
        "status": clip.get("review_status", "pending_review"),
        "rating": clip.get("review_rating"),
        "reason": clip.get("review_reason", ""),
        "notes": clip.get("review_notes", ""),
        "ideal_start_seconds": clip.get("ideal_start_seconds"),
        "ideal_end_seconds": clip.get("ideal_end_seconds"),
        "reviewed_at": clip.get("reviewed_at"),
        "has_complete_ending": clip.get("has_complete_ending"),
        "has_development": clip.get("has_development"),
        "completeness_score": clip.get("completeness_score"),
        "selected_boundary_reason": clip.get("selected_boundary_reason"),
    }


def _rendered_review_records() -> list[dict[str, Any]]:
    reviews = _load_rendered_reviews()
    if not reviews:
        return []
    plan_index = _latest_plan_index()
    records: list[dict[str, Any]] = []
    for clip_id, review in sorted(reviews.items()):
        if not isinstance(review, dict):
            continue
        status = str(review.get("status") or "")
        if status not in REVIEWED_STATUSES:
            continue
        output_filename = Path(str(review.get("output_filename") or f"{clip_id}.mp4")).name
        video_id = str(review.get("video_id") or _video_id_from_clip_id(clip_id))
        rank = _rank_from_clip_id(clip_id)
        plan_item = _match_plan_item(plan_index, clip_id, output_filename, video_id, rank)
        record = {
            "source_collection": "rendered_clip_reviews",
            "feedback_origin": "rendered_app_review",
            "source_type": "rendered_export",
            "target": "rendered_clip",
            "clip_id": clip_id,
            "video_id": video_id,
            "output_filename": output_filename,
            "status": status,
            "rating": review.get("rating"),
            "reason": review.get("reason", ""),
            "notes": review.get("notes", ""),
            "review_status": status,
            "review_rating": review.get("rating"),
            "review_reason": review.get("reason", ""),
            "review_notes": review.get("notes", ""),
            "ideal_start_seconds": review.get("ideal_start_seconds"),
            "ideal_end_seconds": review.get("ideal_end_seconds"),
            "reviewed_at": review.get("reviewed_at"),
            "created_at": review.get("created_at"),
            "updated_at": review.get("updated_at"),
            "video_title": plan_item.get("video_title", ""),
            "rank": plan_item.get("rank") or rank,
            "start_seconds": plan_item.get("start_seconds"),
            "end_seconds": plan_item.get("end_seconds"),
            "final_start_seconds": plan_item.get("final_start_seconds"),
            "final_end_seconds": plan_item.get("final_end_seconds"),
            "duration_seconds": plan_item.get("final_duration_seconds")
            or plan_item.get("duration_seconds"),
            "youtube_url": plan_item.get("youtube_url", ""),
            "url": plan_item.get("youtube_url", ""),
            "source_quality_score": plan_item.get("source_quality_score"),
            "source_quality_tier": plan_item.get("source_quality_tier"),
            "ranking_quality_score": plan_item.get("ranking_quality_score"),
            "ranking_quality_tier": plan_item.get("ranking_quality_tier"),
            "topic_merge_score": plan_item.get("topic_merge_score"),
            "sponsor_product_score": plan_item.get("sponsor_product_score"),
            "score": plan_item.get("ranking_quality_score"),
            "text": "",
            "first_sentence": "",
            "has_complete_ending": None,
            "has_development": None,
            "completeness_score": None,
            "selected_boundary_reason": "",
        }
        records.append(record)
    return records


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# ClipRadar Feedback Dataset",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Reviewed clips: {payload['clips_count']}",
        f"Terminal reviews: {payload.get('terminal_reviews_count', 0)}",
        f"Rendered app reviews: {payload.get('rendered_reviews_count', 0)}",
        "",
        "Only manually reviewed clips are included. `pending_review` clips are excluded.",
        "",
    ]
    for clip in payload["clips"]:
        lines.extend(
            [
                f"## {clip['video_id']} rank {clip['rank']}",
                "",
                f"Title: {clip['video_title']}",
                f"Source collection: {clip['source_collection']}",
                f"Feedback origin: {clip.get('feedback_origin', '')}",
                f"Status: {clip['review_status']}",
                f"Rating: {clip['review_rating']}",
                f"Reason: {clip['review_reason']}",
                f"Ideal: {clip['ideal_start_seconds']} - {clip['ideal_end_seconds']}",
                f"Original: {clip['start_seconds']} - {clip['end_seconds']}",
                f"URL: {clip['url']}",
                "",
                f"Text: {_display(clip['text'], 500)}",
                "",
            ]
        )
    return "\n".join(lines)


def _iter_clips():
    if not config.STORAGE_CLIPS_DIR.exists():
        return
    for path in sorted(config.STORAGE_CLIPS_DIR.glob("*_clips.json")):
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception as exc:
            print(f"[dataset] falha ao ler {path}: {exc}")
            continue
        video_id = str(payload.get("video_id") or path.name.replace("_clips.json", ""))
        for source_collection in ("clips", "diagnostic_candidates"):
            for clip in payload.get(source_collection, []):
                yield {
                    "video_id": video_id,
                    "payload": payload,
                    "clip": clip,
                    "source_collection": source_collection,
                }


def _load_rendered_reviews() -> dict[str, dict[str, Any]]:
    if not RENDERED_REVIEWS_PATH.exists():
        return {}
    try:
        with RENDERED_REVIEWS_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as exc:
        print(f"[dataset] falha ao ler {RENDERED_REVIEWS_PATH}: {exc}")
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def _latest_plan_index() -> dict[str, Any]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    paths = sorted(reports_dir.glob("approved_clips_plan_*.json"))
    if not paths:
        return {"by_output": {}, "by_clip_id": {}, "by_video_rank": {}}
    try:
        with paths[-1].open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as exc:
        print(f"[dataset] falha ao ler plano aprovado {paths[-1]}: {exc}")
        return {"by_output": {}, "by_clip_id": {}, "by_video_rank": {}}
    items = payload.get("items", []) if isinstance(payload, dict) else []
    by_output: dict[str, dict[str, Any]] = {}
    by_clip_id: dict[str, dict[str, Any]] = {}
    by_video_rank: dict[tuple[str, int], dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        output_filename = Path(str(item.get("output_filename") or "")).name
        video_id = str(item.get("video_id") or "")
        rank = _safe_int(item.get("rank"))
        if output_filename:
            by_output[output_filename] = item
            by_clip_id[Path(output_filename).stem] = item
        if video_id and rank is not None:
            by_video_rank[(video_id, rank)] = item
    return {"by_output": by_output, "by_clip_id": by_clip_id, "by_video_rank": by_video_rank}


def _match_plan_item(
    index: dict[str, Any],
    clip_id: str,
    output_filename: str,
    video_id: str,
    rank: int | None,
) -> dict[str, Any]:
    if output_filename in index["by_output"]:
        return index["by_output"][output_filename]
    if clip_id in index["by_clip_id"]:
        return index["by_clip_id"][clip_id]
    if rank is not None and (video_id, rank) in index["by_video_rank"]:
        return index["by_video_rank"][(video_id, rank)]
    return {}


def _video_id_from_clip_id(clip_id: str) -> str:
    return clip_id.split("__", 1)[0]


def _rank_from_clip_id(clip_id: str) -> int | None:
    match = re.search(r"__rank_(\d+)", clip_id)
    return int(match.group(1)) if match else None


def _safe_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _display(value: object, limit: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
