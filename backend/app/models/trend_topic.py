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
    evidence_titles: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)
    original_keywords: list[str] = Field(default_factory=list)
    extracted_entities: list[str] = Field(default_factory=list)
    dynamic_queries: list[str] = Field(default_factory=list)
    dynamic_query_quality_score: float = 0.0
    topic_origin: str = "dynamic_trend"
    topic_base_quality_score: float = 0.0
    expansion_allowed: bool = False
    expansion_block_reason: str = ""
    signals_count: int
    mock_signals_count: int = 0
    real_signals_count: int = 0
    trend_score: float
    opportunity_score: float
    risk_score: float
    suitability_score: float = 0.0
    attention_score: float = 0.0
    attention_category: str = "unknown"
    quota_exhausted: bool = False
    needs_youtube_validation: bool = False
    youtube_quota_limited: bool = False
    clip_permission_score: float = 0.0
    clip_permission_status: str = "unknown"
    needs_permission_review: bool = True
    videos: list[SourceVideo]
    decision: str
    created_at: datetime
