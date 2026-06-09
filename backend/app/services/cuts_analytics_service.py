from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.cache_manifest_service import cache_summary
from app.services.candidate_review_service import load_candidate_queue
from app.services.post_metadata_service import load_posts, posts_summary


def build_cuts_analytics() -> dict[str, Any]:
    candidates = load_candidate_queue()
    posts = load_posts(status="all")
    post_summary = posts_summary()
    overview = _overview(candidates, post_summary)
    return {
        "updated_at": datetime.utcnow().isoformat(),
        "overview": overview,
        "by_video": _by_video(candidates, posts),
        "by_source": _by_source(candidates),
        "jobs": _jobs(),
        "cache": cache_summary(),
    }


def _overview(candidates: list[dict[str, Any]], post_summary: dict[str, Any]) -> dict[str, Any]:
    reviews = [
        candidate.get("current_candidate_review")
        for candidate in candidates
        if isinstance(candidate.get("current_candidate_review"), dict)
    ]
    status_counts = Counter(str(review.get("status") or "") for review in reviews)
    ratings = [_float(review.get("rating")) for review in reviews]
    ratings = [rating for rating in ratings if rating is not None]
    reason_counts = Counter(
        str(review.get("reason") or "sem_motivo") for review in reviews
    )
    preview_ready = sum(1 for candidate in candidates if candidate.get("preview_exists"))
    reviewed = len(reviews)
    approved = status_counts.get("approved", 0)
    rejected = status_counts.get("rejected", 0)
    needs_adjustment = status_counts.get("needs_adjustment", 0)
    return {
        "total_candidates": len(candidates),
        "preview_ready": preview_ready,
        "missing_preview": max(0, len(candidates) - preview_ready),
        "reviewed": reviewed,
        "pending": max(0, len(candidates) - reviewed),
        "approved": approved,
        "rejected": rejected,
        "needs_adjustment": needs_adjustment,
        "approval_rate": _rate(approved, reviewed),
        "rejection_rate": _rate(rejected, reviewed),
        "adjustment_rate": _rate(needs_adjustment, reviewed),
        "average_rating": _average(ratings),
        "count_by_reason": dict(reason_counts),
        "generated_posts_count": _int(post_summary.get("total")),
        "not_posted_count": _int(post_summary.get("not_posted")),
        "posted_count": _int(post_summary.get("posted")),
        "scheduled_count": _int(post_summary.get("scheduled")),
        "do_not_post_count": _int(post_summary.get("do_not_post")),
    }


def _by_video(candidates: list[dict[str, Any]], posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    posts_by_video = Counter(str(post.get("video_id") or "") for post in posts)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[str(candidate.get("video_id") or "unknown")].append(candidate)
    rows = [_group_row(video_id, items, posts_by_video.get(video_id, 0)) for video_id, items in grouped.items()]
    return sorted(
        rows,
        key=lambda row: (
            row["approved_count"],
            row["approval_rate"] or 0,
            row["average_score"] or 0,
            row["total_candidates"],
        ),
        reverse=True,
    )


def _by_source(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        source = str(candidate.get("source_collection") or "unknown")
        grouped[source].append(candidate)
    rows = [_group_row(source, items, generated_posts_count=0, key_name="source") for source, items in grouped.items()]
    return sorted(
        rows,
        key=lambda row: (
            row["approved_count"],
            row["approval_rate"] or 0,
            row["total_candidates"],
        ),
        reverse=True,
    )


def _group_row(
    key: str,
    items: list[dict[str, Any]],
    generated_posts_count: int,
    key_name: str = "video_id",
) -> dict[str, Any]:
    reviews = [
        item.get("current_candidate_review")
        for item in items
        if isinstance(item.get("current_candidate_review"), dict)
    ]
    statuses = Counter(str(review.get("status") or "") for review in reviews)
    ratings = [_float(review.get("rating")) for review in reviews]
    ratings = [rating for rating in ratings if rating is not None]
    scores = [_candidate_score(item) for item in items]
    scores = [score for score in scores if score is not None]
    approved = statuses.get("approved", 0)
    title = ""
    if key_name == "video_id" and items:
        title = str(items[0].get("video_title") or "")
    row = {
        key_name: key,
        "candidates_count": len(items),
        "total_candidates": len(items),
        "preview_ready": sum(1 for item in items if item.get("preview_exists")),
        "missing_preview": sum(1 for item in items if not item.get("preview_exists")),
        "reviewed_count": len(reviews),
        "reviewed": len(reviews),
        "pending": max(0, len(items) - len(reviews)),
        "approved_count": approved,
        "rejected_count": statuses.get("rejected", 0),
        "needs_adjustment_count": statuses.get("needs_adjustment", 0),
        "approval_rate": _rate(approved, len(reviews)),
        "average_rating": _average(ratings),
        "average_score": _average(scores),
    }
    if key_name == "video_id":
        row["video_title"] = title
        row["generated_posts_count"] = generated_posts_count
    if key_name == "source":
        row["source_collection"] = key
    return row


def _jobs() -> dict[str, Any]:
    runs = _load_job_runs()
    search_runs = [run for run in runs if str(run.get("job_key") or "") == "find_videos_flow"]
    elapsed_values = [_float(run.get("elapsed_seconds")) for run in search_runs]
    elapsed_values = [value for value in elapsed_values if value is not None]
    status_counts = Counter(str(run.get("status") or "unknown") for run in search_runs)
    fast_count = sum(1 for run in search_runs if _run_has_flag(run, "fast_mode", "--fast-mode"))
    deep_count = sum(
        1
        for run in search_runs
        if _run_has_flag(run, "no_candidate_limit", "--no-candidate-limit")
        or _run_has_flag(run, "render_all_good_candidates", "--render-all-good-candidates")
    )
    latest = search_runs[0] if search_runs else {}
    latest_payload = _latest_search_payload(latest)
    return {
        "total_search_runs": len(search_runs),
        "search_runs_count": len(search_runs),
        "fast_search_runs_count": fast_count,
        "deep_search_runs_count": deep_count,
        "success_count": status_counts.get("success", 0),
        "success_with_warnings_count": status_counts.get("success_with_warnings", 0),
        "failed_count": status_counts.get("failed", 0),
        "cancelled_count": status_counts.get("cancelled", 0),
        "average_search_elapsed_seconds": _average(elapsed_values),
        "average_time_to_first_reviewable": _average(_time_to_first_reviewable(search_runs)),
        "average_time_to_first_reviewable_seconds": _average(_time_to_first_reviewable(search_runs)),
        "latest_search": latest_payload,
        "latest_search_run_id": latest_payload.get("run_id", ""),
        "latest_search_status": latest_payload.get("status", ""),
        "latest_search_elapsed_seconds": latest_payload.get("elapsed_seconds"),
        "latest_search_candidate_count": latest_payload.get("candidate_count", 0),
        "latest_search_preview_ready": latest_payload.get("preview_ready", 0),
        "latest_search_pending_reviewable_count": latest_payload.get("pending_reviewable_count", 0),
        "latest_search_next_action": latest_payload.get("next_action", ""),
    }


def _latest_search_payload(run: dict[str, Any]) -> dict[str, Any]:
    if not run:
        return {}
    cache_metrics = _cache_metrics_from_run(run)
    return {
        "run_id": run.get("run_id") or "",
        "status": run.get("status") or "",
        "started_at": run.get("started_at") or "",
        "finished_at": run.get("finished_at") or "",
        "elapsed_seconds": run.get("elapsed_seconds"),
        "candidate_count": _int(run.get("candidate_count")),
        "preview_ready": _int(run.get("preview_ready")),
        "missing_preview": _int(run.get("missing_preview")),
        "pending_reviewable_count": _int(run.get("pending_reviewable_count")),
        "next_action": run.get("next_action") or "",
        "latest_error": run.get("latest_error") or "",
        "warning_message": run.get("warning_message") or "",
        **cache_metrics,
    }


def _cache_metrics_from_run(run: dict[str, Any]) -> dict[str, Any]:
    stdout = "\n".join(
        str(run.get(key) or "")
        for key in ("stdout_tail", "stderr_tail", "latest_error")
    )
    parsed = _parse_cache_summary(stdout)
    return {
        "cache_hits": _int(run.get("cache_hits")) or parsed.get("cache_hits", 0),
        "cache_misses": _int(run.get("cache_misses")) or parsed.get("cache_misses", 0),
        "videos_reused_from_cache": _int(run.get("videos_reused_from_cache")) or parsed.get("videos_reused", 0),
        "videos_processed_from_scratch": _int(run.get("videos_processed_from_scratch")) or parsed.get("videos_processed_from_scratch", 0),
        "estimated_seconds_saved": _float(run.get("estimated_seconds_saved")) or parsed.get("estimated_seconds_saved"),
    }


def _parse_cache_summary(text: str) -> dict[str, Any]:
    match = re.search(r"\[cache_summary\]\s+(.+)", text or "")
    if not match:
        return {}
    values: dict[str, Any] = {}
    for item in match.group(1).split():
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        values[key] = _int(value)
    return values


def _load_job_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in config.STORAGE_JOB_RUNS_DIR.glob("*.json"):
        payload = _load_json(path)
        if isinstance(payload, dict):
            payload["_path"] = str(path)
            payload["_mtime"] = path.stat().st_mtime
            runs.append(payload)
    return sorted(
        runs,
        key=lambda run: str(run.get("started_at") or run.get("created_at") or run.get("_mtime") or ""),
        reverse=True,
    )


def _time_to_first_reviewable(runs: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for run in runs:
        value = _float(run.get("time_to_first_reviewable_seconds"))
        if value is not None:
            values.append(value)
    return values


def _run_has_flag(run: dict[str, Any], param_name: str, cli_flag: str) -> bool:
    params = run.get("params")
    if isinstance(params, dict) and params.get(param_name) is True:
        return True
    command = run.get("command")
    if isinstance(command, list):
        return cli_flag in [str(item) for item in command]
    return cli_flag in str(command or "")


def _candidate_score(candidate: dict[str, Any]) -> float | None:
    for key in ("quality_score", "ranking_quality_score", "score", "source_quality_score"):
        value = _float(candidate.get(key))
        if value is not None:
            return value
    return None


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _rate(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(value / total, 4)


def _int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None
