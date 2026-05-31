from __future__ import annotations

import sys

from app.services.feedback_calibration_service import FeedbackCalibrationService


def main() -> None:
    configure_output()
    service = FeedbackCalibrationService()
    calibration = service.load_latest()
    print("FEEDBACK DATASET ANALYSIS")
    print(f"Dataset: {calibration.dataset_path}")
    print(f"Total revisado: {calibration.total}")
    print(f"approved: {calibration.status_counts.get('approved', 0)}")
    print(f"rejected: {calibration.status_counts.get('rejected', 0)}")
    print(f"needs_adjustment: {calibration.status_counts.get('needs_adjustment', 0)}")
    print("")
    print("Top reasons positivos:")
    for reason in calibration.positive_reasons:
        print(
            f"- {reason}: count={calibration.reason_counts.get(reason, 0)} "
            f"avg_rating={calibration.average_rating_by_reason.get(reason)}"
        )
    print("")
    print("Top reasons negativos:")
    for reason in calibration.negative_reasons:
        print(
            f"- {reason}: count={calibration.reason_counts.get(reason, 0)} "
            f"avg_rating={calibration.average_rating_by_reason.get(reason)}"
        )
    print("")
    print("Duplicate reasons:")
    for reason in calibration.duplicate_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Low engagement reasons:")
    for reason in calibration.low_engagement_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Strong positive reasons:")
    for reason in calibration.strong_positive_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Moderate positive reasons:")
    for reason in calibration.moderate_positive_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Positive adjustment reasons:")
    for reason in calibration.positive_adjustment_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Trim positive reasons:")
    for reason in calibration.trim_positive_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Strong negative reasons:")
    for reason in calibration.strong_negative_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Incomplete ending reasons:")
    for reason in calibration.incomplete_ending_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Incomplete story reasons:")
    for reason in calibration.incomplete_story_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Source quality warning reasons:")
    for reason in calibration.source_quality_warning_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Average rating por reason:")
    for reason, rating in sorted(calibration.average_rating_by_reason.items()):
        print(f"- {reason}: {rating}")
    print("")
    print("Reasons de ajuste:")
    for reason in calibration.needs_adjustment_reasons:
        print(
            f"- {reason}: count={calibration.reason_counts.get(reason, 0)} "
            f"avg_rating={calibration.average_rating_by_reason.get(reason)}"
        )
    print("")
    print(f"Média ajuste ideal_start: {calibration.average_start_adjustment:.2f}s")
    print(f"Média ajuste ideal_end: {calibration.average_end_adjustment:.2f}s")
    print(f"Tail padding sugerido: {calibration.suggested_tail_padding_seconds}s")
    print("")
    print("Recomendações automáticas para o analyzer:")
    for recommendation in service.analyzer_recommendations():
        print(f"- {recommendation}")
    print("")
    print("Resumo por vídeo:")
    summaries = sorted(
        service.source_feedback_summary().values(),
        key=lambda item: item.source_quality_score_from_feedback,
        reverse=True,
    )
    for item in summaries:
        print(
            f"- {item.video_id}: score={item.source_quality_score_from_feedback} "
            f"avg={item.average_rating} approved={item.approved_count} "
            f"rejected={item.rejected_count} rejection_rate={item.rejection_rate} "
            f"weak_source={item.weak_source_feedback_count} "
            f"reasons={', '.join(item.source_quality_reasons[:4])}"
        )
    print("")
    print("Top vídeos bons:")
    for item in summaries[:5]:
        print(f"- {item.video_id}: {item.source_quality_score_from_feedback}")
    print("")
    print("Top vídeos fracos:")
    for item in list(reversed(summaries))[:5]:
        print(f"- {item.video_id}: {item.source_quality_score_from_feedback}")
    print("")
    for item in summaries:
        if item.video_id == "758VjvlA-xo" and item.source_quality_score_from_feedback < 5.0:
            print("Recomendação: João Kléber / 758VjvlA-xo deve ser tratado como weak_source ou bad_source.")
        if item.video_id in {"vZdVOYUl8Sg", "LuEPSwvsBrs"} and item.source_quality_score_from_feedback >= 5.0:
            print(f"Recomendação: {item.video_id} deve continuar como good_source/review_source se os ratings seguirem bons.")


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
