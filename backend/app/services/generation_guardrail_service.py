from __future__ import annotations

from typing import Any


SENSITIVE_NICHES = {"politica", "política", "saude", "saúde", "true crime", "crime"}


def analyze_generation_project(project: dict[str, Any]) -> dict[str, Any]:
    niche = str(project.get("niche") or "").strip().lower()
    fact_notes = _string_list(project.get("fact_check_notes"))
    visual_context = _string_list(project.get("visual_context"))
    visual_items = [item for item in project.get("visual_items") or [] if isinstance(item, dict)]
    voice_status = str(project.get("voice_status") or "")
    quality_tier = str(project.get("script_quality_tier") or "")
    depth_score = _number(project.get("depth_score"))
    narrative_score = _number(project.get("narrative_score"))
    source_urls = _string_list(project.get("source_urls"))
    claim_pairs = project.get("claim_evidence_pairs") if isinstance(project.get("claim_evidence_pairs"), list) else []
    grounding_used = bool(project.get("grounding_used"))
    confidence = str(
        project.get("factual_grounding_confidence")
        or project.get("research_brief", {}).get("confidence")
        or ""
    ).lower()
    risks: list[str] = []
    platform_notes: list[str] = []

    factual_claims = _has_factual_claims(project)
    fact_check_required = bool(fact_notes) or niche in SENSITIVE_NICHES
    if factual_claims and (not grounding_used or not source_urls or confidence == "low"):
        fact_check_required = True
    claims_without_evidence = [
        item for item in claim_pairs if isinstance(item, dict) and (item.get("needs_fact_check") or not item.get("evidence"))
    ]
    if claims_without_evidence:
        fact_check_required = True
    copyright_review_required = not visual_context
    restricted_visuals = [item for item in visual_items if str(item.get("license_lane") or "") == "restricted"]
    unknown_manual_visuals = [
        item
        for item in visual_items
        if str(item.get("source") or "") == "manual"
        and str(item.get("license_lane") or "") in {"", "unknown", "review"}
    ]
    review_visuals = [
        item
        for item in visual_items
        if str(item.get("license_lane") or "") == "review" or str(item.get("type") or "") == "screenshot"
    ]
    if restricted_visuals or unknown_manual_visuals or review_visuals:
        copyright_review_required = True
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
    if factual_claims and not grounding_used:
        risks.append("ungrounded_factual_claims")
        platform_notes.append("Roteiro tem afirmações factuais sem grounding externo.")
    if factual_claims and not source_urls:
        risks.append("missing_sources")
        platform_notes.append("Sem fontes registradas; revisão humana recomendada antes de publicar.")
    if confidence == "low":
        risks.append("low_factual_confidence")
        platform_notes.append("Confiança factual baixa; confirme fatos fortes antes de avançar.")
    if quality_tier in {"weak", "reject"}:
        risks.append("script_quality_low")
        platform_notes.append("Melhore hook, ritmo e especificidade antes de renderizar.")
    if restricted_visuals:
        risks.append("restricted_visual_asset")
        platform_notes.append("Há item visual restrito; substitua por asset próprio ou stock seguro.")
    if unknown_manual_visuals:
        risks.append("unknown_visual_license")
        platform_notes.append("Itens manuais precisam de licença/crédito antes do render.")
    if review_visuals:
        risks.append("visual_copyright_review_required")
        platform_notes.append("Revise direitos de imagem dos itens visuais antes de renderizar.")
    if claims_without_evidence:
        risks.append("claim_without_evidence")
        platform_notes.append("Algumas afirmações não têm evidência ligada; revise antes de publicar.")
    if _interpretation_presented_as_fact(project):
        risks.append("interpretation_presented_as_fact")
        platform_notes.append("Há interpretação com tom factual forte; ajuste ou confirme evidência.")
    if depth_score and depth_score < 5.5:
        risks.append("low_depth_score")
        platform_notes.append("Roteiro pode estar raso; melhore contexto e consequência.")
    if narrative_score and narrative_score < 5.5:
        risks.append("low_narrative_score")
        platform_notes.append("Estrutura narrativa fraca; revise conflito, virada e fechamento.")

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


def _has_factual_claims(project: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(project.get("hook") or ""),
            *[str(item or "") for item in project.get("script_lines") or []],
        ]
    ).lower()
    markers = ["2014", "7x1", "semifinal", "quartas", "lesão", "lesao", "placar", "colômbia", "colombia", "alemanha"]
    return any(marker in text for marker in markers)


def _interpretation_presented_as_fact(project: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(project.get("hook") or ""),
            *[str(item or "") for item in project.get("script_lines") or []],
        ]
    ).lower()
    strong_markers = ["provou que", "causou sozinho", "com certeza", "foi o único motivo", "foi o unico motivo"]
    return any(marker in text for marker in strong_markers)


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
