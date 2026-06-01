from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from app import config


POSITIVE_REASONS = {
    "otimo", "bom", "perfeito", "bom_final_engracado", "muito_bom",
    "otimo_mas_longo", "bom_nao_otimo",
}
EXTEND_END_REASONS = {
    "otimo_final_curto", "bom_mas_curto", "bom_com_ajuste",
}
TOPIC_MERGE_ADJUSTMENT_REASONS = {
    "bom_mas_extendeu_assuntos", "emendou_assuntos", "topic_merge",
}
SPONSOR_NEGATIVE_REASONS = {
    "propaganda_produto", "sponsor_segment", "patrocinio", "merchan",
}
STRONG_NON_CONTENT_REASONS = SPONSOR_NEGATIVE_REASONS | {"sem_sentido", "nada_com_nada"}
POSITIVE_ADJUSTMENT_REASONS = (
    EXTEND_END_REASONS | {"otimo_mas_longo"} | TOPIC_MERGE_ADJUSTMENT_REASONS
)
STRONG_POSITIVE_REASONS = {"muito_bom", "perfeito", "otimo"}
MODERATE_POSITIVE_REASONS = {
    "bom", "bom_nao_otimo", "bom_final_engracado", "bom_mas_extendeu_assuntos",
}
DUPLICATE_REASONS = {"duplicado_versao_inferior"}
LOW_ENGAGEMENT_REASONS = {"nao_prendeu", "sem_sentido", "nada_com_nada"}
INCOMPLETE_ENDING_REASONS = {
    "nao_fechou_bem", "final_sem_contexto", "pergunta_sem_resposta",
    "historia_longa_incompleta",
}
STRONG_NEGATIVE_REASONS = {
    "nao_prendeu", "sem_sentido", "nada_com_nada", "nao_gostei",
    "historia_longa_incompleta", "sem_contexto_ruim", "nao_gostei_video_fraco",
} 
STRONG_NEGATIVE_REASONS |= SPONSOR_NEGATIVE_REASONS
SOURCE_NEGATIVE_REASONS = {
    "sem_contexto_ruim", "nao_gostei_video_fraco", "historia_longa_incompleta",
    "nao_gostei", "nao_prendeu", "sem_sentido", "nada_com_nada",
}
SOURCE_WEAK_REASONS = {
    "bom_mas_video_fraco", "historia_longa_incompleta", "final_sem_contexto",
    "nao_fechou_bem",
}
SOURCE_QUALITY_WARNING_REASONS = SOURCE_NEGATIVE_REASONS | SOURCE_WEAK_REASONS
NEGATIVE_REASONS = {
    "nada_com_nada",
    "pergunta_sem_resposta",
    "mediano_ruim",
    "nao_prendeu",
    "sem_sentido",
    "duplicado_versao_inferior",
    "nao_fechou_bem",
    "final_sem_contexto",
    "historia_longa_incompleta",
    "nao_gostei",
    "sem_contexto_ruim",
    "nao_gostei_video_fraco",
    "bom_mas_video_fraco",
} | SPONSOR_NEGATIVE_REASONS


@dataclass
class FeedbackCalibration:
    dataset_path: Path | None
    total: int
    status_counts: dict[str, int]
    reason_counts: dict[str, int]
    average_rating_by_reason: dict[str, float]
    average_start_adjustment: float
    average_end_adjustment: float
    suggested_tail_padding_seconds: int
    positive_reasons: list[str]
    negative_reasons: list[str]
    duplicate_reasons: list[str]
    low_engagement_reasons: list[str]
    strong_positive_reasons: list[str]
    positive_strong_reasons: list[str]
    moderate_positive_reasons: list[str]
    positive_adjustment_reasons: list[str]
    trim_positive_reasons: list[str]
    negative_engagement_reasons: list[str]
    strong_negative_reasons: list[str]
    incomplete_ending_reasons: list[str]
    incomplete_story_reasons: list[str]
    needs_adjustment_reasons: list[str]
    source_negative_reasons: list[str]
    source_weak_reasons: list[str]
    source_quality_warning_reasons: list[str]
    sponsor_negative_reasons: list[str]
    topic_merge_adjustment_reasons: list[str]
    strong_non_content_reasons: list[str]
    sponsor_rejection_count: int
    topic_merge_adjustment_count: int
    feedback_origin_counts: dict[str, int]
    source_collection_counts: dict[str, int]
    rendered_reviews_count: int
    rendered_average_rating: float
    rendered_reason_counts: dict[str, int]
    rendered_video_ids: list[str]
    has_test_reviews: bool


@dataclass
class SourceFeedbackStats:
    video_id: str
    total_reviews: int
    approved_count: int
    rejected_count: int
    needs_adjustment_count: int
    average_rating: float
    rejection_rate: float
    weak_source_feedback_count: int
    source_quality_score_from_feedback: float
    source_quality_reasons: list[str]


class FeedbackCalibrationService:
    def __init__(self, reports_dir: Path | None = None) -> None:
        self.reports_dir = reports_dir or (config.STORAGE_TRENDS_DIR.parent / "reports")

    def latest_dataset_path(self) -> Path | None:
        paths = sorted(self.reports_dir.glob("feedback_dataset_*.json"))
        return paths[-1] if paths else None

    def load_latest(self) -> FeedbackCalibration:
        path = self.latest_dataset_path()
        if not path:
            return self._empty(None)
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception:
            return self._empty(path)
        clips = [clip for clip in payload.get("clips", []) if isinstance(clip, dict)]
        status_counts = Counter(str(clip.get("review_status", "")) for clip in clips)
        reason_counts = Counter(str(clip.get("review_reason", "")) for clip in clips)
        feedback_origin_counts = Counter(str(clip.get("feedback_origin") or "terminal_review") for clip in clips)
        source_collection_counts = Counter(str(clip.get("source_collection") or "") for clip in clips)
        rendered_clips = [
            clip
            for clip in clips
            if clip.get("source_collection") == "rendered_clip_reviews"
            or clip.get("feedback_origin") == "rendered_app_review"
        ]
        rendered_ratings: list[float] = []
        for clip in rendered_clips:
            try:
                rendered_ratings.append(float(clip.get("review_rating")))
            except (TypeError, ValueError):
                pass
        rendered_reason_counts = Counter(str(clip.get("review_reason") or "") for clip in rendered_clips)
        ratings: dict[str, list[float]] = defaultdict(list)
        start_diffs: list[float] = []
        end_diffs: list[float] = []
        for clip in clips:
            reason = str(clip.get("review_reason", ""))
            rating = clip.get("review_rating")
            if rating is not None:
                try:
                    ratings[reason].append(float(rating))
                except (TypeError, ValueError):
                    pass
            start = clip.get("start_seconds")
            end = clip.get("end_seconds")
            ideal_start = clip.get("ideal_start_seconds")
            ideal_end = clip.get("ideal_end_seconds")
            if start is not None and ideal_start is not None:
                start_diffs.append(float(ideal_start) - float(start))
            if end is not None and ideal_end is not None:
                end_diffs.append(float(ideal_end) - float(end))

        average_rating_by_reason = {
            reason: round(mean(values), 2)
            for reason, values in ratings.items()
            if values
        }
        average_end_adjustment = round(mean(end_diffs), 2) if end_diffs else 0.0
        suggested_tail_padding_seconds = int(
            max(5, min(10, round(average_end_adjustment or 6)))
        )
        return FeedbackCalibration(
            dataset_path=path,
            total=len(clips),
            status_counts=dict(status_counts),
            reason_counts=dict(reason_counts),
            average_rating_by_reason=average_rating_by_reason,
            average_start_adjustment=round(mean(start_diffs), 2) if start_diffs else 0.0,
            average_end_adjustment=average_end_adjustment,
            suggested_tail_padding_seconds=suggested_tail_padding_seconds,
            positive_reasons=sorted(POSITIVE_REASONS & set(reason_counts)),
            negative_reasons=sorted(NEGATIVE_REASONS & set(reason_counts)),
            duplicate_reasons=sorted(DUPLICATE_REASONS & set(reason_counts)),
            low_engagement_reasons=sorted(LOW_ENGAGEMENT_REASONS & set(reason_counts)),
            strong_positive_reasons=sorted(STRONG_POSITIVE_REASONS & set(reason_counts)),
            positive_strong_reasons=sorted(STRONG_POSITIVE_REASONS & set(reason_counts)),
            moderate_positive_reasons=sorted(MODERATE_POSITIVE_REASONS & set(reason_counts)),
            positive_adjustment_reasons=sorted(POSITIVE_ADJUSTMENT_REASONS & set(reason_counts)),
            trim_positive_reasons=sorted(POSITIVE_ADJUSTMENT_REASONS & set(reason_counts)),
            negative_engagement_reasons=sorted(LOW_ENGAGEMENT_REASONS & set(reason_counts)),
            strong_negative_reasons=sorted(STRONG_NEGATIVE_REASONS & set(reason_counts)),
            incomplete_ending_reasons=sorted(INCOMPLETE_ENDING_REASONS & set(reason_counts)),
            incomplete_story_reasons=sorted({"historia_longa_incompleta"} & set(reason_counts)),
            needs_adjustment_reasons=sorted(POSITIVE_ADJUSTMENT_REASONS & set(reason_counts)),
            source_negative_reasons=sorted(SOURCE_NEGATIVE_REASONS & set(reason_counts)),
            source_weak_reasons=sorted(SOURCE_WEAK_REASONS & set(reason_counts)),
            source_quality_warning_reasons=sorted(SOURCE_QUALITY_WARNING_REASONS & set(reason_counts)),
            sponsor_negative_reasons=sorted(SPONSOR_NEGATIVE_REASONS & set(reason_counts)),
            topic_merge_adjustment_reasons=sorted(TOPIC_MERGE_ADJUSTMENT_REASONS & set(reason_counts)),
            strong_non_content_reasons=sorted(STRONG_NON_CONTENT_REASONS & set(reason_counts)),
            sponsor_rejection_count=sum(reason_counts.get(reason, 0) for reason in SPONSOR_NEGATIVE_REASONS),
            topic_merge_adjustment_count=sum(
                reason_counts.get(reason, 0) for reason in TOPIC_MERGE_ADJUSTMENT_REASONS
            ),
            feedback_origin_counts=dict(feedback_origin_counts),
            source_collection_counts=dict(source_collection_counts),
            rendered_reviews_count=len(rendered_clips),
            rendered_average_rating=round(mean(rendered_ratings), 2) if rendered_ratings else 0.0,
            rendered_reason_counts=dict(rendered_reason_counts),
            rendered_video_ids=sorted({str(clip.get("video_id") or "") for clip in rendered_clips if clip.get("video_id")}),
            has_test_reviews=reason_counts.get("teste_api", 0) > 0,
        )

    def analyzer_recommendations(self) -> list[str]:
        calibration = self.load_latest()
        recommendations: list[str] = []
        if calibration.sponsor_rejection_count:
            recommendations.append("Penalizar propaganda/produto como non-content forte.")
            recommendations.append("Reforçar filtros de sponsor por produto + benefício/CTA.")
        if calibration.topic_merge_adjustment_count:
            recommendations.append("Penalizar emendou_assuntos/topic_merge no ranking e sugerir trim.")
            recommendations.append("Manter bom_mas_extendeu_assuntos como ajuste positivo, não rejeição.")
        if "pergunta_sem_resposta" in calibration.reason_counts:
            recommendations.append("Bloquear clipes que terminam em pergunta sem resposta.")
        if calibration.needs_adjustment_reasons:
            recommendations.append(
                f"Aplicar tail padding de ~{calibration.suggested_tail_padding_seconds}s em clipes bons."
            )
        if {"otimo", "bom"} & set(calibration.reason_counts):
            recommendations.append(
                "Permitir candidatos abaixo de 60s quando alignment/standalone/narrativa forem altos."
            )
        if calibration.duplicate_reasons:
            recommendations.append("Suprimir duplicados e versões inferiores por região temporal.")
        if calibration.low_engagement_reasons:
            recommendations.append("Penalizar padrões de baixo engajamento: nao_prendeu/sem_sentido.")
        if calibration.positive_adjustment_reasons:
            recommendations.append("Promover bons candidatos com ajuste manual como review_required/needs_trim.")
        if calibration.incomplete_ending_reasons:
            recommendations.append("Manter em diagnostics candidatos com risco de final sem fechamento.")
        if calibration.strong_negative_reasons:
            recommendations.append("Rebaixar ranking de nao_gostei/nao_prendeu/historia_longa_incompleta.")
        if calibration.trim_positive_reasons:
            recommendations.append("Gerar suggested trim para cortes bons, mas longos.")
        if calibration.source_quality_warning_reasons:
            recommendations.append("Usar feedback por vídeo para limitar recomendações de fontes fracas.")
        return recommendations

    def source_feedback_by_video(self, video_id: str) -> SourceFeedbackStats:
        return self.source_feedback_summary().get(video_id, self._empty_source_stats(video_id))

    def source_feedback_summary(self) -> dict[str, SourceFeedbackStats]:
        paths = sorted(self.reports_dir.glob("feedback_dataset_*.json"), reverse=True)
        if not paths:
            return {}

        grouped: dict[str, list[dict[str, Any]]] = {}
        # Use the newest exported feedback available per video. This keeps the
        # latest dataset authoritative for newly reviewed videos while preserving
        # source-quality knowledge for videos omitted from a later export.
        for path in paths:
            try:
                with path.open("r", encoding="utf-8") as file:
                    payload = json.load(file)
            except Exception:
                continue
            by_video: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for clip in payload.get("clips", []):
                video_id = str(clip.get("video_id") or "")
                if video_id and video_id not in grouped:
                    by_video[video_id].append(clip)
            grouped.update({video_id: clips for video_id, clips in by_video.items() if clips})

        return {
            video_id: self._source_stats_from_clips(video_id, clips)
            for video_id, clips in grouped.items()
        }

    def positive_ranges_for_video(self, video_id: str) -> list[dict[str, Any]]:
        path = self.latest_dataset_path()
        if not path:
            return []
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception:
            return []
        positive_reasons = POSITIVE_REASONS | EXTEND_END_REASONS | {"bom_mas_extendeu_assuntos"}
        ranges: list[dict[str, Any]] = []
        for clip in payload.get("clips", []):
            if clip.get("video_id") != video_id:
                continue
            if clip.get("review_status") not in {"approved", "needs_adjustment"}:
                continue
            if clip.get("review_reason") not in positive_reasons:
                continue
            ideal_start = clip.get("ideal_start_seconds")
            ideal_end = clip.get("ideal_end_seconds")
            start = clip.get("ideal_start_seconds") or clip.get("start_seconds")
            end = clip.get("ideal_end_seconds") or clip.get("end_seconds")
            if start is None or end is None:
                continue
            ranges.append(
                {
                    "start": float(start),
                    "end": float(end),
                    "original_start": float(clip.get("start_seconds")),
                    "original_end": float(clip.get("end_seconds")),
                    "ideal_start": float(ideal_start) if ideal_start is not None else None,
                    "ideal_end": float(ideal_end) if ideal_end is not None else None,
                    "reason": clip.get("review_reason", ""),
                    "rating": clip.get("review_rating"),
                }
            )
        return ranges

    def reviewed_ranges_for_video(self, video_id: str) -> list[dict[str, Any]]:
        path = self.latest_dataset_path()
        if not path:
            return []
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception:
            return []
        ranges: list[dict[str, Any]] = []
        for clip in payload.get("clips", []):
            if clip.get("video_id") != video_id:
                continue
            start = clip.get("start_seconds")
            end = clip.get("end_seconds")
            if start is None or end is None:
                continue
            ranges.append(
                {
                    "start": float(start),
                    "end": float(end),
                    "rank": clip.get("rank"),
                    "reason": clip.get("review_reason", ""),
                    "rating": clip.get("review_rating"),
                    "status": clip.get("review_status"),
                }
            )
        return ranges

    @staticmethod
    def _empty(path: Path | None) -> FeedbackCalibration:
        return FeedbackCalibration(
            dataset_path=path,
            total=0,
            status_counts={},
            reason_counts={},
            average_rating_by_reason={},
            average_start_adjustment=0.0,
            average_end_adjustment=0.0,
            suggested_tail_padding_seconds=6,
            positive_reasons=[],
            negative_reasons=[],
            duplicate_reasons=[],
            low_engagement_reasons=[],
            strong_positive_reasons=[],
            positive_strong_reasons=[],
            moderate_positive_reasons=[],
            positive_adjustment_reasons=[],
            trim_positive_reasons=[],
            negative_engagement_reasons=[],
            strong_negative_reasons=[],
            incomplete_ending_reasons=[],
            incomplete_story_reasons=[],
            needs_adjustment_reasons=[],
            source_negative_reasons=[],
            source_weak_reasons=[],
            source_quality_warning_reasons=[],
            sponsor_negative_reasons=[],
            topic_merge_adjustment_reasons=[],
            strong_non_content_reasons=[],
            sponsor_rejection_count=0,
            topic_merge_adjustment_count=0,
            feedback_origin_counts={},
            source_collection_counts={},
            rendered_reviews_count=0,
            rendered_average_rating=0.0,
            rendered_reason_counts={},
            rendered_video_ids=[],
            has_test_reviews=False,
        )

    @staticmethod
    def _source_stats_from_clips(video_id: str, clips: list[dict[str, Any]]) -> SourceFeedbackStats:
        total = len(clips)
        approved = sum(1 for clip in clips if clip.get("review_status") == "approved")
        rejected = sum(1 for clip in clips if clip.get("review_status") == "rejected")
        needs_adjustment = sum(1 for clip in clips if clip.get("review_status") == "needs_adjustment")
        ratings: list[float] = []
        reasons = Counter()
        weak_count = 0
        for clip in clips:
            reason = str(clip.get("review_reason") or "")
            if reason:
                reasons[reason] += 1
            if reason in SOURCE_QUALITY_WARNING_REASONS:
                weak_count += 1
            rating = clip.get("review_rating")
            if rating is not None:
                try:
                    ratings.append(float(rating))
                except (TypeError, ValueError):
                    pass

        average_rating = round(mean(ratings), 2) if ratings else 0.0
        rejection_rate = round(rejected / total, 2) if total else 0.0
        score = 5.0
        score += approved * 0.45
        score += needs_adjustment * 0.15
        score -= rejected * 0.9
        rendered_count = sum(
            1
            for clip in clips
            if clip.get("feedback_origin") == "rendered_app_review"
            or clip.get("source_collection") == "rendered_clip_reviews"
        )
        score += min(0.4, rendered_count * 0.1)
        score -= weak_count * 1.15
        if ratings:
            score += (average_rating - 3.0) * 1.4
        score -= rejection_rate * 2.0
        if reasons.get("bom_mas_video_fraco"):
            score -= 1.4
        if reasons.get("nao_gostei_video_fraco") or reasons.get("sem_contexto_ruim"):
            score -= 2.0
        if reasons.get("historia_longa_incompleta"):
            score -= 1.2
        if approved and any(reasons.get(reason) for reason in SPONSOR_NEGATIVE_REASONS):
            score = max(score, 5.2)
        if reasons.get("otimo") or reasons.get("perfeito") or reasons.get("muito_bom"):
            score += 0.8
        source_reasons = [
            f"{reason}:{count}"
            for reason, count in reasons.most_common()
            if (
                reason in SOURCE_QUALITY_WARNING_REASONS
                or reason in POSITIVE_REASONS
                or reason in SPONSOR_NEGATIVE_REASONS
                or reason in TOPIC_MERGE_ADJUSTMENT_REASONS
            )
        ]
        return SourceFeedbackStats(
            video_id=video_id,
            total_reviews=total,
            approved_count=approved,
            rejected_count=rejected,
            needs_adjustment_count=needs_adjustment,
            average_rating=average_rating,
            rejection_rate=rejection_rate,
            weak_source_feedback_count=weak_count,
            source_quality_score_from_feedback=round(max(0.0, min(10.0, score)), 2),
            source_quality_reasons=source_reasons,
        )

    @staticmethod
    def _empty_source_stats(video_id: str) -> SourceFeedbackStats:
        return SourceFeedbackStats(
            video_id=video_id,
            total_reviews=0,
            approved_count=0,
            rejected_count=0,
            needs_adjustment_count=0,
            average_rating=0.0,
            rejection_rate=0.0,
            weak_source_feedback_count=0,
            source_quality_score_from_feedback=5.0,
            source_quality_reasons=[],
        )
