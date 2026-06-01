from __future__ import annotations

import argparse
import sys

from app.services.candidate_review_service import load_candidate_queue


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--missing-only", action="store_true")
    args = parser.parse_args()

    candidates = load_candidate_queue()
    if args.video_id:
        candidates = [
            candidate
            for candidate in candidates
            if str(candidate.get("video_id") or "") == args.video_id
        ]

    preview_ready = [candidate for candidate in candidates if candidate.get("preview_exists")]
    missing_preview = [candidate for candidate in candidates if not candidate.get("preview_exists")]
    reviewed = [candidate for candidate in candidates if candidate.get("already_reviewed")]
    pending = [candidate for candidate in candidates if not candidate.get("already_reviewed")]
    listed = missing_preview if args.missing_only else candidates

    print("CANDIDATE PREVIEW STATUS")
    print(f"total candidates: {len(candidates)}")
    print(f"preview_ready: {len(preview_ready)}")
    print(f"missing_preview: {len(missing_preview)}")
    print(f"reviewed: {len(reviewed)}")
    print(f"pending: {len(pending)}")
    print("")
    title = "Missing previews" if args.missing_only else "Candidates"
    print(f"{title}:")
    for candidate in listed[:50]:
        print(
            f"- {candidate.get('candidate_id')} | "
            f"{candidate.get('output_preview_filename')} | "
            f"preview_exists={candidate.get('preview_exists')}"
        )
    if len(listed) > 50:
        print(f"... {len(listed) - 50} restantes")


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
