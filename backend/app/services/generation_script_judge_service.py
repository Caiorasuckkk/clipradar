"""LLM-as-judge orchestration for generation scripts (Fase 2).

Scores a finished script with one cheap LLM call and, when the script is weak,
rewrites it with the critique and keeps the best version. When the judge is
available its verdict becomes the authoritative quality score; the regex/heuristic
scorer is preserved only as advisory metadata.
"""
from __future__ import annotations

from typing import Any, Callable

from app import config
from app.services.generation_llm_provider_service import judge_script


def evaluate_and_improve(
    payload: dict[str, Any],
    regenerate: Callable[[str], dict[str, Any]] | None = None,
    provider_override: str = "auto",
) -> dict[str, Any]:
    """Judge ``payload``; optionally rewrite weak scripts. Returns the best payload.

    ``regenerate(critique)`` must return a freshly finalized script payload built
    with the given critique. If the judge is unavailable the payload is returned
    unchanged (heuristic score stays in place).
    """
    verdict = judge_script(payload, provider_override=provider_override)
    if not verdict:
        payload["judge_used"] = False
        return payload

    best = _apply_verdict(payload, verdict)
    rewrites = 0
    max_rewrites = max(0, int(config.GENERATION_MAX_SCRIPT_REWRITES))
    threshold = float(config.GENERATION_JUDGE_REWRITE_THRESHOLD)
    # Keep rewriting toward the threshold (judge scores vary, so a fresh attempt
    # can clear the bar even when the previous one didn't). Always keep the best.
    while (
        regenerate is not None
        and rewrites < max_rewrites
        and float(best.get("judge_overall") or 0.0) < threshold
    ):
        critique = _rewrite_brief(best)
        try:
            candidate = regenerate(critique)
        except Exception:
            break
        rewrites += 1
        candidate_verdict = judge_script(candidate, provider_override=provider_override)
        if not candidate_verdict:
            break
        candidate = _apply_verdict(candidate, candidate_verdict)
        if float(candidate.get("judge_overall") or 0.0) > float(best.get("judge_overall") or 0.0):
            best = candidate

    best["judge_rewrites_applied"] = rewrites
    return best


def _apply_verdict(payload: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    # Preserve the heuristic score as advisory only.
    payload["script_quality_score_heuristic"] = payload.get("script_quality_score")
    payload["script_quality_tier_heuristic"] = payload.get("script_quality_tier")

    payload["judge_used"] = True
    payload["judge_overall"] = verdict["overall"]
    payload["judge_hook_score"] = verdict["hook_score"]
    payload["judge_retention_score"] = verdict["retention_score"]
    payload["judge_specificity_score"] = verdict["specificity_score"]
    payload["judge_naturalness_score"] = verdict["naturalness_score"]
    payload["judge_tier"] = verdict["tier"]
    payload["judge_verdict"] = verdict["verdict"]
    payload["judge_strengths"] = verdict["strengths"]
    payload["judge_weaknesses"] = verdict["weaknesses"]
    payload["judge_critique"] = verdict["critique"]
    payload["judge_suggested_hook"] = verdict["suggested_hook"]
    payload["judge_model"] = verdict["model"]

    # The judge is the authoritative quality verdict when it ran.
    payload["script_quality_score"] = verdict["overall"]
    payload["script_quality_tier"] = verdict["tier"]
    return payload


def _rewrite_brief(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    critique = str(payload.get("judge_critique") or "").strip()
    if critique:
        parts.append(critique)
    weaknesses = [str(item).strip() for item in payload.get("judge_weaknesses") or [] if str(item).strip()]
    if weaknesses:
        parts.append("Pontos fracos a corrigir: " + "; ".join(weaknesses))
    suggested_hook = str(payload.get("judge_suggested_hook") or "").strip()
    if suggested_hook:
        parts.append(f"Sugestão de hook mais forte: {suggested_hook}")
    return "\n".join(parts)
