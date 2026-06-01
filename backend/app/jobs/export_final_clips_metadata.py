from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.final_clips_service import load_final_clips


def main() -> None:
    configure_output()
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"final_clips_metadata_{timestamp}.json"
    md_path = reports_dir / f"final_clips_metadata_{timestamp}.md"
    items = load_final_clips(include_duration=True)
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_final": len(items),
        "ready_to_post": sum(1 for item in items if item.get("ready_to_post") is True),
        "pending_final_review": sum(
            1 for item in items if item.get("post_status") == "pending_final_review"
        ),
        "items": items,
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))

    print("EXPORT FINAL CLIPS METADATA")
    print(f"final clips: {len(items)}")
    print(f"pending final review: {payload['pending_final_review']}")
    print(f"ready to post: {payload['ready_to_post']}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print("")
    for reason, count in Counter(str(item.get("reason") or "sem_reason") for item in items).most_common(8):
        print(f"- {reason}: {count}")


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Final Clips Metadata",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Total final: {payload['total_final']}",
        f"Pending final review: {payload['pending_final_review']}",
        f"Ready to post: {payload['ready_to_post']}",
        "",
        "## Clips",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"### {item.get('final_filename')} - {item.get('post_status')}",
                "",
                f"Final clip ID: {item.get('final_clip_id')}",
                f"Clip ID: {item.get('clip_id')}",
                f"Video: {item.get('video_title') or item.get('video_id')}",
                f"Rank: {item.get('rank')}",
                f"Rating/reason: {item.get('rating')} / {item.get('reason')}",
                f"Rendered review: {item.get('review_status')} / {item.get('review_rating')} / {item.get('review_reason')}",
                f"Time: {_fmt(item.get('start_seconds'))} - {_fmt(item.get('end_seconds'))}",
                f"Duration: {item.get('final_duration_seconds') or item.get('duration_seconds')}s",
                f"Ready to post: {str(item.get('ready_to_post')).lower()}",
                f"Path: {item.get('final_path')}",
                f"Local URL: {item.get('final_url_local')}",
                "",
            ]
        )
    return "\n".join(lines)


def _fmt(value: object) -> str:
    try:
        total = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return "-"
    minutes, seconds = divmod(total, 60)
    return f"{minutes}:{seconds:02d}"


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
