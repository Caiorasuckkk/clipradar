from app.models import TrendTopic


class TopicBaseQualityService:
    REAL_SOURCE_BONUS = {"trends_rss", "rss_news", "youtube_popular", "youtube_trending"}
    ENTITY_HINTS = {
        "ator",
        "cantor",
        "celebridade",
        "clube",
        "empresa",
        "empresário",
        "famoso",
        "humorista",
        "influenciador",
        "jogador",
        "político",
        "podcast",
        "youtuber",
        "actor",
        "celebrity",
        "company",
        "influencer",
        "politician",
    }
    CLIP_SIGNALS = {
        "acusação",
        "bastidores",
        "debate",
        "engraçado",
        "entrevista",
        "escândalo",
        "fraude",
        "história",
        "investigação",
        "podcast",
        "polêmica",
        "processo",
        "revelou",
        "accusation",
        "backstage",
        "debate",
        "funny",
        "fraud",
        "interview",
        "investigation",
        "podcast",
        "revealed",
        "scandal",
    }
    BAD_CONTEXT = {
        "amazon",
        "colisão",
        "ecommerce",
        "frontal",
        "lounge chair",
        "recall",
        "rodovia",
        "trânsito",
    }
    PUBLIC_CASE_TERMS = {
        "celebridade",
        "deputado",
        "empresário",
        "famoso",
        "influenciador",
        "ministro",
        "político",
        "presidente",
        "senador",
        "ator",
        "cantor",
        "humorista",
    }
    LOCAL_SPORT_HINTS = {" vs ", " x ", "fc", "central", "guardians", "red sox"}
    GENERIC = {"brasil", "mundo", "news", "notícia", "viral", "hoje", "agora"}

    def score_topic(self, topic: TrendTopic) -> tuple[float, bool, str]:
        text = self._text(topic)
        keyword_words = topic.normalized_keyword.split()
        score = 2.5

        if any(source in topic.real_sources for source in self.REAL_SOURCE_BONUS):
            score += 1.5
        if topic.real_sources_count >= 2:
            score += 1.0
        if topic.evidence_titles:
            score += 1.0
        if topic.extracted_entities:
            score += min(1.5, len(topic.extracted_entities) * 0.5)
        if self._has_any(text, self.ENTITY_HINTS):
            score += 1.0
        if self._has_any(text, self.CLIP_SIGNALS):
            score += 1.5
        if 2 <= len(keyword_words) <= 6:
            score += 0.6

        if self._has_any(text, self.BAD_CONTEXT):
            score -= 4.0
        if self._looks_like_local_sport(topic, text):
            score -= 2.0
        if len(keyword_words) < 2 or topic.normalized_keyword in self.GENERIC:
            score -= 1.5
        if not topic.evidence_titles:
            score -= 1.5
        if self._looks_like_random_name_without_context(topic, text):
            score -= 1.5

        score = round(max(0.0, min(10.0, score)), 2)
        evidence_allows = self.has_strong_evidence(text)
        hard_block = self._hard_block_expansion(topic, text)
        allowed = not hard_block and (score >= 5.0 or evidence_allows)
        reason = "" if allowed else self._block_reason(topic, text, score)
        return score, allowed, reason

    def has_strong_evidence(self, text: str) -> bool:
        return self._has_any(text.lower(), self.CLIP_SIGNALS | self.ENTITY_HINTS)

    def _block_reason(self, topic: TrendTopic, text: str, score: float) -> str:
        if self._has_any(text, self.BAD_CONTEXT):
            return "produto/acidente/assunto local sem evidência forte de corte"
        if self._looks_like_local_sport(topic, text):
            return "esporte local sem apelo nacional/global claro"
        if not topic.evidence_titles:
            return "sem evidence_title útil"
        if not topic.extracted_entities:
            return "sem entidade forte detectada"
        return f"base_quality abaixo do mínimo ({score:.2f})"

    def _hard_block_expansion(self, topic: TrendTopic, text: str) -> bool:
        if self._has_any(text, self.BAD_CONTEXT) and not self._has_any(text, self.PUBLIC_CASE_TERMS):
            return True
        if self._looks_like_local_sport(topic, text):
            return True
        return False

    def _looks_like_local_sport(self, topic: TrendTopic, text: str) -> bool:
        if not any(term in text for term in self.LOCAL_SPORT_HINTS):
            return False
        national_terms = {"flamengo", "corinthians", "palmeiras", "champions", "world cup", "nba"}
        return not any(term in text for term in national_terms)

    @staticmethod
    def _looks_like_random_name_without_context(topic: TrendTopic, text: str) -> bool:
        words = topic.normalized_keyword.split()
        if len(words) not in {2, 3}:
            return False
        context = TopicBaseQualityService.CLIP_SIGNALS | TopicBaseQualityService.ENTITY_HINTS
        return not any(term in text for term in context)

    @staticmethod
    def _has_any(text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)

    @staticmethod
    def _text(topic: TrendTopic) -> str:
        return " ".join(
            [
                topic.keyword,
                topic.normalized_keyword,
                " ".join(topic.evidence_titles),
                " ".join(topic.evidence_sources),
                " ".join(topic.original_keywords),
                " ".join(topic.extracted_entities),
                " ".join(topic.sources),
            ]
        ).lower()
