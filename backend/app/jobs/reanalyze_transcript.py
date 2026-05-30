from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from app import config
from app.services.clip_analyzer_service import ClipAnalyzerService
from app.services.transcription_service import TranscriptionService
from app.services.video_history_service import VideoHistoryService


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", required=True)
    args = parser.parse_args()

    video_id = args.video_id
    transcriber = TranscriptionService(model_size=config.WHISPER_MODEL_SIZE)
    transcript = transcriber.load_transcript(video_id)
    if not transcript:
        print(f"REANALYZE falhou: transcript não encontrado para {video_id}")
        return

    history = VideoHistoryService()
    video = history._read().get(video_id, {"video_id": video_id})
    analyzer = ClipAnalyzerService()
    analysis = analyzer.analyze_with_diagnostics(transcript, video)
    clips = analysis["clips"]
    diagnostic_candidates = analysis["diagnostic_candidates"]
    analysis_summary = analysis["analysis_summary"]

    output_path = save_clips(video_id, video, clips, diagnostic_candidates, analysis_summary)
    print(f"REANALYZE concluído: {video_id}")
    print(f"Clipes recomendados: {len(clips)}")
    print(f"Diagnostic candidates: {len(diagnostic_candidates)}")
    if analysis_summary.get("reason"):
        print(f"Motivo principal: {analysis_summary['reason']}")
    print(f"Output: {output_path}")
    print("")
    print("Novos timestamps:")
    if len(clips) < 5:
        print(
            "menos clipes retornados porque os demais não atingiram qualidade "
            "narrativa mínima"
        )
    for clip in clips:
        print(
            f"#{clip['rank']} {clip['start_seconds']:.2f}-{clip['end_seconds']:.2f}s "
            f"score={clip['score']:.2f} hook={clip['hook_score']:.2f} "
            f"dev={clip['development_score']:.2f} end={clip['ending_quality_score']:.2f} "
            f"incomplete={clip['incomplete_ending']} merged={clip['merged_from']} "
            f"reason={clip['boundary_adjustment_reason']}"
        )
    if diagnostic_candidates:
        print("")
        print("Diagnostic candidates:")
        for candidate in diagnostic_candidates[:8]:
            print(
                f"#{candidate['rank']} {candidate['start_seconds']:.2f}-{candidate['end_seconds']:.2f}s "
                f"score={candidate['score']:.2f} narrative={candidate['narrative_quality_score']:.2f} "
                f"standalone={candidate['standalone_score']:.2f} "
                f"risk={candidate['false_full_thought_risk']:.2f} "
                f"reason={candidate['not_recommended_reason']}"
            )


def save_clips(
    video_id: str,
    video: dict[str, Any],
    clips: list[dict[str, Any]],
    diagnostic_candidates: list[dict[str, Any]],
    analysis_summary: dict[str, Any],
):
    config.STORAGE_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json"
    payload = {
        "video_id": video_id,
        "video_title": video.get("title", ""),
        "channel_name": video.get("channel_name") or video.get("channel_title", ""),
        "url": video.get("url", ""),
        "processed_at": datetime.utcnow().isoformat(),
        "analysis_note": analysis_summary.get("reason", ""),
        "analysis_summary": analysis_summary,
        "clips": clips,
        "diagnostic_candidates": diagnostic_candidates,
    }
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return output_path


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
