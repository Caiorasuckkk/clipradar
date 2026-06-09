from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.candidate_preview_validation_service import validate_candidate_preview


MANIFEST_PATH = config.STORAGE_TRENDS_DIR.parent / "cache" / "cache_manifest.json"
MIN_TEXT_LENGTH = 20
MIN_MEDIA_BYTES = 32 * 1024


def load_manifest() -> dict[str, Any]:
    payload = _load_json(MANIFEST_PATH)
    if isinstance(payload, dict) and isinstance(payload.get("videos"), dict):
        return payload
    return {"updated_at": "", "videos": {}}


def save_manifest(manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = datetime.utcnow().isoformat()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)


def rebuild_manifest(video_ids: list[str] | None = None) -> dict[str, Any]:
    ids = set(video_ids or [])
    if not ids:
        ids.update(_video_ids_from_paths())
        ids.update(_video_ids_from_candidates())
        ids.update(_video_ids_from_posts())
    manifest = load_manifest()
    manifest["videos"] = {
        video_id: build_video_cache_entry(video_id, manifest["videos"].get(video_id, {}))
        for video_id in sorted(ids)
        if video_id
    }
    save_manifest(manifest)
    return manifest


def update_video_cache(
    video_id: str,
    *,
    video_title: str = "",
    youtube_url: str = "",
    last_processed: bool = False,
) -> dict[str, Any]:
    manifest = load_manifest()
    previous = manifest["videos"].get(video_id, {})
    if video_title:
        previous["video_title"] = video_title
    if youtube_url:
        previous["youtube_url"] = youtube_url
    if last_processed:
        previous["last_processed_at"] = datetime.utcnow().isoformat()
    entry = build_video_cache_entry(video_id, previous)
    manifest["videos"][video_id] = entry
    save_manifest(manifest)
    return entry


def touch_video_cache(video_id: str) -> None:
    if not video_id:
        return
    manifest = load_manifest()
    previous = manifest["videos"].get(video_id, {})
    previous["last_used_at"] = datetime.utcnow().isoformat()
    manifest["videos"][video_id] = build_video_cache_entry(video_id, previous)
    save_manifest(manifest)


def record_cache_run_metrics(metrics: dict[str, Any]) -> None:
    manifest = load_manifest()
    manifest["latest_cache_run"] = {
        "updated_at": datetime.utcnow().isoformat(),
        "cache_hits": _int(metrics.get("cache_hits")),
        "cache_misses": _int(metrics.get("cache_misses")),
        "cache_partials": _int(metrics.get("cache_partials")),
        "cache_bypassed": _int(metrics.get("cache_bypassed")),
        "videos_reused": _int(metrics.get("videos_reused")),
        "videos_processed_from_scratch": _int(metrics.get("videos_processed_from_scratch")),
        "estimated_seconds_saved": _int(metrics.get("estimated_seconds_saved")),
    }
    save_manifest(manifest)


def get_cache_status(video_id: str) -> dict[str, Any]:
    manifest = load_manifest()
    return build_video_cache_entry(video_id, manifest["videos"].get(video_id, {}))


def has_valid_download(video_id: str) -> bool:
    entry = get_cache_status(video_id)
    return bool(entry.get("downloaded_video_path") or entry.get("downloaded_audio_path"))


def has_valid_transcript(video_id: str) -> bool:
    return bool(get_cache_status(video_id).get("transcript_exists"))


def has_valid_clips(video_id: str) -> bool:
    return bool(get_cache_status(video_id).get("clips_exists"))


def has_valid_previews(video_id: str) -> bool:
    entry = get_cache_status(video_id)
    return int(entry.get("previews_ready_count") or 0) > 0


def has_valid_final(candidate_id: str) -> bool:
    if not candidate_id:
        return False
    for path in config.STORAGE_FINAL_EXPORTS_DIR.glob(f"*{candidate_id}*.mp4"):
        if path.is_file() and path.stat().st_size > MIN_MEDIA_BYTES:
            return True
    for item in _load_post_items():
        if str(item.get("candidate_id") or "") == candidate_id:
            path = Path(str(item.get("package_video_path") or ""))
            if path.exists() and path.stat().st_size > MIN_MEDIA_BYTES:
                return True
    return False


def build_video_cache_entry(video_id: str, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    previous = previous or {}
    transcript_path = config.STORAGE_TRANSCRIPTS_DIR / f"{video_id}.json"
    clips_path = config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json"
    download_video = _first_valid_media(
        [config.STORAGE_VIDEOS_DIR, config.STORAGE_DOWNLOADS_DIR, config.STORAGE_TRENDS_DIR.parent / "cache"],
        video_id,
        video_exts={".mp4", ".mkv", ".webm", ".mov"},
    )
    download_audio = _first_valid_media(
        [config.STORAGE_DOWNLOADS_DIR],
        video_id,
        video_exts={".m4a", ".mp3", ".opus", ".webm", ".wav"},
    )
    transcript = _valid_transcript(transcript_path)
    clips_info = _clips_info(clips_path)
    candidate_items = _candidate_items_for_video(video_id)
    candidate_ids = sorted(
        dict.fromkeys(str(item.get("candidate_id") or "") for item in candidate_items if item.get("candidate_id"))
    )
    preview_counts = _preview_counts(candidate_items)
    finals_count = _finals_count(video_id, candidate_ids)
    posts_count = _posts_count(video_id, candidate_ids)
    positives = [
        bool(download_video or download_audio),
        transcript["valid"],
        clips_info["valid"],
        preview_counts["ready"] > 0,
        finals_count > 0,
        posts_count > 0,
    ]
    invalid = (
        transcript["invalid"]
        or clips_info["invalid"]
        or preview_counts["invalid"] > 0
    )
    status = "empty"
    if invalid:
        status = "invalid"
    elif all(positives[:3]) and preview_counts["ready"] > 0:
        status = "ready"
    elif any(positives):
        status = "partial"
    return {
        "video_id": video_id,
        "video_title": previous.get("video_title") or _title_for_video(video_id),
        "youtube_url": previous.get("youtube_url") or _youtube_url_for_video(video_id),
        "downloaded_video_path": str(download_video) if download_video else "",
        "downloaded_audio_path": str(download_audio) if download_audio else "",
        "transcript_path": str(transcript_path),
        "transcript_exists": transcript["valid"],
        "transcript_updated_at": _mtime(transcript_path) if transcript["valid"] else "",
        "clips_path": str(clips_path),
        "clips_exists": clips_info["valid"],
        "clips_count": clips_info["count"],
        "candidate_queue_ids": candidate_ids,
        "previews_count": preview_counts["total"],
        "previews_ready_count": preview_counts["ready"],
        "previews_invalid_count": preview_counts["invalid"],
        "finals_count": finals_count,
        "posts_count": posts_count,
        "last_processed_at": previous.get("last_processed_at") or "",
        "last_used_at": previous.get("last_used_at") or "",
        "input_signature": _input_signature(video_id, transcript_path, clips_path),
        "source_hash": _input_signature(video_id, transcript_path, clips_path),
        "cache_status": status,
    }


def cache_summary() -> dict[str, Any]:
    manifest = rebuild_manifest()
    entries = list(manifest.get("videos", {}).values())
    statuses = Counter(str(entry.get("cache_status") or "empty") for entry in entries)
    latest_run = _latest_find_run()
    latest_cache = _cache_metrics_from_run(latest_run)
    if not any(latest_cache.values()):
        latest_cache = _cache_metrics_from_manifest(manifest)
    integrity = cache_integrity_summary(manifest=manifest)
    return {
        "total_videos_cached": len(entries),
        "ready_count": statuses.get("ready", 0),
        "partial_count": statuses.get("partial", 0),
        "invalid_count": statuses.get("invalid", 0),
        "stale_count": integrity["stale_count"],
        "transcript_cached_count": sum(1 for entry in entries if entry.get("transcript_exists")),
        "clips_cached_count": sum(1 for entry in entries if entry.get("clips_exists")),
        "previews_cached_count": sum(1 for entry in entries if int(entry.get("previews_ready_count") or 0) > 0),
        "finals_cached_count": sum(1 for entry in entries if int(entry.get("finals_count") or 0) > 0),
        "cache_hits_latest_run": latest_cache["cache_hits"],
        "cache_misses_latest_run": latest_cache["cache_misses"],
        "cache_partials_latest_run": latest_cache["cache_partials"],
        "cache_bypassed_latest_run": latest_cache["cache_bypassed"],
        "videos_reused_latest_run": latest_cache["videos_reused"],
        "videos_processed_from_scratch_latest_run": latest_cache["videos_processed_from_scratch"],
        "estimated_seconds_saved_latest_run": latest_cache["estimated_seconds_saved"],
        "duplicate_candidates_detected_latest_run": _int(latest_run.get("duplicate_candidates_detected"))
        or _int(latest_run.get("duplicates_removed"))
        or integrity["duplicate_candidates"],
        "duplicate_posts_detected": integrity["duplicate_posts"],
        "approved_missing_finals": integrity["approved_missing_finals"],
        "orphan_finals": integrity["orphan_finals"],
        "orphan_posts": integrity["orphan_posts"],
    }


def cache_integrity_summary(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or load_manifest()
    entries = list((manifest.get("videos") or {}).values()) if isinstance(manifest, dict) else []
    stale_entries = [
        str(entry.get("video_id") or "")
        for entry in entries
        if str(entry.get("cache_status") or "") in {"stale", "invalid"}
    ]
    candidate_items = _load_candidate_items()
    candidate_ids = [str(item.get("candidate_id") or "") for item in candidate_items if item.get("candidate_id")]
    duplicate_candidate_ids = _duplicates(candidate_ids)
    post_items = _load_post_items()
    post_keys = [_post_stable_key(item) for item in post_items]
    duplicate_post_keys = _duplicates([key for key in post_keys if key])
    approved_candidate_ids = _approved_candidate_ids(candidate_items)
    generated_candidate_ids = {
        str(item.get("candidate_id") or "")
        for item in post_items
        if item.get("candidate_id") and _post_has_file(item)
    }
    generated_candidate_ids.update(_candidate_ids_from_final_files(approved_candidate_ids))
    approved_missing = sorted(approved_candidate_ids - generated_candidate_ids)
    known_preview_files = {
        str(item.get("output_preview_filename") or "")
        for item in candidate_items
        if item.get("output_preview_filename")
    }
    orphan_previews = [
        path.name
        for path in config.STORAGE_CANDIDATE_PREVIEWS_DIR.glob("*.mp4")
        if path.name not in known_preview_files
    ]
    known_final_names = {
        Path(str(item.get("package_video_path") or "")).name
        for item in post_items
        if item.get("package_video_path")
    }
    orphan_finals = [
        path.name
        for path in config.STORAGE_FINAL_EXPORTS_DIR.glob("*.mp4")
        if path.name not in known_final_names and not any(candidate_id and candidate_id in path.name for candidate_id in approved_candidate_ids)
    ]
    orphan_posts = [
        str(item.get("post_id") or item.get("candidate_id") or item.get("package_video_filename") or "")
        for item in post_items
        if not _post_has_file(item)
    ]
    missing_files = _missing_manifest_files(entries)
    invalid_json = _invalid_json_files(entries)
    return {
        "stale_count": len([item for item in stale_entries if item]),
        "stale_entries": [item for item in stale_entries if item],
        "missing_files": missing_files,
        "missing_files_count": len(missing_files),
        "invalid_json": invalid_json,
        "invalid_json_count": len(invalid_json),
        "orphan_previews": len(orphan_previews),
        "orphan_preview_files": orphan_previews[:100],
        "orphan_finals": len(orphan_finals),
        "orphan_final_files": orphan_finals[:100],
        "orphan_posts": len(orphan_posts),
        "orphan_post_ids": orphan_posts[:100],
        "duplicate_candidates": len(duplicate_candidate_ids),
        "duplicate_candidate_ids": duplicate_candidate_ids[:100],
        "duplicate_posts": len(duplicate_post_keys),
        "duplicate_post_keys": duplicate_post_keys[:100],
        "approved_missing_finals": len(approved_missing),
        "approved_missing_final_candidate_ids": approved_missing[:100],
        "posts_missing_files": len(orphan_posts),
    }


def _cache_metrics_from_run(run: dict[str, Any]) -> dict[str, Any]:
    text = "\n".join(str(run.get(key) or "") for key in ("stdout_tail", "stderr_tail", "latest_error"))
    parsed = _parse_cache_summary(text)
    return {
        "cache_hits": _int(run.get("cache_hits")) or parsed.get("cache_hits", 0),
        "cache_misses": _int(run.get("cache_misses")) or parsed.get("cache_misses", 0),
        "cache_partials": _int(run.get("cache_partials")) or parsed.get("cache_partials", 0),
        "cache_bypassed": _int(run.get("cache_bypassed")) or parsed.get("cache_bypassed", 0),
        "videos_reused": _int(run.get("videos_reused_from_cache")) or parsed.get("videos_reused", 0),
        "videos_processed_from_scratch": _int(run.get("videos_processed_from_scratch")) or parsed.get("videos_processed_from_scratch", 0),
        "estimated_seconds_saved": _float_or_none(run.get("estimated_seconds_saved")) or parsed.get("estimated_seconds_saved"),
    }


def _cache_metrics_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    latest = manifest.get("latest_cache_run")
    if not isinstance(latest, dict):
        latest = {}
    return {
        "cache_hits": _int(latest.get("cache_hits")),
        "cache_misses": _int(latest.get("cache_misses")),
        "cache_partials": _int(latest.get("cache_partials")),
        "cache_bypassed": _int(latest.get("cache_bypassed")),
        "videos_reused": _int(latest.get("videos_reused")),
        "videos_processed_from_scratch": _int(latest.get("videos_processed_from_scratch")),
        "estimated_seconds_saved": _float_or_none(latest.get("estimated_seconds_saved")),
    }


def _parse_cache_summary(text: str) -> dict[str, Any]:
    match = re.search(r"\[cache_summary\]\s+(.+)", text or "")
    if not match:
        return {}
    values: dict[str, Any] = {}
    for item in match.group(1).split():
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        values[key] = _int(value)
    return values


def _valid_transcript(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return {"valid": False, "invalid": path.exists()}
    text = str(payload.get("text") or "").strip()
    segments = payload.get("segments")
    valid_segments = isinstance(segments, list) and len(segments) > 0
    valid = (len(text) >= MIN_TEXT_LENGTH or valid_segments) and path.stat().st_size > 10
    return {"valid": valid, "invalid": not valid and path.exists()}


def _clips_info(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        return {"valid": False, "invalid": path.exists(), "count": 0}
    clips = payload.get("clips") if isinstance(payload.get("clips"), list) else []
    diagnostics = payload.get("diagnostic_candidates") if isinstance(payload.get("diagnostic_candidates"), list) else []
    count = len(clips) + len(diagnostics)
    return {"valid": count > 0, "invalid": count <= 0 and path.exists(), "count": count}


def _candidate_items_for_video(video_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    payload = _load_json(config.STORAGE_CANDIDATE_QUEUE_DIR / "candidate_review_queue.json")
    for item in payload.get("items", []) if isinstance(payload, dict) else []:
        if isinstance(item, dict) and str(item.get("video_id") or "") == video_id:
            items.append(item)
    return items


def _preview_counts(candidate_items: list[dict[str, Any]]) -> dict[str, int]:
    total = ready = invalid = 0
    seen: set[Path] = set()
    for item in candidate_items:
        filename = str(item.get("output_preview_filename") or "")
        paths = [config.STORAGE_CANDIDATE_PREVIEWS_DIR / filename] if filename else []
        candidate_id = str(item.get("candidate_id") or "")
        paths.extend(config.STORAGE_CANDIDATE_PREVIEWS_DIR.glob(f"{candidate_id}*.mp4"))
        for path in paths:
            if path in seen or not path.exists():
                continue
            seen.add(path)
            total += 1
            validation = validate_candidate_preview(path, deep=False)
            if validation.valid:
                ready += 1
            else:
                invalid += 1
    return {"total": total, "ready": ready, "invalid": invalid}


def _finals_count(video_id: str, candidate_ids: list[str]) -> int:
    count = 0
    candidate_set = set(candidate_ids)
    for path in config.STORAGE_FINAL_EXPORTS_DIR.glob("*.mp4"):
        name = path.name
        if video_id in name or any(candidate_id and candidate_id in name for candidate_id in candidate_set):
            if path.stat().st_size > MIN_MEDIA_BYTES:
                count += 1
    return count


def _posts_count(video_id: str, candidate_ids: list[str]) -> int:
    candidate_set = set(candidate_ids)
    count = 0
    for item in _load_post_items():
        if str(item.get("video_id") or "") == video_id or str(item.get("candidate_id") or "") in candidate_set:
            count += 1
    return count


def _load_post_items() -> list[dict[str, Any]]:
    payload = _load_json(config.STORAGE_POST_METADATA_DIR / "post_metadata.json")
    return [item for item in payload.get("items", []) if isinstance(item, dict)] if isinstance(payload, dict) else []


def _load_candidate_items() -> list[dict[str, Any]]:
    payload = _load_json(config.STORAGE_CANDIDATE_QUEUE_DIR / "candidate_review_queue.json")
    return [item for item in payload.get("items", []) if isinstance(item, dict)] if isinstance(payload, dict) else []


def _approved_candidate_ids(candidate_items: list[dict[str, Any]]) -> set[str]:
    approved: set[str] = set()
    for item in candidate_items:
        candidate_id = str(item.get("candidate_id") or "")
        if not candidate_id:
            continue
        status = str(item.get("review_status") or item.get("status") or "").lower()
        if status == "approved":
            approved.add(candidate_id)
    reviews_payload = _load_json(config.STORAGE_CANDIDATE_QUEUE_DIR / "candidate_reviews.json")
    if isinstance(reviews_payload, dict):
        reviews = reviews_payload.get("reviews") if isinstance(reviews_payload.get("reviews"), list) else []
        for review in reviews:
            if not isinstance(review, dict):
                continue
            candidate_id = str(review.get("candidate_id") or "")
            status = str(review.get("status") or "").lower()
            if candidate_id and status == "approved":
                approved.add(candidate_id)
    return approved


def _candidate_ids_from_final_files(candidate_ids: set[str]) -> set[str]:
    generated: set[str] = set()
    if not candidate_ids:
        return generated
    for path in config.STORAGE_FINAL_EXPORTS_DIR.glob("*.mp4"):
        name = path.name
        if not path.is_file() or path.stat().st_size <= MIN_MEDIA_BYTES:
            continue
        for candidate_id in candidate_ids:
            if candidate_id and candidate_id in name:
                generated.add(candidate_id)
    return generated


def _post_stable_key(item: dict[str, Any]) -> str:
    return str(
        item.get("candidate_id")
        or item.get("final_clip_id")
        or item.get("clip_id")
        or item.get("post_id")
        or item.get("package_video_filename")
        or ""
    )


def _post_has_file(item: dict[str, Any]) -> bool:
    raw_path = str(item.get("package_video_path") or "")
    if not raw_path:
        filename = str(item.get("package_video_filename") or "")
        raw_path = str(config.STORAGE_POSTING_PACKAGE_DIR / "latest" / "videos" / filename) if filename else ""
    if not raw_path:
        return False
    path = Path(raw_path)
    return path.is_file() and path.stat().st_size > MIN_MEDIA_BYTES


def _missing_manifest_files(entries: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for entry in entries:
        for key in ("downloaded_video_path", "downloaded_audio_path"):
            raw_path = str(entry.get(key) or "")
            if raw_path and not Path(raw_path).exists():
                missing.append(raw_path)
    return missing[:200]


def _invalid_json_files(entries: list[dict[str, Any]]) -> list[str]:
    invalid: list[str] = []
    for entry in entries:
        for key in ("transcript_path", "clips_path"):
            raw_path = str(entry.get(key) or "")
            if not raw_path:
                continue
            path = Path(raw_path)
            if path.exists() and _load_json(path) == {}:
                invalid.append(raw_path)
    return invalid[:200]


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(value for value in values if value)
    return sorted(value for value, count in counts.items() if count > 1)


def _first_valid_media(directories: list[Path], video_id: str, video_exts: set[str]) -> Path | None:
    for directory in directories:
        if not directory.exists():
            continue
        exact_mp4 = directory / f"{video_id}.mp4"
        if exact_mp4.exists() and exact_mp4.stat().st_size > MIN_MEDIA_BYTES and exact_mp4.suffix.lower() in video_exts:
            return exact_mp4
        for path in sorted(directory.glob(f"{video_id}.*")):
            if path.suffix.lower() in video_exts and path.is_file() and path.stat().st_size > MIN_MEDIA_BYTES:
                return path
    return None


def _video_ids_from_paths() -> set[str]:
    ids: set[str] = set()
    for directory, suffix in [
        (config.STORAGE_TRANSCRIPTS_DIR, ".json"),
        (config.STORAGE_CLIPS_DIR, "_clips.json"),
        (config.STORAGE_VIDEOS_DIR, ""),
        (config.STORAGE_DOWNLOADS_DIR, ""),
    ]:
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if suffix and not name.endswith(suffix):
                continue
            if name.endswith("_clips.json"):
                ids.add(name.replace("_clips.json", ""))
            else:
                ids.add(name.split(".", 1)[0])
    return ids


def _video_ids_from_candidates() -> set[str]:
    payload = _load_json(config.STORAGE_CANDIDATE_QUEUE_DIR / "candidate_review_queue.json")
    return {
        str(item.get("video_id"))
        for item in payload.get("items", []) if isinstance(item, dict) and item.get("video_id")
    } if isinstance(payload, dict) else set()


def _video_ids_from_posts() -> set[str]:
    return {str(item.get("video_id")) for item in _load_post_items() if item.get("video_id")}


def _title_for_video(video_id: str) -> str:
    clips = _load_json(config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json")
    if isinstance(clips, dict):
        return str(clips.get("video_title") or "")
    return ""


def _youtube_url_for_video(video_id: str) -> str:
    clips = _load_json(config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json")
    if isinstance(clips, dict):
        return str(clips.get("url") or clips.get("youtube_url") or "")
    return ""


def _input_signature(video_id: str, transcript_path: Path, clips_path: Path) -> str:
    parts = [video_id]
    for path in (transcript_path, clips_path):
        if path.exists():
            stat = path.stat()
            parts.append(f"{path.name}:{int(stat.st_mtime)}:{stat.st_size}")
    return "|".join(parts)


def _latest_find_run() -> dict[str, Any]:
    runs = []
    for path in config.STORAGE_JOB_RUNS_DIR.glob("*.json"):
        payload = _load_json(path)
        if isinstance(payload, dict) and payload.get("job_key") == "find_videos_flow":
            runs.append(payload)
    return sorted(runs, key=lambda item: str(item.get("started_at") or ""), reverse=True)[0] if runs else {}


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _mtime(path: Path) -> str:
    return datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else ""


def _int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None
