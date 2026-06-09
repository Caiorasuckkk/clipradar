from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.cache_manifest_service import (
    get_cache_status,
    has_valid_clips,
    has_valid_download,
    has_valid_transcript,
    record_cache_run_metrics,
    touch_video_cache,
    update_video_cache,
)
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
    parser.add_argument("--cache-check-only", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    history = VideoHistoryService()
    downloader: DownloaderService | None = None
    transcriber: TranscriptionService | None = None
    analyzer: ClipAnalyzerService | None = None
    metadata_svc: MetadataService | None = None

    manual_ids = _parse_manual_ids(args.video_id, args.video_ids)
    if manual_ids:
        queued = _manual_videos(
            history,
            manual_ids,
            force=args.force,
            cache_check_only=args.cache_check_only,
        )
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
    cache_hits = 0
    cache_misses = 0
    cache_partials = 0
    cache_bypassed = 0
    videos_reused = 0
    videos_processed_from_scratch = 0

    videos_to_process = queued if manual_ids else queued[: config.MAX_VIDEOS_PER_RUN]
    total_videos = len(videos_to_process)
    for index, video in enumerate(videos_to_process, start=1):
        video_id = video["video_id"]
        title = video.get("title", "")
        video_started = time.perf_counter()
        print(
            f"[step3_video_start] video_id={video_id} index={index}/{total_videos} "
            f"title={_display(title, 120)}",
            flush=True,
        )
        print(f"Processando [{video_id}]: {title}")
        cached_output = config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json"
        cache_entry = get_cache_status(video_id)
        missing_cache_parts = _missing_cache_parts(cache_entry)
        done_skip_reason = str(video.get("_cache_skip_reason") or "")
        reusable_cache = bool(
            cache_entry.get("transcript_exists")
            or cache_entry.get("clips_exists")
            or int(cache_entry.get("previews_ready_count") or 0) > 0
        )
        reused_this_video = False
        print(f"[cache_check] video_id={video_id}", flush=True)
        if args.force:
            cache_bypassed += 1
            print(f"[cache_bypass] overwrite=true video_id={video_id}", flush=True)
        elif done_skip_reason and reusable_cache:
            cache_hits += 1
            videos_reused += 1
            reused_this_video = True
            touch_video_cache(video_id)
            print(
                f"[cache_hit] done video_id={video_id} reason={done_skip_reason}",
                flush=True,
            )
            if cache_entry.get("transcript_exists"):
                print(f"[cache_hit] transcript video_id={video_id}", flush=True)
            if cache_entry.get("clips_exists"):
                print(f"[cache_hit] clips video_id={video_id}", flush=True)
            if int(cache_entry.get("previews_ready_count") or 0) > 0:
                print(f"[cache_hit] previews video_id={video_id}", flush=True)
            print(
                f"[step3_video_end] video_id={video_id} status=CACHED_DONE "
                f"elapsed_seconds={round(time.perf_counter() - video_started, 2)}",
                flush=True,
            )
            continue
        elif not missing_cache_parts:
            cache_hits += 1
            videos_reused += 1
            reused_this_video = True
            print(
                f"[cache_hit] transcript=true clips=true previews=true video_id={video_id}",
                flush=True,
            )
        elif len(missing_cache_parts) < 3:
            cache_partials += 1
            print(
                f"[cache_partial] video_id={video_id} missing={','.join(missing_cache_parts)}",
                flush=True,
            )
        else:
            cache_misses += 1
            print(
                f"[cache_miss] video_id={video_id} missing={','.join(missing_cache_parts)}",
                flush=True,
            )
        if args.cache_check_only:
            print(
                f"[step3_video_end] video_id={video_id} status=CACHE_CHECK_ONLY "
                f"elapsed_seconds={round(time.perf_counter() - video_started, 2)}",
                flush=True,
            )
            continue
        if has_valid_clips(video_id) and not args.force:
            history.mark_done(video_id)
            processed += 1
            if not reused_this_video:
                videos_reused += 1
                reused_this_video = True
            touch_video_cache(video_id)
            print(
                f"[cache_hit] clips video_id={video_id} clips_path={cached_output}",
                flush=True,
            )
            if has_valid_transcript(video_id):
                print(f"[cache_hit] transcript video_id={video_id}", flush=True)
            if has_valid_download(video_id):
                print(f"[cache_hit] download video_id={video_id}", flush=True)
            print(
                f"[step3_video_end] video_id={video_id} status=CACHED "
                f"elapsed_seconds={round(time.perf_counter() - video_started, 2)}",
                flush=True,
            )
            continue
        history.mark_processing(video_id)
        videos_processed_from_scratch += 1

        try:
            print(f"[step3_process_start] video_id={video_id}", flush=True)
            if transcriber is None:
                transcriber = TranscriptionService(model_size=config.WHISPER_MODEL_SIZE)
            transcript = transcriber.load_transcript(video_id)
            if not transcript:
                download_started = time.perf_counter()
                if has_valid_download(video_id) and not args.force:
                    print(f"[cache_hit] download video_id={video_id}", flush=True)
                print(f"[step3_download_start] video_id={video_id}", flush=True)
                if downloader is None:
                    downloader = DownloaderService()
                audio_path = downloader.download(video_id, video["url"])
                print(
                    f"[step3_download_end] video_id={video_id} "
                    f"elapsed_seconds={round(time.perf_counter() - download_started, 2)} "
                    f"success={bool(audio_path)}",
                    flush=True,
                )
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
            else:
                print(f"[cache_hit] transcript video_id={video_id}", flush=True)
                print(f"[step3_transcript_cache_hit] video_id={video_id}", flush=True)

            if analyzer is None:
                analyzer = ClipAnalyzerService()
            analysis = analyzer.analyze_with_diagnostics(transcript, video)
            clips = analysis["clips"]
            diagnostic_candidates = analysis["diagnostic_candidates"]
            history.update_source_quality(video_id, analysis["analysis_summary"])
            source_tier = analysis["analysis_summary"].get("source_quality_tier", "")
            if source_tier in {"bad_source", "weak_source"}:
                print(
                    "Vídeo com baixa qualidade de fonte para clipping: "
                    f"{source_tier} / {analysis['analysis_summary'].get('source_quality_score')} / "
                    f"{analysis['analysis_summary'].get('source_quality_reason')}"
                )
            if not clips and not diagnostic_candidates:
                output_path = save_clips(video, analysis, transcript)
                update_video_cache(
                    video_id,
                    video_title=title,
                    youtube_url=str(video.get("url") or ""),
                    last_processed=True,
                )
                if analysis["analysis_summary"].get("should_continue_video_review") is False:
                    history.mark_source_rejected(video_id)
                else:
                    history.mark_rejected(video_id)
                rejected += 1
                print(f"Nenhum clipe ou diagnostic encontrado: {video_id} — {output_path}")
                continue
            if not clips and diagnostic_candidates:
                output_path = save_clips(video, analysis, transcript)
                update_video_cache(
                    video_id,
                    video_title=title,
                    youtube_url=str(video.get("url") or ""),
                    last_processed=True,
                )
                if analysis["analysis_summary"].get("should_continue_video_review") is False:
                    history.mark_weak_source_reviewed(video_id)
                else:
                    history.mark_needs_manual_review(video_id)
                processed += 1
                print(
                    f"Nenhum recomendado, mas {len(diagnostic_candidates)} diagnostics "
                    f"salvos para revisão manual: {video_id} — {output_path}"
                )
                continue

            for clip in clips:
                if metadata_svc is None:
                    metadata_svc = MetadataService()
                meta = metadata_svc.generate(
                    clip_text=clip["text"],
                    video_title=video.get("title", ""),
                    channel_name=video.get("channel_name") or video.get("channel_title", ""),
                )
                clip.update(meta)

            output_path = save_clips(video, analysis, transcript)
            update_video_cache(
                video_id,
                video_title=title,
                youtube_url=str(video.get("url") or ""),
                last_processed=True,
            )
            history.mark_done(video_id)
            processed += 1
            total_clips += len(clips)
            print(f"✓ {len(clips)} clipes gerados: {video_id} — {output_path}")
            print(
                f"[step3_process_end] video_id={video_id} "
                f"elapsed_seconds={round(time.perf_counter() - video_started, 2)}",
                flush=True,
            )
        except Exception as exc:
            history.mark_error(video_id, str(exc))
            errors += 1
            print(f"PROCESS falhou: {video_id} — {exc}")
        finally:
            print(
                f"[step3_video_end] video_id={video_id} "
                f"elapsed_seconds={round(time.perf_counter() - video_started, 2)}",
                flush=True,
            )

    elapsed = time.perf_counter() - started
    cache_summary = {
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_partials": cache_partials,
        "cache_bypassed": cache_bypassed,
        "videos_reused": videos_reused,
        "videos_processed_from_scratch": videos_processed_from_scratch,
        "estimated_seconds_saved": videos_reused * 240 if videos_reused else 0,
    }
    record_cache_run_metrics(cache_summary)
    print(
        f"[cache_summary] cache_hits={cache_summary['cache_hits']} "
        f"cache_misses={cache_summary['cache_misses']} "
        f"cache_partials={cache_summary['cache_partials']} "
        f"cache_bypassed={cache_summary['cache_bypassed']} "
        f"videos_reused={cache_summary['videos_reused']} "
        f"videos_processed_from_scratch={cache_summary['videos_processed_from_scratch']} "
        f"estimated_seconds_saved={cache_summary['estimated_seconds_saved']}",
        flush=True,
    )
    print_summary(processed, total_clips, errors, rejected, elapsed)


def save_clips(video: dict[str, Any], analysis: dict[str, Any], transcript: dict[str, Any] | None = None) -> Path:
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
        "analysis_note": analysis["analysis_summary"].get("reason", ""),
        "analysis_summary": analysis["analysis_summary"],
        "source_quality_score": analysis["analysis_summary"].get("source_quality_score"),
        "source_quality_tier": analysis["analysis_summary"].get("source_quality_tier"),
        "source_quality_reason": analysis["analysis_summary"].get("source_quality_reason", ""),
        "source_quality_warning": analysis["analysis_summary"].get("source_quality_warning", ""),
        "should_continue_video_review": analysis["analysis_summary"].get("should_continue_video_review", True),
        "clips": analysis["clips"],
        "diagnostic_candidates": analysis["diagnostic_candidates"],
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


def _manual_videos(
    history: VideoHistoryService,
    video_ids: list[str],
    force: bool,
    cache_check_only: bool = False,
) -> list[dict[str, Any]]:
    data = history._read()
    selected: list[dict[str, Any]] = []
    for video_id in video_ids:
        item = data.get(video_id)
        if not item:
            print(f"[manual] vídeo não encontrado no histórico: {video_id}")
            continue
        if item.get("status") == "done" and not force:
            cache_entry = get_cache_status(video_id)
            if (
                cache_check_only
                or cache_entry.get("transcript_exists")
                or cache_entry.get("clips_exists")
                or int(cache_entry.get("previews_ready_count") or 0) > 0
            ):
                cached_item = dict(item)
                cached_item["_cache_skip_reason"] = "already_done_without_force"
                selected.append(cached_item)
                continue
            print(f"[manual] pulando done sem cache válido: {video_id} | {item.get('title', '')}")
            continue
        selected.append(dict(item))
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


def _missing_cache_parts(cache_entry: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not cache_entry.get("downloaded_video_path") and not cache_entry.get("downloaded_audio_path"):
        missing.append("download")
    if not cache_entry.get("transcript_exists"):
        missing.append("transcript")
    if not cache_entry.get("clips_exists"):
        missing.append("clips")
    if int(cache_entry.get("previews_ready_count") or 0) <= 0:
        missing.append("previews")
    return missing

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
