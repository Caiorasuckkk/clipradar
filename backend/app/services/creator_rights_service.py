from app.models import SourceVideo, TrendTopic


class CreatorRightsService:
    OFFICIAL_CLIPS_ECOSYSTEM = {
        "flow podcast": "Canal com ecossistema oficial de cortes; ainda exige validação do vídeo/canal.",
        "inteligência ltda": "Canal com ecossistema oficial de cortes; ainda exige validação do vídeo/canal.",
        "inteligencia ltda": "Canal com ecossistema oficial de cortes; ainda exige validação do vídeo/canal.",
        "podpah": "Canal com ecossistema oficial de cortes; ainda exige validação do vídeo/canal.",
        "cortes do flow": "Canal de cortes relacionado ao Flow.",
        "cortes do podcast": "Canal de cortes relacionado a podcast.",
    }
    HIGH_VALUE_REVIEW_CREATORS = {
        "mrbeast": "Criador de alto potencial, mas sem permissão blanket verificada; exige revisão.",
        "mr beast": "Criador de alto potencial, mas sem permissão blanket verificada; exige revisão.",
        "diary of a ceo": "Podcast internacional forte; exige revisão de licença/permissão.",
        "joe rogan": "Podcast internacional forte; exige revisão de licença/permissão.",
        "theo von": "Podcast internacional forte; exige revisão de licença/permissão.",
        "piers morgan": "Entrevistas com alto potencial; exige revisão de licença/permissão.",
        "hot ones": "Formato forte para cortes; exige revisão de licença/permissão.",
    }

    def annotate_video(self, video: SourceVideo) -> SourceVideo:
        text = f"{video.channel_title} {video.title}".lower()
        notes: list[str] = []

        if video.license == "creativeCommon":
            video.clip_permission_status = "creative_commons_review"
            video.clip_permission_score = 9.0
            notes.append("Vídeo marcado como Creative Commons na API; confirmar atribuição e uso antes de publicar.")
        elif match := self._match(text, self.OFFICIAL_CLIPS_ECOSYSTEM):
            video.clip_permission_status = "official_clips_ecosystem_review"
            video.clip_permission_score = 6.5
            notes.append(self.OFFICIAL_CLIPS_ECOSYSTEM[match])
        elif match := self._match(text, self.HIGH_VALUE_REVIEW_CREATORS):
            video.clip_permission_status = "high_value_needs_permission"
            video.clip_permission_score = 4.5
            notes.append(self.HIGH_VALUE_REVIEW_CREATORS[match])
        else:
            video.clip_permission_status = "needs_permission_review"
            video.clip_permission_score = 2.5
            notes.append("Sem licença/permissão detectada; usar apenas com autorização, licença clara ou transformação editorial robusta.")

        video.clip_permission_notes = notes
        return video

    def summarize_topic(self, topic: TrendTopic) -> TrendTopic:
        if not topic.videos:
            topic.clip_permission_score = 0.0
            topic.clip_permission_status = "not_validated"
            topic.needs_permission_review = True
            return topic

        statuses = [video.clip_permission_status for video in topic.videos]
        scores = [video.clip_permission_score for video in topic.videos]
        topic.clip_permission_score = round(max(scores or [0.0]), 2)

        if any(status == "creative_commons_review" for status in statuses):
            topic.clip_permission_status = "creative_commons_review"
        elif any(status == "official_clips_ecosystem_review" for status in statuses):
            topic.clip_permission_status = "official_clips_ecosystem_review"
        elif any(status == "high_value_needs_permission" for status in statuses):
            topic.clip_permission_status = "high_value_needs_permission"
        else:
            topic.clip_permission_status = "needs_permission_review"

        topic.needs_permission_review = topic.clip_permission_status not in {
            "creative_commons_review",
            "official_clips_ecosystem_review",
        }
        return topic

    @staticmethod
    def _match(text: str, profiles: dict[str, str]) -> str | None:
        for name in profiles:
            if name in text:
                return name
        return None
