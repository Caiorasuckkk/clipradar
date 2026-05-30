from __future__ import annotations

import json
from typing import Any

from app.config import OPENAI_API_KEY


class MetadataService:
    def __init__(self, api_key: str = OPENAI_API_KEY) -> None:
        self.api_key = api_key.strip()

    def generate(
        self,
        clip_text: str,
        video_title: str,
        channel_name: str,
    ) -> dict[str, Any]:
        if not self.api_key:
            print("METADATA aviso: OPENAI_API_KEY ausente; usando placeholders.")
            return self._placeholder(clip_text)

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                max_tokens=400,
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é especialista em criar títulos virais para YouTube Shorts "
                            "e TikTok brasileiro. Seu objetivo é maximizar cliques e retenção."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._prompt(clip_text, video_title, channel_name),
                    },
                ],
            )
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
            return {
                "suggested_title": parsed.get("titulo", ""),
                "description": parsed.get("descricao", ""),
                "hashtags": parsed.get("hashtags", []),
                "hook": parsed.get("gancho", ""),
                "viral_reason": parsed.get("motivo_viral", ""),
            }
        except Exception as exc:
            print(f"METADATA falhou: {exc}; usando placeholders.")
            return self._placeholder(clip_text)

    @staticmethod
    def _prompt(clip_text: str, video_title: str, channel_name: str) -> str:
        return f"""
Canal de origem: {channel_name}
Tema do episódio: {video_title}
Trecho (30-60s):
---
{clip_text}
---

Retorne SOMENTE um JSON válido sem markdown:
{{
  "titulo": "título chamativo em PT-BR, máx 60 chars, sem clickbait vazio",
  "descricao": "descrição curta em PT-BR, 2-3 frases, com contexto",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
  "gancho": "primeira frase para ganhar atenção em 3 segundos",
  "motivo_viral": "por que esse trecho tem potencial viral — 1 frase"
}}
""".strip()

    @staticmethod
    def _placeholder(clip_text: str) -> dict[str, Any]:
        words = clip_text.split()
        title = " ".join(words[:8])[:60] if words else "Trecho com potencial"
        return {
            "suggested_title": title,
            "description": "Placeholder local: revise o trecho e ajuste o contexto antes de publicar.",
            "hashtags": ["#shorts", "#cortes", "#podcast"],
            "hook": " ".join(words[:15]) if words else "",
            "viral_reason": "Trecho selecionado por gatilhos locais de retenção.",
        }
