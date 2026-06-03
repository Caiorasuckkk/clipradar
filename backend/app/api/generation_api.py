from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.approved_generation_service import (
    generation_status,
    trigger_approved_generation,
)


router = APIRouter(prefix="/generation", tags=["generation"])


class TriggerApprovedGenerationPayload(BaseModel):
    candidate_id: str | None = None
    run_async: bool = True
    retry_failed: bool = False


@router.post("/approved/trigger")
def trigger_generation(payload: TriggerApprovedGenerationPayload) -> dict[str, Any]:
    return trigger_approved_generation(
        candidate_id=payload.candidate_id,
        run_async=payload.run_async,
        force_failed=payload.retry_failed,
    )


@router.get("/approved/status")
def get_generation_status() -> dict[str, Any]:
    return generation_status()
