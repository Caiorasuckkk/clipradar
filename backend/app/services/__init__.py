from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "AttentionScoreService": "attention_score_service",
    "ClipAnalyzerService": "clip_analyzer_service",
    "ContentSuitabilityService": "content_suitability_service",
    "CreatorRightsService": "creator_rights_service",
    "DownloaderService": "downloader_service",
    "DynamicQueryExpansionService": "dynamic_query_expansion_service",
    "DynamicQueryQualityService": "dynamic_query_quality_service",
    "MetadataService": "metadata_service",
    "NoiseFilterService": "noise_filter_service",
    "OpportunityReportService": "opportunity_report_service",
    "OpportunityScoreService": "opportunity_score_service",
    "ProcessingPriorityService": "processing_priority_service",
    "SourceFinderService": "source_finder_service",
    "TopicBaseQualityService": "topic_base_quality_service",
    "TranscriptionService": "transcription_service",
    "TrendAggregatorService": "trend_aggregator_service",
    "TrendEntityExtractor": "trend_entity_extractor",
    "VideoHistoryService": "video_history_service",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if not module_name:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"app.services.{module_name}")
    value = getattr(module, name)
    globals()[name] = value
    return value
