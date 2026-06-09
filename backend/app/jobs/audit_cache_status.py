from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from typing import Any

from app import config
from app.services.cache_manifest_service import rebuild_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit ClipRadar cache status.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = rebuild_manifest()
    entries = list(manifest.get("videos", {}).values())
    statuses = Counter(str(entry.get("cache_status") or "empty") for entry in entries)
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "manifest_path": str(config.STORAGE_TRENDS_DIR.parent / "cache" / "cache_manifest.json"),
        "videos_cached": len(entries),
        "ready": statuses.get("ready", 0),
        "partial": statuses.get("partial", 0),
        "invalid": statuses.get("invalid", 0),
        "empty": statuses.get("empty", 0),
        "transcripts": sum(1 for entry in entries if entry.get("transcript_exists")),
        "clips": sum(1 for entry in entries if entry.get("clips_exists")),
        "previews": sum(1 for entry in entries if int(entry.get("previews_ready_count") or 0) > 0),
        "finals": sum(1 for entry in entries if int(entry.get("finals_count") or 0) > 0),
        "orphan_files": [],
        "stale_entries": [
            entry.get("video_id")
            for entry in entries
            if str(entry.get("cache_status") or "") in {"stale", "invalid"}
        ],
        "items": entries,
    }
    paths = _write_report(payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print("CACHE STATUS")
    print(f"videos_cached: {payload['videos_cached']}")
    print(f"ready: {payload['ready']}")
    print(f"partial: {payload['partial']}")
    print(f"invalid: {payload['invalid']}")
    print(f"transcripts: {payload['transcripts']}")
    print(f"clips: {payload['clips']}")
    print(f"previews: {payload['previews']}")
    print(f"finals: {payload['finals']}")
    print(f"orphan_files: {len(payload['orphan_files'])}")
    print(f"stale_entries: {len(payload['stale_entries'])}")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['md']}")


def _write_report(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"cache_status_{stamp}.json"
    md_path = reports_dir / f"cache_status_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cache Status",
        "",
        f"* videos_cached: {payload['videos_cached']}",
        f"* ready: {payload['ready']}",
        f"* partial: {payload['partial']}",
        f"* invalid: {payload['invalid']}",
        f"* transcripts: {payload['transcripts']}",
        f"* clips: {payload['clips']}",
        f"* previews: {payload['previews']}",
        f"* finals: {payload['finals']}",
        "",
        "## Invalid/Stale",
        "",
    ]
    for video_id in payload.get("stale_entries", [])[:50]:
        lines.append(f"* {video_id}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
