from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

from app import config
from app.services.cache_manifest_service import rebuild_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-test ClipRadar cache reuse without heavy processing.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--only-ready", action="store_true")
    parser.add_argument("--include-partial", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute anything heavy. This job is dry by design.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = rebuild_manifest()
    entries = _select_entries(list((manifest.get("videos") or {}).values()), args)
    payload = _build_payload(entries)
    paths = _write_report(payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("CACHE REUSE TEST")
    print(f"dry_run: {bool(args.dry_run)}")
    for key in (
        "tested",
        "ready_tested",
        "partial_tested",
        "cache_hits",
        "cache_misses",
        "would_run_whisper",
        "would_render_previews",
        "estimated_seconds_saved",
    ):
        print(f"{key}: {payload[key]}")
    if payload["would_run_whisper"]:
        print("warning: some selected entries would need transcript generation if processed for real")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['md']}")


def _select_entries(entries: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    allowed = {"ready"} if args.only_ready else {"ready", "partial"} if args.include_partial else {"ready", "partial", "invalid"}
    selected = [entry for entry in entries if str(entry.get("cache_status") or "empty") in allowed]
    selected.sort(key=lambda item: (str(item.get("cache_status") or ""), str(item.get("video_id") or "")))
    if args.limit and args.limit > 0:
        return selected[: args.limit]
    return selected


def _build_payload(entries: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    cache_hits = 0
    cache_misses = 0
    would_run_whisper = 0
    would_render_previews = 0
    for entry in entries:
        transcript_ok = bool(entry.get("transcript_exists"))
        clips_ok = bool(entry.get("clips_exists"))
        previews_ok = int(entry.get("previews_ready_count") or 0) > 0
        reusable = transcript_ok and clips_ok
        if reusable:
            cache_hits += 1
        else:
            cache_misses += 1
        if not transcript_ok:
            would_run_whisper += 1
        if not previews_ok:
            would_render_previews += 1
        items.append(
            {
                "video_id": entry.get("video_id"),
                "cache_status": entry.get("cache_status"),
                "transcript_exists": transcript_ok,
                "clips_exists": clips_ok,
                "previews_ready_count": int(entry.get("previews_ready_count") or 0),
                "reusable_without_whisper": reusable,
                "would_run_whisper": not transcript_ok,
                "would_render_previews": not previews_ok,
            }
        )
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "tested": len(entries),
        "ready_tested": sum(1 for entry in entries if str(entry.get("cache_status") or "") == "ready"),
        "partial_tested": sum(1 for entry in entries if str(entry.get("cache_status") or "") == "partial"),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "would_run_whisper": would_run_whisper,
        "would_render_previews": would_render_previews,
        "estimated_seconds_saved": cache_hits * 240,
        "items": items,
    }


def _write_report(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"cache_reuse_test_{stamp}.json"
    md_path = reports_dir / f"cache_reuse_test_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cache Reuse Test",
        "",
        f"Tested: {payload.get('tested')}",
        f"Cache hits: {payload.get('cache_hits')}",
        f"Cache misses: {payload.get('cache_misses')}",
        f"Would run Whisper: {payload.get('would_run_whisper')}",
        f"Would render previews: {payload.get('would_render_previews')}",
        f"Estimated seconds saved: {payload.get('estimated_seconds_saved')}",
        "",
    ]
    for item in payload.get("items", []):
        lines.append(
            f"* {item.get('video_id')} | {item.get('cache_status')} | "
            f"transcript={item.get('transcript_exists')} clips={item.get('clips_exists')} "
            f"previews={item.get('previews_ready_count')}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
