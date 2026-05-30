import json
import sys
from datetime import datetime
from pathlib import Path

from app.config import (
    DEFAULT_BR_FEEDS,
    DEFAULT_GLOBAL_FEEDS,
    DYNAMIC_TOPICS_TO_EXPAND,
    ENABLE_DYNAMIC_QUERY_EXPANSION,
    ENABLE_HIGH_ATTENTION_SCANNER,
    REPORT_TOP_N,
    STORAGE_TRENDS_DIR,
    TOP_TOPICS_TO_PROCESS,
    VIDEOS_PER_TOPIC,
)
from app.models import TrendSignal, TrendTopic
from app.scanners import trend_query_builder, youtube_errors
from app.scanners.google_news_rss_scanner import GoogleNewsRSSScanner
from app.scanners.google_trends_scanner import GoogleTrendsScanner
from app.scanners.rss_news_scanner import RSSNewsScanner
from app.scanners.youtube_high_attention_scanner import YouTubeHighAttentionScanner
from app.scanners.youtube_popular_scanner import YouTubePopularScanner
from app.services import OpportunityReportService, SourceFinderService, TrendAggregatorService
from app.services.dynamic_query_expansion_service import DynamicQueryExpansionService
from app.services.noise_filter_service import NoiseFilterService
from app.services.video_history_service import VideoHistoryService
from app.scanners.trend_query_builder import _br_relevance_score


def main() -> None:
    configure_output()
    youtube_errors.reset_quota_state()
    trend_query_builder.reset_query_debug()
    print_banner()

    signals = collect_signals()
    print_dynamic_sources_block()
    print(f"[clipradar] Collected {len(signals)} trend signals")

    aggregator = TrendAggregatorService()
    topics = aggregator.aggregate(signals)
    topics = sorted(topics, key=lambda topic: topic.trend_score, reverse=True)
    topics = expand_dynamic_queries(topics)

    source_finder = SourceFinderService()
    topics = source_finder.attach_videos(
        topics[:TOP_TOPICS_TO_PROCESS],
        limit=TOP_TOPICS_TO_PROCESS,
        videos_per_topic=VIDEOS_PER_TOPIC,
    )
    topics = sorted(topics, key=lambda topic: topic.opportunity_score, reverse=True)
    clean_topics = clean_top_topics(topics)

    output_path = save_results(clean_topics)
    print(f"[clipradar] Saved results to {output_path}")

    report_service = OpportunityReportService()
    markdown_report_path, json_report_path = report_service.generate(
        clean_topics,
        top_n=REPORT_TOP_N,
    )
    print(f"[clipradar] Saved opportunity report Markdown to {markdown_report_path}")
    print(f"[clipradar] Saved opportunity report JSON to {json_report_path}")

    queued_count = VideoHistoryService().enqueue_from_topics(clean_topics)
    print(f"[clipradar] Queued {queued_count} videos for transcription pipeline")

    print_ranking(clean_topics[:TOP_TOPICS_TO_PROCESS])
    if len(clean_topics) < 10:
        print("")
        print(
            f"ℹ️  Apenas {len(clean_topics)} tópicos com qualidade suficiente nesta execução."
        )
        print(
            "Causa provável: YouTube API quota esgotada ou fontes dinâmicas indisponíveis."
        )


def collect_signals() -> list[TrendSignal]:
    scanners = [
        GoogleTrendsScanner(market="BR", language="pt-BR", limit=20),
        GoogleTrendsScanner(market="GLOBAL", language="en", limit=20),
        RSSNewsScanner(
            feeds=DEFAULT_BR_FEEDS,
            market="BR",
            language="pt-BR",
            max_items_per_feed=20,
        ),
        RSSNewsScanner(
            feeds=DEFAULT_GLOBAL_FEEDS,
            market="GLOBAL",
            language="en",
            max_items_per_feed=20,
        ),
        GoogleNewsRSSScanner(market="BR", language="pt-BR", max_items_per_query=8),
        GoogleNewsRSSScanner(market="GLOBAL", language="en", max_items_per_query=8),
    ]
    if ENABLE_HIGH_ATTENTION_SCANNER:
        scanners.extend(
            [
                YouTubeHighAttentionScanner(market="BR", language="pt-BR"),
                YouTubeHighAttentionScanner(market="GLOBAL", language="en"),
            ]
        )
    scanners.extend(
        [
            YouTubePopularScanner(market="BR", language="pt-BR", max_results=25),
            YouTubePopularScanner(market="GLOBAL", language="en", max_results=25),
        ]
    )

    signals: list[TrendSignal] = []
    for scanner in scanners:
        try:
            signals.extend(scanner.scan())
        except Exception as exc:
            print(f"[clipradar] Scanner failed: {scanner.__class__.__name__}: {exc}")
    return signals


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


def print_banner() -> None:
    print("╔══════════════════════════════════════╗")
    print("║   CLIPRADAR 0.4.5 — Dynamic Radar   ║")
    print("╚══════════════════════════════════════╝")


def save_results(topics: list[TrendTopic]) -> Path:
    STORAGE_TRENDS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = STORAGE_TRENDS_DIR / f"results_{timestamp}.json"

    payload = {
        "generated_at": datetime.now().isoformat(),
        "topics_count": len(topics),
        "topics": [model_to_jsonable(topic) for topic in topics],
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    return output_path


def model_to_jsonable(model: TrendTopic) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def print_ranking(topics: list[TrendTopic]) -> None:
    print("")
    print(f"ClipRadar MVP Scanner 0.4.5 - Top {len(topics)} Opportunities")
    print("-" * 178)
    print(
        f"{'#':<3} {'topic':<28} {'market':<7} {'base':<5} {'exp':<5} "
        f"{'dyn':<5} {'attn':<6} {'rights':<6} {'risk':<6} {'validation':<13} decisão"
    )
    print("-" * 178)

    for index, topic in enumerate(topics, start=1):
        keyword = _display_text(topic.keyword, 27)
        validation = "needs_yt" if topic.needs_youtube_validation else "ok"
        if topic.youtube_quota_limited:
            validation = "quota_limited"
        expansion = "yes" if topic.expansion_allowed else "no"
        print(
            f"{index:<3} {keyword:<28} {topic.market:<7} "
            f"{topic.topic_base_quality_score:<5.1f} {expansion:<5} "
            f"{topic.dynamic_query_quality_score:<5.1f} {topic.attention_score:<6.2f} "
            f"{topic.clip_permission_score:<6.2f} {topic.risk_score:<6.2f} "
            f"{validation:<13} {topic.decision}"
        )


def print_dynamic_sources_block() -> None:
    print("")
    print("Fontes dinâmicas:")
    statuses = trend_query_builder.get_source_status()
    if statuses:
        for status in statuses:
            mark = "✓" if status.get("ok") else "✗"
            print(f"{mark} {status.get('name')} — {status.get('detail')}")
    else:
        print("✗ TrendQueryBuilder — nenhum status registrado")

    for message, success in youtube_errors.get_rotation_events():
        mark = "✓" if success else "✗"
        print(f"{mark} YouTube API — {message}")
    if youtube_errors.QUOTA_EXHAUSTED:
        print("✗ YouTube API — quota_exhausted")
    else:
        print("✓ YouTube API — ok")
    print(f"Degraded mode: {str(youtube_errors.QUOTA_EXHAUSTED).lower()}")

    print("")
    print("Queries desta execução:")
    events = trend_query_builder.get_query_events()
    if not events:
        print("(nenhuma query dinâmica registrada)")
        return
    for event in events:
        print(f"[{event['source']}] {event['query']}")


def clean_top_topics(topics: list[TrendTopic]) -> list[TrendTopic]:
    noise_filter = NoiseFilterService()
    clean: list[TrendTopic] = []
    for topic in topics:
        if topic.attention_category == "noise":
            continue
        if topic.attention_score < 1.5:
            continue
        if len(topic.normalized_keyword.split()) <= 1:
            continue
        if topic.topic_base_quality_score < 3.5 and not topic.videos:
            continue
        if (
            topic.market == "BR"
            and "trends_rss" in topic.real_sources
            and "watchlist" not in topic.real_sources
            and _br_relevance_score(topic.keyword) < 0.25
        ):
            continue
        if noise_filter.is_noisy(topic):
            continue
        clean.append(topic)
    return clean


def expand_dynamic_queries(topics: list[TrendTopic]) -> list[TrendTopic]:
    if not ENABLE_DYNAMIC_QUERY_EXPANSION:
        return topics

    expansion_service = DynamicQueryExpansionService()
    expanded: list[TrendTopic] = []
    for index, topic in enumerate(topics):
        if index < DYNAMIC_TOPICS_TO_EXPAND:
            expanded.append(expansion_service.expand_topic(topic))
        else:
            expanded.append(topic)
    return expanded


def _display_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0]
    return trimmed or text[:limit]


if __name__ == "__main__":
    main()
