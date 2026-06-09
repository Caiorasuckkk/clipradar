from __future__ import annotations

from fastapi import APIRouter

from app.services.cuts_analytics_service import build_cuts_analytics


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/cuts/summary")
def get_cuts_analytics_summary() -> dict[str, object]:
    return build_cuts_analytics()
