from datetime import datetime

from pydantic import BaseModel


class SourceVideo(BaseModel):
    video_id: str
    title: str
    channel_title: str
    url: str
    published_at: datetime | None
    view_count: int
    like_count: int
    comment_count: int
    duration_seconds: int
    engagement_score: float
