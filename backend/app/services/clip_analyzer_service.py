from __future__ import annotations

import re
from typing import Any

from app.config import (
    DIAGNOSTIC_CANDIDATES_TOP_N,
    FULL_THOUGHT_SECONDS_MAX,
    FULL_THOUGHT_SECONDS_MIN,
    HARD_MAX_CLIP_SECONDS,
    MIN_CLIP_SECONDS,
    SHORT_CLIP_SECONDS_MAX,
    SHORT_CLIP_SECONDS_MIN,
    SOFT_MAX_CLIP_SECONDS,
    TARGET_CLIP_SECONDS,
)
from app.services.feedback_calibration_service import FeedbackCalibrationService


class ClipAnalyzerService:
    MIN_CLIP_SECONDS = MIN_CLIP_SECONDS
    TARGET_SECONDS = TARGET_CLIP_SECONDS
    SOFT_MAX_SECONDS = SOFT_MAX_CLIP_SECONDS
    HARD_MAX_SECONDS = HARD_MAX_CLIP_SECONDS
    SHORT_MIN_SECONDS = SHORT_CLIP_SECONDS_MIN
    SHORT_MAX_SECONDS = SHORT_CLIP_SECONDS_MAX
    FULL_MIN_SECONDS = FULL_THOUGHT_SECONDS_MIN
    FULL_MAX_SECONDS = FULL_THOUGHT_SECONDS_MAX
    DIAGNOSTIC_TOP_N = DIAGNOSTIC_CANDIDATES_TOP_N

    HOOK_TRIGGERS_PT = {
        "nunca", "sempre", "impossível", "inacreditável", "verdade",
        "mentira", "segredo", "absurdo", "polêmica", "escândalo",
        "preso", "processado", "bilhão", "milhão", "ninguém",
        "todo mundo", "literalmente", "exatamente", "na verdade",
        "o problema é", "o que aconteceu foi", "deixa eu te contar",
        "você não vai acreditar", "corrupção", "operação", "polícia",
        "crime", "prisão", "investigação", "denúncia", "bastidores",
    }
    HOOK_TRIGGERS_EN = {
        "never", "always", "impossible", "unbelievable", "truth", "lie",
        "secret", "absurd", "scandal", "arrested", "billion", "million",
        "nobody", "everyone", "literally", "exactly", "actually",
        "the problem is", "what happened was", "let me tell you",
        "you won't believe", "corruption", "operation", "police", "crime",
        "prison", "investigation", "lawsuit", "allegation",
    }
    THOUGHT_START_TERMS = {
        "o problema é", "a verdade é", "o que aconteceu foi", "ninguém sabia",
        "todo mundo sabia", "na verdade", "por exemplo", "aí", "ai",
        "então", "mas", "porque", "só que", "so que", "agora",
        "the problem is", "the truth is", "what happened was", "for example",
        "actually", "so", "but", "because", "now",
    }
    DEVELOPMENT_TERMS = {
        "porque", "por que", "então", "por isso", "aí", "foi quando",
        "o problema", "a consequência", "no final", "aconteceu", "exemplo",
        "por exemplo", "contexto", "resultado", "significa", "explica",
        "motivo", "causa", "só que", "mas", "conclusão", "consequência",
        "because", "therefore", "for example", "what happened", "means",
        "result", "consequence", "context", "problem", "solution", "but",
        "in the end",
    }
    CONTINUATION_ENDINGS = {
        "porque", "então", "mas", "aí", "ai", "quando", "se", "que", "e",
        "só que", "so que", "por exemplo", "né", "ne", "because", "so",
        "but", "when", "if", "that", "and", "for example", "you know",
    }
    CONCLUSION_TERMS = {
        "por isso", "então", "no final", "resultado", "conclusão", "resumo",
        "é isso", "foi isso", "therefore", "that's why", "in the end",
        "the result", "conclusion", "so",
    }
    WEAK_CONCLUSION_TERMS = {"então", "so"}
    NON_CONTENT_TERMS = {
        "superchat", "super chat", "manda salve", "se inscreve", "deixa o like",
        "patrocínio", "patrocinio", "patrocinador", "cupom", "merchandise",
        "merchan", "plataforma", "pix", "apoia.se", "membros", "recado rápido",
        "recado rapido", "intervalo", "chamada comercial", "propaganda",
        "publicidade", "loja", "camiseta", "sponsor", "sponsored",
        "subscribe", "like the video", "merch", "membership", "promo code",
        "ad break", "produto", "produtos", "venda", "vender", "comprar",
        "compre", "curso", "demonstração de produto", "demonstracao de produto",
    }
    PRODUCT_TERMS = {
        "produto", "produtos", "patrocínio", "patrocinio", "publicidade",
        "propaganda", "merchan", "cupom", "venda", "vender", "comprar",
        "compre", "loja", "curso", "demonstração de produto",
        "demonstracao de produto",
    }
    ENTITY_ACTION_TERMS = {
        "polícia", "policia", "crime", "prisão", "prisao", "investigação",
        "investigacao", "governo", "banco", "master", "lula", "bolsonaro",
        "stf", "operação", "operacao", "facção", "faccao", "dinheiro",
        "empresa", "presidente", "ministro", "prefeito", "governador",
        "police", "crime", "prison", "government", "bank", "court",
        "money", "company", "president", "minister", "lawsuit",
    }
    OUT_OF_CONTEXT_STARTS = {
        "isso", "ele", "ela", "eles", "elas", "aí", "ai", "então",
        "porque", "como eu disse", "né", "ne", "isso aí", "this",
        "that", "he", "she", "they", "so", "because", "as i said",
    }

    def __init__(self) -> None:
        self.feedback_calibration_service = FeedbackCalibrationService()
        self.feedback_calibration = self.feedback_calibration_service.load_latest()

    def analyze(
        self,
        transcript: dict[str, Any],
        video_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self.analyze_with_diagnostics(transcript, video_metadata)["clips"]

    def analyze_with_diagnostics(
        self,
        transcript: dict[str, Any],
        video_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        segments = transcript.get("segments", [])
        if not segments:
            return {
                "clips": [],
                "diagnostic_candidates": [],
                "analysis_summary": {
                    "recommended_count": 0,
                    "diagnostic_count": 0,
                    "reason": "transcript sem segmentos",
                },
            }

        video_duration = float(
            transcript.get("duration_seconds")
            or video_metadata.get("duration_seconds")
            or segments[-1].get("end", 0.0)
            or 0.0
        )
        thought_units = self._build_thought_units(segments, video_duration, video_metadata)
        thought_units.extend(self._feedback_seed_units(segments, video_duration, video_metadata))
        selected = self._select_thought_units(thought_units)
        diagnostics = self._select_diagnostic_units(thought_units, selected)

        clips = [
            self._format_clip(unit, rank, video_metadata, rejected_by_analyzer=False)
            for rank, unit in enumerate(selected, start=1)
        ]
        diagnostic_candidates = [
            self._format_clip(unit, rank, video_metadata, rejected_by_analyzer=True)
            for rank, unit in enumerate(diagnostics, start=1)
        ]
        reason = ""
        if not clips and diagnostic_candidates:
            reason = "nenhum candidato atingiu qualidade narrativa mínima"
        elif not clips:
            reason = "nenhum candidato detectado"
        elif len(clips) < 5:
            reason = "menos clipes retornados porque os demais não atingiram qualidade narrativa mínima"

        return {
            "clips": clips,
            "diagnostic_candidates": diagnostic_candidates,
            "analysis_summary": {
                "recommended_count": len(clips),
                "diagnostic_count": len(diagnostic_candidates),
                "reason": reason,
            },
        }

    def _format_clip(
        self,
        unit: dict[str, Any],
        rank: int,
        video_metadata: dict[str, Any],
        rejected_by_analyzer: bool,
    ) -> dict[str, Any]:
        start_seconds = round(unit["start"], 2)
        base_url = str(video_metadata.get("url", ""))
        timestamp = int(start_seconds)
        link = f"{base_url}&t={timestamp}s" if base_url else ""
        return {
            "rank": rank,
            "start_seconds": start_seconds,
            "end_seconds": round(unit["end"], 2),
            "duration_seconds": round(unit["duration"], 2),
            "score": round(unit["score"], 2),
            "hook_score": round(unit["hook_score"], 2),
            "development_score": round(unit["development_score"], 2),
            "ending_quality_score": round(unit["ending_quality_score"], 2),
            "context_quality_score": round(unit["context_quality_score"], 2),
            "weak_development": unit["weak_development"],
            "incomplete_ending": not unit["has_complete_ending"],
            "boundary_adjustment_reason": unit["boundary_adjustment_reason"],
            "merged_from": unit["merged_from"],
            "thought_unit_start": round(unit["thought_unit_start"], 2),
            "thought_unit_end": round(unit["thought_unit_end"], 2),
            "completeness_score": round(unit["completeness_score"], 2),
            "contains_multiple_thoughts": unit["contains_multiple_thoughts"],
            "split_suggestion_seconds": (
                round(unit["split_suggestion_seconds"], 2)
                if unit["split_suggestion_seconds"] is not None
                else None
            ),
            "has_complete_ending": unit["has_complete_ending"],
            "has_development": unit["has_development"],
            "selected_boundary_reason": unit["selected_boundary_reason"],
            "text": unit["text"],
            "first_sentence": unit["first_sentence"],
            "trigger_words": unit["trigger_words"],
            "words_per_second": round(unit["words_per_second"], 2),
            "clip_version": unit["clip_version"],
            "recommended_version": False if rejected_by_analyzer else unit["recommended_version"],
            "recommended_review_required": unit["recommended_review_required"],
            "recommendation_reason": unit["recommendation_reason"],
            "story_completion_score": round(unit["story_completion_score"], 2),
            "thought_closure_score": round(unit["thought_closure_score"], 2),
            "context_before_score": round(unit["context_before_score"], 2),
            "starts_out_of_context": unit["starts_out_of_context"],
            "content_density_score": round(unit["content_density_score"], 2),
            "weak_content": unit["weak_content"],
            "narrative_quality_score": round(unit["narrative_quality_score"], 2),
            "standalone_score": round(unit["standalone_score"], 2),
            "false_full_thought_risk": round(unit["false_full_thought_risk"], 2),
            "reference_alignment_score": round(unit["reference_alignment_score"], 2),
            "tail_padding_applied": unit["tail_padding_applied"],
            "tail_padding_seconds": unit["tail_padding_seconds"],
            "tail_padding_reason": unit["tail_padding_reason"],
            "ends_with_unanswered_question": unit["ends_with_unanswered_question"],
            "feedback_calibration_notes": unit["feedback_calibration_notes"],
            "feedback_similarity_reason": unit["feedback_similarity_reason"],
            "not_recommended_reason": unit["not_recommended_reason"],
            "failed_criteria": unit["failed_criteria"],
            "rejected_by_analyzer": rejected_by_analyzer,
            "non_content_score": round(unit["non_content_score"], 2),
            "rejected_content_reason": unit["rejected_content_reason"],
            "reason_for_duration": unit["reason_for_duration"],
            "ending_type": unit["ending_type"],
            "link": link,
            "suggested_title": "",
            "hashtags": [],
        }

    def _select_diagnostic_units(
        self,
        units: list[dict[str, Any]],
        selected: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        selected_ids = {id(unit) for unit in selected}
        candidates = sorted(
            [unit for unit in units if id(unit) not in selected_ids],
            key=lambda unit: (
                unit["score"],
                unit["narrative_quality_score"],
                unit["standalone_score"],
                unit["story_completion_score"],
                -unit["false_full_thought_risk"],
            ),
            reverse=True,
        )
        diagnostics: list[dict[str, Any]] = []
        for candidate in candidates:
            if candidate["duration"] < self.SHORT_MIN_SECONDS:
                continue
            if any(self._overlap_ratio(candidate, item) > 0.75 for item in diagnostics):
                continue
            diagnostics.append(candidate)
            if len(diagnostics) >= self.DIAGNOSTIC_TOP_N:
                break
        return diagnostics

    def _build_thought_units(
        self,
        segments: list[dict[str, Any]],
        video_duration: float,
        video_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        starts = self._candidate_start_indexes(segments)
        units: list[dict[str, Any]] = []
        for source_rank, start_index in enumerate(starts, start=1):
            for clip_version, target, soft_max, hard_max in (
                ("short", 52, self.SHORT_MAX_SECONDS, self.SHORT_MAX_SECONDS),
                ("full_thought", self.TARGET_SECONDS, self.SOFT_MAX_SECONDS, self.HARD_MAX_SECONDS),
            ):
                unit = self._build_unit_from_start(
                    segments,
                    start_index,
                    video_duration,
                    video_metadata,
                    [source_rank],
                    clip_version=clip_version,
                    target_seconds=target,
                    soft_max_seconds=soft_max,
                    hard_max_seconds=hard_max,
                )
                min_seconds = self.SHORT_MIN_SECONDS if clip_version == "short" else self.MIN_CLIP_SECONDS
                if unit and unit["duration"] >= min_seconds:
                    units.append(unit)

        units.extend(self._merge_hook_and_development(units, segments, video_duration, video_metadata))
        return units

    def _feedback_seed_units(
        self,
        segments: list[dict[str, Any]],
        video_duration: float,
        video_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        video_id = str(video_metadata.get("video_id", ""))
        if not video_id:
            return []
        units: list[dict[str, Any]] = []
        for index, item in enumerate(self.feedback_calibration_service.positive_ranges_for_video(video_id), start=1):
            selected = self._segments_between(segments, item["start"], item["end"])
            if not selected:
                continue
            unit = self._score_unit(
                selected,
                video_duration,
                video_metadata,
                source_ranks=[-index],
                selected_boundary_reason=f"feedback calibration seed: {item['reason']}",
                split_suggestion_seconds=None,
                new_thought_count=0,
                clip_version="full_thought",
                context_expanded=False,
                merged_from=[],
                tail_padding_applied=bool(item["end"] > selected[-1].get("end", item["end"])),
                tail_padding_seconds=0.0,
                tail_padding_reason=f"feedback seed from {item['reason']}",
            )
            unit["feedback_calibration_notes"].append(
                f"feedback: intervalo manual positivo ({item['reason']}, rating={item['rating']})"
            )
            if not unit["rejected_content_reason"] and not unit["ends_with_unanswered_question"]:
                unit["recommended_version"] = True
                unit["recommended_review_required"] = True
                unit["recommendation_reason"] = "recommended from positive manual feedback calibration"
                unit["not_recommended_reason"] = ""
                unit["failed_criteria"] = []
            if item["reason"] in {"otimo_final_curto", "bom_mas_curto", "bom_com_ajuste"}:
                unit["tail_padding_applied"] = True
                if item.get("ideal_end") is not None:
                    unit["tail_padding_seconds"] = round(
                        max(0.0, float(item["ideal_end"]) - float(item["original_end"])),
                        2,
                    )
                unit["tail_padding_reason"] = f"feedback: {item['reason']}"
            units.append(unit)
        return units

    def _candidate_start_indexes(self, segments: list[dict[str, Any]]) -> list[int]:
        starts: list[int] = []
        last_start_time = -999.0
        for index, segment in enumerate(segments):
            text = str(segment.get("text", "")).strip()
            lowered = text.lower()
            start_time = float(segment.get("start", 0.0))
            is_start = (
                index == 0
                or self._is_new_thought_start(text)
                or bool(self._trigger_hits(lowered))
                or "?" in text
            )
            if is_start and start_time - last_start_time >= 18:
                starts.append(index)
                last_start_time = start_time
        return starts

    def _build_unit_from_start(
        self,
        segments: list[dict[str, Any]],
        start_index: int,
        video_duration: float,
        video_metadata: dict[str, Any],
        source_ranks: list[int],
        clip_version: str,
        target_seconds: int,
        soft_max_seconds: int,
        hard_max_seconds: int,
    ) -> dict[str, Any] | None:
        original_start_index = start_index
        start_index = self._expand_start_for_context(segments, start_index)
        start = float(segments[start_index].get("start", 0.0))
        best_end_index = start_index
        best_reason = "hard boundary"
        split_suggestion: float | None = None
        new_thought_count = 0

        for end_index in range(start_index, len(segments)):
            current = segments[start_index : end_index + 1]
            end = float(current[-1].get("end", start))
            duration = end - start
            text = self._segments_text(current)
            next_segment = segments[end_index + 1] if end_index + 1 < len(segments) else None
            next_is_new = bool(next_segment and self._is_new_thought_start(str(next_segment.get("text", ""))))

            if end_index > start_index and next_is_new:
                new_thought_count += 1
                if duration >= self.MIN_CLIP_SECONDS and self._has_complete_thought_ending(text):
                    best_end_index = end_index
                    best_reason = "closed before next thought"
                    split_suggestion = end
                    break

            if duration >= target_seconds and self._has_complete_thought_ending(text):
                best_end_index = end_index
                best_reason = "complete thought near target duration"
                if duration >= soft_max_seconds or next_is_new:
                    break

            if duration >= soft_max_seconds and self._has_complete_thought_ending(text):
                best_end_index = end_index
                best_reason = "complete thought before soft max"
                break

            if duration >= hard_max_seconds:
                best_end_index = self._best_complete_boundary(
                    segments,
                    start_index,
                    end_index,
                    start + target_seconds,
                    start + hard_max_seconds,
                )
                best_reason = "best complete boundary before hard max"
                break

            best_end_index = end_index

        selected = segments[start_index : best_end_index + 1]
        if not selected:
            return None
        unit = self._score_unit(
            selected,
            video_duration,
            video_metadata,
            source_ranks=source_ranks,
            selected_boundary_reason=best_reason,
            split_suggestion_seconds=split_suggestion,
            new_thought_count=new_thought_count,
            clip_version=clip_version,
            context_expanded=start_index != original_start_index,
        )
        padded_unit = self._apply_tail_padding(
            unit,
            segments,
            best_end_index,
            video_duration,
            video_metadata,
            source_ranks=source_ranks,
            selected_boundary_reason=best_reason,
            split_suggestion_seconds=split_suggestion,
            clip_version=clip_version,
            context_expanded=start_index != original_start_index,
            merged_from=None,
        )
        return padded_unit or unit

    def _best_complete_boundary(
        self,
        segments: list[dict[str, Any]],
        start_index: int,
        end_index: int,
        min_end: float,
        max_end: float,
    ) -> int:
        best = end_index
        best_distance = float("inf")
        for index in range(start_index, end_index + 1):
            end = float(segments[index].get("end", 0.0))
            if not (min_end <= end <= max_end):
                continue
            text = self._segments_text(segments[start_index : index + 1])
            if self._has_complete_thought_ending(text):
                distance = abs(end - (min_end + max_end) / 2)
                if distance < best_distance:
                    best = index
                    best_distance = distance
        return best

    def _apply_tail_padding(
        self,
        unit: dict[str, Any],
        all_segments: list[dict[str, Any]],
        end_index: int,
        video_duration: float,
        video_metadata: dict[str, Any],
        source_ranks: list[int],
        selected_boundary_reason: str,
        split_suggestion_seconds: float | None,
        clip_version: str,
        context_expanded: bool,
        merged_from: list[int] | None,
    ) -> dict[str, Any] | None:
        padding = self._tail_padding_seconds(unit)
        if padding <= 0 or end_index >= len(all_segments) - 1:
            return None
        target_end = min(
            unit["end"] + padding,
            unit["start"] + self.HARD_MAX_SECONDS,
            video_duration,
        )
        padded_end_index = end_index
        for index in range(end_index + 1, len(all_segments)):
            padded_end_index = index
            if float(all_segments[index].get("end", 0.0)) >= target_end:
                break
        if padded_end_index <= end_index:
            return None
        selected = self._segments_between(all_segments, unit["start"], float(all_segments[padded_end_index].get("end", unit["end"])))
        if not selected or selected[-1].get("end") == unit["end"]:
            return None
        return self._score_unit(
            selected,
            video_duration,
            video_metadata,
            source_ranks=source_ranks,
            selected_boundary_reason=selected_boundary_reason,
            split_suggestion_seconds=split_suggestion_seconds,
            new_thought_count=0,
            clip_version=clip_version,
            context_expanded=context_expanded,
            merged_from=merged_from,
            tail_padding_applied=True,
            tail_padding_seconds=round(float(selected[-1].get("end", unit["end"])) - unit["end"], 2),
            tail_padding_reason="feedback: bons clipes frequentemente precisam de +5s a +10s no final",
        )

    def _tail_padding_seconds(self, unit: dict[str, Any]) -> int:
        if unit.get("tail_padding_applied"):
            return 0
        if unit.get("ends_with_unanswered_question"):
            return 0
        if unit.get("rejected_content_reason"):
            return 0
        if (
            unit.get("narrative_quality_score", 0) >= 9
            and unit.get("standalone_score", 0) >= 9
            and unit.get("story_completion_score", 0) >= 8
            and unit.get("false_full_thought_risk", 10) <= 3
            and unit.get("ending_type") in {"complete", "new_topic_started"}
            and unit.get("duration", 0) < self.HARD_MAX_SECONDS - 5
        ):
            return self.feedback_calibration.suggested_tail_padding_seconds
        return 0

    def _score_unit(
        self,
        segments: list[dict[str, Any]],
        video_duration: float,
        video_metadata: dict[str, Any],
        source_ranks: list[int],
        selected_boundary_reason: str,
        split_suggestion_seconds: float | None,
        new_thought_count: int,
        clip_version: str,
        context_expanded: bool = False,
        merged_from: list[int] | None = None,
        tail_padding_applied: bool = False,
        tail_padding_seconds: float = 0.0,
        tail_padding_reason: str = "",
    ) -> dict[str, Any]:
        start = float(segments[0].get("start", 0.0))
        end = float(segments[-1].get("end", start))
        duration = max(1.0, end - start)
        text = self._segments_text(segments)
        lowered = text.lower()
        title_lower = str(video_metadata.get("title", "")).lower()
        channel_lower = str(video_metadata.get("channel_name") or video_metadata.get("channel_title") or "").lower()
        words = re.findall(r"\b[\wÀ-ÿ']+\b", text)
        first_sentence = " ".join(words[:15])
        trigger_words = self._trigger_hits(lowered)

        hook_score = self._hook_score(lowered, first_sentence.lower(), trigger_words, title_lower)
        development_score = self._development_score(lowered, duration)
        ending_quality_score = self._ending_quality_score(text)
        context_quality_score = self._context_quality_score(lowered, title_lower, channel_lower)
        has_complete_ending = self._has_complete_thought_ending(text)
        has_development = self._has_development(text)
        weak_development = hook_score >= 3.0 and not has_development
        contains_multiple_thoughts, split_suggestion = self._detect_multiple_thoughts(segments)
        if split_suggestion_seconds is None:
            split_suggestion_seconds = split_suggestion
        is_podcast = self._is_podcast(video_metadata)
        context_before_score, starts_out_of_context = self._context_before_score(text)
        content_density_score, weak_content = self._content_density_score(text)
        non_content_score, rejected_content_reason = self._non_content_score(text)
        ends_with_unanswered_question = self._ends_with_unanswered_question(text)
        story_completion_score = self._story_completion_score(text, duration, has_development)
        thought_closure_score = self._thought_closure_score(text, has_complete_ending)
        narrative_quality_score = self._narrative_quality_score(
            text=text,
            hook_score=hook_score,
            development_score=development_score,
            story_completion_score=story_completion_score,
            thought_closure_score=thought_closure_score,
            context_before_score=context_before_score,
            content_density_score=content_density_score,
            starts_out_of_context=starts_out_of_context,
            weak_content=weak_content,
            contains_multiple_thoughts=contains_multiple_thoughts,
        )
        standalone_score = self._standalone_score(
            text=text,
            context_before_score=context_before_score,
            starts_out_of_context=starts_out_of_context,
            has_development=has_development,
            has_complete_ending=has_complete_ending,
            content_density_score=content_density_score,
        )
        false_full_thought_risk = self._false_full_thought_risk(
            segments=segments,
            text=text,
            starts_out_of_context=starts_out_of_context,
            has_complete_ending=has_complete_ending,
            has_development=has_development,
            contains_multiple_thoughts=contains_multiple_thoughts,
            context_before_score=context_before_score,
            thought_closure_score=thought_closure_score,
        )
        ending_type = self._ending_type(
            has_complete_ending=has_complete_ending,
            selected_boundary_reason=selected_boundary_reason,
            duration=duration,
        )
        reference_alignment_score = self._reference_alignment_score(
            hook_score=hook_score,
            context_before_score=context_before_score,
            story_completion_score=story_completion_score,
            thought_closure_score=thought_closure_score,
            content_density_score=content_density_score,
            non_content_score=non_content_score,
            false_full_thought_risk=false_full_thought_risk,
        )
        (
            recommended_version,
            not_recommended_reason,
            failed_criteria,
            recommended_review_required,
            recommendation_reason,
        ) = self._recommendation(
            duration=duration,
            narrative_quality_score=narrative_quality_score,
            standalone_score=standalone_score,
            story_completion_score=story_completion_score,
            content_density_score=content_density_score,
            false_full_thought_risk=false_full_thought_risk,
            rejected_content_reason=rejected_content_reason,
            contains_multiple_thoughts=contains_multiple_thoughts,
            reference_alignment_score=reference_alignment_score,
            non_content_score=non_content_score,
            is_podcast=is_podcast,
            ends_with_unanswered_question=ends_with_unanswered_question,
        )
        reported_clip_version = (
            "long_candidate"
            if clip_version == "full_thought" and not recommended_version
            else clip_version
        )

        completeness_score = 0.0
        completeness_score += 4.0 if has_complete_ending else 0.0
        completeness_score += 3.0 if has_development else 0.0
        completeness_score += min(2.0, ending_quality_score / 5)
        completeness_score += 1.0 if not contains_multiple_thoughts else -1.0
        completeness_score = max(0.0, min(10.0, completeness_score))

        score = (
            hook_score * 0.18
            + development_score * 0.12
            + ending_quality_score * 0.16
            + context_quality_score * 0.08
            + completeness_score * 0.10
            + story_completion_score * 0.14
            + thought_closure_score * 0.12
            + context_before_score * 0.06
            + content_density_score * 0.14
            + narrative_quality_score * 0.12
            + standalone_score * 0.08
        )
        words_per_second = len(words) / duration
        if words_per_second > 2.5:
            score += 0.8
        if words_per_second < 1.0:
            score -= 0.6
        if weak_development:
            score -= 2.5
        if not has_complete_ending:
            score -= 3.0
        if ending_quality_score < 5:
            score -= 1.5
        if contains_multiple_thoughts:
            score -= 0.8
        if starts_out_of_context:
            score -= 1.4
        if weak_content:
            score -= 2.0
        if narrative_quality_score < 5:
            score -= 2.2
        if standalone_score < 4:
            score -= 1.8
        if false_full_thought_risk > 4:
            score -= (false_full_thought_risk - 4) * 0.7
        if non_content_score >= 4:
            score -= non_content_score * 0.8
        if ends_with_unanswered_question:
            score -= 2.5
        if is_podcast and duration < self.MIN_CLIP_SECONDS and story_completion_score < 8:
            score -= 2.5
        if is_podcast and clip_version == "full_thought":
            score += 0.8
        if not is_podcast and clip_version == "short":
            score += 0.3
        if hook_score < 1.5 and len(trigger_words) == 0:
            score = min(score, 6.2)
        if hook_score < 2.5 and development_score < 4.0:
            score = min(score, 6.8)
        if narrative_quality_score < 5.0 or standalone_score < 4.0:
            score = min(score, 5.8)
        if false_full_thought_risk > 6.0:
            score = min(score, 5.5)
        if not recommended_version:
            score = min(score, 6.6)
        position_ratio = start / max(1.0, video_duration)
        if 0.05 <= position_ratio <= 0.35:
            score += 0.4

        return {
            "start": start,
            "end": end,
            "duration": duration,
            "text": text,
            "score": max(0.0, min(10.0, score)),
            "hook_score": hook_score,
            "development_score": development_score,
            "ending_quality_score": ending_quality_score,
            "context_quality_score": context_quality_score,
            "weak_development": weak_development,
            "has_complete_ending": has_complete_ending,
            "has_development": has_development,
            "completeness_score": completeness_score,
            "contains_multiple_thoughts": contains_multiple_thoughts,
            "split_suggestion_seconds": split_suggestion_seconds,
            "selected_boundary_reason": selected_boundary_reason,
            "boundary_adjustment_reason": selected_boundary_reason,
            "merged_from": merged_from or [],
            "source_ranks": source_ranks,
            "thought_unit_start": start,
            "thought_unit_end": end,
            "first_sentence": first_sentence,
            "trigger_words": trigger_words,
            "words_per_second": words_per_second,
            "clip_version": reported_clip_version,
            "recommended_version": recommended_version,
            "recommended_review_required": recommended_review_required,
            "recommendation_reason": recommendation_reason,
            "story_completion_score": story_completion_score,
            "thought_closure_score": thought_closure_score,
            "context_before_score": context_before_score,
            "starts_out_of_context": starts_out_of_context,
            "content_density_score": content_density_score,
            "weak_content": weak_content,
            "narrative_quality_score": narrative_quality_score,
            "standalone_score": standalone_score,
            "false_full_thought_risk": false_full_thought_risk,
            "reference_alignment_score": reference_alignment_score,
            "not_recommended_reason": not_recommended_reason,
            "failed_criteria": failed_criteria,
            "non_content_score": non_content_score,
            "rejected_content_reason": rejected_content_reason,
            "ends_with_unanswered_question": ends_with_unanswered_question,
            "tail_padding_applied": tail_padding_applied,
            "tail_padding_seconds": tail_padding_seconds,
            "tail_padding_reason": tail_padding_reason,
            "feedback_calibration_notes": self._feedback_calibration_notes(
                rejected_content_reason,
                ends_with_unanswered_question,
                tail_padding_applied,
            ),
            "feedback_similarity_reason": self._feedback_similarity_reason(reference_alignment_score),
            "reason_for_duration": self._reason_for_duration(reported_clip_version, duration, is_podcast),
            "ending_type": ending_type,
            "context_expanded": context_expanded,
        }

    def _merge_hook_and_development(
        self,
        units: list[dict[str, Any]],
        segments: list[dict[str, Any]],
        video_duration: float,
        video_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        ordered = sorted(units, key=lambda unit: unit["start"])
        for left, right in zip(ordered, ordered[1:]):
            gap = right["start"] - left["end"]
            if gap > 8 and self._overlap_ratio(left, right) <= 0.15:
                continue
            if not (left["weak_development"] or right["development_score"] >= left["development_score"]):
                continue
            start = self._best_hook_start(left, right)
            end = right["end"]
            if end - start > self.HARD_MAX_SECONDS:
                start = max(left["start"], end - self.HARD_MAX_SECONDS)
            selected = self._segments_between(segments, start, end)
            if not selected:
                continue
            merged_from = list(dict.fromkeys(left.get("source_ranks", []) + right.get("source_ranks", [])))
            unit = self._score_unit(
                selected,
                video_duration,
                video_metadata,
                source_ranks=merged_from,
                selected_boundary_reason="merged hook with following development",
                split_suggestion_seconds=None,
                new_thought_count=0,
                clip_version="full_thought",
                context_expanded=False,
                merged_from=merged_from,
            )
            end_index = max(
                (
                    index
                    for index, segment in enumerate(segments)
                    if float(segment.get("end", 0.0)) <= unit["end"] + 0.01
                ),
                default=0,
            )
            merged.append(
                self._apply_tail_padding(
                    unit,
                    segments,
                    end_index,
                    video_duration,
                    video_metadata,
                    source_ranks=merged_from,
                    selected_boundary_reason="merged hook with following development",
                    split_suggestion_seconds=None,
                    clip_version="full_thought",
                    context_expanded=False,
                    merged_from=merged_from,
                )
                or unit
            )
        return merged

    def _select_thought_units(self, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidates = sorted(
            units,
            key=lambda unit: (
                unit["recommended_version"],
                unit["narrative_quality_score"],
                unit["standalone_score"],
                -unit["false_full_thought_risk"],
                unit["score"],
                unit["has_complete_ending"],
                unit["has_development"],
                not unit["contains_multiple_thoughts"],
                unit["ending_quality_score"],
                unit["completeness_score"],
            ),
            reverse=True,
        )
        selected: list[dict[str, Any]] = []
        for candidate in candidates:
            if not candidate["recommended_version"]:
                continue
            if candidate["narrative_quality_score"] < 5.0:
                continue
            if candidate["standalone_score"] < 4.0:
                continue
            if candidate["false_full_thought_risk"] > 6.5:
                continue
            if candidate["duration"] < self.MIN_CLIP_SECONDS:
                if candidate["story_completion_score"] < 8.5 or candidate["clip_version"] != "short":
                    continue
            if candidate["duration"] > self.HARD_MAX_SECONDS:
                continue
            if candidate["non_content_score"] >= 6 and candidate["content_density_score"] < 8:
                continue
            if candidate["weak_content"] and any(
                self._same_region(candidate, other) and not other["weak_content"]
                for other in candidates
            ):
                continue
            if not candidate["has_complete_ending"] and any(
                self._same_region(candidate, other) and other["has_complete_ending"]
                for other in candidates
            ):
                continue
            if candidate["weak_development"] and any(
                self._same_region(candidate, other) and other["has_development"]
                for other in candidates
            ):
                continue
            if any(self._overlap_ratio(candidate, item) > 0.50 for item in selected):
                continue
            selected.append(candidate)
            if len(selected) >= 5:
                break
        return selected

    def _expand_start_for_context(self, segments: list[dict[str, Any]], start_index: int) -> int:
        text = str(segments[start_index].get("text", ""))
        _, starts_out = self._context_before_score(text)
        if not starts_out or start_index <= 0:
            return start_index
        original_start = float(segments[start_index].get("start", 0.0))
        best = start_index
        for index in range(start_index - 1, -1, -1):
            start = float(segments[index].get("start", 0.0))
            if original_start - start > 20:
                break
            candidate_text = self._segments_text(segments[index : start_index + 1])
            _, candidate_out = self._context_before_score(candidate_text)
            best = index
            if not candidate_out:
                return index
        return best

    def _has_complete_thought_ending(self, text: str) -> bool:
        clean = re.sub(r"\s+", " ", text).strip()
        if not clean:
            return False
        lowered = clean.lower().strip(" \"'”")
        words = re.findall(r"\b[\wÀ-ÿ']+\b", lowered)
        if len(words) < 8:
            return False
        tail = " ".join(words[-4:])
        if any(tail.endswith(term) or lowered.endswith(term) for term in self.CONTINUATION_ENDINGS):
            return False
        if lowered.endswith((",", ";", ":")):
            return False
        sentences = [sentence.strip() for sentence in re.split(r"[.!?…]+", clean) if sentence.strip()]
        last_sentence = sentences[-1] if sentences else clean
        if len(last_sentence.split()) <= 3:
            return False
        has_punctuation = bool(re.search(r"[.!?…][\"”']?$", clean))
        has_closure = self._has_strong_closure(lowered)
        has_development = self._has_development(clean)
        has_anchor = self._has_subject_anchor(clean)
        if has_closure and has_development:
            return True
        if has_punctuation and has_development and has_anchor and len(words) >= 70:
            return True
        return False

    def _is_new_thought_start(self, text: str) -> bool:
        clean = re.sub(r"\s+", " ", text).strip()
        lowered = clean.lower()
        if not clean:
            return False
        if "?" in clean:
            return True
        if any(lowered.startswith(term) for term in self.THOUGHT_START_TERMS):
            return True
        if any(term in lowered[:140] for term in {"o problema é", "a verdade é", "the problem is", "actually"}):
            return True
        if self._trigger_hits(lowered) and len(clean.split()) >= 6:
            return True
        return False

    def _has_development(self, text: str) -> bool:
        lowered = text.lower()
        hits = sum(1 for term in self.DEVELOPMENT_TERMS if term in lowered)
        sentence_count = len([part for part in re.split(r"[.!?…]+|\s{2,}", text) if len(part.split()) >= 5])
        return hits >= 1 and sentence_count >= 2 or hits >= 2 or len(text.split()) >= 90

    def _detect_multiple_thoughts(
        self,
        segments: list[dict[str, Any]],
    ) -> tuple[bool, float | None]:
        if len(segments) < 4:
            return False, None
        starts: list[float] = []
        base_start = float(segments[0].get("start", 0.0))
        base_end = float(segments[-1].get("end", base_start))
        for segment in segments[1:]:
            start = float(segment.get("start", 0.0))
            if start - base_start < 25:
                continue
            if base_end - start < 12:
                continue
            if self._is_new_thought_start(str(segment.get("text", ""))):
                starts.append(start)
        if not starts:
            return False, None
        return True, starts[0]

    def _context_before_score(self, text: str) -> tuple[float, bool]:
        clean = re.sub(r"\s+", " ", text).strip()
        lowered = clean.lower()
        words = re.findall(r"\b[\wÀ-ÿ']+\b", lowered)
        first = " ".join(words[:4])
        starts_out = any(first.startswith(term) for term in self.OUT_OF_CONTEXT_STARTS)
        has_entity_or_action = any(term in lowered[:260] for term in self.ENTITY_ACTION_TERMS)
        has_question_or_setup = "?" in clean[:180] or any(term in lowered[:220] for term in self.THOUGHT_START_TERMS)
        score = 3.0
        if has_entity_or_action:
            score += 3.0
        if has_question_or_setup:
            score += 2.0
        if starts_out:
            score -= 3.0
        if len(words) >= 20:
            score += 1.0
        return max(0.0, min(10.0, score)), starts_out

    def _content_density_score(self, text: str) -> tuple[float, bool]:
        lowered = text.lower()
        words = re.findall(r"\b[\wÀ-ÿ']+\b", lowered)
        unique_ratio = len(set(words)) / max(1, len(words))
        entity_hits = sum(1 for term in self.ENTITY_ACTION_TERMS if term in lowered)
        dev_hits = sum(1 for term in self.DEVELOPMENT_TERMS if term in lowered)
        repeated_fillers = sum(lowered.count(term) for term in {"né", "tipo", "cara", "assim", "you know", "like"})
        score = 2.0
        score += min(3.0, entity_hits * 0.8)
        score += min(3.0, dev_hits * 0.6)
        if len(words) >= 120:
            score += 1.0
        if unique_ratio < 0.35:
            score -= 1.5
        if repeated_fillers >= 8:
            score -= 1.5
        weak = score < 4.0 or (entity_hits == 0 and dev_hits <= 1)
        return max(0.0, min(10.0, score)), weak

    def _narrative_quality_score(
        self,
        text: str,
        hook_score: float,
        development_score: float,
        story_completion_score: float,
        thought_closure_score: float,
        context_before_score: float,
        content_density_score: float,
        starts_out_of_context: bool,
        weak_content: bool,
        contains_multiple_thoughts: bool,
    ) -> float:
        lowered = text.lower()
        words = re.findall(r"\b[\wÀ-ÿ']+\b", lowered)
        has_setup = any(term in lowered[:320] for term in self.THOUGHT_START_TERMS) or "?" in text[:240]
        has_anchor = self._has_subject_anchor(text)
        has_development = self._has_development(text)
        has_closure = self._has_strong_closure(lowered)
        intelligibility_score = self._intelligibility_score(text)

        score = 0.0
        if hook_score >= 2.0 or has_setup:
            score += 1.5
        if context_before_score >= 5 and has_anchor:
            score += 2.0
        elif context_before_score >= 4:
            score += 1.0
        if has_development and development_score >= 3:
            score += 2.0
        if content_density_score >= 5:
            score += 1.4
        if story_completion_score >= 7:
            score += 1.4
        if thought_closure_score >= 7 and has_closure:
            score += 1.2
        elif thought_closure_score >= 8 and has_anchor:
            score += 0.6
        if len(words) >= 120:
            score += 0.5

        if starts_out_of_context:
            score -= 2.0
        if weak_content:
            score -= 2.0
        if contains_multiple_thoughts:
            score -= 1.0
        if not has_anchor:
            score -= 1.5
        if not has_closure and story_completion_score < 8:
            score -= 1.0
        score -= max(0.0, 6.0 - intelligibility_score) * 0.8
        if not has_closure:
            score = min(score, 6.5)
        if intelligibility_score < 5.0:
            score = min(score, 5.0)
        return max(0.0, min(10.0, score))

    def _standalone_score(
        self,
        text: str,
        context_before_score: float,
        starts_out_of_context: bool,
        has_development: bool,
        has_complete_ending: bool,
        content_density_score: float,
    ) -> float:
        lowered = text.lower()
        words = re.findall(r"\b[\wÀ-ÿ']+\b", lowered)
        first = " ".join(words[:5])
        starts_with_loose_pronoun = any(first.startswith(term) for term in self.OUT_OF_CONTEXT_STARTS)
        has_anchor = self._has_subject_anchor(text)
        has_setup = "?" in text[:240] or any(term in lowered[:260] for term in self.THOUGHT_START_TERMS)
        intelligibility_score = self._intelligibility_score(text)

        score = 2.0
        score += min(2.5, context_before_score * 0.35)
        if has_anchor:
            score += 2.0
        if has_setup:
            score += 1.0
        if has_development:
            score += 1.2
        if has_complete_ending:
            score += 1.0
        if content_density_score >= 5:
            score += 1.0
        if starts_out_of_context or starts_with_loose_pronoun:
            score -= 2.5
        if len(words) < 80:
            score -= 0.8
        score -= max(0.0, 6.0 - intelligibility_score) * 0.7
        if not has_anchor:
            score = min(score, 5.5)
        if intelligibility_score < 5.0:
            score = min(score, 5.0)
        return max(0.0, min(10.0, score))

    def _false_full_thought_risk(
        self,
        segments: list[dict[str, Any]],
        text: str,
        starts_out_of_context: bool,
        has_complete_ending: bool,
        has_development: bool,
        contains_multiple_thoughts: bool,
        context_before_score: float,
        thought_closure_score: float,
    ) -> float:
        lowered = text.lower()
        words = re.findall(r"\b[\wÀ-ÿ']+\b", lowered)
        short_segments = 0
        for segment in segments:
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
            if end - start <= 2.0:
                short_segments += 1
        short_segment_ratio = short_segments / max(1, len(segments))
        first = " ".join(words[:5])

        risk = 0.0
        if short_segment_ratio > 0.45:
            risk += 1.5
        if starts_out_of_context or any(first.startswith(term) for term in self.OUT_OF_CONTEXT_STARTS):
            risk += 2.0
        if not has_complete_ending:
            risk += 2.2
        if not has_development:
            risk += 1.8
        if contains_multiple_thoughts:
            risk += 1.2
        if context_before_score < 4:
            risk += 1.0
        if thought_closure_score < 6:
            risk += 1.2
        if not self._has_strong_closure(lowered):
            risk += 1.6
        if not self._has_subject_anchor(text):
            risk += 1.4
        risk += max(0.0, 6.0 - self._intelligibility_score(text)) * 0.6
        return max(0.0, min(10.0, risk))

    def _recommendation(
        self,
        duration: float,
        narrative_quality_score: float,
        standalone_score: float,
        story_completion_score: float,
        content_density_score: float,
        false_full_thought_risk: float,
        rejected_content_reason: str,
        contains_multiple_thoughts: bool,
        reference_alignment_score: float,
        non_content_score: float,
        is_podcast: bool,
        ends_with_unanswered_question: bool,
    ) -> tuple[bool, str, list[str], bool, str]:
        has_high_editorial_quality = (
            reference_alignment_score >= 8
            and narrative_quality_score >= 8
            and standalone_score >= 8
            and content_density_score >= 5
            and non_content_score == 0
        )
        duration_soft_allowed = (
            duration >= self.SHORT_MIN_SECONDS
            and reference_alignment_score >= 8
            and standalone_score >= 8
            and story_completion_score >= 7
            and content_density_score >= 5
            and non_content_score == 0
        )
        soft_warnings: list[str] = []
        hard_checks = [
            (narrative_quality_score >= 7, "narrative_quality_score below 7"),
            (standalone_score >= 6, "standalone_score below 6"),
            (story_completion_score >= 7, "story_completion_score below 7"),
            (content_density_score >= 5, "content_density_score below 5"),
            (false_full_thought_risk <= 4, "false_full_thought_risk above 4"),
            (not rejected_content_reason, "non-content/merchan detected"),
            (not ends_with_unanswered_question, "ends with unanswered question"),
        ]

        if duration < 60:
            soft_warnings.append("duration below 60s")
            if not duration_soft_allowed:
                hard_checks.append((False, "duration below 60s"))
        if contains_multiple_thoughts:
            soft_warnings.append("contains multiple thoughts")
            if not has_high_editorial_quality:
                hard_checks.append((False, "contains multiple thoughts"))
        if is_podcast and duration < 60:
            soft_warnings.append("short podcast candidate")

        failed = [reason for passed, reason in hard_checks if not passed]
        if failed:
            return False, "; ".join(failed[:3]), failed, False, ""
        if soft_warnings:
            reason = "recommended despite soft warnings because reference alignment is high"
            return True, "", soft_warnings, True, reason
        return True, "", [], False, ""

    @staticmethod
    def _reference_alignment_score(
        hook_score: float,
        context_before_score: float,
        story_completion_score: float,
        thought_closure_score: float,
        content_density_score: float,
        non_content_score: float,
        false_full_thought_risk: float,
    ) -> float:
        score = (
            hook_score * 0.18
            + context_before_score * 0.16
            + story_completion_score * 0.22
            + thought_closure_score * 0.18
            + content_density_score * 0.18
            + max(0.0, 10.0 - false_full_thought_risk) * 0.08
        )
        if non_content_score > 0:
            score -= min(4.0, non_content_score * 0.7)
        return max(0.0, min(10.0, score))

    @staticmethod
    def _ends_with_unanswered_question(text: str) -> bool:
        clean = re.sub(r"\s+", " ", text).strip()
        lowered = clean.lower()
        tail = lowered[-260:]
        question_terms = {
            "e você", "mas me fala", "como é", "por que", "porque",
            "qual", "o que você acha", "o que voce acha", "me explica",
            "conta pra gente", "como foi",
        }
        if clean.endswith("?") and not re.search(r"\?.{20,}[.!]", clean[-220:]):
            return True
        if any(term in tail for term in question_terms):
            question_pos = max(tail.rfind(term) for term in question_terms if term in tail)
            after = tail[question_pos:]
            if len(after.split()) < 12:
                return True
        return False

    @staticmethod
    def _feedback_similarity_reason(reference_alignment_score: float) -> str:
        if reference_alignment_score >= 8:
            return "alto alinhamento com benchmark de cortes bons"
        if reference_alignment_score >= 6:
            return "alinhamento moderado com benchmark de cortes bons"
        return "baixo alinhamento com benchmark de cortes bons"

    @staticmethod
    def _feedback_calibration_notes(
        rejected_content_reason: str,
        ends_with_unanswered_question: bool,
        tail_padding_applied: bool,
    ) -> list[str]:
        notes: list[str] = []
        if rejected_content_reason == "propaganda_produto":
            notes.append("feedback: propaganda/produto deve cair forte")
        if ends_with_unanswered_question:
            notes.append("feedback: pergunta sem resposta deve ser penalizada")
        if tail_padding_applied:
            notes.append("feedback: clipes bons frequentemente precisam de +5s a +10s no final")
        return notes

    def _has_subject_anchor(self, text: str) -> bool:
        lowered = text.lower()
        if any(term in lowered for term in self.ENTITY_ACTION_TERMS):
            return True
        capitalized = re.findall(r"\b[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ']+(?:\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ']+){0,3}\b", text)
        useful = [
            item
            for item in capitalized
            if item.lower() not in {"Eu", "Você", "Aí", "Então", "Porque", "Isso", "Cara"}
        ]
        return bool(useful)

    def _has_strong_closure(self, lowered_text: str) -> bool:
        tail = lowered_text[-220:]
        tail = tail.replace("é isso que", "").replace("e isso que", "")
        strong_terms = self.CONCLUSION_TERMS - self.WEAK_CONCLUSION_TERMS
        return any(re.search(rf"\b{re.escape(term)}\b", tail) for term in strong_terms)

    @staticmethod
    def _intelligibility_score(text: str) -> float:
        words = re.findall(r"\b[\wÀ-ÿ']+\b", text)
        if not words:
            return 0.0
        non_latin = re.findall(r"[^\w\sÀ-ÿ.,!?;:'\"()\-]", text)
        short_words = [word for word in words if len(word) <= 2]
        odd_tokens = [
            word
            for word in words
            if re.search(r"[^\x00-\x7FÀ-ÿ]", word) or len(re.findall(r"[aeiouáàâãéêíóôõú]", word.lower())) == 0 and len(word) > 5
        ]
        score = 10.0
        score -= min(4.0, len(non_latin) / max(1, len(text)) * 120)
        score -= min(2.5, len(short_words) / max(1, len(words)) * 5)
        score -= min(3.0, len(odd_tokens) * 0.8)
        return max(0.0, min(10.0, score))

    def _non_content_score(self, text: str) -> tuple[float, str]:
        lowered = text.lower()
        hits = [term for term in self.NON_CONTENT_TERMS if term in lowered]
        if not hits:
            return 0.0, ""
        if any(term in lowered for term in self.PRODUCT_TERMS):
            return 9.0, "propaganda_produto"
        score = min(10.0, 2.5 + len(hits) * 1.5)
        return score, ", ".join(hits[:5])

    def _story_completion_score(self, text: str, duration: float, has_development: bool) -> float:
        lowered = text.lower()
        score = 0.0
        if has_development:
            score += 4.0
        if self._has_complete_thought_ending(text):
            score += 3.0
        if self._has_strong_closure(lowered):
            score += 1.5
        if duration >= self.FULL_MIN_SECONDS:
            score += 1.0
        if duration > self.HARD_MAX_SECONDS:
            score -= 1.0
        return max(0.0, min(10.0, score))

    def _thought_closure_score(self, text: str, has_complete_ending: bool) -> float:
        if not has_complete_ending:
            return 1.0 if self._has_development(text) else 0.0
        score = 7.0
        lowered = text.lower()
        if self._has_strong_closure(lowered):
            score += 2.0
        if re.search(r"[.!?…][\"”']?$", text.strip()):
            score += 1.0
        return min(10.0, score)

    def _ending_type(self, has_complete_ending: bool, selected_boundary_reason: str, duration: float) -> str:
        if has_complete_ending and "next thought" in selected_boundary_reason:
            return "new_topic_started"
        if has_complete_ending:
            return "complete"
        if duration >= self.HARD_MAX_SECONDS - 1:
            return "cut_by_limit"
        return "incomplete"

    def _reason_for_duration(self, clip_version: str, duration: float, is_podcast: bool) -> str:
        if clip_version == "full_thought":
            if duration >= self.FULL_MIN_SECONDS:
                return "full thought for podcast/interview" if is_podcast else "full thought"
            return "shorter full thought because idea closed early"
        if clip_version == "long_candidate":
            return "long candidate kept for review, but narrative quality did not prove a full thought"
        return "short version for concise hook"

    @staticmethod
    def _is_podcast(video_metadata: dict[str, Any]) -> bool:
        text = f"{video_metadata.get('title', '')} {video_metadata.get('channel_name', '')} {video_metadata.get('channel_title', '')}".lower()
        return any(
            term in text
            for term in {
                "podcast", "entrevista", "ticaracaticast", "flow", "podpah",
                "inteligência ltda", "inteligencia ltda", "papo de elite",
                "oestecast", "venus podcast", "the noite",
            }
        )

    def _hook_score(
        self,
        text_lower: str,
        first_sentence_lower: str,
        trigger_words: list[str],
        title_lower: str,
    ) -> float:
        score = min(4.0, len(trigger_words) * 0.9)
        if any(trigger in first_sentence_lower for trigger in self._all_triggers()):
            score += 1.6
        if any(trigger in title_lower for trigger in self._all_triggers()):
            score += 0.8
        if "?" in first_sentence_lower:
            score += 0.6
        return min(10.0, score)

    def _development_score(self, text_lower: str, duration: float) -> float:
        hits = sum(1 for term in self.DEVELOPMENT_TERMS if term in text_lower)
        score = min(5.0, hits * 0.9)
        if len(text_lower.split()) >= 90:
            score += 1.5
        if duration >= self.TARGET_SECONDS:
            score += 1.0
        if self._has_strong_closure(text_lower):
            score += 1.0
        return min(10.0, score)

    def _ending_quality_score(self, text: str) -> float:
        if not self._has_complete_thought_ending(text):
            return 2.0 if self._has_development(text) else 0.0
        lowered = text.lower()
        score = 7.0
        if self._has_strong_closure(lowered):
            score += 1.5
        if re.search(r"[.!?…][\"”']?$", text.strip()):
            score += 1.0
        if self._has_development(text):
            score += 0.5
        return min(10.0, score)

    def _context_quality_score(self, text_lower: str, title_lower: str, channel_lower: str) -> float:
        score = 0.0
        if any(term in text_lower for term in {"quem", "onde", "quando", "como", "why", "how", "when", "where"}):
            score += 1.0
        if any(term in text_lower for term in self.DEVELOPMENT_TERMS):
            score += 1.2
        if "podcast" in title_lower or "podcast" in channel_lower:
            score += 0.8
        if len(text_lower.split()) >= 80:
            score += 1.0
        return min(10.0, score)

    def _trigger_hits(self, text: str) -> list[str]:
        hits: list[str] = []
        for trigger in self._all_triggers():
            if trigger in text and trigger not in hits:
                hits.append(trigger)
        return hits

    def _all_triggers(self) -> set[str]:
        return self.HOOK_TRIGGERS_PT | self.HOOK_TRIGGERS_EN

    @staticmethod
    def _segments_between(
        segments: list[dict[str, Any]],
        start: float,
        end: float,
    ) -> list[dict[str, Any]]:
        return [
            segment
            for segment in segments
            if float(segment.get("end", 0.0)) > start
            and float(segment.get("start", 0.0)) < end
        ]

    @staticmethod
    def _segments_text(segments: list[dict[str, Any]]) -> str:
        text = " ".join(str(segment.get("text", "")).strip() for segment in segments)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
        start = max(left["start"], right["start"])
        end = min(left["end"], right["end"])
        overlap = max(0.0, end - start)
        return overlap / max(1.0, min(left.get("duration", 1.0), right.get("duration", 1.0)))

    @staticmethod
    def _same_region(left: dict[str, Any], right: dict[str, Any]) -> bool:
        return abs(left["start"] - right["start"]) < 30 or ClipAnalyzerService._overlap_ratio(left, right) > 0.30

    @staticmethod
    def _best_hook_start(left: dict[str, Any], right: dict[str, Any]) -> float:
        return left["start"] if left.get("hook_score", 0) >= right.get("hook_score", 0) else right["start"]
