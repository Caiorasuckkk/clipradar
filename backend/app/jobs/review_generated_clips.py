from __future__ import annotations

import argparse
import json
import sys

from app import config


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", required=True)
    args = parser.parse_args()

    path = config.STORAGE_CLIPS_DIR / f"{args.video_id}_clips.json"
    if not path.exists():
        print(f"Arquivo não encontrado: {path}")
        return

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    print(f"REVIEW GENERATED CLIPS — {args.video_id}")
    print(payload.get("video_title", ""))
    _print_language_warning(args.video_id, payload)
    _print_source_quality(payload)
    if payload.get("analysis_note"):
        print(payload.get("analysis_note"))
    base_url = payload.get("url", "")
    clips = payload.get("clips", [])
    if not clips:
        print("Nenhum clipe recomendado.")
    for clip in clips:
        timestamp = int(float(clip.get("start_seconds") or 0))
        link = f"{base_url}&t={timestamp}s" if base_url else ""
        print(
            f"#{clip.get('rank')} {clip.get('start_seconds')}-{clip.get('end_seconds')}s "
            f"duration={clip.get('duration_seconds')}s version={clip.get('clip_version')} "
            f"recommended={clip.get('recommended_version')} score={clip.get('score')} "
            f"review_required={clip.get('recommended_review_required')} "
            f"context={clip.get('context_quality_score')} "
            f"ending={clip.get('ending_quality_score')} complete={clip.get('has_complete_ending')} "
            f"development={clip.get('has_development')} completeness={clip.get('completeness_score')} "
            f"multi={clip.get('contains_multiple_thoughts')} split={clip.get('split_suggestion_seconds')} "
            f"merged={clip.get('merged_from')}"
        )
        print(
            f"story={clip.get('story_completion_score')} closure={clip.get('thought_closure_score')} "
            f"context_before={clip.get('context_before_score')} out_of_context={clip.get('starts_out_of_context')} "
            f"density={clip.get('content_density_score')} weak_content={clip.get('weak_content')}"
        )
        print(
            f"narrative={clip.get('narrative_quality_score')} standalone={clip.get('standalone_score')} "
            f"false_full_thought_risk={clip.get('false_full_thought_risk')} "
            f"reference_alignment={clip.get('reference_alignment_score')} "
            f"recommended={clip.get('recommended_version')} "
            f"not_recommended={clip.get('not_recommended_reason', '')}"
        )
        print(
            f"tail_padding={clip.get('tail_padding_applied')} "
            f"tail_seconds={clip.get('tail_padding_seconds')} "
            f"unanswered_question={clip.get('ends_with_unanswered_question')} "
            f"review_required={clip.get('recommended_review_required')} "
            f"duplicate_suppressed={clip.get('duplicate_suppressed')} "
            f"duplicate_of={clip.get('duplicate_of_rank')}"
        )
        print(
            f"promoted_from_diagnostic={clip.get('promoted_from_diagnostic')} "
            f"promotion_reason={clip.get('promotion_reason')} "
            f"needs_trim={clip.get('needs_trim')}"
        )
        print(
            f"ranking={clip.get('ranking_quality_score')} "
            f"tier={clip.get('ranking_quality_tier')} "
            f"long_story_risk={clip.get('long_incomplete_story_risk')}"
        )
        print(f"ranking_reason={clip.get('ranking_reason')}")
        if clip.get("needs_trim"):
            print(
                f"trim_reason={clip.get('trim_reason')} "
                f"strategy={clip.get('suggested_trim_strategy')}"
            )
            print(_trim_line(clip))
        print(
            f"engagement_risk={clip.get('engagement_risk_score')} "
            f"boring_or_confusing={clip.get('boring_or_confusing_score')} "
            f"feedback_similarity={clip.get('feedback_similarity_reason')}"
        )
        if clip.get("feedback_calibration_notes"):
            print(f"feedback_notes={clip.get('feedback_calibration_notes')}")
        if clip.get("tail_padding_reason"):
            print(f"tail_reason={clip.get('tail_padding_reason')}")
        if clip.get("recommendation_reason"):
            print(f"recommendation_reason={clip.get('recommendation_reason')}")
        print(
            f"non_content={clip.get('non_content_score')} rejected_reason={clip.get('rejected_content_reason')} "
            f"duration_reason={clip.get('reason_for_duration')} ending_type={clip.get('ending_type')}"
        )
        print(
            f"review: status={clip.get('review_status', 'pending_review')} "
            f"rating={clip.get('review_rating')} reason={clip.get('review_reason', '')}"
        )
        print(
            f"notes: {_display(clip.get('review_notes', ''), 140)} "
            f"ideal={clip.get('ideal_start_seconds')} - {clip.get('ideal_end_seconds')}"
        )
        print(f"selected: {clip.get('selected_boundary_reason')}")
        print(f"boundary: {clip.get('boundary_adjustment_reason')}")
        if link:
            print(f"link: {link}")
        print(f"text: {_display(clip.get('text', ''), 220)}")
        print(
            "review command: "
            f"python -m app.jobs.review_clip --video-id {args.video_id} "
            f"--rank {clip.get('rank')} --status approved --rating 4 --reason \"bom\""
        )
        print("")

    diagnostic_candidates = payload.get("diagnostic_candidates", [])
    if diagnostic_candidates:
        print("Diagnostic Candidates")
        for candidate in diagnostic_candidates:
            timestamp = int(float(candidate.get("start_seconds") or 0))
            link = candidate.get("link") or (f"{base_url}&t={timestamp}s" if base_url else "")
            print(
                f"#{candidate.get('rank')} {candidate.get('start_seconds')}-{candidate.get('end_seconds')}s "
                f"duration={candidate.get('duration_seconds')}s score={candidate.get('score')} "
                f"narrative={candidate.get('narrative_quality_score')} "
                f"standalone={candidate.get('standalone_score')} "
                f"risk={candidate.get('false_full_thought_risk')} "
                f"reference_alignment={candidate.get('reference_alignment_score')}"
            )
            print(
                f"tail_padding={candidate.get('tail_padding_applied')} "
                f"tail_seconds={candidate.get('tail_padding_seconds')} "
                f"unanswered_question={candidate.get('ends_with_unanswered_question')} "
                f"duplicate_suppressed={candidate.get('duplicate_suppressed')} "
                f"duplicate_of={candidate.get('duplicate_of_rank')}"
            )
            print(
                f"promoted_from_diagnostic={candidate.get('promoted_from_diagnostic')} "
                f"promotion_reason={candidate.get('promotion_reason')} "
                f"needs_trim={candidate.get('needs_trim')}"
            )
            print(
                f"ranking={candidate.get('ranking_quality_score')} "
                f"tier={candidate.get('ranking_quality_tier')} "
                f"long_story_risk={candidate.get('long_incomplete_story_risk')}"
            )
            print(f"ranking_reason={candidate.get('ranking_reason')}")
            if candidate.get("needs_trim"):
                print(
                    f"trim_reason={candidate.get('trim_reason')} "
                    f"strategy={candidate.get('suggested_trim_strategy')}"
                )
                print(_trim_line(candidate))
            print(
                f"engagement_risk={candidate.get('engagement_risk_score')} "
                f"boring_or_confusing={candidate.get('boring_or_confusing_score')} "
                f"feedback_similarity={candidate.get('feedback_similarity_reason')}"
            )
            if candidate.get("feedback_calibration_notes"):
                print(f"feedback_notes={candidate.get('feedback_calibration_notes')}")
            print(f"reason: {candidate.get('not_recommended_reason', '')}")
            print(f"failed_criteria: {', '.join(candidate.get('failed_criteria', []))}")
            print(
                "review command: "
                f"python -m app.jobs.review_clip --video-id {args.video_id} "
                f"--target diagnostic --rank {candidate.get('rank')} "
                "--status approved --rating 4 --reason \"bom\""
            )
            if candidate.get("rejected_content_reason"):
                print(f"rejected_content: {candidate.get('rejected_content_reason')}")
            if link:
                print(f"link: {link}")
            print(f"text: {_display(candidate.get('text', ''), 220)}")
            print("")


def _display(value: object, limit: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def _trim_line(item: dict[str, object]) -> str:
    start = item.get("suggested_trim_start_seconds")
    end = item.get("suggested_trim_end_seconds")
    duration = item.get("suggested_trim_duration_seconds")
    confidence = item.get("trim_confidence_score")
    strategy = item.get("trim_strategy")
    warning = item.get("trim_warning")
    if start is None or end is None:
        return (
            f"suggested trim: unavailable | confidence={confidence} "
            f"strategy={strategy} warning={warning}"
        )
    return (
        f"suggested trim: {_mmss(float(start))} até {_mmss(float(end))} "
        f"({duration}s) | confidence={confidence} strategy={strategy} warning={warning}"
    )


def _print_source_quality(payload: dict) -> None:
    summary = dict(payload.get("analysis_summary") or {})
    score = payload.get("source_quality_score", summary.get("source_quality_score"))
    tier = payload.get("source_quality_tier", summary.get("source_quality_tier"))
    reason = payload.get("source_quality_reason", summary.get("source_quality_reason", ""))
    warning = payload.get("source_quality_warning", summary.get("source_quality_warning", ""))
    continue_review = payload.get(
        "should_continue_video_review",
        summary.get("should_continue_video_review", True),
    )
    if score is None and not tier:
        return
    print(f"source quality: {score} / {tier}")
    print(f"source reason: {reason}")
    if warning:
        print(f"source warning: {warning}")
    print(f"continue review: {continue_review}")


def _mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def _print_language_warning(video_id: str, payload: dict) -> None:
    transcript_meta = dict(payload.get("transcript_metadata") or {})
    transcript_path = config.STORAGE_TRANSCRIPTS_DIR / f"{video_id}.json"
    if transcript_path.exists():
        try:
            with transcript_path.open("r", encoding="utf-8") as file:
                transcript_meta.update(json.load(file))
        except Exception:
            pass
    requested = transcript_meta.get("requested_language")
    detected = transcript_meta.get("detected_language") or transcript_meta.get("language")
    conflict = bool(transcript_meta.get("language_conflict"))
    if not conflict and requested and detected:
        conflict = str(requested).lower() != str(detected).lower()
        if str(requested).lower() == "pt" and str(detected).lower() in {"pt", "portuguese"}:
            conflict = False
    if conflict:
        print("⚠️ Language warning:")
        print(f"requested_language={requested}")
        print(f"detected_language={detected}")
        print("This transcript may be unreliable.")
    elif requested or detected:
        print(f"language: requested={requested or 'auto'} detected={detected or 'unknown'}")


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
