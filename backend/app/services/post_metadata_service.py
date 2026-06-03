from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


POST_METADATA_PATH = config.STORAGE_POST_METADATA_DIR / "post_metadata.json"
POST_METADATA_MD_PATH = config.STORAGE_POST_METADATA_DIR / "post_metadata.md"
POST_STATUS_PATH = config.STORAGE_POST_METADATA_DIR / "post_status.json"
PACKAGE_PATH = config.STORAGE_POSTING_PACKAGE_DIR / "latest" / "posting_package.json"

VALID_POST_STATUSES = {"not_posted", "posted", "scheduled", "do_not_post"}
BASE_HASHTAGS = ["#shorts", "#cortes", "#podcast", "#darkflow"]
KEYWORD_HASHTAGS = [
    ("tdah", "#tdah"),
    ("bolsa familia", "#bolsafamilia"),
    ("bolsa família", "#bolsafamilia"),
    ("debate", "#debate"),
    ("cultura", "#cultura"),
    ("viagem", "#viagem"),
    ("china", "#china"),
    ("sri lanka", "#srilanka"),
    ("achismos", "#achismos"),
    ("podpah", "#podpah"),
    ("redcast", "#redcast"),
    ("ticaracaticast", "#ticaracaticast"),
    ("inteligência", "#inteligencialtda"),
    ("inteligencia", "#inteligencialtda"),
]


def export_post_metadata() -> dict[str, Any]:
    package = _load_json(PACKAGE_PATH)
    items = package.get("items", []) if isinstance(package, dict) else []
    statuses = load_post_status()
    now = datetime.utcnow().isoformat()
    exported_items = [
        _post_item_from_package_item(item, statuses.get(_post_id(item), {}), now)
        for item in items
        if isinstance(item, dict)
    ]
    payload = {
        "generated_at": now,
        "source_package_path": str(PACKAGE_PATH),
        "items_count": len(exported_items),
        "items": exported_items,
    }
    config.STORAGE_POST_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(POST_METADATA_PATH, payload)
    POST_METADATA_MD_PATH.write_text(_markdown(payload), encoding="utf-8")
    if not POST_STATUS_PATH.exists():
        _write_json(POST_STATUS_PATH, {})
    return payload


def load_posts(status: str = "all") -> list[dict[str, Any]]:
    payload = _load_json(POST_METADATA_PATH)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        payload = export_post_metadata()
    statuses = load_post_status()
    posts: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        post_id = str(item.get("post_id") or "")
        merged = dict(item)
        merged.update(_status_fields(statuses.get(post_id, {})))
        if status != "all" and merged.get("posted_status") != status:
            continue
        posts.append(merged)
    return posts


def get_post(post_id: str) -> dict[str, Any] | None:
    for post in load_posts(status="all"):
        if post.get("post_id") == post_id:
            return post
    return None


def update_post_status(
    post_id: str,
    status: str,
    platforms: list[str],
    posted_at: str | None,
    post_url: str,
    notes: str,
) -> dict[str, Any]:
    if status not in VALID_POST_STATUSES:
        raise ValueError("invalid_post_status")
    if not get_post(post_id):
        raise KeyError("post_not_found")
    statuses = load_post_status()
    now = datetime.utcnow().isoformat()
    previous = statuses.get(post_id, {})
    statuses[post_id] = {
        "post_id": post_id,
        "status": status,
        "platforms": list(dict.fromkeys(platforms)),
        "posted_at": posted_at or previous.get("posted_at") or "",
        "post_url": post_url,
        "notes": notes,
        "updated_at": now,
    }
    _write_json(POST_STATUS_PATH, statuses)
    return statuses[post_id]


def posts_summary() -> dict[str, Any]:
    posts = load_posts(status="all")
    status_counts = Counter(str(post.get("posted_status") or "not_posted") for post in posts)
    platform_counts: Counter[str] = Counter()
    for post in posts:
        for platform in post.get("posted_platforms") or []:
            platform_counts[str(platform)] += 1
    return {
        "total": len(posts),
        "not_posted": status_counts.get("not_posted", 0),
        "posted": status_counts.get("posted", 0),
        "scheduled": status_counts.get("scheduled", 0),
        "do_not_post": status_counts.get("do_not_post", 0),
        "count_by_platform": dict(platform_counts),
    }


def load_post_status() -> dict[str, dict[str, Any]]:
    payload = _load_json(POST_STATUS_PATH)
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items() if isinstance(value, dict)}
    return {}


def _post_item_from_package_item(item: dict[str, Any], status_item: dict[str, Any], now: str) -> dict[str, Any]:
    video_title = _clean_title(str(item.get("video_title") or ""))
    youtube_url = str(item.get("original_youtube_url") or "")
    suggested_title = str(item.get("suggested_title_base") or _suggest_title(video_title))
    suggested_description = str(item.get("suggested_description_base") or _suggest_description(video_title, youtube_url))
    suggested_hashtags = item.get("suggested_hashtags_base")
    if not isinstance(suggested_hashtags, list):
        suggested_hashtags = _suggest_hashtags(video_title)
    status_fields = _status_fields(status_item)
    return {
        "post_id": _post_id(item),
        "final_clip_id": item.get("final_clip_id"),
        "clip_id": item.get("clip_id"),
        "candidate_id": item.get("candidate_id"),
        "video_id": item.get("video_id"),
        "video_title": video_title,
        "original_youtube_url": youtube_url,
        "package_video_filename": item.get("package_video_filename"),
        "package_video_path": item.get("package_video_path"),
        "video_url": f"/posting_package/latest/videos/{item.get('package_video_filename')}",
        "duration_seconds": item.get("duration_seconds"),
        "final_review_rating": item.get("final_review_rating"),
        "final_review_reason": item.get("final_review_reason"),
        "final_review_notes": item.get("final_review_notes") or "",
        "suggested_title": suggested_title,
        "suggested_description": suggested_description,
        "suggested_hashtags": [str(hashtag) for hashtag in suggested_hashtags],
        "platform_status": status_fields["posted_status"],
        "posted_status": status_fields["posted_status"],
        "posted_at": status_fields["posted_at"],
        "posted_platforms": status_fields["posted_platforms"],
        "post_url": status_fields["post_url"],
        "notes": status_fields["notes"],
        "created_at": item.get("exported_at") or now,
        "updated_at": status_item.get("updated_at") or now,
    }


def _status_fields(status_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "posted_status": status_item.get("status") or "not_posted",
        "posted_at": status_item.get("posted_at") or "",
        "posted_platforms": status_item.get("platforms") if isinstance(status_item.get("platforms"), list) else [],
        "post_url": status_item.get("post_url") or "",
        "notes": status_item.get("notes") or "",
    }


def _post_id(item: dict[str, Any]) -> str:
    base = str(item.get("final_clip_id") or item.get("clip_id") or item.get("package_video_filename") or "post")
    return _safe_id(base)


def _suggest_title(video_title: str) -> str:
    title = _clean_title(video_title)
    generic = not title or bool(re.fullmatch(r"[-_A-Za-z0-9]{8,16}", title))
    if generic:
        title = f"Corte de podcast: {title or 'vídeo selecionado'}"
    if len(title) <= 90:
        return title
    return title[:87].rstrip() + "..."


def _suggest_description(video_title: str, youtube_url: str) -> str:
    lines = [f"Corte extraído de: {video_title}"]
    if youtube_url:
        lines.append(f"Fonte original: {youtube_url}")
    lines.append("Vídeo selecionado e revisado no DarkFlow.")
    return "\n".join(lines)


def _suggest_hashtags(video_title: str) -> list[str]:
    normalized = _strip_accents(video_title).lower()
    hashtags = list(BASE_HASHTAGS)
    for keyword, hashtag in KEYWORD_HASHTAGS:
        if _strip_accents(keyword).lower() in normalized and hashtag not in hashtags:
            hashtags.append(hashtag)
    return hashtags[:10]


def _clean_title(value: str) -> str:
    title = re.sub(r"#\S+", "", str(value or ""))
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _safe_id(value: str) -> str:
    text = _strip_accents(value)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or "post"


def _strip_accents(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(char)
    )


def _markdown(payload: dict[str, Any]) -> str:
    lines = ["# Post Metadata", "", f"Items: {payload.get('items_count', 0)}", ""]
    for item in payload.get("items", []):
        lines.extend(
            [
                f"## {item.get('suggested_title')}",
                "",
                f"* post_id: {item.get('post_id')}",
                f"* file: {item.get('package_video_filename')}",
                f"* status: {item.get('posted_status')}",
                f"* hashtags: {' '.join(item.get('suggested_hashtags') or [])}",
                "",
            ]
        )
    return "\n".join(lines)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
