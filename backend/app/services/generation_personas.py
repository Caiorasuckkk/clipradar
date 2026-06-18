"""Generation "studios" (personas).

Each persona is a full preset bundle for a niche channel: a scriptwriter voice
(prompt), niche/tone/narrative style, narrator voice + speed, background-music
mood and a visual style. Picking a studio tunes the whole pipeline at once so
every video of that channel is consistent and on-brand.
"""
from __future__ import annotations

from typing import Any


PERSONAS: list[dict[str, Any]] = [
    {
        "id": "historico",
        "label": "Histórico & Curiosidades",
        "description": (
            "Histórias e curiosidades reais contadas com gancho forte: prende nos "
            "2 primeiros segundos, uma curiosidade central, e um final que surpreende."
        ),
        "icon": "auto_stories",
        "accent": "warning",
        "niche": "história e curiosidades",
        "tone": "curioso",
        "narrative_style": "documentary",
        "scriptwriter": (
            "Você é um contador de histórias e curiosidades reais, apaixonado por fatos "
            "fascinantes da história. Transforme fatos verídicos em uma narrativa curta e "
            "envolvente para vídeos verticais (Shorts/Reels). REGRAS: (1) Abra com um GANCHO "
            "forte nos 2 primeiros segundos — uma pergunta intrigante ou um fato chocante. "
            "(2) Conte UMA curiosidade central com contexto, tensão e emoção. (3) Termine com "
            "um payoff que surpreende ou faz pensar. Use linguagem simples, popular e direta, "
            "como quem conta um segredo para um amigo. Nada de aula chata."
        ),
        "voice": "openai:onyx",
        "speed": "normal",
        "music_mood": "dramatico",
        "visual_style": "historically accurate, period, realistic, cinematic",
    },
]

_BY_ID = {p["id"]: p for p in PERSONAS}

# Fields safe to expose to the app (no internal-only data; all are fine here).
_PUBLIC_FIELDS = ("id", "label", "description", "icon", "accent", "voice")


def list_personas() -> list[dict[str, Any]]:
    return [{k: p[k] for k in _PUBLIC_FIELDS} for p in PERSONAS]


def get_persona(persona_id: str) -> dict[str, Any] | None:
    return _BY_ID.get(str(persona_id or "").strip().lower())
