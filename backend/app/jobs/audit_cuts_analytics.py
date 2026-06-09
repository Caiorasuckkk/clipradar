from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.cuts_analytics_service import build_cuts_analytics


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit DarkFlow cuts analytics.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    payload = build_cuts_analytics()
    report_paths = _write_reports(payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"JSON report: {report_paths['json']}")
        print(f"Markdown report: {report_paths['markdown']}")
        return

    overview = payload["overview"]
    jobs = payload["jobs"]
    latest = jobs.get("latest_search") or {}
    print("CUTS QA + ANALYTICS")
    print(f"candidates: {overview['total_candidates']}")
    print(f"preview ready: {overview['preview_ready']}")
    print(f"pending: {overview['pending']}")
    print(f"reviewed: {overview['reviewed']}")
    print(f"approved: {overview['approved']}")
    print(f"rejected: {overview['rejected']}")
    print(f"needs adjustment: {overview['needs_adjustment']}")
    print(f"approval rate: {_percent(overview['approval_rate'])}")
    print(f"generated posts: {overview['generated_posts_count']}")
    print(f"not posted: {overview['not_posted_count']}")
    print(f"do not post: {overview['do_not_post_count']}")
    print("")
    print("Search jobs:")
    print(f"runs: {jobs['search_runs_count']}")
    print(f"fast: {jobs['fast_search_runs_count']}")
    print(f"deep: {jobs['deep_search_runs_count']}")
    print(f"success with warnings: {jobs['success_with_warnings_count']}")
    if latest:
        print(f"latest: {latest.get('status')} / {latest.get('next_action')}")
    print("")
    print("Top videos:")
    for item in payload["by_video"][:5]:
        print(
            f"* {item.get('video_id')} | approved={item.get('approved_count')} "
            f"reviewed={item.get('reviewed')} rate={_percent(item.get('approval_rate'))}"
        )
    print("")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['markdown']}")


def _write_reports(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"cuts_analytics_{stamp}.json"
    md_path = reports_dir / f"cuts_analytics_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    overview = payload["overview"]
    jobs = payload["jobs"]
    lines = [
        "# Cuts QA + Analytics",
        "",
        "## Overview",
        "",
        f"* candidates: {overview['total_candidates']}",
        f"* preview_ready: {overview['preview_ready']}",
        f"* pending: {overview['pending']}",
        f"* reviewed: {overview['reviewed']}",
        f"* approved: {overview['approved']}",
        f"* rejected: {overview['rejected']}",
        f"* needs_adjustment: {overview['needs_adjustment']}",
        f"* approval_rate: {_percent(overview['approval_rate'])}",
        f"* generated_posts: {overview['generated_posts_count']}",
        "",
        "## Jobs",
        "",
        f"* search_runs: {jobs['search_runs_count']}",
        f"* fast_search_runs: {jobs['fast_search_runs_count']}",
        f"* deep_search_runs: {jobs['deep_search_runs_count']}",
        f"* average_elapsed_seconds: {jobs['average_search_elapsed_seconds']}",
        "",
        "## Top Videos",
        "",
    ]
    for item in payload["by_video"][:10]:
        lines.append(
            f"* {item.get('video_id')} | approved={item.get('approved_count')} "
            f"| reviewed={item.get('reviewed')} | rate={_percent(item.get('approval_rate'))}"
        )
    lines.extend(["", "## Sources", ""])
    for item in payload["by_source"]:
        lines.append(
            f"* {item.get('source')} | approved={item.get('approved_count')} "
            f"| total={item.get('total_candidates')} | rate={_percent(item.get('approval_rate'))}"
        )
    return "\n".join(lines)


def _percent(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "0%"


if __name__ == "__main__":
    main()
