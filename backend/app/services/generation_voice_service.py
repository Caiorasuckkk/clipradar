from __future__ import annotations

import asyncio
import importlib.util
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.services.generation_workspace_service import get_project, update_project


AUDIO_DIR = config.STORAGE_GENERATION_DIR / "audio"
DEFAULT_VOICES = [
    {"name": "pt-BR-AntonioNeural", "label": "Antônio", "locale": "pt-BR", "gender": "male", "provider": "edge-tts"},
    {"name": "pt-BR-FranciscaNeural", "label": "Francisca", "locale": "pt-BR", "gender": "female", "provider": "edge-tts"},
    {"name": "en-US-GuyNeural", "label": "Guy", "locale": "en-US", "gender": "male", "provider": "edge-tts"},
    {"name": "es-ES-AlvaroNeural", "label": "Álvaro", "locale": "es-ES", "gender": "male", "provider": "edge-tts"},
]


def list_voices() -> dict[str, Any]:
    available = importlib.util.find_spec("edge_tts") is not None
    return {
        "provider": "edge-tts",
        "available": available,
        "install_hint": "" if available else "Instale a dependência com: pip install edge-tts",
        "voices": DEFAULT_VOICES,
    }


def generate_voice_for_project(project_id: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz") -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise VoiceGenerationError("Projeto não encontrado.")
    narration_text = narration_text_for_project(project)
    if not narration_text:
        project = update_project(
            project_id,
            {
                **project,
                "voice_status": "failed",
                "voice_error": "Roteiro vazio. Crie ou edite um roteiro antes de gerar voz.",
            },
        )
        raise VoiceGenerationError("Roteiro vazio. Crie ou edite um roteiro antes de gerar voz.", project)
    if importlib.util.find_spec("edge_tts") is None:
        project = update_project(
            project_id,
            {
                **project,
                "voice_status": "failed",
                "voice_error": "edge-tts não está instalado. Instale com: pip install edge-tts",
            },
        )
        raise VoiceGenerationError("edge-tts não está instalado. Instale com: pip install edge-tts", project)
    selected_voice = voice if _valid_voice(voice) else DEFAULT_VOICES[0]["name"]
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = AUDIO_DIR / f"{_safe_project_id(project_id)}.mp3"
    update_project(
        project_id,
        {
            **project,
            "voice_status": "generating",
            "voice_name": selected_voice,
            "voice_provider": "edge-tts",
            "voice_rate": rate,
            "voice_pitch": pitch,
            "voice_error": "",
            "voice_outdated": False,
        },
    )
    try:
        asyncio.run(_edge_tts_save(narration_text, selected_voice, rate, pitch, audio_path))
    except Exception as error:
        project = update_project(
            project_id,
            {
                **project,
                "voice_status": "failed",
                "voice_name": selected_voice,
                "voice_provider": "edge-tts",
                "voice_rate": rate,
                "voice_pitch": pitch,
                "voice_error": str(error),
            },
        )
        raise VoiceGenerationError("Não foi possível gerar a narração.", project) from error
    duration = estimate_duration_seconds(narration_text)
    updated = update_project(
        project_id,
        {
            **(get_project(project_id) or project),
            "status": "ready_for_visual",
            "voice_status": "ready",
            "voice_name": selected_voice,
            "voice_provider": "edge-tts",
            "voice_rate": rate,
            "voice_pitch": pitch,
            "voice_audio_path": str(audio_path),
            "voice_audio_url": f"/generation/projects/{project_id}/voice/audio",
            "voice_duration_seconds": duration,
            "voice_generated_at": datetime.utcnow().isoformat(),
            "voice_error": "",
            "voice_outdated": False,
        },
    )
    return {"project": updated or project, "audio_url": f"/generation/projects/{project_id}/voice/audio"}


def get_voice_file(project_id: str) -> Path:
    project = get_project(project_id)
    if not project:
        raise VoiceGenerationError("Projeto não encontrado.")
    path = Path(str(project.get("voice_audio_path") or "")) if project.get("voice_audio_path") else AUDIO_DIR / f"{_safe_project_id(project_id)}.mp3"
    if not path.exists() or not path.is_file():
        raise VoiceGenerationError("Áudio ainda não foi gerado.")
    return path


def delete_voice_file(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise VoiceGenerationError("Projeto não encontrado.")
    path = Path(str(project.get("voice_audio_path") or "")) if project.get("voice_audio_path") else AUDIO_DIR / f"{_safe_project_id(project_id)}.mp3"
    if path.exists() and path.is_file():
        path.unlink()
    updated = update_project(
        project_id,
        {
            **project,
            "status": "script" if project.get("script_lines") else "idea",
            "voice_status": "none",
            "voice_name": "",
            "voice_provider": "",
            "voice_rate": "",
            "voice_pitch": "",
            "voice_audio_path": "",
            "voice_audio_url": "",
            "voice_duration_seconds": None,
            "voice_generated_at": "",
            "voice_error": "",
            "voice_outdated": False,
        },
    )
    return {"project": updated or project, "deleted": True}


def narration_text_for_project(project: dict[str, Any]) -> str:
    parts: list[str] = []
    if project.get("hook"):
        parts.append(str(project.get("hook") or ""))
    for line in project.get("script_lines") or []:
        parts.append(str(line or ""))
    if project.get("cta"):
        parts.append(str(project.get("cta") or ""))
    cleaned = [_clean_tts_text(part) for part in parts]
    return " ".join(part for part in cleaned if part).strip()


def estimate_duration_seconds(text: str) -> float:
    words = re.findall(r"\b[\wÀ-ÿ]+\b", text)
    return round(max(1, len(words)) / 2.45, 1)


async def _edge_tts_save(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> None:
    import edge_tts  # type: ignore

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))


def _clean_tts_text(value: str) -> str:
    text = re.sub(r"#\w+", "", str(value or ""))
    text = re.sub(r"[*_`>\[\](){}]", " ", text)
    text = re.sub(r"[^\wÀ-ÿ\s.,!?;:%-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return text


def _valid_voice(voice: str) -> bool:
    return any(item["name"] == voice for item in DEFAULT_VOICES)


def _safe_project_id(project_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", project_id).strip("._-") or "project"


class VoiceGenerationError(Exception):
    def __init__(self, message: str, project: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.project = project
