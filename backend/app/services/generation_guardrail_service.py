from __future__ import annotations

from typing import Any


SENSITIVE_NICHES = {"politica", "política", "saude", "saúde", "true crime", "crime"}


def analyze_generation_project(project: dict[str, Any]) -> dict[str, Any]:
    niche = str(project.get("niche") or "").strip().lower()
    fact_notes = _string_list(project.get("fact_check_notes"))
    visual_context = _string_list(project.get("visual_context"))
    voice_status = str(project.get("voice_status") or "")
    quality_tier = str(project.get("script_quality_tier") or "")
    risks: list[str] = []
    platform_notes: list[str] = []

    fact_check_required = bool(fact_notes) or niche in SENSITIVE_NICHES
    copyright_review_required = not visual_context
    disclosure_recommended = voice_status == "ready" or str(project.get("voice_provider") or "")

    if fact_check_required:
        risks.append("fact_check_required")
        platform_notes.append("Revise fatos sensíveis antes de gravar/renderizar.")
    if copyright_review_required:
        risks.append("visual_context_missing")
        platform_notes.append("Defina b-roll/visual sem usar rosto, marca ou obra sem licença.")
    if disclosure_recommended:
        risks.append("ai_voice_disclosure_recommended")
        platform_notes.append("Considere disclosure de voz sintética quando aplicável.")
    if quality_tier in {"weak", "reject"}:
        risks.append("script_quality_low")
        platform_notes.append("Melhore hook, ritmo e especificidade antes de renderizar.")

    status = "review"
    if not risks:
        status = "pass"
    elif len(risks) >= 3 or quality_tier == "reject":
        status = "high_risk"

    return {
        "guardrail_status": status,
        "guardrail_risks": risks,
        "disclosure_recommended": bool(disclosure_recommended),
        "fact_check_required": bool(fact_check_required),
        "copyright_review_required": bool(copyright_review_required),
        "platform_notes": platform_notes,
    }


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []
