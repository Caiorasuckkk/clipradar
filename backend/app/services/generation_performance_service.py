"""Performance loop for generated videos.

Records where each generated video was posted and tracks its metrics so the
owner can see what actually works (by studio/niche/duration) and double down —
the data that decides monetization. YouTube view/like/comment counts are pulled
automatically via the existing API key; retention/CTR are entered manually
(read from Studio) since those need channel OAuth.
"""
from __future__ import annotations

import re
import statistics
from datetime import datetime
from typing import Any

import requests

from app import config
from app.services.generation_workspace_service import get_project, list_projects, update_project


def mark_posted(
    project_id: str,
    platform: str,
    url: str = "",
    views: int | None = None,
    retention: float | None = None,
    ctr: float | None = None,
    notes: str = "",
) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    platform = str(platform or "").strip().lower() or "youtube"
    url = str(url or "").strip()
    video_id = _extract_youtube_id(url) if platform == "youtube" else ""
    payload: dict[str, Any] = {
        **project,
        "posted_platform": platform,
        "posted_url": url,
        "posted_video_id": video_id,
        "posted_at": project.get("posted_at") or _now(),
        "posted_notes": str(notes or ""),
        "metric_retention": retention,
        "metric_ctr": ctr,
    }
    stats = _fetch_youtube_stats(video_id) if video_id else None
    if stats:
        payload["metric_views"] = stats["views"]
        payload["metric_likes"] = stats["likes"]
        payload["metric_comments"] = stats["comments"]
        payload["metrics_updated_at"] = _now()
    elif views is not None:
        payload["metric_views"] = int(views)
        payload["metrics_updated_at"] = _now()
    return update_project(project_id, payload)


def refresh_metrics(project_id: str) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    video_id = str(project.get("posted_video_id") or "") or _extract_youtube_id(str(project.get("posted_url") or ""))
    stats = _fetch_youtube_stats(video_id) if video_id else None
    if not stats:
        return project
    return update_project(
        project_id,
        {
            **project,
            "posted_video_id": video_id,
            "metric_views": stats["views"],
            "metric_likes": stats["likes"],
            "metric_comments": stats["comments"],
            "metrics_updated_at": _now(),
        },
    )


def performance_summary(refresh: bool = False) -> dict[str, Any]:
    posted = [p for p in list_projects() if str(p.get("posted_url") or "") or p.get("posted_platform")]
    if refresh:
        for project in posted:
            if project.get("posted_video_id") or _extract_youtube_id(str(project.get("posted_url") or "")):
                refresh_metrics(str(project.get("project_id")))
        posted = [p for p in list_projects() if str(p.get("posted_url") or "") or p.get("posted_platform")]

    videos = [_video_row(p) for p in posted]
    videos.sort(key=lambda v: v["views"], reverse=True)
    return {
        "videos": videos,
        "total_posted": len(videos),
        "by_studio": _aggregate(videos, "persona_label"),
        "by_niche": _aggregate(videos, "niche"),
    }


def _video_row(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": str(project.get("project_id") or ""),
        "title": str(project.get("title") or ""),
        "persona": str(project.get("persona") or ""),
        "persona_label": str(project.get("persona_label") or "") or "—",
        "niche": str(project.get("niche") or "") or "—",
        "platform": str(project.get("posted_platform") or ""),
        "url": str(project.get("posted_url") or ""),
        "duration_seconds": _num(project.get("requested_duration_seconds") or project.get("estimated_duration_seconds")),
        "views": _int(project.get("metric_views")),
        "likes": _int(project.get("metric_likes")),
        "comments": _int(project.get("metric_comments")),
        "retention": _num(project.get("metric_retention")),
        "ctr": _num(project.get("metric_ctr")),
        "posted_at": str(project.get("posted_at") or ""),
        "metrics_updated_at": str(project.get("metrics_updated_at") or ""),
    }


def _aggregate(videos: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for video in videos:
        groups.setdefault(str(video.get(key) or "—"), []).append(video)
    rows: list[dict[str, Any]] = []
    for name, items in groups.items():
        view_list = [v["views"] for v in items]
        rows.append(
            {
                "name": name,
                "count": len(items),
                "avg_views": round(statistics.mean(view_list), 1) if view_list else 0,
                "median_views": round(statistics.median(view_list), 1) if view_list else 0,
                "total_views": sum(view_list),
            }
        )
    rows.sort(key=lambda r: r["avg_views"], reverse=True)
    return rows


def _fetch_youtube_stats(video_id: str) -> dict[str, int] | None:
    key = (config.YOUTUBE_API_KEYS_LIST[0] if config.YOUTUBE_API_KEYS_LIST else config.YOUTUBE_API_KEY)
    if not video_id or not key:
        return None
    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": video_id, "key": key},
            timeout=20,
        )
        response.raise_for_status()
        items = (response.json() or {}).get("items") or []
        if not items:
            return None
        stats = items[0].get("statistics") or {}
        return {
            "views": int(stats.get("viewCount") or 0),
            "likes": int(stats.get("likeCount") or 0),
            "comments": int(stats.get("commentCount") or 0),
        }
    except Exception:
        return None


def _extract_youtube_id(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return ""
    patterns = [
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{6,})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{6,})",
        r"(?:youtube\.com/watch\?[^ ]*v=)([A-Za-z0-9_-]{6,})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{6,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{6,}", url):
        return url
    return ""


def _now() -> str:
    return datetime.utcnow().isoformat()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _num(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0
