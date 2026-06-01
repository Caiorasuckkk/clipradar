from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


Step = dict[str, Any]


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--video-id")
    parser.add_argument("--download-missing", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--skip-approved-plan", action="store_true")
    parser.add_argument("--skip-render-approved", action="store_true")
    parser.add_argument("--skip-vertical", action="store_true")
    parser.add_argument("--skip-final", action="store_true")
    parser.add_argument("--skip-final-metadata", action="store_true")
    parser.add_argument("--skip-posting-package", action="store_true")
    parser.add_argument("--package-name")
    args = parser.parse_args()

    started_at = datetime.utcnow().isoformat()
    started_perf = time.perf_counter()
    steps = _build_steps(args)
    results: list[Step] = []

    print("PIPELINE READY TO POST")
    print("")

    for index, step in enumerate(steps, start=1):
        label = step["label"]
        print(f"Step {index}/{len(steps)}: {label}")
        if step["skip"]:
            result = _skipped_step(step)
            results.append(result)
            print("Status: SKIPPED")
            print("")
            continue
        if args.dry_run:
            result = _dry_run_step(step)
            results.append(result)
            print(f"Command: {_command_for_display(step['command'])}")
            print("Status: DRY_RUN")
            print("")
            continue

        result = _run_step(step)
        results.append(result)
        print(f"Status: {result['status'].upper()}")
        if result.get("error_message"):
            print(result["error_message"])
        print("")
        if result["status"] == "ok":
            _wire_single_clip_outputs(args, step, steps)
        if result["status"] == "error" and not args.continue_on_error:
            break

    finished_at = datetime.utcnow().isoformat()
    payload = {
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": round(time.perf_counter() - started_perf, 2),
        "dry_run": args.dry_run,
        "continue_on_error": args.continue_on_error,
        "steps_total": len(results),
        "steps_ok": sum(1 for item in results if item["status"] == "ok"),
        "steps_skipped": sum(1 for item in results if item["status"] in {"skipped", "dry_run"}),
        "steps_failed": sum(1 for item in results if item["status"] == "error"),
        "steps": results,
    }
    report_paths = _write_report(payload)

    print("PIPELINE SUMMARY")
    print(f"steps_total: {payload['steps_total']}")
    print(f"steps_ok: {payload['steps_ok']}")
    print(f"steps_skipped: {payload['steps_skipped']}")
    print(f"steps_failed: {payload['steps_failed']}")
    print(f"started_at: {started_at}")
    print(f"finished_at: {finished_at}")
    print(f"elapsed_seconds: {payload['elapsed_seconds']}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")

    if payload["steps_failed"] > 0 and not args.continue_on_error:
        raise SystemExit(1)


def _build_steps(args: argparse.Namespace) -> list[Step]:
    return [
        {
            "name": "export_approved_clips_plan",
            "label": "export approved clips plan",
            "skip": args.skip_approved_plan,
            "command": _command(
                "app.jobs.export_approved_clips_plan",
                limit=args.limit,
                video_id=args.video_id,
            ),
        },
        {
            "name": "render_approved_clips",
            "label": "render approved clips",
            "skip": args.skip_render_approved,
            "command": _command(
                "app.jobs.render_approved_clips",
                limit=args.limit,
                video_id=args.video_id,
                dry_run=False,
                overwrite=args.overwrite,
                download_missing=args.download_missing,
            ),
        },
        {
            "name": "render_vertical_clips",
            "label": "render vertical clips",
            "skip": args.skip_vertical,
            "command": _command(
                "app.jobs.render_vertical_clips",
                limit=args.limit,
                video_id=args.video_id,
                dry_run=False,
                overwrite=args.overwrite,
            ),
        },
        {
            "name": "render_final_clips",
            "label": "render final clips",
            "skip": args.skip_final,
            "command": _command(
                "app.jobs.render_final_clips",
                limit=args.limit,
                video_id=args.video_id,
                dry_run=False,
                overwrite=args.overwrite,
            ),
        },
        {
            "name": "export_final_clips_metadata",
            "label": "export final clips metadata",
            "skip": args.skip_final_metadata,
            "command": _command("app.jobs.export_final_clips_metadata"),
        },
        {
            "name": "export_ready_to_post_package",
            "label": "export ready-to-post package",
            "skip": args.skip_posting_package,
            "command": _command(
                "app.jobs.export_ready_to_post_package",
                limit=args.limit,
                dry_run=False,
                overwrite=args.overwrite,
                package_name=args.package_name,
            ),
        },
    ]


def _command(
    module: str,
    input_path: str | None = None,
    limit: int | None = None,
    video_id: str | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
    download_missing: bool = False,
    package_name: str | None = None,
) -> list[str]:
    command = [sys.executable, "-m", module]
    if input_path:
        command.extend(["--input", input_path])
    if limit is not None:
        command.extend(["--limit", str(limit)])
    if video_id:
        command.extend(["--video-id", video_id])
    if dry_run:
        command.append("--dry-run")
    if overwrite:
        command.append("--overwrite")
    if download_missing:
        command.append("--download-missing")
    if package_name:
        command.extend(["--package-name", package_name])
    return command


def _wire_single_clip_outputs(args: argparse.Namespace, completed_step: Step, steps: list[Step]) -> None:
    if args.limit != 1:
        return
    if completed_step["name"] == "render_approved_clips":
        output_path = _latest_rendered_output("render_report_*.json")
        if output_path:
            _replace_step_command(
                steps,
                "render_vertical_clips",
                _command(
                    "app.jobs.render_vertical_clips",
                    input_path=output_path,
                    overwrite=args.overwrite,
                ),
            )
    elif completed_step["name"] == "render_vertical_clips":
        output_path = _latest_rendered_output("vertical_render_report_*.json")
        if output_path:
            _replace_step_command(
                steps,
                "render_final_clips",
                _command(
                    "app.jobs.render_final_clips",
                    input_path=output_path,
                    overwrite=args.overwrite,
                ),
            )


def _replace_step_command(steps: list[Step], name: str, command: list[str]) -> None:
    for step in steps:
        if step["name"] == name:
            step["command"] = command
            return


def _latest_rendered_output(pattern: str) -> str | None:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    paths = sorted(reports_dir.glob(pattern))
    for path in reversed(paths):
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception:
            continue
        items = payload.get("items", []) if isinstance(payload, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("status") == "rendered" and item.get("output_path"):
                return str(item["output_path"])
    return None


def _run_step(step: Step) -> Step:
    started_at = datetime.utcnow().isoformat()
    started_perf = time.perf_counter()
    try:
        completed = subprocess.run(
            step["command"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,
            check=False,
        )
    except Exception as exc:
        return {
            **_base_step(step, started_at, started_perf),
            "status": "error",
            "stdout_tail": "",
            "stderr_tail": "",
            "error_message": str(exc),
        }
    status = "ok" if completed.returncode == 0 else "error"
    return {
        **_base_step(step, started_at, started_perf),
        "status": status,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "error_message": "" if status == "ok" else f"returncode={completed.returncode}",
    }


def _skipped_step(step: Step) -> Step:
    started_at = datetime.utcnow().isoformat()
    return {
        "name": step["name"],
        "command": _command_for_display(step["command"]),
        "status": "skipped",
        "started_at": started_at,
        "finished_at": started_at,
        "elapsed_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
        "error_message": "step skipped by flag",
    }


def _dry_run_step(step: Step) -> Step:
    started_at = datetime.utcnow().isoformat()
    return {
        "name": step["name"],
        "command": _command_for_display(step["command"]),
        "status": "dry_run",
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


def _write_report(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"pipeline_ready_to_post_{timestamp}.json"
    md_path = reports_dir / f"pipeline_ready_to_post_{timestamp}.md"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    md_path.write_text(_markdown_report(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Pipeline Ready to Post",
        "",
        f"Started at: {payload['started_at']}",
        f"Finished at: {payload['finished_at']}",
        f"Elapsed seconds: {payload['elapsed_seconds']}",
        f"Dry run: {str(payload['dry_run']).lower()}",
        f"Steps OK: {payload['steps_ok']}",
        f"Steps skipped: {payload['steps_skipped']}",
        f"Steps failed: {payload['steps_failed']}",
        "",
        "## Steps",
        "",
    ]
    for index, step in enumerate(payload["steps"], start=1):
        lines.extend(
            [
                f"### {index}. {step['name']} - {step['status']}",
                "",
                f"Command: `{step['command']}`",
                f"Started: {step['started_at']}",
                f"Finished: {step['finished_at']}",
                f"Elapsed: {step['elapsed_seconds']}s",
                f"Error: {step['error_message']}",
                "",
                "Stdout tail:",
                "```text",
                step.get("stdout_tail", ""),
                "```",
                "",
                "Stderr tail:",
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
    return " ".join(_quote_arg(arg) for arg in command)


def _quote_arg(arg: object) -> str:
    text = str(arg)
    if not text or any(char.isspace() for char in text):
        return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
    return text


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
