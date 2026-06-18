"""SQLite-backed background job queue (Bloco A).

A single daemon worker thread drains a durable queue so long-running work
(render, voice, script generation) never runs on a FastAPI request thread.
Jobs are pollable (status/progress), retryable (max_attempts) and cancellable.

Handlers register by job ``type``. A handler receives a :class:`JobContext`
and may report progress, check for cancellation, and register the PID of a
child process so the queue can kill it on cancel.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Callable

from app import config
from app.services.log_sanitizer import sanitize
from app.storage import db


JobHandler = Callable[["JobContext"], "dict[str, Any] | None"]

_HANDLERS: dict[str, JobHandler] = {}
_WORKER_THREAD: threading.Thread | None = None
_WORKER_LOCK = threading.Lock()
_HANDLERS_LOADED = False
_STOP = threading.Event()

POLL_INTERVAL_SECONDS = 1.0
TERMINAL_STATUSES = {"success", "failed", "cancelled"}


class JobCancelled(Exception):
    """Raised inside a handler when the job has been cancelled."""


class JobContext:
    def __init__(self, job_id: str, job_type: str, project_id: str | None, payload: dict[str, Any]) -> None:
        self.job_id = job_id
        self.job_type = job_type
        self.project_id = project_id
        self.payload = payload

    def set_progress(self, progress: float, step: str = "") -> None:
        progress = max(0.0, min(1.0, float(progress)))
        _patch(self.job_id, "progress=?, step=?, updated_at=?", (progress, step, _now()))

    def set_pid(self, pid: int | None) -> None:
        _patch(self.job_id, "pid=?, updated_at=?", (pid, _now()))

    def is_cancelled(self) -> bool:
        row = db.query_one("SELECT cancel_requested FROM jobs WHERE id=?", (self.job_id,))
        return bool(row and row.get("cancel_requested"))

    def check_cancelled(self) -> None:
        if self.is_cancelled():
            raise JobCancelled()


def register_handler(job_type: str, handler: JobHandler) -> None:
    _HANDLERS[job_type] = handler


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enqueue(
    job_type: str,
    payload: dict[str, Any] | None = None,
    project_id: str | None = None,
    max_attempts: int | None = None,
    priority: int = 0,
) -> dict[str, Any]:
    bootstrap()
    job_id = "job_" + uuid.uuid4().hex[:16]
    now = _now()
    attempts_cap = int(max_attempts if max_attempts is not None else config.GENERATION_JOB_MAX_ATTEMPTS)
    db.mutate(
        """
        INSERT INTO jobs (id, type, project_id, payload, status, max_attempts, priority, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?)
        """,
        (job_id, job_type, project_id, db.to_json(payload or {}), max(1, attempts_cap), priority, now, now),
    )
    return get_job(job_id) or {"id": job_id, "status": "queued", "type": job_type}


def get_job(job_id: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM jobs WHERE id=?", (job_id,))
    return _public_job(row) if row else None


def list_jobs(
    job_type: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if job_type:
        clauses.append("type=?")
        params.append(job_type)
    if project_id:
        clauses.append("project_id=?")
        params.append(project_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(max(1, min(limit, 200)))
    rows = db.query_all(
        f"SELECT * FROM jobs{where} ORDER BY created_at DESC LIMIT ?",
        tuple(params),
    )
    return [_public_job(row) for row in rows]


def cancel_job(job_id: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not row:
        return None
    status = row.get("status")
    now = _now()
    if status == "queued":
        db.mutate(
            "UPDATE jobs SET status='cancelled', cancel_requested=1, finished_at=?, updated_at=?, error='job_cancelled' WHERE id=?",
            (now, now, job_id),
        )
    elif status == "running":
        db.mutate("UPDATE jobs SET cancel_requested=1, updated_at=? WHERE id=?", (now, job_id))
        pid = row.get("pid")
        if pid:
            _terminate_pid(int(pid))
    return get_job(job_id)


def retry_job(job_id: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not row:
        return None
    if row.get("status") not in {"failed", "cancelled"}:
        return get_job(job_id)
    now = _now()
    db.mutate(
        """
        UPDATE jobs SET status='queued', attempts=0, cancel_requested=0, progress=0, step='',
        error=NULL, result=NULL, pid=NULL, started_at=NULL, finished_at=NULL, updated_at=?
        WHERE id=?
        """,
        (now, job_id),
    )
    bootstrap()
    return get_job(job_id)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def bootstrap() -> None:
    """Idempotent: init schema, load handlers, start the worker thread."""
    db.init_db()
    _load_handlers()
    start_worker()


def start_worker() -> None:
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD and _WORKER_THREAD.is_alive():
            return
        _STOP.clear()
        _WORKER_THREAD = threading.Thread(target=_worker_loop, name="darkflow-job-worker", daemon=True)
        _WORKER_THREAD.start()


def stop_worker() -> None:
    _STOP.set()


def _load_handlers() -> None:
    global _HANDLERS_LOADED
    if _HANDLERS_LOADED:
        return
    _HANDLERS_LOADED = True
    # Import modules that register handlers. Kept lazy to avoid import cycles
    # (handler modules import this service to call register_handler).
    try:
        from app.services import generation_render_service  # noqa: F401
    except Exception as exc:  # pragma: no cover - defensive
        print(f"job_queue: failed to load generation_render handler: {sanitize(str(exc))}")
    try:
        from app.services import generation_voice_service  # noqa: F401
    except Exception as exc:  # pragma: no cover - defensive
        print(f"job_queue: failed to load generation_voice handler: {sanitize(str(exc))}")
    try:
        from app.services import generation_autopilot_service  # noqa: F401
    except Exception as exc:  # pragma: no cover - defensive
        print(f"job_queue: failed to load generation_autopilot handler: {sanitize(str(exc))}")


def _worker_loop() -> None:
    # Recover jobs left 'running' by a previous process crash.
    _recover_orphaned_jobs()
    while not _STOP.is_set():
        job = _claim_next_job()
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        _run_job(job)


def _claim_next_job() -> dict[str, Any] | None:
    try:
        with db.write_transaction() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status='queued' AND cancel_requested=0 "
                "ORDER BY priority DESC, created_at ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            job = dict(row)
            now = _now()
            conn.execute(
                "UPDATE jobs SET status='running', started_at=COALESCE(started_at, ?), "
                "attempts=attempts+1, updated_at=? WHERE id=?",
                (now, now, job["id"]),
            )
            job["attempts"] = int(job.get("attempts") or 0) + 1
            return job
    except Exception as exc:  # pragma: no cover - defensive
        print(f"job_queue: claim failed: {sanitize(str(exc))}")
        return None


def _run_job(job: dict[str, Any]) -> None:
    handler = _HANDLERS.get(job["type"])
    payload = db.from_json(job.get("payload"), {}) or {}
    ctx = JobContext(job["id"], job["type"], job.get("project_id"), payload)
    if handler is None:
        _finish(job["id"], "failed", error=f"no_handler_for_type:{job['type']}")
        return
    try:
        result = handler(ctx) or {}
        _finish(job["id"], "success", result=result, progress=1.0)
    except JobCancelled:
        _finish(job["id"], "cancelled", error="job_cancelled")
    except Exception as exc:
        message = sanitize(str(exc)) or sanitize(traceback.format_exc())
        attempts = int(job.get("attempts") or 1)
        max_attempts = int(job.get("max_attempts") or 1)
        if attempts < max_attempts:
            _requeue(job["id"], error=message)
        else:
            _finish(job["id"], "failed", error=message)


def _requeue(job_id: str, error: str) -> None:
    now = _now()
    db.mutate(
        "UPDATE jobs SET status='queued', pid=NULL, error=?, step='retrying', updated_at=? WHERE id=?",
        (error, now, job_id),
    )


def _finish(
    job_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    progress: float | None = None,
) -> None:
    now = _now()
    sets = ["status=?", "finished_at=?", "updated_at=?", "pid=NULL"]
    params: list[Any] = [status, now, now]
    if result is not None:
        sets.append("result=?")
        params.append(db.to_json(result))
    if error is not None:
        sets.append("error=?")
        params.append(sanitize(error))
    if progress is not None:
        sets.append("progress=?")
        params.append(max(0.0, min(1.0, float(progress))))
    params.append(job_id)
    db.mutate(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", tuple(params))


def _recover_orphaned_jobs() -> None:
    """Jobs stuck in 'running' after a backend restart can never be resumed by
    this in-process model — mark them failed so the user can retry."""
    rows = db.query_all("SELECT id, pid FROM jobs WHERE status='running'")
    for row in rows:
        pid = row.get("pid")
        if pid and _process_exists(int(pid)):
            continue
        _finish(row["id"], "failed", error="orphaned_after_restart")


def _patch(job_id: str, set_clause: str, params: tuple[Any, ...]) -> None:
    db.mutate(f"UPDATE jobs SET {set_clause} WHERE id=?", (*params, job_id))


def _public_job(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "type": row.get("type"),
        "project_id": row.get("project_id"),
        "status": row.get("status"),
        "progress": row.get("progress") or 0.0,
        "step": row.get("step") or "",
        "attempts": row.get("attempts") or 0,
        "max_attempts": row.get("max_attempts") or 1,
        "cancel_requested": bool(row.get("cancel_requested")),
        "result": db.from_json(row.get("result"), None),
        "error": row.get("error") or "",
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "updated_at": row.get("updated_at"),
    }


def _now() -> str:
    return datetime.utcnow().isoformat()


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=5, check=False,
            )
            return str(pid) in (completed.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_pid(pid: int) -> None:
    if pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, check=False,
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
