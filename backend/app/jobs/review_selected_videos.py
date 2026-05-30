from __future__ import annotations

import sys
from typing import Any

from app.services.video_history_service import VideoHistoryService


def main() -> None:
    configure_output()
    history = VideoHistoryService()
    history.refresh_processing_priorities()
    data = history._read()
    videos = sorted(
        data.values(),
        key=lambda item: float(item.get("processing_priority_score") or 0.0),
        reverse=True,
    )

    print("REVIEW SELECTED VIDEOS")
    print(f"Total no histórico: {len(videos)}")
    print("")
    for index, video in enumerate(videos[:30], start=1):
        print(
            f"{index:>2}. {float(video.get('processing_priority_score') or 0):>4.1f} | "
            f"{video.get('status', ''):<15} | "
            f"{int(video.get('duration_seconds') or 0):>5}s | "
            f"{_display(video.get('channel_name') or video.get('channel_title') or '', 22):<22} | "
            f"{_display(video.get('title', ''), 58)}"
        )
        print(f"    priority: {_display(video.get('processing_priority_reason', ''), 120)}")
        if video.get("queue_reject_reason"):
            print(f"    queue_reject: {_display(video.get('queue_reject_reason', ''), 120)}")


def _display(value: object, limit: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0]
    return trimmed or text[:limit]


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
