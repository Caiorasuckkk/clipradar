from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--video-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--copy", action="store_true")
    mode_group.add_argument("--reencode", action="store_true")
    args = parser.parse_args()

    inputs = _resolve_inputs(args.input, args.video_id)
    if args.limit is not None:
        inputs = inputs[: max(0, args.limit)]

    config.STORAGE_FINAL_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    mode = "reencode" if args.reencode else "copy"
    results = [
        _render_final_clip(path, overwrite=args.overwrite, dry_run=args.dry_run, mode=mode)
        for path in inputs
    ]
    report_paths = _write_report(inputs, results, dry_run=args.dry_run)

    print("FINAL RENDER CLIPS")
    print(f"Inputs: {len(inputs)}")
    print(f"To render: {len(inputs)}")
    print(f"Rendered: {sum(1 for item in results if item['status'] == 'rendered')}")
    print(f"Skipped: {sum(1 for item in results if item['status'] == 'skipped')}")
    print(f"Errors: {sum(1 for item in results if item['status'] == 'error')}")
    print(f"Output dir: {config.STORAGE_FINAL_EXPORTS_DIR}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")
    print("")
    for item in results:
        print(
            f"- {Path(item['input_path']).name} -> "
            f"{Path(item['output_path']).name} | {item['status']}"
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


def _render_final_clip(input_path: Path, overwrite: bool, dry_run: bool, mode: str) -> dict[str, Any]:
    metadata = _parse_clip_metadata(input_path.name)
    output_path = _output_path(input_path)
    duration = _probe_duration(input_path)
    result = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": "skipped",
        "ffmpeg_command": "",
        "error_message": "",
        "video_id": metadata["video_id"],
        "rank": metadata["rank"],
        "rating": metadata["rating"],
        "reason": metadata["reason"],
        "start_seconds": metadata["start_seconds"],
        "end_seconds": metadata["end_seconds"],
        "duration_seconds": duration,
        "file_size_bytes": input_path.stat().st_size if input_path.exists() else None,
        "mode": mode,
    }

    if not input_path.exists():
        result["status"] = "error"
        result["error_message"] = "input não existe"
        return result
    if input_path.suffix.lower() != ".mp4":
        result["status"] = "error"
        result["error_message"] = "input precisa ser .mp4"
        return result

    command = _ffmpeg_command(
        input_path=input_path,
        output_path=output_path,
        overwrite=overwrite,
        mode=mode,
    )
    result["ffmpeg_command"] = _command_for_display(command)

    if dry_run:
        result["status"] = "skipped"
        result["error_message"] = "dry-run: renderização não executada"
        return result
    if output_path.exists() and not overwrite:
        result["status"] = "skipped"
        result["error_message"] = "output já existe; use --overwrite para recriar"
        return result

    output_path.parent.mkdir(parents=True, exist_ok=True)
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
        result["error_message"] = _display(stderr, 1200) or f"ffmpeg retornou {completed.returncode}"
        return result

    result["status"] = "rendered"
    result["output_file_size_bytes"] = output_path.stat().st_size if output_path.exists() else None
    return result


def _output_path(input_path: Path) -> Path:
    return config.STORAGE_FINAL_EXPORTS_DIR / f"{input_path.stem}__final.mp4"


def _parse_clip_metadata(filename: str) -> dict[str, Any]:
    stem = Path(filename).stem.removesuffix("__vertical")
    parts = stem.split("__")
    metadata: dict[str, Any] = {
        "video_id": parts[0] if parts else "",
        "rank": None,
        "rating": None,
        "reason": "",
        "start_seconds": None,
        "end_seconds": None,
    }
    for part in parts[1:]:
        if part.startswith("rank_"):
            metadata["rank"] = _to_int(part.removeprefix("rank_"))
        elif part.startswith("rating_"):
            metadata["rating"] = _to_int(part.removeprefix("rating_"))
        elif re.fullmatch(r"\d+(?:\.\d+)?_\d+(?:\.\d+)?", part):
            start, end = part.split("_", 1)
            metadata["start_seconds"] = _to_float(start)
            metadata["end_seconds"] = _to_float(end)
        elif part:
            metadata["reason"] = part
    return metadata


def _ffmpeg_command(
    input_path: Path,
    output_path: Path,
    overwrite: bool,
    mode: str,
) -> list[str]:
    command = [
        _ffmpeg_executable(),
        "-y" if overwrite else "-n",
        "-i",
        str(input_path),
    ]
    if mode == "reencode":
        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
            ]
        )
    else:
        command.extend(
            [
                "-c",
                "copy",
            ]
        )
    command.extend(["-movflags", "+faststart", str(output_path)])
    return command


def _probe_duration(input_path: Path) -> float | None:
    if not input_path.exists():
        return None
    command = [
        _ffprobe_executable(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
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
    except Exception:
        return _probe_duration_with_ffmpeg(input_path)
    if completed.returncode != 0:
        return _probe_duration_with_ffmpeg(input_path)
    try:
        return round(float((completed.stdout or "").strip()), 2)
    except (TypeError, ValueError):
        return _probe_duration_with_ffmpeg(input_path)


def _probe_duration_with_ffmpeg(input_path: Path) -> float | None:
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


def _ffprobe_executable() -> str:
    found = shutil.which("ffprobe")
    if found:
        return found
    ffmpeg = _ffmpeg_executable()
    ffmpeg_path = Path(ffmpeg)
    if ffmpeg_path.name.lower().startswith("ffmpeg"):
        candidate = ffmpeg_path.with_name(ffmpeg_path.name.replace("ffmpeg", "ffprobe", 1))
        if candidate.exists():
            return str(candidate)
    return "ffprobe"


def _write_report(
    inputs: list[Path],
    results: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"final_render_report_{timestamp}.json"
    md_path = reports_dir / f"final_render_report_{timestamp}.md"
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "total_inputs": len(inputs),
        "rendered_count": sum(1 for item in results if item["status"] == "rendered"),
        "skipped_count": sum(1 for item in results if item["status"] == "skipped"),
        "error_count": sum(1 for item in results if item["status"] == "error"),
        "output_dir": str(config.STORAGE_FINAL_EXPORTS_DIR),
        "items": results,
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))
    return {"json": str(json_path), "md": str(md_path)}


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Final Render Report",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Dry run: {str(payload['dry_run']).lower()}",
        f"Total inputs: {payload['total_inputs']}",
        f"Rendered: {payload['rendered_count']}",
        f"Skipped: {payload['skipped_count']}",
        f"Errors: {payload['error_count']}",
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
                f"Video ID: {item.get('video_id')}",
                f"Rank: {item.get('rank')}",
                f"Rating: {item.get('rating')}",
                f"Reason: {item.get('reason')}",
                f"Mode: {item.get('mode')}",
                f"Size: {item.get('file_size_bytes')} bytes",
                f"FFmpeg: `{item.get('ffmpeg_command', '')}`",
                f"Error: {item.get('error_message', '')}",
                "",
            ]
        )
    return "\n".join(lines)


def _to_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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
