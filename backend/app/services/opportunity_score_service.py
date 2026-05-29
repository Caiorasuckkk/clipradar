from statistics import mean

from app.models import TrendTopic


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

    def score_topic(self, topic: TrendTopic) -> TrendTopic:
        topic.risk_score = self.calculate_risk_score(topic)
        topic.opportunity_score = self.calculate_opportunity_score(topic)
        topic.decision = self.decision(topic.opportunity_score, topic.risk_score)
        return topic

    def calculate_risk_score(self, topic: TrendTopic) -> float:
        text = f"{topic.keyword} {topic.normalized_keyword}".lower()
        terms = self.SENSITIVE_TERMS["pt"] + self.SENSITIVE_TERMS["en"]
        hits = sum(1 for term in terms if term in text)
        return round(min(10.0, hits * 3.0), 2)

    def calculate_opportunity_score(self, topic: TrendTopic) -> float:
        sources_score = min(2.0, len(topic.sources) * 0.7)
        videos_score = min(2.0, len(topic.videos) * 0.4)
        engagement_score = 0.0
        if topic.videos:
            engagement_score = min(2.0, mean(video.engagement_score for video in topic.videos) / 5)

        base_score = (topic.trend_score * 0.45) + sources_score + videos_score + engagement_score
        score = base_score - (topic.risk_score * 0.55)
        return round(max(0.0, min(10.0, score)), 2)

    @staticmethod
    def decision(opportunity_score: float, risk_score: float) -> str:
        if risk_score >= 8 or opportunity_score < 5:
            return "ignore"
        if opportunity_score >= 7 and risk_score < 6:
            return "produce"
        return "review"
