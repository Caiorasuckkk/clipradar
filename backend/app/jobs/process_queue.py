from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.clip_analyzer_service import ClipAnalyzerService
from app.services.downloader_service import DownloaderService
from app.services.metadata_service import MetadataService
from app.services.transcription_service import TranscriptionService
from app.services.video_history_service import VideoHistoryService


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id")
    parser.add_argument("--video-ids")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    history = VideoHistoryService()
    downloader = DownloaderService()
    transcriber = TranscriptionService(model_size=config.WHISPER_MODEL_SIZE)
    analyzer = ClipAnalyzerService()
    metadata_svc = MetadataService()

    manual_ids = _parse_manual_ids(args.video_id, args.video_ids)
    if manual_ids:
        queued = _manual_videos(history, manual_ids, force=args.force)
        print_manual_selection(queued)
        if args.dry_run:
            print("DRY RUN: nenhum download, Whisper ou análise executados.")
            return
    else:
        queued = history.get_next_for_processing(config.MAX_VIDEOS_PER_RUN)
        print(f"Fila: {len(queued)} vídeos para processar")
        print_processing_candidates(queued)

    processed = 0
    total_clips = 0
    errors = 0
    rejected = 0

    videos_to_process = queued if manual_ids else queued[: config.MAX_VIDEOS_PER_RUN]
    for video in videos_to_process:
        video_id = video["video_id"]
        title = video.get("title", "")
        print(f"Processando [{video_id}]: {title}")
        history.mark_processing(video_id)

        try:
            transcript = transcriber.load_transcript(video_id)
            if not transcript:
                audio_path = downloader.download(video_id, video["url"])
                if not audio_path:
                    history.mark_error(video_id, "download falhou")
                    errors += 1
                    continue

                transcript = transcriber.transcribe(audio_path, metadata=video)
                if not transcript:
                    history.mark_error(video_id, "transcrição falhou")
                    downloader.cleanup(video_id)
                    errors += 1
                    continue

                transcriber.save_transcript(video_id, transcript)
                downloader.cleanup(video_id)

            clips = analyzer.analyze(transcript, video)
            if not clips:
                history.mark_rejected(video_id)
                rejected += 1
                print(f"Nenhum clipe encontrado: {video_id}")
                continue

            for clip in clips:
                meta = metadata_svc.generate(
                    clip_text=clip["text"],
                    video_title=video.get("title", ""),
                    channel_name=video.get("channel_name") or video.get("channel_title", ""),
                )
                clip.update(meta)

            output_path = save_clips(video, clips, transcript)
            history.mark_done(video_id)
            processed += 1
            total_clips += len(clips)
            print(f"✓ {len(clips)} clipes gerados: {video_id} — {output_path}")
        except Exception as exc:
            history.mark_error(video_id, str(exc))
            errors += 1
            print(f"PROCESS falhou: {video_id} — {exc}")

    elapsed = time.perf_counter() - started
    print_summary(processed, total_clips, errors, rejected, elapsed)


def save_clips(video: dict[str, Any], clips: list[dict[str, Any]], transcript: dict[str, Any] | None = None) -> Path:
    config.STORAGE_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    video_id = video["video_id"]
    output_path = config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json"
    result = {
        "video_id": video_id,
        "video_title": video.get("title", ""),
        "channel_name": video.get("channel_name") or video.get("channel_title", ""),
        "url": video.get("url", ""),
        "processed_at": datetime.utcnow().isoformat(),
        "transcript_metadata": _transcript_metadata(transcript or {}),
        "clips": clips,
    }
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    return output_path


def _parse_manual_ids(video_id: str | None, video_ids: str | None) -> list[str]:
    ids: list[str] = []
    if video_id:
        ids.append(video_id.strip())
    if video_ids:
        ids.extend(item.strip() for item in video_ids.split(",") if item.strip())
    return list(dict.fromkeys(ids))


def _manual_videos(history: VideoHistoryService, video_ids: list[str], force: bool) -> list[dict[str, Any]]:
    data = history._read()
    selected: list[dict[str, Any]] = []
    for video_id in video_ids:
        item = data.get(video_id)
        if not item:
            print(f"[manual] vídeo não encontrado no histórico: {video_id}")
            continue
        if item.get("status") == "done" and not force:
            print(f"[manual] pulando done sem --force: {video_id} | {item.get('title', '')}")
            continue
        selected.append(item)
    return selected


def print_manual_selection(videos: list[dict[str, Any]]) -> None:
    print("")
    print("MANUAL VIDEO IDS SELECTED:")
    if not videos:
        print("(nenhum vídeo manual elegível)")
        return
    for index, video in enumerate(videos, start=1):
        print(
            f"{index}. {video.get('video_id')} | {video.get('status')} | "
            f"{_display(video.get('title', ''), 90)}"
        )


def _transcript_metadata(transcript: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "requested_language",
        "detected_language",
        "language_mode",
        "language_source",
        "language_conflict",
    ]
    return {key: transcript.get(key) for key in keys if key in transcript}

def print_processing_candidates(videos: list[dict[str, Any]]) -> None:
    print("")
    print("TOP PROCESSING CANDIDATES:")
    if not videos:
        print("(nenhum vídeo queued elegível)")
        return
    for index, video in enumerate(videos[:10], start=1):
        score = float(video.get("processing_priority_score") or 0.0)
        duration = int(video.get("duration_seconds") or 0)
        channel = _display(video.get("channel_name") or video.get("channel_title") or "", 24)
        title = _display(video.get("title", ""), 54)
        reason = _display(video.get("processing_priority_reason", ""), 90)
        print(f"{index}. {score:>4.1f} | {duration:>5}s | {channel:<24} | {title} | {reason}")


def _display(value: object, limit: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0]
    return trimmed or text[:limit]


def print_summary(
    processed: int,
    total_clips: int,
    errors: int,
    rejected: int,
    elapsed: float,
) -> None:
    print(
        f"""
╔══════════════════════════════════════╗
║   PROCESS QUEUE — RESULTADO          ║
╠══════════════════════════════════════╣
║  Processados:    {processed:<4}              ║
║  Clipes gerados: {total_clips:<4}              ║
║  Erros:          {errors:<4}              ║
║  Rejeitados:     {rejected:<4}              ║
║  Tempo total:    {elapsed:<6.1f}s          ║
╚══════════════════════════════════════╝
"""
    )


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
