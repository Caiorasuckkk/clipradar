from app.config import TOP_TOPICS_TO_PROCESS, VIDEOS_PER_TOPIC
from app.models import TrendTopic
from app.scanners import youtube_errors
from app.scanners.youtube_scanner import YouTubeScanner
from app.services.creator_rights_service import CreatorRightsService
from app.services.opportunity_score_service import OpportunityScoreService


class SourceFinderService:
    def __init__(
        self,
        youtube_scanner: YouTubeScanner | None = None,
        score_service: OpportunityScoreService | None = None,
        rights_service: CreatorRightsService | None = None,
    ) -> None:
        self.youtube_scanner = youtube_scanner or YouTubeScanner(max_results=VIDEOS_PER_TOPIC)
        self.score_service = score_service or OpportunityScoreService()
        self.rights_service = rights_service or CreatorRightsService()

    def attach_videos(
        self,
        topics: list[TrendTopic],
        limit: int = TOP_TOPICS_TO_PROCESS,
        videos_per_topic: int = VIDEOS_PER_TOPIC,
    ) -> list[TrendTopic]:
        enriched_topics: list[TrendTopic] = []
        self.youtube_scanner.max_results = min(videos_per_topic, 5)

        for index, topic in enumerate(topics):
            if index < limit:
                topic.videos = self._search_topic_videos(topic)
                topic.videos = [self.rights_service.annotate_video(video) for video in topic.videos]
                topic = self.rights_service.summarize_topic(topic)
            topic.quota_exhausted = youtube_errors.QUOTA_EXHAUSTED
            enriched_topics.append(self.score_service.score_topic(topic))

        return enriched_topics

    def _search_topic_videos(self, topic: TrendTopic):
        queries = topic.dynamic_queries[:3] if topic.dynamic_queries else [topic.keyword]
        videos = []
        seen_ids: set[str] = set()
        for query in queries:
            for video in self.youtube_scanner.search_videos(query):
                if video.video_id in seen_ids:
                    continue
                seen_ids.add(video.video_id)
                videos.append(video)
                if len(videos) >= self.youtube_scanner.max_results:
                    return videos
        return videos
