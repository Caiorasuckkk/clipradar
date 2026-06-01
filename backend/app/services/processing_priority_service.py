from __future__ import annotations

import re
from typing import Any


class ProcessingPriorityService:
    PODCAST_TERMS = {
        "podcast", "entrevista", "ticaracaticast", "flow", "podpah",
        "inteligência ltda", "inteligencia ltda", "venus podcast",
        "papo de elite", "oestecast", "the noite", "achismos",
        "achismos tv", "nômade raiz", "nomade raiz", "rango brabo",
        "quebrada fc", "podpah visita", "podpah de verão",
        "podpah de verao",
    }
    CLIP_POTENTIAL_TERMS = {
        "escândalo", "escandalo", "crime", "política", "politica",
        "segurança pública", "seguranca publica", "operação", "operacao",
        "entrevista", "conversa", "bastidores", "revelou", "história",
        "historia", "humorista", "jogador", "cantor", "ator",
        "corrupção", "corrupcao", "investigação", "investigacao",
        "denúncia", "denuncia", "banco master", "relato", "perrengue",
        "viagem", "cultura", "experiência", "experiencia", "debate",
        "opinião", "opiniao", "curiosidade", "curiosidades", "perigo",
        "perigoso", "perigosos", "mundo", "realidade", "favela",
        "futebol", "famoso", "empresário", "empresario", "fortuna",
        "ciência", "ciencia", "comportamento", "sociedade",
    }
    SHORT_TERMS = {"#shorts", "shorts", "shortvideo", "#short", "short "}
    GENERIC_TERMS = {"🤔", "?", "ao vivo", "live", "viral", "completo"}

    def score_video(self, video: dict[str, Any]) -> tuple[float, str]:
        status = str(video.get("status", ""))
        if status in {"done", "error", "rejected", "rejected_queue"}:
            return 0.0, f"status {status} nao processavel"

        title = str(video.get("title", ""))
        channel = str(video.get("channel_name") or video.get("channel_title") or "")
        text = f"{title} {channel}".lower()
        duration = self._to_int(video.get("duration_seconds"))
        engagement = self._to_float(video.get("engagement_score"))
        views = self._to_int(video.get("view_count"))
        comments = self._to_int(video.get("comment_count"))
        likes = self._to_int(video.get("like_count"))

        score = 0.0
        reasons: list[str] = []

        score += min(2.0, engagement / 5)
        reasons.append(f"engagement {engagement:.2f}")

        if duration >= 480:
            score += 2.0
            reasons.append("video longo/podcast")
        elif duration >= 300:
            score += 1.0
            reasons.append("duracao media")
        elif duration < 120:
            score -= 3.0
            reasons.append("duracao menor que 120s")
        elif duration < 300:
            score -= 1.0
            reasons.append("duracao curta")

        podcast_hits = self._hits(text, self.PODCAST_TERMS)
        if podcast_hits:
            score += 2.0
            reasons.append(f"fonte/formato forte: {', '.join(podcast_hits[:3])}")

        potential_hits = self._hits(text, self.CLIP_POTENTIAL_TERMS)
        if potential_hits:
            score += min(2.0, 0.5 * len(potential_hits))
            reasons.append(f"potencial corte: {', '.join(potential_hits[:4])}")

        if views >= 1_000_000:
            score += 1.0
            reasons.append("views muito altos")
        elif views >= 100_000:
            score += 0.7
            reasons.append("views altos")
        elif views >= 10_000:
            score += 0.3
            reasons.append("views moderados")

        if comments >= 1000:
            score += 0.8
            reasons.append("muitos comentarios")
        elif comments >= 100:
            score += 0.4
            reasons.append("comentarios relevantes")

        if likes <= 0 and comments <= 0:
            score -= 1.0
            reasons.append("likes/comentarios baixos")
        if engagement < 5:
            score -= 1.5
            reasons.append("engagement menor que 5")

        if self._hits(text, self.SHORT_TERMS):
            score -= 4.0
            reasons.append("shorts/shortvideo")
        if self.is_generic_title(title):
            score -= 3.0
            reasons.append("titulo generico/emoji")

        if duration < 300 and not self._is_validated_short_clip(text):
            score = min(score, 4.0)
            reasons.append("capado por duracao curta sem corte validado")

        return round(max(0.0, min(10.0, score)), 2), "; ".join(reasons)

    def should_reject_queue(self, video: dict[str, Any]) -> tuple[bool, str]:
        title = str(video.get("title", ""))
        text = f"{title} {video.get('channel_name') or video.get('channel_title') or ''}".lower()
        duration = self._to_int(video.get("duration_seconds"))
        engagement = self._to_float(video.get("engagement_score"))

        if duration < 120:
            return True, "duration_seconds < 120"
        if self._hits(text, self.SHORT_TERMS):
            return True, "titulo/canal contem shorts"
        if engagement < 5:
            return True, "engagement_score < 5"
        if self.is_generic_title(title):
            return True, "titulo generico ou emoji"
        return False, ""

    def is_generic_title(self, title: str) -> bool:
        clean = re.sub(r"\s+", " ", title).strip()
        if not clean:
            return True
        words = re.findall(r"[A-Za-zÀ-ÿ0-9]{2,}", clean)
        if len(words) < 2:
            return True
        letters = re.findall(r"[A-Za-zÀ-ÿ]", clean)
        if len(letters) < 6:
            return True
        lowered = clean.lower()
        return lowered in self.GENERIC_TERMS

    def _is_validated_short_clip(self, text: str) -> bool:
        return any(
            term in text
            for term in {
                "cortes", "corte", "podcast", "entrevista", "relato",
                "história", "historia", "bastidores", "viagem",
            }
        )

    @staticmethod
    def _hits(text: str, terms: set[str]) -> list[str]:
        return [term for term in terms if term in text]

    @staticmethod
    def _to_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_float(value: object) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
