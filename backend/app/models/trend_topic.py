from datetime import datetime

from pydantic import BaseModel

from app.models.source_video import SourceVideo


class TrendTopic(BaseModel):
    keyword: str
    normalized_keyword: str
    language: str
    market: str
    sources: list[str]
    signals_count: int
    trend_score: float
    opportunity_score: float
    risk_score: float
    videos: list[SourceVideo]
    decision: str
    created_at: datetime
