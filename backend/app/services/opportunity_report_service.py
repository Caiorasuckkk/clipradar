import json
from datetime import datetime
from pathlib import Path
from statistics import mean

from app.config import REPORT_TOP_N, STORAGE_TRENDS_DIR
from app.models import SourceVideo, TrendTopic


REPORTS_DIR = STORAGE_TRENDS_DIR.parent / "reports"


class OpportunityReportService:
    def __init__(self, reports_dir: Path = REPORTS_DIR) -> None:
        self.reports_dir = reports_dir

    def generate(self, topics: list[TrendTopic], top_n: int = REPORT_TOP_N) -> tuple[Path, Path]:
        opportunities = self._opportunities(topics, limit=top_n)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        markdown_path = self.reports_dir / f"opportunity_report_{timestamp}.md"
        json_path = self.reports_dir / f"opportunity_report_{timestamp}.json"

        markdown_path.write_text(
            self.render_markdown(opportunities),
            encoding="utf-8",
        )
        json_path.write_text(
            json.dumps(self.render_json(opportunities), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return markdown_path, json_path

    @staticmethod
    def _opportunities(topics: list[TrendTopic], limit: int) -> list[TrendTopic]:
        filtered = [topic for topic in topics if topic.decision in {"produce", "review"}]
        return sorted(filtered, key=lambda topic: topic.opportunity_score, reverse=True)[:limit]

    def render_markdown(self, topics: list[TrendTopic]) -> str:
        lines = [
            "# ClipRadar Opportunity Report",
            "",
            f"Data de geração: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Top Opportunities",
            "",
        ]

        if not topics:
            lines.append("Nenhuma oportunidade classificada como produce ou review nesta execução.")
            lines.append("")
            return "\n".join(lines)

        for index, topic in enumerate(topics, start=1):
            lines.extend(self._topic_markdown(index, topic))

        return "\n".join(lines)

    def render_json(self, topics: list[TrendTopic]) -> dict:
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "opportunities_count": len(topics),
            "opportunities": [
                {
                    "rank": index,
                    "keyword": topic.keyword,
                    "market": topic.market,
                    "language": topic.language,
                    "decision": topic.decision,
                    "opportunity_score": topic.opportunity_score,
                    "suitability_score": topic.suitability_score,
                    "attention_score": topic.attention_score,
                    "attention_category": topic.attention_category,
                    "risk_score": topic.risk_score,
                    "needs_youtube_validation": topic.needs_youtube_validation,
                    "youtube_quota_limited": topic.youtube_quota_limited,
                    "clip_permission_score": topic.clip_permission_score,
                    "clip_permission_status": topic.clip_permission_status,
                    "needs_permission_review": topic.needs_permission_review,
                    "real_sources": topic.real_sources,
                    "mock_sources": topic.mock_sources,
                    "real_sources_count": topic.real_sources_count,
                    "mock_sources_count": topic.mock_sources_count,
                    "sources": topic.sources,
                    "extracted_entities": topic.extracted_entities,
                    "dynamic_queries": topic.dynamic_queries,
                    "dynamic_query_quality_score": topic.dynamic_query_quality_score,
                    "topic_origin": topic.topic_origin,
                    "topic_base_quality_score": topic.topic_base_quality_score,
                    "expansion_allowed": topic.expansion_allowed,
                    "expansion_block_reason": topic.expansion_block_reason,
                    "evidence_titles": topic.evidence_titles,
                    "evidence_urls": topic.evidence_urls,
                    "evidence_sources": topic.evidence_sources,
                    "original_keywords": topic.original_keywords,
                    "videos": [self._video_json(video) for video in topic.videos[:5]],
                    "why_this_may_work": self._why(topic),
                    "attention_signals": self._attention_signals(topic),
                    "debug_notes": self._debug_notes(topic),
                    "suggested_short_video_angles": self._angles(topic.keyword),
                }
                for index, topic in enumerate(topics, start=1)
            ],
        }

    def _topic_markdown(self, index: int, topic: TrendTopic) -> list[str]:
        lines = [
            f"### {index}. {topic.keyword}",
            "",
            f"Market: {topic.market}",
            f"Language: {topic.language}",
            f"Decision: {topic.decision}",
            f"Opportunity Score: {topic.opportunity_score:.2f}",
            f"Suitability Score: {topic.suitability_score:.2f}",
            f"Attention Score: {topic.attention_score:.2f}",
            f"Attention Category: {topic.attention_category}",
            f"Risk Score: {topic.risk_score:.2f}",
            f"Dynamic Query Quality Score: {topic.dynamic_query_quality_score:.2f}",
            f"Topic Base Quality Score: {topic.topic_base_quality_score:.2f}",
            f"Topic Origin: {topic.topic_origin}",
            f"Needs YouTube Validation: {str(topic.needs_youtube_validation).lower()}",
            f"YouTube Quota Limited: {str(topic.youtube_quota_limited).lower()}",
            f"Clip Permission Status: {topic.clip_permission_status}",
            f"Clip Permission Score: {topic.clip_permission_score:.2f}",
            f"Needs Permission Review: {str(topic.needs_permission_review).lower()}",
            f"Real Sources: {topic.real_sources_count}",
            f"Mock Sources: {topic.mock_sources_count}",
            f"Sources: {', '.join(topic.sources) if topic.sources else 'none'}",
            "",
            "#### Why this may work",
        ]
        lines.extend([f"- {reason}" for reason in self._why(topic)])
        lines.extend(["", "#### Attention Signals"])
        lines.extend([f"- {signal}" for signal in self._attention_signals(topic)])
        lines.extend(["", "#### Why this can become a clip"])
        lines.extend([f"- {reason}" for reason in self._clip_reasons(topic)])
        lines.extend(["", "#### Extracted Entities"])
        if topic.extracted_entities:
            lines.extend([f"- {entity}" for entity in topic.extracted_entities[:8]])
        else:
            lines.append("- Nenhuma entidade clara detectada.")
        lines.extend(["", "#### Dynamic Queries"])
        if topic.dynamic_queries:
            lines.extend([f"- {query}" for query in topic.dynamic_queries[:8]])
        else:
            lines.append("- Nenhuma query dinâmica gerada.")
        lines.extend(["", "#### Expansion Decision"])
        lines.append(f"- Allowed: {str(topic.expansion_allowed).lower()}")
        lines.append(f"- Base quality: {topic.topic_base_quality_score:.2f}")
        lines.append(f"- Reason: {topic.expansion_block_reason or 'expansão permitida'}")
        lines.append(
            f"- Dynamic queries generated: {len(topic.dynamic_queries)}"
        )
        lines.extend(["", "#### Evidence"])
        lines.extend(self._evidence_markdown(topic))
        lines.extend(["", "#### Original Keywords"])
        if topic.original_keywords:
            lines.extend([f"- {keyword}" for keyword in topic.original_keywords[:10]])
        else:
            lines.append("- Nenhuma keyword original registrada.")
        lines.extend(["", "#### Debug Notes"])
        lines.extend([f"- {note}" for note in self._debug_notes(topic)])
        lines.extend(["", "#### Videos Found"])

        if topic.videos:
            for video in topic.videos[:5]:
                lines.extend(self._video_markdown(video))
        else:
            lines.append("- Nenhum vídeo relacionado encontrado nesta execução.")

        lines.extend(["", "#### Suggested Short Video Angles"])
        lines.extend([f"- {angle}" for angle in self._angles(topic.keyword)])
        lines.append("")
        return lines

    @staticmethod
    def _evidence_markdown(topic: TrendTopic) -> list[str]:
        if not topic.evidence_titles and not topic.evidence_urls:
            return ["- Nenhuma evidência de sinal registrada."]

        rows: list[str] = []
        max_items = max(
            len(topic.evidence_titles),
            len(topic.evidence_urls),
            len(topic.evidence_sources),
        )
        for index in range(min(5, max_items)):
            source = _safe_get(topic.evidence_sources, index, "unknown")
            title = _safe_get(topic.evidence_titles, index, "")
            url = _safe_get(topic.evidence_urls, index, "")
            rows.append(f"- source: {source}")
            rows.append(f"  title: {title or 'n/a'}")
            rows.append(f"  url: {url or 'n/a'}")
        return rows

    @staticmethod
    def _video_markdown(video: SourceVideo) -> list[str]:
        return [
            f"- title: {video.title}",
            f"  channel_title: {video.channel_title}",
            f"  url: {video.url}",
            f"  view_count: {video.view_count}",
            f"  like_count: {video.like_count}",
            f"  comment_count: {video.comment_count}",
            f"  duration_seconds: {video.duration_seconds}",
            f"  engagement_score: {video.engagement_score:.2f}",
            f"  license: {video.license or 'unknown'}",
            f"  clip_permission_status: {video.clip_permission_status}",
            f"  clip_permission_score: {video.clip_permission_score:.2f}",
        ]

    @staticmethod
    def _video_json(video: SourceVideo) -> dict:
        return {
            "video_id": video.video_id,
            "title": video.title,
            "channel_title": video.channel_title,
            "url": video.url,
            "published_at": video.published_at.isoformat() if video.published_at else None,
            "view_count": video.view_count,
            "like_count": video.like_count,
            "comment_count": video.comment_count,
            "duration_seconds": video.duration_seconds,
            "engagement_score": video.engagement_score,
            "license": video.license,
            "clip_permission_status": video.clip_permission_status,
            "clip_permission_score": video.clip_permission_score,
            "clip_permission_notes": video.clip_permission_notes,
        }

    @staticmethod
    def _why(topic: TrendTopic) -> list[str]:
        reasons: list[str] = []
        if topic.real_sources_count >= 2:
            reasons.append("Aparece em múltiplas fontes reais, reduzindo dependência de mock.")
        elif topic.real_sources_count == 1:
            reasons.append("Foi encontrado em pelo menos uma fonte real de tendência.")
        if topic.videos:
            reasons.append(f"Tem {len(topic.videos)} vídeos relacionados encontrados no YouTube.")
            avg_engagement = mean(video.engagement_score for video in topic.videos)
            if avg_engagement >= 6:
                reasons.append("Os vídeos relacionados têm bom engajamento médio.")
        if topic.risk_score < 4:
            reasons.append("O risco editorial está baixo para uma pauta curta.")
        if topic.suitability_score >= 6:
            reasons.append("A adequação ao formato de conteúdo curto está boa.")
        if topic.mock_sources_count:
            reasons.append("Há sinais mockados, então a pauta deve ser revisada com mais cuidado.")
        if topic.needs_youtube_validation:
            reasons.append("Precisa de validação manual no YouTube porque a quota da API limitou esta execução.")
        if topic.needs_permission_review:
            reasons.append("Precisa revisar permissão/licença antes de qualquer publicação.")
        return reasons or ["Pontuação suficiente para revisão humana, mas requer validação editorial."]

    @staticmethod
    def _clip_reasons(topic: TrendTopic) -> list[str]:
        reasons: list[str] = []
        if topic.extracted_entities:
            reasons.append(f"Tem entidade/personagem claro: {topic.extracted_entities[0]}.")
        if topic.dynamic_queries:
            reasons.append("Gerou queries com intenção de podcast, entrevista ou corte.")
        if any(term in " ".join(topic.dynamic_queries).lower() for term in ["podcast", "entrevista", "interview", "corte", "funny", "bastidores"]):
            reasons.append("O formato sugerido favorece trecho curto, bastidor, humor ou fala comentável.")
        if topic.real_sources_count:
            reasons.append("A origem vem de fonte real recente, não de caso fixo manual.")
        if topic.videos:
            reasons.append("Já possui vídeos encontrados para validação de corte.")
        elif topic.needs_youtube_validation:
            reasons.append("A validação no YouTube ficou pendente por quota, então entra como revisão.")
        return reasons or ["Precisa de validação editorial antes de virar pauta de corte."]

    @staticmethod
    def _debug_notes(topic: TrendTopic) -> list[str]:
        notes: list[str] = []
        if topic.real_sources_count >= 2:
            notes.append("Veio de múltiplas fontes reais.")
        elif topic.real_sources_count == 1:
            notes.append("Tem apenas uma fonte real principal.")
        else:
            notes.append("Não há fonte real; depende de mock ou sinal fraco.")

        if topic.sources == ["youtube_popular"]:
            notes.append("Depende muito de YouTube Popular; revisar se há contexto fora da plataforma.")
        if topic.mock_sources_count:
            notes.append("Contém sinais mockados do fallback.")
        if 2 <= len(topic.keyword.split()) <= 6 and topic.suitability_score >= 6:
            notes.append("Keyword parece boa para revisão humana.")
        else:
            notes.append("Keyword parece fraca ou precisa de ajuste editorial.")
        if topic.evidence_titles:
            notes.append(f"{len(topic.evidence_titles)} títulos de evidência registrados.")
        if topic.youtube_quota_limited:
            notes.append("Modo degradado ativo: sem validação completa pela API do YouTube.")
        notes.append(f"Status de permissão para corte: {topic.clip_permission_status}.")
        return notes

    @staticmethod
    def _attention_signals(topic: TrendTopic) -> list[str]:
        signals: list[str] = []
        if any(source.startswith("youtube") for source in topic.real_sources):
            signals.append("Aparece em fontes do YouTube.")
        if "youtube_high_attention" in topic.real_sources:
            signals.append("Foi capturado pelo High Attention Radar.")
        text = " ".join([topic.keyword, *topic.evidence_titles, *topic.original_keywords]).lower()
        if any(term in text for term in ["podcast", "entrevista", "interview", "corte"]):
            signals.append("Tem indícios de podcast, entrevista ou corte viral.")
        if any(
            term in text
            for term in [
                "escândalo",
                "investigação",
                "polêmica",
                "fraude",
                "scandal",
                "investigation",
                "controversy",
                "fraud",
                "files",
                "lawsuit",
            ]
        ):
            signals.append("Contém gatilhos de polêmica, investigação ou caso judicial.")
        if any(source in topic.real_sources for source in ["trends_rss", "rss_news"]):
            signals.append("Tem validação por notícia/RSS.")
        if topic.videos:
            signals.append("Tem vídeos recentes ou relacionados encontrados.")
        return signals or ["Não há sinal forte de atenção; revisar manualmente."]

    @staticmethod
    def _angles(keyword: str) -> list[str]:
        return [
            f"Entenda por que {keyword} está em alta",
            f"O que você precisa saber sobre {keyword}",
            f"Por que {keyword} pode viralizar agora",
        ]


def _safe_get(values: list[str], index: int, default: str) -> str:
    try:
        return values[index]
    except IndexError:
        return default
