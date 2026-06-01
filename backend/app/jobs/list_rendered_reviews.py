from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app import config


REVIEWS_PATH = config.STORAGE_REVIEWS_DIR / "rendered_clip_reviews.json"


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--reason")
    args = parser.parse_args()

    reviews = _load_reviews()
    items = [
        review
        for review in reviews.values()
        if not args.reason or str(review.get("reason") or "") == args.reason
    ]
    items.sort(key=lambda item: str(item.get("reviewed_at") or ""))

    print("LIST RENDERED REVIEWS")
    print(f"source: {REVIEWS_PATH}")
    print(f"total: {len(items)}")
    if args.reason:
        print(f"reason: {args.reason}")
    print("")
    for item in items:
        print(
            f"- {item.get('clip_id', '')} | video_id={item.get('video_id', '')} | "
            f"status={item.get('status', '')} | rating={item.get('rating', '')} | "
            f"reason={item.get('reason', '')} | reviewed_at={item.get('reviewed_at', '')}"
        )


def _load_reviews() -> dict[str, dict[str, Any]]:
    if not REVIEWS_PATH.exists():
        return {}
    try:
        with REVIEWS_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as exc:
        print(f"Falha ao ler {REVIEWS_PATH}: {exc}")
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
