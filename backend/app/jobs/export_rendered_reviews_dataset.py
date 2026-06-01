from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


REVIEWS_PATH = config.STORAGE_REVIEWS_DIR / "rendered_clip_reviews.json"


def main() -> None:
    configure_output()
    reviews = _load_reviews()
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"rendered_reviews_dataset_{timestamp}.json"
    md_path = reports_dir / f"rendered_reviews_dataset_{timestamp}.md"
    items = list(reviews.values())
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "source_path": str(REVIEWS_PATH),
        "reviews_count": len(items),
        "count_by_status": dict(Counter(str(item.get("status") or "") for item in items)),
        "count_by_reason": dict(Counter(str(item.get("reason") or "") for item in items)),
        "items": items,
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown(payload))

    print("EXPORT RENDERED REVIEWS DATASET")
    print(f"reviews: {len(items)}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


def _load_reviews() -> dict[str, dict[str, Any]]:
    if not REVIEWS_PATH.exists():
        return {}
    with REVIEWS_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Rendered Reviews Dataset",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Source: {payload['source_path']}",
        f"Reviews: {payload['reviews_count']}",
        "",
        "## Reviews",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"### {item.get('clip_id', '')}",
                "",
                f"* video_id: {item.get('video_id', '')}",
                f"* output: {item.get('output_filename', '')}",
                f"* status: {item.get('status', '')}",
                f"* rating: {item.get('rating', '')}",
                f"* reason: {item.get('reason', '')}",
                f"* notes: {item.get('notes', '')}",
                f"* ideal: {item.get('ideal_start_seconds')} - {item.get('ideal_end_seconds')}",
                "",
            ]
        )
    return "\n".join(lines)


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
