from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


MAX_LINE_CHARS = 34
MAX_BLOCK_SECONDS = 4.0
MIN_BLOCK_SECONDS = 1.0


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--video-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--subtitle-offset", type=float, default=0.0)
    args = parser.parse_args()

    inputs = _resolve_inputs(args.input, args.video_id)
    if args.limit is not None:
        inputs = inputs[: max(0, args.limit)]

    config.STORAGE_SUBTITLED_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config.STORAGE_SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)
    plan_index = _latest_plan_index()
    results = [
        _render_subtitled_clip(
            input_path=path,
            plan_index=plan_index,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            subtitle_offset=args.subtitle_offset,
        )
        for path in inputs
    ]
    report_paths = _write_report(inputs, results, dry_run=args.dry_run)

    print("SUBTITLE RENDER CLIPS")
    print(f"Inputs: {len(inputs)}")
    print(f"To render: {len(inputs)}")
    print(f"Rendered: {sum(1 for item in results if item['status'] == 'rendered')}")
    print(f"Skipped: {sum(1 for item in results if item['status'] == 'skipped')}")
    print(f"Missing transcript: {sum(1 for item in results if item['status'] == 'missing_transcript')}")
    print(f"Missing clip time: {sum(1 for item in results if item['status'] == 'missing_clip_time')}")
    print(f"Timing errors: {sum(1 for item in results if item['status'] == 'timing_error')}")
    print(f"Errors: {sum(1 for item in results if item['status'] == 'error')}")
    print(f"Output dir: {config.STORAGE_SUBTITLED_EXPORTS_DIR}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")
    print("")
    for item in results:
        print(
            f"- {Path(item['input_path']).name} | subtitles={item['subtitle_count']} | "
            f"{item['status']} | {item['output_path']}"
        )
        if item.get("error_message"):
            print(f"  {item['error_message']}")


def _resolve_inputs(input_value: str | None, video_id: str | None) -> list[Path]:
    if input_value:
        paths = [Path(input_value).expanduser().resolve()]
    else:
        paths = sorted(
            config.STORAGE_VERTICAL_EXPORTS_DIR.glob("*.mp4"),
            key=lambda path: path.name.lower(),
        )
    if video_id:
        paths = [path for path in paths if video_id in path.name]
    return paths


def _render_subtitled_clip(
    input_path: Path,
    plan_index: dict[str, dict[str, Any]],
    overwrite: bool,
    dry_run: bool,
    subtitle_offset: float,
) -> dict[str, Any]:
    output_path = _output_path(input_path)
    clip_id = _clip_id_from_filename(input_path.name)
    video_id = _video_id_from_filename(input_path.name)
    subtitle_path = config.STORAGE_SUBTITLES_DIR / f"{input_path.stem}.ass"
    clip_transcript_path = config.STORAGE_CLIP_TRANSCRIPTS_DIR / f"{clip_id}.json"
    source_transcript_path = config.STORAGE_TRANSCRIPTS_DIR / f"{video_id}.json"
    clip_start, clip_end = _clip_time_from_filename(input_path.name)
    if clip_start is None or clip_end is None:
        clip_start, clip_end = _clip_time_from_plan(input_path.name, plan_index)
    clip_duration = _probe_duration(input_path)
    result = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "subtitle_ass_path": str(subtitle_path),
        "video_id": video_id,
        "clip_id": clip_id,
        "clip_start": clip_start,
        "clip_end": clip_end,
        "clip_duration_seconds": clip_duration,
        "transcript_source": "",
        "clip_transcript_path": str(clip_transcript_path),
        "source_transcript_path": str(source_transcript_path),
        "missing_clip_transcript": not clip_transcript_path.exists(),
        "subtitle_count": 0,
        "first_subtitle_start": None,
        "subtitle_offset_seconds": subtitle_offset,
        "possible_absolute_timestamps": False,
        "timing_error": False,
        "status": "skipped",
        "error_message": "",
        "ffmpeg_command": "",
    }

    if not input_path.exists():
        result["status"] = "error"
        result["error_message"] = "input não existe"
        return result
    if input_path.suffix.lower() != ".mp4":
        result["status"] = "error"
        result["error_message"] = "input precisa ser .mp4"
        return result

    if clip_transcript_path.exists():
        subtitles, timing_error = _subtitles_from_clip_transcript(clip_transcript_path, clip_duration)
        result["timing_error"] = timing_error
        result["transcript_source"] = "clip_transcript"
    else:
        result["transcript_source"] = "source_video_transcript"
        if not source_transcript_path.exists():
            result["status"] = "missing_transcript"
            result["error_message"] = f"transcript não encontrado: {source_transcript_path}"
            return result
        if clip_start is None or clip_end is None or clip_end <= clip_start:
            result["status"] = "missing_clip_time"
            result["error_message"] = "não foi possível descobrir start/end do clipe"
            return result
        subtitles = _subtitles_for_clip(source_transcript_path, clip_start, clip_end)
    subtitles = _apply_subtitle_offset(subtitles, subtitle_offset, clip_duration)
    result["subtitle_count"] = len(subtitles)
    result["first_subtitle_start"] = subtitles[0]["start"] if subtitles else None
    result["possible_absolute_timestamps"] = bool(
        subtitles and float(subtitles[0]["start"]) > 10.0
    )
    _print_subtitle_input(result)

    if result["timing_error"]:
        result["status"] = "timing_error"
        result["error_message"] = "clip_transcript contém segmento fora da duração do clipe"
        return result
    if result["possible_absolute_timestamps"]:
        result["error_message"] = "warning: possível timestamp absoluto no primeiro subtitle"
    _write_ass_file(subtitle_path, subtitles)
    command = _ffmpeg_command(input_path, subtitle_path, output_path, overwrite=overwrite)
    result["ffmpeg_command"] = _command_for_display(command)

    if output_path.exists() and not overwrite:
        result["status"] = "skipped"
        result["error_message"] = "output já existe; use --overwrite para recriar"
        return result
    if not subtitles:
        result["status"] = "error"
        result["error_message"] = "nenhuma legenda encontrada para o intervalo do clipe"
        return result
    if dry_run:
        result["status"] = "skipped"
        result["error_message"] = "dry-run: burn-in não executado"
        return result
    if output_path.exists() and overwrite:
        output_path.unlink()

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1200,
            check=False,
        )
    except Exception as exc:
        result["status"] = "error"
        result["error_message"] = str(exc)
        return result

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        result["status"] = "error"
        result["error_message"] = _display(stderr, 1000) or f"ffmpeg retornou {completed.returncode}"
        return result

    result["status"] = "rendered"
    return result


def _output_path(input_path: Path) -> Path:
    return config.STORAGE_SUBTITLED_EXPORTS_DIR / f"{input_path.stem}__subtitled.mp4"


def _clip_id_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    return stem.removesuffix("__vertical")


def _video_id_from_filename(filename: str) -> str:
    return _clip_id_from_filename(filename).split("__", 1)[0]


def _clip_time_from_filename(filename: str) -> tuple[float | None, float | None]:
    stem = Path(filename).stem
    match = re.search(r"__(\d+(?:\.\d+)?)_(\d+(?:\.\d+)?)(?:__vertical)?$", stem)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _clip_time_from_plan(
    filename: str,
    plan_index: dict[str, dict[str, Any]],
) -> tuple[float | None, float | None]:
    base_name = Path(filename).name.replace("__vertical.mp4", ".mp4")
    item = plan_index.get(base_name) or plan_index.get(Path(base_name).stem)
    if not item:
        return None, None
    start = _to_float(item.get("final_start_seconds") or item.get("start_seconds"))
    end = _to_float(item.get("final_end_seconds") or item.get("end_seconds"))
    return start, end


def _latest_plan_index() -> dict[str, dict[str, Any]]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    paths = sorted(reports_dir.glob("approved_clips_plan_*.json"))
    if not paths:
        return {}
    try:
        with paths[-1].open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return {}
    items = payload.get("items", []) if isinstance(payload, dict) else []
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        output_filename = str(item.get("output_filename") or "")
        if output_filename:
            indexed[Path(output_filename).name] = item
            indexed[Path(output_filename).stem] = item
    return indexed


def _subtitles_for_clip(
    transcript_path: Path,
    clip_start: float,
    clip_end: float,
) -> list[dict[str, Any]]:
    with transcript_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    segments = payload.get("segments", []) if isinstance(payload, dict) else []
    subtitles: list[dict[str, Any]] = []
    clip_duration = max(0.0, clip_end - clip_start)
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        start = _to_float(segment.get("start"))
        end = _to_float(segment.get("end"))
        text = _clean_text(segment.get("text"))
        if start is None or end is None:
            continue
        if not text or len(text) < 2 or end <= clip_start or start >= clip_end:
            continue
        relative_start = max(0.0, start - clip_start)
        relative_end = min(clip_duration, end - clip_start)
        if relative_end <= relative_start:
            continue
        subtitles.extend(_split_subtitle_block(relative_start, relative_end, text))
    return subtitles


def _subtitles_from_clip_transcript(
    transcript_path: Path,
    clip_duration: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    with transcript_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    segments = payload.get("segments", []) if isinstance(payload, dict) else []
    subtitles: list[dict[str, Any]] = []
    transcript_duration = _to_float(
        payload.get("clip_duration_seconds") or payload.get("duration_seconds")
    )
    effective_duration = clip_duration if clip_duration is not None else transcript_duration
    timing_error = False
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        start = _to_float(segment.get("start"))
        end = _to_float(segment.get("end"))
        text = _clean_text(segment.get("text"))
        if start is None or end is None:
            continue
        if effective_duration is not None and start > effective_duration:
            timing_error = True
            continue
        if effective_duration is not None:
            end = min(end, effective_duration)
        if not text or len(text) < 2 or end <= start:
            continue
        subtitles.extend(_split_subtitle_block(max(0.0, start), end, text))
    return subtitles, timing_error


def _apply_subtitle_offset(
    subtitles: list[dict[str, Any]],
    offset: float,
    clip_duration: float | None,
) -> list[dict[str, Any]]:
    if offset == 0:
        return subtitles
    adjusted: list[dict[str, Any]] = []
    for subtitle in subtitles:
        start = max(0.0, float(subtitle["start"]) + offset)
        end = max(start + 0.4, float(subtitle["end"]) + offset)
        if clip_duration is not None:
            if start > clip_duration:
                continue
            end = min(end, clip_duration)
        if end <= start:
            continue
        adjusted.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "text": subtitle["text"],
            }
        )
    return adjusted


def _print_subtitle_input(result: dict[str, Any]) -> None:
    print("")
    print("SUBTITLE INPUT")
    print(f"input file: {result['input_path']}")
    print(f"clip_id: {result['clip_id']}")
    print(f"transcript_source: {result['transcript_source']}")
    print(f"clip_transcript_path: {result['clip_transcript_path']}")
    print(f"source_transcript_path: {result['source_transcript_path']}")
    print(f"clip_start: {result['clip_start']}")
    print(f"clip_end: {result['clip_end']}")
    print(f"subtitle_count: {result['subtitle_count']}")


def _split_subtitle_block(start: float, end: float, text: str) -> list[dict[str, Any]]:
    duration = max(0.0, end - start)
    chunks = _text_chunks(text)
    if duration > MAX_BLOCK_SECONDS and len(chunks) == 1:
        chunks = _text_chunks(text, max_chars=MAX_LINE_CHARS)
    if not chunks:
        return []
    slice_duration = duration / len(chunks)
    subtitles: list[dict[str, Any]] = []
    current = start
    for index, chunk in enumerate(chunks):
        block_start = current
        block_end = end if index == len(chunks) - 1 else min(end, current + max(MIN_BLOCK_SECONDS, slice_duration))
        if block_end - block_start > MAX_BLOCK_SECONDS:
            block_end = block_start + MAX_BLOCK_SECONDS
        current = block_end
        subtitles.append(
            {
                "start": round(block_start, 2),
                "end": round(max(block_start + 0.4, min(end, block_end)), 2),
                "text": _wrap_subtitle_text(chunk),
            }
        )
        if current >= end:
            break
    return subtitles


def _text_chunks(text: str, max_chars: int = MAX_LINE_CHARS * 2) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not parts:
        parts = [text]
    chunks: list[str] = []
    for part in parts:
        if len(part) <= max_chars:
            chunks.append(part)
            continue
        words = part.split()
        current: list[str] = []
        for word in words:
            candidate = " ".join(current + [word])
            if len(candidate) > max_chars and current:
                chunks.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            chunks.append(" ".join(current))
    return chunks


def _wrap_subtitle_text(text: str) -> str:
    lines = textwrap.wrap(text, width=MAX_LINE_CHARS, break_long_words=False, break_on_hyphens=False)
    if len(lines) <= 2:
        return r"\N".join(lines)
    first = lines[0]
    second = " ".join(lines[1:])
    second = textwrap.shorten(second, width=MAX_LINE_CHARS, placeholder="")
    return rf"{first}\N{second}".strip()


def _write_ass_file(path: Path, subtitles: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Default,Arial,62,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,0,0,1,4,1,2,80,80,220,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for subtitle in subtitles:
        lines.append(
            "Dialogue: 0,"
            f"{_ass_time(subtitle['start'])},{_ass_time(subtitle['end'])},"
            f"Default,,0,0,0,,{_ass_escape(subtitle['text'])}"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _ffmpeg_command(input_path: Path, subtitle_path: Path, output_path: Path, overwrite: bool) -> list[str]:
    return [
        _ffmpeg_executable(),
        "-y" if overwrite else "-n",
        "-i",
        str(input_path),
        "-vf",
        f"ass='{_ffmpeg_filter_path(subtitle_path)}'",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def _ffmpeg_filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    return value


def _ffmpeg_executable() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return str(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        return "ffmpeg"


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


def _write_report(
    inputs: list[Path],
    results: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"subtitle_render_report_{timestamp}.json"
    md_path = reports_dir / f"subtitle_render_report_{timestamp}.md"
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "total_inputs": len(inputs),
        "rendered_count": sum(1 for item in results if item["status"] == "rendered"),
        "skipped_count": sum(1 for item in results if item["status"] == "skipped"),
        "error_count": sum(1 for item in results if item["status"] == "error"),
        "timing_error_count": sum(1 for item in results if item["status"] == "timing_error"),
        "missing_transcript_count": sum(1 for item in results if item["status"] == "missing_transcript"),
        "missing_clip_time_count": sum(1 for item in results if item["status"] == "missing_clip_time"),
        "output_dir": str(config.STORAGE_SUBTITLED_EXPORTS_DIR),
        "items": results,
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))
    return {"json": str(json_path), "md": str(md_path)}


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Subtitle Render Report",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Dry run: {str(payload['dry_run']).lower()}",
        f"Total inputs: {payload['total_inputs']}",
        f"Rendered: {payload['rendered_count']}",
        f"Skipped: {payload['skipped_count']}",
        f"Errors: {payload['error_count']}",
        f"Timing errors: {payload['timing_error_count']}",
        f"Missing transcript: {payload['missing_transcript_count']}",
        f"Missing clip time: {payload['missing_clip_time_count']}",
        f"Output dir: {payload['output_dir']}",
        "",
        "## Items",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"### {Path(item['input_path']).name} - {item['status']}",
                "",
                f"Input: {item['input_path']}",
                f"Output: {item['output_path']}",
                f"ASS: {item['subtitle_ass_path']}",
                f"Video ID: {item['video_id']}",
                f"Transcript source: {item['transcript_source']}",
                f"Clip transcript: {item['clip_transcript_path']}",
                f"Source transcript: {item['source_transcript_path']}",
                f"Missing clip transcript: {item['missing_clip_transcript']}",
                f"Clip: {item['clip_start']} - {item['clip_end']}",
                f"Clip duration: {item['clip_duration_seconds']}",
                f"Subtitle offset: {item['subtitle_offset_seconds']}",
                f"Subtitles: {item['subtitle_count']}",
                f"First subtitle start: {item['first_subtitle_start']}",
                f"Possible absolute timestamps: {item['possible_absolute_timestamps']}",
                f"Timing error: {item['timing_error']}",
                f"FFmpeg: `{item['ffmpeg_command']}`",
                f"Error: {item['error_message']}",
                "",
            ]
        )
    return "\n".join(lines)


def _ass_time(value: float) -> str:
    total_centiseconds = max(0, int(round(value * 100)))
    hours, remainder = divmod(total_centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("{", r"\{").replace("}", r"\}")


def _clean_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _to_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _command_for_display(command: list[str]) -> str:
    return " ".join(_quote_arg(arg) for arg in command)


def _quote_arg(arg: object) -> str:
    text = str(arg)
    if not text or re.search(r"\s", text):
        return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
    return text


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
