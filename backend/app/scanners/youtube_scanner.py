from datetime import UTC, datetime
from math import log10

import isodate
from googleapiclient.discovery import build

from app.config import YOUTUBE_API_KEYS_LIST
from app.models import SourceVideo
from app.scanners import youtube_errors
from app.scanners.youtube_errors import (
    is_quota_error,
    KeyRotationManager,
    mark_quota_exhausted,
    record_rotation_event,
    sanitize_youtube_error,
)


class YouTubeScanner:
    # TODO: avaliar fallback via SerpAPI/SearchAPI quando YouTube quota esgotar.
    # Verificar limite gratuito atual antes de implementar.
    # SERPAPI_KEY= no .env
    # Não implementar agora.
    def __init__(self, api_key: str | None = None, max_results: int = 5) -> None:
        keys = [api_key] if api_key else YOUTUBE_API_KEYS_LIST
        self.key_manager = KeyRotationManager([key for key in keys if key])
        self.max_results = max_results
        self.quota_exhausted = False

    def search_videos(self, keyword: str) -> list[SourceVideo]:
        if self.quota_exhausted or youtube_errors.QUOTA_EXHAUSTED:
            return []
        if not self.key_manager.current_key():
            print("[youtube] YOUTUBE_API_KEY is missing. Skipping YouTube validation.")
            return []

        while self.key_manager.current_key():
            try:
                youtube = build(
                    "youtube",
                    "v3",
                    developerKey=self.key_manager.current_key(),
                )
                video_ids = self._search_video_ids(youtube, keyword)
                if not video_ids:
                    return []
                return self._fetch_video_details(youtube, video_ids)
            except Exception as exc:
                if is_quota_error(exc):
                    if self._rotate_key():
                        continue
                    self.quota_exhausted = True
                    mark_quota_exhausted()
                    print("[youtube] YouTube quota exhausted. Skipping remaining video validation.")
                else:
                    print(
                        f"[youtube] Failed to search videos for '{keyword}': "
                        f"{sanitize_youtube_error(exc)}"
                    )
                return []
        return []

    def _rotate_key(self) -> bool:
        current = self.key_manager.current_index
        total = self.key_manager.total
        if self.key_manager.rotate():
            message = f"quota esgotada (key {current}/{total}); rotacionou para key {self.key_manager.current_index}"
            record_rotation_event(message, True)
            print(f"[youtube] {message}")
            return True

        message = f"quota esgotada (key {current}/{total}); todas as keys esgotadas"
        record_rotation_event(message, False)
        return False

    def _search_video_ids(self, youtube: object, keyword: str) -> list[str]:
        response = (
            youtube.search()
            .list(
                part="id",
                q=keyword,
                type="video",
                maxResults=self.max_results,
                order="relevance",
                safeSearch="moderate",
            )
            .execute()
        )
        return [
            item["id"]["videoId"]
            for item in response.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

    def _fetch_video_details(self, youtube: object, video_ids: list[str]) -> list[SourceVideo]:
        response = (
            youtube.videos()
            .list(
                part="snippet,statistics,contentDetails,status",
                id=",".join(video_ids),
            )
            .execute()
        )

        videos: list[SourceVideo] = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            details = item.get("contentDetails", {})
            status = item.get("status", {})
            video_id = item.get("id", "")
            published_at = self._parse_datetime(snippet.get("publishedAt"))
            view_count = self._to_int(statistics.get("viewCount"))
            like_count = self._to_int(statistics.get("likeCount"))
            comment_count = self._to_int(statistics.get("commentCount"))

            videos.append(
                SourceVideo(
                    video_id=video_id,
                    title=snippet.get("title", ""),
                    channel_title=snippet.get("channelTitle", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    published_at=published_at,
                    view_count=view_count,
                    like_count=like_count,
                    comment_count=comment_count,
                    duration_seconds=self._duration_seconds(details.get("duration")),
                    engagement_score=self._engagement_score(
                        view_count=view_count,
                        like_count=like_count,
                        comment_count=comment_count,
                        published_at=published_at,
                    ),
                    license=status.get("license"),
                )
            )

        return videos

    @staticmethod
    def _to_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _duration_seconds(value: str | None) -> int:
        if not value:
            return 0
        try:
            return int(isodate.parse_duration(value).total_seconds())
        except Exception:
            return 0

    @staticmethod
    def _engagement_score(
        view_count: int,
        like_count: int,
        comment_count: int,
        published_at: datetime | None,
    ) -> float:
        if view_count <= 0:
            return 0.0

        interaction_rate = (like_count + (comment_count * 2)) / view_count
        volume_score = min(4.0, log10(view_count + 1) / 2)
        engagement_score = min(4.0, interaction_rate * 120)

        recency_score = 1.0
        if published_at:
            age_days = max(0, (datetime.now(UTC) - published_at).days)
            if age_days <= 7:
                recency_score = 2.0
            elif age_days <= 30:
                recency_score = 1.5

        return round(min(10.0, volume_score + engagement_score + recency_score), 2)
