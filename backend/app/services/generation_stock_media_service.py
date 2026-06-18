from __future__ import annotations

import re
from typing import Any

import requests

from app import config


_WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
_WIKIMEDIA_UA = "DarkFlow/1.0 (generation pipeline; contact: local)"
_WIKIMEDIA_OK_MIME = {"image/jpeg", "image/png", "image/webp"}


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


def pexels_configured() -> bool:
    return bool(config.PEXELS_API_KEY)


def _pexels_request(query: str, orientation: str, per_page: int) -> dict[str, Any]:
    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": config.PEXELS_API_KEY},
        params={
            "query": query,
            "orientation": orientation or "portrait",
            "per_page": max(1, min(20, int(per_page))),
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
        return _pexels_request(query, orientation, config.GENERATION_MAX_STOCK_RESULTS)
    except Exception as error:
        return {
            "provider": "pexels",
            "available": False,
            "fallback_used": True,
            "error_message": str(error),
            "results": [],
        }


def search_stock_media_for_render(query: str, orientation: str = "portrait", per_page: int = 5) -> dict[str, Any]:
    """Pexels VIDEO search used by the render asset pipeline. Only requires a key
    (independent of the GENERATION_ENABLE_STOCK_SEARCH UI flag)."""
    if not config.PEXELS_API_KEY:
        return {"provider": "pexels", "available": False, "fallback_used": True, "results": []}
    try:
        return _pexels_request(query, orientation, per_page)
    except Exception as error:
        return {
            "provider": "pexels",
            "available": False,
            "fallback_used": True,
            "error_message": str(error),
            "results": [],
        }


def search_stock_photos_for_render(query: str, orientation: str = "portrait", per_page: int = 5) -> dict[str, Any]:
    """Pexels PHOTO search — fallback when no good video clip is found."""
    if not config.PEXELS_API_KEY:
        return {"provider": "pexels", "available": False, "fallback_used": True, "results": []}
    try:
        response = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={
                "query": query,
                "orientation": orientation or "portrait",
                "per_page": max(1, min(20, int(per_page))),
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        photos = payload.get("photos", []) if isinstance(payload, dict) else []
        return {
            "provider": "pexels",
            "available": True,
            "fallback_used": False,
            "results": [normalize_pexels_photo(item) for item in photos if isinstance(item, dict)],
        }
    except Exception as error:
        return {
            "provider": "pexels",
            "available": False,
            "fallback_used": True,
            "error_message": str(error),
            "results": [],
        }


def wikimedia_configured() -> bool:
    return bool(config.GENERATION_ENABLE_WIKIMEDIA)


def search_wikimedia_images(query: str, per_page: int = 6) -> dict[str, Any]:
    """Free image search on Wikimedia Commons (no API key). Great for history,
    real people, places and events that stock libraries don't have. Most files
    are CC/public-domain — safe to use with attribution."""
    if not config.GENERATION_ENABLE_WIKIMEDIA or not str(query or "").strip():
        return {"provider": "wikimedia", "available": False, "fallback_used": True, "results": []}
    try:
        response = requests.get(
            _WIKIMEDIA_API,
            headers={"User-Agent": _WIKIMEDIA_UA},
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": f"{query} filetype:bitmap",
                "gsrnamespace": "6",
                "gsrlimit": max(1, min(20, int(per_page))),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": "1080",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        pages = (payload.get("query", {}) or {}).get("pages", {}) if isinstance(payload, dict) else {}
        results: list[dict[str, Any]] = []
        for page in (pages.values() if isinstance(pages, dict) else []):
            if not isinstance(page, dict):
                continue
            normalized = normalize_wikimedia_result(page)
            if normalized:
                results.append(normalized)
        return {"provider": "wikimedia", "available": True, "fallback_used": False, "results": results}
    except Exception as error:
        return {
            "provider": "wikimedia",
            "available": False,
            "fallback_used": True,
            "error_message": str(error),
            "results": [],
        }


def normalize_wikimedia_result(page: dict[str, Any]) -> dict[str, Any] | None:
    info_list = page.get("imageinfo") if isinstance(page.get("imageinfo"), list) else []
    info = info_list[0] if info_list and isinstance(info_list[0], dict) else {}
    if not info:
        return None
    mime = str(info.get("mime") or "").lower()
    if mime and mime not in _WIKIMEDIA_OK_MIME:
        return None
    media_url = str(info.get("thumburl") or info.get("url") or "")
    if not media_url:
        return None
    meta = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
    description = _strip_html(_meta_value(meta, "ImageDescription")) or _clean_title(str(page.get("title") or ""))
    artist = _strip_html(_meta_value(meta, "Artist"))
    license_name = _meta_value(meta, "LicenseShortName")
    return {
        "media_id": f"wikimedia_{page.get('pageid') or ''}",
        "source": "wikimedia",
        "media_type": "photo",
        "title": _clean_title(str(page.get("title") or "")),
        "description": description,
        "thumbnail_url": media_url,
        "media_url": media_url,
        "photographer": artist,
        "credit": " ".join(part for part in [artist, license_name] if part).strip(),
        "license_lane": "wikimedia",
        "width": int(info.get("thumbwidth") or info.get("width") or 0),
        "height": int(info.get("thumbheight") or info.get("height") or 0),
        "duration": 0.0,
    }


def _meta_value(meta: dict[str, Any], key: str) -> str:
    entry = meta.get(key) if isinstance(meta, dict) else None
    if isinstance(entry, dict):
        return str(entry.get("value") or "").strip()
    return ""


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def _clean_title(value: str) -> str:
    text = re.sub(r"^File:", "", str(value or "")).strip()
    return re.sub(r"\.[a-zA-Z0-9]{2,4}$", "", text).replace("_", " ").strip()


# ---------------------------------------------------------------------------
# Pixabay (free key) — generic stock photos + videos, commercial, no attribution
# ---------------------------------------------------------------------------

def pixabay_configured() -> bool:
    return bool(config.GENERATION_ENABLE_PIXABAY and config.PIXABAY_API_KEY)


def search_pixabay_photos(query: str, per_page: int = 6) -> dict[str, Any]:
    if not pixabay_configured() or not str(query or "").strip():
        return {"provider": "pixabay", "available": False, "fallback_used": True, "results": []}
    try:
        response = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": config.PIXABAY_API_KEY, "q": query, "image_type": "photo",
                "orientation": "vertical", "per_page": max(3, min(20, int(per_page))),
                "safesearch": "true",
            },
            timeout=20,
        )
        response.raise_for_status()
        hits = (response.json() or {}).get("hits", [])
        return {"provider": "pixabay", "available": True, "fallback_used": False,
                "results": [_normalize_pixabay_photo(h) for h in hits if isinstance(h, dict)]}
    except Exception as error:
        return {"provider": "pixabay", "available": False, "fallback_used": True, "error_message": str(error), "results": []}


def search_pixabay_videos(query: str, per_page: int = 6) -> dict[str, Any]:
    if not pixabay_configured() or not str(query or "").strip():
        return {"provider": "pixabay", "available": False, "fallback_used": True, "results": []}
    try:
        response = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": config.PIXABAY_API_KEY, "q": query, "per_page": max(3, min(20, int(per_page))), "safesearch": "true"},
            timeout=20,
        )
        response.raise_for_status()
        hits = (response.json() or {}).get("hits", [])
        return {"provider": "pixabay", "available": True, "fallback_used": False,
                "results": [_normalize_pixabay_video(h) for h in hits if isinstance(h, dict)]}
    except Exception as error:
        return {"provider": "pixabay", "available": False, "fallback_used": True, "error_message": str(error), "results": []}


def _normalize_pixabay_photo(h: dict[str, Any]) -> dict[str, Any]:
    tags = str(h.get("tags") or "")
    return {
        "media_id": f"pixabay_{h.get('id') or ''}", "source": "pixabay", "media_type": "photo",
        "title": tags, "description": tags,
        "thumbnail_url": str(h.get("webformatURL") or ""),
        "media_url": str(h.get("largeImageURL") or h.get("webformatURL") or ""),
        "photographer": str(h.get("user") or ""), "credit": str(h.get("user") or ""),
        "license_lane": "pixabay", "width": int(h.get("imageWidth") or 0), "height": int(h.get("imageHeight") or 0),
        "duration": 0.0,
    }


def _normalize_pixabay_video(h: dict[str, Any]) -> dict[str, Any]:
    videos = h.get("videos") if isinstance(h.get("videos"), dict) else {}
    best = videos.get("large") or videos.get("medium") or videos.get("small") or videos.get("tiny") or {}
    return {
        "media_id": f"pixabay_{h.get('id') or ''}", "source": "pixabay", "media_type": "video",
        "title": str(h.get("tags") or ""), "description": str(h.get("tags") or ""),
        "thumbnail_url": "", "media_url": str(best.get("url") or ""),
        "photographer": str(h.get("user") or ""), "credit": str(h.get("user") or ""),
        "license_lane": "pixabay", "width": int(best.get("width") or 0), "height": int(best.get("height") or 0),
        "duration": float(h.get("duration") or 0),
    }


# ---------------------------------------------------------------------------
# Openverse (no key) — millions of CC images; some need attribution
# ---------------------------------------------------------------------------

def search_openverse_images(query: str, per_page: int = 6) -> dict[str, Any]:
    if not config.GENERATION_ENABLE_OPENVERSE or not str(query or "").strip():
        return {"provider": "openverse", "available": False, "fallback_used": True, "results": []}
    try:
        response = requests.get(
            "https://api.openverse.org/v1/images/",
            headers={"User-Agent": _WIKIMEDIA_UA},
            params={"q": query, "license_type": "commercial", "page_size": max(1, min(20, int(per_page)))},
            timeout=20,
        )
        response.raise_for_status()
        results = (response.json() or {}).get("results", [])
        return {"provider": "openverse", "available": True, "fallback_used": False,
                "results": [_normalize_openverse(r) for r in results if isinstance(r, dict) and r.get("url")]}
    except Exception as error:
        return {"provider": "openverse", "available": False, "fallback_used": True, "error_message": str(error), "results": []}


def _normalize_openverse(r: dict[str, Any]) -> dict[str, Any]:
    creator = str(r.get("creator") or "")
    lic = str(r.get("license") or "").upper()
    return {
        "media_id": f"openverse_{r.get('id') or ''}", "source": "openverse", "media_type": "photo",
        "title": str(r.get("title") or ""), "description": str(r.get("title") or ""),
        "thumbnail_url": str(r.get("thumbnail") or r.get("url") or ""), "media_url": str(r.get("url") or ""),
        "photographer": creator, "credit": " ".join(p for p in [creator, lic] if p).strip(),
        "license_lane": "openverse", "width": int(r.get("width") or 0), "height": int(r.get("height") or 0),
        "duration": 0.0,
    }


# ---------------------------------------------------------------------------
# The Met Museum Open Access (no key) — public-domain art/artifacts
# ---------------------------------------------------------------------------

def search_met_images(query: str, per_page: int = 4) -> dict[str, Any]:
    if not config.GENERATION_ENABLE_MET or not str(query or "").strip():
        return {"provider": "met", "available": False, "fallback_used": True, "results": []}
    try:
        search = requests.get(
            "https://collectionapi.metmuseum.org/public/collection/v1/search",
            params={"q": query, "hasImages": "true"},
            timeout=20,
        )
        search.raise_for_status()
        ids = (search.json() or {}).get("objectIDs") or []
        results: list[dict[str, Any]] = []
        for object_id in ids[: max(1, min(10, int(per_page) * 2))]:
            try:
                obj = requests.get(
                    f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}",
                    timeout=15,
                ).json()
            except Exception:
                continue
            if not isinstance(obj, dict) or not obj.get("isPublicDomain"):
                continue
            image = str(obj.get("primaryImage") or obj.get("primaryImageSmall") or "")
            if not image:
                continue
            artist = str(obj.get("artistDisplayName") or "")
            results.append(
                {
                    "media_id": f"met_{object_id}", "source": "met", "media_type": "photo",
                    "title": str(obj.get("title") or ""),
                    "description": " ".join(p for p in [str(obj.get("title") or ""), str(obj.get("objectName") or ""), str(obj.get("culture") or "")] if p),
                    "thumbnail_url": str(obj.get("primaryImageSmall") or image), "media_url": image,
                    "photographer": artist, "credit": " ".join(p for p in [artist, "The Met (Public Domain)"] if p),
                    "license_lane": "public_domain", "width": 0, "height": 0, "duration": 0.0,
                }
            )
            if len(results) >= int(per_page):
                break
        return {"provider": "met", "available": True, "fallback_used": False, "results": results}
    except Exception as error:
        return {"provider": "met", "available": False, "fallback_used": True, "error_message": str(error), "results": []}


def normalize_pexels_photo(result: dict[str, Any]) -> dict[str, Any]:
    src = result.get("src") if isinstance(result.get("src"), dict) else {}
    media_url = str(src.get("portrait") or src.get("large2x") or src.get("large") or src.get("original") or "")
    return {
        "media_id": str(result.get("id") or ""),
        "source": "pexels",
        "media_type": "photo",
        "title": str(result.get("alt") or "Pexels photo"),
        "description": str(result.get("alt") or ""),
        "thumbnail_url": str(src.get("medium") or src.get("small") or media_url),
        "media_url": media_url,
        "photographer": str(result.get("photographer") or ""),
        "credit": str(result.get("photographer_url") or result.get("url") or ""),
        "license_lane": "pexels",
        "width": int(result.get("width") or 0),
        "height": int(result.get("height") or 0),
        "duration": 0.0,
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
