"""Generation render pipeline (Bloco B).

Turns a ``ready_for_render`` generation project into a real 1080x1920 vertical
MP4: narration audio + per-line b-roll (downloaded from Pexels, color fallback)
+ burned-in subtitles synced to the edge-tts word timings.

Runs entirely inside the SQLite job queue worker thread (never on a FastAPI
request), invoking FFmpeg as child processes so heavy work stays off the API and
stays cancellable. Adapted conceptually from canal-dark's short_factory assembly.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from app import config
from app.services import job_queue_service
from app.services.job_queue_service import JobCancelled, JobContext
from app.services.generation_workspace_service import get_project, update_project
from app.services.generation_voice_service import ensure_voice_words
from app.services.generation_asset_service import acquire_assets, has_media, usable_items
from app.services import generation_caption_service


JOB_TYPE = "generation_render"

WIDTH = config.GENERATION_RENDER_WIDTH
HEIGHT = config.GENERATION_RENDER_HEIGHT
FPS = config.GENERATION_RENDER_FPS
MAX_SECONDS = config.GENERATION_RENDER_MAX_SECONDS
RENDER_TIMEOUT = config.GENERATION_RENDER_TIMEOUT_SECONDS

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MUSIC_DIR = config.STORAGE_GENERATION_MUSIC_DIR
MUSIC_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}
BG_COLOR = "0x0E1116"

# Visible fallback palettes (clearly NOT black). One distinct look per segment.
# Bright top colour grading down to a mid tone so subtitles stay readable while
# the frame reads as a real designed background, not an empty black screen.
_GRADIENT_PALETTE: tuple[tuple[str, str], ...] = (
    ("0x3D6FB0", "0x1B3358"),
    ("0x8A4FB0", "0x361F55"),
    ("0x3DA06B", "0x174A30"),
    ("0xB07A3D", "0x523618"),
    ("0x5A6FCF", "0x232A66"),
    ("0x3D95B0", "0x174450"),
    ("0xB0506B", "0x501E2C"),
)
_SOLID_PALETTE: tuple[str, ...] = (
    "0x35589A", "0x5E3E8A", "0x2E7A52", "0x8A5E32", "0x4858A0", "0x8A3A52",
)


class RenderError(Exception):
    def __init__(self, message: str, code: str = "render_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

def _usable_visual_items(project: dict[str, Any]) -> list[dict[str, Any]]:
    return usable_items(project)


def readiness_report(project: dict[str, Any]) -> list[str]:
    """Return a list of blocker codes. Empty list == ready to render."""
    missing: list[str] = []
    audio = _project_audio_path(project)
    if not audio or not audio.exists():
        missing.append("missing_voice_audio")
    words = str(project.get("voice_words_path") or "")
    if not words or not Path(words).exists():
        missing.append("missing_voice_words")
    items = _usable_visual_items(project)
    if not items:
        missing.append("missing_visual_items")
    else:
        has_real = any(has_media(item) for item in items)
        has_fallback = any(item.get("fallback_visual") for item in items)
        if not has_real and not has_fallback:
            # Visual "ready" must mean real media OR an explicit visible fallback,
            # never a silent black screen from bare placeholders.
            missing.append("missing_visual_media")
    if str(project.get("visual_status") or "") != "ready":
        missing.append("visual_not_ready")
    if str(project.get("status") or "") not in {"ready_for_render", "rendered"}:
        missing.append("project_not_ready_for_render")
    return missing


def _visual_counts(acq: dict[str, Any]) -> dict[str, Any]:
    return {
        "visual_items_without_media_count": acq["without_media_count"],
        "pexels_downloaded_count": acq["downloaded"],
        "fallback_visual_count": acq["fallback_count"],
        "visual_media_count": acq["media_count"],
        "pexels_available": acq["pexels_available"],
    }


def prepare_render(
    project_id: str,
    mark_visual_ready: bool = False,
    allow_visual_fallback: bool = False,
) -> dict[str, Any]:
    """Make a project render-ready without starting a render.

    Ensures narration word timings, downloads real b-roll from Pexels for items
    that lack media, optionally enables a visible visual fallback, and promotes
    the project to ready_for_render once prerequisites are met.
    """
    project = get_project(project_id)
    if not project:
        raise RenderError("Projeto não encontrado.", "project_not_found")

    fixed: list[str] = []

    # 1. Narration word timings (real or approximate fallback) + caption blocks.
    audio = _project_audio_path(project)
    if audio and audio.exists():
        words_result = ensure_voice_words(project)
        if words_result.get("generated"):
            fixed.append("voice_words_generated")
        project = words_result.get("project") or project
        caption_result = generation_caption_service.ensure_captions(project)
        if caption_result.get("captions_path"):
            if not project.get("voice_captions_path"):
                fixed.append("captions_generated")
            project = update_project(
                project_id,
                {
                    **project,
                    "voice_captions_path": caption_result["captions_path"],
                    "voice_caption_count": caption_result["caption_count"],
                },
            ) or project

    # 2. Acquire visual assets (download Pexels; optionally enable fallback).
    acq = acquire_assets(project, allow_fallback=allow_visual_fallback)
    if acq["downloaded"] > 0:
        fixed.append("pexels_downloaded")
    if acq["fallback_count"] > 0:
        fixed.append("visual_fallback_enabled")

    has_visible_visual = acq["media_count"] > 0 or acq["fallback_count"] > 0
    visual_status = project.get("visual_status")
    next_status = project.get("status")

    # 3. Mark visual ready only when there is real media or an enabled fallback.
    if mark_visual_ready and has_visible_visual:
        items = _mark_items_ready(acq["items"])
        visual_status = "ready"
        if next_status not in {"ready_for_render", "rendered", "archived"}:
            next_status = "ready_for_render"
        fixed.append("visual_marked_ready")
    else:
        items = acq["items"]

    project = update_project(
        project_id,
        {
            **project,
            "visual_items": items,
            "visual_status": visual_status,
            "status": next_status,
            "visual_fallback_used": acq["fallback_count"] > 0,
            "visual_fallback_reason": "no_assets_available" if acq["fallback_count"] > 0 else "",
        },
    ) or project

    missing = readiness_report(project)
    return {
        "project_id": project_id,
        "ready_for_render": not missing,
        "missing": missing,
        "fixed": fixed,
        **_visual_counts(acq),
        "project": project,
    }


def _mark_items_ready(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        next_item = dict(item)
        status = str(next_item.get("status") or "")
        if has_media(next_item):
            next_item["status"] = "downloaded" if next_item.get("media_path") else "ready"
        elif next_item.get("fallback_visual"):
            next_item["status"] = "ready"
        elif status == "selected":
            next_item["status"] = "ready"
        result.append(next_item)
    return result


# ---------------------------------------------------------------------------
# Public API (called from generation_api)
# ---------------------------------------------------------------------------

def request_render(
    project_id: str,
    overwrite: bool = True,
    allow_visual_fallback: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    # A render always produces a fresh MP4 (overwrite); ``force`` is accepted so
    # callers can explicitly re-render after stale-invalidating changes.
    overwrite = overwrite or force
    project = get_project(project_id)
    if not project:
        raise RenderError("Projeto não encontrado.", "project_not_found")

    audio_path = _project_audio_path(project)
    if not audio_path or not audio_path.exists():
        raise RenderError("Gere a narração (voz) antes de renderizar o vídeo.", "missing_voice_audio")

    # Auto-prepare word timings so a project with audio is never stuck.
    words_result = ensure_voice_words(project)
    project = words_result.get("project") or project
    words = str(project.get("voice_words_path") or "")
    if not words or not Path(words).exists():
        raise RenderError("Não foi possível preparar os timestamps da narração.", "missing_voice_words")

    if not _usable_visual_items(project):
        raise RenderError("Adicione itens visuais antes de renderizar.", "missing_visual_items")

    # Acquire real media; only allow a visible fallback when explicitly opted in.
    acq = acquire_assets(project, allow_fallback=allow_visual_fallback)
    if acq["media_count"] == 0 and acq["fallback_count"] == 0:
        raise RenderError(
            "Nenhum item visual tem mídia real. Baixe b-roll (Pexels) ou renderize com fallback visual.",
            "missing_visual_media",
        )

    items = _mark_items_ready(acq["items"])
    fallback_used = acq["fallback_count"] > 0

    # Persist items BEFORE enqueue so the worker reads the resolved media.
    next_status = project.get("status")
    if next_status not in {"ready_for_render", "rendered", "archived"}:
        next_status = "ready_for_render"
    project = update_project(
        project_id,
        {
            **project,
            "visual_items": items,
            "visual_status": "ready",
            "status": next_status,
            "visual_fallback_used": fallback_used,
            "visual_fallback_reason": "no_assets_available" if fallback_used else "",
        },
    ) or project

    job = job_queue_service.enqueue(
        JOB_TYPE,
        payload={"project_id": project_id, "overwrite": bool(overwrite)},
        project_id=project_id,
    )
    updated = update_project(
        project_id,
        {
            **project,
            "render_status": "queued",
            "render_job_id": job.get("id"),
            "render_error": "",
        },
    )
    return {"job": job, "project": updated or project, **_visual_counts(acq)}


def get_render_status(project_id: str) -> dict[str, Any] | None:
    project = get_project(project_id)
    if not project:
        return None
    jobs = job_queue_service.list_jobs(job_type=JOB_TYPE, project_id=project_id, limit=1)
    items = usable_items(project)
    media_items = sum(1 for item in items if has_media(item))
    return {
        "project_id": project_id,
        "render_status": project.get("render_status") or "none",
        "render_video_url": project.get("render_video_url") or "",
        "render_thumbnail_url": project.get("render_thumbnail_url") or "",
        "render_duration_seconds": project.get("render_duration_seconds"),
        "render_segment_count": project.get("render_segment_count"),
        "render_error": project.get("render_error") or "",
        "render_generated_at": project.get("render_generated_at") or "",
        "visual_fallback_used": bool(project.get("visual_fallback_used")),
        "visual_fallback_reason": project.get("visual_fallback_reason") or "",
        "narration_style": project.get("narration_style") or "",
        "narration_style_label": project.get("narration_style_label") or "",
        "voice_caption_count": project.get("voice_caption_count") or 0,
        "voice_word_count": project.get("voice_word_count") or 0,
        "voice_words_source": project.get("voice_words_source") or "",
        "visual_media_count": media_items,
        "visual_item_count": len(items),
        "job": jobs[0] if jobs else None,
    }


def get_render_video_path(project_id: str) -> Path:
    project = get_project(project_id)
    if not project:
        raise RenderError("Projeto não encontrado.")
    path = Path(str(project.get("render_video_path") or "")) if project.get("render_video_path") else _output_path(project_id)
    if not path.exists() or not path.is_file():
        raise RenderError("Vídeo ainda não foi renderizado.")
    return path


# ---------------------------------------------------------------------------
# Job handler
# ---------------------------------------------------------------------------

def _handle_render(ctx: JobContext) -> dict[str, Any]:
    project_id = ctx.project_id or str(ctx.payload.get("project_id") or "")
    if not project_id:
        raise RenderError("project_id ausente no job de render.")
    project = get_project(project_id)
    if not project:
        raise RenderError("Projeto não encontrado.")

    update_project(project_id, {**project, "render_status": "rendering", "render_error": ""})
    try:
        result = _render_project(ctx, project_id, project)
    except JobCancelled:
        latest = get_project(project_id) or project
        update_project(project_id, {**latest, "render_status": "cancelled"})
        raise
    except Exception as exc:
        latest = get_project(project_id) or project
        update_project(
            project_id,
            {**latest, "render_status": "failed", "render_error": str(exc)[:500]},
        )
        raise
    return result


def _render_project(ctx: JobContext, project_id: str, project: dict[str, Any]) -> dict[str, Any]:
    ctx.set_progress(0.03, "preparando")
    audio_path = _project_audio_path(project)
    if not audio_path or not audio_path.exists():
        raise RenderError("Narração não encontrada.")

    audio_duration = _probe_duration(audio_path) or _safe_float(project.get("voice_duration_seconds")) or 30.0
    total = round(min(audio_duration, float(MAX_SECONDS)), 2)
    if total < 1.0:
        raise RenderError("Duração de áudio inválida.")

    work_dir = _work_dir(project_id)
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    config.STORAGE_GENERATION_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    config.STORAGE_GENERATION_RENDERS_DIR.mkdir(parents=True, exist_ok=True)

    segments = _plan_segments(project, total)
    ctx.check_cancelled()

    # 1. Download assets (Pexels). 0.05 -> 0.35
    _download_assets(ctx, segments)

    # 2. Normalize each segment to a uniform 1080x1920 clip. 0.35 -> 0.78
    fallback_segments = _build_segment_clips(ctx, segments, work_dir)

    # 3. Subtitles from caption blocks synced to the narration. 0.80
    ctx.set_progress(0.80, "legendas")
    ass_path, cues, caption_source = _build_subtitles(project, work_dir, total)
    generation_caption_service.write_timing_report(
        config.STORAGE_GENERATION_RENDERS_DIR / f"{_safe_id(project_id)}.timing.json",
        audio_duration=total,
        word_count=int(project.get("voice_word_count") or 0),
        captions=cues,
        source=caption_source,
    )

    # 4. Concat + audio mux + subtitle burn. 0.82 -> 0.95
    ctx.set_progress(0.82, "montando vídeo")
    output_path = _output_path(project_id)
    _assemble(ctx, segments, work_dir, audio_path, ass_path, output_path, total)

    # 5. Thumbnail. 0.97
    ctx.set_progress(0.97, "thumbnail")
    thumb_path = _build_thumbnail(ctx, output_path, project_id)

    shutil.rmtree(work_dir, ignore_errors=True)

    latest = get_project(project_id) or project
    update_project(
        project_id,
        {
            **latest,
            "status": "rendered",
            "render_status": "ready",
            "render_video_path": str(output_path),
            "render_video_url": f"/generation/projects/{project_id}/render/video",
            "render_thumbnail_path": str(thumb_path) if thumb_path else "",
            "render_thumbnail_url": f"/generation/projects/{project_id}/render/thumbnail" if thumb_path else "",
            "render_duration_seconds": total,
            "render_segment_count": len(segments),
            "render_width": WIDTH,
            "render_height": HEIGHT,
            "render_generated_at": datetime.utcnow().isoformat(),
            "render_error": "",
            "visual_fallback_used": fallback_segments > 0,
            "visual_fallback_reason": _fallback_reason(fallback_segments, len(segments)),
        },
    )
    return {
        "project_id": project_id,
        "video_path": str(output_path),
        "video_url": f"/generation/projects/{project_id}/render/video",
        "duration_seconds": total,
        "segment_count": len(segments),
        "fallback_segment_count": fallback_segments,
    }


def _fallback_reason(fallback_segments: int, total_segments: int) -> str:
    if fallback_segments <= 0:
        return ""
    if fallback_segments >= total_segments:
        return "no_assets_available"
    return "partial_fallback"


# ---------------------------------------------------------------------------
# Segment planning
# ---------------------------------------------------------------------------

def _plan_segments(project: dict[str, Any], total: float) -> list[dict[str, Any]]:
    items = [item for item in project.get("visual_items") or [] if isinstance(item, dict)]
    items = [item for item in items if str(item.get("status") or "") != "rejected"]
    items.sort(key=lambda item: _safe_float(item.get("order")) or 0.0)
    lines = [str(line or "") for line in project.get("script_lines") or []]

    if not items:
        return [
            {
                "index": 0,
                "duration": total,
                "media_url": "",
                "media_path": "",
                "source": "placeholder",
                "type": "placeholder",
                "line": (project.get("hook") or project.get("title") or ""),
                "local_path": None,
            }
        ]

    weights = [max(0.5, _safe_float(item.get("duration_seconds")) or 1.0) for item in items]
    weight_sum = sum(weights) or float(len(items))
    segments: list[dict[str, Any]] = []
    allocated = 0.0
    for index, item in enumerate(items):
        if index == len(items) - 1:
            duration = round(max(0.8, total - allocated), 2)
        else:
            duration = round(max(0.8, total * (weights[index] / weight_sum)), 2)
        allocated = round(allocated + duration, 2)
        line_index = int(_safe_float(item.get("script_line_index")) or index)
        line = lines[line_index] if 0 <= line_index < len(lines) else str(item.get("description") or "")
        segments.append(
            {
                "index": index,
                "duration": duration,
                "media_url": str(item.get("media_url") or ""),
                "media_path": str(item.get("media_path") or ""),
                "source": str(item.get("source") or "placeholder"),
                "type": str(item.get("type") or "broll"),
                "line": line,
                "local_path": None,
            }
        )
    return segments


# ---------------------------------------------------------------------------
# Asset download
# ---------------------------------------------------------------------------

def _download_assets(ctx: JobContext, segments: list[dict[str, Any]]) -> None:
    downloadable = [seg for seg in segments if seg.get("media_url") or seg.get("media_path")]
    for position, seg in enumerate(downloadable):
        ctx.check_cancelled()
        local = _resolve_asset(seg)
        seg["local_path"] = str(local) if local else None
        progress = 0.05 + (0.30 * (position + 1) / max(1, len(downloadable)))
        ctx.set_progress(progress, f"baixando mídia {position + 1}/{len(downloadable)}")


def _resolve_asset(seg: dict[str, Any]) -> Path | None:
    media_path = seg.get("media_path") or ""
    if media_path:
        path = Path(media_path)
        if path.exists() and path.is_file():
            return path
    url = seg.get("media_url") or ""
    if not url:
        return None
    extension = _extension_from_url(url, seg.get("type") or "")
    cache_path = config.STORAGE_GENERATION_ASSETS_DIR / f"{_hash(url)}{extension}"
    if cache_path.exists() and cache_path.stat().st_size > 1024:
        return cache_path
    try:
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            with cache_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=262144):
                    if chunk:
                        file.write(chunk)
    except Exception:
        if cache_path.exists():
            cache_path.unlink(missing_ok=True)
        return None
    if cache_path.exists() and cache_path.stat().st_size > 1024:
        return cache_path
    return None


# ---------------------------------------------------------------------------
# Segment normalization
# ---------------------------------------------------------------------------

def _build_segment_clips(ctx: JobContext, segments: list[dict[str, Any]], work_dir: Path) -> int:
    """Render each segment to a uniform 1080x1920 clip. Returns how many segments
    fell back to a generated visual (no real media). Never produces black."""
    fallback_count = 0
    for position, seg in enumerate(segments):
        ctx.check_cancelled()
        seg_path = work_dir / f"seg_{seg['index']:03d}.mp4"
        local = seg.get("local_path")
        used_fallback = False

        if local:
            try:
                _run_ffmpeg(ctx, _media_command(seg, str(local), seg_path), RENDER_TIMEOUT)
            except RenderError:
                pass

        if not _valid_clip(seg_path):
            # Visible gradient fallback (colored, moving) — never a black screen.
            try:
                _run_ffmpeg(ctx, _gradient_command(seg["index"], seg["duration"], seg_path), RENDER_TIMEOUT)
                used_fallback = True
            except RenderError:
                pass

        if not _valid_clip(seg_path):
            # Last resort: a distinct dark solid color (still not pure black).
            _run_ffmpeg(ctx, _solid_command(seg["index"], seg["duration"], seg_path), RENDER_TIMEOUT)
            used_fallback = True

        seg["clip_path"] = str(seg_path)
        seg["used_fallback"] = used_fallback
        if used_fallback:
            fallback_count += 1
        progress = 0.35 + (0.43 * (position + 1) / max(1, len(segments)))
        ctx.set_progress(progress, f"montando cena {position + 1}/{len(segments)}")
    return fallback_count


def _valid_clip(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 1024


def _media_command(seg: dict[str, Any], local: str, seg_path: Path) -> list[str]:
    duration = float(seg["duration"])
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS}"
    )
    if _is_image(Path(local)):
        # Stills get a slow Ken Burns zoom so the video reads as "edited", not a
        # static slideshow. Direction alternates per scene for variety.
        if config.GENERATION_ENABLE_KEN_BURNS:
            vf = _ken_burns_vf(int(seg.get("index") or 0), duration)
        return [
            _ffmpeg(), "-y", "-loop", "1", "-t", f"{duration}", "-i", local,
            "-vf", vf, "-t", f"{duration}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            str(seg_path),
        ]
    return [
        _ffmpeg(), "-y", "-stream_loop", "-1", "-i", local,
        "-an", "-vf", vf, "-t", f"{duration}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
        str(seg_path),
    ]


def _ken_burns_vf(index: int, duration: float) -> str:
    """Build a jitter-free slow-zoom (Ken Burns) filter for a still image.

    Pre-scales to a larger canvas (sharpness + headroom), then a centred zoompan
    so there is no horizontal pan jitter. Even scenes zoom in, odd scenes zoom out.
    """
    frames = max(1, int(round(duration * FPS)))
    zoom = max(0.02, float(config.GENERATION_KENBURNS_ZOOM))
    zmax = round(1.0 + zoom, 4)
    inc = round(zoom / frames, 7)
    up_w, up_h = int(WIDTH * 1.5), int(HEIGHT * 1.5)
    if index % 2 == 0:
        z_expr = f"min(1+on*{inc}\\,{zmax})"          # zoom in
    else:
        z_expr = f"max({zmax}-on*{inc}\\,1)"           # zoom out
    return (
        f"scale={up_w}:{up_h}:force_original_aspect_ratio=increase,"
        f"crop={up_w}:{up_h},"
        f"zoompan=z='{z_expr}':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1"
    )


def _gradient_command(index: int, duration: float, seg_path: Path) -> list[str]:
    c0, c1 = _GRADIENT_PALETTE[index % len(_GRADIENT_PALETTE)]
    source = (
        f"gradients=s={WIDTH}x{HEIGHT}:c0={c0}:c1={c1}:x0=0:y0=0:"
        f"x1={WIDTH}:y1={HEIGHT}:d={max(2.0, float(duration))}:r={FPS}"
    )
    return [
        _ffmpeg(), "-y", "-f", "lavfi", "-i", source, "-t", f"{duration}",
        "-vf", "hue=h=t*8,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        str(seg_path),
    ]


def _solid_command(index: int, duration: float, seg_path: Path) -> list[str]:
    color = _SOLID_PALETTE[index % len(_SOLID_PALETTE)]
    return [
        _ffmpeg(), "-y", "-f", "lavfi",
        "-i", f"color=c={color}:s={WIDTH}x{HEIGHT}:r={FPS}", "-t", f"{duration}",
        "-vf", "format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
        str(seg_path),
    ]


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------

def _build_subtitles(project: dict[str, Any], work_dir: Path, total: float) -> tuple[Path | None, list[dict[str, Any]], str]:
    """Returns (ass_path, cues, source). Prefers the pre-built caption blocks
    (synced to speech) over fixed per-segment slots."""
    cues = _cues_from_captions(project)
    source = "captions"
    if not cues:
        cues = _cues_from_words(project)
        source = "words"
    if not cues:
        cues = _cues_from_lines(project, total)
        source = "lines"
    if not cues:
        return None, [], "none"
    cues = generation_caption_service.validate_and_fix(cues, total)
    ass_path = work_dir / "subs.ass"
    try:
        _write_ass(ass_path, cues)
    except OSError:
        return None, cues, source
    return ass_path, cues, source


def _cues_from_captions(project: dict[str, Any]) -> list[dict[str, Any]]:
    captions_path = str(project.get("voice_captions_path") or "")
    if not captions_path or not Path(captions_path).exists():
        return []
    try:
        with Path(captions_path).open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    cues = payload.get("captions") if isinstance(payload, dict) else None
    if not isinstance(cues, list):
        return []
    return [
        {"start": float(c.get("start") or 0), "end": float(c.get("end") or 0), "text": str(c.get("text") or "")}
        for c in cues
        if isinstance(c, dict) and c.get("text")
    ]


def _cues_from_words(project: dict[str, Any]) -> list[dict[str, Any]]:
    words_path = project.get("voice_words_path") or ""
    if not words_path or not Path(words_path).exists():
        return []
    try:
        with Path(words_path).open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    words = payload.get("words") if isinstance(payload, dict) else None
    if not isinstance(words, list) or not words:
        return []
    cues: list[dict[str, Any]] = []
    group: list[dict[str, Any]] = []

    def flush() -> None:
        if not group:
            return
        text = " ".join(str(w.get("text") or "") for w in group).strip()
        if text:
            cues.append({"start": float(group[0]["start"]), "end": float(group[-1]["end"]), "text": text})
        group.clear()

    for word in words:
        if not isinstance(word, dict) or word.get("start") is None:
            continue
        group.append(word)
        joined = " ".join(str(w.get("text") or "") for w in group)
        if len(group) >= 3 or len(joined) >= 22:
            flush()
    flush()
    return cues


def _cues_from_lines(project: dict[str, Any], total: float) -> list[dict[str, Any]]:
    parts: list[str] = []
    if project.get("hook"):
        parts.append(str(project["hook"]))
    parts.extend(str(line or "") for line in project.get("script_lines") or [])
    if project.get("cta"):
        parts.append(str(project["cta"]))
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []
    slot = total / len(parts)
    cues: list[dict[str, Any]] = []
    for index, part in enumerate(parts):
        start = round(index * slot, 2)
        end = round(total if index == len(parts) - 1 else (index + 1) * slot, 2)
        cues.append({"start": start, "end": end, "text": _shorten(part, 60)})
    return cues


def _write_ass(path: Path, cues: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    font = config.GENERATION_CAPTION_FONT or "Arial"
    size = max(40, int(config.GENERATION_CAPTION_FONTSIZE))
    margin_v = int(HEIGHT * 0.20)  # lower third, inside the safe area
    upper = config.GENERATION_CAPTION_UPPERCASE
    # Big bold white text with a thick black outline + drop shadow so it stays
    # readable over any b-roll (the viral-shorts caption look).
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {WIDTH}",
        f"PlayResY: {HEIGHT}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Default,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,7,4,2,70,70,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    body = []
    for cue in cues:
        text = str(cue["text"])
        if upper:
            text = text.upper()
        body.append(
            "Dialogue: 0,"
            f"{_ass_time(cue['start'])},{_ass_time(cue['end'])},Default,,0,0,0,,{_ass_escape(text)}"
        )
    path.write_text("\n".join(header + body), encoding="utf-8")


# ---------------------------------------------------------------------------
# Final assembly
# ---------------------------------------------------------------------------

def _assemble(
    ctx: JobContext,
    segments: list[dict[str, Any]],
    work_dir: Path,
    audio_path: Path,
    ass_path: Path | None,
    output_path: Path,
    total: float,
) -> None:
    list_path = work_dir / "concat.txt"
    lines = []
    for seg in segments:
        clip = seg.get("clip_path")
        if clip and Path(clip).exists():
            lines.append(f"file '{Path(clip).resolve().as_posix()}'")
    if not lines:
        raise RenderError("Nenhuma cena foi renderizada.")
    list_path.write_text("\n".join(lines), encoding="utf-8")

    if output_path.exists():
        output_path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    music = _select_music(ctx.project_id) if config.GENERATION_ENABLE_BG_MUSIC else None
    try:
        _run_ffmpeg(
            ctx,
            _assemble_command(list_path, audio_path, ass_path, output_path, total, music),
            RENDER_TIMEOUT,
        )
    except RenderError:
        # Never let background music break a render — retry without it.
        if music is None:
            raise
        _run_ffmpeg(
            ctx,
            _assemble_command(list_path, audio_path, ass_path, output_path, total, None),
            RENDER_TIMEOUT,
        )


def _assemble_command(
    list_path: Path,
    audio_path: Path,
    ass_path: Path | None,
    output_path: Path,
    total: float,
    music: Path | None,
) -> list[str]:
    has_ass = bool(ass_path and ass_path.exists())
    command = [
        _ffmpeg(), "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-i", str(audio_path),
    ]
    if music is not None:
        # Loop the track so it covers the whole video; trimmed by -t below.
        command += ["-stream_loop", "-1", "-i", str(music)]
        vol = max(0.0, float(config.GENERATION_BG_MUSIC_VOLUME))
        audio_chain = (
            f"[1:a]volume=1.0[a1];[2:a]volume={vol}[a2];"
            "[a1][a2]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a]"
        )
        if has_ass:
            filter_complex = f"[0:v]ass='{_filter_path(ass_path)}'[v];{audio_chain}"
            command += ["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"]
        else:
            command += ["-filter_complex", audio_chain, "-map", "0:v:0", "-map", "[a]"]
    else:
        if has_ass:
            command += ["-vf", f"ass='{_filter_path(ass_path)}'"]
        command += ["-map", "0:v:0", "-map", "1:a:0"]
    command += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-r", f"{FPS}",
        "-t", f"{total}", "-movflags", "+faststart",
        str(output_path),
    ]
    return command


# Mood folders the owner fills with royalty-free tracks. The video's niche/tone
# picks the folder; the track is then varied per project.
MUSIC_MOODS = ("dramatico", "animado", "calmo", "tenso")
# Keys are accent-stripped/lowercase to match _normalize_ascii lookups.
_NICHE_MOOD = {
    "futebol": "animado",
    "tecnologia": "animado",
    "curiosidades": "animado",
    "historia": "dramatico",
    "true crime": "tenso",
    "crime": "tenso",
    "financas": "calmo",
    "negocios": "calmo",
    "saude": "calmo",
    "politica": "tenso",
}
_TONE_MOOD = {
    "dramatico": "dramatico",
    "serio": "dramatico",
    "polemico": "tenso",
    "leve": "animado",
    "curioso": "animado",
    "didatico": "calmo",
}


def _select_music(project_id: str | None) -> Path | None:
    """Pick a royalty-free track by mood (niche/tone), varied per project.

    Looks in ``music/<mood>/`` first; falls back to any track anywhere under the
    music dir. Returns None when no track exists (narration-only render).
    """
    mood = _mood_for_project(project_id)
    tracks = _list_tracks(MUSIC_DIR / mood)
    if not tracks:
        tracks = _list_tracks(MUSIC_DIR, recursive=True)
    if not tracks:
        return None
    seed = int(hashlib.md5(str(project_id or "").encode("utf-8")).hexdigest(), 16)
    return tracks[seed % len(tracks)]


def _list_tracks(directory: Path, recursive: bool = False) -> list[Path]:
    try:
        items = directory.rglob("*") if recursive else directory.iterdir()
        return sorted(
            p for p in items if p.is_file() and p.suffix.lower() in MUSIC_EXTENSIONS
        )
    except (OSError, FileNotFoundError):
        return []


def _mood_for_project(project_id: str | None) -> str:
    # Niche is the strongest theme signal; tone is only a fallback (most projects
    # default to tone "curioso", which would otherwise force everything "animado").
    project = get_project(str(project_id or "")) or {}
    # A persona/studio can pin the music mood directly.
    mood = _normalize_ascii(str(project.get("music_mood") or ""))
    if mood in MUSIC_MOODS:
        return mood
    niche = _normalize_ascii(str(project.get("niche") or ""))
    if niche in _NICHE_MOOD:
        return _NICHE_MOOD[niche]
    tone = _normalize_ascii(str(project.get("tone") or ""))
    return _TONE_MOOD.get(tone, "dramatico")


def _normalize_ascii(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return text.strip().lower()
    if not output_path.exists() or output_path.stat().st_size < 4096:
        raise RenderError("Render falhou: arquivo de saída inválido.")


def _build_thumbnail(ctx: JobContext, output_path: Path, project_id: str) -> Path | None:
    thumb_path = config.STORAGE_GENERATION_RENDERS_DIR / f"{_safe_id(project_id)}.jpg"
    command = [
        _ffmpeg(), "-y", "-ss", "1", "-i", str(output_path),
        "-frames:v", "1", "-q:v", "3", str(thumb_path),
    ]
    try:
        _run_ffmpeg(ctx, command, 120)
    except RenderError:
        return None
    return thumb_path if thumb_path.exists() else None


# ---------------------------------------------------------------------------
# FFmpeg helpers
# ---------------------------------------------------------------------------

def _run_ffmpeg(ctx: JobContext, command: list[str], timeout: int) -> str:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    ctx.set_pid(process.pid)
    try:
        _, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        ctx.set_pid(None)
        raise RenderError("ffmpeg excedeu o tempo limite.")
    ctx.set_pid(None)
    if process.returncode != 0:
        if ctx.is_cancelled():
            raise JobCancelled()
        raise RenderError(_shorten((stderr or "").replace("\n", " ").strip(), 600) or f"ffmpeg_failed_{process.returncode}")
    return stderr or ""


def _probe_duration(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        completed = subprocess.run(
            [_ffmpeg(), "-i", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, check=False,
        )
    except Exception:
        return None
    text = (completed.stderr or "") + (completed.stdout or "")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return round(int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3)), 2)


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return str(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        return "ffmpeg"


def _filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    return value


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _project_audio_path(project: dict[str, Any]) -> Path | None:
    raw = project.get("voice_audio_path") or ""
    if not raw:
        return None
    return Path(str(raw))


def _output_path(project_id: str) -> Path:
    return config.STORAGE_GENERATION_RENDERS_DIR / f"{_safe_id(project_id)}.mp4"


def _work_dir(project_id: str) -> Path:
    return config.STORAGE_GENERATION_RENDERS_DIR / f"{_safe_id(project_id)}_work"


def _safe_id(project_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(project_id)).strip("._-") or "project"


def _hash(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:20]


def _extension_from_url(url: str, media_type: str) -> str:
    match = re.search(r"\.([a-zA-Z0-9]{2,4})(?:\?|$)", url)
    if match:
        ext = "." + match.group(1).lower()
        if ext in IMAGE_EXTENSIONS or ext in {".mp4", ".mov", ".webm", ".m4v"}:
            return ext
    return ".jpg" if media_type in {"image", "screenshot", "text_card"} else ".mp4"


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _shorten(text: str, limit: int) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0]


def _ass_time(value: float) -> str:
    total_centiseconds = max(0, int(round(float(value) * 100)))
    hours, remainder = divmod(total_centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _ass_escape(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text or ""))
    return text.replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


# Register with the job queue at import time.
job_queue_service.register_handler(JOB_TYPE, _handle_render)
