from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config


PLAN_LIST_KEYS = ("items", "clips", "approved_clips", "plan", "approved", "data")
SOURCE_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov")
MIN_RENDER_SECONDS = 5.0
MAX_RENDER_SECONDS = 180.0
MISSING_SOURCE_MESSAGE = (
    "Vídeo original não encontrado. Rode process_queue antes ou use "
    "--download-missing para baixar a fonte via yt-dlp."
)


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-path")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--video-id")
    parser.add_argument("--rank", type=int)
    parser.add_argument("--min-rating", type=float, default=4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--download-missing", action="store_true")
    parser.add_argument("--open-folder", action="store_true")
    args = parser.parse_args()

    plan_path = _resolve_plan_path(args.plan_path)
    if not plan_path:
        print("RENDER APPROVED CLIPS")
        print("Plan: nenhum approved_clips_plan_*.json encontrado")
        return

    plan_payload = _load_json(plan_path)
    items = _extract_items(plan_payload)
    if items is None:
        keys = sorted(plan_payload.keys()) if isinstance(plan_payload, dict) else []
        print("RENDER APPROVED CLIPS")
        print(f"Plan: {plan_path}")
        print("Erro: lista de clips não encontrada no plano.")
        print(f"Chaves disponíveis: {', '.join(keys) if keys else '(payload não é objeto)'}")
        return

    filtered = [
        item
        for item in items
        if _to_float(item.get("review_rating")) >= args.min_rating
        and (not args.video_id or str(item.get("video_id") or "") == args.video_id)
        and (args.rank is None or int(item.get("rank") or 0) == args.rank)
    ]
    if args.limit is not None:
        filtered = filtered[: max(0, args.limit)]

    config.STORAGE_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        _render_item(
            item=item,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            download_missing=args.download_missing,
        )
        for item in filtered
    ]
    report_paths = _write_report(
        plan_path=plan_path,
        total_items=len(items),
        selected_items=len(filtered),
        results=results,
        dry_run=args.dry_run,
    )

    print("RENDER APPROVED CLIPS")
    print(f"Plan: {plan_path}")
    print(f"Items loaded: {len(items)}")
    print(f"To render: {len(filtered)}")
    print(f"Rendered: {sum(1 for item in results if item['status'] == 'rendered')}")
    print(f"Skipped: {sum(1 for item in results if item['status'] == 'skipped')}")
    print(f"Errors: {sum(1 for item in results if item['status'] == 'error')}")
    print(f"Missing source: {sum(1 for item in results if item['status'] == 'missing_source')}")
    print(f"Downloaded missing source: {sum(1 for item in results if item['downloaded_missing_source'])}")
    print(f"Exports: {config.STORAGE_EXPORTS_DIR}")
    print(f"JSON: {report_paths['json']}")
    print(f"Markdown: {report_paths['md']}")
    print("")
    for result in results:
        print(
            f"- {result['video_id']} | {_display(result['title'], 70)} | "
            f"{_mmss(result['final_start'])} até {_mmss(result['final_end'])} | "
            f"{Path(result['output_path']).name if result.get('output_path') else ''} | "
            f"{result['status']}"
        )
        if result.get("error_message"):
            print(f"  {result['error_message']}")

    if args.open_folder:
        _open_exports_folder()


def _resolve_plan_path(path_value: str | None) -> Path | None:
    if path_value:
        return Path(path_value).expanduser().resolve()
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    paths = sorted(reports_dir.glob("approved_clips_plan_*.json"))
    return paths[-1] if paths else None


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _extract_items(payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return None
    for key in PLAN_LIST_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for key, value in payload.items():
        if isinstance(value, list) and key.endswith("_clips"):
            return [item for item in value if isinstance(item, dict)]
    return None


def _render_item(
    item: dict[str, Any],
    dry_run: bool,
    overwrite: bool,
    download_missing: bool,
) -> dict[str, Any]:
    video_id = str(item.get("video_id") or "")
    title = str(item.get("video_title") or item.get("title") or "")
    rank = int(item.get("rank") or 0)
    rating = item.get("review_rating")
    reason = str(item.get("review_reason") or "sem_reason")
    youtube_url = str(item.get("youtube_url") or "")
    start = _to_float(item.get("final_start_seconds", item.get("start_seconds")))
    end = _to_float(item.get("final_end_seconds", item.get("end_seconds")))
    duration = _to_float(item.get("final_duration_seconds")) or max(0.0, end - start)
    if duration <= 0:
        duration = max(0.0, end - start)
    output_filename = str(item.get("output_filename") or "") or _output_filename(
        video_id,
        rank,
        _to_float(rating),
        reason,
        start,
        end,
    )
    output_path = config.STORAGE_EXPORTS_DIR / output_filename
    result = {
        "video_id": video_id,
        "title": title,
        "rank": rank,
        "rating": rating,
        "reason": reason,
        "start": _to_float(item.get("start_seconds")),
        "end": _to_float(item.get("end_seconds")),
        "final_start": round(start, 2),
        "final_end": round(end, 2),
        "duration": round(duration, 2),
        "output_path": str(output_path),
        "source_path": "",
        "source_found": False,
        "downloaded_missing_source": False,
        "download_error": "",
        "source_resolution_reason": "",
        "status": "skipped",
        "ffmpeg_command": "",
        "error_message": "",
    }

    if duration <= MIN_RENDER_SECONDS or duration >= MAX_RENDER_SECONDS:
        result["status"] = "error"
        result["error_message"] = (
            f"duração inválida para render: {duration:.2f}s "
            f"(esperado > {MIN_RENDER_SECONDS:.0f}s e < {MAX_RENDER_SECONDS:.0f}s)"
        )
        return result

    source_path, source_reason = _find_source_video(video_id)
    result["source_resolution_reason"] = source_reason

    if not source_path and download_missing:
        if dry_run:
            result["source_resolution_reason"] = "dry_run_download_missing_not_executed"
        elif not youtube_url:
            result["download_error"] = "youtube_url ausente no plano"
            result["source_resolution_reason"] = "missing_youtube_url"
        else:
            source_path, download_error = _download_missing_source(video_id, youtube_url)
            if source_path:
                result["downloaded_missing_source"] = True
                result["source_resolution_reason"] = "downloaded_missing_source"
            else:
                result["download_error"] = download_error
                result["source_resolution_reason"] = "download_failed"

    if not source_path:
        result["status"] = "missing_source"
        result["error_message"] = result["download_error"] or MISSING_SOURCE_MESSAGE
        return result

    result["source_path"] = str(source_path)
    result["source_found"] = True

    command = _ffmpeg_command(source_path, output_path, start, duration, overwrite=overwrite)
    result["ffmpeg_command"] = _command_for_display(command)

    if output_path.exists() and not overwrite:
        result["status"] = "skipped"
        result["error_message"] = "arquivo de saída já existe; use --overwrite para recriar"
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
            timeout=900,
            check=False,
        )
    except Exception as exc:
        result["status"] = "error"
        result["error_message"] = str(exc)
        return result

    if completed.returncode != 0:
        result["status"] = "error"
        stderr = (completed.stderr or completed.stdout or "").strip()
        result["error_message"] = _display(stderr, 800) or f"ffmpeg retornou {completed.returncode}"
        return result

    result["status"] = "rendered"
    return result


def _find_source_video(video_id: str) -> tuple[Path | None, str]:
    if not video_id:
        return None, "missing_video_id"
    search_dirs = [
        config.STORAGE_DOWNLOADS_DIR,
        config.STORAGE_VIDEOS_DIR,
        config.STORAGE_TRENDS_DIR.parent / "cache",
    ]
    for directory in search_dirs:
        if not directory.exists():
            continue
        exact_mp4 = directory / f"{video_id}.mp4"
        if exact_mp4.exists():
            return exact_mp4, f"exact_mp4:{directory}"
    for directory in search_dirs:
        if not directory.exists():
            continue
        for extension in SOURCE_EXTENSIONS:
            if extension == ".mp4":
                continue
            candidate = directory / f"{video_id}{extension}"
            if candidate.exists():
                return candidate, f"exact_source:{directory}"
    matches: list[Path] = []
    for directory in search_dirs:
        if not directory.exists():
            continue
        matches.extend(
            path
            for path in directory.glob(f"{video_id}.*")
            if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
        )
    if matches:
        match = sorted(matches, key=_source_sort_key)[0]
        return match, f"matched_source:{match.parent}"
    return None, "not_found"


def _source_sort_key(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if path.suffix.lower() == ".mp4" and ".f" not in name:
        return 0, name
    if ".f" not in name:
        return 1, name
    return 2, name


def _download_missing_source(video_id: str, youtube_url: str) -> tuple[Path | None, str]:
    config.STORAGE_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        return None, f"yt-dlp indisponível: {exc}"

    output_template = str(config.STORAGE_VIDEOS_DIR / f"{video_id}.%(ext)s")
    options = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/best",
        "outtmpl": output_template,
        "ffmpeg_location": _ffmpeg_executable(),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 120,
        "retries": 2,
        "fragment_retries": 2,
    }
    try:
        with YoutubeDL(options) as downloader:
            error_code = downloader.download([youtube_url])
        if error_code:
            return None, f"yt-dlp retornou {error_code}"
    except Exception as exc:
        return None, str(exc)

    source_path, _reason = _find_source_video(video_id)
    if not source_path:
        return None, "arquivo fonte não encontrado após download"

    exact_mp4 = config.STORAGE_VIDEOS_DIR / f"{video_id}.mp4"
    if exact_mp4.exists():
        return exact_mp4, ""
    if source_path.parent == config.STORAGE_VIDEOS_DIR and source_path.suffix.lower() == ".mp4":
        return source_path, ""
    return None, f"download não gerou MP4 utilizável em {exact_mp4}"


def _ffmpeg_command(
    source_path: Path,
    output_path: Path,
    start: float,
    duration: float,
    overwrite: bool,
) -> list[str]:
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


def _write_report(
    plan_path: Path,
    total_items: int,
    selected_items: int,
    results: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"render_report_{timestamp}.json"
    md_path = reports_dir / f"render_report_{timestamp}.md"
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "plan_path": str(plan_path),
        "dry_run": dry_run,
        "total_items": total_items,
        "selected_items": selected_items,
        "rendered_count": sum(1 for item in results if item["status"] == "rendered"),
        "skipped_count": sum(1 for item in results if item["status"] == "skipped"),
        "error_count": sum(1 for item in results if item["status"] == "error"),
        "missing_source_count": sum(1 for item in results if item["status"] == "missing_source"),
        "downloaded_missing_source_count": sum(
            1 for item in results if item["downloaded_missing_source"]
        ),
        "duration_rendered": round(
            sum(float(item.get("duration") or 0.0) for item in results if item["status"] == "rendered"),
            2,
        ),
        "output_files": [
            item["output_path"]
            for item in results
            if item["status"] == "rendered" and item.get("output_path")
        ],
        "errors": [
            {
                "video_id": item["video_id"],
                "rank": item["rank"],
                "status": item["status"],
                "error_message": item["error_message"],
            }
            for item in results
            if item["status"] in {"error", "missing_source"}
        ],
        "items": results,
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))
    return {"json": str(json_path), "md": str(md_path)}


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Render Report",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Plan: {payload['plan_path']}",
        f"Dry run: {str(payload['dry_run']).lower()}",
        f"Total items: {payload['total_items']}",
        f"Selected items: {payload['selected_items']}",
        f"Rendered: {payload['rendered_count']}",
        f"Skipped: {payload['skipped_count']}",
        f"Errors: {payload['error_count']}",
        f"Missing source: {payload['missing_source_count']}",
        f"Downloaded missing source: {payload['downloaded_missing_source_count']}",
        f"Duration rendered: {payload['duration_rendered']}s",
        "",
        "## Items",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"### {item['video_id']} rank {item['rank']} - {item['status']}",
                "",
                f"Title: {item['title']}",
                f"Rating: {item['rating']}",
                f"Reason: {item['reason']}",
                f"Original: {_mmss(item['start'])} até {_mmss(item['end'])}",
                f"Final: {_mmss(item['final_start'])} até {_mmss(item['final_end'])}",
                f"Source found: {str(item['source_found']).lower()}",
                f"Source: {item['source_path']}",
                f"Downloaded missing source: {str(item['downloaded_missing_source']).lower()}",
                f"Source resolution: {item['source_resolution_reason']}",
                f"Download error: {item['download_error']}",
                f"Output: {item['output_path']}",
                f"FFmpeg: `{item['ffmpeg_command']}`",
                f"Error: {item['error_message']}",
                "",
            ]
        )
    return "\n".join(lines)


def _output_filename(
    video_id: str,
    rank: int,
    rating: float,
    reason: str,
    start: float,
    end: float,
) -> str:
    rating_text = str(int(rating)) if float(rating).is_integer() else str(rating).replace(".", "_")
    return (
        f"{_slug(video_id)}__rank_{rank}__rating_{rating_text}__"
        f"{_slug(reason)}__{int(round(start))}_{int(round(end))}.mp4"
    )


def _slug(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or "clip"


def _command_for_display(command: list[str]) -> str:
    return " ".join(_quote_arg(arg) for arg in command)


def _quote_arg(arg: object) -> str:
    text = str(arg)
    if not text or re.search(r"\s", text):
        return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
    return text


def _open_exports_folder() -> None:
    try:
        os.startfile(config.STORAGE_EXPORTS_DIR)  # type: ignore[attr-defined]
    except Exception as exc:
        print(f"Não foi possível abrir a pasta de exports: {exc}")


def _mmss(value: object) -> str:
    total = max(0, int(round(_to_float(value))))
    minutes, seconds = divmod(total, 60)
    return f"{minutes}:{seconds:02d}"


def _to_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


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
