import json
import sys
from datetime import datetime
from pathlib import Path

from app.config import DEFAULT_BR_FEEDS, DEFAULT_GLOBAL_FEEDS, STORAGE_TRENDS_DIR
from app.models import TrendSignal, TrendTopic
from app.scanners.google_news_rss_scanner import GoogleNewsRSSScanner
from app.scanners.google_trends_scanner import GoogleTrendsScanner
from app.scanners.rss_news_scanner import RSSNewsScanner
from app.scanners.youtube_popular_scanner import YouTubePopularScanner
from app.services import OpportunityReportService, SourceFinderService, TrendAggregatorService


def main() -> None:
    configure_output()
    print("[clipradar] Starting MVP Scanner 0.3")

    signals = collect_signals()
    print(f"[clipradar] Collected {len(signals)} trend signals")

    aggregator = TrendAggregatorService()
    topics = aggregator.aggregate(signals)
    topics = sorted(topics, key=lambda topic: topic.trend_score, reverse=True)

    source_finder = SourceFinderService()
    topics = source_finder.attach_videos(topics[:30], limit=10)
    topics = sorted(topics, key=lambda topic: topic.opportunity_score, reverse=True)

    output_path = save_results(topics)
    print(f"[clipradar] Saved results to {output_path}")

    report_service = OpportunityReportService()
    markdown_report_path, json_report_path = report_service.generate(topics, limit=10)
    print(f"[clipradar] Saved opportunity report Markdown to {markdown_report_path}")
    print(f"[clipradar] Saved opportunity report JSON to {json_report_path}")

    print_ranking(topics[:10])


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
        YouTubePopularScanner(market="BR", language="pt-BR", max_results=25),
        YouTubePopularScanner(market="GLOBAL", language="en", max_results=25),
    ]

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
    print("ClipRadar MVP Scanner 0.3 - Top 10 Opportunities")
    print("-" * 126)
    print(
        f"{'#':<3} {'keyword':<32} {'market':<8} {'lang':<8} "
        f"{'sources':<18} {'videos':<7} {'risk':<6} {'suit':<6} "
        f"{'real':<5} {'mock':<5} {'score':<6} decision"
    )
    print("-" * 126)

    for index, topic in enumerate(topics, start=1):
        keyword = _display_text(topic.keyword, 31)
        sources = ",".join(topic.sources)[:17]
        print(
            f"{index:<3} {keyword:<32} {topic.market:<8} {topic.language:<8} "
            f"{sources:<18} {len(topic.videos):<7} {topic.risk_score:<6.2f} "
            f"{topic.suitability_score:<6.2f} {topic.real_sources_count:<5} "
            f"{topic.mock_sources_count:<5} "
            f"{topic.opportunity_score:<6.2f} {topic.decision}"
        )


def _display_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0]
    return trimmed or text[:limit]


if __name__ == "__main__":
    main()
