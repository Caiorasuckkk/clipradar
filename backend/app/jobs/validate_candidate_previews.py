from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app import config
from app.services.candidate_preview_validation_service import validate_candidate_preview


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--bad-only", action="store_true")
    parser.add_argument("--delete-bad", action="store_true")
    parser.add_argument("--video-id")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    items: list[dict[str, Any]] = []
    deleted = 0
    for path in sorted(config.STORAGE_CANDIDATE_PREVIEWS_DIR.glob("*.mp4"), key=lambda item: item.name.lower()):
        if args.video_id and args.video_id not in path.name:
            continue
        validation = validate_candidate_preview(path)
        item = {
            "filename": path.name,
            **validation.to_dict(),
            "status": "ok" if validation.valid else "invalid",
            "deleted": False,
        }
        if args.bad_only and validation.valid:
            continue
        if args.delete_bad and not validation.valid:
            try:
                path.unlink(missing_ok=True)
                item["deleted"] = True
                deleted += 1
            except Exception as exc:
                item["delete_error"] = str(exc)
        items.append(item)

    payload = {
        "total_checked": len(items),
        "ok_count": sum(1 for item in items if item["status"] == "ok"),
        "invalid_count": sum(1 for item in items if item["status"] == "invalid"),
        "deleted_count": deleted,
        "items": items,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("VALIDATE CANDIDATE PREVIEWS")
    print(f"checked: {payload['total_checked']}")
    print(f"ok: {payload['ok_count']}")
    print(f"invalid: {payload['invalid_count']}")
    print(f"deleted: {payload['deleted_count']}")
    print("")
    for item in items:
        print(
            f"- {item['filename']} | {item['status']} | "
            f"{item.get('video_codec') or '-'} | "
            f"{item.get('format_name') or '-'} | "
            f"{item.get('duration_seconds') or '-'}s"
        )
        if item.get("error_message"):
            print(f"  {item['error_message']}")


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
