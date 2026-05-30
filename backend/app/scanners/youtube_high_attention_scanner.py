from datetime import UTC, datetime, timedelta

from googleapiclient.discovery import build

from app.config import HIGH_ATTENTION_QUERIES_PER_MARKET, YOUTUBE_API_KEYS_LIST
from app.models import TrendSignal
from app.scanners import youtube_errors
from app.scanners.keyword_extraction import extract_keyword
from app.scanners.trend_query_builder import TrendQueryBuilder
from app.scanners.youtube_errors import (
    is_quota_error,
    KeyRotationManager,
    mark_quota_exhausted,
    record_rotation_event,
    sanitize_youtube_error,
)


class YouTubeHighAttentionScanner:
    def __init__(
        self,
        market: str,
        language: str,
        api_key: str | None = None,
        queries_per_market: int = HIGH_ATTENTION_QUERIES_PER_MARKET,
        max_results_per_query: int = 3,
    ) -> None:
        self.market = market.upper()
        self.language = language
        keys = [api_key] if api_key else YOUTUBE_API_KEYS_LIST
        self.key_manager = KeyRotationManager([key for key in keys if key])
        self.queries_per_market = queries_per_market
        self.max_results_per_query = max_results_per_query

    def scan(self) -> list[TrendSignal]:
        queries = self._queries()
        if youtube_errors.QUOTA_EXHAUSTED:
            print("[youtube_high_attention] YouTube quota already exhausted. Skipping scanner.")
            return self._queries_to_degraded_signals(queries, "quota_exhausted")
        if not self.key_manager.current_key():
            print("[youtube_high_attention] YOUTUBE_API_KEY is missing. Skipping scanner.")
            return self._queries_to_degraded_signals(queries, "missing_api_key")

        signals: list[TrendSignal] = []
        detected_at = datetime.now(UTC)
        for query in queries:
            while self.key_manager.current_key():
                try:
                    youtube = build(
                        "youtube",
                        "v3",
                        developerKey=self.key_manager.current_key(),
                    )
                    video_ids = self._search_video_ids(youtube, query)
                    if video_ids:
                        signals.extend(
                            self._videos_to_signals(youtube, video_ids, query, detected_at)
                        )
                    break
                except Exception as exc:
                    if is_quota_error(exc):
                        if self._rotate_key():
                            continue
                        mark_quota_exhausted()
                        print(
                            "[youtube_high_attention] YouTube quota exhausted. "
                            "Stopping high-attention queries."
                        )
                        signals.extend(
                            self._queries_to_degraded_signals(
                                queries,
                                "quota_exhausted",
                                existing=len(signals),
                            )
                        )
                        return signals
                    print(
                        f"[youtube_high_attention] Failed query '{query}': "
                        f"{sanitize_youtube_error(exc)}"
                    )
                    break

        return signals

    def _queries_to_degraded_signals(
        self,
        queries: list[str],
        reason: str,
        existing: int = 0,
    ) -> list[TrendSignal]:
        detected_at = datetime.now(UTC)
        signals: list[TrendSignal] = []
        for index, query in enumerate(queries):
            signals.append(
                TrendSignal(
                    source="watchlist",
                    keyword=query,
                    title=query,
                    url=None,
                    language=self.language,
                    market=self.market,
                    raw_score=max(45.0, 75.0 - float((index + existing) * 2)),
                    detected_at=detected_at,
                    metadata={
                        "is_mock": False,
                        "is_high_attention": True,
                        "needs_youtube_validation": True,
                        "youtube_quota_limited": reason == "quota_exhausted",
                        "query": query,
                        "reason": reason,
                    },
                )
            )
        return signals

    def _queries(self) -> list[str]:
        return TrendQueryBuilder(
            market=self.market,
            max_queries=self.queries_per_market,
        ).build_queries()

    def _search_video_ids(self, youtube: object, query: str) -> list[str]:
        published_after = (datetime.now(UTC) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
        response = (
            youtube.search()
            .list(
                part="id",
                q=query,
                type="video",
                maxResults=self.max_results_per_query,
                order="date",
                safeSearch="moderate",
                publishedAfter=published_after,
                relevanceLanguage="pt" if self.market == "BR" else "en",
                regionCode="BR" if self.market == "BR" else "US",
            )
            .execute()
        )
        return [
            item["id"]["videoId"]
            for item in response.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

    def _videos_to_signals(
        self,
        youtube: object,
        video_ids: list[str],
        query: str,
        detected_at: datetime,
    ) -> list[TrendSignal]:
        response = (
            youtube.videos()
            .list(part="snippet,statistics,status", id=",".join(video_ids))
            .execute()
        )

        signals: list[TrendSignal] = []
        for index, item in enumerate(response.get("items", [])):
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            video_id = item.get("id", "")
            title = snippet.get("title", "").strip()
            if not title or not video_id:
                continue

            view_count = self._to_int(statistics.get("viewCount"))
            like_count = self._to_int(statistics.get("likeCount"))
            comment_count = self._to_int(statistics.get("commentCount"))
            url = f"https://www.youtube.com/watch?v={video_id}"
            signals.append(
                TrendSignal(
                    source="youtube_high_attention",
                    keyword=extract_keyword(title),
                    title=title,
                    url=url,
                    language=self.language,
                    market=self.market,
                    raw_score=self._raw_score(index, view_count, comment_count),
                    detected_at=detected_at,
                    metadata={
                        "is_mock": False,
                        "is_high_attention": True,
                        "query": query,
                        "video_title": title,
                        "channel_title": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt"),
                        "view_count": view_count,
                        "like_count": like_count,
                        "comment_count": comment_count,
                        "url": url,
                    },
                )
            )
        return signals

    @staticmethod
    def _raw_score(index: int, view_count: int, comment_count: int) -> float:
        rank_score = max(35.0, 85.0 - float(index * 5))
        attention_bonus = min(15.0, (view_count / 250_000) + (comment_count / 200))
        return round(min(100.0, rank_score + attention_bonus), 2)

    def _rotate_key(self) -> bool:
        current = self.key_manager.current_index
        total = self.key_manager.total
        if self.key_manager.rotate():
            message = f"quota esgotada (key {current}/{total}); rotacionou para key {self.key_manager.current_index}"
            record_rotation_event(message, True)
            print(f"[youtube_high_attention] {message}")
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
