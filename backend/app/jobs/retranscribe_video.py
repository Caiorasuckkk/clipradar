from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.clip_analyzer_service import ClipAnalyzerService
from app.services.downloader_service import DownloaderService
from app.services.transcription_service import TranscriptionService
from app.services.video_history_service import VideoHistoryService


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--language", required=True)
    args = parser.parse_args()

    history = VideoHistoryService()
    video = history._read().get(args.video_id)
    if not video:
        print(f"Vídeo não encontrado no histórico: {args.video_id}")
        return

    transcript_path = config.STORAGE_TRANSCRIPTS_DIR / f"{args.video_id}.json"
    if transcript_path.exists():
        backup_path = transcript_path.with_suffix(".json.bak")
        shutil.copy2(transcript_path, backup_path)
        print(f"Backup transcript: {backup_path}")

    downloader = DownloaderService()
    transcriber = TranscriptionService(model_size=config.WHISPER_MODEL_SIZE)
    analyzer = ClipAnalyzerService()

    audio_path = downloader.download(args.video_id, video["url"])
    if not audio_path:
        print(f"RETRANSCRIBE falhou: download falhou para {args.video_id}")
        return

    transcript = transcriber.transcribe(audio_path, metadata=video, language=args.language)
    if not transcript:
        downloader.cleanup(args.video_id)
        print(f"RETRANSCRIBE falhou: transcrição falhou para {args.video_id}")
        return

    saved_transcript = transcriber.save_transcript(args.video_id, transcript)
    downloader.cleanup(args.video_id)

    analysis = analyzer.analyze_with_diagnostics(transcript, video)
    clips_path = save_clips(video, analysis, transcript)

    print("RETRANSCRIBE concluído")
    print(f"video_id: {args.video_id}")
    print(f"requested_language: {transcript.get('requested_language')}")
    print(f"detected_language: {transcript.get('detected_language')}")
    print(f"language_conflict: {transcript.get('language_conflict')}")
    print(f"Transcript: {saved_transcript}")
    print(f"Clips: {clips_path}")
    print(f"Clipes recomendados: {len(analysis['clips'])}")
    print(f"Diagnostic candidates: {len(analysis['diagnostic_candidates'])}")


def save_clips(video: dict[str, Any], analysis: dict[str, Any], transcript: dict[str, Any]) -> Path:
    config.STORAGE_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    video_id = video["video_id"]
    output_path = config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json"
    result = {
        "video_id": video_id,
        "video_title": video.get("title", ""),
        "channel_name": video.get("channel_name") or video.get("channel_title", ""),
        "url": video.get("url", ""),
        "processed_at": datetime.utcnow().isoformat(),
        "analysis_note": analysis["analysis_summary"].get("reason", ""),
        "analysis_summary": analysis["analysis_summary"],
        "transcript_metadata": _transcript_metadata(transcript),
        "clips": analysis["clips"],
        "diagnostic_candidates": analysis["diagnostic_candidates"],
    }
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    return output_path


def _transcript_metadata(transcript: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "requested_language",
        "detected_language",
        "language_mode",
        "language_source",
        "language_conflict",
    ]
    return {key: transcript.get(key) for key in keys if key in transcript}


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
