from __future__ import annotations

import argparse
import sys
from typing import Any

from app import config
from app.services.video_history_service import VideoHistoryService


NEGATIVE_REVIEW_TERMS = {
    "unimed", "rádio jota", "radio jota", "rádio carbo", "radio carbo",
    "arapuan verdade", "entrevista dr.", "entrevista doutor", "prefeitura",
    "câmara municipal", "camara municipal", "institucional", "gameplay",
    "walkthrough", "call of duty", "modern warfare", "unreal engine", "mw2",
    "mw4", "ign", "game", "react:", "react", "reação", "reacao", "reacts",
    "trailer", "official video", "music video", "lyrics", "clipe oficial",
    "videoclipe", "música", "musica", "fan clip", "fan edit",
    "compilado", "compilação", "compilacao", "melhores momentos",
    "highlights",
}


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-all", action="store_true")
    parser.add_argument("--show-processed", action="store_true")
    parser.add_argument("--show-rejected-sources", action="store_true")
    args = parser.parse_args()

    history = VideoHistoryService()
    history.refresh_processing_priorities()
    data = history._read()
    visible: list[dict[str, Any]] = []
    hidden_counts = {
        "processed": 0,
        "source_quality": 0,
        "editorial_zero": 0,
        "negative_filters": 0,
    }
    hidden_examples: list[tuple[str, dict[str, Any]]] = []
    for item in data.values():
        reason = _hidden_reason(item, args)
        if reason and not args.show_all:
            hidden_counts[reason] = hidden_counts.get(reason, 0) + 1
            if len(hidden_examples) < 12:
                hidden_examples.append((reason, item))
            continue
        visible.append(item)

    videos = sorted(
        visible,
        key=lambda item: (
            float(item.get("combined_discovery_score") or 0.0),
            float(item.get("editorial_fit_score") or 0.0),
            float(item.get("processing_priority_score") or 0.0),
        ),
        reverse=True,
    )

    print("REVIEW SELECTED VIDEOS")
    print(f"Total no histórico: {len(data)}")
    print(f"Candidatos processáveis: {len(videos)}")
    print(f"Ocultados por já processados: {hidden_counts.get('processed', 0)}")
    print(f"Ocultados por source_quality ruim: {hidden_counts.get('source_quality', 0)}")
    print(f"Ocultados por editorial 0: {hidden_counts.get('editorial_zero', 0)}")
    print(f"Ocultados por filtros negativos: {hidden_counts.get('negative_filters', 0)}")
    print("")
    for index, video in enumerate(videos[:30], start=1):
        print(
            f"{index:>2}. {float(video.get('processing_priority_score') or 0):>4.1f} | "
            f"editorial {float(video.get('editorial_fit_score') or 0):>4.1f} | "
            f"combined {float(video.get('combined_discovery_score') or 0):>4.1f} | "
            f"{video.get('status', ''):<15} | "
            f"source {str(video.get('source_quality_tier') or '-'):<16} | "
            f"{int(video.get('duration_seconds') or 0):>5}s | "
            f"{_display(video.get('channel_name') or video.get('channel_title') or '', 22):<22} | "
            f"{_display(video.get('title', ''), 58)}"
        )
        print(f"    video_id: {video.get('video_id', '')} | url: {video.get('url', '')}")
        if video.get("topic_bucket"):
            print(f"    bucket: {video.get('topic_bucket')}")
        if video.get("editorial_fit_reasons"):
            print(f"    editorial: {_display(', '.join(video.get('editorial_fit_reasons', [])), 140)}")
        print(f"    priority: {_display(video.get('processing_priority_reason', ''), 120)}")
        if video.get("queue_reject_reason"):
            print(f"    queue_reject: {_display(video.get('queue_reject_reason', ''), 120)}")
    if hidden_examples:
        print("")
        print("Exemplos ocultados:")
        for reason, video in hidden_examples:
            print(
                f"- {reason}: {video.get('video_id', '')} | "
                f"{video.get('status', '')} | "
                f"{_display(video.get('title', ''), 90)}"
            )


def _hidden_reason(item: dict[str, Any], args: argparse.Namespace) -> str:
    status = str(item.get("status") or "")
    video_id = str(item.get("video_id") or "")
    if not args.show_rejected_sources and (
        status in {"source_rejected", "weak_source_reviewed", "bad_source"}
        or item.get("source_quality_tier") == "bad_source"
        or item.get("should_continue_video_review") is False
    ):
        return "source_quality"
    if not args.show_processed and (
        status in {"done", "processed"}
        or (config.STORAGE_TRANSCRIPTS_DIR / f"{video_id}.json").exists()
        or (config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json").exists()
    ):
        return "processed"
    if float(item.get("editorial_fit_score") or 0.0) <= 0 or float(item.get("combined_discovery_score") or 0.0) <= 0:
        return "editorial_zero"
    text = f"{item.get('title', '')} {item.get('channel_name', '')} {item.get('channel_title', '')}".lower()
    if any(term in text for term in NEGATIVE_REVIEW_TERMS):
        return "negative_filters"
    return ""


def _display(value: object, limit: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0]
    return trimmed or text[:limit]


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
