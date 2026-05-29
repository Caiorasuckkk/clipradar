from datetime import UTC, datetime
from urllib.parse import quote_plus

import feedparser

from app.models import TrendSignal
from app.scanners.keyword_extraction import extract_keyword


class GoogleNewsRSSScanner:
    BR_QUERIES = [
        "Brasil",
        "tecnologia",
        "inteligência artificial",
        "futebol",
        "economia",
        "entretenimento",
        "viral",
    ]

    GLOBAL_QUERIES = [
        "technology",
        "artificial intelligence",
        "business",
        "creator economy",
        "viral",
        "entertainment",
        "global news",
    ]

    def __init__(
        self,
        market: str,
        language: str,
        max_items_per_query: int = 8,
    ) -> None:
        self.market = market.upper()
        self.language = language
        self.max_items_per_query = max_items_per_query

    def scan(self) -> list[TrendSignal]:
        signals: list[TrendSignal] = []
        detected_at = datetime.now(UTC)

        for query in self._queries():
            url = self._rss_url(query)
            try:
                feed = feedparser.parse(url)
                if getattr(feed, "bozo", False):
                    print(f"[google_news] Warning while parsing {query}: {feed.bozo_exception}")

                entries = getattr(feed, "entries", [])[: self.max_items_per_query]
                for index, entry in enumerate(entries):
                    title = self._entry_value(entry, "title")
                    if not title:
                        continue

                    signals.append(
                        TrendSignal(
                            source="google_news",
                            keyword=extract_keyword(title),
                            title=title,
                            url=self._entry_value(entry, "link"),
                            language=self.language,
                            market=self.market,
                            raw_score=max(20.0, 85.0 - float(index * 3)),
                            detected_at=detected_at,
                            metadata={
                                "is_mock": False,
                                "query": query,
                                "rss_url": url,
                            },
                        )
                    )
            except Exception as exc:
                print(f"[google_news] Failed to scan query '{query}': {exc}")

        return signals

    def _queries(self) -> list[str]:
        return self.BR_QUERIES if self.market == "BR" else self.GLOBAL_QUERIES

    def _rss_url(self, query: str) -> str:
        if self.market == "BR":
            return (
                "https://news.google.com/rss/search?"
                f"q={quote_plus(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
            )
        return (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )

    @staticmethod
    def _entry_value(entry: object, key: str) -> str | None:
        value = getattr(entry, key, None)
        return str(value).strip() if value else None
