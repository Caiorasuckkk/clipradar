from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app import config


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--clip-id")
    parser.add_argument("--input")
    args = parser.parse_args()

    clip_id, export_path = _resolve_clip(args.input, args.video_id, args.clip_id)
    if not clip_id:
        print("INSPECT CLIP SUBTITLE SYNC")
        print("Nenhum clipe encontrado. Use --input, --clip-id ou --video-id.")
        return

    video_id = clip_id.split("__", 1)[0]
    vertical_path = config.STORAGE_VERTICAL_EXPORTS_DIR / f"{clip_id}__vertical.mp4"
    subtitled_path = config.STORAGE_SUBTITLED_EXPORTS_DIR / f"{clip_id}__vertical__subtitled.mp4"
    clip_transcript_path = config.STORAGE_CLIP_TRANSCRIPTS_DIR / f"{clip_id}.json"
    source_transcript_path = config.STORAGE_TRANSCRIPTS_DIR / f"{video_id}.json"
    subtitle_path = config.STORAGE_SUBTITLES_DIR / f"{clip_id}__vertical.ass"
    latest_report_item = _latest_report_item(clip_id)

    transcript_payload = _read_json(clip_transcript_path)
    transcript_segments = _first_segments(transcript_payload, limit=5)
    ass_events = _first_ass_events(subtitle_path, limit=5)

    print("INSPECT CLIP SUBTITLE SYNC")
    print(f"clip_id: {clip_id}")
    print(f"video_id: {video_id}")
    print(f"export clip path: {_path_status(export_path)}")
    print(f"vertical path: {_path_status(vertical_path)}")
    print(f"subtitled path: {_path_status(subtitled_path)}")
    print(f"clip transcript path: {_path_status(clip_transcript_path)}")
    print(f"source transcript path: {_path_status(source_transcript_path)}")
    print(f"subtitle ass path: {_path_status(subtitle_path)}")
    print(f"export duration: {_probe_duration(export_path)}")
    print(f"vertical duration: {_probe_duration(vertical_path)}")
    print(f"subtitled duration: {_probe_duration(subtitled_path)}")
    print(f"segment_count: {_segment_count(transcript_payload)}")
    print(f"latest report transcript_source: {latest_report_item.get('transcript_source', '')}")
    print(f"latest report output_path: {latest_report_item.get('output_path', '')}")
    print("")
    print("First transcript segments:")
    for segment in transcript_segments:
        print(f"- {segment['start']} - {segment['end']}: {segment['text']}")
    if not transcript_segments:
        print("- nenhum segmento em clip_transcript")
    print("")
    print("First ASS events:")
    for event in ass_events:
        print(f"- {event['start']} - {event['end']}: {event['text']}")
    if not ass_events:
        print("- nenhum evento ASS encontrado")


def _resolve_clip(
    input_value: str | None,
    video_id: str | None,
    clip_id: str | None,
) -> tuple[str, Path]:
    if input_value:
        path = Path(input_value).expanduser().resolve()
        return _clip_id_from_path(path), _export_path_for_clip(_clip_id_from_path(path), path)

    if clip_id:
        return clip_id, config.STORAGE_EXPORTS_DIR / f"{clip_id}.mp4"

    if not video_id:
        return "", Path()

    matches = sorted(config.STORAGE_EXPORTS_DIR.glob(f"*{video_id}*.mp4"), key=lambda path: path.name.lower())
    if not matches:
        matches = sorted(config.STORAGE_VERTICAL_EXPORTS_DIR.glob(f"*{video_id}*.mp4"), key=lambda path: path.name.lower())
    if not matches:
        matches = sorted(config.STORAGE_SUBTITLED_EXPORTS_DIR.glob(f"*{video_id}*.mp4"), key=lambda path: path.name.lower())
    if not matches:
        return "", Path()
    resolved_clip_id = _clip_id_from_path(matches[0])
    return resolved_clip_id, _export_path_for_clip(resolved_clip_id, matches[0])


def _clip_id_from_path(path: Path) -> str:
    stem = path.stem
    stem = stem.removesuffix("__subtitled")
    stem = stem.removesuffix("__vertical")
    stem = stem.removesuffix("__subtitled")
    stem = stem.removesuffix("__vertical")
    return stem


def _export_path_for_clip(clip_id: str, fallback: Path) -> Path:
    export_path = config.STORAGE_EXPORTS_DIR / f"{clip_id}.mp4"
    return export_path if export_path.exists() else fallback


def _path_status(path: Path) -> str:
    exists = "exists" if path.exists() else "missing"
    return f"{path} ({exists})"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _segment_count(payload: dict[str, Any]) -> int:
    if payload.get("segment_count") is not None:
        return int(payload.get("segment_count") or 0)
    segments = payload.get("segments", [])
    return len(segments) if isinstance(segments, list) else 0


def _first_segments(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    segments = payload.get("segments", [])
    if not isinstance(segments, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for segment in segments[:limit]:
        if not isinstance(segment, dict):
            continue
        cleaned.append(
            {
                "start": segment.get("start"),
                "end": segment.get("end"),
                "text": str(segment.get("text", "")).strip(),
            }
        )
    return cleaned


def _first_ass_events(path: Path, limit: int) -> list[dict[str, str]]:
    if not path.exists():
        return []
    events: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        events.append(
            {
                "start": parts[1],
                "end": parts[2],
                "text": parts[9].replace(r"\N", " / "),
            }
        )
        if len(events) >= limit:
            break
    return events


def _latest_report_item(clip_id: str) -> dict[str, Any]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    for report_path in sorted(reports_dir.glob("subtitle_render_report_*.json"), reverse=True):
        payload = _read_json(report_path)
        items = payload.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("clip_id") == clip_id:
                return item
    return {}


def _probe_duration(input_path: Path) -> float | None:
    if not input_path.exists():
        return None
    command = [_ffmpeg_executable(), "-i", str(input_path)]
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
    text = (completed.stderr or "") + (completed.stdout or "")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return round(
        (int(match.group(1)) * 3600)
        + (int(match.group(2)) * 60)
        + float(match.group(3)),
        2,
    )


def _ffmpeg_executable() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return str(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        return "ffmpeg"


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
