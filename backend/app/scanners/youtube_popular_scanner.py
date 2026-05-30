from datetime import UTC, datetime

from googleapiclient.discovery import build

from app.config import YOUTUBE_API_KEYS_LIST
from app.models import TrendSignal
from app.scanners import youtube_errors
from app.scanners.keyword_extraction import extract_keyword
from app.scanners.youtube_errors import (
    is_quota_error,
    KeyRotationManager,
    mark_quota_exhausted,
    record_rotation_event,
    sanitize_youtube_error,
)


class YouTubePopularScanner:
    def __init__(
        self,
        market: str,
        language: str,
        api_key: str | None = None,
        max_results: int = 25,
    ) -> None:
        self.market = market.upper()
        self.language = language
        keys = [api_key] if api_key else YOUTUBE_API_KEYS_LIST
        self.key_manager = KeyRotationManager([key for key in keys if key])
        self.max_results = max_results

    def scan(self) -> list[TrendSignal]:
        if youtube_errors.QUOTA_EXHAUSTED:
            print("[youtube_popular] YouTube quota already exhausted. Skipping popular videos.")
            return []
        if not self.key_manager.current_key():
            print("[youtube_popular] YOUTUBE_API_KEY is missing. Skipping popular videos.")
            return []

        while self.key_manager.current_key():
            try:
                youtube = build(
                    "youtube",
                    "v3",
                    developerKey=self.key_manager.current_key(),
                )
                response = (
                    youtube.videos()
                    .list(
                        part="snippet,statistics,status",
                        chart="mostPopular",
                        regionCode=self._region_code(),
                        maxResults=self.max_results,
                    )
                    .execute()
                )
                break
            except Exception as exc:
                if is_quota_error(exc):
                    if self._rotate_key():
                        continue
                    mark_quota_exhausted()
                    print(f"[youtube_popular] YouTube quota exhausted for {self.market}.")
                else:
                    print(
                        f"[youtube_popular] Failed to fetch popular videos for {self.market}: "
                        f"{sanitize_youtube_error(exc)}"
                    )
                return []

        detected_at = datetime.now(UTC)
        signals: list[TrendSignal] = []
        for index, item in enumerate(response.get("items", [])):
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            title = snippet.get("title", "").strip()
            video_id = item.get("id", "")
            if not title or not video_id:
                continue

            signals.append(
                TrendSignal(
                    source="youtube_popular",
                    keyword=extract_keyword(title),
                    title=title,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    language=self.language,
                    market=self.market,
                    raw_score=self._raw_score(index, statistics),
                    detected_at=detected_at,
                    metadata={
                        "is_mock": False,
                        "video_id": video_id,
                        "channel_title": snippet.get("channelTitle", ""),
                        "view_count": self._to_int(statistics.get("viewCount")),
                        "like_count": self._to_int(statistics.get("likeCount")),
                        "comment_count": self._to_int(statistics.get("commentCount")),
                    },
                )
            )

        return signals

    def _region_code(self) -> str:
        return "BR" if self.market == "BR" else "US"

    def _raw_score(self, index: int, statistics: dict) -> float:
        views = self._to_int(statistics.get("viewCount"))
        rank_score = max(20.0, 90.0 - float(index * 2))
        view_bonus = min(10.0, views / 500_000)
        return round(min(100.0, rank_score + view_bonus), 2)

    def _rotate_key(self) -> bool:
        current = self.key_manager.current_index
        total = self.key_manager.total
        if self.key_manager.rotate():
            message = f"quota esgotada (key {current}/{total}); rotacionou para key {self.key_manager.current_index}"
            record_rotation_event(message, True)
            print(f"[youtube_popular] {message}")
            return True

        message = f"quota esgotada (key {current}/{total}); todas as keys esgotadas"
        record_rotation_event(message, False)
        return False

    @staticmethod
    def _to_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
