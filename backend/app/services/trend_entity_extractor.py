import re


class TrendEntityExtractor:
    MEDIA_OUTLETS = {
        "AP News",
        "BBC",
        "CNN",
        "Estadão",
        "Folha",
        "G1",
        "Globo",
        "Reuters",
        "Terra",
        "UOL",
    }
    GENERIC_TERMS = {
        "agora",
        "brasil",
        "completo",
        "hoje",
        "mundo",
        "notícia",
        "noticias",
        "news",
        "viral",
        "vídeo",
        "video",
    }
    CONTEXT_TERMS = {
        "ator",
        "cantor",
        "caso",
        "empresário",
        "entrevista",
        "escândalo",
        "humorista",
        "influenciador",
        "investigação",
        "jogador",
        "podcast",
        "polêmica",
        "revelou",
    }

    def extract(self, values: list[str]) -> list[str]:
        entities: list[str] = []
        for value in values:
            text = self._clean(value)
            entities.extend(self._capitalized_entities(text))
            entities.extend(self._context_entities(text))
            entities.extend(self._compound_terms(text))
        return self._dedupe_quality(entities)

    def _clean(self, text: str) -> str:
        cleaned = text
        for outlet in self.MEDIA_OUTLETS:
            cleaned = re.sub(rf"\b{re.escape(outlet)}\b", " ", cleaned, flags=re.I)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _capitalized_entities(self, text: str) -> list[str]:
        pattern = r"\b[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ'-]*(?:\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ'-]*){0,3}"
        return re.findall(pattern, text)

    def _context_entities(self, text: str) -> list[str]:
        entities: list[str] = []
        words = text.split()
        for index, word in enumerate(words):
            normalized = self._normalize(word)
            if normalized not in self.CONTEXT_TERMS:
                continue
            window = words[max(0, index - 3) : min(len(words), index + 4)]
            candidate = " ".join(window)
            candidate = re.sub(r"[^\wÀ-ÿ\s'-]", " ", candidate)
            entities.append(re.sub(r"\s+", " ", candidate).strip())
        return entities

    def _compound_terms(self, text: str) -> list[str]:
        words = [
            word
            for word in re.findall(r"\b[\wÀ-ÿ'-]{4,}\b", text)
            if self._normalize(word) not in self.GENERIC_TERMS
        ]
        terms: list[str] = []
        for index in range(max(0, len(words) - 1)):
            terms.append(" ".join(words[index : index + 2]))
        return terms

    def _dedupe_quality(self, entities: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for entity in entities:
            cleaned = self._trim(entity)
            normalized = self._normalize(cleaned)
            if not self._is_quality(cleaned, normalized) or normalized in seen:
                continue
            seen.add(normalized)
            result.append(cleaned)
            if len(result) >= 8:
                break
        return result

    def _is_quality(self, entity: str, normalized: str) -> bool:
        words = normalized.split()
        if len(words) > 6 or len(entity.replace(" ", "")) < 4:
            return False
        if normalized in self.GENERIC_TERMS:
            return False
        return any(word not in self.GENERIC_TERMS for word in words)

    @staticmethod
    def _trim(entity: str) -> str:
        cleaned = re.sub(r"[^\wÀ-ÿ\s'-]", " ", entity)
        return re.sub(r"\s+", " ", cleaned).strip(" -'")

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.lower()).strip()
