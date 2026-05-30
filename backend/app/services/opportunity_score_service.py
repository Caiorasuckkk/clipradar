from statistics import mean

from app.models import TrendTopic
from app.scanners import youtube_errors
from app.services.attention_score_service import AttentionScoreService
from app.services.content_suitability_service import ContentSuitabilityService
from app.services.noise_filter_service import NoiseFilterService


class OpportunityScoreService:
    SENSITIVE_TERMS = {
        "pt": [
            "politica",
            "política",
            "morte",
            "assassinato",
            "crime",
            "golpe",
            "guerra",
            "doenca",
            "doença",
            "remedio",
            "remédio",
            "aposta",
            "denúncia",
            "escândalo",
            "fraude",
            "investigação",
            "operação",
            "polêmica",
            "prisão",
            "processo",
        ],
        "en": [
            "allegations",
            "controversy",
            "court",
            "politics",
            "death",
            "murder",
            "crime",
            "fraud",
            "investigation",
            "lawsuit",
            "leak",
            "war",
            "disease",
            "medicine",
            "betting",
        ],
    }
    RISK_TERMS = {
        "político",
        "política",
        "politics",
        "crime",
        "fraude",
        "fraud",
        "processo",
        "prisão",
        "arrest",
        "lawsuit",
        "criminal",
        "leaked",
        "explicit",
        "violência",
        "violence",
        "escândalo",
        "scandal",
        "investigação",
        "investigation",
    }

    def __init__(
        self,
        suitability_service: ContentSuitabilityService | None = None,
        attention_service: AttentionScoreService | None = None,
        noise_filter_service: NoiseFilterService | None = None,
    ) -> None:
        self.suitability_service = suitability_service or ContentSuitabilityService()
        self.attention_service = attention_service or AttentionScoreService()
        self.noise_filter_service = noise_filter_service or NoiseFilterService()

    def score_topic(self, topic: TrendTopic) -> TrendTopic:
        topic.risk_score = self.calculate_risk_score(topic)
        topic.attention_score, topic.attention_category = self.attention_service.score_topic(topic)
        topic.risk_score = self.calculate_risk_score(topic)
        topic.suitability_score = self.suitability_service.score_topic(topic)
        topic.opportunity_score = self.calculate_opportunity_score(topic)
        topic.youtube_quota_limited = youtube_errors.QUOTA_EXHAUSTED or topic.quota_exhausted
        topic.needs_youtube_validation = topic.youtube_quota_limited and not topic.videos
        if self.noise_filter_service.is_noisy(topic):
            topic.opportunity_score = max(0.0, round(topic.opportunity_score - 3.0, 2))
        if topic.topic_base_quality_score < 4 and not topic.videos:
            topic.opportunity_score = min(topic.opportunity_score, 3.0)
        topic.decision = self.decision(topic)
        return topic

    def calculate_risk_score(self, topic: TrendTopic) -> float:
        text = self._risk_text(topic)
        hits = sum(1 for term in self.RISK_TERMS if term in text)
        risk = min(6.0, hits * 1.5)

        if topic.market == "GLOBAL" and not any(source in topic.real_sources for source in ["rss_news", "trends_rss"]):
            risk += 1.0
        if topic.attention_score > 7 and not any(source in topic.real_sources for source in ["trends_rss", "rss_news"]):
            risk += 2.0
        if any(source in topic.real_sources for source in ["trends_rss", "rss_news"]):
            risk -= 1.0
        if topic.attention_category in {"podcast_viral", "tech_controversy"} and not any(
            term in text for term in ["crime", "criminal", "fraude", "fraud", "prisão", "arrest"]
        ):
            risk -= 0.5

        return round(max(0.0, min(10.0, risk)), 2)

    def calculate_opportunity_score(self, topic: TrendTopic) -> float:
        videos_score = min(2.0, len(topic.videos) * 0.4)
        engagement_score = 0.0
        if topic.videos:
            engagement_score = min(2.0, mean(video.engagement_score for video in topic.videos) / 5)

        base_score = (
            (topic.trend_score * 0.35)
            + videos_score
            + engagement_score
            + min(2.0, topic.real_sources_count * 0.65)
            + (topic.topic_base_quality_score * 0.45)
            + (topic.suitability_score * 0.35)
            + (topic.attention_score * 0.45)
            + (topic.dynamic_query_quality_score * 0.35)
            + min(1.0, topic.clip_permission_score * 0.1)
        )

        penalty = topic.risk_score * 0.55
        if topic.suitability_score < 4:
            penalty += 3.0
        if topic.topic_base_quality_score < 4:
            penalty += 2.5
        if not topic.expansion_allowed:
            penalty += 1.5
        if topic.real_signals_count == 0:
            penalty += 3.5
        if topic.sources == ["youtube_popular"]:
            penalty += 4.0
        if self.suitability_service.is_music_only(topic):
            penalty += 3.0

        score = base_score - penalty
        return round(max(0.0, min(10.0, score)), 2)

    def decision(self, topic: TrendTopic) -> str:
        opportunity_score = topic.opportunity_score
        risk_score = topic.risk_score
        suitability_score = topic.suitability_score
        attention_score = topic.attention_score
        has_real_context = self._has_real_context(topic)

        if topic.topic_base_quality_score < 4 and not topic.videos:
            return "ignore"

        if topic.youtube_quota_limited:
            if (
                opportunity_score >= 4.0
                and topic.topic_base_quality_score >= 5
                and topic.dynamic_query_quality_score >= 5
                and attention_score >= 3.5
                and risk_score < 8
                and has_real_context
                and topic.expansion_allowed
            ):
                return "review"
            if (
                topic.topic_base_quality_score >= 8
                and attention_score >= 4.5
                and risk_score < 6
                and has_real_context
                and topic.expansion_allowed
            ):
                return "review"
            return "ignore"

        if (
            opportunity_score >= 7
            and suitability_score >= 6
            and attention_score >= 6
            and topic.dynamic_query_quality_score >= 5
            and risk_score < 6
            and not topic.needs_youtube_validation
            and not topic.youtube_quota_limited
            and not topic.needs_permission_review
        ):
            return "produce"
        if opportunity_score >= 5 and attention_score >= 5 and risk_score < 8:
            return "review"
        return "ignore"

    @staticmethod
    def _has_real_context(topic: TrendTopic) -> bool:
        return any(
            source in topic.real_sources
            for source in [
                "trends_rss",
                "rss_news",
                "watchlist",
                "youtube_high_attention",
                "youtube_popular",
            ]
        )

    @staticmethod
    def _risk_text(topic: TrendTopic) -> str:
        evidence = " ".join(topic.evidence_titles)
        keywords = " ".join(topic.original_keywords)
        videos = " ".join(video.title for video in topic.videos[:5])
        return f"{topic.keyword} {topic.normalized_keyword} {keywords} {evidence} {videos}".lower()
