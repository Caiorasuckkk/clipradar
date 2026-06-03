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
from app.services.candidate_review_service import load_candidate_queue


Step = dict[str, Any]


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-videos", type=int, default=3)
    parser.add_argument("--max-previews", type=int, default=10)
    parser.add_argument("--include-diagnostics", action="store_true")
    parser.add_argument("--download-missing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    started_at = datetime.utcnow().isoformat()
    started_perf = time.perf_counter()
    process_started_perf = time.time()
    steps = _build_steps(args)
    results: list[Step] = []

    print("PIPELINE FIND CANDIDATES")
    print("")

    for index, step in enumerate(steps, start=1):
        print(f"Step {index}/{len(steps)}: {step['label']}")
        if args.dry_run:
            result = _dry_run_step(step)
            results.append(result)
            print(f"Command: {_command_for_display(step['command'])}")
            print("Status: DRY_RUN")
            print("")
            continue

        if step["name"] == "export_candidate_review_queue":
            processed_ids = _processed_video_ids_since(process_started_perf)
            if processed_ids:
                step["command"].append(f"--video-id={','.join(processed_ids)}")

        result = _run_step(step)
        results.append(result)
        print(f"Status: {result['status'].upper()}")
        if result.get("error_message"):
            print(result["error_message"])
        print("")
        if result["status"] == "error" and not args.continue_on_error:
            break

    finished_at = datetime.utcnow().isoformat()
    summary = _candidate_summary()
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
        "steps_total": len(results),
        "steps_ok": sum(1 for item in results if item["status"] == "ok"),
        "steps_skipped": sum(1 for item in results if item["status"] == "dry_run"),
        "steps_failed": steps_failed,
        "selected_videos_count": _selected_videos_count(results),
        "processed_videos_count": len(_processed_video_ids_since(process_started_perf)),
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
    print(f"status: {pipeline_status}")
    print(f"next_action: {payload['next_action']}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")

    if pipeline_status == "failed" and not args.continue_on_error:
        raise SystemExit(1)


def _build_steps(args: argparse.Namespace) -> list[Step]:
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
            "env": {"MAX_VIDEOS_PER_RUN": str(max(0, args.max_videos))},
        },
        {
            "name": "export_candidate_review_queue",
            "label": "export candidate queue",
            "command": _command(
                "app.jobs.export_candidate_review_queue",
                include_diagnostics=args.include_diagnostics,
                overwrite=args.overwrite,
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
                max_missing=args.max_previews,
            ),
            "env": {},
        },
    ]


def _command(
    module: str,
    include_diagnostics: bool = False,
    overwrite: bool = False,
    only_missing: bool = False,
    download_missing: bool = False,
    max_missing: int | None = None,
) -> list[str]:
    command = [sys.executable, "-m", module]
    if include_diagnostics:
        command.append("--include-diagnostics")
    if overwrite:
        command.append("--overwrite")
    if only_missing:
        command.append("--only-missing")
    if download_missing:
        command.append("--download-missing")
    if max_missing is not None:
        command.extend(["--max-missing", str(max(0, max_missing))])
    return command


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


def _candidate_summary() -> dict[str, int]:
    candidates = load_candidate_queue()
    return {
        "total_candidates": len(candidates),
        "preview_ready": sum(1 for item in candidates if item.get("preview_exists")),
        "missing_preview": sum(1 for item in candidates if not item.get("preview_exists")),
        "pending": sum(1 for item in candidates if not item.get("already_reviewed")),
    }


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
        f"Candidates: {payload['candidate_count']}",
        f"Preview ready: {payload['preview_ready']}",
        f"Pending reviews: {payload['candidate_pending_reviews']}",
        f"Next action: {payload['next_action']}",
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


def _command_for_display(command: list[str]) -> str:
    return " ".join(str(arg) for arg in command)


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
