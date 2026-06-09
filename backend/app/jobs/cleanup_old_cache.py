from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app import config


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely list/remove old cache files.")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--include-previews", action="store_true")
    parser.add_argument("--include-downloads", action="store_true")
    parser.add_argument("--include-transcripts", action="store_true")
    parser.add_argument("--include-finals", action="store_true")
    args = parser.parse_args()

    cutoff = datetime.now() - timedelta(days=max(1, args.days))
    protected_posts = _posted_video_paths()
    candidates = _cleanup_candidates(args, cutoff, protected_posts)
    removed: list[str] = []
    if not args.dry_run:
        for path in candidates:
            try:
                path.unlink()
                removed.append(str(path))
            except Exception:
                pass
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "dry_run": args.dry_run,
        "days": args.days,
        "include_previews": args.include_previews,
        "include_downloads": args.include_downloads,
        "include_transcripts": args.include_transcripts,
        "include_finals": args.include_finals,
        "candidate_count": len(candidates),
        "removed_count": len(removed),
        "candidates": [str(path) for path in candidates],
        "removed": removed,
    }
    paths = _write_report(payload)
    print("CLEANUP OLD CACHE")
    print(f"dry_run: {args.dry_run}")
    print(f"days: {args.days}")
    print(f"candidate_count: {len(candidates)}")
    print(f"removed_count: {len(removed)}")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['md']}")


def _cleanup_candidates(args: argparse.Namespace, cutoff: datetime, protected_posts: set[Path]) -> list[Path]:
    groups: list[tuple[bool, Path, tuple[str, ...]]] = [
        (args.include_previews, config.STORAGE_CANDIDATE_PREVIEWS_DIR, (".mp4",)),
        (args.include_downloads, config.STORAGE_DOWNLOADS_DIR, (".m4a", ".mp3", ".webm", ".mp4", ".part", ".ytdl")),
        (args.include_transcripts, config.STORAGE_TRANSCRIPTS_DIR, (".json",)),
        (args.include_finals, config.STORAGE_FINAL_EXPORTS_DIR, (".mp4",)),
    ]
    files: list[Path] = []
    for enabled, directory, suffixes in groups:
        if not enabled or not directory.exists():
            continue
        root = directory.resolve()
        for path in directory.iterdir():
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            resolved = path.resolve()
            if root not in resolved.parents or resolved in protected_posts:
                continue
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                files.append(path)
    return files


def _posted_video_paths() -> set[Path]:
    payload = _load_json(config.STORAGE_POST_METADATA_DIR / "post_metadata.json")
    protected: set[Path] = set()
    for item in payload.get("items", []) if isinstance(payload, dict) else []:
        path = Path(str(item.get("package_video_path") or ""))
        if path.exists():
            protected.add(path.resolve())
    return protected


def _write_report(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"cleanup_old_cache_{stamp}.json"
    md_path = reports_dir / f"cleanup_old_cache_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cleanup Old Cache",
        "",
        f"* dry_run: {payload['dry_run']}",
        f"* days: {payload['days']}",
        f"* candidate_count: {payload['candidate_count']}",
        f"* removed_count: {payload['removed_count']}",
        "",
    ]
    for path in payload.get("candidates", [])[:100]:
        lines.append(f"* {path}")
    return "\n".join(lines)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


if __name__ == "__main__":
    main()
