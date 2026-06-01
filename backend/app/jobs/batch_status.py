from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from app import config
from app.services.candidate_review_service import load_candidate_queue
from app.services.final_clips_service import load_final_clips


FAILED_DOWNLOADS_PATH = config.STORAGE_TRENDS_DIR.parent / "reports" / "failed_candidate_downloads.json"


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--video-id")
    args = parser.parse_args()

    payload = build_status(video_id=args.video_id)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return
    _print_status(payload)


def build_status(video_id: str | None = None) -> dict[str, Any]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    candidates = load_candidate_queue()
    if video_id:
        candidates = [
            candidate
            for candidate in candidates
            if str(candidate.get("video_id") or "") == video_id
        ]
    candidate_reviews = [
        candidate.get("current_candidate_review")
        for candidate in candidates
        if isinstance(candidate.get("current_candidate_review"), dict)
    ]
    candidate_status_counts = Counter(str(review.get("status") or "") for review in candidate_reviews)
    final_clips = load_final_clips(include_duration=False)
    if video_id:
        final_clips = [
            clip for clip in final_clips if str(clip.get("video_id") or "") == video_id
        ]
    final_reviews = [
        clip.get("current_final_review")
        for clip in final_clips
        if isinstance(clip.get("current_final_review"), dict)
    ]
    final_status_counts = Counter(str(review.get("status") or "") for review in final_reviews)
    failed_downloads = _load_failed_downloads()
    if video_id:
        failed_downloads = [
            failure for failure in failed_downloads if str(failure.get("video_id") or "") == video_id
        ]

    approved_plan = _latest_report_payload("approved_clips_plan_*.json")
    latest_package = _latest_posting_package()
    recent_reports = _recent_reports(
        [
            "candidate_preview_render_report_*.json",
            "approved_clips_plan_*.json",
            "render_report_*.json",
            "vertical_render_report_*.json",
            "final_render_report_*.json",
            "final_clips_metadata_*.json",
            "ready_to_post_package_*.json",
            "pipeline_ready_to_post_*.json",
        ]
    )

    return {
        "video_id": video_id,
        "candidate_queue": {
            "total_candidates": len(candidates),
            "preview_ready": sum(1 for item in candidates if item.get("preview_exists")),
            "missing_preview": sum(1 for item in candidates if not item.get("preview_exists")),
            "reviews_pending": sum(1 for item in candidates if not item.get("already_reviewed")),
            "approved": candidate_status_counts.get("approved", 0),
            "rejected": candidate_status_counts.get("rejected", 0),
            "needs_adjustment": candidate_status_counts.get("needs_adjustment", 0),
        },
        "approved_clips_plan": approved_plan,
        "exports": {
            "horizontal_exports": _count_mp4(config.STORAGE_EXPORTS_DIR, video_id),
            "vertical_exports": _count_mp4(config.STORAGE_VERTICAL_EXPORTS_DIR, video_id),
            "final_exports": _count_mp4(config.STORAGE_FINAL_EXPORTS_DIR, video_id),
        },
        "final_reviews": {
            "pending": max(0, len(final_clips) - len(final_reviews)),
            "ready_to_post": final_status_counts.get("ready_to_post", 0),
            "do_not_post": final_status_counts.get("do_not_post", 0),
            "needs_edit": final_status_counts.get("needs_edit", 0),
        },
        "posting_package": latest_package,
        "recent_reports": recent_reports,
        "failed_downloads": {
            "count": len(failed_downloads),
            "path": str(FAILED_DOWNLOADS_PATH),
            "items": failed_downloads[:20],
        },
        "reports_dir": str(reports_dir),
    }


def _latest_report_payload(pattern: str) -> dict[str, Any]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    paths = sorted(reports_dir.glob(pattern))
    if not paths:
        return {"path": None, "item_count": 0}
    path = paths[-1]
    payload = _load_json(path)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    return {
        "path": str(path),
        "item_count": len(items),
        "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
        "exported_at": payload.get("exported_at") if isinstance(payload, dict) else None,
    }


def _latest_posting_package() -> dict[str, Any]:
    root = config.STORAGE_POSTING_PACKAGE_DIR
    if not root.exists():
        return {"path": None}
    dirs = [path for path in root.iterdir() if path.is_dir()]
    if not dirs:
        return {"path": None}
    latest = max(dirs, key=lambda path: path.stat().st_mtime)
    payload = _load_json(latest / "posting_package.json")
    return {
        "path": str(latest),
        "package_id": payload.get("package_id") if isinstance(payload, dict) else latest.name,
        "total_ready_to_post": payload.get("total_ready_to_post") if isinstance(payload, dict) else None,
        "copied_count": payload.get("copied_count") if isinstance(payload, dict) else None,
    }


def _recent_reports(patterns: list[str]) -> list[dict[str, Any]]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports: list[Path] = []
    for pattern in patterns:
        reports.extend(reports_dir.glob(pattern))
    latest = sorted(set(reports), key=lambda path: path.stat().st_mtime, reverse=True)[:10]
    return [{"path": str(path), "modified_at": path.stat().st_mtime} for path in latest]


def _count_mp4(directory: Path, video_id: str | None) -> int:
    if not directory.exists():
        return 0
    paths = directory.glob("*.mp4")
    if video_id:
        paths = (path for path in paths if video_id in path.name)
    return sum(1 for _ in paths)


def _load_failed_downloads() -> list[dict[str, Any]]:
    payload = _load_json(FAILED_DOWNLOADS_PATH)
    return payload if isinstance(payload, list) else []


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _print_status(payload: dict[str, Any]) -> None:
    candidate = payload["candidate_queue"]
    exports = payload["exports"]
    final_reviews = payload["final_reviews"]
    print("BATCH STATUS")
    if payload.get("video_id"):
        print(f"video_id: {payload['video_id']}")
    print("")
    print("Candidate queue:")
    print(f"- total candidates: {candidate['total_candidates']}")
    print(f"- previews prontos: {candidate['preview_ready']}")
    print(f"- previews faltantes: {candidate['missing_preview']}")
    print(f"- reviews pendentes: {candidate['reviews_pending']}")
    print(f"- approved: {candidate['approved']}")
    print(f"- rejected: {candidate['rejected']}")
    print(f"- needs_adjustment: {candidate['needs_adjustment']}")
    print("")
    print("Approved clips plan:")
    print(f"- latest: {payload['approved_clips_plan']['path']}")
    print(f"- items: {payload['approved_clips_plan']['item_count']}")
    print("")
    print("Exports:")
    print(f"- horizontal: {exports['horizontal_exports']}")
    print(f"- vertical: {exports['vertical_exports']}")
    print(f"- final: {exports['final_exports']}")
    print("")
    print("Final reviews:")
    print(f"- pending: {final_reviews['pending']}")
    print(f"- ready_to_post: {final_reviews['ready_to_post']}")
    print(f"- do_not_post: {final_reviews['do_not_post']}")
    print(f"- needs_edit: {final_reviews['needs_edit']}")
    print("")
    print("Posting package:")
    print(f"- latest: {payload['posting_package']['path']}")
    print(f"- total_ready_to_post: {payload['posting_package']['total_ready_to_post']}")
    print("")
    print("Failed candidate downloads:")
    print(f"- count: {payload['failed_downloads']['count']}")
    print(f"- path: {payload['failed_downloads']['path']}")
    print("")
    print("Recent reports:")
    for report in payload["recent_reports"]:
        print(f"- {report['path']}")


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
