from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.candidate_review_service import load_candidate_queue, load_candidate_reviews
from app.services.final_clips_service import load_final_clips, load_final_reviews, save_final_reviews


STATE_PATH = config.STORAGE_GENERATION_STATE_DIR / "approved_generation_state.json"
REPORTS_DIR = config.STORAGE_TRENDS_DIR.parent / "reports"
_THREAD_LOCK = threading.Lock()
_WORKER_THREAD: threading.Thread | None = None


def trigger_approved_generation(
    candidate_id: str | None = None,
    run_async: bool = True,
    force_failed: bool = False,
) -> dict[str, Any]:
    state = load_generation_state()
    state = _clear_stale_running_state(state)
    if candidate_id:
        audit = audit_approved_generation()
        if candidate_id in set(audit["generated_candidate_ids"]) and not force_failed:
            _sync_generated_ids(state, audit["generated_candidate_ids"])
            return _response("already_generated", candidate_id, state)
        _append_unique(state["pending_candidate_ids"], candidate_id)
        state["failed_candidate_ids"] = [
            item for item in state["failed_candidate_ids"] if item.get("candidate_id") != candidate_id
        ]
        state["updated_at"] = _now()
        save_generation_state(state)

    if state.get("running"):
        return _response("running", candidate_id, state)

    run_id = _new_run_id()
    state["running"] = True
    state["last_run_id"] = run_id
    state["latest_error"] = ""
    state["updated_at"] = _now()
    save_generation_state(state)

    if run_async:
        _start_worker_thread(run_id, force_failed=force_failed)
    else:
        run_generation_worker(run_id=run_id, force_failed=force_failed)
    refreshed = load_generation_state()
    return _response("queued", candidate_id, refreshed)


def run_generation_worker(run_id: str | None = None, force_failed: bool = False) -> dict[str, Any]:
    run_id = run_id or _new_run_id()
    started_at = _now()
    started_perf = time.perf_counter()
    audit_before = audit_approved_generation()
    state = _backfill_pending_from_audit(load_generation_state(), audit_before)
    pending = list(dict.fromkeys(str(item) for item in state.get("pending_candidate_ids", []) if item))
    if force_failed:
        failed_ids = [str(item.get("candidate_id")) for item in state.get("failed_candidate_ids", []) if item.get("candidate_id")]
        pending = list(dict.fromkeys(pending + failed_ids))
    state.update(
        {
            "running": True,
            "last_run_id": run_id,
            "latest_error": "",
            "updated_at": _now(),
        }
    )
    save_generation_state(state)

    report: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": None,
        "elapsed_seconds": None,
        "pending_candidate_ids": pending,
        "approved_reviews_count": audit_before["approved_reviews_count"],
        "approved_missing_generation_count": audit_before["missing_generation_count"],
        "status": "ok",
        "command": _command_for_display(_pipeline_command()),
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "error_message": "",
    }

    if not pending:
        refresh_result = _refresh_ready_to_post_outputs(audit_before["generated_candidate_ids"])
        state["running"] = False
        state["updated_at"] = _now()
        save_generation_state(state)
        report.update(
            {
                "finished_at": _now(),
                "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
                "status": "nothing_to_generate",
                "refresh_result": refresh_result,
            }
        )
        _write_report(report)
        return report

    completed = _run_pipeline()
    audit_mid = audit_approved_generation()
    refresh_result = (
        _refresh_ready_to_post_outputs(audit_mid["generated_candidate_ids"])
        if completed.returncode == 0
        else None
    )
    report.update(
        {
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
            "refresh_result": refresh_result,
        }
    )

    state = load_generation_state()
    audit_after = audit_approved_generation()
    generated_now = set(audit_after["generated_candidate_ids"]) & set(pending)
    still_missing = [candidate_id for candidate_id in pending if candidate_id not in generated_now]
    if completed.returncode == 0:
        generated = set(str(item) for item in state.get("generated_candidate_ids", []))
        generated.update(generated_now)
        state["generated_candidate_ids"] = sorted(generated)
        pending_set = generated_now
        state["pending_candidate_ids"] = [
            item for item in state.get("pending_candidate_ids", []) if item not in pending_set
        ]
        state["failed_candidate_ids"] = [
            item for item in state.get("failed_candidate_ids", []) if item.get("candidate_id") not in pending_set
        ]
        if still_missing:
            report["status"] = "partial"
            report["error_message"] = "some_approved_candidates_still_missing_final_exports"
            state["failed_candidate_ids"] = _merge_failed(
                state.get("failed_candidate_ids", []),
                still_missing,
                report["error_message"],
            )
            state["latest_error"] = report["error_message"]
    else:
        report["status"] = "error"
        report["error_message"] = f"pipeline_ready_to_post returncode={completed.returncode}"
        state["failed_candidate_ids"] = _merge_failed(
            state.get("failed_candidate_ids", []),
            pending,
            report["error_message"],
        )
        state["latest_error"] = report["error_message"]

    state["running"] = False
    state["updated_at"] = _now()
    save_generation_state(state)

    report.update(
        {
            "finished_at": _now(),
            "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
        }
    )
    _write_report(report)

    next_state = load_generation_state()
    if next_state.get("pending_candidate_ids") and not next_state.get("running"):
        run_generation_worker(run_id=_new_run_id(), force_failed=False)
    return report


def generation_status() -> dict[str, Any]:
    state = _clear_stale_running_state(load_generation_state())
    audit = audit_approved_generation()
    return {
        "running": bool(state.get("running")),
        "pending_count": len(state.get("pending_candidate_ids", [])),
        "generated_count": len(state.get("generated_candidate_ids", [])),
        "failed_count": len(state.get("failed_candidate_ids", [])),
        "approved_reviews_count": audit["approved_reviews_count"],
        "approved_already_generated_count": audit["generated_for_approved_count"],
        "approved_missing_generation_count": audit["missing_generation_count"],
        "last_run_id": state.get("last_run_id") or "",
        "latest_error": state.get("latest_error") or "",
        "pending_candidate_ids": state.get("pending_candidate_ids", []),
        "generated_candidate_ids": state.get("generated_candidate_ids", []),
        "failed_candidate_ids": state.get("failed_candidate_ids", []),
        "updated_at": state.get("updated_at") or "",
    }


def audit_approved_generation() -> dict[str, Any]:
    approved = _approved_candidate_items()
    state = load_generation_state()
    generated_ids: list[str] = []
    missing_ids: list[str] = []
    for candidate_id, item in approved.items():
        if _candidate_final_exists(item):
            generated_ids.append(candidate_id)
        else:
            missing_ids.append(candidate_id)
    generated_set = set(generated_ids)
    state_generated = set(str(item) for item in state.get("generated_candidate_ids", []))
    orphan_generated = sorted(state_generated - set(approved))
    return {
        "approved_reviews_count": len(approved),
        "generated_for_approved_count": len(generated_ids),
        "missing_generation_count": len(missing_ids),
        "orphan_generated_count": len(orphan_generated),
        "approved_candidate_ids": sorted(approved),
        "generated_candidate_ids": sorted(generated_ids),
        "missing_candidate_ids": sorted(missing_ids),
        "orphan_generated_candidate_ids": orphan_generated,
        "state_pending_candidate_ids": state.get("pending_candidate_ids", []),
        "state_generated_candidate_ids": state.get("generated_candidate_ids", []),
        "state_failed_candidate_ids": state.get("failed_candidate_ids", []),
        "posting_package_candidate_ids": _candidate_ids_from_posting_package(),
        "post_metadata_candidate_ids": _candidate_ids_from_post_metadata(),
    }


def load_generation_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return _empty_state()
    try:
        with STATE_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return _empty_state()
    if not isinstance(payload, dict):
        return _empty_state()
    state = _empty_state()
    state.update(payload)
    state["pending_candidate_ids"] = [
        str(item) for item in state.get("pending_candidate_ids", []) if item
    ]
    state["generated_candidate_ids"] = [
        str(item) for item in state.get("generated_candidate_ids", []) if item
    ]
    state["failed_candidate_ids"] = [
        item for item in state.get("failed_candidate_ids", []) if isinstance(item, dict)
    ]
    return state


def save_generation_state(state: dict[str, Any]) -> None:
    config.STORAGE_GENERATION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def _start_worker_thread(run_id: str, force_failed: bool) -> None:
    global _WORKER_THREAD
    with _THREAD_LOCK:
        if _WORKER_THREAD and _WORKER_THREAD.is_alive():
            return
        _WORKER_THREAD = threading.Thread(
            target=run_generation_worker,
            kwargs={"run_id": run_id, "force_failed": force_failed},
            daemon=True,
        )
        _WORKER_THREAD.start()


def _clear_stale_running_state(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("running"):
        return state
    if _WORKER_THREAD and _WORKER_THREAD.is_alive():
        return state
    state["running"] = False
    state["latest_error"] = "stale_generation_worker_marked_idle"
    state["updated_at"] = _now()
    save_generation_state(state)
    return state


def _run_pipeline() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _pipeline_command(),
        cwd=str(config.BACKEND_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=7200,
        check=False,
    )


def _refresh_ready_to_post_outputs(candidate_ids: list[str]) -> dict[str, Any]:
    marked = _mark_generated_candidate_finals_ready(candidate_ids)
    commands = [
        [sys.executable, "-m", "app.jobs.export_final_clips_metadata"],
        [
            sys.executable,
            "-m",
            "app.jobs.export_ready_to_post_package",
            "--package-name",
            "latest",
            "--overwrite",
        ],
        [sys.executable, "-m", "app.jobs.export_post_metadata"],
    ]
    results: list[dict[str, Any]] = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=str(config.BACKEND_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        results.append(
            {
                "command": _command_for_display(command),
                "returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout, limit=1200),
                "stderr_tail": _tail(completed.stderr, limit=1200),
            }
        )
    return {"marked_final_reviews": marked, "commands": results}


def _mark_generated_candidate_finals_ready(candidate_ids: list[str]) -> list[str]:
    pending = set(candidate_ids)
    if not pending:
        return []
    approved = _approved_candidate_items()
    final_reviews = load_final_reviews()
    marked: list[str] = []
    now = _now()
    for clip in load_final_clips(include_duration=False):
        candidate_id = str(clip.get("candidate_id") or "")
        if candidate_id not in pending:
            continue
        final_clip_id = str(clip.get("final_clip_id") or "")
        if not final_clip_id or final_clip_id in final_reviews:
            continue
        source = approved.get(candidate_id, {})
        review = source.get("review", {}) if isinstance(source.get("review"), dict) else {}
        final_reviews[final_clip_id] = {
            "final_clip_id": final_clip_id,
            "clip_id": clip.get("clip_id"),
            "candidate_id": candidate_id,
            "video_id": clip.get("video_id"),
            "final_filename": clip.get("final_filename"),
            "status": "ready_to_post",
            "rating": int(float(review.get("rating") or 5)),
            "reason": review.get("reason") or "candidate_approved",
            "notes": "auto_ready_from_candidate_approval",
            "created_at": now,
            "reviewed_at": now,
            "updated_at": None,
        }
        marked.append(final_clip_id)
    if marked:
        save_final_reviews(final_reviews)
    return marked


def _pipeline_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "app.jobs.pipeline_ready_to_post",
        "--download-missing",
        "--continue-on-error",
        "--package-name",
        "latest",
    ]


def _backfill_pending_from_audit(state: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    missing = set(str(item) for item in audit.get("missing_candidate_ids", []))
    generated = set(str(item) for item in audit.get("generated_candidate_ids", []))
    for candidate_id in sorted(missing):
        _append_unique(state["pending_candidate_ids"], candidate_id)
    _sync_generated_ids(state, generated)
    state["pending_candidate_ids"] = [
        item for item in state.get("pending_candidate_ids", []) if item not in generated
    ]
    state["updated_at"] = _now()
    save_generation_state(state)
    return state


def _sync_generated_ids(state: dict[str, Any], generated_ids: Any) -> None:
    generated = set(str(item) for item in state.get("generated_candidate_ids", []))
    generated.update(str(item) for item in generated_ids if item)
    state["generated_candidate_ids"] = sorted(generated)


def _approved_candidate_items() -> dict[str, dict[str, Any]]:
    reviews = load_candidate_reviews()
    queue_index = {
        str(item.get("candidate_id")): item
        for item in load_candidate_queue()
        if isinstance(item, dict) and item.get("candidate_id")
    }
    approved: dict[str, dict[str, Any]] = {}
    for candidate_id, review in reviews.items():
        if str(review.get("status") or "") != "approved":
            continue
        queue_item = queue_index.get(candidate_id)
        if not queue_item:
            continue
        expected = _expected_paths_for_candidate(queue_item, review)
        approved[candidate_id] = {
            "candidate_id": candidate_id,
            "review": review,
            "queue_item": queue_item,
            **expected,
        }
    return approved


def _expected_paths_for_candidate(
    queue_item: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    video_id = str(queue_item.get("video_id") or review.get("video_id") or "")
    start = _to_float(queue_item.get("start_seconds"))
    end = _to_float(queue_item.get("end_seconds"))
    final_start = _to_float(
        review.get("ideal_start_seconds")
        or queue_item.get("final_start_seconds")
        or start
    )
    final_end = _to_float(
        review.get("ideal_end_seconds")
        or queue_item.get("final_end_seconds")
        or end
    )
    rank = int(queue_item.get("rank") or review.get("rank") or 0)
    rating = _to_float(review.get("rating"))
    reason = str(review.get("reason") or "sem_reason")
    output_filename = _output_filename(video_id, rank, rating, reason, final_start, final_end)
    clip_id = Path(output_filename).stem
    final_filename = f"{clip_id}__vertical__final.mp4"
    return {
        "expected_output_filename": output_filename,
        "expected_clip_id": clip_id,
        "expected_final_filename": final_filename,
        "expected_final_path": str(config.STORAGE_FINAL_EXPORTS_DIR / final_filename),
    }


def _candidate_final_exists(item: dict[str, Any]) -> bool:
    path = Path(str(item.get("expected_final_path") or ""))
    return path.exists() and path.suffix.lower() == ".mp4" and path.stat().st_size > 0


def _candidate_ids_from_posting_package() -> list[str]:
    payload = _load_json(config.STORAGE_POSTING_PACKAGE_DIR / "latest" / "posting_package.json")
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return sorted(
        {
            str(item.get("candidate_id"))
            for item in items
            if isinstance(item, dict) and item.get("candidate_id")
        }
    )


def _candidate_ids_from_post_metadata() -> list[str]:
    payload = _load_json(config.STORAGE_POST_METADATA_DIR / "post_metadata.json")
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return sorted(
        {
            str(item.get("candidate_id"))
            for item in items
            if isinstance(item, dict) and item.get("candidate_id")
        }
    )


def _merge_failed(
    current: list[dict[str, Any]],
    pending: list[str],
    error_message: str,
) -> list[dict[str, Any]]:
    indexed = {str(item.get("candidate_id")): dict(item) for item in current if item.get("candidate_id")}
    failed_at = _now()
    for candidate_id in pending:
        previous = indexed.get(candidate_id, {})
        indexed[candidate_id] = {
            "candidate_id": candidate_id,
            "error_message": error_message,
            "failed_at": failed_at,
            "retry_count": int(previous.get("retry_count") or 0) + 1,
        }
    return list(indexed.values())


def _output_filename(
    video_id: str,
    rank: int,
    rating: float,
    reason: str,
    start: float,
    end: float,
) -> str:
    rating_text = str(int(rating)) if float(rating).is_integer() else str(rating).replace(".", "_")
    return (
        f"{_slug(video_id)}__rank_{rank}__rating_{rating_text}__"
        f"{_slug(reason)}__{int(round(start))}_{int(round(end))}.mp4"
    )


def _slug(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or "clip"


def _to_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _response(status: str, candidate_id: str | None, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "candidate_id": candidate_id or "",
        "run_id": state.get("last_run_id") or "",
        "pending_count": len(state.get("pending_candidate_ids", [])),
        "generated_count": len(state.get("generated_candidate_ids", [])),
        "failed_count": len(state.get("failed_candidate_ids", [])),
    }


def _write_report(payload: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"generate_finals_for_approved_candidates_{timestamp}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _empty_state() -> dict[str, Any]:
    return {
        "running": False,
        "last_run_id": "",
        "pending_candidate_ids": [],
        "generated_candidate_ids": [],
        "failed_candidate_ids": [],
        "latest_error": "",
        "updated_at": _now(),
    }


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _new_run_id() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]


def _now() -> str:
    return datetime.utcnow().isoformat()


def _tail(value: str | None, limit: int = 4000) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[-limit:]


def _command_for_display(command: list[str]) -> str:
    return " ".join(_quote_arg(arg) for arg in command)


def _quote_arg(arg: object) -> str:
    text = str(arg)
    if not text or any(char.isspace() for char in text):
        return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
    return text
