from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

from app import config
from app.services.source_intelligence_service import build_source_quality_audit, load_source_rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit ClipRadar source quality.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_source_quality_audit()
    payload["rules_path"] = str(config.STORAGE_TRENDS_DIR.parent / "config" / "source_rules.json")
    payload["rules"] = load_source_rules()
    paths = _write_report(payload)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("SOURCE QUALITY REPORT")
    for key in (
        "total_videos_seen",
        "videos_processed",
        "videos_accepted",
        "videos_rejected",
    ):
        print(f"{key}: {payload.get(key, 0)}")
    print(f"best_channels: {len(payload.get('best_channels') or [])}")
    print(f"worst_channels: {len(payload.get('worst_channels') or [])}")
    print(f"best_queries: {len(payload.get('best_queries') or [])}")
    print(f"repeated_videos: {len(payload.get('repeated_videos') or [])}")
    print(f"recently_reprocessed_videos: {len(payload.get('recently_reprocessed_videos') or [])}")
    print(f"blocked_keyword_hits: {payload.get('blocked_keyword_hits') or {}}")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['md']}")


def _write_report(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"source_quality_{stamp}.json"
    md_path = reports_dir / f"source_quality_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Source Quality Report",
        "",
        f"Generated at: {payload.get('generated_at')}",
        f"Total videos seen: {payload.get('total_videos_seen')}",
        f"Videos processed: {payload.get('videos_processed')}",
        f"Videos accepted: {payload.get('videos_accepted')}",
        f"Videos rejected: {payload.get('videos_rejected')}",
        "",
        "## Best Channels",
        "",
    ]
    for item in payload.get("best_channels") or []:
        lines.append(f"* {item.get('name')}: {item.get('approval_rate')} ({item.get('approved')}/{item.get('total')})")
    lines.extend(["", "## Worst Channels", ""])
    for item in payload.get("worst_channels") or []:
        lines.append(f"* {item.get('name')}: {item.get('approval_rate')} ({item.get('approved')}/{item.get('total')})")
    lines.extend(["", "## Blocked Keyword Hits", ""])
    for reason, count in (payload.get("blocked_keyword_hits") or {}).items():
        lines.append(f"* {reason}: {count}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
