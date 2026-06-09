from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.jobs.batch_status import build_status
from app.services.local_job_runner_service import LocalJobRunnerService


router = APIRouter(prefix="/ops", tags=["operations"])
runner = LocalJobRunnerService()


class JobRunRequest(BaseModel):
    job_key: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/jobs")
def list_jobs() -> dict[str, Any]:
    jobs = runner.list_jobs()
    return {"jobs": jobs, "count": len(jobs)}


@router.get("/status")
def ops_status(video_id: str | None = Query(None)) -> dict[str, Any]:
    return build_status(video_id=video_id)


@router.post("/jobs/run")
def run_job(payload: JobRunRequest) -> dict[str, Any]:
    try:
        return runner.start_job(payload.job_key, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/runs")
def list_runs(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    runs = runner.list_runs(limit=limit)
    return {"runs": runs, "count": len(runs)}


@router.get("/jobs/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = runner.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    return run


@router.get("/jobs/runs/{run_id}/logs")
def get_run_logs(run_id: str) -> dict[str, Any]:
    logs = runner.get_logs(run_id)
    if not logs:
        raise HTTPException(status_code=404, detail="run_not_found")
    return logs


@router.post("/jobs/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict[str, Any]:
    run = runner.cancel_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    return {
        "run_id": run_id,
        "status": run.get("status"),
        "cancel_supported": True,
        "message": run.get("cancel_message") or "job_cancelled",
    }
