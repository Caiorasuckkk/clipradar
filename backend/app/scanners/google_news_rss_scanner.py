from datetime import UTC, datetime
import xml.etree.ElementTree as ET

import requests

from app.models import TrendSignal
from app.scanners.trend_query_builder import _br_relevance_score


class GoogleNewsRSSScanner:
    BR_SUFFIXES = ["podcast", "escândalo", "investigação", "polêmica", "caso", "revelou"]
    GLOBAL_SUFFIXES = ["podcast", "scandal", "investigation", "files", "exposed", "lawsuit"]

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
        url = self._rss_url()

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            feed = ET.fromstring(response.content)
            items = feed.findall(".//item/title")
            terms = [item.text.strip() for item in items if item.text and item.text.strip()]
            if self.market == "BR":
                strong_terms = [term for term in terms if _br_relevance_score(term) >= 0.45]
                auxiliary_terms = [
                    term for term in terms if 0.25 <= _br_relevance_score(term) < 0.45
                ]
                terms = strong_terms + auxiliary_terms

            for index, query in enumerate(self._ranked_queries(terms[:6])):
                signals.append(
                    TrendSignal(
                        source="trends_rss",
                        keyword=query["query"],
                        title=query["term"],
                        url=url,
                        language=self.language,
                        market=self.market,
                        raw_score=max(35.0, 90.0 - float(index * 3)),
                        detected_at=detected_at,
                        metadata={
                            "is_mock": False,
                            "term": query["term"],
                            "suffix": query["suffix"],
                            "rss_url": url,
                        },
                    )
                )
        except Exception as exc:
            print(f"[trends_rss] Failed to scan {self.market}: {exc}")

        return signals

    def _rss_url(self) -> str:
        if self.market == "BR":
            return "https://trends.google.com/trending/rss?geo=BR&hl=pt-BR"
        return "https://trends.google.com/trending/rss?geo=US&hl=en-US"

    def _ranked_queries(self, terms: list[str]) -> list[dict[str, str]]:
        suffixes = self.BR_SUFFIXES if self.market == "BR" else self.GLOBAL_SUFFIXES
        candidates: list[dict[str, str]] = []
        for term in terms:
            for suffix in suffixes[:2]:
                candidates.append(
                    {
                        "term": term,
                        "suffix": suffix,
                        "query": f"{term} {suffix}",
                    }
                )
        return sorted(candidates, key=lambda item: len(item["query"]), reverse=True)[:6]
