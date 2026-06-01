from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.final_clips_service import load_final_clips


BASE_HASHTAGS = ["#shorts", "#cortes", "#podcast", "#darkflow"]
KEYWORD_HASHTAGS = [
    ("tdah", "#tdah"),
    ("cultura", "#cultura"),
    ("viagem", "#viagem"),
    ("china", "#china"),
    ("sri lanka", "#srilanka"),
    ("achismos", "#achismos"),
    ("inteligência", "#inteligenciaLtda"),
    ("inteligencia", "#inteligenciaLtda"),
    ("ticaracaticast", "#ticaracaticast"),
]


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--package-name")
    parser.add_argument("--clean-old", action="store_true")
    args = parser.parse_args()

    exported_at = datetime.utcnow().isoformat()
    package_id = _package_id(args.package_name)
    package_dir = config.STORAGE_POSTING_PACKAGE_DIR / package_id
    videos_dir = package_dir / "videos"
    metadata_dir = package_dir / "metadata"
    final_metadata = _latest_final_metadata_index()
    ready_clips = [
        _merge_metadata(clip, final_metadata.get(str(clip.get("final_clip_id") or ""), {}))
        for clip in load_final_clips(include_duration=False)
        if clip.get("final_review_status") == "ready_to_post"
    ]
    if args.limit is not None:
        ready_clips = ready_clips[: max(0, args.limit)]

    results: list[dict[str, Any]] = []
    copied = skipped = errors = 0
    for index, clip in enumerate(ready_clips, start=1):
        item = _package_item(
            package_index=index,
            clip=clip,
            videos_dir=videos_dir,
            metadata_dir=metadata_dir,
            exported_at=exported_at,
        )
        status = "dry_run" if args.dry_run else "copied"
        error_message = ""
        try:
            if not args.dry_run:
                source_path = Path(str(clip.get("final_path") or ""))
                if not source_path.exists():
                    status = "error"
                    error_message = f"final export não encontrado: {source_path}"
                elif item["package_video_path"].exists() and not args.overwrite:
                    status = "skipped"
                    error_message = "arquivo já existe; use --overwrite"
                else:
                    videos_dir.mkdir(parents=True, exist_ok=True)
                    metadata_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, item["package_video_path"])
                    _write_json(metadata_dir / f"{index:03d}_{_safe_filename(clip['clip_id'])}.json", item)
        except Exception as exc:
            status = "error"
            error_message = str(exc)

        item["status"] = status
        item["error_message"] = error_message
        item["package_video_path"] = str(item["package_video_path"])
        if status == "copied":
            copied += 1
        elif status == "skipped":
            skipped += 1
        elif status == "error":
            errors += 1
        results.append(item)

    payload = {
        "package_id": package_id,
        "exported_at": exported_at,
        "dry_run": args.dry_run,
        "total_ready_to_post": len(ready_clips),
        "copied_count": copied,
        "skipped_count": skipped,
        "error_count": errors,
        "package_dir": str(package_dir),
        "videos_dir": str(videos_dir),
        "metadata_dir": str(metadata_dir),
        "items": results,
    }

    if not args.dry_run:
        package_dir.mkdir(parents=True, exist_ok=True)
        _write_json(package_dir / "posting_package.json", payload)
        (package_dir / "posting_package.md").write_text(_markdown_package(payload), encoding="utf-8")

    cleaned_packages: list[str] = []
    if args.clean_old and not args.dry_run:
        cleaned_packages = _clean_old_packages(keep_package_id=package_id)
        payload["cleaned_old_packages"] = cleaned_packages
        _write_json(package_dir / "posting_package.json", payload)
        (package_dir / "posting_package.md").write_text(_markdown_package(payload), encoding="utf-8")
    else:
        payload["cleaned_old_packages"] = []
    report_paths = _write_reports(payload)
    _print_summary(payload, report_paths)
    if cleaned_packages:
        print("Cleaned old packages:")
        for path in cleaned_packages:
            print(f"- {path}")


def _package_item(
    package_index: int,
    clip: dict[str, Any],
    videos_dir: Path,
    metadata_dir: Path,
    exported_at: str,
) -> dict[str, Any]:
    final_review = clip.get("current_final_review") if isinstance(clip.get("current_final_review"), dict) else {}
    video_title = str(clip.get("video_title") or clip.get("video_id") or "")
    reason = str(clip.get("reason") or clip.get("review_reason") or "clip")
    package_video_filename = _package_video_filename(package_index, clip)
    hashtags = _suggest_hashtags(video_title)
    return {
        "package_index": package_index,
        "final_clip_id": clip.get("final_clip_id"),
        "clip_id": clip.get("clip_id"),
        "video_id": clip.get("video_id"),
        "video_title": video_title,
        "original_youtube_url": clip.get("original_youtube_url") or "",
        "final_filename_original": clip.get("final_filename"),
        "package_video_filename": package_video_filename,
        "package_video_path": videos_dir / package_video_filename,
        "rank": clip.get("rank"),
        "rating": clip.get("rating"),
        "reason": reason,
        "review_status": clip.get("review_status"),
        "review_rating": clip.get("review_rating"),
        "review_reason": clip.get("review_reason"),
        "review_notes": clip.get("review_notes"),
        "final_review_status": final_review.get("status") or clip.get("final_review_status"),
        "final_review_rating": final_review.get("rating") or clip.get("final_review_rating"),
        "final_review_reason": final_review.get("reason") or clip.get("final_review_reason"),
        "final_review_notes": final_review.get("notes") or clip.get("final_review_notes") or "",
        "duration_seconds": clip.get("final_duration_seconds") or clip.get("duration_seconds"),
        "file_size_bytes": clip.get("file_size_bytes"),
        "suggested_title_base": _suggest_title(video_title, reason),
        "suggested_description_base": _suggest_description(video_title, clip.get("original_youtube_url") or ""),
        "suggested_hashtags_base": hashtags,
        "created_at": clip.get("created_at") or final_review.get("created_at"),
        "exported_at": exported_at,
        "metadata_dir": str(metadata_dir),
    }


def _package_video_filename(package_index: int, clip: dict[str, Any]) -> str:
    video_id = _safe_filename(str(clip.get("video_id") or "video"))
    rank = clip.get("rank") or "x"
    reason = _safe_filename(str(clip.get("reason") or clip.get("review_reason") or "clip"))
    return f"{package_index:03d}_{video_id}_rank_{rank}_{reason}.mp4"


def _suggest_title(video_title: str, reason: str) -> str:
    title = _clean_title(video_title)
    if reason and reason not in {"pronto", "bom", "otimo", "perfeito"}:
        title = f"{title} - {reason.replace('_', ' ')}"
    if len(title) <= 80:
        return title
    return title[:77].rstrip() + "..."


def _suggest_description(video_title: str, youtube_url: str) -> str:
    lines = [f"Corte extraído de: {_clean_title(video_title)}"]
    if youtube_url:
        lines.append(f"Fonte original: {youtube_url}")
    return "\n".join(lines)


def _suggest_hashtags(video_title: str) -> list[str]:
    text = _strip_accents(video_title).lower()
    hashtags = list(BASE_HASHTAGS)
    for keyword, hashtag in KEYWORD_HASHTAGS:
        normalized_keyword = _strip_accents(keyword).lower()
        if normalized_keyword in text and hashtag not in hashtags:
            hashtags.append(hashtag)
    return hashtags


def _clean_title(video_title: str) -> str:
    title = re.sub(r"\s+", " ", str(video_title or "")).strip()
    return title or "Corte selecionado"


def _merge_metadata(clip: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    merged = dict(metadata)
    merged.update({key: value for key, value in clip.items() if value not in (None, "")})
    if "current_final_review" not in merged and metadata.get("current_final_review"):
        merged["current_final_review"] = metadata["current_final_review"]
    return merged


def _latest_final_metadata_index() -> dict[str, dict[str, Any]]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    paths = sorted(reports_dir.glob("final_clips_metadata_*.json"))
    if not paths:
        return {}
    payload = _load_json(paths[-1])
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return {
        str(item.get("final_clip_id")): item
        for item in items
        if isinstance(item, dict) and item.get("final_clip_id")
    }


def _package_id(package_name: str | None) -> str:
    if package_name:
        return _safe_filename(package_name)
    return datetime.now().strftime("%Y%m%d_%H%M")


def _clean_old_packages(keep_package_id: str) -> list[str]:
    root = config.STORAGE_POSTING_PACKAGE_DIR.resolve()
    if not root.exists():
        return []
    package_dirs = [
        path
        for path in root.iterdir()
        if path.is_dir() and path.resolve().parent == root
    ]
    timestamp_dirs = [path for path in package_dirs if path.name != "latest"]
    newest_timestamp = max(timestamp_dirs, key=lambda path: path.stat().st_mtime, default=None)
    keep_names = {"latest", keep_package_id}
    if newest_timestamp:
        keep_names.add(newest_timestamp.name)
    removed: list[str] = []
    for path in package_dirs:
        resolved = path.resolve()
        if path.name in keep_names:
            continue
        if resolved.parent != root:
            continue
        shutil.rmtree(resolved)
        removed.append(str(resolved))
    return removed


def _write_reports(payload: dict[str, Any]) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"ready_to_post_package_{timestamp}.json"
    md_path = reports_dir / f"ready_to_post_package_{timestamp}.md"
    _write_json(json_path, payload)
    md_path.write_text(_markdown_package(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _markdown_package(payload: dict[str, Any]) -> str:
    lines = [
        "# Ready-to-Post Package",
        "",
        f"Package: {payload['package_id']}",
        f"Total: {payload['total_ready_to_post']}",
        f"Videos dir: {payload['videos_dir']}",
        f"Cleaned old packages: {len(payload.get('cleaned_old_packages') or [])}",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"## {item['package_index']:03d} - {item['suggested_title_base']}",
                "",
                f"* file: {item['package_video_filename']}",
                f"* rating: {item.get('rating')} / final {item.get('final_review_rating')}",
                f"* reason: {item.get('reason')}",
                f"* final review: {item.get('final_review_status')} / {item.get('final_review_reason')}",
                f"* source: {item.get('original_youtube_url')}",
                f"* suggested title: {item.get('suggested_title_base')}",
                f"* description: {item.get('suggested_description_base')}",
                f"* hashtags: {' '.join(item.get('suggested_hashtags_base') or [])}",
                f"* status: {item.get('status')}",
                f"* error: {item.get('error_message')}",
                "",
            ]
        )
    return "\n".join(lines)


def _print_summary(payload: dict[str, Any], report_paths: dict[str, str]) -> None:
    print("READY TO POST PACKAGE")
    print(f"Ready clips: {payload['total_ready_to_post']}")
    print(f"Copied: {payload['copied_count']}")
    print(f"Skipped: {payload['skipped_count']}")
    print(f"Errors: {payload['error_count']}")
    print(f"Package: {payload['package_dir']}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")
    print("")
    for item in payload["items"]:
        print(f"- {item['package_video_filename']} | {item['status']}")
        if item.get("error_message"):
            print(f"  {item['error_message']}")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=str)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _safe_filename(value: str) -> str:
    text = _strip_accents(str(value or "")).lower()
    text = re.sub(r"[^a-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or "clip"


def _strip_accents(value: str) -> str:
    replacements = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ",
        "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN",
    )
    return value.translate(replacements)


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
