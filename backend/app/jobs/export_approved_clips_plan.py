from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app import config


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-rating", type=float, default=4)
    parser.add_argument("--include-rating-3", action="store_true")
    parser.add_argument("--include-diagnostics", action="store_true")
    parser.add_argument("--video-id")
    parser.add_argument("--reason")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    min_rating = 3 if args.include_rating_3 else args.min_rating
    allowed_statuses = {"approved", "needs_adjustment"} if args.include_rating_3 else {"approved"}
    items = [
        _plan_item(item)
        for item in _iter_reviewed_clips(
            min_rating=min_rating,
            allowed_statuses=allowed_statuses,
            include_diagnostics=args.include_diagnostics,
            video_id=args.video_id,
            reason=args.reason,
        )
    ]
    items.sort(
        key=lambda item: (
            str(item["video_title"]).lower(),
            item["video_id"],
            -float(item.get("review_rating") or 0),
            float(item.get("final_start_seconds") or 0),
            int(item.get("rank") or 0),
        )
    )
    if args.limit is not None:
        items = items[: max(0, args.limit)]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"approved_clips_plan_{timestamp}.json"
    md_path = reports_dir / f"approved_clips_plan_{timestamp}.md"

    exported_at = datetime.utcnow().isoformat()
    for item in items:
        item["exported_at"] = exported_at

    payload = {
        "generated_at": exported_at,
        "exported_at": exported_at,
        "min_rating": min_rating,
        "include_rating_3": bool(args.include_rating_3),
        "include_diagnostics": bool(args.include_diagnostics),
        "video_id_filter": args.video_id,
        "reason_filter": args.reason,
        "clips_count": len([item for item in items if item["source_collection"] == "clips"]),
        "diagnostics_count": len(
            [item for item in items if item["source_collection"] == "diagnostic_candidates"]
        ),
        "videos_count": len({item["video_id"] for item in items}),
        "items": items,
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))

    print("EXPORT APPROVED CLIPS PLAN")
    print(f"clips approved: {payload['clips_count']}")
    print(f"diagnostics approved: {payload['diagnostics_count']}")
    print(f"videos included: {payload['videos_count']}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print("")
    print("Top by rating:")
    reason_counts = Counter(str(item.get("review_reason") or "sem_reason") for item in items)
    for reason, count in reason_counts.most_common(10):
        print(f"- {reason}: {count}")


def _iter_reviewed_clips(
    min_rating: float,
    allowed_statuses: set[str],
    include_diagnostics: bool,
    video_id: str | None,
    reason: str | None,
):
    if not config.STORAGE_CLIPS_DIR.exists():
        return
    collections = ["clips"]
    if include_diagnostics:
        collections.append("diagnostic_candidates")
    for path in sorted(config.STORAGE_CLIPS_DIR.glob("*_clips.json")):
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception as exc:
            print(f"[approved_plan] falha ao ler {path}: {exc}")
            continue
        current_video_id = str(payload.get("video_id") or path.name.replace("_clips.json", ""))
        if video_id and current_video_id != video_id:
            continue
        for source_collection in collections:
            for clip in payload.get(source_collection, []):
                review_status = str(clip.get("review_status") or "pending_review")
                review_reason = str(clip.get("review_reason") or "")
                rating = _to_float(clip.get("review_rating"))
                if review_status not in allowed_statuses:
                    continue
                if rating < min_rating:
                    continue
                if reason and review_reason != reason:
                    continue
                yield {
                    "video_id": current_video_id,
                    "payload": payload,
                    "clip": clip,
                    "source_collection": source_collection,
                }


def _plan_item(item: dict[str, Any]) -> dict[str, Any]:
    payload = item["payload"]
    clip = item["clip"]
    start = _to_float(clip.get("start_seconds"))
    end = _to_float(clip.get("end_seconds"))
    trim_start = clip.get("suggested_trim_start_seconds")
    trim_end = clip.get("suggested_trim_end_seconds")
    trim_duration = clip.get("suggested_trim_duration_seconds")
    trim_confidence = _to_float(clip.get("trim_confidence_score"))
    use_trim = trim_start is not None and trim_end is not None and trim_confidence >= 6
    final_start = _to_float(trim_start) if use_trim else start
    final_end = _to_float(trim_end) if use_trim else end
    final_duration = max(0.0, final_end - final_start)
    reason = str(clip.get("review_reason") or "sem_reason")
    rank = int(clip.get("rank") or 0)
    rating = _to_float(clip.get("review_rating"))
    video_id = item["video_id"]
    youtube_url = _youtube_url(payload, video_id, final_start)
    exported_at = datetime.utcnow().isoformat()
    return {
        "video_id": video_id,
        "video_title": payload.get("video_title", ""),
        "source_quality_score": payload.get(
            "source_quality_score",
            (payload.get("analysis_summary") or {}).get("source_quality_score"),
        ),
        "source_quality_tier": payload.get(
            "source_quality_tier",
            (payload.get("analysis_summary") or {}).get("source_quality_tier"),
        ),
        "rank": rank,
        "source_collection": item["source_collection"],
        "review_status": clip.get("review_status", "pending_review"),
        "review_rating": clip.get("review_rating"),
        "review_reason": reason,
        "review_notes": clip.get("review_notes", ""),
        "start_seconds": start,
        "end_seconds": end,
        "duration_seconds": _to_float(clip.get("duration_seconds")) or max(0.0, end - start),
        "suggested_trim_start_seconds": trim_start,
        "suggested_trim_end_seconds": trim_end,
        "suggested_trim_duration_seconds": trim_duration,
        "final_start_seconds": round(final_start, 2),
        "final_end_seconds": round(final_end, 2),
        "final_duration_seconds": round(final_duration, 2),
        "use_suggested_trim": use_trim,
        "youtube_url": youtube_url,
        "output_filename": _output_filename(video_id, rank, rating, reason, final_start, final_end),
        "clip_version": clip.get("clip_version"),
        "recommended_version": clip.get("recommended_version"),
        "ranking_quality_score": clip.get("ranking_quality_score"),
        "ranking_quality_tier": clip.get("ranking_quality_tier"),
        "sponsor_product_score": clip.get("sponsor_product_score"),
        "topic_merge_score": clip.get("topic_merge_score"),
        "needs_trim": clip.get("needs_trim"),
        "trim_reason": clip.get("trim_reason"),
        "created_at": clip.get("created_at") or clip.get("reviewed_at") or payload.get("processed_at"),
        "exported_at": exported_at,
    }


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Approved Clips Plan",
        "",
        f"Exported at: {payload['exported_at']}",
        f"Items: {len(payload['items'])}",
        f"Min rating: {payload['min_rating']}",
        f"Include diagnostics: {payload['include_diagnostics']}",
        "",
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in payload["items"]:
        grouped[item["video_id"]].append(item)

    for video_id, clips in grouped.items():
        title = clips[0].get("video_title") or video_id
        lines.extend(
            [
                f"## {title}",
                "",
                f"video_id: {video_id}",
                f"source_quality: {clips[0].get('source_quality_score')} / {clips[0].get('source_quality_tier')}",
                "approved clips:",
                "",
            ]
        )
        for clip in clips:
            lines.extend(
                [
                    f"### #{clip['rank']} - {clip['review_reason']} - rating {clip['review_rating']}",
                    "",
                    f"* time: {_mmss(clip['start_seconds'])} até {_mmss(clip['end_seconds'])}",
                    f"* final: {_mmss(clip['final_start_seconds'])} até {_mmss(clip['final_end_seconds'])}",
                    f"* use trim: {str(clip['use_suggested_trim']).lower()}",
                    f"* youtube: {clip['youtube_url']}",
                    f"* output: {clip['output_filename']}",
                    "",
                ]
            )
    return "\n".join(lines)


def _youtube_url(payload: dict[str, Any], video_id: str, start_seconds: float) -> str:
    base_url = str(payload.get("url") or "")
    if not base_url:
        base_url = f"https://www.youtube.com/watch?v={video_id}"
    separator = "&" if "?" in base_url else "?"
    if re.search(r"[?&]t=", base_url):
        return base_url
    return f"{base_url}{separator}t={int(start_seconds)}s"


def _output_filename(
    video_id: str,
    rank: int,
    rating: float,
    reason: str,
    start: float,
    end: float,
) -> str:
    safe_reason = _slug(reason or "sem_reason")
    rating_text = str(int(rating)) if float(rating).is_integer() else str(rating).replace(".", "_")
    return (
        f"{_slug(video_id)}__rank_{rank}__rating_{rating_text}__"
        f"{safe_reason}__{int(round(start))}_{int(round(end))}.mp4"
    )


def _slug(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or "clip"


def _mmss(value: object) -> str:
    total = max(0, int(round(_to_float(value))))
    minutes, seconds = divmod(total, 60)
    return f"{minutes}:{seconds:02d}"


def _to_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
