import re
import string
from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean

from app.models import TrendSignal, TrendTopic
from app.scanners.keyword_extraction import extract_keyword
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
        real_sources = sorted(
            {signal.source for signal in signals if not self._is_mock_signal(signal)}
        )
        mock_sources = sorted({signal.source for signal in signals if self._is_mock_signal(signal)})
        real_signals_count = sum(1 for signal in signals if not self._is_mock_signal(signal))
        mock_signals_count = len(signals) - real_signals_count
        markets = [signal.market for signal in signals if signal.market]
        languages = [signal.language for signal in signals if signal.language]
        avg_raw_score = mean(signal.raw_score for signal in signals)
        trend_score = self._trend_score(
            signals_count=len(signals),
            real_signals_count=real_signals_count,
            real_sources_count=len(real_sources),
            avg_raw_score=avg_raw_score,
            is_mock_only=real_signals_count == 0,
        )

        return TrendTopic(
            keyword=self._best_keyword(signals),
            normalized_keyword=normalized_keyword,
            language=self._most_common(languages, default="unknown"),
            market=self._most_common(markets, default="unknown"),
            sources=sources,
            real_sources=real_sources,
            mock_sources=mock_sources,
            real_sources_count=len(real_sources),
            mock_sources_count=len(mock_sources),
            signals_count=len(signals),
            mock_signals_count=mock_signals_count,
            real_signals_count=real_signals_count,
            trend_score=trend_score,
            opportunity_score=0.0,
            risk_score=0.0,
            videos=[],
            decision="ignore",
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _trend_score(
        signals_count: int,
        real_signals_count: int,
        real_sources_count: int,
        avg_raw_score: float,
        is_mock_only: bool,
    ) -> float:
        score = (
            (signals_count * 0.7)
            + (real_signals_count * 1.2)
            + (real_sources_count * 1.7)
            + (avg_raw_score / 20.0)
        )
        if is_mock_only:
            score *= 0.35
        return round(min(10.0, score), 2)

    @staticmethod
    def _best_keyword(signals: list[TrendSignal]) -> str:
        candidates = []
        for signal in signals:
            keyword = extract_keyword(signal.keyword)
            words = keyword.split()
            if not keyword or len(keyword.replace(" ", "")) < 3:
                continue
            readability = 0
            if 2 <= len(words) <= 6:
                readability += 3
            if not bool(signal.metadata.get("is_mock", False)):
                readability += 2
            readability -= max(0, len(words) - 6)
            candidates.append((readability, len(keyword), keyword))

        if not candidates:
            return max((signal.keyword for signal in signals), key=len)
        return sorted(candidates, reverse=True)[0][2]

    @staticmethod
    def _most_common(values: list[str], default: str) -> str:
        if not values:
            return default
        return max(set(values), key=values.count)

    @staticmethod
    def _is_mock_signal(signal: TrendSignal) -> bool:
        return bool(signal.metadata.get("is_mock", False))
