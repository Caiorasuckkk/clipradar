from datetime import UTC, datetime

from googleapiclient.discovery import build

from app.config import YOUTUBE_API_KEY
from app.models import TrendSignal
from app.scanners.keyword_extraction import extract_keyword


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
        self.api_key = api_key if api_key is not None else YOUTUBE_API_KEY
        self.max_results = max_results

    def scan(self) -> list[TrendSignal]:
        if not self.api_key:
            print("[youtube_popular] YOUTUBE_API_KEY is missing. Skipping popular videos.")
            return []

        try:
            youtube = build("youtube", "v3", developerKey=self.api_key)
            response = (
                youtube.videos()
                .list(
                    part="snippet,statistics",
                    chart="mostPopular",
                    regionCode=self._region_code(),
                    maxResults=self.max_results,
                )
                .execute()
            )
        except Exception as exc:
            print(f"[youtube_popular] Failed to fetch popular videos for {self.market}: {exc}")
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

    @staticmethod
    def _to_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
