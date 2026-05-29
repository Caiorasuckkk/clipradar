import re

from app.models import TrendTopic


class ContentSuitabilityService:
    POSITIVE_TERMS = {
        "ai",
        "artificial intelligence",
        "business",
        "cinema",
        "creator economy",
        "economia",
        "esporte",
        "futebol",
        "games",
        "global",
        "ia",
        "inteligência artificial",
        "negócios",
        "news",
        "notícia",
        "tecnologia",
        "technology",
    }

    MUSIC_TERMS = {
        "album",
        "álbum",
        "cantor",
        "cantora",
        "clipe",
        "concert",
        "lemonade",
        "letra",
        "live performance",
        "lyrics",
        "music",
        "música",
        "mv",
        "official video",
        "show",
        "song",
        "teaser",
        "tour",
        "turnê",
    }

    GENERIC_TERMS = {
        "brasil",
        "business",
        "economia",
        "global news",
        "news",
        "notícias",
        "technology",
        "tecnologia",
        "viral",
    }

    def score_topic(self, topic: TrendTopic) -> float:
        keyword = topic.normalized_keyword or topic.keyword.lower()
        text = self._topic_text(topic)
        words_count = len(keyword.split())
        score = 5.0

        if 2 <= words_count <= 6:
            score += 1.2
        elif words_count == 1:
            score -= 1.6
        else:
            score -= 0.8

        if self._has_any(text, self.POSITIVE_TERMS):
            score += 1.3
        if topic.real_sources_count >= 2:
            score += 1.5
        if topic.videos:
            score += 0.8
        if "google_news" in topic.real_sources and "youtube_popular" in topic.real_sources:
            score += 1.0
        if self._looks_like_curiosity(keyword):
            score += 0.8

        if self.is_music_only(topic):
            score -= 4.0
        if self._has_many_non_latin(topic.keyword):
            score -= 2.0
        if self._looks_like_celebrity_only(topic):
            score -= 2.0
        if keyword in self.GENERIC_TERMS:
            score -= 2.5
        if topic.sources == ["youtube_popular"]:
            score -= 4.0
        if topic.real_signals_count == 0:
            score -= 3.5

        return round(max(0.0, min(10.0, score)), 2)

    def is_music_only(self, topic: TrendTopic) -> bool:
        text = self._topic_text(topic)
        has_music_term = self._has_any(text, self.MUSIC_TERMS)
        youtube_only = topic.sources == ["youtube_popular"]
        likely_short_name = len(topic.normalized_keyword.split()) <= 4
        return has_music_term or (youtube_only and likely_short_name and not self._has_news_context(text))

    @staticmethod
    def _topic_text(topic: TrendTopic) -> str:
        video_titles = " ".join(video.title for video in topic.videos[:5])
        return f"{topic.keyword} {topic.normalized_keyword} {video_titles}".lower()

    @staticmethod
    def _has_any(text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)

    @staticmethod
    def _has_many_non_latin(text: str) -> bool:
        non_latin = len(re.findall(r"[^A-Za-zÀ-ÿ0-9\s.,:;!?%$€£@#&'\"()/+-]", text))
        useful = max(1, len(re.sub(r"\s+", "", text)))
        return non_latin / useful > 0.2

    @staticmethod
    def _looks_like_celebrity_only(topic: TrendTopic) -> bool:
        words = topic.normalized_keyword.split()
        if len(words) not in {2, 3}:
            return False
        has_context_source = any(source in topic.real_sources for source in ["google_news", "rss_news"])
        title_case_name = all(word[:1].isalpha() for word in words)
        return title_case_name and topic.sources == ["youtube_popular"] and not has_context_source

    @staticmethod
    def _has_news_context(text: str) -> bool:
        terms = {
            "ai",
            "business",
            "economia",
            "explained",
            "futebol",
            "games",
            "how",
            "ia",
            "news",
            "notícia",
            "por que",
            "tecnologia",
            "technology",
            "why",
        }
        return any(term in text for term in terms)

    @staticmethod
    def _looks_like_curiosity(keyword: str) -> bool:
        return any(term in keyword for term in ["como", "por que", "why", "how", "explained"])
