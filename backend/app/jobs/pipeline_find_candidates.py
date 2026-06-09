from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.candidate_review_service import (
    QUEUE_PATH,
    filter_candidate_clips,
    load_candidate_queue,
)
from app.services.cache_manifest_service import get_cache_status, has_valid_clips
from app.services.video_history_service import VideoHistoryService


Step = dict[str, Any]


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-videos", type=int, default=3)
    parser.add_argument("--max-previews", type=int, default=10)
    parser.add_argument("--max-previews-initial", type=int)
    parser.add_argument("--max-previews-total", type=int)
    parser.add_argument("--render-all-good-candidates", action="store_true")
    parser.add_argument("--include-diagnostics", action="store_true")
    parser.add_argument("--download-missing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-candidate-limit", action="store_true")
    parser.add_argument("--max-candidates-per-video")
    parser.add_argument("--min-ranking-score", type=float, default=6.0)
    parser.add_argument("--min-source-score", type=float, default=0.0)
    parser.add_argument("--min-duration", type=float, default=25.0)
    parser.add_argument("--max-duration", type=float, default=120.0)
    parser.add_argument("--quality-threshold", type=float, default=6.0)
    parser.add_argument("--dedup-overlap", type=float, default=0.65)
    parser.add_argument("--fast-mode", action="store_true")
    parser.add_argument("--min-reviewable-to-release", type=int, default=3)
    parser.add_argument("--max-seconds-before-partial-release", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    if args.fast_mode:
        _run_fast_mode(args)
        return

    started_at = datetime.utcnow().isoformat()
    started_perf = time.perf_counter()
    process_started_perf = time.time()
    steps = _build_steps(args)
    results: list[Step] = []
    export_video_ids: list[str] = []

    print("PIPELINE FIND CANDIDATES")
    print("")

    for index, step in enumerate(steps, start=1):
        print(f"Step {index}/{len(steps)}: {step['label']}")
        print(f"[step_start] step={index} name={step['name']} started_at={datetime.utcnow().isoformat()}", flush=True)
        if step["name"] == "export_candidate_review_queue":
            processed_ids = _processed_video_ids_since(process_started_perf)
            if not processed_ids:
                processed_ids = _recent_clip_video_ids(args.max_videos)
            export_video_ids = processed_ids
            if processed_ids:
                step["command"].append(f"--video-id={','.join(processed_ids)}")
        print(f"[step_command] step={index} command={_command_for_display(step['command'])}", flush=True)
        if args.dry_run:
            result = _dry_run_step(step)
            results.append(result)
            print(f"Command: {_command_for_display(step['command'])}")
            print("Status: DRY_RUN")
            print(
                f"[step_end] step={index} name={step['name']} status=DRY_RUN returncode=None elapsed_seconds=0.0",
                flush=True,
            )
            print("")
            continue

        result = _run_step(step)
        results.append(result)
        print(f"Status: {result['status'].upper()}")
        if result.get("error_message"):
            print(result["error_message"])
            print(
                f"[step_error] step={index} name={step['name']} returncode={result.get('returncode')} "
                f"stderr_tail={_single_line(result.get('stderr_tail') or result.get('stdout_tail') or result.get('error_message'))}",
                flush=True,
            )
            print(
                f"[step_end] step={index} name={step['name']} status=ERROR "
                f"returncode={result.get('returncode')} elapsed_seconds={result.get('elapsed_seconds')}",
                flush=True,
            )
        else:
            print(
                f"[step_end] step={index} name={step['name']} status={result['status'].upper()} "
                f"returncode={result.get('returncode')} elapsed_seconds={result.get('elapsed_seconds')}",
                flush=True,
            )
        print("")
        if result["status"] == "error" and not args.continue_on_error:
            if step["name"] == "process_queue" and _has_recent_or_existing_clips(args.max_videos, process_started_perf):
                print("[pipeline_warning] process_queue failed, but clip outputs exist; continuing to export candidates", flush=True)
                continue
            break

    finished_at = datetime.utcnow().isoformat()
    summary = _candidate_summary()
    queue_payload = _candidate_queue_payload()
    cache_metrics = _cache_metrics_from_results(results, export_video_ids)
    steps_failed = sum(1 for item in results if item["status"] == "error")
    has_ready_candidates = summary["total_candidates"] > 0 and summary["preview_ready"] > 0
    pipeline_status = "success"
    if steps_failed > 0:
        pipeline_status = "success_with_warnings" if has_ready_candidates else "failed"
    payload = {
        "status": pipeline_status,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
        "dry_run": args.dry_run,
        "continue_on_error": args.continue_on_error,
        "max_videos": args.max_videos,
        "max_previews": args.max_previews,
        "max_previews_initial": args.max_previews_initial,
        "max_previews_total": args.max_previews_total,
        "render_all_good_candidates": args.render_all_good_candidates,
        "no_candidate_limit": args.no_candidate_limit,
        "max_candidates_per_video": args.max_candidates_per_video,
        "min_ranking_score": args.min_ranking_score,
        "min_source_score": args.min_source_score,
        "min_duration": args.min_duration,
        "max_duration": args.max_duration,
        "quality_threshold": args.quality_threshold,
        "dedup_overlap": args.dedup_overlap,
        "candidates_raw": queue_payload.get("candidates_raw"),
        "candidates_after_quality_filter": queue_payload.get("candidates_after_quality_filter"),
        "candidates_after_dedup": queue_payload.get("candidates_after_dedup"),
        "duplicates_removed": queue_payload.get("duplicates_removed"),
        "duplicate_candidates_detected": queue_payload.get("duplicate_candidate_ids_removed"),
        "duplicates_removed_from_cache": queue_payload.get("duplicates_removed_from_cache"),
        "duplicates_removed_from_new_processing": queue_payload.get("duplicates_removed_from_new_processing"),
        "candidates_dropped_by_quality": queue_payload.get("candidates_dropped_by_quality"),
        "candidates_dropped_by_dedupe": queue_payload.get("candidates_dropped_by_dedupe"),
        "candidates_dropped_by_limit": queue_payload.get("candidates_dropped_by_limit"),
        "candidate_stats_by_video": queue_payload.get("stats_by_video", []),
        **cache_metrics,
        "steps_total": len(results),
        "steps_ok": sum(1 for item in results if item["status"] == "ok"),
        "steps_skipped": sum(1 for item in results if item["status"] in {"dry_run", "skipped"}),
        "steps_failed": steps_failed,
        "selected_videos_count": _selected_videos_count(results),
        "processed_videos_count": len(export_video_ids) or len(_processed_video_ids_since(process_started_perf)),
        "export_video_ids": export_video_ids,
        "candidate_count": summary["total_candidates"],
        "preview_ready": summary["preview_ready"],
        "missing_preview": summary["missing_preview"],
        "candidate_pending_reviews": summary["pending"],
        "next_action": _next_action(summary),
        "steps": results,
    }
    report_paths = _write_report(payload)

    print("PIPELINE FIND CANDIDATES SUMMARY")
    print(f"steps_ok: {payload['steps_ok']}")
    print(f"steps_failed: {payload['steps_failed']}")
    print(f"selected_videos_count: {payload['selected_videos_count']}")
    print(f"processed_videos_count: {payload['processed_videos_count']}")
    print(f"candidate_count: {payload['candidate_count']}")
    print(f"preview_ready: {payload['preview_ready']}")
    print(f"missing_preview: {payload['missing_preview']}")
    print(f"candidate_pending_reviews: {payload['candidate_pending_reviews']}")
    print(f"cache_hits: {payload['cache_hits']}")
    print(f"cache_misses: {payload['cache_misses']}")
    print(f"cache_partials: {payload['cache_partials']}")
    print(f"cache_bypassed: {payload['cache_bypassed']}")
    print(f"status: {pipeline_status}")
    print(f"next_action: {payload['next_action']}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")

    if pipeline_status == "failed" and not args.continue_on_error:
        raise SystemExit(1)


def _run_fast_mode(args: argparse.Namespace) -> None:
    started_at = datetime.utcnow().isoformat()
    started_perf = time.perf_counter()
    process_started_timestamp = time.time()
    processed_video_ids: list[str] = []
    partial_reviewable = False
    released_at: str | None = None
    early_exit = False
    warning_message = ""
    results: list[Step] = []

    print("PIPELINE FIND CANDIDATES")
    print("[fast_mode] enabled=true")
    print(
        "[fast_config] "
        f"max_videos={args.max_videos} max_previews={args.max_previews} "
        f"min_reviewable_to_release={args.min_reviewable_to_release} "
        f"max_seconds_before_partial_release={args.max_seconds_before_partial_release} "
        f"overwrite={args.overwrite}",
        flush=True,
    )
    print("")

    bootstrap_steps = _build_fast_bootstrap_steps(args)
    for index, step in enumerate(bootstrap_steps, start=1):
        result = _execute_numbered_step(index, 5, step, args.dry_run)
        results.append(result)
        if result["status"] == "error" and not args.continue_on_error:
            break

    if not args.dry_run and not any(item["status"] == "error" for item in results):
        videos = _fast_processing_videos(args.max_videos)
        total_videos = len(videos)
        print("Step 3/5: process selected videos")
        print(
            f"[step_start] step=3 name=process_queue started_at={datetime.utcnow().isoformat()}",
            flush=True,
        )
        print(f"[step3_start] total_videos={total_videos}", flush=True)
        step_started_at = datetime.utcnow().isoformat()
        step_started_perf = time.perf_counter()
        step_error = ""
        step_returncode = 0
        step_stdout_parts: list[str] = []
        step_stderr_parts: list[str] = []

        for index, video in enumerate(videos, start=1):
            before_summary = _candidate_summary()
            before_pending_reviewable = _pending_reviewable_count()
            before_exit, before_reason = _should_early_exit_fast_mode(
                before_summary,
                before_pending_reviewable,
                started_perf,
                args,
            )
            if before_exit:
                partial_reviewable = before_pending_reviewable > 0
                released_at = released_at or datetime.utcnow().isoformat()
                early_exit = True
                warning_message = _early_exit_warning(before_reason)
                print(
                    "[early_exit] "
                    f"reason={before_reason} preview_ready={before_summary['preview_ready']} "
                    f"pending_reviewable={before_pending_reviewable} "
                    f"next_action={_next_action_for_pending(before_summary, before_pending_reviewable)}",
                    flush=True,
                )
                break
            video_id = str(video.get("video_id") or "")
            title = _single_line(video.get("title") or video_id, 160)
            if not video_id:
                continue
            print(
                f"[step3_video_start] video_id={video_id} index={index}/{total_videos} title={title}",
                flush=True,
            )
            print(
                f"[partial_status] partial_reviewable={str(partial_reviewable).lower()} "
                f"current_video_id={video_id} current_video_index={index} total_videos={total_videos} "
                f"current_step_detail=processando_video",
                flush=True,
            )
            video_started = time.perf_counter()
            cached = _clip_cache_exists(video_id) and not args.overwrite
            if cached:
                print(f"[step3_cache_hit] video_id={video_id} clips_path={_clips_path(video_id)}", flush=True)
                process_result = _cached_step_result(video_id, video_started)
            else:
                print(f"[step3_process_start] video_id={video_id}", flush=True)
                process_result = _run_streaming_command(
                    {
                        "name": "process_queue_video",
                        "command": _command("app.jobs.process_queue", video_id=video_id),
                        "env": {"MAX_VIDEOS_PER_RUN": "1"},
                    },
                    prefix=f"[process_queue:{video_id}] ",
                )
                print(
                    f"[step3_process_end] video_id={video_id} "
                    f"returncode={process_result.get('returncode')} "
                    f"elapsed_seconds={process_result.get('elapsed_seconds')}",
                    flush=True,
                )

            step_stdout_parts.append(process_result.get("stdout_tail", ""))
            step_stderr_parts.append(process_result.get("stderr_tail", ""))
            if process_result["status"] == "error":
                step_returncode = int(process_result.get("returncode") or 1)
                step_error = process_result.get("error_message") or "process_queue_video_failed"
                if not args.continue_on_error and not _clip_cache_exists(video_id):
                    print(
                        f"[step3_video_end] video_id={video_id} status=ERROR "
                        f"elapsed_seconds={round(time.perf_counter() - video_started, 2)}",
                        flush=True,
                    )
                    break
            if _clip_cache_exists(video_id):
                processed_video_ids.append(video_id)
                export_result = _run_fast_export_and_preview(args, processed_video_ids)
                step_stdout_parts.append(export_result.get("stdout_tail", ""))
                step_stderr_parts.append(export_result.get("stderr_tail", ""))
                summary = _candidate_summary()
                pending_reviewable = _pending_reviewable_count()
                should_release = _should_release_fast_mode(
                    pending_reviewable,
                    args.min_reviewable_to_release,
                    started_perf,
                    args.max_seconds_before_partial_release,
                )
                if should_release and not partial_reviewable:
                    partial_reviewable = True
                    released_at = datetime.utcnow().isoformat()
                    early_exit = True
                    warning_message = _early_exit_warning("partial_release")
                    print(
                        "[partial_release] "
                        f"partial_reviewable=true partial_candidate_count={summary['total_candidates']} "
                        f"partial_preview_ready={summary['preview_ready']} "
                        f"partial_pending_reviewable_count={pending_reviewable} "
                        "next_action=open_candidate_clips",
                        flush=True,
                    )
                should_exit, exit_reason = _should_early_exit_fast_mode(
                    summary,
                    pending_reviewable,
                    started_perf,
                    args,
                )
                if should_exit:
                    early_exit = True
                    warning_message = _early_exit_warning(exit_reason)
                    print(
                        "[early_exit] "
                        f"reason={exit_reason} preview_ready={summary['preview_ready']} "
                        f"pending_reviewable={pending_reviewable} "
                        f"next_action={_next_action_for_pending(summary, pending_reviewable)}",
                        flush=True,
                    )
                print(
                    "[step3_progress] "
                    f"processed={len(processed_video_ids)}/{total_videos} "
                    f"candidates_so_far={summary['total_candidates']} "
                    f"previews_ready_so_far={summary['preview_ready']} "
                    f"pending_reviewable={pending_reviewable}",
                    flush=True,
                )
                print(
                    "[partial_status] "
                    f"partial_reviewable={str(partial_reviewable).lower()} "
                    f"partial_candidate_count={summary['total_candidates']} "
                    f"partial_preview_ready={summary['preview_ready']} "
                    f"partial_pending_reviewable_count={pending_reviewable} "
                    f"current_video_id={video_id} current_video_index={index} total_videos={total_videos} "
                    "current_step_detail=previews_atualizados",
                    flush=True,
                )
            print(
                f"[step3_video_end] video_id={video_id} "
                f"elapsed_seconds={round(time.perf_counter() - video_started, 2)}",
                flush=True,
            )
            if early_exit:
                break

        step_status = "error" if step_error else "ok"
        step_result = {
            "name": "process_queue",
            "command": "progressive process_queue --video-id",
            "status": step_status,
            "returncode": step_returncode,
            "started_at": step_started_at,
            "finished_at": datetime.utcnow().isoformat(),
            "elapsed_seconds": round(time.perf_counter() - step_started_perf, 2),
            "stdout_tail": _tail("\n".join(step_stdout_parts)),
            "stderr_tail": _tail("\n".join(step_stderr_parts)),
            "error_message": step_error,
        }
        results.append(step_result)
        print(
            f"[step_end] step=3 name=process_queue status={step_status.upper()} "
            f"returncode={step_returncode} elapsed_seconds={step_result['elapsed_seconds']}",
            flush=True,
        )
        print("")

    if args.dry_run:
        dry_export = _fast_export_step(args, [])
        dry_preview = _fast_preview_step(args)
        results.append(_execute_numbered_step(3, 5, _fast_process_dry_step(args), True))
        results.append(_execute_numbered_step(4, 5, dry_export, True))
        results.append(_execute_numbered_step(5, 5, dry_preview, True))
    elif early_exit:
        results.append(_skipped_step(_fast_export_step(args, processed_video_ids), warning_message))
        results.append(_skipped_step(_fast_preview_step(args, _remaining_preview_cap(args)), warning_message))
    elif processed_video_ids:
        results.append(_execute_numbered_step(4, 5, _fast_export_step(args, processed_video_ids), False))
        results.append(_execute_numbered_step(5, 5, _fast_preview_step(args, _remaining_preview_cap(args)), False))

    _finish_pipeline(
        args=args,
        started_at=started_at,
        started_perf=started_perf,
        process_started_perf=process_started_timestamp,
        results=results,
        export_video_ids=processed_video_ids,
        fast_mode=True,
        partial_reviewable=partial_reviewable,
        partial_release_at=released_at,
        early_exit=early_exit,
        warning_message=warning_message,
    )


def _execute_numbered_step(index: int, total: int, step: Step, dry_run: bool) -> Step:
    print(f"Step {index}/{total}: {step['label']}")
    print(
        f"[step_start] step={index} name={step['name']} started_at={datetime.utcnow().isoformat()}",
        flush=True,
    )
    print(f"[step_command] step={index} command={_command_for_display(step['command'])}", flush=True)
    if dry_run:
        result = _dry_run_step(step)
        print(f"Command: {_command_for_display(step['command'])}")
        print("Status: DRY_RUN")
        print(
            f"[step_end] step={index} name={step['name']} status=DRY_RUN returncode=None elapsed_seconds=0.0",
            flush=True,
        )
        print("")
        return result
    result = _run_step(step)
    print(f"Status: {result['status'].upper()}")
    if result.get("error_message"):
        print(result["error_message"])
        print(
            f"[step_error] step={index} name={step['name']} returncode={result.get('returncode')} "
            f"stderr_tail={_single_line(result.get('stderr_tail') or result.get('stdout_tail') or result.get('error_message'))}",
            flush=True,
        )
    print(
        f"[step_end] step={index} name={step['name']} status={result['status'].upper()} "
        f"returncode={result.get('returncode')} elapsed_seconds={result.get('elapsed_seconds')}",
        flush=True,
    )
    print("")
    return result


def _build_steps(args: argparse.Namespace) -> list[Step]:
    preview_cap = _preview_cap(args)
    return [
        {
            "name": "discover_podcast_batch",
            "label": "discover videos",
            "command": _command("app.jobs.discover_podcast_batch"),
            "env": {},
        },
        {
            "name": "review_selected_videos",
            "label": "review selected videos",
            "command": _command("app.jobs.review_selected_videos"),
            "env": {},
        },
        {
            "name": "process_queue",
            "label": "process selected videos",
            "command": _command("app.jobs.process_queue"),
            "env": {
                "MAX_VIDEOS_PER_RUN": str(max(0, args.max_videos)),
                **({"CLIPRADAR_NO_CANDIDATE_LIMIT": "1"} if args.no_candidate_limit else {}),
            },
        },
        {
            "name": "export_candidate_review_queue",
            "label": "export candidate queue",
            "command": _command(
                "app.jobs.export_candidate_review_queue",
                include_diagnostics=args.include_diagnostics or args.no_candidate_limit,
                overwrite=args.overwrite,
                no_candidate_limit=args.no_candidate_limit,
                max_candidates_per_video=args.max_candidates_per_video,
                min_ranking_score=args.min_ranking_score,
                min_source_score=args.min_source_score,
                min_duration=args.min_duration,
                max_duration=args.max_duration,
                quality_threshold=args.quality_threshold,
                dedup_overlap=args.dedup_overlap,
            ),
            "env": {},
        },
        {
            "name": "render_candidate_previews",
            "label": "render candidate previews",
            "command": _command(
                "app.jobs.render_candidate_previews",
                only_missing=True,
                download_missing=args.download_missing,
                overwrite=args.overwrite,
                max_missing=preview_cap,
                render_all_good_candidates=args.render_all_good_candidates,
                max_previews_total=args.max_previews_total,
            ),
            "env": {},
        },
    ]


def _build_fast_bootstrap_steps(args: argparse.Namespace) -> list[Step]:
    return _build_steps(args)[:2]


def _fast_process_dry_step(args: argparse.Namespace) -> Step:
    return {
        "name": "process_queue",
        "label": "process selected videos progressively",
        "command": _command("app.jobs.process_queue", video_id="<each-selected-video>"),
        "env": {"MAX_VIDEOS_PER_RUN": "1"},
    }


def _fast_export_step(args: argparse.Namespace, video_ids: list[str]) -> Step:
    command = _command(
        "app.jobs.export_candidate_review_queue",
        include_diagnostics=args.include_diagnostics or args.no_candidate_limit,
        overwrite=args.overwrite,
        no_candidate_limit=args.no_candidate_limit,
        max_candidates_per_video=args.max_candidates_per_video,
        min_ranking_score=args.min_ranking_score,
        min_source_score=args.min_source_score,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        quality_threshold=args.quality_threshold,
        dedup_overlap=args.dedup_overlap,
    )
    if video_ids:
        command.append(f"--video-id={','.join(list(dict.fromkeys(video_ids)))}")
    return {
        "name": "export_candidate_review_queue",
        "label": "export candidate queue",
        "command": command,
        "env": {},
    }


def _fast_preview_step(args: argparse.Namespace, max_missing: int | None = None) -> Step:
    return {
        "name": "render_candidate_previews",
        "label": "render candidate previews",
        "command": _command(
            "app.jobs.render_candidate_previews",
            only_missing=True,
            download_missing=args.download_missing,
            overwrite=args.overwrite,
            max_missing=max_missing if max_missing is not None else _preview_cap(args),
            render_all_good_candidates=args.render_all_good_candidates,
            max_previews_total=args.max_previews_total,
        ),
        "env": {},
    }


def _fast_processing_videos(limit: int) -> list[dict[str, Any]]:
    history = VideoHistoryService()
    videos = history.get_next_for_processing(max(0, limit))
    if videos:
        return videos
    cached_ids = _recent_clip_video_ids(limit)
    data = history._read()
    return [data.get(video_id, {"video_id": video_id, "title": video_id}) for video_id in cached_ids]


def _run_fast_export_and_preview(args: argparse.Namespace, video_ids: list[str]) -> Step:
    export_result = _run_step(_fast_export_step(args, video_ids))
    if export_result["status"] == "error":
        return export_result
    remaining = _remaining_preview_cap(args)
    if remaining is not None and remaining <= 0:
        return export_result
    preview_result = _run_step(_fast_preview_step(args, max_missing=remaining))
    stdout = "\n".join(
        item
        for item in (export_result.get("stdout_tail", ""), preview_result.get("stdout_tail", ""))
        if item
    )
    stderr = "\n".join(
        item
        for item in (export_result.get("stderr_tail", ""), preview_result.get("stderr_tail", ""))
        if item
    )
    return {
        "name": "progressive_export_preview",
        "command": f"{export_result['command']} && {preview_result['command']}",
        "status": "error" if preview_result["status"] == "error" else "ok",
        "returncode": preview_result.get("returncode"),
        "started_at": export_result["started_at"],
        "finished_at": preview_result["finished_at"],
        "elapsed_seconds": round(
            float(export_result.get("elapsed_seconds") or 0)
            + float(preview_result.get("elapsed_seconds") or 0),
            2,
        ),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "error_message": preview_result.get("error_message", ""),
    }


def _remaining_preview_cap(args: argparse.Namespace) -> int | None:
    preview_cap = _preview_cap(args)
    if preview_cap is None:
        return None
    return max(0, preview_cap - _candidate_summary()["preview_ready"])


def _clips_path(video_id: str) -> Path:
    return config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json"


def _clip_cache_exists(video_id: str) -> bool:
    return has_valid_clips(video_id)


def _cached_step_result(video_id: str, started_perf: float) -> Step:
    now = datetime.utcnow().isoformat()
    cache = get_cache_status(video_id)
    transcript_hit = str(bool(cache.get("transcript_exists"))).lower()
    clips_hit = str(bool(cache.get("clips_exists"))).lower()
    previews_hit = str(int(cache.get("previews_ready_count") or 0) > 0).lower()
    return {
        "name": "process_queue_video",
        "command": f"cache_hit {video_id}",
        "status": "ok",
        "returncode": 0,
        "started_at": now,
        "finished_at": now,
        "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
        "stdout_tail": (
            f"[cache_check] video_id={video_id}\n"
            f"[cache_hit] transcript={transcript_hit} clips={clips_hit} previews={previews_hit} video_id={video_id}\n"
            f"[step3_cache_hit] video_id={video_id} clips_path={_clips_path(video_id)}"
        ),
        "stderr_tail": "",
        "error_message": "",
    }


def _run_streaming_command(step: Step, prefix: str = "") -> Step:
    started_at = datetime.utcnow().isoformat()
    started_perf = time.perf_counter()
    env = os.environ.copy()
    env.update(step.get("env") or {})
    stdout_lines: list[str] = []
    stderr_text = ""
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            step["command"],
            cwd=str(config.BACKEND_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            text = line.rstrip()
            stdout_lines.append(text)
            print(f"{prefix}{text}", flush=True)
        stderr_text = process.stderr.read() if process.stderr is not None else ""
        returncode = process.wait(timeout=7200)
    except Exception as exc:
        if process and process.poll() is None:
            process.kill()
        return {
            **_base_step(step, started_at, started_perf),
            "status": "error",
            "returncode": None,
            "stdout_tail": _tail("\n".join(stdout_lines)),
            "stderr_tail": _tail(stderr_text),
            "error_message": str(exc),
        }
    status = "ok" if returncode == 0 else "error"
    error_source = stderr_text or "\n".join(stdout_lines)
    return {
        **_base_step(step, started_at, started_perf),
        "status": status,
        "returncode": returncode,
        "stdout_tail": _tail("\n".join(stdout_lines)),
        "stderr_tail": _tail(stderr_text),
        "error_message": "" if status == "ok" else f"returncode={returncode}: {_tail(error_source, 800)}",
    }


def _pending_reviewable_count() -> int:
    return len(
        filter_candidate_clips(
            load_candidate_queue(),
            status="pending",
            include_missing_previews=False,
        )
    )


def _should_release_fast_mode(
    pending_reviewable: int,
    min_reviewable_to_release: int,
    started_perf: float,
    max_seconds_before_partial_release: int,
) -> bool:
    if pending_reviewable >= max(1, min_reviewable_to_release):
        return True
    elapsed = time.perf_counter() - started_perf
    return pending_reviewable > 0 and elapsed >= max(1, max_seconds_before_partial_release)


def _should_early_exit_fast_mode(
    summary: dict[str, int],
    pending_reviewable: int,
    started_perf: float,
    args: argparse.Namespace,
) -> tuple[bool, str]:
    preview_ready = int(summary.get("preview_ready") or 0)
    elapsed = time.perf_counter() - started_perf
    preview_cap = _preview_cap(args)
    has_reviewable = pending_reviewable > 0
    if preview_cap is not None and preview_ready >= max(1, preview_cap) and has_reviewable:
        return True, "max_previews_reached"
    if preview_ready >= 5 and has_reviewable:
        return True, "preview_ready_threshold"
    if pending_reviewable >= max(1, args.min_reviewable_to_release):
        return True, "pending_reviewable_threshold"
    if elapsed >= max(1, args.max_seconds_before_partial_release) and preview_ready >= 1 and has_reviewable:
        return True, "time_threshold_with_preview"
    return False, ""


def _early_exit_warning(reason: str) -> str:
    return (
        "Busca rápida encerrada cedo porque já havia cortes prontos para avaliar."
        if reason
        else ""
    )


def _next_action_for_pending(summary: dict[str, int], pending_reviewable: int) -> str:
    if pending_reviewable > 0:
        return "open_candidate_clips"
    return _next_action(summary)


def _command(
    module: str,
    video_id: str | None = None,
    include_diagnostics: bool = False,
    overwrite: bool = False,
    only_missing: bool = False,
    download_missing: bool = False,
    no_candidate_limit: bool = False,
    render_all_good_candidates: bool = False,
    max_missing: int | None = None,
    max_previews_total: int | None = None,
    max_candidates_per_video: str | None = None,
    min_ranking_score: float | None = None,
    min_source_score: float | None = None,
    min_duration: float | None = None,
    max_duration: float | None = None,
    quality_threshold: float | None = None,
    dedup_overlap: float | None = None,
) -> list[str]:
    command = [sys.executable, "-m", module]
    if video_id:
        command.extend(["--video-id", video_id])
    if include_diagnostics:
        command.append("--include-diagnostics")
    if overwrite:
        command.append("--overwrite")
    if only_missing:
        command.append("--only-missing")
    if download_missing:
        command.append("--download-missing")
    if no_candidate_limit:
        command.append("--no-candidate-limit")
    if render_all_good_candidates:
        command.append("--render-all-good-candidates")
    if max_missing is not None:
        command.extend(["--max-missing", str(max(0, max_missing))])
    if max_previews_total is not None:
        command.extend(["--max-previews-total", str(max(0, max_previews_total))])
    if max_candidates_per_video:
        command.extend(["--max-candidates-per-video", str(max_candidates_per_video)])
    if min_ranking_score is not None:
        command.extend(["--min-ranking-score", str(min_ranking_score)])
    if min_source_score is not None:
        command.extend(["--min-source-score", str(min_source_score)])
    if min_duration is not None:
        command.extend(["--min-duration", str(min_duration)])
    if max_duration is not None:
        command.extend(["--max-duration", str(max_duration)])
    if quality_threshold is not None:
        command.extend(["--quality-threshold", str(quality_threshold)])
    if dedup_overlap is not None:
        command.extend(["--dedup-overlap", str(dedup_overlap)])
    return command


def _preview_cap(args: argparse.Namespace) -> int | None:
    if args.render_all_good_candidates:
        return args.max_previews_total
    if args.max_previews_initial is not None:
        return args.max_previews_initial
    return args.max_previews


def _run_step(step: Step) -> Step:
    started_at = datetime.utcnow().isoformat()
    started_perf = time.perf_counter()
    env = os.environ.copy()
    env.update(step.get("env") or {})
    try:
        completed = subprocess.run(
            step["command"],
            cwd=str(config.BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200,
            check=False,
        )
    except Exception as exc:
        return {
            **_base_step(step, started_at, started_perf),
            "status": "error",
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "error_message": str(exc),
        }
    status = "ok" if completed.returncode == 0 else "error"
    return {
        **_base_step(step, started_at, started_perf),
        "status": status,
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "error_message": "" if status == "ok" else f"returncode={completed.returncode}: {_tail(completed.stderr or completed.stdout, 800)}",
    }


def _dry_run_step(step: Step) -> Step:
    started_at = datetime.utcnow().isoformat()
    return {
        "name": step["name"],
        "command": _command_for_display(step["command"]),
        "status": "dry_run",
        "returncode": None,
        "started_at": started_at,
        "finished_at": started_at,
        "elapsed_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
        "error_message": "pipeline dry-run: command not executed",
    }


def _skipped_step(step: Step, reason: str) -> Step:
    timestamp = datetime.utcnow().isoformat()
    return {
        "name": step["name"],
        "command": _command_for_display(step["command"]),
        "status": "skipped",
        "returncode": None,
        "started_at": timestamp,
        "finished_at": timestamp,
        "elapsed_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
        "error_message": reason or "skipped_by_fast_search_early_exit",
    }


def _base_step(step: Step, started_at: str, started_perf: float) -> dict[str, Any]:
    return {
        "name": step["name"],
        "command": _command_for_display(step["command"]),
        "started_at": started_at,
        "finished_at": datetime.utcnow().isoformat(),
        "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
    }


def _processed_video_ids_since(started_timestamp: float) -> list[str]:
    ids: list[str] = []
    for path in sorted(config.STORAGE_CLIPS_DIR.glob("*_clips.json")):
        try:
            if path.stat().st_mtime < started_timestamp:
                continue
        except OSError:
            continue
        ids.append(path.name.replace("_clips.json", ""))
    return list(dict.fromkeys(ids))


def _has_recent_or_existing_clips(limit: int | None, started_timestamp: float) -> bool:
    return bool(_processed_video_ids_since(started_timestamp) or _recent_clip_video_ids(limit))


def _recent_clip_video_ids(limit: int | None) -> list[str]:
    if limit is not None and limit <= 0:
        return []
    paths = sorted(
        config.STORAGE_CLIPS_DIR.glob("*_clips.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    ids = [path.name.replace("_clips.json", "") for path in paths]
    if limit is not None:
        ids = ids[:limit]
    return list(dict.fromkeys(ids))


def _candidate_summary() -> dict[str, int]:
    candidates = load_candidate_queue()
    return {
        "total_candidates": len(candidates),
        "preview_ready": sum(1 for item in candidates if item.get("preview_exists")),
        "missing_preview": sum(1 for item in candidates if not item.get("preview_exists")),
        "pending": sum(1 for item in candidates if not item.get("already_reviewed")),
    }


def _cache_metrics_from_results(results: list[Step], export_video_ids: list[str]) -> dict[str, Any]:
    text = "\n".join(
        "\n".join([str(item.get("stdout_tail") or ""), str(item.get("stderr_tail") or "")])
        for item in results
    )
    hits = len(re.findall(r"\[cache_hit\]", text))
    misses = len(re.findall(r"\[cache_miss\]", text))
    partials = len(re.findall(r"\[cache_partial\]", text))
    bypassed = len(re.findall(r"\[cache_bypass\]", text))
    processed_from_scratch = len(
        {
            match.group(1)
            for match in re.finditer(r"\[step3_process_start\]\s+video_id=([^\s]+)", text)
        }
    )
    reused_ids = {
        match.group(1)
        for match in re.finditer(r"\[step3_cache_hit\]\s+video_id=([^\s]+)", text)
    }
    if not reused_ids:
        reused_ids = {
            video_id
            for video_id in export_video_ids
            if video_id and has_valid_clips(video_id)
        }
    estimated_saved = len(reused_ids) * 240
    return {
        "cache_enabled": True,
        "cache_hits": hits,
        "cache_misses": misses,
        "cache_partials": partials,
        "cache_bypassed": bypassed,
        "videos_reused_from_cache": len(reused_ids),
        "videos_processed_from_scratch": processed_from_scratch,
        "estimated_seconds_saved": estimated_saved if estimated_saved else None,
    }


def _candidate_queue_payload() -> dict[str, Any]:
    try:
        with QUEUE_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _next_action(summary: dict[str, int]) -> str:
    if summary["total_candidates"] > 0 and summary["preview_ready"] > 0 and summary["pending"] > 0:
        return "open_candidate_clips"
    if summary["total_candidates"] > 0 and summary["missing_preview"] > 0:
        return "render_candidate_previews"
    if summary["total_candidates"] > 0:
        return "view_reviewed_candidates"
    return "run_analysis_again"


def _selected_videos_count(results: list[Step]) -> int:
    for step in results:
        if step.get("name") != "review_selected_videos":
            continue
        match = re.search(r"Candidatos processáveis:\s*(\d+)", step.get("stdout_tail", ""))
        if match:
            return int(match.group(1))
    return 0


def _finish_pipeline(
    args: argparse.Namespace,
    started_at: str,
    started_perf: float,
    process_started_perf: float,
    results: list[Step],
    export_video_ids: list[str],
    fast_mode: bool,
    partial_reviewable: bool,
    partial_release_at: str | None,
    early_exit: bool = False,
    warning_message: str = "",
) -> None:
    finished_at = datetime.utcnow().isoformat()
    summary = _candidate_summary()
    queue_payload = _candidate_queue_payload()
    pending_reviewable = _pending_reviewable_count()
    cache_metrics = _cache_metrics_from_results(results, export_video_ids)
    steps_failed = sum(1 for item in results if item["status"] == "error")
    has_ready_candidates = summary["total_candidates"] > 0 and summary["preview_ready"] > 0
    pipeline_status = "success"
    if steps_failed > 0:
        pipeline_status = "success_with_warnings" if has_ready_candidates else "failed"
    elif fast_mode and early_exit:
        pipeline_status = "success_with_warnings"
    payload = {
        "status": pipeline_status,
        "warning_message": warning_message,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
        "dry_run": args.dry_run,
        "continue_on_error": args.continue_on_error,
        "fast_mode": fast_mode,
        "early_exit": early_exit,
        "partial_reviewable": partial_reviewable or pending_reviewable > 0,
        "partial_release_at": partial_release_at,
        "partial_candidate_count": summary["total_candidates"],
        "partial_preview_ready": summary["preview_ready"],
        "partial_pending_reviewable_count": pending_reviewable,
        "current_video_id": "",
        "current_video_index": None,
        "total_videos": args.max_videos,
        "current_step_detail": "finished",
        "max_videos": args.max_videos,
        "max_previews": args.max_previews,
        "max_previews_initial": args.max_previews_initial,
        "max_previews_total": args.max_previews_total,
        "render_all_good_candidates": args.render_all_good_candidates,
        "no_candidate_limit": args.no_candidate_limit,
        "max_candidates_per_video": args.max_candidates_per_video,
        "min_ranking_score": args.min_ranking_score,
        "min_source_score": args.min_source_score,
        "min_duration": args.min_duration,
        "max_duration": args.max_duration,
        "quality_threshold": args.quality_threshold,
        "dedup_overlap": args.dedup_overlap,
        "candidates_raw": queue_payload.get("candidates_raw"),
        "candidates_after_quality_filter": queue_payload.get("candidates_after_quality_filter"),
        "candidates_after_dedup": queue_payload.get("candidates_after_dedup"),
        "duplicates_removed": queue_payload.get("duplicates_removed"),
        "duplicate_candidates_detected": queue_payload.get("duplicate_candidate_ids_removed"),
        "duplicates_removed_from_cache": queue_payload.get("duplicates_removed_from_cache"),
        "duplicates_removed_from_new_processing": queue_payload.get("duplicates_removed_from_new_processing"),
        "candidates_dropped_by_quality": queue_payload.get("candidates_dropped_by_quality"),
        "candidates_dropped_by_dedupe": queue_payload.get("candidates_dropped_by_dedupe"),
        "candidates_dropped_by_limit": queue_payload.get("candidates_dropped_by_limit"),
        "candidate_stats_by_video": queue_payload.get("stats_by_video", []),
        **cache_metrics,
        "steps_total": len(results),
        "steps_ok": sum(1 for item in results if item["status"] == "ok"),
        "steps_skipped": sum(1 for item in results if item["status"] == "dry_run"),
        "steps_failed": steps_failed,
        "selected_videos_count": _selected_videos_count(results),
        "processed_videos_count": len(export_video_ids) or len(_processed_video_ids_since(process_started_perf)),
        "export_video_ids": export_video_ids,
        "candidate_count": summary["total_candidates"],
        "preview_ready": summary["preview_ready"],
        "missing_preview": summary["missing_preview"],
        "candidate_pending_reviews": summary["pending"],
        "pending_reviewable_count": pending_reviewable,
        "next_action": "open_candidate_clips" if pending_reviewable > 0 else _next_action(summary),
        "steps": results,
    }
    report_paths = _write_report(payload)
    print(
        "[partial_status] "
        f"partial_reviewable={str(payload['partial_reviewable']).lower()} "
        f"partial_candidate_count={payload['partial_candidate_count']} "
        f"partial_preview_ready={payload['partial_preview_ready']} "
        f"partial_pending_reviewable_count={payload['partial_pending_reviewable_count']} "
        "current_step_detail=finished",
        flush=True,
    )
    print("PIPELINE FIND CANDIDATES SUMMARY")
    print(f"steps_ok: {payload['steps_ok']}")
    print(f"steps_failed: {payload['steps_failed']}")
    print(f"selected_videos_count: {payload['selected_videos_count']}")
    print(f"processed_videos_count: {payload['processed_videos_count']}")
    print(f"candidate_count: {payload['candidate_count']}")
    print(f"preview_ready: {payload['preview_ready']}")
    print(f"missing_preview: {payload['missing_preview']}")
    print(f"candidate_pending_reviews: {payload['candidate_pending_reviews']}")
    print(f"pending_reviewable_count: {payload['pending_reviewable_count']}")
    print(f"cache_hits: {payload['cache_hits']}")
    print(f"cache_misses: {payload['cache_misses']}")
    print(f"cache_partials: {payload['cache_partials']}")
    print(f"cache_bypassed: {payload['cache_bypassed']}")
    print(f"videos_reused_from_cache: {payload['videos_reused_from_cache']}")
    print(f"videos_processed_from_scratch: {payload['videos_processed_from_scratch']}")
    print(f"status: {pipeline_status}")
    if warning_message:
        print(f"warning_message: {warning_message}")
    print(f"next_action: {payload['next_action']}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")
    if pipeline_status == "failed" and not args.continue_on_error:
        raise SystemExit(1)


def _write_report(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"pipeline_find_candidates_{timestamp}.json"
    md_path = reports_dir / f"pipeline_find_candidates_{timestamp}.md"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    md_path.write_text(_markdown_report(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Pipeline Find Candidates",
        "",
        f"Started at: {payload['started_at']}",
        f"Finished at: {payload['finished_at']}",
        f"Elapsed seconds: {payload['elapsed_seconds']}",
        f"Steps OK: {payload['steps_ok']}",
        f"Steps failed: {payload['steps_failed']}",
        f"Status: {payload['status']}",
        f"Warning: {payload.get('warning_message', '')}",
        f"Fast mode: {payload.get('fast_mode', False)}",
        f"Early exit: {payload.get('early_exit', False)}",
        f"Partial reviewable: {payload.get('partial_reviewable', False)}",
        f"Partial candidates: {payload.get('partial_candidate_count')}",
        f"Partial preview ready: {payload.get('partial_preview_ready')}",
        f"Partial pending reviewable: {payload.get('partial_pending_reviewable_count')}",
        f"Candidates: {payload['candidate_count']}",
        f"Candidates raw: {payload.get('candidates_raw')}",
        f"After quality filter: {payload.get('candidates_after_quality_filter')}",
        f"After dedupe: {payload.get('candidates_after_dedup')}",
        f"Duplicates removed: {payload.get('duplicates_removed')}",
        f"Duplicate candidates detected: {payload.get('duplicate_candidates_detected')}",
        f"Duplicates removed from cache: {payload.get('duplicates_removed_from_cache')}",
        f"Duplicates removed from new processing: {payload.get('duplicates_removed_from_new_processing')}",
        f"Dropped by quality: {payload.get('candidates_dropped_by_quality')}",
        f"Dropped by dedupe: {payload.get('candidates_dropped_by_dedupe')}",
        f"Dropped by limit: {payload.get('candidates_dropped_by_limit')}",
        f"Preview ready: {payload['preview_ready']}",
        f"Pending reviews: {payload['candidate_pending_reviews']}",
        f"Next action: {payload['next_action']}",
        f"Cache enabled: {payload.get('cache_enabled')}",
        f"Cache hits: {payload.get('cache_hits')}",
        f"Cache misses: {payload.get('cache_misses')}",
        f"Cache partials: {payload.get('cache_partials')}",
        f"Cache bypassed: {payload.get('cache_bypassed')}",
        f"Videos reused from cache: {payload.get('videos_reused_from_cache')}",
        f"Videos processed from scratch: {payload.get('videos_processed_from_scratch')}",
        f"Estimated seconds saved: {payload.get('estimated_seconds_saved')}",
        "",
    ]
    for index, step in enumerate(payload["steps"], start=1):
        lines.extend(
            [
                f"## {index}. {step['name']} - {step['status']}",
                "",
                f"Command: `{step['command']}`",
                f"Return code: {step.get('returncode')}",
                f"Elapsed: {step['elapsed_seconds']}s",
                f"Error: {step['error_message']}",
                "",
                "Stdout tail:",
                "",
                "```text",
                step.get("stdout_tail", ""),
                "```",
                "",
                "Stderr tail:",
                "",
                "```text",
                step.get("stderr_tail", ""),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _tail(value: str | None, limit: int = 4000) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _single_line(value: object, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _command_for_display(command: list[str]) -> str:
    return " ".join(str(arg) for arg in command)


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
