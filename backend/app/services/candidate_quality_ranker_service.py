from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app import config


RULES_PATH = config.STORAGE_TRENDS_DIR.parent / "config" / "candidate_quality_rules.json"

DEFAULT_RULES: dict[str, Any] = {
    "tier_excellent_min": 8.0,
    "tier_good_min": 6.5,
    "tier_average_min": 5.0,
    "tier_weak_min": 3.5,
    "positive_keywords": [
        "polêmica",
        "polemica",
        "absurdo",
        "revelou",
        "ninguém fala",
        "ninguem fala",
        "o problema é",
        "o problema e",
        "a verdade",
        "não faz sentido",
        "nao faz sentido",
        "por que",
        "como",
        "comparado",
        "o erro",
        "o segredo",
        "explica",
        "denúncia",
        "denuncia",
        "perigo",
        "realidade",
    ],
    "negative_keywords": [
        "se inscreve",
        "deixa o like",
        "link na descrição",
        "link na descricao",
        "patrocinado",
        "cupom",
        "use o código",
        "use o codigo",
        "publicidade",
        "merchandising",
        "vinheta",
        "salve galera",
        "fala pessoal",
        "sejam bem-vindos",
        "comecando mais um",
        "começando mais um",
        "até o próximo",
        "ate o proximo",
        "obrigado por assistir",
        "não esquece de seguir",
        "nao esquece de seguir",
        "ative o sininho",
        "segue a gente",
    ],
    "hard_reject_keywords": [
        "se inscreve",
        "deixa o like",
        "link na descrição",
        "link na descricao",
        "patrocinado",
        "cupom",
        "use o código",
        "use o codigo",
        "publicidade",
        "salve galera",
        "fala pessoal",
        "sejam bem-vindos",
        "comecando mais um",
        "começando mais um",
        "até o próximo",
        "ate o proximo",
        "obrigado por assistir",
        "não esquece de seguir",
        "nao esquece de seguir",
    ],
    "hard_min_duration_seconds": 8,
    "hard_max_duration_seconds": 180,
    "hard_min_text_chars": 60,
    "hard_min_words": 12,
    "hard_min_density_words_per_second": 0.45,
    "min_duration_seconds": 12,
    "ideal_min_duration_seconds": 20,
    "ideal_max_duration_seconds": 90,
    "max_duration_seconds": 140,
    "min_text_chars": 120,
    "min_words": 25,
    "min_density_words_per_second": 0.8,
    "min_quality_score_fast": 5.5,
    "min_quality_score_deep": 4.5,
    "text_similarity_threshold": 0.86,
    "time_start_tolerance_seconds": 3,
    "time_end_tolerance_seconds": 4,
}


def load_candidate_quality_rules() -> dict[str, Any]:
    if not RULES_PATH.exists():
        RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _write_json(RULES_PATH, DEFAULT_RULES)
        return dict(DEFAULT_RULES)
    payload = _load_json(RULES_PATH)
    if not isinstance(payload, dict):
        _write_json(RULES_PATH, DEFAULT_RULES)
        return dict(DEFAULT_RULES)
    rules = dict(DEFAULT_RULES)
    rules.update(payload)
    return rules


def rank_candidate(candidate: dict[str, Any], rules: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = rules or load_candidate_quality_rules()
    text = str(candidate.get("text") or candidate.get("reason") or "")
    normalized = _normalize(text)
    words = _words(normalized)
    duration = _float(candidate.get("duration_seconds"))
    score = 4.0
    positive: list[str] = []
    negative: list[str] = []
    reject_reason = ""
    hard_reject_reason = ""

    hard_keyword_hits = _keyword_hits(normalized, rules.get("hard_reject_keywords", []))
    if duration < _float(rules.get("hard_min_duration_seconds")):
        hard_reject_reason = "hard_rule:duration_too_short"
    elif duration > _float(rules.get("hard_max_duration_seconds")):
        hard_reject_reason = "hard_rule:duration_too_long"
    elif len(text.strip()) < _int(rules.get("hard_min_text_chars")):
        hard_reject_reason = "hard_rule:text_too_short"
    elif len(words) < _int(rules.get("hard_min_words")):
        hard_reject_reason = "hard_rule:few_words"

    density = len(words) / max(duration, 1.0)
    if not hard_reject_reason and density < _float(rules.get("hard_min_density_words_per_second")):
        hard_reject_reason = "hard_rule:low_speech_density"
    if not hard_reject_reason and hard_keyword_hits:
        hard_reject_reason = f"hard_rule:blocked_phrase:{hard_keyword_hits[0]}"

    if duration < _float(rules.get("min_duration_seconds")):
        score -= 3.5
        negative.append("duration_too_short")
        reject_reason = "duration_too_short"
    elif _float(rules.get("ideal_min_duration_seconds")) <= duration <= _float(rules.get("ideal_max_duration_seconds")):
        score += 1.0
        positive.append("good_clip_duration")
    elif duration > _float(rules.get("max_duration_seconds")):
        score -= 2.3
        negative.append("duration_too_long")
        reject_reason = reject_reason or "duration_too_long"
    else:
        score -= 0.4
        negative.append("suboptimal_duration")

    if len(text.strip()) >= _int(rules.get("min_text_chars")):
        score += 0.5
        positive.append("enough_text")
    else:
        score -= 1.3
        negative.append("text_too_short")
        reject_reason = reject_reason or "text_too_short"

    if len(words) >= _int(rules.get("min_words")):
        score += 0.4
        positive.append("enough_words")
    else:
        score -= 1.0
        negative.append("few_words")

    if density >= _float(rules.get("min_density_words_per_second")):
        score += 0.5
        positive.append("good_speech_density")
    else:
        score -= 1.6
        negative.append("low_speech_density")

    positive_hits = _keyword_hits(normalized, rules.get("positive_keywords", []))
    if positive_hits:
        score += min(1.6, 0.4 * len(positive_hits))
        positive.extend(f"keyword:{item}" for item in positive_hits[:5])

    negative_hits = _keyword_hits(normalized, rules.get("negative_keywords", []))
    if negative_hits:
        score -= min(3.0, 0.9 * len(negative_hits))
        negative.extend(f"negative_keyword:{item}" for item in negative_hits[:5])
        reject_reason = reject_reason or "negative_keyword"

    if "?" in text or any(item in normalized for item in ("por que", "como que", "qual ", "quando ", "onde ")):
        score += 0.65
        positive.append("clear_question")
    if any(item in normalized for item in ("mas ", "só que", "so que", "porém", "porem", "contra", "briga", "debate", "polêmica", "polemica")):
        score += 0.55
        positive.append("conflict_or_debate")
    if any(item in normalized for item in ("eu acho", "na minha opinião", "na minha opiniao", "absurdo", "inacreditável", "inacreditavel")):
        score += 0.45
        positive.append("strong_opinion")
    if any(item in normalized for item in ("maior que", "menor que", "comparado", "diferença", "diferenca", "versus")):
        score += 0.35
        positive.append("comparison")
    if re.search(r"\b\d+([,.]\d+)?\b", normalized):
        score += 0.3
        positive.append("concrete_number")

    if _starts_badly(normalized):
        score -= 1.1
        negative.append("weak_start")
    else:
        score += 0.2
        positive.append("understandable_start")
    if _ends_badly(normalized):
        score -= 1.2
        negative.append("cut_off_ending")
    else:
        score += 0.2
        positive.append("understandable_end")
    filler_ratio = _filler_ratio(words)
    if filler_ratio > 0.16:
        score -= 1.0
        negative.append("too_many_fillers")

    if _looks_like_opening_or_closing(normalized):
        score -= 1.8
        negative.append("opening_or_closing")
        reject_reason = reject_reason or "opening_or_closing"

    if _looks_generic(normalized):
        score -= 0.8
        negative.append("generic_text")
    if not _has_verb_or_hook(normalized):
        score -= 0.7
        negative.append("no_verb_opinion_or_question")

    score = round(max(0.0, min(10.0, score)), 2)
    if hard_reject_reason:
        reject_reason = hard_reject_reason
    tier = quality_tier(score, reject_reason, rules)
    if tier == "reject" and not reject_reason:
        reject_reason = "low_quality_score"
    return {
        "candidate_quality_score": score,
        "quality_score": score,
        "quality_tier": tier,
        "candidate_quality_tier": tier,
        "positive_signals": positive,
        "negative_signals": negative,
        "quality_positive_signals": positive,
        "quality_negative_signals": negative,
        "reject_reason": reject_reason,
        "candidate_quality_reject_reason": reject_reason,
        "hard_reject": bool(hard_reject_reason),
        "candidate_quality_hard_reject": bool(hard_reject_reason),
        "hard_reject_reason": hard_reject_reason,
        "speech_density_words_per_second": round(density, 2),
        "word_count": len(words),
        "text_normalized": normalized,
    }


def quality_tier(score: float, reject_reason: str = "", rules: dict[str, Any] | None = None) -> str:
    rules = rules or DEFAULT_RULES
    if str(reject_reason).startswith("hard_rule:"):
        return "reject"
    if score >= _float(rules.get("tier_excellent_min")):
        return "excellent"
    if score >= _float(rules.get("tier_good_min")):
        return "good"
    if score >= _float(rules.get("tier_average_min")):
        return "average"
    if score >= _float(rules.get("tier_weak_min")):
        return "weak"
    return "reject"


def filter_by_quality(
    items: list[dict[str, Any]],
    *,
    min_score: float,
    fallback_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    strong_accepted: list[dict[str, Any]] = []
    average_candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    hard_rejected = 0
    score_rejected = 0
    for item in items:
        score = _float(item.get("candidate_quality_score") or item.get("quality_score"))
        tier = str(item.get("quality_tier") or item.get("candidate_quality_tier") or "")
        hard_reject = bool(item.get("candidate_quality_hard_reject") or item.get("hard_reject"))
        if hard_reject or tier == "reject":
            hard_rejected += 1 if hard_reject else 0
            score_rejected += 0 if hard_reject else 1
            rejected.append({**item, "candidate_quality_reject_reason": item.get("candidate_quality_reject_reason") or "low_quality_score"})
        elif score >= min_score and tier in {"excellent", "good"}:
            strong_accepted.append(item)
        elif score >= min_score and tier == "average":
            average_candidates.append(item)
        else:
            score_rejected += 1
            rejected.append(item)
    accepted = strong_accepted if strong_accepted else average_candidates
    if strong_accepted:
        score_rejected += len(average_candidates)
        rejected.extend({**item, "candidate_quality_reject_reason": "average_skipped_because_good_available"} for item in average_candidates)
    fallback_used = False
    fallback_items: list[dict[str, Any]] = []
    if not accepted and rejected and fallback_limit > 0:
        eligible_fallback = [
            item for item in rejected
            if not bool(item.get("candidate_quality_hard_reject") or item.get("hard_reject"))
            and not str(item.get("candidate_quality_reject_reason") or "").startswith("hard_rule:")
        ]
        fallback_items = sorted(eligible_fallback, key=_quality_sort_key, reverse=True)[:fallback_limit]
        fallback_used = bool(fallback_items)
        accepted = [{**item, "quality_fallback_used": True} for item in fallback_items]
        fallback_ids = {str(item.get("candidate_id") or "") for item in fallback_items}
        rejected = [item for item in rejected if str(item.get("candidate_id") or "") not in fallback_ids]
    stats = {
        "quality_rejected": len(rejected),
        "hard_rejected": hard_rejected,
        "score_rejected": score_rejected,
        "quality_fallback_used": fallback_used,
        "fallback_used": fallback_used,
        "quality_fallback_selected_count": len(fallback_items),
        "fallback_selected_count": len(fallback_items),
    }
    return sorted(accepted, key=_quality_sort_key, reverse=True), stats


def dedupe_candidates(
    items: list[dict[str, Any]],
    *,
    overlap_threshold: float,
    text_similarity_threshold: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rules = load_candidate_quality_rules()
    text_threshold = text_similarity_threshold or _float(rules.get("text_similarity_threshold")) or 0.86
    kept: list[dict[str, Any]] = []
    removed_by_time = 0
    removed_by_text = 0
    for item in sorted(items, key=_quality_sort_key, reverse=True):
        duplicate_time = False
        duplicate_text = False
        for other in kept:
            if str(other.get("video_id") or "") != str(item.get("video_id") or ""):
                continue
            if _same_time(item, other, overlap_threshold, rules):
                duplicate_time = True
                break
            if _text_similarity(item, other) >= text_threshold:
                duplicate_text = True
                break
        if duplicate_time:
            removed_by_time += 1
            continue
        if duplicate_text:
            removed_by_text += 1
            continue
        kept.append(item)
    return kept, {
        "duplicates_removed_by_time": removed_by_time,
        "duplicates_removed_by_text": removed_by_text,
        "duplicates_removed": removed_by_time + removed_by_text,
    }


def candidate_quality_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [item for item in items if item.get("candidate_quality_score") is not None or item.get("quality_score") is not None]
    scores = [_float(item.get("candidate_quality_score") or item.get("quality_score")) for item in scored]
    tiers = Counter(
        str(item.get("quality_tier") or item.get("candidate_quality_tier") or quality_tier(_float(item.get("candidate_quality_score") or item.get("quality_score"))))
        for item in scored
    )
    positive = Counter(signal for item in scored for signal in _list(item.get("positive_signals") or item.get("quality_positive_signals")))
    negative = Counter(signal for item in scored for signal in _list(item.get("negative_signals") or item.get("quality_negative_signals")))
    sorted_scores = sorted(scores)
    bottom = sorted(scored, key=_quality_sort_key)[:10]
    bottom_negative = Counter(signal for item in bottom for signal in _list(item.get("negative_signals") or item.get("quality_negative_signals")))
    return {
        "total_scored": len(scored),
        "score_min": round(min(scores), 2) if scores else 0,
        "score_max": round(max(scores), 2) if scores else 0,
        "score_p25": _quantile(sorted_scores, 0.25),
        "score_p50": _quantile(sorted_scores, 0.50),
        "score_p75": _quantile(sorted_scores, 0.75),
        "excellent_count": tiers.get("excellent", 0),
        "good_count": tiers.get("good", 0),
        "average_count": tiers.get("average", 0),
        "weak_count": tiers.get("weak", 0),
        "rejected_count": tiers.get("reject", 0),
        "hard_rejected_count": sum(1 for item in scored if item.get("candidate_quality_hard_reject") or item.get("hard_reject")),
        "average_quality_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "top_positive_signals": [{"signal": key, "count": value} for key, value in positive.most_common(8)],
        "top_negative_signals": [{"signal": key, "count": value} for key, value in negative.most_common(8)],
        "bottom_negative_signals": [{"signal": key, "count": value} for key, value in bottom_negative.most_common(8)],
    }


def _quality_sort_key(item: dict[str, Any]) -> tuple[float, float, float]:
    return (
        _float(item.get("candidate_quality_score") or item.get("quality_score")),
        _float(item.get("ranking_quality_score") or item.get("score")),
        -_float(item.get("rank")),
    )


def _same_time(left: dict[str, Any], right: dict[str, Any], overlap_threshold: float, rules: dict[str, Any]) -> bool:
    start_diff = abs(_float(left.get("start_seconds")) - _float(right.get("start_seconds")))
    end_diff = abs(_float(left.get("end_seconds")) - _float(right.get("end_seconds")))
    if start_diff <= _float(rules.get("time_start_tolerance_seconds")) and end_diff <= _float(rules.get("time_end_tolerance_seconds")):
        return True
    return _overlap_ratio(left, right) >= overlap_threshold


def _overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
    start = max(_float(left.get("start_seconds")), _float(right.get("start_seconds")))
    end = min(_float(left.get("end_seconds")), _float(right.get("end_seconds")))
    overlap = max(0.0, end - start)
    return overlap / max(1.0, min(_float(left.get("duration_seconds")), _float(right.get("duration_seconds"))))


def _text_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_text = str(left.get("text_normalized") or _normalize(str(left.get("text") or "")))
    right_text = str(right.get("text_normalized") or _normalize(str(right.get("text") or "")))
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _starts_badly(text: str) -> bool:
    return bool(re.match(r"^(entao|então|ai|aí|tipo|ne|né|cara|mano|e )\b", text))


def _ends_badly(text: str) -> bool:
    return bool(re.search(r"\b(entao|então|porque|por que|que|mas|só que|so que|e|ai|aí|daí|dai)$", text.strip()))


def _looks_like_opening_or_closing(text: str) -> bool:
    return any(item in text for item in ("bem vindos", "bem-vindos", "sejam bem vindos", "salve galera", "fala pessoal", "comecando mais um", "ate a proxima", "ate o proximo", "obrigado por assistir", "nao esquece de seguir"))


def _looks_generic(text: str) -> bool:
    if not text:
        return True
    generic_hits = sum(1 for item in ("coisa", "negocio", "bagulho", "assim", "tipo", "cara", "mano") if item in text)
    return generic_hits >= 3


def _has_verb_or_hook(text: str) -> bool:
    if "?" in text:
        return True
    hook_terms = ("acho", "penso", "revelou", "explica", "aconteceu", "falou", "disse", "mostrou", "perguntou", "respondeu", "defendeu", "criticou", "polemica", "absurdo")
    if any(term in text for term in hook_terms):
        return True
    return bool(re.search(r"\b\w+(ou|aram|eram|iam|ava|avam|ando|endo|indo|ei|eu|ia|ou|ar|er|ir)\b", text))


def _filler_ratio(words: list[str]) -> float:
    if not words:
        return 0.0
    fillers = {"tipo", "né", "ne", "mano", "cara", "assim", "então", "entao", "aí", "ai"}
    return sum(1 for word in words if word in fillers) / len(words)


def _keyword_hits(text: str, keywords: Any) -> list[str]:
    return [str(keyword) for keyword in keywords if _normalize(str(keyword)) in text]


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\wÀ-ÿ]+\b", text.lower())


def _normalize(value: str) -> str:
    stripped = "".join(
        char for char in unicodedata.normalize("NFKD", str(value or ""))
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _quantile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    index = (len(sorted_values) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    value = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    return round(value, 2)


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
