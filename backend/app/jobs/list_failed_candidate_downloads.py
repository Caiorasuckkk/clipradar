from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app import config


FAILED_DOWNLOADS_PATH = config.STORAGE_TRENDS_DIR.parent / "reports" / "failed_candidate_downloads.json"


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--clear-video-id")
    args = parser.parse_args()

    failures = _load_failures()
    if args.clear:
        _write_failures([])
        print("failed_candidate_downloads limpo.")
        return
    if args.clear_video_id:
        failures = [
            failure
            for failure in failures
            if str(failure.get("video_id") or "") != args.clear_video_id
        ]
        _write_failures(failures)
        print(f"falhas removidas para video_id={args.clear_video_id}")
        return

    listed = failures
    if args.video_id:
        listed = [
            failure
            for failure in listed
            if str(failure.get("video_id") or "") == args.video_id
        ]

    print("FAILED CANDIDATE DOWNLOADS")
    print(f"total: {len(listed)}")
    print(f"path: {FAILED_DOWNLOADS_PATH}")
    print("")
    for failure in listed:
        print(f"- video_id: {failure.get('video_id')}")
        print(f"  candidate_id: {failure.get('candidate_id')}")
        print(f"  youtube_url: {failure.get('youtube_url')}")
        print(f"  error_message: {failure.get('error_message')}")
        print(f"  failed_at: {failure.get('failed_at')}")
        print(f"  retry_count: {failure.get('retry_count')}")


def _load_failures() -> list[dict[str, Any]]:
    if not FAILED_DOWNLOADS_PATH.exists():
        return []
    try:
        with FAILED_DOWNLOADS_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _write_failures(failures: list[dict[str, Any]]) -> None:
    FAILED_DOWNLOADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FAILED_DOWNLOADS_PATH.open("w", encoding="utf-8") as file:
        json.dump(failures, file, ensure_ascii=False, indent=2)


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
