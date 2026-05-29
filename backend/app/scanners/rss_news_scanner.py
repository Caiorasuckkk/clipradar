from calendar import timegm
from datetime import UTC, datetime

import feedparser

from app.models import TrendSignal
from app.scanners.keyword_extraction import extract_keyword


class RSSNewsScanner:
    def __init__(
        self,
        feeds: list[str],
        market: str,
        language: str,
        max_items_per_feed: int = 20,
    ) -> None:
        self.feeds = feeds
        self.market = market
        self.language = language
        self.max_items_per_feed = max_items_per_feed

    def scan(self) -> list[TrendSignal]:
        signals: list[TrendSignal] = []
        detected_at = datetime.now(UTC)

        for feed_url in self.feeds:
            try:
                feed = feedparser.parse(feed_url)
                if getattr(feed, "bozo", False):
                    print(f"[rss] Warning while parsing {feed_url}: {feed.bozo_exception}")

                entries = getattr(feed, "entries", [])[: self.max_items_per_feed]
                for index, entry in enumerate(entries):
                    title = self._entry_value(entry, "title")
                    if not title:
                        continue

                    signals.append(
                        TrendSignal(
                            source="rss_news",
                            keyword=self._keyword_from_title(title),
                            title=title,
                            url=self._entry_value(entry, "link"),
                            language=self.language,
                            market=self.market,
                            raw_score=max(10.0, 60.0 - float(index * 2)),
                            detected_at=detected_at,
                            metadata={
                                "is_mock": False,
                                "feed_url": feed_url,
                                "published_at": self._entry_datetime(entry),
                            },
                        )
                    )
            except Exception as exc:
                print(f"[rss] Failed to scan {feed_url}: {exc}")

        return signals

    @staticmethod
    def _entry_value(entry: object, key: str) -> str | None:
        value = getattr(entry, key, None)
        return str(value).strip() if value else None

    @staticmethod
    def _entry_datetime(entry: object) -> str | None:
        published = getattr(entry, "published_parsed", None) or getattr(
            entry, "updated_parsed", None
        )
        if not published:
            return None
        return datetime.fromtimestamp(timegm(published), UTC).isoformat()

    @staticmethod
    def _keyword_from_title(title: str) -> str:
        return extract_keyword(title)
