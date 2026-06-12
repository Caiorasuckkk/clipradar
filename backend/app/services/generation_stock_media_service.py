from __future__ import annotations

from typing import Any

import requests

from app import config


def get_stock_provider_status() -> dict[str, Any]:
    provider = config.GENERATION_VISUAL_PROVIDER if config.GENERATION_VISUAL_PROVIDER in {"local", "pexels"} else "local"
    pexels_available = bool(config.PEXELS_API_KEY) and config.GENERATION_ENABLE_STOCK_SEARCH
    return {
        "provider": provider,
        "available": provider == "pexels" and pexels_available,
        "pexels_configured": bool(config.PEXELS_API_KEY),
        "stock_search_enabled": bool(config.GENERATION_ENABLE_STOCK_SEARCH),
        "max_results": config.GENERATION_MAX_STOCK_RESULTS,
    }


def search_stock_media(query: str, orientation: str = "portrait") -> dict[str, Any]:
    status = get_stock_provider_status()
    if not status["available"]:
        return {
            "provider": status["provider"],
            "available": False,
            "fallback_used": True,
            "results": [],
        }
    try:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={
                "query": query,
                "orientation": orientation or "portrait",
                "per_page": max(1, min(20, int(config.GENERATION_MAX_STOCK_RESULTS))),
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        videos = payload.get("videos", []) if isinstance(payload, dict) else []
        return {
            "provider": "pexels",
            "available": True,
            "fallback_used": False,
            "results": [normalize_pexels_result(item) for item in videos if isinstance(item, dict)],
        }
    except Exception as error:
        return {
            "provider": "pexels",
            "available": False,
            "fallback_used": True,
            "error_message": str(error),
            "results": [],
        }


def normalize_pexels_result(result: dict[str, Any]) -> dict[str, Any]:
    files = result.get("video_files") if isinstance(result.get("video_files"), list) else []
    pictures = result.get("video_pictures") if isinstance(result.get("video_pictures"), list) else []
    best_file = _best_video_file(files)
    thumbnail = ""
    if pictures:
        first = pictures[0]
        if isinstance(first, dict):
            thumbnail = str(first.get("picture") or "")
    return {
        "media_id": str(result.get("id") or ""),
        "source": "pexels",
        "title": str(result.get("url") or "Pexels video"),
        "description": str(result.get("url") or ""),
        "thumbnail_url": thumbnail,
        "media_url": str(best_file.get("link") or ""),
        "photographer": str(result.get("user", {}).get("name") or "") if isinstance(result.get("user"), dict) else "",
        "credit": str(result.get("user", {}).get("url") or "") if isinstance(result.get("user"), dict) else "",
        "license_lane": "safe",
        "width": int(best_file.get("width") or result.get("width") or 0),
        "height": int(best_file.get("height") or result.get("height") or 0),
        "duration": float(result.get("duration") or 0),
    }


def _best_video_file(files: list[Any]) -> dict[str, Any]:
    candidates = [item for item in files if isinstance(item, dict) and item.get("link")]
    if not candidates:
        return {}
    portrait = [item for item in candidates if int(item.get("height") or 0) >= int(item.get("width") or 0)]
    pool = portrait or candidates
    return sorted(pool, key=lambda item: int(item.get("height") or 0), reverse=True)[0]
