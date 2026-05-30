import re
import string
from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean

from app.models import TrendSignal, TrendTopic
from app.scanners import youtube_errors
from app.scanners.keyword_extraction import extract_keyword
from app.services.opportunity_score_service import OpportunityScoreService
from app.services.topic_base_quality_service import TopicBaseQualityService
from app.services.trend_entity_extractor import TrendEntityExtractor


GENERIC_KEYWORD_WORDS = {
    "art",
    "brasil",
    "business",
    "global",
    "made",
    "news",
    "novo",
    "nova",
    "technology",
    "tecnologia",
    "viral",
}

PREFERRED_EVIDENCE_SOURCES = {"trends_rss", "rss_news"}


class TrendAggregatorService:
    def __init__(
        self,
        score_service: OpportunityScoreService | None = None,
        entity_extractor: TrendEntityExtractor | None = None,
        base_quality_service: TopicBaseQualityService | None = None,
    ) -> None:
        self.score_service = score_service or OpportunityScoreService()
        self.entity_extractor = entity_extractor or TrendEntityExtractor()
        self.base_quality_service = base_quality_service or TopicBaseQualityService()

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

        keyword = self._best_keyword(signals)
        evidence_titles = self._evidence_titles(signals)
        evidence_urls = self._evidence_urls(signals)
        evidence_sources = self._evidence_sources(signals)
        original_keywords = self._original_keywords(signals)
        extracted_entities = self.entity_extractor.extract(
            [keyword, *original_keywords, *evidence_titles]
        )
        draft_topic = TrendTopic(
            keyword=keyword,
            normalized_keyword=normalized_keyword,
            language=self._most_common(languages, default="unknown"),
            market=self._most_common(markets, default="unknown"),
            sources=sources,
            real_sources=real_sources,
            mock_sources=mock_sources,
            real_sources_count=len(real_sources),
            mock_sources_count=len(mock_sources),
            evidence_titles=evidence_titles,
            evidence_urls=evidence_urls,
            evidence_sources=evidence_sources,
            original_keywords=original_keywords,
            extracted_entities=extracted_entities,
            topic_origin=self._topic_origin(signals),
            signals_count=len(signals),
            mock_signals_count=mock_signals_count,
            real_signals_count=real_signals_count,
            trend_score=trend_score,
            opportunity_score=0.0,
            risk_score=0.0,
            quota_exhausted=youtube_errors.QUOTA_EXHAUSTED,
            videos=[],
            decision="ignore",
            created_at=datetime.now(UTC),
        )
        base_score, expansion_allowed, block_reason = self.base_quality_service.score_topic(
            draft_topic
        )
        draft_topic.topic_base_quality_score = base_score
        draft_topic.expansion_allowed = expansion_allowed
        draft_topic.expansion_block_reason = block_reason

        return draft_topic

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

    def _best_keyword(self, signals: list[TrendSignal]) -> str:
        candidates = []
        for signal in signals:
            keyword = extract_keyword(signal.keyword)
            words = keyword.split()
            if not keyword or len(keyword.replace(" ", "")) < 3:
                continue
            readability = self._keyword_readability(keyword)
            if 2 <= len(words) <= 6:
                readability += 3
            if not bool(signal.metadata.get("is_mock", False)):
                readability += 2
            if signal.source in PREFERRED_EVIDENCE_SOURCES:
                readability += 2
            if signal.title and keyword.lower() in signal.title.lower():
                readability += 2
            readability -= max(0, len(words) - 6)
            candidates.append((readability, len(keyword), keyword))

        if not candidates:
            return max((signal.keyword for signal in signals), key=len)
        return sorted(candidates, reverse=True)[0][2]

    @staticmethod
    def _keyword_readability(keyword: str) -> int:
        words = keyword.split()
        score = 0
        if all(len(word) >= 3 for word in words):
            score += 2
        if not any(word in GENERIC_KEYWORD_WORDS for word in words):
            score += 2
        if len(set(words)) == len(words):
            score += 1
        if any(word in GENERIC_KEYWORD_WORDS for word in words[-1:]):
            score -= 3
        if len(words) < 2 or len(words) > 6:
            score -= 4
        return score

    @staticmethod
    def _evidence_titles(signals: list[TrendSignal]) -> list[str]:
        return TrendAggregatorService._unique_limited(
            [signal.title for signal in signals if signal.title],
            limit=5,
        )

    @staticmethod
    def _evidence_urls(signals: list[TrendSignal]) -> list[str]:
        return TrendAggregatorService._unique_limited(
            [signal.url for signal in signals if signal.url],
            limit=5,
        )

    @staticmethod
    def _evidence_sources(signals: list[TrendSignal]) -> list[str]:
        sources: list[str] = []
        for signal in signals:
            if signal.title or signal.url:
                sources.append(signal.source)
        return sources[:5]

    @staticmethod
    def _original_keywords(signals: list[TrendSignal]) -> list[str]:
        return TrendAggregatorService._unique_limited(
            [signal.keyword for signal in signals if signal.keyword],
            limit=10,
        )

    @staticmethod
    def _unique_limited(values: list[str | None], limit: int) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if not value:
                continue
            cleaned = str(value).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def _most_common(values: list[str], default: str) -> str:
        if not values:
            return default
        return max(set(values), key=values.count)

    @staticmethod
    def _is_mock_signal(signal: TrendSignal) -> bool:
        return bool(signal.metadata.get("is_mock", False))

    @staticmethod
    def _topic_origin(signals: list[TrendSignal]) -> str:
        sources = {signal.source for signal in signals}
        if "watchlist" in sources:
            return "dynamic_query_degraded"
        if "trends_rss" in sources:
            return "dynamic_trend"
        if "youtube_popular" in sources:
            return "youtube_trend"
        if "rss_news" in sources:
            return "news_signal"
        return "dynamic_trend"
