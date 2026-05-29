import json
from datetime import datetime
from pathlib import Path
from statistics import mean

from app.config import STORAGE_TRENDS_DIR
from app.models import SourceVideo, TrendTopic


REPORTS_DIR = STORAGE_TRENDS_DIR.parent / "reports"


class OpportunityReportService:
    def __init__(self, reports_dir: Path = REPORTS_DIR) -> None:
        self.reports_dir = reports_dir

    def generate(self, topics: list[TrendTopic], limit: int = 10) -> tuple[Path, Path]:
        opportunities = self._opportunities(topics, limit=limit)
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
                    "risk_score": topic.risk_score,
                    "real_sources": topic.real_sources,
                    "mock_sources": topic.mock_sources,
                    "real_sources_count": topic.real_sources_count,
                    "mock_sources_count": topic.mock_sources_count,
                    "sources": topic.sources,
                    "videos": [self._video_json(video) for video in topic.videos[:5]],
                    "why_this_may_work": self._why(topic),
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
            f"Risk Score: {topic.risk_score:.2f}",
            f"Real Sources: {topic.real_sources_count}",
            f"Mock Sources: {topic.mock_sources_count}",
            f"Sources: {', '.join(topic.sources) if topic.sources else 'none'}",
            "",
            "#### Why this may work",
        ]
        lines.extend([f"- {reason}" for reason in self._why(topic)])
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
        return reasons or ["Pontuação suficiente para revisão humana, mas requer validação editorial."]

    @staticmethod
    def _angles(keyword: str) -> list[str]:
        return [
            f"Entenda por que {keyword} está em alta",
            f"O que você precisa saber sobre {keyword}",
            f"Por que {keyword} pode viralizar agora",
        ]
