from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import STORAGE_VIDEOS_DIR
from app.models import SourceVideo, TrendTopic
from app.services.processing_priority_service import ProcessingPriorityService


class VideoHistoryService:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or STORAGE_VIDEOS_DIR / "video_history.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.priority_service = ProcessingPriorityService()

    def enqueue_from_topics(self, topics: list[TrendTopic]) -> int:
        queued = 0
        for topic in topics:
            if topic.decision not in {"produce", "review"}:
                continue
            for video in topic.videos:
                if self.enqueue_video(video, topic):
                    queued += 1
        return queued

    def enqueue_video(self, video: SourceVideo, topic: TrendTopic | None = None) -> bool:
        data = self._read()
        video_id = video.video_id
        existing = data.get(video_id)
        if existing and existing.get("status") in {"queued", "processing", "done"}:
            return False

        now = self._now()
        item = {
            "video_id": video_id,
            "title": video.title,
            "channel_name": video.channel_title,
            "channel_title": video.channel_title,
            "url": video.url,
            "status": "queued",
            "topic_keyword": topic.keyword if topic else "",
            "topic_decision": topic.decision if topic else "",
            "view_count": video.view_count,
            "like_count": video.like_count,
            "comment_count": video.comment_count,
            "duration_seconds": video.duration_seconds,
            "engagement_score": video.engagement_score,
            "clip_permission_status": video.clip_permission_status,
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
            "error": "",
        }
        score, reason = self.priority_service.score_video(item)
        item["processing_priority_score"] = score
        item["processing_priority_reason"] = reason
        item["queue_reject_reason"] = existing.get("queue_reject_reason", "") if existing else ""
        data[video_id] = item
        self._write(data)
        return True

    def get_by_status(self, status: str) -> list[dict[str, Any]]:
        data = self._read()
        return [
            item
            for item in data.values()
            if item.get("status") == status
        ]

    def get_next_for_processing(self, limit: int = 1) -> list[dict[str, Any]]:
        data = self._read()
        queued: list[dict[str, Any]] = []
        changed = False
        for video_id, item in data.items():
            if item.get("status") != "queued":
                continue
            if self._to_int(item.get("duration_seconds")) < 120:
                continue
            score, reason = self.priority_service.score_video(item)
            if item.get("processing_priority_score") != score:
                item["processing_priority_score"] = score
                changed = True
            if item.get("processing_priority_reason") != reason:
                item["processing_priority_reason"] = reason
                changed = True
            data[video_id] = item
            queued.append(item)

        if changed:
            self._write(data)

        queued.sort(
            key=lambda item: (
                float(item.get("processing_priority_score") or 0.0),
                int(item.get("duration_seconds") or 0),
                int(item.get("view_count") or 0),
            ),
            reverse=True,
        )
        return queued[:limit]

    def refresh_processing_priorities(self) -> None:
        data = self._read()
        for video_id, item in data.items():
            score, reason = self.priority_service.score_video(item)
            item["processing_priority_score"] = score
            item["processing_priority_reason"] = reason
            data[video_id] = item
        self._write(data)

    def mark_processing(self, video_id: str) -> None:
        self._set_status(video_id, "processing")

    def mark_done(self, video_id: str) -> None:
        self._set_status(video_id, "done")

    def mark_processed(self, video_id: str) -> None:
        self.mark_done(video_id)

    def mark_rejected(self, video_id: str) -> None:
        self._set_status(video_id, "rejected")

    def mark_rejected_queue(self, video_id: str, reason: str) -> None:
        data = self._read()
        item = data.get(video_id, {"video_id": video_id})
        item["status"] = "rejected_queue"
        item["queue_reject_reason"] = reason
        item["updated_at"] = self._now()
        data[video_id] = item
        self._write(data)

    def mark_error(self, video_id: str, error: str) -> None:
        self._set_status(video_id, "error", error=error)

    def _set_status(self, video_id: str, status: str, error: str = "") -> None:
        data = self._read()
        item = data.get(video_id, {"video_id": video_id})
        item["status"] = status
        item["updated_at"] = self._now()
        item["error"] = error
        data[video_id] = item
        self._write(data)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.storage_path.exists():
            return {}
        try:
            with self.storage_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            print(f"[history] falha ao ler historico: {exc}")
        return {}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        with self.storage_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    @staticmethod
    def _to_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()
