from app.models import TrendTopic
from app.scanners.youtube_scanner import YouTubeScanner
from app.services.opportunity_score_service import OpportunityScoreService


class SourceFinderService:
    def __init__(
        self,
        youtube_scanner: YouTubeScanner | None = None,
        score_service: OpportunityScoreService | None = None,
    ) -> None:
        self.youtube_scanner = youtube_scanner or YouTubeScanner()
        self.score_service = score_service or OpportunityScoreService()

    def attach_videos(self, topics: list[TrendTopic], limit: int = 10) -> list[TrendTopic]:
        enriched_topics: list[TrendTopic] = []

        for index, topic in enumerate(topics):
            if index < limit:
                topic.videos = self.youtube_scanner.search_videos(topic.keyword)
            enriched_topics.append(self.score_service.score_topic(topic))

        return enriched_topics
