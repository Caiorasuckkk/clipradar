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
    "otimo_mas_longo",
}
EXTEND_END_REASONS = {
    "otimo_final_curto", "bom_mas_curto", "bom_com_ajuste",
}
POSITIVE_ADJUSTMENT_REASONS = EXTEND_END_REASONS | {"otimo_mas_longo"}
STRONG_POSITIVE_REASONS = {"muito_bom", "perfeito", "otimo"}
DUPLICATE_REASONS = {"duplicado_versao_inferior"}
LOW_ENGAGEMENT_REASONS = {"nao_prendeu", "sem_sentido", "nada_com_nada"}
INCOMPLETE_ENDING_REASONS = {"nao_fechou_bem", "final_sem_contexto", "pergunta_sem_resposta"}
NEGATIVE_REASONS = {
    "propaganda_produto",
    "nada_com_nada",
    "pergunta_sem_resposta",
    "mediano_ruim",
    "nao_prendeu",
    "sem_sentido",
    "duplicado_versao_inferior",
    "nao_fechou_bem",
    "final_sem_contexto",
}


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
    positive_adjustment_reasons: list[str]
    negative_engagement_reasons: list[str]
    incomplete_ending_reasons: list[str]
    needs_adjustment_reasons: list[str]


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
            positive_adjustment_reasons=sorted(POSITIVE_ADJUSTMENT_REASONS & set(reason_counts)),
            negative_engagement_reasons=sorted(LOW_ENGAGEMENT_REASONS & set(reason_counts)),
            incomplete_ending_reasons=sorted(INCOMPLETE_ENDING_REASONS & set(reason_counts)),
            needs_adjustment_reasons=sorted(POSITIVE_ADJUSTMENT_REASONS & set(reason_counts)),
        )

    def analyzer_recommendations(self) -> list[str]:
        calibration = self.load_latest()
        recommendations: list[str] = []
        if "propaganda_produto" in calibration.reason_counts:
            recommendations.append("Penalizar propaganda/produto como non-content forte.")
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
        return recommendations

    def positive_ranges_for_video(self, video_id: str) -> list[dict[str, Any]]:
        path = self.latest_dataset_path()
        if not path:
            return []
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except Exception:
            return []
        positive_reasons = POSITIVE_REASONS | EXTEND_END_REASONS
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
            positive_adjustment_reasons=[],
            negative_engagement_reasons=[],
            incomplete_ending_reasons=[],
            needs_adjustment_reasons=[],
        )
