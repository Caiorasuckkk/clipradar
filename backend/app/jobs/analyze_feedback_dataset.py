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
    print("Positive adjustment reasons:")
    for reason in calibration.positive_adjustment_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
    print("")
    print("Incomplete ending reasons:")
    for reason in calibration.incomplete_ending_reasons:
        print(f"- {reason}: count={calibration.reason_counts.get(reason, 0)}")
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


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
