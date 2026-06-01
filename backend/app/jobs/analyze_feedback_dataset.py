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
    print(f"rendered reviews incluídas: {calibration.rendered_reviews_count}")
    print(f"candidate reviews incluídas: {calibration.source_collection_counts.get('candidate_clip_reviews', 0)}")
    print(f"média rendered reviews: {calibration.rendered_average_rating}")
    if calibration.has_test_reviews:
        print('WARNING: Há reviews de teste no dataset; considere corrigir antes de calibrar.')
    print("")
    print("Count por feedback_origin:")
    for origin, count in sorted(calibration.feedback_origin_counts.items()):
        print(f"- {origin}: {count}")
    print("")
    print("Count por source_collection:")
    for source_collection, count in sorted(calibration.source_collection_counts.items()):
        print(f"- {source_collection}: {count}")
    print("")
    print("Top reasons do app:")
    for reason, count in sorted(
        calibration.rendered_reason_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[:10]:
        print(f"- {reason}: {count}")
    print("")
    print("Top reasons dos candidatos:")
    for reason, count in sorted(
        (
            (reason, count)
            for reason, count in calibration.candidate_reason_counts.items()
            if reason
        ),
        key=lambda item: (-item[1], item[0]),
    )[:10]:
        print(f"- {reason}: {count}")
    print("")
    print("Vídeos com rendered reviews:")
    for video_id in calibration.rendered_video_ids:
        print(f"- {video_id}")
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
    print(f"Sponsor/product rejected count: {calibration.sponsor_rejection_count}")
    for reason in calibration.sponsor_negative_reasons:
        print(
            f"- {reason}: count={calibration.reason_counts.get(reason, 0)} "
            f"avg_rating={calibration.average_rating_by_reason.get(reason)}"
        )
    print("")
    print(f"Topic merge adjustment count: {calibration.topic_merge_adjustment_count}")
    for reason in calibration.topic_merge_adjustment_reasons:
        print(
            f"- {reason}: count={calibration.reason_counts.get(reason, 0)} "
            f"avg_rating={calibration.average_rating_by_reason.get(reason)}"
        )
    print("")
    print("Strong non-content reasons:")
    for reason in calibration.strong_non_content_reasons:
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
    print("- reforçar propaganda_produto quando produto vier com benefício/CTA.")
    print("- penalizar emendou_assuntos/topic_merge com trim e cap de ranking.")
    print("- manter bom_mas_extendeu_assuntos como ajuste positivo, não rejeição.")
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
        if any(
            reason.startswith(("propaganda_produto", "sponsor_segment", "patrocinio", "merchan"))
            for reason in item.source_quality_reasons
        ):
            print(f"  sponsor/product example: {item.video_id}")
        if any(
            reason.startswith(("bom_mas_extendeu_assuntos", "emendou_assuntos", "topic_merge"))
            for reason in item.source_quality_reasons
        ):
            print(f"  topic merge example: {item.video_id}")
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
