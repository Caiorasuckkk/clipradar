from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import config
from app.services.post_metadata_service import (
    VALID_POST_STATUSES,
    get_post,
    load_posts,
    posts_summary,
    update_post_status,
)


router = APIRouter()


class PostStatusPayload(BaseModel):
    status: str
    platforms: list[str] = []
    posted_at: str | None = None
    post_url: str = ""
    notes: str = ""


@router.get("/posts")
def list_posts(status: str = "not_posted") -> dict[str, object]:
    if status != "all" and status not in VALID_POST_STATUSES:
        raise HTTPException(status_code=400, detail="invalid_status")
    posts = load_posts(status=status)
    return {"status": status, "count": len(posts), "posts": posts}


@router.get("/posts/summary")
def get_posts_summary() -> dict[str, object]:
    return posts_summary()


@router.get("/posts/{post_id}")
def get_post_detail(post_id: str) -> dict[str, object]:
    post = get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")
    return {"post": post}


@router.post("/posts/{post_id}")
def update_post(post_id: str, payload: PostStatusPayload) -> dict[str, object]:
    try:
        status = update_post_status(
            post_id=post_id,
            status=payload.status,
            platforms=payload.platforms,
            posted_at=payload.posted_at,
            post_url=payload.post_url,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"post_id": post_id, "status": status, "post": get_post(post_id)}


@router.get("/posting_package/latest/videos/{filename}")
def get_latest_package_video(filename: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.mp4", filename):
        raise HTTPException(status_code=400, detail="invalid_filename")
    videos_dir = (config.STORAGE_POSTING_PACKAGE_DIR / "latest" / "videos").resolve()
    path = (videos_dir / filename).resolve()
    if path.parent != videos_dir or not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="video_not_found")
    return FileResponse(Path(path), media_type="video/mp4", filename=filename)
