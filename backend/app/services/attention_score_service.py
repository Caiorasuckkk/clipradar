import re

from app.models import TrendTopic


class AttentionScoreService:
    TRIGGERS_PT = {
        "acusação",
        "denúncia",
        "escândalo",
        "fraude",
        "investigação",
        "operação",
        "polêmica",
        "prisão",
        "processo",
        "revelou",
        "vazamento",
    }
    TRIGGERS_EN = {
        "allegations",
        "arrest",
        "controversy",
        "court",
        "exposed",
        "files",
        "fraud",
        "investigation",
        "lawsuit",
        "leak",
        "podcast",
        "revealed",
        "scandal",
    }
    PUBLIC_ENTITY_TERMS = {
        "banco",
        "bank",
        "case",
        "caso",
        "celebrity",
        "empresa",
        "famoso",
        "influencer",
        "master",
        "político",
        "politician",
        "presidente",
    }
    CATEGORY_RULES = [
        ("financial_scandal", {"banco", "bank", "financeiro", "financial", "fraud", "fraude"}),
        ("podcast_viral", {"podcast", "corte", "clip", "entrevista", "interview"}),
        ("celebrity_scandal", {"celebrity", "famoso", "diddy", "epstein", "scandal"}),
        ("politics", {"política", "politico", "político", "government", "presidente", "senado"}),
        ("crime_investigation", {"crime", "investigação", "investigation", "prisão", "arrest"}),
        ("influencer_drama", {"influencer", "influenciador", "tiktoker", "youtuber"}),
        ("business_controversy", {"empresa", "company", "business", "controversy"}),
        ("international_case", {"epstein", "diddy", "global", "international", "files"}),
        ("sports_controversy", {"futebol", "football", "corinthians", "patrocínio"}),
        ("tech_controversy", {"tecnologia", "technology", "ai", "ia", "dados", "data"}),
    ]
    MUSIC_TERMS = {"music", "song", "lyrics", "official video", "lemonade", "clipe", "música"}
    GENERIC_TERMS = {"brasil", "news", "viral", "technology", "tecnologia", "opinion"}

    def score_topic(self, topic: TrendTopic) -> tuple[float, str]:
        text = self._topic_text(topic)
        score = 0.0

        trigger_hits = self._hits(text, self.TRIGGERS_PT | self.TRIGGERS_EN)
        score += min(3.0, trigger_hits * 0.9)
        if "youtube_high_attention" in topic.real_sources:
            score += 2.0
        if "watchlist" in topic.real_sources:
            score += 1.5
        if any(source.startswith("youtube") for source in topic.real_sources):
            score += 1.0
        if topic.videos:
            score += 1.2
        if self._has_podcast_or_interview(text):
            score += 1.2
        if any(source in topic.real_sources for source in ["trends_rss", "rss_news"]):
            score += 1.0
        if "trends_rss" in topic.real_sources:
            score += 0.5
        if self._hits(text, self.PUBLIC_ENTITY_TERMS):
            score += 1.0
        if topic.evidence_titles:
            score += 0.6

        if self._is_music_or_generic_noise(text, topic):
            score -= 3.0
        if not topic.quota_exhausted:
            if topic.real_sources_count == 0:
                score -= 3.0
            if not topic.evidence_titles:
                score -= 1.0
        else:
            score -= 1.0
            score += 0.5
        if topic.risk_score >= 6 and not any(source in topic.real_sources for source in ["trends_rss", "rss_news"]):
            score -= 2.0

        category = self.category(text, score)
        return round(max(0.0, min(10.0, score)), 2), category

    def category(self, text: str, score: float) -> str:
        for category, terms in self.CATEGORY_RULES:
            if self._hits(text, terms):
                return category
        if score >= 5:
            return "general_attention"
        if score < 2.0:
            return "noise"
        return "unknown"

    @staticmethod
    def _topic_text(topic: TrendTopic) -> str:
        evidence = " ".join(topic.evidence_titles[:5])
        videos = " ".join(video.title for video in topic.videos[:5])
        keywords = " ".join(topic.original_keywords[:8])
        return f"{topic.keyword} {topic.normalized_keyword} {keywords} {evidence} {videos}".lower()

    @staticmethod
    def _hits(text: str, terms: set[str]) -> int:
        return sum(1 for term in terms if term in text)

    @staticmethod
    def _has_podcast_or_interview(text: str) -> bool:
        return any(term in text for term in ["podcast", "entrevista", "interview", "corte", "clip"])

    def _is_music_or_generic_noise(self, text: str, topic: TrendTopic) -> bool:
        if any(term in text for term in self.MUSIC_TERMS):
            return True
        keyword = topic.normalized_keyword.strip()
        if keyword in self.GENERIC_TERMS:
            return True
        non_latin = len(re.findall(r"[^A-Za-zÀ-ÿ0-9\s.,:;!?%$€£@#&'\"()/+-]", topic.keyword))
        useful = max(1, len(re.sub(r"\s+", "", topic.keyword)))
        return non_latin / useful > 0.2
