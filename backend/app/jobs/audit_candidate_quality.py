from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from typing import Any

from app import config
from app.services.candidate_quality_ranker_service import (
    candidate_quality_summary,
    dedupe_candidates,
    load_candidate_quality_rules,
    rank_candidate,
)
from app.services.candidate_review_service import load_candidate_queue


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit candidate clip quality.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rules = load_candidate_quality_rules()
    raw_candidates = load_candidate_queue()
    scored = [{**item, **rank_candidate(item, rules)} for item in raw_candidates]
    deduped, dedupe_stats = dedupe_candidates(scored, overlap_threshold=0.65)
    summary = candidate_quality_summary(scored)
    top_candidates = sorted(scored, key=lambda row: float(row.get("candidate_quality_score") or 0), reverse=True)[:10]
    bottom_candidates = sorted(scored, key=lambda row: float(row.get("candidate_quality_score") or 0))[:10]
    payload: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat(),
        "dry_run": bool(args.dry_run),
        "total_candidates": len(raw_candidates),
        "scored": len(scored),
        "excellent": summary["excellent_count"],
        "good": summary["good_count"],
        "average": summary["average_count"],
        "weak": summary["weak_count"],
        "reject": summary["rejected_count"],
        "hard_rejected": summary["hard_rejected_count"],
        "score_min": summary["score_min"],
        "score_max": summary["score_max"],
        "score_p25": summary["score_p25"],
        "score_p50": summary["score_p50"],
        "score_p75": summary["score_p75"],
        "average_quality_score": summary["average_quality_score"],
        "duplicates_by_text": dedupe_stats.get("duplicates_removed_by_text", 0),
        "duplicates_by_time": dedupe_stats.get("duplicates_removed_by_time", 0),
        "deduped_count": len(deduped),
        "top_candidates": [_compact(item) for item in top_candidates],
        "bottom_candidates": [_compact(item) for item in bottom_candidates],
        "top_positive_signals": summary["top_positive_signals"],
        "top_negative_signals": summary["top_negative_signals"],
        "bottom_negative_signals": summary["bottom_negative_signals"],
        "tier_counts": dict(Counter(str(item.get("quality_tier") or "unknown") for item in scored)),
    }
    paths = _write_report(payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("CANDIDATE QUALITY REPORT")
    for key in (
        "total_candidates",
        "scored",
        "excellent",
        "good",
        "average",
        "weak",
        "reject",
        "hard_rejected",
        "score_min",
        "score_p25",
        "score_p50",
        "score_p75",
        "score_max",
        "average_quality_score",
        "duplicates_by_text",
        "duplicates_by_time",
    ):
        print(f"{key}: {payload[key]}")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['md']}")


def _compact(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": item.get("candidate_id"),
        "video_id": item.get("video_id"),
        "score": item.get("candidate_quality_score"),
        "tier": item.get("quality_tier"),
        "duration_seconds": item.get("duration_seconds"),
        "reject_reason": item.get("candidate_quality_reject_reason"),
        "positive_signals": item.get("positive_signals") or [],
        "negative_signals": item.get("negative_signals") or [],
        "text_preview": str(item.get("text") or "")[:240],
    }


def _write_report(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"candidate_quality_{stamp}.json"
    md_path = reports_dir / f"candidate_quality_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Candidate Quality Report",
        "",
        f"Generated at: {payload.get('generated_at')}",
        f"Total candidates: {payload.get('total_candidates')}",
        f"Scored: {payload.get('scored')}",
        f"Excellent: {payload.get('excellent')}",
        f"Good: {payload.get('good')}",
        f"Average: {payload.get('average')}",
        f"Weak: {payload.get('weak')}",
        f"Reject: {payload.get('reject')}",
        f"Hard rejected: {payload.get('hard_rejected')}",
        f"Score min/p25/p50/p75/max: {payload.get('score_min')} / {payload.get('score_p25')} / {payload.get('score_p50')} / {payload.get('score_p75')} / {payload.get('score_max')}",
        f"Average quality score: {payload.get('average_quality_score')}",
        f"Duplicates by text: {payload.get('duplicates_by_text')}",
        f"Duplicates by time: {payload.get('duplicates_by_time')}",
        "",
        "## Top Candidates",
        "",
    ]
    for item in payload.get("top_candidates", []):
        lines.append(f"* {item.get('score')} {item.get('tier')} | {item.get('candidate_id')} | + {', '.join(item.get('positive_signals') or [])}")
    lines.extend(["", "## Bottom Candidates", ""])
    for item in payload.get("bottom_candidates", []):
        lines.append(f"* {item.get('score')} {item.get('tier')} | {item.get('reject_reason')} | {item.get('candidate_id')}")
    lines.extend(["", "## Top Positive Signals", ""])
    for item in payload.get("top_positive_signals", []):
        lines.append(f"* {item.get('signal')}: {item.get('count')}")
    lines.extend(["", "## Top Negative Signals", ""])
    for item in payload.get("top_negative_signals", []):
        lines.append(f"* {item.get('signal')}: {item.get('count')}")
    lines.extend(["", "## Bottom Negative Signals", ""])
    for item in payload.get("bottom_negative_signals", []):
        lines.append(f"* {item.get('signal')}: {item.get('count')}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
