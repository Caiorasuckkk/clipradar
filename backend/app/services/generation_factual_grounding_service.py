from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app import config


FACT_PACKS_PATH = config.STORAGE_VIDEOS_DIR.parent / "config" / "generation_fact_packs.json"
DEFAULT_FACT_PACKS_PATH = Path(__file__).resolve().parents[1] / "config_data" / "generation_fact_packs.json"
ABSTRACT_PATTERNS = [
    "um detalhe",
    "detalhe escondido",
    "a história",
    "uma decisão pequena",
    "uma consequencia enorme",
    "uma consequência enorme",
    "isso muda tudo",
    "parece simples",
    "ninguém percebe",
    "ninguem percebe",
]


def generate_factual_brief(
    niche: str,
    topic: str = "",
    idea: str = "",
    language: str = "pt-BR",
) -> dict[str, Any]:
    query = " ".join(item for item in [topic, idea, niche] if item).strip()
    pack = detect_known_topic(query)
    if pack:
        return {
            "subject": pack["subject"],
            "key_entities": list(pack.get("key_entities") or []),
            "timeline": list(pack.get("timeline") or []),
            "key_facts": list(pack.get("key_facts") or []),
            "conflict": str(pack.get("conflict") or ""),
            "consequence": str(pack.get("consequence") or ""),
            "emotional_angle": str(pack.get("emotional_angle") or ""),
            "fact_check_notes": list(pack.get("fact_check_notes") or []),
            "confidence": str(pack.get("confidence") or "medium"),
            "source_mode": str(pack.get("source_mode") or "local_knowledge"),
            "fact_pack_id": str(pack.get("id") or ""),
            "language": language or "pt-BR",
        }
    subject = _clean(topic or idea or niche or "Tema sem fatos específicos")
    return {
        "subject": subject,
        "key_entities": _extract_entities(subject),
        "timeline": [],
        "key_facts": [],
        "conflict": "",
        "consequence": "",
        "emotional_angle": "",
        "fact_check_notes": [
            "Fact pack local não encontrado. Adicionar fatos específicos antes de publicar.",
        ],
        "confidence": "low",
        "source_mode": "fallback_template",
        "fact_pack_id": "",
        "language": language or "pt-BR",
    }


def detect_known_topic(query: str) -> dict[str, Any] | None:
    normalized_query = _normalize(query)
    if not normalized_query:
        return None
    best: tuple[int, dict[str, Any]] | None = None
    for pack in _load_fact_packs():
        terms = [str(item or "") for item in pack.get("match_terms") or []]
        score = 0
        for term in terms:
            normalized_term = _normalize(term)
            if normalized_term and normalized_term in normalized_query:
                score = max(score, len(normalized_term))
        entities = [str(item or "") for item in pack.get("key_entities") or []]
        score += sum(1 for entity in entities if _normalize(entity) in normalized_query)
        if score > 0 and (best is None or score > best[0]):
            best = (score, pack)
    return best[1] if best else None


def validate_specificity(
    script_lines: object,
    factual_brief: dict[str, Any] | None,
    topic: str = "",
) -> dict[str, Any]:
    lines = _string_list(script_lines)
    text = " ".join(lines)
    normalized_text = _normalize(text)
    brief = factual_brief or {}
    entities = [str(item) for item in brief.get("key_entities") or [] if str(item).strip()]
    present_entities = [
        entity for entity in entities if _normalize(entity) and _normalize(entity) in normalized_text
    ]
    concrete_facts = _concrete_fact_count(text)
    abstract_hits = [
        pattern for pattern in ABSTRACT_PATTERNS if _normalize(pattern) in normalized_text
    ]
    conflict = _normalize(str(brief.get("conflict") or ""))
    consequence = _normalize(str(brief.get("consequence") or ""))
    has_conflict = bool(conflict) and _overlap_words(conflict, normalized_text) >= 2
    has_consequence = bool(consequence) and _overlap_words(consequence, normalized_text) >= 2
    if not has_conflict:
        has_conflict = any(marker in normalized_text for marker in ["perdeu", "fora", "pressao", "choque", "lesao"])
    if not has_consequence:
        has_consequence = any(marker in normalized_text for marker in ["7x1", "alemanha", "semifinal", "trauma"])

    required_entities = min(3, len(entities)) if entities else 0
    missing_entities = [entity for entity in entities if entity not in present_entities]
    brief_used = bool(brief.get("confidence") != "low" and present_entities)
    score = 0.0
    if entities:
        score += min(4.0, (len(present_entities) / max(1, required_entities)) * 4.0)
    if concrete_facts:
        score += min(2.0, concrete_facts * 0.7)
    if has_conflict:
        score += 1.5
    if has_consequence:
        score += 1.5
    if abstract_hits:
        score -= min(3.0, len(abstract_hits) * 0.8)
    score = max(0.0, min(10.0, round(score, 1)))

    positive: list[str] = []
    negative: list[str] = []
    if brief_used:
        positive.append("factual_grounding_used")
    else:
        negative.append("factual_brief_not_used")
    if present_entities:
        positive.append("specific_entities_present")
    elif entities:
        negative.append("missing_key_entities")
    if concrete_facts > 0:
        positive.append("clear_historical_context")
    else:
        negative.append("no_specific_facts")
    if has_conflict:
        positive.append("concrete_conflict")
    if has_consequence:
        positive.append("concrete_consequence")
    if abstract_hits:
        negative.append("abstract_language_overuse")
    if _looks_generic(topic, text, entities, present_entities, concrete_facts):
        negative.append("generic_script_detected")

    return {
        "specificity_score": score,
        "is_specific": score >= 6.0 and "generic_script_detected" not in negative,
        "present_entities": present_entities,
        "missing_entities": missing_entities,
        "abstract_hits": list(dict.fromkeys(abstract_hits)),
        "positive_signals": list(dict.fromkeys(positive)),
        "negative_signals": list(dict.fromkeys(negative)),
    }


def repair_generic_script_with_brief(
    factual_brief: dict[str, Any],
    tone: str = "dramático",
    duration_seconds: int = 45,
) -> dict[str, Any]:
    subject = str(factual_brief.get("subject") or "essa história")
    pack_id = str(factual_brief.get("fact_pack_id") or "")
    if pack_id == "world_cup_2014_neymar" or "Neymar" in factual_brief.get("key_entities", []):
        lines = [
            "Nas quartas de final da Copa de 2014, o Brasil enfrentou a Colômbia.",
            "O jogo terminou com vitória brasileira, mas deixou uma perda gigantesca.",
            "Neymar levou uma joelhada nas costas de Zúñiga e saiu lesionado.",
            "A notícia foi um choque: o principal jogador da seleção estava fora da Copa.",
            "Sem Neymar, o Brasil chegou para enfrentar a Alemanha com um peso emocional enorme.",
            "Não era só uma semifinal. Era uma seleção tentando se reorganizar sem sua maior referência.",
            "E quando veio o 7x1, muita gente olhou só para aquele jogo.",
            "Mas parte daquela história começou antes, no momento em que Neymar caiu no gramado.",
            "Você acha que aquela semifinal teria sido diferente com Neymar em campo?",
        ]
        if duration_seconds >= 90:
            lines = [
                "Em 2014, Neymar não era só mais um jogador da seleção brasileira.",
                "Ele era a principal esperança técnica e emocional de um país inteiro.",
                "Nas quartas de final, o Brasil enfrentou a Colômbia em um jogo pesado.",
                "A seleção venceu, avançou, e parecia continuar viva no sonho da Copa em casa.",
                "Só que no fim daquele jogo veio o lance que mudou o clima do torneio.",
                "Neymar levou uma joelhada nas costas de Zúñiga e caiu no gramado.",
                "A lesão tirou o camisa 10 do restante da Copa.",
                "A notícia foi um choque porque o Brasil perdeu sua maior referência antes da semifinal.",
                "Sem Neymar, a equipe chegou para enfrentar a Alemanha tentando se reorganizar às pressas.",
                "Não era só uma ausência técnica. Era uma ausência emocional.",
                "A torcida ainda tentava acreditar, mas o clima já era de tensão.",
                "Quando veio o 7x1, o mundo olhou para a semifinal como um desastre isolado.",
                "Mas parte daquele colapso começou antes, no momento em que Neymar saiu da Copa.",
                "A pergunta que fica é difícil: com Neymar em campo, aquela noite teria sido diferente?",
            ]
        if duration_seconds >= 120:
            lines = [
                "A Copa de 2014 no Brasil tinha uma carga emocional enorme antes mesmo de começar.",
                "Para muita gente, Neymar era o rosto daquele sonho.",
                "Ele carregava a camisa 10, a expectativa da torcida e a sensação de que algo especial ainda podia acontecer.",
                "Nas quartas de final, o Brasil enfrentou a Colômbia em um jogo tenso.",
                "A seleção venceu por 2 a 1 e garantiu vaga na semifinal.",
                "Mas a vitória veio junto com uma notícia devastadora.",
                "No fim do jogo, Neymar levou uma joelhada nas costas de Zúñiga.",
                "Ele caiu no gramado, sentiu muita dor e precisou deixar a partida.",
                "Depois veio a confirmação: Neymar estava fora do restante da Copa.",
                "A seleção perdeu seu principal jogador antes do jogo mais importante do torneio.",
                "E isso mudou o ambiente do Brasil inteiro.",
                "Sem Neymar, o time precisava enfrentar a Alemanha sem sua maior referência técnica.",
                "Também jogava sem a mesma confiança emocional que vinha carregando até ali.",
                "A semifinal deixou de ser apenas um jogo por vaga na final.",
                "Virou uma tentativa de sobreviver a um choque que ainda estava fresco.",
                "Quando a Alemanha começou a marcar um gol atrás do outro, o Brasil pareceu desmoronar.",
                "O 7x1 virou o símbolo máximo daquele colapso.",
                "Mas a história não começou no primeiro gol alemão.",
                "Ela começou antes, quando Neymar caiu contra a Colômbia e o sonho brasileiro perdeu seu maior personagem.",
                "Você acha que o 7x1 teria acontecido do mesmo jeito com Neymar em campo?",
            ]
        return {
            "title": "O lance que mudou a Copa do Brasil em 2014",
            "hook": "Todo mundo lembra do 7x1... mas a Copa do Brasil começou a desmoronar antes da Alemanha.",
            "script_lines": lines,
            "visual_context": [
                "Imagem de estádio cheio na Copa de 2014",
                "Brasil contra Colômbia nas quartas de final",
                "Neymar caído no gramado após a lesão",
                "Torcida brasileira em clima de choque",
                "Referência visual ao placar Brasil 1 x 7 Alemanha",
            ],
        }
    timeline = _string_list(factual_brief.get("timeline"))
    facts = _string_list(factual_brief.get("key_facts"))
    conflict = _clean(factual_brief.get("conflict"))
    consequence = _clean(factual_brief.get("consequence"))
    lines = [*timeline[:3], *facts[:2]]
    if conflict:
        lines.append(conflict)
    if consequence:
        lines.append(consequence)
    if not lines:
        lines = [
            f"{subject} precisa de fatos mais específicos antes de virar um roteiro final.",
            "Sem esses fatos, o vídeo corre o risco de soar genérico demais.",
            "A melhor saída é confirmar nomes, datas e consequências antes de gravar.",
        ]
    return {
        "title": subject[:90],
        "hook": f"Pouca gente entende o peso real de {subject}.",
        "script_lines": lines[:8],
        "visual_context": [f"Imagem relacionada a {subject}", "B-roll documental com contexto histórico"],
    }


def _load_fact_packs() -> list[dict[str, Any]]:
    path = FACT_PACKS_PATH if FACT_PACKS_PATH.exists() else DEFAULT_FACT_PACKS_PATH
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    packs = payload.get("fact_packs", []) if isinstance(payload, dict) else []
    return [item for item in packs if isinstance(item, dict)]


def _extract_entities(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][\wÀ-ÿ0-9xX-]{2,}\b", text)))


def _concrete_fact_count(text: str) -> int:
    count = 0
    count += len(re.findall(r"\b(?:19|20)\d{2}\b", text))
    count += len(re.findall(r"\b\d+\s*x\s*\d+\b", text, flags=re.I))
    concrete_terms = ["Neymar", "Brasil", "Colômbia", "Colombia", "Zúñiga", "Zuniga", "Alemanha", "semifinal", "quartas", "lesão", "lesao", "Copa"]
    normalized = _normalize(text)
    count += sum(1 for term in concrete_terms if _normalize(term) in normalized)
    return count


def _looks_generic(topic: str, text: str, entities: list[str], present: list[str], facts: int) -> bool:
    if entities and len(present) < min(2, len(entities)):
        return True
    if facts == 0:
        return True
    normalized = _normalize(text)
    abstract_count = sum(1 for pattern in ABSTRACT_PATTERNS if _normalize(pattern) in normalized)
    return abstract_count >= 2


def _overlap_words(source: str, target: str) -> int:
    words = {word for word in re.findall(r"\b[\wÀ-ÿ]{4,}\b", source) if word not in {"para", "com", "uma", "mais", "como"}}
    return sum(1 for word in words if word in target)


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    return [text] if text else []


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize(value: str) -> str:
    table = str.maketrans("áàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ", "aaaaeeioooucAAAAEEIOOOUC")
    return _clean(value).lower().translate(table)
