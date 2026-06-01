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
from app.services.candidate_review_service import QUEUE_PATH


SOURCE_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov")


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--candidate-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--download-missing", action="store_true")
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--max-missing", type=int)
    args = parser.parse_args()

    items = _load_queue_items()
    if args.video_id:
        items = [item for item in items if str(item.get("video_id") or "") == args.video_id]
    if args.candidate_id:
        items = [item for item in items if str(item.get("candidate_id") or "") == args.candidate_id]
    if args.only_missing:
        items = [item for item in items if not _output_path_for_item(item).exists()]
    if args.max_missing is not None:
        items = items[: max(0, args.max_missing)]
    if args.limit is not None:
        items = items[: max(0, args.limit)]

    config.STORAGE_CANDIDATE_PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    interrupted = False
    try:
        total = len(items)
        for index, item in enumerate(items, start=1):
            candidate_id = str(item.get("candidate_id") or "")
            video_id = str(item.get("video_id") or "")
            start = _to_float(
                item.get("final_start_seconds")
                if item.get("final_start_seconds") is not None
                else item.get("start_seconds")
            )
            end = _to_float(
                item.get("final_end_seconds")
                if item.get("final_end_seconds") is not None
                else item.get("end_seconds")
            )
            print(f"[{index}/{total}] Rendering {candidate_id}...")
            print(f"input video_id: {video_id}")
            print(f"start/end: {start:.3f}/{end:.3f}")
            print(f"output filename: {_output_path_for_item(item).name}")
            result = _render_item(item, args.overwrite, args.dry_run, args.download_missing)
            results.append(result)
            print(result["status"].upper())
            if result.get("error_message"):
                print(result["error_message"])
    except KeyboardInterrupt:
        interrupted = True
        print("")
        print("Interrompido pelo usuário; salvando relatório parcial.")
    report = _write_report(results, args.dry_run, interrupted=interrupted)

    print("RENDER CANDIDATE PREVIEWS")
    print(f"Inputs: {len(items)}")
    print(f"Rendered: {sum(1 for item in results if item['status'] == 'rendered')}")
    print(f"Skipped: {sum(1 for item in results if item['status'] == 'skipped')}")
    print(f"Missing source: {sum(1 for item in results if item['status'] == 'missing_source')}")
    print(f"Errors: {sum(1 for item in results if item['status'] == 'error')}")
    if interrupted:
        print(f"Interrupted: true")
    print(f"Output dir: {config.STORAGE_CANDIDATE_PREVIEWS_DIR}")
    print(f"JSON: {report['json']}")
    print(f"Markdown: {report['md']}")
    for item in results:
        print(f"- {item['candidate_id']} | {item['status']} | {item['output_path']}")
        if item.get("error_message"):
            print(f"  {item['error_message']}")


def _render_item(
    item: dict[str, Any],
    overwrite: bool,
    dry_run: bool,
    download_missing: bool,
) -> dict[str, Any]:
    video_id = str(item.get("video_id") or "")
    candidate_id = str(item.get("candidate_id") or "")
    start = _to_float(item.get("final_start_seconds") if item.get("final_start_seconds") is not None else item.get("start_seconds"))
    end = _to_float(item.get("final_end_seconds") if item.get("final_end_seconds") is not None else item.get("end_seconds"))
    duration = max(0.0, end - start)
    output_path = _output_path_for_item(item)
    result = {
        "candidate_id": candidate_id,
        "video_id": video_id,
        "start_seconds": start,
        "end_seconds": end,
        "duration_seconds": duration,
        "output_path": str(output_path),
        "source_path": "",
        "downloaded_missing_source": False,
        "status": "skipped",
        "ffmpeg_command": "",
        "error_message": "",
    }
    source_path, _reason = _find_source_video(video_id)
    if not source_path and download_missing and not dry_run:
        source_path, error = _download_missing_source(video_id, str(item.get("youtube_url") or ""))
        if source_path:
            result["downloaded_missing_source"] = True
        else:
            result["error_message"] = error
    if not source_path:
        result["status"] = "missing_source"
        result["error_message"] = result["error_message"] or "fonte local não encontrada; use --download-missing"
        return result
    result["source_path"] = str(source_path)
    command = _ffmpeg_command(source_path, output_path, start, duration, overwrite)
    result["ffmpeg_command"] = " ".join(command)
    if output_path.exists() and not overwrite:
        result["status"] = "skipped"
        result["error_message"] = "preview já existe; use --overwrite"
        return result
    if dry_run:
        result["status"] = "skipped"
        result["error_message"] = "dry-run: renderização não executada"
        return result
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            check=False,
        )
    except Exception as exc:
        result["status"] = "error"
        result["error_message"] = str(exc)
        return result
    if completed.returncode != 0:
        result["status"] = "error"
        result["error_message"] = (completed.stderr or completed.stdout or "").strip()[:1000]
        return result
    result["status"] = "rendered"
    return result


def _load_queue_items() -> list[dict[str, Any]]:
    payload = _load_json(QUEUE_PATH)
    return payload.get("items", []) if isinstance(payload, dict) else []


def _output_path_for_item(item: dict[str, Any]) -> Path:
    candidate_id = str(item.get("candidate_id") or "candidate")
    filename = str(item.get("output_preview_filename") or f"{candidate_id}.mp4")
    return config.STORAGE_CANDIDATE_PREVIEWS_DIR / filename


def _find_source_video(video_id: str) -> tuple[Path | None, str]:
    for directory in [config.STORAGE_VIDEOS_DIR, config.STORAGE_DOWNLOADS_DIR, config.STORAGE_TRENDS_DIR.parent / "cache"]:
        if not directory.exists():
            continue
        exact = directory / f"{video_id}.mp4"
        if exact.exists():
            return exact, "exact_mp4"
        matches = [
            path for path in directory.glob(f"{video_id}.*")
            if path.suffix.lower() in SOURCE_EXTENSIONS
        ]
        if matches:
            return sorted(matches, key=lambda p: (p.suffix.lower() != ".mp4", p.name))[0], "matched"
    return None, "not_found"


def _download_missing_source(video_id: str, youtube_url: str) -> tuple[Path | None, str]:
    if not youtube_url:
        return None, "youtube_url ausente"
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        return None, f"yt-dlp indisponível: {exc}"
    config.STORAGE_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/best",
        "outtmpl": str(config.STORAGE_VIDEOS_DIR / f"{video_id}.%(ext)s"),
        "ffmpeg_location": _ffmpeg_executable(),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with YoutubeDL(options) as downloader:
            code = downloader.download([youtube_url])
        if code:
            return None, f"yt-dlp retornou {code}"
    except Exception as exc:
        return None, str(exc)
    return _find_source_video(video_id)[0], ""


def _ffmpeg_command(source_path: Path, output_path: Path, start: float, duration: float, overwrite: bool) -> list[str]:
    return [
        _ffmpeg_executable(),
        "-y" if overwrite else "-n",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source_path),
        "-t",
        f"{duration:.3f}",
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


def _ffmpeg_executable() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return str(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        return "ffmpeg"


def _write_report(results: list[dict[str, Any]], dry_run: bool, interrupted: bool = False) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"candidate_preview_render_report_{timestamp}.json"
    md_path = reports_dir / f"candidate_preview_render_report_{timestamp}.md"
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "interrupted": interrupted,
        "items": results,
    }
    _write_json(json_path, payload)
    md_path.write_text("# Candidate Preview Render Report\n\n" + "\n".join(f"- {r['candidate_id']}: {r['status']}" for r in results), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _to_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
