from datetime import datetime

from pydantic import BaseModel, Field

from app.models.source_video import SourceVideo


class TrendTopic(BaseModel):
    keyword: str
    normalized_keyword: str
    language: str
    market: str
    sources: list[str]
    real_sources: list[str] = Field(default_factory=list)
    mock_sources: list[str] = Field(default_factory=list)
    real_sources_count: int = 0
    mock_sources_count: int = 0
    signals_count: int
    mock_signals_count: int = 0
    real_signals_count: int = 0
    trend_score: float
    opportunity_score: float
    risk_score: float
    suitability_score: float = 0.0
    videos: list[SourceVideo]
    decision: str
    created_at: datetime
