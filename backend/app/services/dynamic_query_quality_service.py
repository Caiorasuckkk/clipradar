import re


class DynamicQueryQualityService:
    INTENT_TERMS = {
        "backstage",
        "bastidores",
        "corte",
        "cortes",
        "entrevista",
        "flow",
        "funny",
        "história engraçada",
        "hot ones",
        "inteligência ltda",
        "interview",
        "joe rogan",
        "piers morgan",
        "podcast",
        "podpah",
        "polêmica",
        "revealed",
        "ticaracaticast",
        "theo von",
    }
    BAD_TERMS = {
        "album",
        "amazon",
        "clipe",
        "ecommerce",
        "lyrics",
        "music",
        "recall",
        "song",
        "trailer",
    }
    GENERIC = {"brasil", "mundo", "news", "notícia", "viral", "video", "vídeo"}

    def score(
        self,
        query: str,
        entity: str,
        real_source: bool = True,
        topic_base_quality_score: float = 0.0,
        strong_evidence: bool = False,
    ) -> float:
        normalized = query.lower()
        words = normalized.split()
        score = 4.0

        if entity and entity.lower() in normalized:
            score += 1.5
        if any(term in normalized for term in self.INTENT_TERMS):
            score += 1.0
        if 2 <= len(words) <= 8:
            score += 1.0
        if real_source:
            score += 1.0
        if self._has_clear_entity(entity):
            score += 1.0

        if any(term in normalized for term in self.BAD_TERMS) and not any(
            term in normalized for term in ["podcast", "interview", "entrevista", "corte"]
        ):
            score -= 2.0
        if self._has_repeated_suffix(normalized):
            score -= 2.0
        if not entity or entity.lower() in self.GENERIC:
            score -= 2.5
        if len(words) > 8 or len(words) < 2:
            score -= 1.5
        if topic_base_quality_score < 4:
            score = min(score, 3.0)
        if topic_base_quality_score < 5 and not strong_evidence:
            score = min(score, 4.0)

        return round(max(0.0, min(10.0, score)), 2)

    @staticmethod
    def _has_clear_entity(entity: str) -> bool:
        return bool(entity and len(entity.split()) <= 5 and len(entity.replace(" ", "")) >= 4)

    @staticmethod
    def _has_repeated_suffix(query: str) -> bool:
        words = re.findall(r"\b[\wÀ-ÿ]+\b", query)
        return len(words) != len(list(dict.fromkeys(words)))
