from __future__ import annotations

import re
from typing import Any


DEPTH_LABELS = {
    "direct": "Direto",
    "normal": "Normal",
    "deep": "Aprofundado",
}

STYLE_LABELS = {
    "documentary": "Documentário",
    "emotional": "Emocional",
    "mystery": "Mistério/curiosidade",
    "controversial": "Polêmico",
    "explanatory": "Explicativo",
    "dramatic": "Dramático",
}


def normalize_script_depth(value: object) -> str:
    depth = str(value or "").strip().lower()
    return depth if depth in DEPTH_LABELS else "normal"


def script_depth_label(value: object) -> str:
    return DEPTH_LABELS[normalize_script_depth(value)]


def normalize_narrative_style(value: object, tone: str = "") -> str:
    style = str(value or "").strip().lower()
    if style in STYLE_LABELS:
        return style
    normalized_tone = _strip_accents(str(tone or "").lower())
    if normalized_tone in {"polemico", "controversial"}:
        return "controversial"
    if normalized_tone in {"didatico", "explicativo", "explanatory"}:
        return "explanatory"
    if normalized_tone in {"serio", "documentary"}:
        return "documentary"
    return "dramatic"


def narrative_style_label(value: object, tone: str = "") -> str:
    return STYLE_LABELS[normalize_narrative_style(value, tone=tone)]


def generate_narrative_plan(
    research_brief: dict[str, Any],
    duration_seconds: int,
    script_depth: str = "normal",
    narrative_style: str = "dramatic",
) -> dict[str, Any]:
    depth = normalize_script_depth(script_depth)
    style = normalize_narrative_style(narrative_style)
    topic = _topic_from_brief(research_brief)
    entities = _string_list(research_brief.get("key_entities"))
    conflict = _clean(research_brief.get("conflict"))
    consequence = _clean(research_brief.get("consequence"))
    summary = _clean(research_brief.get("summary"))
    emotional_angle = _clean(research_brief.get("emotional_angle") or research_brief.get("content_angle"))
    hidden_detail = _clean(research_brief.get("hidden_detail"))

    if _is_world_cup_neymar(topic, entities, summary):
        main_claim = (
            "O 7x1 não começou apenas contra a Alemanha; ele foi precedido por uma "
            "ruptura emocional na seleção com a lesão de Neymar."
        )
        central_question = "O Brasil perdeu só dentro de campo ou já entrou emocionalmente quebrado?"
        emotional_core = "A perda da maior esperança brasileira dentro de uma Copa em casa."
        conflict = conflict or "O Brasil seguia vivo na Copa, mas sem sua maior referência técnica e simbólica."
        stakes = "Uma semifinal em casa carregava expectativa nacional, pressão e cobrança histórica."
        hidden_detail = hidden_detail or "Neymar concentrava a esperança emocional da seleção naquele momento."
        turning_point = "A lesão contra a Colômbia mudou o clima da semifinal."
        consequence = consequence or "A seleção enfrentou a Alemanha sob pressão extrema e sem seu principal ponto de confiança."
        interpretation = "Isso não explica sozinho o 7x1, mas ajuda a entender o desmoronamento emocional daquele jogo."
        closing_question = "Com Neymar em campo, o Brasil teria perdido do mesmo jeito?"
    else:
        main_claim = _claim_from_brief(topic, summary, consequence)
        central_question = f"O que realmente muda quando você olha para {topic} pelo detalhe que quase ninguém comenta?"
        emotional_core = emotional_angle or f"A sensação de que {topic} era mais complexo do que parecia."
        conflict = conflict or f"A versão popular sobre {topic} parece simples, mas o contexto cria outra leitura."
        stakes = _stakes_for(topic, style)
        hidden_detail = hidden_detail or f"O detalhe pouco percebido é o que conecta o fato à consequência."
        turning_point = _turning_point_for(topic, research_brief)
        consequence = consequence or f"A consequência é que {topic} deixa de ser só um fato isolado e vira uma história com impacto."
        interpretation = _interpretation_for(topic, style, consequence)
        closing_question = f"Esse detalhe muda a forma como você enxerga {topic}?"

    beats = _story_beats(
        topic=topic,
        main_claim=main_claim,
        central_question=central_question,
        emotional_core=emotional_core,
        conflict=conflict,
        stakes=stakes,
        hidden_detail=hidden_detail,
        turning_point=turning_point,
        consequence=consequence,
        interpretation=interpretation,
        closing_question=closing_question,
        facts=_brief_facts(research_brief),
        depth=depth,
        duration_seconds=duration_seconds,
    )
    return {
        "main_claim": main_claim,
        "central_question": central_question,
        "emotional_core": emotional_core,
        "conflict": conflict,
        "stakes": stakes,
        "hidden_detail": hidden_detail,
        "turning_point": turning_point,
        "consequence": consequence,
        "interpretation": interpretation,
        "closing_question": closing_question,
        "story_beats": beats,
        "script_depth": depth,
        "script_depth_label": script_depth_label(depth),
        "narrative_style": style,
        "narrative_style_label": narrative_style_label(style),
        "narrative_plan_fallback_used": True,
    }


def build_script_from_narrative_plan(
    research_brief: dict[str, Any],
    narrative_plan: dict[str, Any],
    duration_seconds: int,
    script_depth: str = "normal",
    narrative_style: str = "dramatic",
) -> dict[str, Any]:
    depth = normalize_script_depth(script_depth)
    style = normalize_narrative_style(narrative_style)
    topic = _topic_from_brief(research_brief)
    plan = narrative_plan or generate_narrative_plan(research_brief, duration_seconds, depth, style)
    if _is_world_cup_neymar(topic, _string_list(research_brief.get("key_entities")), _clean(research_brief.get("summary"))):
        lines = _neymar_lines(duration_seconds, depth, plan)
    else:
        lines = _generic_lines(duration_seconds, depth, style, topic, plan)
    title = _title_for(topic, plan, style)
    hook = lines[0] if lines else _clean(plan.get("central_question"))
    body = lines[1:] if len(lines) > 1 else lines
    return {
        "title": title,
        "hook": hook,
        "script_lines": body,
        "cta": _clean(plan.get("closing_question")) or "Comenta: essa leitura faz sentido para você?",
        "visual_context": _visual_context(topic, plan, style),
        "fact_check_notes": _fact_notes_from_pairs(claim_evidence_pairs_from_brief(research_brief, plan)),
    }


def repair_shallow_script_with_narrative_plan(
    script: dict[str, Any],
    research_brief: dict[str, Any],
    narrative_plan: dict[str, Any],
    duration_seconds: int,
    script_depth: str = "normal",
    narrative_style: str = "dramatic",
) -> dict[str, Any]:
    repaired = build_script_from_narrative_plan(
        research_brief=research_brief,
        narrative_plan=narrative_plan,
        duration_seconds=duration_seconds,
        script_depth=script_depth,
        narrative_style=narrative_style,
    )
    return {**script, **repaired}


def claim_evidence_pairs_from_brief(
    research_brief: dict[str, Any],
    narrative_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    plan = narrative_plan or {}
    sources = _string_list(research_brief.get("source_urls"))
    facts = _brief_facts(research_brief)
    pairs: list[dict[str, Any]] = []
    for item in [
        plan.get("main_claim"),
        plan.get("turning_point"),
        plan.get("consequence"),
        *facts[:5],
    ]:
        claim = _clean(item)
        if not claim:
            continue
        evidence = _evidence_for_claim(claim, facts, research_brief)
        has_source = bool(sources)
        pairs.append(
            {
                "claim": claim,
                "evidence": evidence,
                "source_url": sources[0] if has_source else "",
                "confidence": "high" if has_source and evidence else ("medium" if evidence else "low"),
                "needs_fact_check": not bool(has_source and evidence),
            }
        )
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for pair in pairs:
        key = _strip_accents(pair["claim"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(pair)
    return unique[:8]


def score_narrative_quality(payload: dict[str, Any]) -> dict[str, Any]:
    lines = [_clean(item) for item in payload.get("script_lines") or [] if _clean(item)]
    hook = _clean(payload.get("hook"))
    cta = _clean(payload.get("cta"))
    text = " ".join([hook, *lines, cta]).lower()
    normalized = _strip_accents(text)
    plan = payload.get("narrative_plan") if isinstance(payload.get("narrative_plan"), dict) else {}
    story_beats = payload.get("story_beats") if isinstance(payload.get("story_beats"), list) else []

    positive: list[str] = []
    negative: list[str] = []
    depth = 4.0
    narrative = 4.0
    retention = 4.0

    if any(marker in normalized for marker in ["contexto", "clima", "pressao", "por tras", "antes"]):
        depth += 1.2
        positive.append("context_present")
    else:
        negative.append("context_missing")
    if any(marker in normalized for marker in ["porque", "por que", "isso ajuda", "explica", "entender"]):
        depth += 1.3
        positive.append("why_it_matters")
    else:
        negative.append("why_it_matters_missing")
    if any(marker in normalized for marker in ["consequencia", "resultado", "mudou", "criou", "levou"]):
        depth += 1.1
        positive.append("consequence_explained")
    else:
        negative.append("no_consequence")
    if any(marker in normalized for marker in ["nao explica sozinho", "ajuda a entender", "leitura", "parecia", "significa"]):
        depth += 1.0
        positive.append("interpretation_present")
    else:
        negative.append("no_interpretation")

    if plan:
        narrative += 1.2
        positive.append("narrative_plan_used")
    if _clean(plan.get("emotional_core")):
        depth += 0.7
        positive.append("emotional_core_present")
    else:
        negative.append("no_emotional_core")
    if _clean(plan.get("conflict")) or "mas" in normalized:
        narrative += 1.0
        positive.append("conflict_present")
    else:
        negative.append("no_clear_conflict")
    if _clean(plan.get("hidden_detail")) or "detalhe" in normalized:
        narrative += 0.9
        positive.append("hidden_detail_present")
    if _clean(plan.get("turning_point")) or any(marker in normalized for marker in ["virada", "mudou o clima", "a partir dali"]):
        narrative += 0.9
        positive.append("turning_point_present")
    else:
        negative.append("no_turning_point")
    if story_beats:
        narrative += min(1.0, len(story_beats) / 8)
        positive.append("story_beats_used")

    if hook and (_has_curiosity(hook) or hook.endswith("?")):
        retention += 1.4
        positive.append("strong_retention_hook")
    else:
        negative.append("low_retention_hook")
    if len(lines) >= 6:
        retention += 0.8
        positive.append("progression_present")
    if any(marker in normalized for marker in ["mas", "so que", "ate", "antes mesmo", "o detalhe"]):
        retention += 1.0
        positive.append("tension_progression")
    if cta.endswith("?") or (lines and lines[-1].endswith("?")):
        retention += 1.0
        narrative += 0.6
        positive.append("strong_closing_question")
    else:
        negative.append("weak_closing_question")
    if lines and max(len(line) for line in lines) <= 230:
        retention += 0.5
        positive.append("short_narratable_lines")
    else:
        negative.append("long_lines")

    fact_list_only = _looks_like_fact_list(lines, normalized)
    shallow = fact_list_only or depth < 6.2 or narrative < 6.0
    if fact_list_only:
        negative.extend(["fact_list_only", "shallow_script_detected"])
    elif shallow:
        negative.append("shallow_script_detected")
    else:
        positive.append("not_just_fact_list")

    return {
        "depth_score": _clamp(depth),
        "narrative_score": _clamp(narrative),
        "retention_score": _clamp(retention),
        "shallow_script_detected": bool(shallow),
        "script_positive_signals": list(dict.fromkeys(positive)),
        "script_negative_signals": list(dict.fromkeys(negative)),
    }


def _story_beats(
    topic: str,
    main_claim: str,
    central_question: str,
    emotional_core: str,
    conflict: str,
    stakes: str,
    hidden_detail: str,
    turning_point: str,
    consequence: str,
    interpretation: str,
    closing_question: str,
    facts: list[str],
    depth: str,
    duration_seconds: int,
) -> list[dict[str, Any]]:
    roles = [
        ("hook", central_question or main_claim, "abrir curiosidade"),
        ("context", emotional_core or topic, "situar o peso emocional"),
        ("tension", conflict, "criar tensão"),
        ("hidden_detail", hidden_detail, "entregar detalhe pouco percebido"),
        ("turning_point", turning_point, "mostrar a virada"),
        ("consequence", consequence, "explicar consequência"),
        ("reflection", interpretation, "separar fato de leitura"),
        ("cta", closing_question, "provocar comentário"),
    ]
    if depth == "direct" or duration_seconds <= 60:
        roles = [roles[0], roles[2], roles[4], roles[5], roles[7]]
    elif depth == "normal" or duration_seconds <= 90:
        roles = [roles[0], roles[1], roles[2], roles[3], roles[4], roles[5], roles[7]]
    beats: list[dict[str, Any]] = []
    for index, (role, content, goal) in enumerate(roles, start=1):
        fact = facts[(index - 1) % len(facts)] if facts else topic
        beats.append(
            {
                "beat_id": f"beat_{index}",
                "role": role,
                "content": _clean(content) or topic,
                "facts_used": [fact] if fact else [],
                "emotional_goal": goal,
            }
        )
    return beats


def _neymar_lines(duration: int, depth: str, plan: dict[str, Any]) -> list[str]:
    direct = [
        "Todo mundo lembra do 7x1 como se ele tivesse começado contra a Alemanha.",
        "Mas o clima daquela semifinal já estava quebrado antes do jogo.",
        "Contra a Colômbia, Neymar levou uma joelhada nas costas de Zúñiga e saiu da Copa.",
        "O Brasil venceu aquela partida, mas perdeu sua maior referência técnica e emocional.",
        "Sem o jogador que concentrava a confiança do país, a seleção entrou contra a Alemanha sob uma pressão estranha.",
        "Isso não explica sozinho o 7x1, mas ajuda a entender por que tudo pareceu desmoronar tão rápido.",
        _clean(plan.get("closing_question")) or "Com Neymar em campo, o Brasil teria perdido do mesmo jeito?",
    ]
    normal = direct[:1] + [
        "Só que a história daquele jogo não começa no primeiro gol alemão.",
        "Ela passa pelo que aconteceu dias antes, nas quartas de final.",
        "Neymar saiu machucado contra a Colômbia e ficou fora do restante da Copa.",
        "Naquele momento, ele não era só o camisa 10.",
        "Ele era o rosto da esperança brasileira dentro de casa.",
        "O Brasil ainda tinha time, estádio lotado e uma semifinal para jogar.",
        "Mas perdeu o ponto emocional que segurava boa parte da confiança da torcida e do grupo.",
        "A Alemanha foi superior em campo, mas o Brasil parecia emocionalmente abalado antes mesmo de o placar ficar impossível.",
        _clean(plan.get("closing_question")) or "O Brasil perdeu só dentro de campo ou já tinha começado a perder quando Neymar saiu daquela Copa?",
    ]
    deep_lines = [
        "Todo mundo lembra do 7x1 como se ele tivesse começado no apito inicial contra a Alemanha.",
        "Mas o clima daquela semifinal já estava quebrado antes do jogo começar.",
        "A Copa era no Brasil, e isso transformava cada partida em uma cobrança nacional.",
        "Nas quartas de final, contra a Colômbia, Neymar levou uma joelhada nas costas de Zúñiga e saiu da Copa.",
        "O Brasil venceu aquela partida, mas perdeu algo maior do que um jogador.",
        "Perdeu sua principal referência técnica, emocional e simbólica.",
        "Até aquele momento, Neymar não era só o camisa 10.",
        "Ele era o rosto da esperança brasileira dentro de casa.",
        "Quando ele ficou fora, a seleção entrou contra a Alemanha carregando uma pressão estranha.",
        "Era uma semifinal, em casa, sem o jogador que concentrava quase toda a confiança do país.",
        "Isso não explica sozinho o 7x1.",
        "A Alemanha jogou melhor, e o colapso teve muitos fatores.",
        "Mas a lesão ajuda a entender por que aquele jogo parecia emocionalmente desmoronado antes mesmo de ficar impossível no placar.",
        _clean(plan.get("closing_question")) or "O Brasil perdeu para a Alemanha só dentro de campo ou já tinha começado a perder quando Neymar saiu daquela Copa?",
    ]
    if depth == "deep" or duration >= 120:
        return deep_lines
    if depth == "normal" or duration >= 90:
        return normal
    return direct


def _generic_lines(duration: int, depth: str, style: str, topic: str, plan: dict[str, Any]) -> list[str]:
    base = [
        _clean(plan.get("central_question")) or f"Tem um detalhe em {topic} que muda a história.",
        _clean(plan.get("conflict")) or f"A versão mais conhecida sobre {topic} parece simples.",
        _clean(plan.get("hidden_detail")) or "Mas o detalhe pouco percebido aparece quando você olha para o contexto.",
        _clean(plan.get("turning_point")) or "A virada acontece quando esse detalhe deixa de ser pequeno.",
        _clean(plan.get("consequence")) or "A consequência é que a história ganha outro peso.",
        _clean(plan.get("interpretation")) or "Isso não transforma interpretação em fato, mas abre uma leitura mais completa.",
        _clean(plan.get("closing_question")) or f"Esse detalhe muda sua visão sobre {topic}?",
    ]
    if style == "mystery":
        base[0] = f"O detalhe mais importante sobre {topic} quase nunca aparece primeiro."
    elif style == "controversial":
        base[0] = f"Essa leitura sobre {topic} pode dividir opiniões."
    elif style == "explanatory":
        base[0] = f"Para entender {topic}, você precisa separar fato, contexto e consequência."
    if depth == "direct" or duration <= 60:
        return [base[0], base[1], base[3], base[4], base[-1]]
    if depth == "deep" or duration >= 120:
        return base[:1] + [
            _clean(plan.get("emotional_core")) or f"O impacto humano de {topic} é o que torna a história maior.",
            *base[1:],
            _clean(plan.get("stakes")) or "É por isso que o tema importa além do fato isolado.",
        ]
    return base


def _brief_facts(brief: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    for key in ["key_facts", "facts", "timeline", "evidence"]:
        value = brief.get(key)
        if isinstance(value, list):
            facts.extend(_clean(item) for item in value if _clean(item))
    for key in ["summary", "conflict", "consequence"]:
        text = _clean(brief.get(key))
        if text:
            facts.append(text)
    return list(dict.fromkeys(facts))


def _topic_from_brief(brief: dict[str, Any]) -> str:
    for key in ["topic", "title", "query", "idea"]:
        text = _clean(brief.get(key))
        if text:
            return text
    summary = _clean(brief.get("summary"))
    return summary[:80] if summary else "essa história"


def _claim_from_brief(topic: str, summary: str, consequence: str) -> str:
    if consequence:
        return consequence
    if summary:
        return summary
    return f"{topic} não é só um fato isolado; o contexto muda a leitura da história."


def _stakes_for(topic: str, style: str) -> str:
    if style == "emotional":
        return f"O que está em jogo em {topic} é o impacto humano por trás do acontecimento."
    if style == "controversial":
        return f"O que está em jogo em {topic} é a diferença entre fato, opinião e narrativa pública."
    return f"O que está em jogo em {topic} é entender por que esse detalhe importa."


def _turning_point_for(topic: str, brief: dict[str, Any]) -> str:
    timeline = _string_list(brief.get("timeline"))
    if timeline:
        return timeline[min(1, len(timeline) - 1)]
    return f"A virada aparece quando o detalhe central de {topic} muda o rumo da história."


def _interpretation_for(topic: str, style: str, consequence: str) -> str:
    if style == "documentary":
        return f"A leitura mais prudente é que {topic} precisa ser visto junto do contexto, não como um episódio solto."
    if style == "dramatic":
        return f"Essa consequência dá a {topic} um peso maior do que a versão resumida costuma mostrar."
    return consequence or f"Essa é uma interpretação possível, desde que os fatos sejam mantidos separados da opinião."


def _evidence_for_claim(claim: str, facts: list[str], brief: dict[str, Any]) -> str:
    normalized_claim_words = set(_strip_accents(claim.lower()).split())
    best = ""
    best_overlap = 0
    for fact in facts:
        overlap = len(normalized_claim_words.intersection(set(_strip_accents(fact.lower()).split())))
        if overlap > best_overlap:
            best = fact
            best_overlap = overlap
    return best or _clean(brief.get("summary"))


def _looks_like_fact_list(lines: list[str], normalized_text: str) -> bool:
    if len(lines) <= 4 and not any(marker in normalized_text for marker in ["mas", "porque", "consequencia", "pressao"]):
        return True
    fact_markers = sum(1 for marker in ["ficou", "perdeu", "venceu", "aconteceu", "foi", "teve"] if marker in normalized_text)
    narrative_markers = sum(1 for marker in ["mas", "so que", "por tras", "isso nao explica", "ajuda a entender"] if marker in normalized_text)
    return fact_markers >= 3 and narrative_markers == 0


def _is_world_cup_neymar(topic: str, entities: list[str], summary: str) -> bool:
    text = _strip_accents(" ".join([topic, summary, *entities]).lower())
    return ("neymar" in text and ("2014" in text or "copa" in text)) or ("7x1" in text and "brasil" in text)


def _title_for(topic: str, plan: dict[str, Any], style: str) -> str:
    if _is_world_cup_neymar(topic, [], _clean(plan.get("main_claim"))):
        return "O 7x1 começou antes da Alemanha?"
    if style == "mystery":
        return f"O detalhe escondido de {topic}"[:90]
    return (_clean(plan.get("main_claim")) or f"A leitura profunda de {topic}")[:90]


def _visual_context(topic: str, plan: dict[str, Any], style: str) -> list[str]:
    return [
        f"B-roll simbólico de {topic}",
        f"Sequência visual para conflito: {_clean(plan.get('conflict'))}",
        f"Imagem de consequência/reflexão em tom {STYLE_LABELS.get(style, 'narrativo')}",
        "Evitar rostos reais, marcas e cenas sem licença.",
    ]


def _fact_notes_from_pairs(pairs: list[dict[str, Any]]) -> list[str]:
    notes = ["Separar fatos de interpretação na revisão final."]
    if any(pair.get("needs_fact_check") for pair in pairs):
        notes.append("Há claims sem fonte externa registrada; confirmar antes de publicar.")
    return notes


def _has_curiosity(text: str) -> bool:
    normalized = _strip_accents(text.lower())
    return any(marker in normalized for marker in ["todo mundo", "pouca gente", "detalhe", "por que", "sera", "parece"])


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    return [text] if text else []


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _strip_accents(value: str) -> str:
    table = str.maketrans("áàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ", "aaaaeeioooucAAAAEEIOOOUC")
    return value.translate(table)


def _clamp(value: float) -> float:
    return max(0.0, min(10.0, round(value, 1)))
