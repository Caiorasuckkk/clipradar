from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from app import config


VALID_STATUSES = {"pending_review", "approved", "rejected", "needs_adjustment"}


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--target", choices=["clips", "diagnostic"], default="clips")
    parser.add_argument("--rank", required=True, type=int)
    parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    parser.add_argument("--rating", type=int)
    parser.add_argument("--reason", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--ideal-start", type=float)
    parser.add_argument("--ideal-end", type=float)
    args = parser.parse_args()

    path = config.STORAGE_CLIPS_DIR / f"{args.video_id}_clips.json"
    if not path.exists():
        print(f"Arquivo não encontrado: {path}")
        return

    payload = _load_json(path)
    collection = "diagnostic_candidates" if args.target == "diagnostic" else "clips"
    clip = _find_clip(payload, args.rank, collection)
    if not clip:
        print(f"Clipe rank {args.rank} não encontrado em {collection} de {path}")
        return

    _ensure_review_fields(clip)
    clip["review_status"] = args.status
    clip["review_rating"] = args.rating
    clip["review_reason"] = args.reason
    clip["review_notes"] = args.notes
    clip["ideal_start_seconds"] = args.ideal_start
    clip["ideal_end_seconds"] = args.ideal_end
    clip["reviewed_at"] = datetime.utcnow().isoformat()

    _save_json(path, payload)
    print("REVIEW CLIP — atualizado")
    print(f"video_id: {args.video_id}")
    print(f"target: {collection}")
    print(f"rank: {clip.get('rank')}")
    print(f"status: {clip.get('review_status')}")
    print(f"rating: {clip.get('review_rating')}")
    print(f"reason: {clip.get('review_reason')}")
    print(f"ideal: {clip.get('ideal_start_seconds')} - {clip.get('ideal_end_seconds')}")
    print(f"timestamp: {clip.get('start_seconds')} - {clip.get('end_seconds')}s")
    print(f"score: {clip.get('score')}")
    print(f"first_sentence: {_display(clip.get('first_sentence', ''), 140)}")


def _find_clip(payload: dict[str, Any], rank: int, collection: str) -> dict[str, Any] | None:
    for clip in payload.get(collection, []):
        if int(clip.get("rank") or 0) == rank:
            return clip
    return None


def _ensure_review_fields(clip: dict[str, Any]) -> None:
    clip.setdefault("review_status", "pending_review")
    clip.setdefault("review_rating", None)
    clip.setdefault("review_reason", "")
    clip.setdefault("review_notes", "")
    clip.setdefault("ideal_start_seconds", None)
    clip.setdefault("ideal_end_seconds", None)
    clip.setdefault("reviewed_at", None)


def _load_json(path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_json(path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _display(value: object, limit: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
