from app.models import TrendTopic


class NoiseFilterService:
    VERBOS_RUIDO = {
        "inicia",
        "negocia",
        "coleciona",
        "lança",
        "anuncia",
        "revela",
        "comenta",
        "critica",
        "defende",
        "ataca",
        "starts",
        "launches",
        "announces",
        "says",
        "gets",
        "lands",
    }
    KNOWN_ENTITIES = {
        "banco",
        "master",
        "lula",
        "stf",
        "trump",
        "epstein",
        "diddy",
        "pcc",
        "congresso",
        "senado",
        "governo",
        "polícia",
        "police",
        "court",
        "bank",
        "government",
    }
    TRIGGER_WORDS = {
        "acusação",
        "denúncia",
        "escândalo",
        "fraude",
        "investigação",
        "polêmica",
        "prisão",
        "processo",
        "vazamento",
        "arrest",
        "controversy",
        "fraud",
        "investigation",
        "lawsuit",
        "leaked",
        "scandal",
    }
    MUSIC_NOISE = {
        "album",
        "lemonade",
        "lyrics",
        "music",
        "mv",
        "official video",
        "song",
        "álbum",
        "clipe",
        "letra",
        "música",
    }
    GENERIC_ONLY = {
        "brasil",
        "global",
        "news",
        "notícias",
        "opinion",
        "technology",
        "tecnologia",
        "viral",
    }

    def is_noisy(self, topic: TrendTopic) -> bool:
        text = self._text(topic)
        keyword = topic.normalized_keyword.strip()
        words = keyword.split()

        if keyword in self.GENERIC_ONLY:
            return True
        if len(words) < 2:
            return True
        if any(term in text for term in self.MUSIC_NOISE) and topic.attention_score < 6:
            return True
        if self._looks_like_news_fragment(text):
            return True
        if topic.attention_score < 1.5 and not self._has_trigger(text):
            return True
        if topic.sources == ["youtube_popular"] and topic.attention_score < 6:
            return True
        if "watchlist" in topic.real_sources and topic.attention_score >= 3.5:
            return False
        if topic.real_sources_count == 0 and not topic.quota_exhausted:
            return True
        return False

    def _looks_like_news_fragment(self, text: str) -> bool:
        has_verb = any(verb in text.split() for verb in self.VERBOS_RUIDO)
        has_context = any(term in text for term in self.KNOWN_ENTITIES | self.TRIGGER_WORDS)
        return has_verb and not has_context

    def _has_trigger(self, text: str) -> bool:
        return any(term in text for term in self.TRIGGER_WORDS)

    @staticmethod
    def _text(topic: TrendTopic) -> str:
        return " ".join(
            [
                topic.keyword,
                topic.normalized_keyword,
                " ".join(topic.original_keywords),
                " ".join(topic.evidence_titles),
            ]
        ).lower()
