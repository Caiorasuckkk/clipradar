from app.config import DYNAMIC_QUERIES_PER_TOPIC, DYNAMIC_QUERY_MIN_SCORE
from app.models import TrendTopic
from app.services.dynamic_query_quality_service import DynamicQueryQualityService


class DynamicQueryExpansionService:
    BR_TEMPLATES = [
        "{entity} podcast",
        "{entity} entrevista",
        "{entity} cortes",
        "{entity} Flow",
        "{entity} Podpah",
        "{entity} Inteligência Ltda",
        "{entity} Ticaracaticast",
        "{entity} RedCast",
        "{entity} história engraçada",
        "{entity} bastidores",
        "{entity} polêmica",

        "{entity} Raiam Santos",
    ]
    GLOBAL_TEMPLATES = [
        "{entity} podcast",
        "{entity} interview",
        "{entity} podcast clip",
        "{entity} funny moment",
        "{entity} revealed",
        "{entity} backstage story",
        "{entity} Joe Rogan",
        "{entity} Theo Von",
        "{entity} Piers Morgan",
        "{entity} Hot Ones",
    ]
    PODCAST_TERMS = {"podcast", "entrevista", "interview", "famoso", "humorista", "funny"}
    CONTROVERSY_TERMS = {
        "acusação",
        "caso",
        "escândalo",
        "fraude",
        "investigação",
        "polêmica",
        "processo",
        "scandal",
        "investigation",
        "lawsuit",
    }
    SPORT_TERMS = {"futebol", "football", "soccer", " vs ", " x ", "fc", "red sox"}
    ACCIDENT_TERMS = {"acidente", "colisão", "frontal", "trânsito", "rodovia"}
    NATIONAL_SPORT_TERMS = {"flamengo", "corinthians", "palmeiras", "champions", "world cup", "nba"}

    def __init__(
        self,
        quality_service: DynamicQueryQualityService | None = None,
        queries_per_topic: int = DYNAMIC_QUERIES_PER_TOPIC,
        min_score: float = DYNAMIC_QUERY_MIN_SCORE,
    ) -> None:
        self.quality_service = quality_service or DynamicQueryQualityService()
        self.queries_per_topic = queries_per_topic
        self.min_score = min_score

    def expand_topic(self, topic: TrendTopic) -> TrendTopic:
        if not topic.expansion_allowed:
            topic.dynamic_queries = self._neutral_query(topic)
            topic.dynamic_query_quality_score = min(topic.topic_base_quality_score, 3.0)
            return topic

        evidence = self._evidence_text(topic)
        if self._should_block_by_context(topic, evidence):
            topic.expansion_allowed = False
            topic.expansion_block_reason = "contexto original não sustenta podcast/escândalo/corte"
            topic.dynamic_queries = []
            topic.dynamic_query_quality_score = 0.0
            return topic

        candidates: list[tuple[float, str]] = []
        for entity in topic.extracted_entities[:5]:
            for template in self._templates(topic):
                if not self._template_allowed(template, evidence, entity):
                    continue
                query = self._clean_query(template.format(entity=entity))
                if not query:
                    continue
                score = self.quality_service.score(
                    query,
                    entity,
                    real_source=topic.real_sources_count > 0,
                    topic_base_quality_score=topic.topic_base_quality_score,
                    strong_evidence=self._has_strong_evidence(evidence),
                )
                if score >= self.min_score:
                    candidates.append((score, query))

        deduped: dict[str, float] = {}
        for score, query in candidates:
            deduped[query.lower()] = max(score, deduped.get(query.lower(), 0.0))

        ranked = sorted(((score, query) for query, score in deduped.items()), reverse=True)
        topic.dynamic_queries = [query for _, query in ranked[: self.queries_per_topic]]
        topic.dynamic_query_quality_score = (
            round(sum(score for score, _ in ranked[: self.queries_per_topic]) / len(ranked[: self.queries_per_topic]), 2)
            if ranked[: self.queries_per_topic]
            else 0.0
        )
        return topic

    def _templates(self, topic: TrendTopic) -> list[str]:
        return self.BR_TEMPLATES if topic.market == "BR" else self.GLOBAL_TEMPLATES

    def _template_allowed(self, template: str, evidence: str, entity: str) -> bool:
        lowered_template = template.lower()
        if "scandal" in lowered_template or "escândalo" in lowered_template or "polêmica" in lowered_template:
            return any(term in evidence for term in self.CONTROVERSY_TERMS)
        if "podcast" in lowered_template and not entity:
            return False
        if any(term in lowered_template for term in ["podcast", "entrevista", "interview", "cortes"]):
            return any(term in evidence for term in self.PODCAST_TERMS | self.CONTROVERSY_TERMS)
        return True

    def _should_block_by_context(self, topic: TrendTopic, evidence: str) -> bool:
        if any(term in evidence for term in self.ACCIDENT_TERMS) and not any(
            term in evidence for term in self.CONTROVERSY_TERMS | self.PODCAST_TERMS
        ):
            return True
        if any(term in evidence for term in self.SPORT_TERMS) and not any(
            term in evidence for term in self.NATIONAL_SPORT_TERMS
        ):
            return True
        return topic.topic_base_quality_score < 4 and not self._has_strong_evidence(evidence)

    def _neutral_query(self, topic: TrendTopic) -> list[str]:
        if topic.topic_base_quality_score >= 4 and topic.extracted_entities:
            return [topic.extracted_entities[0]]
        return []

    def _has_strong_evidence(self, evidence: str) -> bool:
        return any(term in evidence for term in self.PODCAST_TERMS | self.CONTROVERSY_TERMS)

    @staticmethod
    def _evidence_text(topic: TrendTopic) -> str:
        return " ".join(
            [
                topic.keyword,
                " ".join(topic.evidence_titles),
                " ".join(topic.original_keywords),
                " ".join(topic.extracted_entities),
            ]
        ).lower()

    @staticmethod
    def _clean_query(query: str) -> str:
        cleaned = " ".join(query.split()).strip()
        words = cleaned.lower().split()
        if len(words) != len(list(dict.fromkeys(words))):
            return ""
        if len(words) > 8:
            return ""
        return cleaned
