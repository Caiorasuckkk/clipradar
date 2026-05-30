from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from app import config
from app.config import STORAGE_TRANSCRIPTS_DIR, WHISPER_MODEL_SIZE


class TranscriptionService:
    def __init__(self, model_size: str = WHISPER_MODEL_SIZE) -> None:
        self.model_size = model_size
        self.device = self._detect_device()
        self._model: Any | None = None
        self.output_dir = STORAGE_TRANSCRIPTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_ffmpeg_path()

    def transcribe(
        self,
        audio_path: str,
        metadata: dict[str, Any] | None = None,
        language: str | None = None,
    ) -> dict[str, Any] | None:
        video_id = Path(audio_path).stem
        language_decision = self._language_decision(metadata or {}, language)
        requested_language = language_decision["requested_language"]
        print(
            f"WHISPER iniciando: {video_id} — modelo {self.model_size} em {self.device} "
            f"language={requested_language or 'auto'} ({language_decision['language_mode']})"
        )
        started = time.perf_counter()
        try:
            model = self._load_model()
            result = model.transcribe(
                audio_path,
                language=requested_language or None,
                task="transcribe",
                verbose=False,
                word_timestamps=True,
                condition_on_previous_text=True,
            )
            detected_language = result.get("language")
            language_conflict = self._language_conflict(requested_language, detected_language)
            if language_conflict:
                print(
                    "WHISPER aviso: idioma solicitado e detectado parecem conflitantes — "
                    f"requested={requested_language} detected={detected_language}"
                )
            segments = [
                {
                    "id": segment.get("id", index),
                    "start": float(segment.get("start", 0.0)),
                    "end": float(segment.get("end", 0.0)),
                    "text": str(segment.get("text", "")).strip(),
                    "avg_logprob": float(segment.get("avg_logprob", 0.0)),
                }
                for index, segment in enumerate(result.get("segments", []))
            ]
            duration_seconds = max((segment["end"] for segment in segments), default=0.0)
            elapsed = time.perf_counter() - started
            print(
                f"WHISPER concluído: {video_id} — "
                f"{duration_seconds / 60:.1f}min em {elapsed:.1f}s"
            )
            return {
                "text": str(result.get("text", "")).strip(),
                "language": result.get("language"),
                "requested_language": requested_language,
                "detected_language": detected_language,
                "language_mode": language_decision["language_mode"],
                "language_source": language_decision["language_source"],
                "language_conflict": language_conflict,
                "segments": segments,
                "duration_seconds": duration_seconds,
            }
        except Exception as exc:
            print(f"WHISPER falhou: {video_id} — {exc}")
            return None

    def save_transcript(self, video_id: str, transcript: dict[str, Any]) -> str:
        path = self.output_dir / f"{video_id}.json"
        with path.open("w", encoding="utf-8") as file:
            json.dump(transcript, file, ensure_ascii=False, indent=2)
        return str(path)

    def load_transcript(self, video_id: str) -> dict[str, Any] | None:
        path = self.output_dir / f"{video_id}.json"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as exc:
            print(f"WHISPER cache falhou: {video_id} — {exc}")
            return None

    def _load_model(self) -> Any:
        if self._model is None:
            import whisper

            self._model = whisper.load_model(self.model_size, device=self.device)
        return self._model

    def _language_decision(
        self,
        metadata: dict[str, Any],
        explicit_language: str | None,
    ) -> dict[str, str]:
        if explicit_language:
            return {
                "requested_language": explicit_language,
                "language_mode": "forced_by_argument",
                "language_source": "argument",
            }
        if config.WHISPER_LANGUAGE_MODE == "forced":
            return {
                "requested_language": config.WHISPER_DEFAULT_LANGUAGE,
                "language_mode": "forced",
                "language_source": "WHISPER_DEFAULT_LANGUAGE",
            }

        language = str(metadata.get("language") or "").lower()
        market = str(metadata.get("market") or metadata.get("discovery_market") or "").upper()
        title = str(metadata.get("title", ""))
        channel = str(metadata.get("channel_name") or metadata.get("channel_title") or "")
        text = f"{title} {channel}".lower()

        if config.WHISPER_FORCE_PT_MARKET and (market == "BR" or language in {"pt", "pt-br"}):
            return {
                "requested_language": "pt",
                "language_mode": "auto_forced_by_market",
                "language_source": f"market:{market or language}",
            }
        if self._is_clear_international(text):
            return {
                "requested_language": "en" if language == "en" or market == "GLOBAL" else "",
                "language_mode": "auto_international",
                "language_source": "channel/title:international",
            }
        if config.WHISPER_FORCE_PT_CHANNELS:
            source = self._pt_signal_source(title, channel)
            if source:
                return {
                    "requested_language": "pt",
                    "language_mode": "auto_forced_by_channel",
                    "language_source": source,
                }
        return {
            "requested_language": config.WHISPER_DEFAULT_LANGUAGE,
            "language_mode": "auto",
            "language_source": "whisper_auto",
        }

    @staticmethod
    def _pt_signal_source(title: str, channel: str) -> str:
        channel_terms = {
            "ticaracaticast", "inteligência ltda", "inteligencia ltda",
            "podpah", "flow", "vênus", "venus", "papo de elite",
            "revista oeste", "oestecast", "chupim metropolitana",
            "programa do joão", "programa do joao", "joão kléber",
            "joao kleber", "rica perrone", "laura müller", "laura muller",
            "fittipaldi", "léo lins", "leo lins", "monark", "vilela",
        }
        title_terms = {
            "entrevista", "conversa", "reage", "revela", "podcast",
            "programa", "viagem", "china", "mídia", "midia", "bolsonaro",
            "petista",
        }
        channel_lower = channel.lower()
        title_lower = title.lower()
        for term in channel_terms:
            if term in channel_lower or term in title_lower:
                return f"channel/title:{term}"
        for term in title_terms:
            if term in title_lower:
                return f"title:{term}"
        return ""

    @staticmethod
    def _is_clear_international(text: str) -> bool:
        return any(
            term in text
            for term in {
                "lex fridman", "theo von", "joe rogan", "piers morgan",
                "hot ones", "powerfuljre", "club shay shay",
                "diary of a ceo",
            }
        )

    @staticmethod
    def _language_conflict(requested_language: str, detected_language: object) -> bool:
        requested = (requested_language or "").lower()
        detected = str(detected_language or "").lower()
        if not requested:
            return False
        if requested == "pt":
            return detected in {"en", "english"}
        if requested == "en":
            return detected in {"pt", "portuguese"}
        return False

    @staticmethod
    def _detect_device() -> str:
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    @staticmethod
    def _ensure_ffmpeg_path() -> None:
        try:
            import imageio_ffmpeg

            ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
            ffmpeg_dir = STORAGE_TRANSCRIPTS_DIR.parent / "cache" / "ffmpeg"
            ffmpeg_dir.mkdir(parents=True, exist_ok=True)
            ffmpeg_alias = ffmpeg_dir / "ffmpeg.exe"
            if not ffmpeg_alias.exists():
                shutil.copy2(ffmpeg_path, ffmpeg_alias)
            os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{ffmpeg_path.parent}{os.pathsep}{os.environ.get('PATH', '')}"
        except Exception:
            pass
