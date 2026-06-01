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


VERTICAL_FILTER = (
    "[0:v]split=2[bg][fg];"
    "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,boxblur=20:1,eq=brightness=-0.08:saturation=0.9[bgv];"
    "[fg]scale=1080:-2:force_original_aspect_ratio=decrease[fgv];"
    "[bgv][fgv]overlay=(W-w)/2:(H-h)/2[v]"
)


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--video-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    inputs = _resolve_inputs(args.input, args.video_id)
    if args.limit is not None:
        inputs = inputs[: max(0, args.limit)]

    config.STORAGE_VERTICAL_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        _render_vertical_clip(path, overwrite=args.overwrite, dry_run=args.dry_run)
        for path in inputs
    ]
    report_paths = _write_report(inputs, results, dry_run=args.dry_run)

    print("VERTICAL RENDER CLIPS")
    print(f"Inputs: {len(inputs)}")
    print(f"To render: {len(inputs)}")
    print(f"Rendered: {sum(1 for item in results if item['status'] == 'rendered')}")
    print(f"Skipped: {sum(1 for item in results if item['status'] == 'skipped')}")
    print(f"Errors: {sum(1 for item in results if item['status'] == 'error')}")
    print(f"Output dir: {config.STORAGE_VERTICAL_EXPORTS_DIR}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")
    print("")
    for item in results:
        print(f"- {Path(item['input_path']).name} | {item['status']} | {item['output_path']}")
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


def _render_vertical_clip(input_path: Path, overwrite: bool, dry_run: bool) -> dict[str, Any]:
    output_path = _output_path(input_path)
    result = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": "skipped",
        "ffmpeg_command": "",
        "error_message": "",
        "duration_seconds": _probe_duration(input_path),
        "file_size_bytes": input_path.stat().st_size if input_path.exists() else None,
    }

    if not input_path.exists():
        result["status"] = "error"
        result["error_message"] = "input não existe"
        return result
    if input_path.suffix.lower() != ".mp4":
        result["status"] = "error"
        result["error_message"] = "input precisa ser .mp4"
        return result

    command = _ffmpeg_command(input_path, output_path, overwrite=overwrite)
    result["ffmpeg_command"] = _command_for_display(command)

    if output_path.exists() and not overwrite:
        result["status"] = "skipped"
        result["error_message"] = "output já existe; use --overwrite para recriar"
        return result
    if dry_run:
        result["status"] = "skipped"
        result["error_message"] = "dry-run: renderização não executada"
        return result

    output_path.parent.mkdir(parents=True, exist_ok=True)
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
        result["error_message"] = _display(stderr, 900) or f"ffmpeg retornou {completed.returncode}"
        return result

    result["status"] = "rendered"
    result["output_file_size_bytes"] = output_path.stat().st_size if output_path.exists() else None
    return result


def _output_path(input_path: Path) -> Path:
    filename = f"{input_path.stem}__vertical.mp4"
    return config.STORAGE_VERTICAL_EXPORTS_DIR / filename


def _ffmpeg_command(input_path: Path, output_path: Path, overwrite: bool) -> list[str]:
    return [
        _ffmpeg_executable(),
        "-y" if overwrite else "-n",
        "-i",
        str(input_path),
        "-filter_complex",
        VERTICAL_FILTER,
        "-map",
        "[v]",
        "-map",
        "0:a?",
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
        "-movflags",
        "+faststart",
        str(output_path),
    ]


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
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return round((hours * 3600) + (minutes * 60) + seconds, 2)


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
    json_path = reports_dir / f"vertical_render_report_{timestamp}.json"
    md_path = reports_dir / f"vertical_render_report_{timestamp}.md"
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "total_inputs": len(inputs),
        "rendered_count": sum(1 for item in results if item["status"] == "rendered"),
        "skipped_count": sum(1 for item in results if item["status"] == "skipped"),
        "error_count": sum(1 for item in results if item["status"] == "error"),
        "output_dir": str(config.STORAGE_VERTICAL_EXPORTS_DIR),
        "items": results,
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))
    return {"json": str(json_path), "md": str(md_path)}


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Vertical Render Report",
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
                f"Duration: {item.get('duration_seconds')}s",
                f"Size: {item.get('file_size_bytes')} bytes",
                f"FFmpeg: `{item.get('ffmpeg_command', '')}`",
                f"Error: {item.get('error_message', '')}",
                "",
            ]
        )
    return "\n".join(lines)


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
