from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from typing import Any

from app import config
from app.services.cache_manifest_service import cache_integrity_summary, rebuild_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit ClipRadar cache integrity.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    manifest = rebuild_manifest()
    entries = list((manifest.get("videos") or {}).values())
    statuses = Counter(str(entry.get("cache_status") or "empty") for entry in entries)
    integrity = cache_integrity_summary(manifest=manifest)
    payload: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat(),
        "manifest_path": str(config.STORAGE_TRENDS_DIR.parent / "cache" / "cache_manifest.json"),
        "videos_checked": len(entries),
        "manifest_entries": len(entries),
        "valid_entries": statuses.get("ready", 0) + statuses.get("partial", 0),
        "ready": statuses.get("ready", 0),
        "partial": statuses.get("partial", 0),
        "invalid": statuses.get("invalid", 0),
        "stale": integrity["stale_count"],
        "missing_files": integrity["missing_files_count"],
        "invalid_json": integrity["invalid_json_count"],
        "orphan_previews": integrity["orphan_previews"],
        "orphan_finals": integrity["orphan_finals"],
        "orphan_posts": integrity["orphan_posts"],
        "duplicate_candidates": integrity["duplicate_candidates"],
        "duplicate_posts": integrity["duplicate_posts"],
        "approved_missing_finals": integrity["approved_missing_finals"],
        "posts_missing_files": integrity["posts_missing_files"],
        "details": integrity,
    }
    paths = _write_report(payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("CACHE INTEGRITY")
    for key in (
        "videos_checked",
        "ready",
        "partial",
        "invalid",
        "stale",
        "missing_files",
        "invalid_json",
        "orphan_previews",
        "orphan_finals",
        "orphan_posts",
        "duplicate_candidates",
        "duplicate_posts",
        "approved_missing_finals",
        "posts_missing_files",
    ):
        print(f"{key}: {payload[key]}")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['md']}")


def _write_report(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"cache_integrity_{stamp}.json"
    md_path = reports_dir / f"cache_integrity_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cache Integrity",
        "",
        f"Generated at: {payload.get('generated_at')}",
        f"Videos checked: {payload.get('videos_checked')}",
        f"Ready: {payload.get('ready')}",
        f"Partial: {payload.get('partial')}",
        f"Invalid: {payload.get('invalid')}",
        f"Stale: {payload.get('stale')}",
        f"Missing files: {payload.get('missing_files')}",
        f"Invalid JSON: {payload.get('invalid_json')}",
        f"Duplicate candidates: {payload.get('duplicate_candidates')}",
        f"Duplicate posts: {payload.get('duplicate_posts')}",
        f"Approved missing finals: {payload.get('approved_missing_finals')}",
        f"Orphan previews: {payload.get('orphan_previews')}",
        f"Orphan finals: {payload.get('orphan_finals')}",
        f"Orphan posts: {payload.get('orphan_posts')}",
        "",
    ]
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    for title, key in (
        ("Duplicate Candidate IDs", "duplicate_candidate_ids"),
        ("Approved Missing Final Candidate IDs", "approved_missing_final_candidate_ids"),
        ("Orphan Preview Files", "orphan_preview_files"),
        ("Orphan Final Files", "orphan_final_files"),
        ("Orphan Post IDs", "orphan_post_ids"),
    ):
        values = details.get(key) if isinstance(details.get(key), list) else []
        if not values:
            continue
        lines.extend([f"## {title}", ""])
        lines.extend(f"* {value}" for value in values[:50])
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
