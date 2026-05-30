from __future__ import annotations

import json
import sys
from typing import Any

from app import config


PENDING_STATUSES = {"pending_review", "needs_adjustment"}


def main() -> None:
    configure_output()
    clips = list(_iter_clips())
    pending = [
        item
        for item in clips
        if item["clip"].get("review_status", "pending_review") in PENDING_STATUSES
    ]
    pending.sort(
        key=lambda item: (
            item["clip"].get("review_status", "pending_review") != "needs_adjustment",
            item["video_id"],
            int(item["clip"].get("rank") or 0),
        )
    )

    print("PENDING CLIP REVIEWS")
    print(f"Total pending/needs_adjustment: {len(pending)}")
    print("")
    for item in pending:
        payload = item["payload"]
        clip = item["clip"]
        start = float(clip.get("start_seconds") or 0.0)
        end = float(clip.get("end_seconds") or 0.0)
        link = _youtube_timestamp_link(payload.get("url", ""), start)
        print(
            f"{item['video_id']} | {payload.get('video_title', '')} | "
            f"{item['source_collection']} rank {clip.get('rank')} | {start:.2f}-{end:.2f}s | "
            f"score={clip.get('score')} | status={clip.get('review_status', 'pending_review')}"
        )
        if link:
            print(f"link: {link}")
        print(f"first_sentence: {_display(clip.get('first_sentence', ''), 160)}")
        print(f"text: {_display(clip.get('text', ''), 220)}")
        print(
            "review command: "
            f"python -m app.jobs.review_clip --video-id {item['video_id']} "
            f"--target {'diagnostic' if item['source_collection'] == 'diagnostic_candidates' else 'clips'} "
            f"--rank {clip.get('rank')} --status approved --rating 4 --reason \"bom\""
        )
        print("")


def _iter_clips():
    if not config.STORAGE_CLIPS_DIR.exists():
        return
    for path in sorted(config.STORAGE_CLIPS_DIR.glob("*_clips.json")):
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception as exc:
            print(f"[pending] falha ao ler {path}: {exc}")
            continue
        video_id = str(payload.get("video_id") or path.name.replace("_clips.json", ""))
        for source_collection in ("clips", "diagnostic_candidates"):
            for clip in payload.get(source_collection, []):
                clip.setdefault("review_status", "pending_review")
                yield {
                    "video_id": video_id,
                    "payload": payload,
                    "clip": clip,
                    "source_collection": source_collection,
                }


def _youtube_timestamp_link(url: str, start_seconds: float) -> str:
    if not url:
        return ""
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}t={int(start_seconds)}s"


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
