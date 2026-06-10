from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app import config
from app.services.cache_manifest_service import get_cache_status


RULES_PATH = config.STORAGE_TRENDS_DIR.parent / "config" / "source_rules.json"
REPORTS_DIR = config.STORAGE_TRENDS_DIR.parent / "reports"

DEFAULT_RULES: dict[str, Any] = {
    "blocked_title_keywords": [
        "shorts",
        "#shorts",
        "trailer",
        "teaser",
        "gameplay",
        "clipe oficial",
        "music video",
        "official video",
        "lyrics",
    ],
    "preferred_title_keywords": [
        "podcast",
        "entrevista",
        "debate",
        "react",
        "análise",
        "analise",
        "desafio",
        "bastidores",
        "polêmica",
        "polemica",
        "explica",
        "opinião",
        "opiniao",
        "história",
        "historia",
        "relato",
        "perrengue",
        "viagem",
    ],
    "blocked_channels": [],
    "preferred_channels": [],
    "min_duration_seconds": 480,
    "hard_min_duration_seconds": 60,
    "soft_min_duration_seconds": 480,
    "short_video_penalty_threshold_seconds": 180,
    "max_duration_seconds": 10800,
    "avoid_recently_processed_days": 7,
    "min_source_relevance_score": 4.0,
    "minimum_source_score_fast": 4.5,
    "minimum_source_score_deep": 3.5,
}


def load_source_rules() -> dict[str, Any]:
    if not RULES_PATH.exists():
        RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _write_json(RULES_PATH, DEFAULT_RULES)
        return dict(DEFAULT_RULES)
    payload = _load_json(RULES_PATH)
    if not isinstance(payload, dict):
        _write_json(RULES_PATH, DEFAULT_RULES)
        return dict(DEFAULT_RULES)
    rules = dict(DEFAULT_RULES)
    rules.update(payload)
    return rules


def evaluate_source_video(
    video: dict[str, Any],
    *,
    history_data: dict[str, dict[str, Any]] | None = None,
    seen_video_ids: set[str] | None = None,
    allow_recent_reprocess: bool = False,
    rules: dict[str, Any] | None = None,
    minimum_score: float | None = None,
) -> dict[str, Any]:
    rules = rules or load_source_rules()
    history_data = history_data or {}
    seen_video_ids = seen_video_ids or set()
    video_id = str(video.get("video_id") or "")
    title = str(video.get("title") or "")
    channel = str(video.get("channel_title") or video.get("channel") or "")
    text = _normalize(f"{title} {channel}")
    duration = _int(video.get("duration_seconds"))
    published_at = _parse_datetime(video.get("published_at"))
    view_count = _int(video.get("view_count"))
    like_count = _int(video.get("like_count"))
    comment_count = _int(video.get("comment_count"))
    cache = get_cache_status(video_id) if video_id else {}
    record = history_data.get(video_id, {})
    positive: list[str] = []
    negative: list[str] = []
    penalties: list[str] = []
    score = 5.0

    blocked_keyword = _first_keyword(text, rules.get("blocked_title_keywords", []))
    if blocked_keyword:
        reason = _keyword_reason(blocked_keyword)
        return _result(video, score=0.0, accepted=False, reason=reason, positive=positive, negative=[blocked_keyword], penalties=penalties, hard_reject=True)

    if video_id in seen_video_ids:
        return _result(video, score=0.0, accepted=False, reason="duplicate_video", positive=positive, negative=["duplicate_video"], penalties=penalties, hard_reject=True)

    hard_min_duration = _int(rules.get("hard_min_duration_seconds")) or 60
    soft_min_duration = _int(rules.get("soft_min_duration_seconds")) or _int(rules.get("min_duration_seconds")) or 480
    short_penalty_threshold = _int(rules.get("short_video_penalty_threshold_seconds")) or 180
    max_duration = _int(rules.get("max_duration_seconds")) or 10800
    if duration and duration < hard_min_duration:
        return _result(video, score=0.0, accepted=False, reason="duration_too_short", positive=positive, negative=["duration_too_short"], penalties=penalties, hard_reject=True)
    if duration and duration < short_penalty_threshold:
        score -= 2.3
        negative.append("very_short_duration")
        penalties.append("duration_60_to_180")
    elif duration and duration < soft_min_duration:
        score -= 1.25
        negative.append("short_but_possible")
        penalties.append("duration_180_to_480")
    if duration and duration > max_duration:
        strong = _has_keyword(text, rules.get("preferred_title_keywords", []))
        if not strong:
            return _result(video, score=2.0, accepted=False, reason="duration_too_long", positive=positive, negative=["duration_too_long"], penalties=penalties, hard_reject=False)
        score -= 0.8
        negative.append("very_long_but_relevant")
        penalties.append("very_long")

    if not allow_recent_reprocess and _recently_processed(record, cache, rules):
        return _result(video, score=3.0, accepted=False, reason="recently_processed", positive=positive, negative=["recently_processed"], penalties=["recently_processed"], hard_reject=False)

    if cache.get("posts_count") or cache.get("finals_count"):
        return _result(video, score=1.0, accepted=False, reason="already_generated_post", positive=positive, negative=["already_generated_post"], penalties=["already_generated_post"], hard_reject=False)

    preferred_hits = _keyword_hits(text, rules.get("preferred_title_keywords", []))
    if preferred_hits:
        score += min(2.6, 0.55 * len(preferred_hits))
        positive.extend(f"keyword:{hit}" for hit in preferred_hits[:5])
    else:
        score -= 1.1
        negative.append("no_cuttable_keyword")
        penalties.append("no_cuttable_keyword")

    preferred_channel = _first_keyword(_normalize(channel), rules.get("preferred_channels", []))
    if preferred_channel:
        score += 1.2
        positive.append(f"preferred_channel:{preferred_channel}")
    blocked_channel = _first_keyword(_normalize(channel), rules.get("blocked_channels", []))
    if blocked_channel:
        return _result(video, score=0.0, accepted=False, reason="blocked_channel", positive=positive, negative=[blocked_channel], penalties=penalties, hard_reject=True)

    if soft_min_duration <= duration <= max_duration:
        score += 1.0
        positive.append("good_duration")
    if 900 <= duration <= 7200:
        score += 0.5
        positive.append("strong_duration")

    if published_at:
        age_days = max(0, (datetime.now(UTC) - published_at).days)
        if age_days <= 14:
            score += 0.8
            positive.append("recent")
        elif age_days > 365:
            score -= 0.4
            negative.append("old")

    score += _engagement_bonus(view_count, like_count, comment_count, published_at)

    if record.get("source_quality_tier") in {"strong", "good"}:
        score += 0.8
        positive.append("historically_good_source")
    if record.get("source_quality_tier") == "bad_source":
        return _result(video, score=0.0, accepted=False, reason="blocked_source_history", positive=positive, negative=["bad_source"], penalties=penalties, hard_reject=True)

    score = round(max(0.0, min(10.0, score)), 2)
    min_score = float(minimum_score if minimum_score is not None else rules.get("min_source_relevance_score") or 4.0)
    accepted = score >= min_score
    reason = "accepted" if accepted else "low_relevance_score"
    return _result(video, score=score, accepted=accepted, reason=reason, positive=positive, negative=negative, penalties=penalties, hard_reject=False)


def write_source_intelligence_report(
    *,
    discovered: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    dry_run: bool = False,
    mode: str = "discovery",
) -> dict[str, str]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = REPORTS_DIR / f"source_intelligence_{stamp}.json"
    md_path = REPORTS_DIR / f"source_intelligence_{stamp}.md"
    scores = [_float(item.get("source_relevance_score")) for item in accepted + selected]
    scores = [score for score in scores if score is not None]
    rejected_by_reason = Counter(_rejection_reason(item) for item in rejected)
    hard_rejected = sum(1 for item in rejected if bool(item.get("source_filter_hard_reject")))
    soft_rejected = max(0, len(rejected) - hard_rejected)
    fallback_selected = [item for item in selected if item.get("source_filter_fallback")]
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "mode": mode,
        "dry_run": dry_run,
        "latest_discovered_count": len(discovered),
        "latest_accepted_count": len(accepted),
        "latest_rejected_count": len(rejected),
        "latest_hard_rejected_count": hard_rejected,
        "latest_soft_rejected_count": soft_rejected,
        "latest_fallback_used": bool(fallback_selected),
        "latest_fallback_selected_count": len(fallback_selected),
        "latest_rejected_by_reason": dict(rejected_by_reason),
        "latest_average_source_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "latest_selected_video_ids": [str(item.get("video_id") or "") for item in selected if item.get("video_id")],
        "top_selected_sources": _top_sources(selected),
        "top_rejected_examples": _compact_examples(rejected, 12),
        "discovered": _compact_examples(discovered, 100),
        "accepted": _compact_examples(accepted, 100),
        "rejected": _compact_examples(rejected, 100),
    }
    _write_json(json_path, payload)
    md_path.write_text(_markdown_source_report(payload), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def source_intelligence_summary() -> dict[str, Any]:
    payload = _latest_source_report()
    if not payload:
        return {
            "latest_discovered_count": 0,
            "latest_accepted_count": 0,
            "latest_rejected_count": 0,
            "latest_hard_rejected_count": 0,
            "latest_soft_rejected_count": 0,
            "latest_fallback_used": False,
            "latest_fallback_selected_count": 0,
            "latest_rejected_by_reason": {},
            "latest_average_source_score": 0,
            "latest_selected_video_ids": [],
            "best_channels_by_approval_rate": [],
            "best_queries_by_approval_rate": [],
            "worst_rejection_reasons": [],
        }
    rejected_by_reason = payload.get("latest_rejected_by_reason") if isinstance(payload.get("latest_rejected_by_reason"), dict) else {}
    return {
        "latest_discovered_count": _int(payload.get("latest_discovered_count")),
        "latest_accepted_count": _int(payload.get("latest_accepted_count")),
        "latest_rejected_count": _int(payload.get("latest_rejected_count")),
        "latest_hard_rejected_count": _int(payload.get("latest_hard_rejected_count")),
        "latest_soft_rejected_count": _int(payload.get("latest_soft_rejected_count")),
        "latest_fallback_used": bool(payload.get("latest_fallback_used")),
        "latest_fallback_selected_count": _int(payload.get("latest_fallback_selected_count")),
        "latest_rejected_by_reason": rejected_by_reason,
        "latest_average_source_score": _float(payload.get("latest_average_source_score")) or 0,
        "latest_selected_video_ids": payload.get("latest_selected_video_ids") if isinstance(payload.get("latest_selected_video_ids"), list) else [],
        "best_channels_by_approval_rate": _approval_rates("channel_title"),
        "best_queries_by_approval_rate": _approval_rates("query"),
        "worst_rejection_reasons": sorted(
            [{"reason": reason, "count": count} for reason, count in rejected_by_reason.items()],
            key=lambda item: item["count"],
            reverse=True,
        )[:8],
    }


def build_source_quality_audit() -> dict[str, Any]:
    history = _load_json(config.STORAGE_VIDEOS_DIR / "video_history.json")
    history_items = list(history.values()) if isinstance(history, dict) else []
    candidates = _candidate_items()
    reports = _source_reports()
    all_rejected: list[dict[str, Any]] = []
    for report in reports:
        rejected = report.get("rejected")
        if isinstance(rejected, list):
            all_rejected.extend(item for item in rejected if isinstance(item, dict))
    videos_by_id = {str(item.get("video_id") or ""): item for item in history_items if isinstance(item, dict)}
    repeated = _duplicates([str(item.get("video_id") or "") for item in history_items if isinstance(item, dict)])
    status_counts = Counter(str(item.get("status") or "unknown") for item in history_items if isinstance(item, dict))
    blocked_hits = Counter(
        reason for reason in (_rejection_reason(item) for item in all_rejected)
        if reason and reason != "accepted"
    )
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_videos_seen": len(videos_by_id),
        "videos_processed": status_counts.get("done", 0) + status_counts.get("processed", 0),
        "videos_accepted": sum(_int(report.get("latest_accepted_count")) for report in reports),
        "videos_rejected": sum(_int(report.get("latest_rejected_count")) for report in reports),
        "best_channels": _channel_quality(candidates, reverse=True),
        "worst_channels": _channel_quality(candidates, reverse=False),
        "best_queries": _query_quality(candidates),
        "videos_with_high_approval_rate": _video_quality(candidates, reverse=True),
        "videos_with_low_candidate_quality": _video_quality(candidates, reverse=False),
        "repeated_videos": repeated[:100],
        "recently_reprocessed_videos": _recently_reprocessed(history_items),
        "blocked_keyword_hits": dict(blocked_hits),
    }


def _result(
    video: dict[str, Any],
    *,
    score: float,
    accepted: bool,
    reason: str,
    positive: list[str],
    negative: list[str],
    penalties: list[str],
    hard_reject: bool,
) -> dict[str, Any]:
    return {
        **video,
        "source_relevance_score": round(score, 2),
        "source_filter_accepted": accepted,
        "source_filter_reason": reason,
        "source_relevance_positive": positive,
        "source_relevance_negative": negative,
        "source_filter_penalties": penalties,
        "source_filter_hard_reject": hard_reject,
        "already_cached": bool(get_cache_status(str(video.get("video_id") or "")).get("clips_exists")) if video.get("video_id") else False,
    }


def _keyword_reason(keyword: str) -> str:
    if "short" in keyword:
        return "likely_short"
    if keyword in {"trailer", "teaser"}:
        return "likely_trailer"
    if "game" in keyword:
        return "likely_gameplay"
    if "music" in keyword or "clipe" in keyword or "lyrics" in keyword:
        return "music_or_official_clip"
    return "blocked_keyword"


def _recently_processed(record: dict[str, Any], cache: dict[str, Any], rules: dict[str, Any]) -> bool:
    if not (cache.get("transcript_exists") and cache.get("clips_exists")):
        return False
    days = _int(rules.get("avoid_recently_processed_days")) or 7
    for key in ("last_processed_at", "updated_at"):
        parsed = _parse_datetime(record.get(key) or cache.get(key))
        if parsed and datetime.now(UTC) - parsed <= timedelta(days=days):
            return True
    return str(record.get("status") or "") in {"done", "processed"}


def _engagement_bonus(view_count: int, like_count: int, comment_count: int, published_at: datetime | None) -> float:
    if view_count <= 0:
        return 0.0
    age_days = max(1, (datetime.now(UTC) - published_at).days) if published_at else 30
    views_per_day = view_count / age_days
    bonus = 0.0
    if views_per_day >= 10000:
        bonus += 0.7
    elif views_per_day >= 2000:
        bonus += 0.35
    if like_count and view_count and like_count / max(view_count, 1) >= 0.02:
        bonus += 0.25
    if comment_count >= 100:
        bonus += 0.25
    return bonus


def _approval_rates(field: str) -> list[dict[str, Any]]:
    rows = _group_candidate_reviews(field)
    return sorted(rows, key=lambda item: (item["approval_rate"], item["total"]), reverse=True)[:8]


def _group_candidate_reviews(field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in _candidate_items():
        key = str(item.get(field) or item.get("source_query") or "unknown")
        grouped[key].append(item)
    rows = []
    for key, items in grouped.items():
        reviewed = [item for item in items if isinstance(item.get("current_candidate_review"), dict)]
        approved = [
            item for item in reviewed
            if str(item.get("current_candidate_review", {}).get("status") or "") == "approved"
        ]
        rows.append({"name": key, "total": len(items), "approved": len(approved), "approval_rate": round(len(approved) / len(reviewed), 3) if reviewed else 0})
    return rows


def _candidate_items() -> list[dict[str, Any]]:
    payload = _load_json(config.STORAGE_CANDIDATE_QUEUE_DIR / "candidate_review_queue.json")
    return [item for item in payload.get("items", []) if isinstance(item, dict)] if isinstance(payload, dict) else []


def _source_reports() -> list[dict[str, Any]]:
    reports = []
    for path in sorted(REPORTS_DIR.glob("source_intelligence_*.json"), reverse=True):
        payload = _load_json(path)
        if isinstance(payload, dict):
            reports.append(payload)
    return reports


def _latest_source_report() -> dict[str, Any]:
    reports = _source_reports()
    return reports[0] if reports else {}


def _channel_quality(candidates: list[dict[str, Any]], *, reverse: bool) -> list[dict[str, Any]]:
    rows = _group_candidate_reviews("channel_title")
    return sorted(rows, key=lambda item: (item["approval_rate"], item["total"]), reverse=reverse)[:10]


def _query_quality(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(_group_candidate_reviews("query"), key=lambda item: (item["approval_rate"], item["total"]), reverse=True)[:10]


def _video_quality(candidates: list[dict[str, Any]], *, reverse: bool) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[str(item.get("video_id") or "unknown")].append(item)
    rows = []
    for video_id, items in grouped.items():
        reviewed = [item for item in items if isinstance(item.get("current_candidate_review"), dict)]
        approved = [item for item in reviewed if str(item.get("current_candidate_review", {}).get("status") or "") == "approved"]
        rows.append({"video_id": video_id, "total_candidates": len(items), "approved": len(approved), "approval_rate": round(len(approved) / len(reviewed), 3) if reviewed else 0})
    return sorted(rows, key=lambda item: (item["approval_rate"], item["total_candidates"]), reverse=reverse)[:10]


def _recently_reprocessed(items: list[Any]) -> list[str]:
    recent = []
    for item in items:
        if not isinstance(item, dict):
            continue
        processed = _parse_datetime(item.get("last_processed_at") or item.get("updated_at"))
        if processed and datetime.now(UTC) - processed <= timedelta(days=7) and item.get("status") in {"done", "processed"}:
            recent.append(str(item.get("video_id") or ""))
    return [item for item in recent if item][:100]


def _compact_examples(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    keys = (
        "video_id", "title", "channel_title", "duration_seconds", "query", "market", "url",
        "source_relevance_score", "source_filter_reason", "reason", "source_relevance_positive",
        "source_filter_penalties", "source_filter_hard_reject", "source_filter_accepted",
    )
    return [{key: item.get(key) for key in keys if key in item} for item in items[:limit]]


def _top_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = Counter(str(item.get("channel_title") or "unknown") for item in items)
    return [{"channel": channel, "count": count} for channel, count in grouped.most_common(8)]


def _markdown_source_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Source Intelligence Report",
        "",
        f"Generated at: {payload.get('generated_at')}",
        f"Discovered: {payload.get('latest_discovered_count')}",
        f"Accepted: {payload.get('latest_accepted_count')}",
        f"Rejected: {payload.get('latest_rejected_count')}",
        f"Hard rejected: {payload.get('latest_hard_rejected_count')}",
        f"Soft rejected: {payload.get('latest_soft_rejected_count')}",
        f"Fallback used: {payload.get('latest_fallback_used')}",
        f"Fallback selected: {payload.get('latest_fallback_selected_count')}",
        f"Average score: {payload.get('latest_average_source_score')}",
        "",
        "## Rejected by reason",
        "",
    ]
    for reason, count in (payload.get("latest_rejected_by_reason") or {}).items():
        lines.append(f"* {reason}: {count}")
    lines.extend(["", "## Selected", ""])
    for video_id in payload.get("latest_selected_video_ids") or []:
        lines.append(f"* {video_id}")
    lines.extend(["", "## Accepted Examples", ""])
    for item in payload.get("accepted") or []:
        lines.append(
            f"* {item.get('video_id')} | score={item.get('source_relevance_score')} | "
            f"duration={item.get('duration_seconds')} | {item.get('title')}"
        )
    lines.extend(["", "## Top rejected examples", ""])
    for item in payload.get("top_rejected_examples") or []:
        lines.append(
            f"* {item.get('video_id')} | score={item.get('source_relevance_score')} | "
            f"hard={item.get('source_filter_hard_reject')} | reason={_rejection_reason(item)} | "
            f"penalties={', '.join(item.get('source_filter_penalties') or [])} | {item.get('title')}"
        )
    return "\n".join(lines)


def _keyword_hits(text: str, keywords: Any) -> list[str]:
    normalized = _normalize(text)
    return [str(keyword) for keyword in keywords if _normalize(str(keyword)) in normalized]


def _rejection_reason(item: dict[str, Any]) -> str:
    source_reason = str(item.get("source_filter_reason") or "")
    reason = str(item.get("reason") or "")
    if source_reason and source_reason != "accepted":
        return source_reason
    return reason or source_reason or "unknown"


def _first_keyword(text: str, keywords: Any) -> str:
    hits = _keyword_hits(text, keywords)
    return hits[0] if hits else ""


def _has_keyword(text: str, keywords: Any) -> bool:
    return bool(_first_keyword(text, keywords))


def _normalize(value: str) -> str:
    stripped = "".join(
        char for char in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(value for value in values if value)
    return sorted(value for value, count in counts.items() if count > 1)


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
