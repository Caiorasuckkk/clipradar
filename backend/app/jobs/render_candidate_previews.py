from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.candidate_review_service import QUEUE_PATH
from app.services.candidate_preview_validation_service import validate_candidate_preview


SOURCE_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov")
FAILED_DOWNLOADS_PATH = config.STORAGE_TRENDS_DIR.parent / "reports" / "failed_candidate_downloads.json"


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
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--clean-partials", action="store_true")
    parser.add_argument("--rerender-invalid", action="store_true")
    args = parser.parse_args()

    items = _load_queue_items()
    if args.retry_failed:
        failed_ids = {
            str(item.get("candidate_id") or "")
            for item in _load_failed_downloads()
            if item.get("candidate_id")
        }
        items = [item for item in items if str(item.get("candidate_id") or "") in failed_ids]
    if args.video_id:
        items = [item for item in items if str(item.get("video_id") or "") == args.video_id]
    if args.candidate_id:
        items = [item for item in items if str(item.get("candidate_id") or "") == args.candidate_id]
    if args.only_missing:
        items = [item for item in items if not validate_candidate_preview(_output_path_for_item(item)).valid]
    if args.rerender_invalid:
        items = [
            item
            for item in items
            if _output_path_for_item(item).exists()
            and not validate_candidate_preview(_output_path_for_item(item)).valid
        ]
    if args.max_missing is not None:
        items = items[: max(0, args.max_missing)]
    if args.limit is not None:
        items = items[: max(0, args.limit)]

    config.STORAGE_CANDIDATE_PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    if args.clean_partials:
        removed = _clean_partials_for_items(items)
        print(f"Cleaned partial files: {removed}")
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
    print(f"Invalid: {sum(1 for item in results if item['status'] == 'invalid_preview')}")
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
        source_path, error, retry_count = _download_missing_source(video_id, str(item.get("youtube_url") or ""))
        if source_path:
            result["downloaded_missing_source"] = True
        else:
            result["error_message"] = error
            result["download_retry_count"] = retry_count
            _record_failed_download(
                video_id=video_id,
                candidate_id=candidate_id,
                youtube_url=str(item.get("youtube_url") or ""),
                error_message=error,
                retry_count=retry_count,
            )
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
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass
        result["status"] = "error"
        result["error_message"] = (completed.stderr or completed.stdout or "").strip()[:1000]
        return result
    validation = validate_candidate_preview(output_path)
    result["preview_validation"] = validation.to_dict()
    if not validation.valid:
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass
        result["status"] = "invalid_preview"
        result["error_message"] = validation.error_message
        return result
    result["status"] = "rendered"
    _clear_failed_download(video_id=video_id, candidate_id=candidate_id)
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


def _download_missing_source(video_id: str, youtube_url: str, max_attempts: int = 3) -> tuple[Path | None, str, int]:
    if not youtube_url:
        return None, "youtube_url ausente", 0
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        return None, f"yt-dlp indisponível: {exc}", 0
    config.STORAGE_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/best",
        "outtmpl": str(config.STORAGE_VIDEOS_DIR / f"{video_id}.%(ext)s"),
        "ffmpeg_location": _ffmpeg_executable(),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            with YoutubeDL(options) as downloader:
                code = downloader.download([youtube_url])
            if code:
                last_error = f"yt-dlp retornou {code}"
            else:
                source_path = _find_source_video(video_id)[0]
                if source_path:
                    return source_path, "", attempt
                last_error = "download concluído, mas fonte local não encontrada"
        except Exception as exc:
            last_error = str(exc)
        if attempt < max_attempts:
            time.sleep(min(8, attempt * 2))
    return None, last_error, max_attempts


def _load_failed_downloads() -> list[dict[str, Any]]:
    payload = _load_json(FAILED_DOWNLOADS_PATH)
    return payload if isinstance(payload, list) else []


def _record_failed_download(
    video_id: str,
    candidate_id: str,
    youtube_url: str,
    error_message: str,
    retry_count: int,
) -> None:
    failures = _load_failed_downloads()
    next_failures = [
        failure
        for failure in failures
        if not (
            str(failure.get("video_id") or "") == video_id
            and str(failure.get("candidate_id") or "") == candidate_id
        )
    ]
    next_failures.append(
        {
            "video_id": video_id,
            "candidate_id": candidate_id,
            "youtube_url": youtube_url,
            "error_message": error_message,
            "failed_at": datetime.utcnow().isoformat(),
            "retry_count": retry_count,
        }
    )
    _write_json(FAILED_DOWNLOADS_PATH, next_failures)


def _clear_failed_download(video_id: str, candidate_id: str) -> None:
    failures = _load_failed_downloads()
    next_failures = [
        failure
        for failure in failures
        if not (
            str(failure.get("video_id") or "") == video_id
            and str(failure.get("candidate_id") or "") == candidate_id
        )
    ]
    if len(next_failures) != len(failures):
        _write_json(FAILED_DOWNLOADS_PATH, next_failures)


def _clean_partials_for_items(items: list[dict[str, Any]]) -> int:
    video_ids = {str(item.get("video_id") or "") for item in items if item.get("video_id")}
    if not video_ids:
        return 0
    directories = [
        config.STORAGE_VIDEOS_DIR,
        config.STORAGE_DOWNLOADS_DIR,
        config.STORAGE_TRENDS_DIR.parent / "cache",
    ]
    removed = 0
    for directory in directories:
        if not directory.exists():
            continue
        root = directory.resolve()
        for video_id in video_ids:
            for pattern in (f"{video_id}*.part", f"{video_id}*.ytdl", f"{video_id}*.temp", f"{video_id}*.tmp"):
                for path in directory.glob(pattern):
                    try:
                        resolved = path.resolve()
                        if not resolved.is_file() or root not in resolved.parents:
                            continue
                        resolved.unlink()
                        removed += 1
                    except Exception:
                        pass
    return removed


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
        "-pix_fmt",
        "yuv420p",
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
    path.parent.mkdir(parents=True, exist_ok=True)
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
