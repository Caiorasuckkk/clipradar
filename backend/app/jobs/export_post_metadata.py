from __future__ import annotations

from app.services.post_metadata_service import (
    POST_METADATA_MD_PATH,
    POST_METADATA_PATH,
    POST_STATUS_PATH,
    export_post_metadata,
    posts_summary,
)


def main() -> None:
    payload = export_post_metadata()
    summary = posts_summary()

    print("EXPORT POST METADATA")
    print(f"posts: {payload.get('items_count', 0)}")
    print(f"not_posted: {summary.get('not_posted', 0)}")
    print(f"posted: {summary.get('posted', 0)}")
    print(f"scheduled: {summary.get('scheduled', 0)}")
    print(f"do_not_post: {summary.get('do_not_post', 0)}")
    print(f"JSON: {POST_METADATA_PATH}")
    print(f"Markdown: {POST_METADATA_MD_PATH}")
    print(f"Status: {POST_STATUS_PATH}")


if __name__ == "__main__":
    main()
