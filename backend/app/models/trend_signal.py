from datetime import datetime

from pydantic import BaseModel


class TrendSignal(BaseModel):
    source: str
    keyword: str
    title: str | None
    url: str | None
    language: str
    market: str
    raw_score: float
    detected_at: datetime
    metadata: dict
