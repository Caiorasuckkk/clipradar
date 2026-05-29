from statistics import mean

from app.models import TrendTopic
from app.services.content_suitability_service import ContentSuitabilityService


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
        ],
        "en": [
            "politics",
            "death",
            "murder",
            "crime",
            "war",
            "disease",
            "medicine",
            "betting",
        ],
    }

    def __init__(self, suitability_service: ContentSuitabilityService | None = None) -> None:
        self.suitability_service = suitability_service or ContentSuitabilityService()

    def score_topic(self, topic: TrendTopic) -> TrendTopic:
        topic.risk_score = self.calculate_risk_score(topic)
        topic.suitability_score = self.suitability_service.score_topic(topic)
        topic.opportunity_score = self.calculate_opportunity_score(topic)
        topic.decision = self.decision(
            topic.opportunity_score,
            topic.risk_score,
            topic.suitability_score,
        )
        return topic

    def calculate_risk_score(self, topic: TrendTopic) -> float:
        text = f"{topic.keyword} {topic.normalized_keyword}".lower()
        terms = self.SENSITIVE_TERMS["pt"] + self.SENSITIVE_TERMS["en"]
        hits = sum(1 for term in terms if term in text)
        return round(min(10.0, hits * 3.0), 2)

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
            + (topic.suitability_score * 0.35)
        )

        penalty = topic.risk_score * 0.55
        if topic.suitability_score < 4:
            penalty += 3.0
        if topic.real_signals_count == 0:
            penalty += 3.5
        if topic.sources == ["youtube_popular"]:
            penalty += 4.0
        if self.suitability_service.is_music_only(topic):
            penalty += 3.0

        score = base_score - penalty
        return round(max(0.0, min(10.0, score)), 2)

    @staticmethod
    def decision(opportunity_score: float, risk_score: float, suitability_score: float) -> str:
        if opportunity_score >= 7 and risk_score < 6 and suitability_score >= 6:
            return "produce"
        if opportunity_score >= 5 and suitability_score >= 4:
            return "review"
        return "ignore"
