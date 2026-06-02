from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MIN_PREVIEW_FILE_SIZE_BYTES = 2048


@dataclass(frozen=True)
class PreviewValidationResult:
    path: str
    valid: bool
    error_message: str
    file_size_bytes: int
    duration_seconds: float | None
    format_name: str
    video_codec: str
    audio_codec: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "valid": self.valid,
            "error_message": self.error_message,
            "file_size_bytes": self.file_size_bytes,
            "duration_seconds": self.duration_seconds,
            "format_name": self.format_name,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
        }


def validate_candidate_preview(path: Path) -> PreviewValidationResult:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return _invalid(path, "file_not_found")
    if path.suffix.lower() != ".mp4":
        return _invalid(path, "not_mp4_extension")
    file_size = path.stat().st_size
    if file_size <= MIN_PREVIEW_FILE_SIZE_BYTES:
        return _invalid(path, "file_too_small", file_size_bytes=file_size)

    command = [
        _ffprobe_executable(),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except Exception as exc:
        fallback = _validate_with_ffmpeg(path, file_size)
        if fallback:
            return fallback
        return _invalid(path, f"ffprobe_error: {exc}", file_size_bytes=file_size)
    if completed.returncode != 0:
        fallback = _validate_with_ffmpeg(path, file_size)
        if fallback:
            return fallback
        return _invalid(path, (completed.stderr or completed.stdout or "ffprobe_failed").strip()[:500], file_size_bytes=file_size)
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        return _invalid(path, f"ffprobe_json_error: {exc}", file_size_bytes=file_size)

    format_data = payload.get("format") if isinstance(payload, dict) else {}
    streams = payload.get("streams") if isinstance(payload, dict) else []
    if not isinstance(format_data, dict) or not isinstance(streams, list):
        return _invalid(path, "missing_ffprobe_format_or_streams", file_size_bytes=file_size)

    format_name = str(format_data.get("format_name") or "")
    try:
        duration = float(format_data.get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    video_stream = next((stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"), None)
    video_codec = str(video_stream.get("codec_name") or "") if isinstance(video_stream, dict) else ""
    audio_codec = str(audio_stream.get("codec_name") or "") if isinstance(audio_stream, dict) else ""

    if "mp4" not in format_name and "mov" not in format_name:
        return _invalid(path, f"invalid_container:{format_name}", file_size_bytes=file_size, duration_seconds=duration, format_name=format_name, video_codec=video_codec, audio_codec=audio_codec)
    if not video_stream:
        return _invalid(path, "missing_video_stream", file_size_bytes=file_size, duration_seconds=duration, format_name=format_name, video_codec=video_codec, audio_codec=audio_codec)
    if video_codec != "h264":
        return _invalid(path, f"invalid_video_codec:{video_codec}", file_size_bytes=file_size, duration_seconds=duration, format_name=format_name, video_codec=video_codec, audio_codec=audio_codec)
    if duration <= 0:
        return _invalid(path, "invalid_duration", file_size_bytes=file_size, duration_seconds=duration, format_name=format_name, video_codec=video_codec, audio_codec=audio_codec)

    return PreviewValidationResult(
        path=str(path),
        valid=True,
        error_message="",
        file_size_bytes=file_size,
        duration_seconds=round(duration, 3),
        format_name=format_name,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )


def _validate_with_ffmpeg(path: Path, file_size: int) -> PreviewValidationResult | None:
    command = [_ffmpeg_executable(), "-hide_banner", "-i", str(path)]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except Exception:
        return None
    output = f"{completed.stderr}\n{completed.stdout}"
    if not output.strip():
        return None
    format_match = re.search(r"Input #0,\s*([^,]+(?:,[^,]+)*)", output)
    format_name = format_match.group(1).strip() if format_match else ""
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    duration = None
    if duration_match:
        hours = float(duration_match.group(1))
        minutes = float(duration_match.group(2))
        seconds = float(duration_match.group(3))
        duration = hours * 3600 + minutes * 60 + seconds
    video_codec = "h264" if re.search(r"Video:\s*h264\b", output, re.IGNORECASE) else ""
    audio_codec = "aac" if re.search(r"Audio:\s*aac\b", output, re.IGNORECASE) else ""
    if "Invalid data found" in output or "moov atom not found" in output:
        return _invalid(path, "ffmpeg_invalid_data", file_size_bytes=file_size, duration_seconds=duration, format_name=format_name, video_codec=video_codec, audio_codec=audio_codec)
    if "mp4" not in format_name and "mov" not in format_name:
        return _invalid(path, f"invalid_container:{format_name}", file_size_bytes=file_size, duration_seconds=duration, format_name=format_name, video_codec=video_codec, audio_codec=audio_codec)
    if not video_codec:
        return _invalid(path, "missing_or_invalid_video_stream", file_size_bytes=file_size, duration_seconds=duration, format_name=format_name, video_codec=video_codec, audio_codec=audio_codec)
    if duration is None or duration <= 0:
        return _invalid(path, "invalid_duration", file_size_bytes=file_size, duration_seconds=duration, format_name=format_name, video_codec=video_codec, audio_codec=audio_codec)
    return PreviewValidationResult(
        path=str(path),
        valid=True,
        error_message="",
        file_size_bytes=file_size,
        duration_seconds=round(duration, 3),
        format_name=format_name,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )


def _invalid(
    path: Path,
    error_message: str,
    file_size_bytes: int = 0,
    duration_seconds: float | None = None,
    format_name: str = "",
    video_codec: str = "",
    audio_codec: str = "",
) -> PreviewValidationResult:
    return PreviewValidationResult(
        path=str(path),
        valid=False,
        error_message=error_message,
        file_size_bytes=file_size_bytes,
        duration_seconds=duration_seconds,
        format_name=format_name,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )


def _ffprobe_executable() -> str:
    found = shutil.which("ffprobe")
    if found:
        return found
    found_ffmpeg = shutil.which("ffmpeg")
    if found_ffmpeg:
        candidate = Path(found_ffmpeg).with_name(Path(found_ffmpeg).name.replace("ffmpeg", "ffprobe", 1))
        if candidate.exists():
            return str(candidate)
    try:
        import imageio_ffmpeg

        ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
        candidate = ffmpeg_path.with_name(ffmpeg_path.name.replace("ffmpeg", "ffprobe", 1))
        if candidate.exists():
            return str(candidate)
    except Exception:
        pass
    return "ffprobe"


def _ffmpeg_executable() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return str(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        return "ffmpeg"
