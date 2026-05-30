from __future__ import annotations

import sys
from typing import Any

from app.services.processing_priority_service import ProcessingPriorityService
from app.services.video_history_service import VideoHistoryService


def main() -> None:
    configure_output()
    history = VideoHistoryService()
    priority = ProcessingPriorityService()
    data = history._read()

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for video_id, item in data.items():
        if item.get("status") != "queued":
            continue

        score, reason = priority.score_video(item)
        item["processing_priority_score"] = score
        item["processing_priority_reason"] = reason

        should_reject, reject_reason = priority.should_reject_queue(item)
        if should_reject:
            item["status"] = "rejected_queue"
            item["queue_reject_reason"] = reject_reason
            rejected.append(item)
        else:
            item["queue_reject_reason"] = ""
            kept.append(item)
        data[video_id] = item

    history._write(data)
    kept.sort(key=lambda item: float(item.get("processing_priority_score") or 0), reverse=True)
    rejected.sort(key=lambda item: float(item.get("processing_priority_score") or 0), reverse=True)

    print("CLEANUP QUEUE — RESULTADO")
    print(f"Mantidos em queued: {len(kept)}")
    print(f"Rejeitados: {len(rejected)}")
    print("")
    print("Top 10 mantidos por processing_priority_score:")
    print_video_table(kept[:10], show_reject=False)
    print("")
    print("Top 10 rejeitados com motivo:")
    print_video_table(rejected[:10], show_reject=True)


def print_video_table(videos: list[dict[str, Any]], show_reject: bool) -> None:
    if not videos:
        print("(nenhum)")
        return
    for index, video in enumerate(videos, start=1):
        score = float(video.get("processing_priority_score") or 0.0)
        duration = int(video.get("duration_seconds") or 0)
        channel = _display(video.get("channel_name") or video.get("channel_title") or "", 22)
        title = _display(video.get("title", ""), 58)
        suffix = video.get("queue_reject_reason") if show_reject else video.get("processing_priority_reason")
        print(f"{index:>2}. {score:>4.1f} | {duration:>5}s | {channel:<22} | {title} | {_display(suffix, 70)}")


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
