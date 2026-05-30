from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any

from app import config


REVIEWED_STATUSES = {"approved", "rejected", "needs_adjustment"}


def main() -> None:
    configure_output()
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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    config.STORAGE_TRENDS_DIR.parent.joinpath("reports").mkdir(parents=True, exist_ok=True)
    json_path = config.STORAGE_TRENDS_DIR.parent / "reports" / f"feedback_dataset_{timestamp}.json"
    md_path = config.STORAGE_TRENDS_DIR.parent / "reports" / f"feedback_dataset_{timestamp}.md"

    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "clips_count": len(reviewed),
        "included_statuses": sorted(REVIEWED_STATUSES),
        "clips": [_dataset_record(item) for item in reviewed],
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))

    print("EXPORT FEEDBACK DATASET")
    print(f"clips revisados incluídos: {len(reviewed)}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print("pending_review incluídos: 0")


def _dataset_record(item: dict[str, Any]) -> dict[str, Any]:
    payload = item["payload"]
    clip = item["clip"]
    return {
        "video_id": item["video_id"],
        "source_collection": item["source_collection"],
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
        "ideal_start_seconds": clip.get("ideal_start_seconds"),
        "ideal_end_seconds": clip.get("ideal_end_seconds"),
        "reviewed_at": clip.get("reviewed_at"),
        "has_complete_ending": clip.get("has_complete_ending"),
        "has_development": clip.get("has_development"),
        "completeness_score": clip.get("completeness_score"),
        "selected_boundary_reason": clip.get("selected_boundary_reason"),
    }


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# ClipRadar Feedback Dataset",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Reviewed clips: {payload['clips_count']}",
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
