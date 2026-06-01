from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


MODEL_CHOICES = ("tiny", "base", "small", "medium")
LANGUAGE_CHOICES = ("pt", "en", "es")


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--video-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--model", choices=MODEL_CHOICES, default="base")
    parser.add_argument("--language", choices=LANGUAGE_CHOICES, default="pt")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-text", action="store_true")
    args = parser.parse_args()

    inputs = _resolve_inputs(args.input, args.video_id)
    if args.limit is not None:
        inputs = inputs[: max(0, args.limit)]

    config.STORAGE_CLIP_TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_ffmpeg_path()
    model: Any | None = None
    results: list[dict[str, Any]] = []
    for input_path in inputs:
        if not args.dry_run and model is None:
            model = _load_model(args.model)
        results.append(
            _transcribe_clip(
                input_path=input_path,
                model=model,
                model_name=args.model,
                language=args.language,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                print_text=args.print_text,
            )
        )

    print("TRANSCRIBE RENDERED CLIPS")
    print(f"Inputs: {len(inputs)}")
    print(f"Transcribed: {sum(1 for item in results if item['status'] == 'transcribed')}")
    print(f"Skipped: {sum(1 for item in results if item['status'] == 'skipped')}")
    print(f"Errors: {sum(1 for item in results if item['status'] == 'error')}")
    print(f"Output dir: {config.STORAGE_CLIP_TRANSCRIPTS_DIR}")
    print("")
    for item in results:
        print(
            f"- {Path(item['input_path']).name} | {item['status']} | "
            f"{item['output_path']} | segments={item['segments_count']}"
        )
        if item.get("error_message"):
            print(f"  {item['error_message']}")


def _resolve_inputs(input_value: str | None, video_id: str | None) -> list[Path]:
    if input_value:
        paths = [Path(input_value).expanduser().resolve()]
    else:
        paths = sorted(config.STORAGE_EXPORTS_DIR.glob("*.mp4"), key=lambda path: path.name.lower())
    if video_id:
        paths = [path for path in paths if video_id in path.name]
    return paths


def _transcribe_clip(
    input_path: Path,
    model: Any | None,
    model_name: str,
    language: str,
    overwrite: bool,
    dry_run: bool,
    print_text: bool,
) -> dict[str, Any]:
    clip_id = input_path.stem
    video_id = clip_id.split("__", 1)[0]
    output_path = config.STORAGE_CLIP_TRANSCRIPTS_DIR / f"{clip_id}.json"
    result = {
        "clip_id": clip_id,
        "video_id": video_id,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "model": model_name,
        "language": language,
        "duration_seconds": None,
        "clip_duration_seconds": _probe_duration(input_path),
        "segments_count": 0,
        "status": "skipped",
        "error_message": "",
    }

    if not input_path.exists():
        result["status"] = "error"
        result["error_message"] = "input não existe"
        return result
    if input_path.suffix.lower() != ".mp4":
        result["status"] = "error"
        result["error_message"] = "input precisa ser .mp4"
        return result
    if output_path.exists() and not overwrite:
        result["status"] = "skipped"
        result["error_message"] = "transcript já existe; use --overwrite para recriar"
        return result
    if dry_run:
        result["status"] = "skipped"
        result["error_message"] = "dry-run: transcrição não executada"
        return result
    if model is None:
        result["status"] = "error"
        result["error_message"] = "modelo Whisper não carregado"
        return result

    started = time.perf_counter()
    try:
        whisper_result = model.transcribe(
            str(input_path),
            language=language,
            task="transcribe",
            verbose=False,
            word_timestamps=False,
            condition_on_previous_text=False,
        )
    except Exception as exc:
        result["status"] = "error"
        result["error_message"] = str(exc)
        return result

    raw_segments = [
        {
            "id": segment.get("id", index),
            "start": round(float(segment.get("start", 0.0)), 2),
            "end": round(float(segment.get("end", 0.0)), 2),
            "text": str(segment.get("text", "")).strip(),
        }
        for index, segment in enumerate(whisper_result.get("segments", []))
    ]
    clip_duration = result["clip_duration_seconds"]
    segments, suspected_absolute_timestamps = _normalize_segments(raw_segments, clip_duration)
    transcript_duration = round(max((segment["end"] for segment in segments), default=0.0), 2)
    first_segment_start = segments[0]["start"] if segments else None
    last_segment_end = segments[-1]["end"] if segments else None
    payload = {
        "clip_id": clip_id,
        "video_id": video_id,
        "input_path": str(input_path),
        "model": model_name,
        "model_used": model_name,
        "language": language,
        "language_used": language,
        "duration_seconds": transcript_duration,
        "clip_duration_seconds": clip_duration,
        "transcript_duration_seconds": transcript_duration,
        "first_segment_start": first_segment_start,
        "last_segment_end": last_segment_end,
        "segment_count": len(segments),
        "suspected_absolute_timestamps": suspected_absolute_timestamps,
        "text": str(whisper_result.get("text", "")).strip(),
        "segments": segments,
        "created_at": datetime.utcnow().isoformat(),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    if print_text:
        _print_transcript_preview(payload)

    result["duration_seconds"] = transcript_duration
    result["segments_count"] = len(segments)
    result["status"] = "transcribed"
    return result


def _normalize_segments(
    segments: list[dict[str, Any]],
    clip_duration: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    if not segments:
        return [], False
    first_start = float(segments[0]["start"])
    suspected_absolute = first_start > 10.0
    if clip_duration is not None:
        suspected_absolute = suspected_absolute or any(
            float(segment["start"]) > clip_duration + 5.0 for segment in segments
        )
    offset = first_start if suspected_absolute else 0.0
    normalized: list[dict[str, Any]] = []
    for segment in segments:
        start = max(0.0, float(segment["start"]) - offset)
        end = max(start, float(segment["end"]) - offset)
        if clip_duration is not None:
            if start > clip_duration:
                continue
            end = min(end, clip_duration)
        if end <= start:
            continue
        normalized.append(
            {
                "id": segment.get("id", len(normalized)),
                "start": round(start, 2),
                "end": round(end, 2),
                "text": str(segment.get("text", "")).strip(),
            }
        )
    return normalized, suspected_absolute


def _print_transcript_preview(payload: dict[str, Any]) -> None:
    print("")
    print("CLIP TRANSCRIPT PREVIEW")
    print(f"clip_id: {payload['clip_id']}")
    print(f"model: {payload['model_used']}")
    print(f"language: {payload['language_used']}")
    print(f"text: {payload['text']}")
    print("segments:")
    for segment in payload["segments"][:5]:
        print(f"- {segment['start']} - {segment['end']}: {segment['text']}")


def _load_model(model_name: str) -> Any:
    import whisper

    return whisper.load_model(model_name, device=_detect_device())


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


def _detect_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _ensure_ffmpeg_path() -> None:
    try:
        import imageio_ffmpeg

        ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
        ffmpeg_dir = config.STORAGE_TRENDS_DIR.parent / "cache" / "ffmpeg"
        ffmpeg_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg_alias = ffmpeg_dir / "ffmpeg.exe"
        if not ffmpeg_alias.exists():
            shutil.copy2(ffmpeg_path, ffmpeg_alias)
        os.environ["PATH"] = (
            f"{ffmpeg_dir}{os.pathsep}{ffmpeg_path.parent}{os.pathsep}"
            f"{os.environ.get('PATH', '')}"
        )
    except Exception:
        pass


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
