"""Visual asset acquisition for the render pipeline (0.5.53, Part 3).

For each usable visual_item with no real media, build 2-4 specific English
queries, search Pexels video (then photo) and SCORE the results (vertical 9:16,
resolution, duration, relevance, no repeats) to pick the best clip. Items that
still have no media are flagged ``fallback_visual`` (render draws a visible
gradient) when allowed, or marked ``needs_asset`` with an ``asset_error``.

Records per item: search_queries_attempted, selected_asset_score,
selected_asset_reason, media_type, source_credit. Pure acquisition — callers
persist the result.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import requests

from app import config
from app.services.generation_stock_media_service import (
    pexels_configured,
    pixabay_configured,
    search_met_images,
    search_openverse_images,
    search_pixabay_photos,
    search_pixabay_videos,
    search_stock_media_for_render,
    search_stock_photos_for_render,
    search_wikimedia_images,
    wikimedia_configured,
)
from app.services.generation_football_footage_service import search_football_clips
from app.services.generation_llm_provider_service import generate_ai_image
from app.services.generation_visual_query_service import build_search_queries
from app.services.generation_visual_service import normalize_visual_item


ASSETS_DIR = config.STORAGE_GENERATION_ASSETS_DIR
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
# Stock só é aceito quando é FORTEMENTE relevante; abaixo disso, geramos a imagem
# com Flux (alinhada à cena) em vez de usar um clipe mais ou menos relacionado.
MIN_VIDEO_SCORE = 3.0
TARGET_HEIGHT = config.GENERATION_RENDER_HEIGHT
TARGET_WIDTH = config.GENERATION_RENDER_WIDTH


def has_local_media(item: dict[str, Any]) -> bool:
    raw = str(item.get("media_path") or "")
    return bool(raw) and Path(raw).exists() and Path(raw).is_file()


def has_media(item: dict[str, Any]) -> bool:
    return has_local_media(item) or bool(str(item.get("media_url") or ""))


def usable_items(project: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in project.get("visual_items") or []
        if isinstance(item, dict) and str(item.get("status") or "") != "rejected"
    ]


def acquire_assets(project: dict[str, Any], allow_fallback: bool = False) -> dict[str, Any]:
    pexels = pexels_configured()
    ai_cap = config.GENERATION_MAX_AI_IMAGES_PER_VIDEO if config.GENERATION_ENABLE_AI_IMAGE_FALLBACK else 0
    any_source = pexels or wikimedia_configured() or ai_cap > 0 or _football_mode(project)
    updated: list[dict[str, Any]] = []
    downloaded = 0
    ai_used = 0
    used_ids: set[str] = set()

    for item in usable_items(project):
        current = dict(item)
        if not has_local_media(current) and any_source:
            fetched = _resolve_item_asset(current, project, used_ids, ai_remaining=max(0, ai_cap - ai_used))
            if fetched and has_local_media(fetched):
                downloaded += 1
                current = fetched
                if str(current.get("source") or "") == "generated":
                    ai_used += 1
        updated.append(current)

    for item in updated:
        _classify(item, allow_fallback, pexels)

    normalized = [normalize_visual_item(item, idx + 1) for idx, item in enumerate(updated)]
    media_count = sum(1 for item in normalized if has_media(item))
    fallback_count = sum(1 for item in normalized if item.get("fallback_visual"))
    without_media = sum(1 for item in normalized if not has_media(item) and not item.get("fallback_visual"))
    return {
        "items": normalized,
        "downloaded": downloaded,
        "media_count": media_count,
        "fallback_count": fallback_count,
        "without_media_count": without_media,
        "total": len(normalized),
        "pexels_available": pexels,
    }


def _classify(item: dict[str, Any], allow_fallback: bool, pexels: bool) -> None:
    if has_local_media(item):
        if str(item.get("status") or "") in {"suggestion", "needs_asset", ""}:
            item["status"] = "downloaded"
        item["fallback_visual"] = False
        item["asset_error"] = ""
    elif str(item.get("media_url") or ""):
        item["fallback_visual"] = False
    elif allow_fallback:
        item["fallback_visual"] = True
        if str(item.get("status") or "") in {"suggestion", "needs_asset", ""}:
            item["status"] = "ready"
        if not item.get("asset_error"):
            item["asset_error"] = (
                "sem mídia real: usando fallback visual"
                if not pexels
                else "Pexels sem resultado: usando fallback visual"
            )
        item.setdefault("media_type", "fallback")
    else:
        item["fallback_visual"] = False
        if str(item.get("status") or "") not in {"ready", "downloaded"}:
            item["status"] = "needs_asset"
        if not item.get("asset_error"):
            item["asset_error"] = (
                "configure PEXELS_API_KEY para baixar b-roll"
                if not pexels
                else "Pexels sem resultado para esta query"
            )


# ---------------------------------------------------------------------------
# Per-item resolution
# ---------------------------------------------------------------------------

_HISTORY_NICHES = {"historia", "história", "true crime", "crime", "biografia", "biografias"}
# Distinctive period markers (accent-stripped) — detect a historical topic even
# when the niche is generic (e.g. "curiosidades" for a Cleopatra video).
_PERIOD_MARKERS = (
    "seculo", "antig", "imperador", "imperatriz", "rainha", "farao", "dinastia",
    "medieval", "imperio romano", "roma antiga", "egito antig", "grecia antig",
    "idade media", "a.c", "d.c", "antiguidade",
)


def _strip_accents_lower(value: str) -> str:
    table = str.maketrans("áàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ", "aaaaeeiooouucAAAAEEIOOOUUC")
    return str(value or "").translate(table).lower()


def _video_is_historical(project: dict[str, Any]) -> bool:
    """Whole-video signal: historical niche, any LLM-marked specific scene, or
    period markers in the title/idea/brief. Lets us route generic period scenes
    (e.g. 'ancient queen') to Wikimedia instead of modern stock."""
    if any(h in str(project.get("niche") or "").strip().lower() for h in _HISTORY_NICHES):
        return True
    items = project.get("visual_items") or []
    if any(isinstance(it, dict) and str(it.get("scene_kind") or "").lower() == "specific" for it in items):
        return True
    brief = project.get("research_brief") if isinstance(project.get("research_brief"), dict) else {}
    blob = _strip_accents_lower(
        " ".join(
            [
                str(project.get("title") or ""),
                str(project.get("idea") or ""),
                " ".join(str(f) for f in (brief.get("key_facts") or [])),
            ]
        )
    )
    return any(marker in blob for marker in _PERIOD_MARKERS)


_ARTIFACT_WORDS = (
    "relief", "statue", "bust", "fresco", "mosaic", "painting", "papyrus", "ruins",
    "ruin", "temple", "coin", "manuscript", "sculpture", "tomb", "monument",
    "artifact", "portrait", "carving", "vase", "tablet", "engraving",
)
_GENERIC_REL_WORDS = {
    "ancient", "the", "of", "in", "a", "an", "and", "scene", "view", "people",
    "crowd", "historic", "historical", "old", "classical", "background", "image",
    "modern", "person", "group", "city",
}


def _has_artifact_word(term: str) -> bool:
    t = str(term or "").lower()
    return any(w in t for w in _ARTIFACT_WORDS)


def _theme_entity_words(project: dict[str, Any]) -> set[str]:
    """Meaningful words from the theme (subject + entities + title) used to verify
    a real image is actually tied to the topic (not just the same era)."""
    brief = project.get("research_brief") if isinstance(project.get("research_brief"), dict) else {}
    parts: list[str] = [str(brief.get("subject") or ""), str(project.get("title") or ""), str(project.get("idea") or "")]
    for ent in (brief.get("key_entities") or []):
        parts.append(str(ent))
    words: set[str] = set()
    for token in _normalize(" ".join(parts)).split():
        token = token.strip(".,:;!?()[]\"'")
        if len(token) >= 4 and token not in _GENERIC_REL_WORDS:
            words.add(token)
    return words


def _entity_hit(result: dict[str, Any], entity_words: set[str]) -> bool:
    if not entity_words:
        return False
    haystack = _normalize(f"{result.get('title') or ''} {result.get('description') or ''}")
    return any(word in haystack for word in entity_words)


def _real_image_ok(score: tuple[int, float, float], entity_words: set[str]) -> bool:
    """Accept a real image only if it's actually tied to the theme: when the topic
    has named entities, require an entity match (score[0]==1); otherwise accept on
    strong relevance (score[1] >= 2). Borderline -> falls through to on-theme AI."""
    ent, rel, _quality = score
    if entity_words:
        return ent == 1
    return rel >= 2


def _relevance(result: dict[str, Any], term: str) -> int:
    """Meaningful term-overlap between the search term and the result text
    (ignores generic words) — so on-topic beats merely pretty."""
    haystack = _normalize(f"{result.get('title') or ''} {result.get('description') or ''}")
    hits = 0
    for word in str(term or "").lower().split():
        if len(word) < 3 or word in _GENERIC_REL_WORDS:
            continue
        if word in haystack:
            hits += 1
    return hits


def _prefer_specific(item: dict[str, Any], project: dict[str, Any]) -> bool:
    """Specific scenes (or any scene in a historical video) are better served by
    real encyclopedic images (Wikimedia) than generic, often-modern stock."""
    if str(item.get("scene_kind") or "").strip().lower() == "specific":
        return True
    return _video_is_historical(project)


def _try_real_image(
    item: dict[str, Any],
    project: dict[str, Any],
    subject: str,
    queries: list[str],
    used_ids: set[str],
) -> bool:
    """Pick the best REAL image (Wikimedia/Openverse/Met) for a named subject,
    entity-gated, and attach it. Returns True on success.

    Tries the subject + period-flavored queries; artifact-style terms first (that's
    what museums hold). Ranks tied-to-theme-entity FIRST, then relevance, then quality.
    """
    terms: list[str] = []
    for term in [subject, *queries]:
        term = str(term or "").strip()
        if term and term not in terms:
            terms.append(term)
    terms.sort(key=lambda t: 0 if _has_artifact_word(t) else 1)

    entity_words = _theme_entity_words(project)
    w_best, w_score, w_term = None, (-1, -1.0, -1.0), subject
    for idx, term in enumerate(terms[:4]):
        for result in _real_image_results(term, include_met=(idx == 0)):
            media_id = str(result.get("media_id") or "")
            if media_id and media_id in used_ids:
                continue
            ent = 1 if _entity_hit(result, entity_words) else 0
            rel = _relevance(result, term)
            quality, _reason = _score(result, term)
            rank = (ent, float(rel), float(quality))
            if rank > w_score:
                w_best, w_score, w_term = result, rank, term
        if w_best is not None and _real_image_ok(w_score, entity_words):
            break
    # Entity gate: if the topic has named entities, the real image MUST contain one.
    if w_best is not None and _real_image_ok(w_score, entity_words):
        return _apply_asset(item, w_best, "photo", w_score[2], f"real:{w_term}", w_term, used_ids)
    return False


def _football_mode(project: dict[str, Any]) -> bool:
    """Football footage source is opt-in per project via footage_source=football
    (set by the Futebol studio). Explicit only — never auto-triggers on niche."""
    return str(project.get("footage_source") or "").strip().lower() == "football"


def _football_query(project: dict[str, Any]) -> str:
    """One query per video — the main subject (player/team) — so every item pulls
    from the same downloaded sources (coherent, cache-friendly)."""
    brief = project.get("research_brief") if isinstance(project.get("research_brief"), dict) else {}
    entities = brief.get("key_entities") or []
    for cand in (brief.get("subject"), entities[0] if entities else None, project.get("title"), project.get("idea")):
        s = str(cand or "").strip()
        if s:
            return f"{s} football" if "football" not in s.lower() and "futebol" not in s.lower() else s
    return "football highlights"


def _try_football(item: dict[str, Any], project: dict[str, Any], used_ids: set[str]) -> bool:
    query = _football_query(project)
    try:
        results = search_football_clips(query, want=8)
    except Exception:
        results = []
    best: dict[str, Any] | None = None
    best_score = -1.0
    best_reason = ""
    for result in results:
        media_id = str(result.get("media_id") or "")
        if media_id and media_id in used_ids:
            continue
        score, reason = _score(result, query)
        if score > best_score:
            best, best_score, best_reason = result, score, reason
    if best is None:
        return False
    return _apply_local_asset(item, best, "video", best_score, best_reason or "football", query, used_ids)


def _resolve_item_asset(
    item: dict[str, Any], project: dict[str, Any], used_ids: set[str], ai_remaining: int = 0
) -> dict[str, Any] | None:
    queries = build_search_queries(item, project)
    item["search_queries_attempted"] = queries

    # FOOTBALL MODE: real football footage (yt-dlp) takes priority. Stock/AI can't
    # produce named players (Messi/Mbappé), so this is the only relevant source.
    # Falls through to the normal sources if no clip is found, so it still renders.
    if _football_mode(project):
        if _try_football(item, project, used_ids):
            return item

    prefer_specific = _prefer_specific(item, project)
    subject = str(item.get("wiki_subject") or "").strip()
    if not subject and prefer_specific and queries:
        subject = queries[0]
    real_sources = wikimedia_configured() or config.GENERATION_ENABLE_OPENVERSE or config.GENERATION_ENABLE_MET
    has_real_subject = bool(subject and prefer_specific and real_sources)

    # EXCEPTION: a real, MODERN, photographable person/team (e.g. Pelé, Messi, a
    # national team) → use the REAL photo FIRST. Flux would invent a fake face.
    # Period/ancient subjects (no real photo exists) skip this and go to Flux.
    person_first = has_real_subject and not _is_period_topic(project)
    if person_first and _try_real_image(item, project, subject, queries, used_ids):
        return item

    # PRIMARY SOURCE: Runware/Flux — generate the scene aligned to this line.
    if ai_remaining > 0:
        if _apply_ai_image(item, project, "ai_generated"):
            return item

    # SECONDARY SOURCE: a REAL image from Wikimedia/Openverse/Met (when Flux is
    # capped/unavailable), best for specific named subjects (e.g. a Nero bust).
    if has_real_subject and not person_first:
        if _try_real_image(item, project, subject, queries, used_ids):
            return item

    # LAST RESORT: stock (Pexels/Pixabay) — only when Flux and Wikimedia both
    # produced nothing. Requires a strong relevance score (MIN_VIDEO_SCORE).
    best: dict[str, Any] | None = None
    best_score = -1.0
    best_reason = ""
    best_query = ""

    for query in queries:
        results = _video_results(query)
        for result in results:
            media_id = str(result.get("media_id") or "")
            if media_id and media_id in used_ids:
                continue
            score, reason = _score(result, query)
            if score > best_score:
                best, best_score, best_reason, best_query = result, score, reason, query
        if best is not None and best_score >= MIN_VIDEO_SCORE + 2:
            break  # already great, stop searching

    if best is not None and best_score >= MIN_VIDEO_SCORE:
        if _apply_asset(item, best, "video", best_score, best_reason, best_query, used_ids):
            return item

    # Photo fallback — only a GOOD (relevant) photo. Weak matches go to AI below
    # for better alignment with the narration.
    for query in queries[:2]:
        photos = _photo_results(query)
        for result in photos:
            media_id = str(result.get("media_id") or "")
            if media_id and media_id in used_ids:
                continue
            score, reason = _score(result, query)
            if score >= MIN_VIDEO_SCORE:
                if _apply_asset(item, result, "photo", score, reason, query, used_ids):
                    return item

    # Even a low-score video beats a blank screen (Flux + Wikimedia already failed).
    if best is not None:
        if _apply_asset(item, best, "video", best_score, best_reason or "low_score", best_query, used_ids):
            return item

    item["asset_error"] = "sem resultado em stock/wikimedia"
    return None


def _image_prompt(item: dict[str, Any], project: dict[str, Any]) -> str:
    base = (
        str(item.get("scene_en") or "").strip()
        or str(item.get("description") or "").strip()
        or str(item.get("query") or "").strip()
        or str(project.get("title") or "").strip()
    )
    base_low = base.lower()

    # Anchor the scene in its real subject/entities so the image matches the
    # narration — only for SPECIFIC scenes (don't force a name onto generic mood shots).
    anchor = ""
    is_specific = (
        str(item.get("scene_kind") or "").strip().lower() == "specific"
        or bool(str(item.get("wiki_subject") or "").strip())
    )
    if is_specific:
        brief = project.get("research_brief") if isinstance(project.get("research_brief"), dict) else {}
        names: list[str] = []
        subject = str(item.get("wiki_subject") or brief.get("subject") or "").strip()
        if subject and subject.lower() not in base_low:
            names.append(subject)
        for entity in (brief.get("key_entities") or [])[:3]:
            ent = str(entity or "").strip()
            if ent and ent.lower() not in base_low and ent.lower() not in " ".join(names).lower():
                names.append(ent)
        if names:
            anchor = ", featuring " + ", ".join(names[:2])

    # A persona/studio can pin the visual style (e.g. "dark, noir" for crime).
    persona_style = str(project.get("visual_style") or "").strip()
    blob = f"{project.get('niche') or ''} {project.get('title') or ''} {project.get('idea') or ''}".lower()
    if persona_style:
        style = f", {persona_style}"
    elif "anime" in blob:
        style = ", anime style illustration, vibrant"
    elif _is_period_topic(project):
        style = ", historically accurate, period-accurate setting and clothing, realistic, cinematic lighting"
    else:
        style = ", cinematic, photorealistic"
    quality = ", highly detailed, sharp focus, dramatic composition, vertical 9:16 format"
    return f"{base}{anchor}{style}{quality}".strip()


def _is_period_topic(project: dict[str, Any]) -> bool:
    """Strict 'past era' check for the AI image STYLE (so a modern 2026 match
    isn't rendered as 'historically accurate'). Unlike _video_is_historical,
    this ignores the 'any specific scene' signal."""
    if any(h in str(project.get("niche") or "").strip().lower() for h in _HISTORY_NICHES):
        return True
    brief = project.get("research_brief") if isinstance(project.get("research_brief"), dict) else {}
    blob = _strip_accents_lower(
        " ".join([str(project.get("title") or ""), str(project.get("idea") or ""),
                  " ".join(str(f) for f in (brief.get("key_facts") or []))])
    )
    return any(marker in blob for marker in _PERIOD_MARKERS)


def _apply_ai_image(item: dict[str, Any], project: dict[str, Any], reason: str) -> bool:
    """Generate a scene-aligned image (Runware/Flux first, OpenAI last resort) and
    attach it to the item. Returns True on success."""
    prompt = _image_prompt(item, project)
    local = _save_generated_image(generate_ai_image(prompt))
    if not local:
        return False
    item.update(
        {
            "source": "generated", "license_lane": "safe", "media_url": "",
            "media_path": str(local), "media_type": "image", "status": "downloaded",
            "asset_error": "", "fallback_visual": False, "selected_asset_score": 0.0,
            "selected_asset_reason": reason, "selected_query": prompt[:80],
            "source_credit": "AI generated",
        }
    )
    return True


def _save_generated_image(data: bytes | None) -> Path | None:
    if not data or len(data) < 1024:
        return None
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSETS_DIR / f"ai_{hashlib.md5(data).hexdigest()[:20]}.png"
    try:
        path.write_bytes(data)
    except OSError:
        return None
    return path if path.exists() and path.stat().st_size > 1024 else None


def _apply_asset(
    item: dict[str, Any],
    result: dict[str, Any],
    media_type: str,
    score: float,
    reason: str,
    query: str,
    used_ids: set[str],
) -> bool:
    url = str(result.get("media_url") or "")
    if not url:
        return False
    local = _download(url)
    if not local:
        item["asset_error"] = "falha ao baixar asset"
        return False
    media_id = str(result.get("media_id") or "")
    if media_id:
        used_ids.add(media_id)
    src = str(result.get("source") or "pexels")
    item.update(
        {
            "source": src,
            "license_lane": str(result.get("license_lane") or src),
            "media_url": url,
            "thumbnail_url": str(result.get("thumbnail_url") or item.get("thumbnail_url") or ""),
            "media_path": str(local),
            "status": "downloaded",
            "asset_error": "",
            "fallback_visual": False,
            "media_type": media_type,
            "selected_asset_score": round(float(score), 2),
            "selected_asset_reason": reason,
            "selected_query": query,
            "source_credit": str(result.get("photographer") or result.get("credit") or ""),
        }
    )
    return True


def _apply_local_asset(
    item: dict[str, Any],
    result: dict[str, Any],
    media_type: str,
    score: float,
    reason: str,
    query: str,
    used_ids: set[str],
) -> bool:
    """Attach an already-local clip (e.g. football footage) without an HTTP
    download. Mirrors _apply_asset's bookkeeping."""
    raw = str(result.get("media_path") or "")
    path = Path(raw)
    if not raw or not path.exists() or not path.is_file():
        return False
    media_id = str(result.get("media_id") or "")
    if media_id:
        used_ids.add(media_id)
    src = str(result.get("source") or "youtube")
    item.update(
        {
            "source": src,
            "license_lane": str(result.get("license_lane") or "review"),
            "media_url": "",
            "thumbnail_url": str(result.get("thumbnail_url") or item.get("thumbnail_url") or ""),
            "media_path": raw,
            "status": "downloaded",
            "asset_error": "",
            "fallback_visual": False,
            "media_type": media_type,
            "selected_asset_score": round(float(score), 2),
            "selected_asset_reason": reason,
            "selected_query": query,
            "source_credit": "",
        }
    )
    return True


def _score(result: dict[str, Any], query: str) -> tuple[float, str]:
    width = int(result.get("width") or 0)
    height = int(result.get("height") or 0)
    duration = float(result.get("duration") or 0)
    score = 0.0
    reasons: list[str] = []
    if height >= width and height > 0:
        score += 3.0
        reasons.append("vertical")
    if height >= TARGET_HEIGHT and width >= TARGET_WIDTH:
        score += 2.0
        reasons.append("hi-res")
    elif height >= 1280:
        score += 1.0
        reasons.append("md-res")
    if duration >= 4.0:
        score += 1.0
        reasons.append("good-length")
    elif 0 < duration < 2.0:
        score -= 0.5
        reasons.append("short")
    # Relevance: query terms appearing in the result title/url slug.
    haystack = _normalize(f"{result.get('title') or ''} {result.get('description') or ''}")
    hits = sum(1 for term in query.split() if term and term in haystack)
    if hits:
        score += 0.5 * hits
        reasons.append(f"relevance+{hits}")
    return score, ",".join(reasons) or "low"


# ---------------------------------------------------------------------------
# Pexels helpers
# ---------------------------------------------------------------------------

def _video_results(query: str) -> list[dict[str, Any]]:
    """Stock video: Pexels + Pixabay."""
    results: list[dict[str, Any]] = []
    if pexels_configured():
        response = search_stock_media_for_render(query, "portrait", per_page=8)
        results.extend(r for r in (response.get("results") or []) if isinstance(r, dict))
    if pixabay_configured():
        pix = search_pixabay_videos(query, per_page=6)
        results.extend(r for r in (pix.get("results") or []) if isinstance(r, dict))
    return results


def _photo_results(query: str) -> list[dict[str, Any]]:
    """Multi-source generic still images: Pexels + Pixabay + Openverse."""
    results: list[dict[str, Any]] = []
    if pexels_configured():
        response = search_stock_photos_for_render(query, "portrait", per_page=8)
        results.extend(r for r in (response.get("results") or []) if isinstance(r, dict))
    if pixabay_configured():
        pix = search_pixabay_photos(query, per_page=6)
        results.extend(r for r in (pix.get("results") or []) if isinstance(r, dict))
    if config.GENERATION_ENABLE_OPENVERSE:
        ov = search_openverse_images(query, per_page=6)
        results.extend(r for r in (ov.get("results") or []) if isinstance(r, dict))
    return results


def _real_image_results(term: str, include_met: bool) -> list[dict[str, Any]]:
    """Real/encyclopedic images for specific scenes: Wikimedia + Openverse +
    (optionally) The Met. Met is a slow 2-step API, so only query it once."""
    results: list[dict[str, Any]] = []
    if wikimedia_configured():
        results.extend(r for r in (search_wikimedia_images(term, per_page=config.GENERATION_WIKIMEDIA_MAX_RESULTS).get("results") or []) if isinstance(r, dict))
    if config.GENERATION_ENABLE_OPENVERSE:
        results.extend(r for r in (search_openverse_images(term, per_page=4).get("results") or []) if isinstance(r, dict))
    if include_met and config.GENERATION_ENABLE_MET:
        results.extend(r for r in (search_met_images(term, per_page=4).get("results") or []) if isinstance(r, dict))
    return results


def _download(url: str) -> Path | None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSETS_DIR / f"{_hash(url)}{_extension(url)}"
    if path.exists() and path.stat().st_size > 1024:
        return path
    try:
        # User-Agent is required by Wikimedia (403 without it) and harmless elsewhere.
        with requests.get(
            url, stream=True, timeout=90,
            headers={"User-Agent": "DarkFlow/1.0 (generation pipeline; contact: local)"},
        ) as response:
            response.raise_for_status()
            with path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=262144):
                    if chunk:
                        file.write(chunk)
    except Exception:
        if path.exists():
            path.unlink(missing_ok=True)
        return None
    if path.exists() and path.stat().st_size > 1024:
        return path
    return None


def _extension(url: str) -> str:
    match = re.search(r"\.([a-zA-Z0-9]{2,4})(?:\?|$)", url)
    if match:
        ext = "." + match.group(1).lower()
        if ext in IMAGE_EXTENSIONS or ext in VIDEO_EXTENSIONS:
            return ext
    return ".jpg" if "images.pexels" in url else ".mp4"


def _hash(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:20]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).lower().strip()
