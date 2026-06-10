from __future__ import annotations

import re
from typing import Any

from app.services.generation_factual_grounding_service import validate_specificity


GENERIC_TERMS = {
    "muita gente",
    "isso e importante",
    "isso é importante",
    "de forma simples",
    "coisas",
    "algo",
    "varias coisas",
    "várias coisas",
}

META_SCRIPT_PATTERNS = [
    "o tema parece",
    "o ponto que prende atenção",
    "o ponto que prende atencao",
    "a virada é",
    "a virada e",
    "use uma imagem",
    "feche com",
    "mostre",
    "explique",
    "fale sobre",
    "o roteiro deve",
    "a ideia é",
    "a ideia e",
    "esse tipo de detalhe funciona",
    "cria contexto rápido",
    "cria contexto rapido",
    "sem encher a tela",
    "cite no roteiro",
    "substitua este trecho",
]


def validate_script_is_narration(script_lines: object) -> dict[str, Any]:
    lines = _string_list(script_lines)
    meta_hits: list[str] = []
    instructional_hits: list[str] = []
    for line in lines:
        normalized = _strip_accents(line.lower())
        for pattern in META_SCRIPT_PATTERNS:
            normalized_pattern = _strip_accents(pattern.lower())
            if normalized_pattern in normalized:
                meta_hits.append(pattern)
                if _is_instruction_pattern(normalized_pattern):
                    instructional_hits.append(pattern)
    narration_like_count = sum(1 for line in lines if _looks_like_direct_narration(line))
    return {
        "is_narration_ready": bool(lines) and not meta_hits and narration_like_count >= max(2, len(lines) // 2),
        "meta_hits": list(dict.fromkeys(meta_hits)),
        "instructional_hits": list(dict.fromkeys(instructional_hits)),
        "narration_like_count": narration_like_count,
        "line_count": len(lines),
    }


def score_generation_script(payload: dict[str, Any]) -> dict[str, Any]:
    title = _clean(payload.get("title"))
    hook = _clean(payload.get("hook"))
    lines = _string_list(payload.get("script_lines"))
    cta = _clean(payload.get("cta"))
    hashtags = _string_list(payload.get("hashtags"))
    visual_context = _string_list(payload.get("visual_context"))
    fact_check_notes = _string_list(payload.get("fact_check_notes"))
    factual_brief = payload.get("factual_brief") if isinstance(payload.get("factual_brief"), dict) else {}
    estimated_duration = _number(
        payload.get("estimated_duration_seconds") or payload.get("duration_seconds")
    )
    narration_validation = validate_script_is_narration(lines)
    specificity = validate_specificity(
        script_lines=lines,
        factual_brief=factual_brief,
        topic=str(payload.get("topic") or payload.get("title") or ""),
    )

    score = 4.0
    positive: list[str] = []
    negative: list[str] = []

    if 12 <= len(title) <= 90:
        score += 0.8
        positive.append("titulo_especifico")
    else:
        score -= 0.6
        negative.append("titulo_curto_ou_longo")

    if len(hook) >= 20 and _has_hook_trigger(hook):
        score += 1.1
        positive.extend(["hook_com_curiosidade", "clear_hook"])
    elif hook:
        score += 0.3
        negative.extend(["hook_pouco_forte", "weak_hook"])
    else:
        score -= 1.2
        negative.append("hook_ausente")

    if 4 <= len(lines) <= 10:
        score += 0.9
        positive.append("estrutura_curta")
    else:
        score -= 0.8
        negative.append("quantidade_de_linhas_fora_do_ideal")

    if lines:
        avg_line = sum(len(line) for line in lines) / max(1, len(lines))
        if avg_line <= 150 and max(len(line) for line in lines) <= 220:
            score += 0.8
            positive.extend(["frases_narraveis", "direct_speech"])
        else:
            score -= 0.9
            negative.append("frases_longas")
    else:
        score -= 1.4
        negative.append("not_narration_ready")

    if narration_validation["is_narration_ready"]:
        score += 1.2
        positive.append("narration_ready")
    else:
        score -= 1.8
        negative.append("not_narration_ready")

    if narration_validation["meta_hits"]:
        score -= 3.5
        negative.append("meta_script_detected")

    if narration_validation["instructional_hits"]:
        score -= 2.0
        negative.append("instructional_language")

    if _has_contrast(lines + [hook]):
        score += 0.8
        positive.append("contraste_ou_virada")
    else:
        negative.append("falta_virada")

    if cta:
        score += 0.5
        positive.append("cta_presente")
    else:
        score -= 0.4
        negative.append("cta_ausente")

    if hashtags:
        score += 0.3
    else:
        negative.append("hashtags_ausentes")

    if visual_context:
        score += 0.6
        positive.extend(["contexto_visual_presente", "visual_context_separated"])
    else:
        score -= 0.5
        negative.append("contexto_visual_ausente")

    if 20 <= estimated_duration <= 90:
        score += 0.5
        positive.append("duracao_provavel_boa")
    elif estimated_duration:
        score -= 0.4
        negative.append("duracao_fora_do_ideal")

    if _contains_fact_check_marker(lines + [hook]):
        if fact_check_notes:
            score += 0.2
            positive.append("fact_check_marcado")
        else:
            score -= 0.8
            negative.append("fact_check_sem_notas")

    generic_hits = _generic_hits(" ".join([title, hook, *lines]).lower())
    if generic_hits:
        score -= min(1.2, 0.35 * len(generic_hits))
        negative.extend(f"generico_{item.replace(' ', '_')}" for item in generic_hits[:3])

    if lines and lines[-1].strip().endswith("?"):
        score += 0.4
        positive.append("strong_closing_question")

    if factual_brief:
        if "factual_grounding_used" in specificity["positive_signals"]:
            score += 1.0
        if "specific_entities_present" in specificity["positive_signals"]:
            score += 0.8
        if "concrete_conflict" in specificity["positive_signals"]:
            score += 0.5
        if "concrete_consequence" in specificity["positive_signals"]:
            score += 0.5
        if "generic_script_detected" in specificity["negative_signals"]:
            score -= 2.5
        if "missing_key_entities" in specificity["negative_signals"]:
            score -= 1.4
        if "no_specific_facts" in specificity["negative_signals"]:
            score -= 1.4
        if "abstract_language_overuse" in specificity["negative_signals"]:
            score -= 1.0
        if "factual_brief_not_used" in specificity["negative_signals"]:
            score -= 1.6
        positive.extend(specificity["positive_signals"])
        negative.extend(specificity["negative_signals"])

    score = max(0.0, min(10.0, round(score, 1)))
    if narration_validation["meta_hits"]:
        score = min(score, 4.9)
    if factual_brief and any(
        signal in specificity["negative_signals"]
        for signal in ["generic_script_detected", "missing_key_entities", "no_specific_facts", "factual_brief_not_used"]
    ):
        score = min(score, 6.4)
    tier = _tier(score)
    reject_reason = ""
    if tier in {"weak", "reject"}:
        reject_reason = ", ".join(negative[:3]) or "roteiro_fraco"

    return {
        "script_quality_score": score,
        "script_quality_tier": tier,
        "script_positive_signals": list(dict.fromkeys(positive)),
        "script_negative_signals": list(dict.fromkeys(negative)),
        "script_reject_reason": reject_reason,
    }


def _tier(score: float) -> str:
    if score >= 8.0:
        return "excellent"
    if score >= 6.5:
        return "good"
    if score >= 5.0:
        return "average"
    if score >= 3.5:
        return "weak"
    return "reject"


def _has_hook_trigger(text: str) -> bool:
    lowered = text.lower()
    triggers = [
        "?",
        "pouca gente",
        "ninguém",
        "segredo",
        "erro",
        "detalhe",
        "verdade",
        "isso muda",
        "por que",
        "porque",
    ]
    return any(trigger in lowered for trigger in triggers)


def _has_contrast(lines: list[str]) -> bool:
    text = " ".join(lines).lower()
    markers = ["mas", "só que", "porém", "na verdade", "o detalhe", "contraste"]
    return any(marker in text for marker in markers)


def _contains_fact_check_marker(lines: list[str]) -> bool:
    text = " ".join(lines).lower()
    return "[fact-check]" in text or "segundo " in text or "dados" in text


def _generic_hits(text: str) -> list[str]:
    normalized = _strip_accents(text)
    return [term for term in GENERIC_TERMS if _strip_accents(term) in normalized]


def _is_instruction_pattern(pattern: str) -> bool:
    return any(
        marker in pattern
        for marker in ["use", "mostre", "explique", "fale", "deve", "feche", "substitua", "cite"]
    )


def _looks_like_direct_narration(line: str) -> bool:
    text = _clean(line)
    if len(text) < 12:
        return False
    normalized = _strip_accents(text.lower())
    if any(_strip_accents(pattern.lower()) in normalized for pattern in META_SCRIPT_PATTERNS):
        return False
    return not normalized.startswith(("use ", "mostre ", "explique ", "fale ", "feche "))


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    if not text:
        return []
    return [_clean(item) for item in re.split(r"[,;\n]+", text) if _clean(item)]


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strip_accents(value: str) -> str:
    table = str.maketrans("áàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ", "aaaaeeioooucAAAAEEIOOOUC")
    return value.translate(table)
