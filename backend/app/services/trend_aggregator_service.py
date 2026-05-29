import re
import string
from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean

from app.models import TrendSignal, TrendTopic
from app.services.opportunity_score_service import OpportunityScoreService


class TrendAggregatorService:
    def __init__(self, score_service: OpportunityScoreService | None = None) -> None:
        self.score_service = score_service or OpportunityScoreService()

    def aggregate(self, signals: list[TrendSignal]) -> list[TrendTopic]:
        grouped: dict[str, list[TrendSignal]] = defaultdict(list)
        for signal in signals:
            normalized = self.normalize_keyword(signal.keyword)
            if normalized:
                grouped[normalized].append(signal)

        topics = [self._build_topic(normalized, group) for normalized, group in grouped.items()]
        topics = [self.score_service.score_topic(topic) for topic in topics]
        return sorted(topics, key=lambda topic: topic.trend_score, reverse=True)

    @staticmethod
    def normalize_keyword(keyword: str) -> str:
        translator = str.maketrans("", "", string.punctuation + "“”‘’")
        cleaned = keyword.lower().translate(translator)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _build_topic(self, normalized_keyword: str, signals: list[TrendSignal]) -> TrendTopic:
        sources = sorted({signal.source for signal in signals})
        markets = [signal.market for signal in signals if signal.market]
        languages = [signal.language for signal in signals if signal.language]
        avg_raw_score = mean(signal.raw_score for signal in signals)
        trend_score = self._trend_score(
            signals_count=len(signals),
            sources_count=len(sources),
            avg_raw_score=avg_raw_score,
        )

        return TrendTopic(
            keyword=self._best_keyword(signals),
            normalized_keyword=normalized_keyword,
            language=self._most_common(languages, default="unknown"),
            market=self._most_common(markets, default="unknown"),
            sources=sources,
            signals_count=len(signals),
            trend_score=trend_score,
            opportunity_score=0.0,
            risk_score=0.0,
            videos=[],
            decision="ignore",
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _trend_score(signals_count: int, sources_count: int, avg_raw_score: float) -> float:
        score = (signals_count * 1.2) + (sources_count * 1.5) + (avg_raw_score / 20.0)
        return round(min(10.0, score), 2)

    @staticmethod
    def _best_keyword(signals: list[TrendSignal]) -> str:
        return max((signal.keyword for signal in signals), key=len)

    @staticmethod
    def _most_common(values: list[str], default: str) -> str:
        if not values:
            return default
        return max(set(values), key=values.count)
