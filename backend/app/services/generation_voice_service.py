from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from app import config
from app.services.generation_workspace_service import get_project, update_project
from app.services import generation_narration_service as narration
from app.services import generation_caption_service as captions


AUDIO_DIR = config.STORAGE_GENERATION_DIR / "audio"
DEFAULT_VOICES = [
    # edge-tts (free) — DEFAULT_VOICES[0] é o fallback seguro; mantenha a Thalita aqui.
    {"name": "pt-BR-ThalitaMultilingualNeural", "label": "Thalita (natural)", "locale": "pt-BR", "gender": "female", "provider": "edge-tts"},
    # Local XTTS — vozes clonadas por estúdio (grátis, na GPU).
    {"name": "xtts:marco", "label": "Marco (História)", "locale": "multi", "gender": "male", "provider": "xtts"},
    {"name": "xtts:atlas", "label": "Atlas (Mitologia)", "locale": "multi", "gender": "male", "provider": "xtts"},
    {"name": "xtts:carlos", "label": "Carlos (Ciência)", "locale": "multi", "gender": "male", "provider": "xtts"},
    {"name": "xtts:clara", "label": "Doutora Clara (Psicologia)", "locale": "multi", "gender": "female", "provider": "xtts"},
    {"name": "pt-BR-AntonioNeural", "label": "Antônio", "locale": "pt-BR", "gender": "male", "provider": "edge-tts"},
    {"name": "pt-BR-FranciscaNeural", "label": "Francisca", "locale": "pt-BR", "gender": "female", "provider": "edge-tts"},
    {"name": "en-US-GuyNeural", "label": "Guy", "locale": "en-US", "gender": "male", "provider": "edge-tts"},
    {"name": "es-ES-AlvaroNeural", "label": "Álvaro", "locale": "es-ES", "gender": "male", "provider": "edge-tts"},
    # OpenAI TTS (realistic; uses OPENAI_API_KEY + enabled TTS model)
    {"name": "openai:onyx", "label": "Onyx (OpenAI, grave)", "locale": "multi", "gender": "male", "provider": "openai"},
    {"name": "openai:fable", "label": "Fable (OpenAI, narrador)", "locale": "multi", "gender": "neutral", "provider": "openai"},
    {"name": "openai:nova", "label": "Nova (OpenAI, feminina)", "locale": "multi", "gender": "female", "provider": "openai"},
    {"name": "openai:echo", "label": "Echo (OpenAI, masculina)", "locale": "multi", "gender": "male", "provider": "openai"},
    # ElevenLabs (most human; needs ELEVENLABS_API_KEY). Premade voice IDs.
    {"name": "elevenlabs:onwK4e9ZLuTAKqWW03F9", "label": "Daniel (ElevenLabs)", "locale": "multi", "gender": "male", "provider": "elevenlabs"},
    {"name": "elevenlabs:EXAVITQu4vr4xnSDxMaL", "label": "Sarah (ElevenLabs)", "locale": "multi", "gender": "female", "provider": "elevenlabs"},
    {"name": "elevenlabs:pNInz6obpgDQGcFmaJgB", "label": "Adam (ElevenLabs)", "locale": "multi", "gender": "male", "provider": "elevenlabs"},
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
    # Prefer the polished conversational narration when present; convert its pause
    # markers into natural punctuation for edge-tts. Default to a slightly slower,
    # more human rate driven by the narration style.
    rate = _effective_rate(project, rate)
    polished = str(project.get("narration_text") or "")
    narration_text = narration.tts_text(polished) if polished else narration_text_for_project(project)
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
    selected_voice = voice if _valid_voice(voice) else DEFAULT_VOICES[0]["name"]
    provider, voice_id = _voice_provider(selected_voice)
    language = str(project.get("language") or "pt-BR")
    if provider == "openai" and not config.OPENAI_API_KEY:
        provider, selected_voice, voice_id = "edge", DEFAULT_VOICES[0]["name"], DEFAULT_VOICES[0]["name"]
    if provider == "elevenlabs" and not config.ELEVENLABS_API_KEY:
        provider, selected_voice, voice_id = "edge", DEFAULT_VOICES[0]["name"], DEFAULT_VOICES[0]["name"]
    if provider == "xtts" and not config.GENERATION_XTTS_ENABLED:
        provider, selected_voice, voice_id = "edge", DEFAULT_VOICES[0]["name"], DEFAULT_VOICES[0]["name"]
    if provider == "edge" and importlib.util.find_spec("edge_tts") is None:
        project = update_project(
            project_id,
            {
                **project,
                "voice_status": "failed",
                "voice_error": "edge-tts não está instalado. Instale com: pip install edge-tts",
            },
        )
        raise VoiceGenerationError("edge-tts não está instalado. Instale com: pip install edge-tts", project)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = AUDIO_DIR / f"{_safe_project_id(project_id)}.mp3"
    words_path = AUDIO_DIR / f"{_safe_project_id(project_id)}.words.json"
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
        if provider == "openai":
            words, words_source = _openai_tts_save(narration_text, voice_id, rate, audio_path, language)
        elif provider == "elevenlabs":
            words, words_source = _elevenlabs_tts_save(narration_text, voice_id, audio_path)
        elif provider == "xtts":
            words, words_source = _xtts_tts_save(narration_text, language, audio_path, voice_id)
        else:
            words, words_source = asyncio.run(_edge_tts_save(narration_text, selected_voice, rate, pitch, audio_path))
    except Exception as premium_error:
        # Premium provider failed (e.g. TTS model not enabled / bad key) — fall
        # back to the free edge-tts voice so a video never breaks over voice.
        if provider != "edge" and importlib.util.find_spec("edge_tts") is not None:
            try:
                selected_voice = DEFAULT_VOICES[0]["name"]
                provider = "edge"
                words, words_source = asyncio.run(_edge_tts_save(narration_text, selected_voice, rate, pitch, audio_path))
            except Exception as error:
                _fail_voice(project_id, project, selected_voice, rate, pitch, error)
                raise VoiceGenerationError("Não foi possível gerar a narração.", project) from error
        else:
            _fail_voice(project_id, project, selected_voice, rate, pitch, premium_error)
            raise VoiceGenerationError("Não foi possível gerar a narração.", project) from premium_error
    # Robust fallback: if no boundary timings at all, anchor words across the real
    # audio duration so captions/sync still work.
    if not words:
        real_duration = _probe_audio_duration(audio_path) or estimate_duration_seconds(narration_text)
        words = _approximate_words(re.findall(r"\S+", narration_text), real_duration)
        words_source = "approximate"
    words_saved = _save_words(words_path, words)
    duration = _probe_audio_duration(audio_path) or _duration_from_words(words) or estimate_duration_seconds(narration_text)
    base = get_project(project_id) or project
    caption_result = captions.ensure_captions(
        {**base, "voice_words_path": str(words_path) if words_saved else "", "voice_duration_seconds": duration}
    )
    updated = update_project(
        project_id,
        {
            **base,
            "status": "ready_for_visual",
            "voice_status": "ready",
            "voice_name": selected_voice,
            "voice_provider": "edge-tts",
            "voice_rate": rate,
            "voice_pitch": pitch,
            "voice_audio_path": str(audio_path),
            "voice_audio_url": f"/generation/projects/{project_id}/voice/audio",
            "voice_words_path": str(words_path) if words_saved else "",
            "voice_word_count": len(words),
            "voice_captions_path": caption_result["captions_path"],
            "voice_caption_count": caption_result["caption_count"],
            "voice_words_source": words_source,
            "voice_duration_seconds": duration,
            "voice_generated_at": datetime.utcnow().isoformat(),
            "voice_error": "",
            "voice_outdated": False,
            **_stale_render(base),
        },
    )
    return {"project": updated or project, "audio_url": f"/generation/projects/{project_id}/voice/audio"}


def _effective_rate(project: dict[str, Any], rate: str) -> str:
    if rate and rate not in {"+0%", ""}:
        return rate
    project_rate = str(project.get("voice_rate") or "")
    if project_rate and project_rate not in {"+0%", ""}:
        return project_rate
    style = project.get("narration_style")
    if style:
        return narration.preset_for(style)["rate"]
    return config.GENERATION_DEFAULT_VOICE_RATE


def _stale_render(project: dict[str, Any]) -> dict[str, Any]:
    """Voice changes invalidate any existing render (Part 4)."""
    if str(project.get("render_status") or "") in {"ready", "queued", "rendering"}:
        return {"render_status": "stale"}
    return {}


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
    words_path = Path(str(project.get("voice_words_path") or "")) if project.get("voice_words_path") else AUDIO_DIR / f"{_safe_project_id(project_id)}.words.json"
    if words_path.exists() and words_path.is_file():
        words_path.unlink()
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
            "voice_words_path": "",
            "voice_word_count": 0,
            "voice_duration_seconds": None,
            "voice_generated_at": "",
            "voice_error": "",
            "voice_outdated": False,
        },
    )
    return {"project": updated or project, "deleted": True}


def ensure_voice_words(project: dict[str, Any]) -> dict[str, Any]:
    """Guarantee a words.json exists for a project that already has narration.

    Real per-word timings come from edge-tts at generation time. Older projects
    (generated before word capture) only have an MP3, so we synthesize an
    *approximate* timeline by spreading the narration tokens evenly across the
    audio duration. Good enough to drive subtitle cues and never blocks render.

    Returns ``{"project", "generated", "word_count", "words_path"}``.
    """
    project_id = str(project.get("project_id") or "")
    existing = str(project.get("voice_words_path") or "")
    if existing:
        path = Path(existing)
        if path.exists() and path.is_file():
            return {
                "project": project,
                "generated": False,
                "word_count": int(project.get("voice_word_count") or 0),
                "words_path": existing,
            }

    audio_raw = str(project.get("voice_audio_path") or "")
    if not audio_raw or not Path(audio_raw).exists():
        return {"project": project, "generated": False, "word_count": 0, "words_path": ""}

    polished = str(project.get("narration_text") or "")
    spoken = narration.strip_pause_markers(polished) if polished else narration_text_for_project(project)
    tokens = re.findall(r"\S+", spoken)
    if not tokens:
        return {"project": project, "generated": False, "word_count": 0, "words_path": ""}

    # Real audio duration drives the fallback timeline; punctuation adds pauses.
    duration = (
        _probe_audio_duration(Path(audio_raw))
        or _safe_positive_float(project.get("voice_duration_seconds"))
        or estimate_duration_seconds(spoken)
    )
    # Prefer real per-word timings (Whisper) so captions stay locked to the voice;
    # only fall back to an approximate timeline if alignment is unavailable.
    aligned = align_words_with_whisper(Path(audio_raw), _xtts_lang(str(project.get("language") or "")))
    words = aligned or _approximate_words(tokens, duration)
    words_source = "openai_whisper" if aligned else "approximate"
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    words_path = AUDIO_DIR / f"{_safe_project_id(project_id)}.words.json"
    if not _save_words(words_path, words):
        return {"project": project, "generated": False, "word_count": 0, "words_path": ""}

    caption_result = captions.ensure_captions(
        {**project, "project_id": project_id, "voice_words_path": str(words_path), "voice_duration_seconds": duration}
    )
    updated = update_project(
        project_id,
        {
            **project,
            "voice_words_path": str(words_path),
            "voice_word_count": len(words),
            "voice_captions_path": caption_result["captions_path"],
            "voice_caption_count": caption_result["caption_count"],
            "voice_words_source": words_source,
            "voice_duration_seconds": duration,
            **_stale_render(project),
        },
    )
    return {
        "project": updated or project,
        "generated": True,
        "word_count": len(words),
        "words_path": str(words_path),
    }


def _token_weights(tokens: list[str]) -> list[float]:
    """Per-token time weight: longer words and punctuation get more time so the
    timeline breathes like real speech instead of a flat metronome."""
    weights: list[float] = []
    for token in tokens:
        weight = 1.0 + min(0.8, max(0, len(token) - 4) * 0.06)
        stripped = token.rstrip("\"')]}")
        if stripped.endswith((".", "!", "?", "…")):
            weight += 1.4  # sentence pause
        elif stripped.endswith((",", ";", ":", "—", "–")):
            weight += 0.6  # soft pause
        weights.append(weight)
    return weights


def _distribute_tokens(tokens: list[str], start: float, end: float) -> list[dict[str, Any]]:
    if not tokens:
        return []
    weights = _token_weights(tokens)
    total_weight = sum(weights) or float(len(tokens))
    span = max(0.1, float(end) - float(start))
    words: list[dict[str, Any]] = []
    cursor = float(start)
    for index, token in enumerate(tokens):
        seg_start = cursor
        seg_end = float(end) if index == len(tokens) - 1 else seg_start + span * (weights[index] / total_weight)
        words.append({"text": token, "start": round(seg_start, 3), "end": round(seg_end, 3)})
        cursor = seg_end
    return words


def _approximate_words(tokens: list[str], duration: float) -> list[dict[str, Any]]:
    return _distribute_tokens(tokens, 0.0, max(0.5, float(duration)))


def _probe_audio_duration(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        import shutil
        import subprocess

        exe = shutil.which("ffprobe")
        if exe:
            completed = subprocess.run(
                [exe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            value = (completed.stdout or "").strip()
            return round(float(value), 2) if value else None
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                return None
        completed = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True, timeout=30, check=False)
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", completed.stderr or "")
        if match:
            return round(int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3)), 2)
    except Exception:
        return None
    return None


def _safe_positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


_FOLLOW_RE = re.compile(r"me segue|segue o canal|segue a[íi]|se inscre|inscreva|follow|subscribe", re.IGNORECASE)


def _has_follow(text: str) -> bool:
    return bool(_FOLLOW_RE.search(str(text or "")))


def narration_text_for_project(project: dict[str, Any]) -> str:
    parts: list[str] = []
    if project.get("hook"):
        parts.append(str(project.get("hook") or ""))
    for line in project.get("script_lines") or []:
        parts.append(str(line or ""))
    # Drop the separate CTA when the script already calls to follow, so the
    # "me segue" / "follow" doesn't get spoken twice.
    cta = str(project.get("cta") or "")
    if cta and not (_has_follow(cta) and any(_has_follow(p) for p in parts)):
        parts.append(cta)
    cleaned = [_clean_tts_text(part) for part in parts if _clean_tts_text(part)]
    return _flowing_narration(cleaned)


def _flowing_narration(sentences: list[str]) -> str:
    """Join short adjacent lines with commas instead of full stops so the speech
    flows like a conversation (edge-tts pauses on every period, which makes many
    short lines sound choppy/breathy)."""
    if not sentences:
        return ""
    result = sentences[0].strip()
    for nxt in sentences[1:]:
        nxt = nxt.strip()
        if not nxt:
            continue
        tail = result.rsplit(". ", 1)[-1]
        tail_words = len(re.findall(r"[\wÀ-ÿ]+", tail))
        nxt_words = len(re.findall(r"[\wÀ-ÿ]+", nxt))
        # Merge two short statements into one flowing clause to cut a hard pause.
        # Only merge after a period — keep the hook's "?" and any "!" intonation.
        if result[-1:] == "." and tail_words <= 11 and nxt_words <= 9:
            result = f"{result[:-1]}, {nxt}"
        else:
            result = f"{result} {nxt}"
    return result.strip()


def estimate_duration_seconds(text: str) -> float:
    words = re.findall(r"\b[\wÀ-ÿ]+\b", text)
    return round(max(1, len(words)) / 2.45, 1)


async def _edge_tts_save(
    text: str, voice: str, rate: str, pitch: str, output_path: Path
) -> tuple[list[dict[str, Any]], str]:
    """Stream synthesis, capturing audio + boundary timings.

    edge-tts emits WordBoundary (word-level) on some versions and SentenceBoundary
    (sentence-level) on others (7.x). We prefer real word timings; otherwise we
    anchor words inside each sentence's real start/end — far better sync than a
    flat approximation. Returns ``(words, source)``.
    """
    import edge_tts  # type: ignore

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    boundaries: list[dict[str, Any]] = []
    with output_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            chunk_type = chunk.get("type")
            if chunk_type == "audio" and chunk.get("data"):
                audio_file.write(chunk["data"])
            elif chunk_type in ("WordBoundary", "SentenceBoundary"):
                start = float(chunk.get("offset", 0)) / 10_000_000.0
                duration = float(chunk.get("duration", 0)) / 10_000_000.0
                boundaries.append(
                    {
                        "type": chunk_type,
                        "text": str(chunk.get("text", "")),
                        "start": round(start, 3),
                        "end": round(start + duration, 3),
                    }
                )
    return _words_from_boundaries(boundaries)


def _words_from_boundaries(boundaries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    word_events = [b for b in boundaries if b["type"] == "WordBoundary"]
    if word_events:
        return ([{"text": b["text"], "start": b["start"], "end": b["end"]} for b in word_events], "wordboundary")
    sentence_events = [b for b in boundaries if b["type"] == "SentenceBoundary"]
    if sentence_events:
        words: list[dict[str, Any]] = []
        for sentence in sentence_events:
            tokens = re.findall(r"\S+", sentence["text"])
            words.extend(_distribute_tokens(tokens, sentence["start"], sentence["end"]))
        if words:
            return words, "sentence"
    return [], "none"


def _save_words(words_path: Path, words: list[dict[str, Any]]) -> bool:
    if not words:
        return False
    try:
        with words_path.open("w", encoding="utf-8") as file:
            json.dump({"words": words}, file, ensure_ascii=False)
        return True
    except OSError:
        return False


def _duration_from_words(words: list[dict[str, Any]]) -> float | None:
    if not words:
        return None
    try:
        return round(float(words[-1]["end"]), 2)
    except (KeyError, TypeError, ValueError):
        return None


def _clean_tts_text(value: str) -> str:
    text = re.sub(r"#\w+", "", str(value or ""))
    text = re.sub(r"[*_`>\[\](){}]", " ", text)
    text = re.sub(r"[^\wÀ-ÿ\s.,!?;:%-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return text


def _valid_voice(voice: str) -> bool:
    v = str(voice or "")
    if v.startswith(("openai:", "elevenlabs:", "11labs:", "xtts:", "local:")):
        return True  # allow custom OpenAI/ElevenLabs/local voice ids beyond the presets
    return any(item["name"] == voice for item in DEFAULT_VOICES)


def _voice_provider(voice: str) -> tuple[str, str]:
    """('edge'|'openai'|'elevenlabs'|'xtts', voice_id)."""
    v = str(voice or "")
    if v.startswith("openai:"):
        return "openai", v.split(":", 1)[1]
    if v.startswith("elevenlabs:") or v.startswith("11labs:"):
        return "elevenlabs", v.split(":", 1)[1]
    if v.startswith("xtts:") or v.startswith("local:"):
        return "xtts", v.split(":", 1)[1]
    return "edge", v


def _xtts_lang(language: str) -> str:
    """Map a project language (pt-BR/en-US/...) to an XTTS language code."""
    code = str(language or "pt").strip().lower().replace("_", "-")
    return code.split("-", 1)[0] or "pt"


def _ffmpeg_bin() -> str | None:
    import shutil

    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


_SPEECH_ABBREV = [
    (re.compile(r"\bd\.\s*C\.?", re.IGNORECASE), "depois de Cristo"),
    (re.compile(r"\ba\.\s*C\.?", re.IGNORECASE), "antes de Cristo"),
    (re.compile(r"\bs[ée]c\.\s*", re.IGNORECASE), "século "),
    (re.compile(r"\bDra\."), "Doutora"),
    (re.compile(r"\bDr\."), "Doutor"),
    (re.compile(r"\bSra\."), "Senhora"),
    (re.compile(r"\bSr\."), "Senhor"),
    (re.compile(r"\betc\.?", re.IGNORECASE), "etcétera"),
    (re.compile(r"\bn[ºo°]\.?\s*", re.IGNORECASE), "número "),
    (re.compile(r"\bkm²"), "quilômetros quadrados"),
    (re.compile(r"\bkm\b"), "quilômetros"),
]


def _normalize_for_speech(text: str, language: str = "pt-BR") -> str:
    """Make raw text speakable: expand abbreviations (a.C., séc., %, ...) and numbers
    to words so the TTS never reads a stray period ('ponto') or spells digits out.
    Portuguese-focused; numbers expanded only for pt languages."""
    t = str(text or "")
    for pattern, repl in _SPEECH_ABBREV:
        t = pattern.sub(repl, t)
    t = t.replace("%", " por cento")
    t = t.replace("…", ", ").replace("...", ", ")

    lang = str(language or "pt").lower()
    if lang.startswith("pt"):
        try:
            from num2words import num2words

            def _repl(match: "re.Match[str]") -> str:
                raw = match.group(0).replace(".", "")
                try:
                    return num2words(int(raw), lang="pt")
                except (ValueError, Exception):  # noqa: BLE001
                    return match.group(0)

            t = re.sub(r"\d{1,3}(?:\.\d{3})+|\d+", _repl, t)
        except Exception:  # noqa: BLE001 - num2words missing -> leave digits
            pass

    # Keep sentence punctuation (. ! ?) so the synth can split into sentences and
    # add real pauses; the synth strips the trailing '.' per sentence so XTTS never
    # vocalizes 'ponto'.
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    return t.strip()


def _xtts_ref_for(voice_id: str, language: str = "") -> Path:
    """Resolve the cloned-voice reference for an xtts voice id, preferring a
    LANGUAGE-SPECIFIC recording when present. Lookup order:
      persona/voz_ref_<id>_<lang>.wav  (e.g. voz_ref_marco_en.wav — native accent)
      persona/voz_ref_<id>.wav
      default (Marco / GENERATION_XTTS_REF)."""
    default = Path(config.GENERATION_XTTS_REF)
    base = default.parent
    name = re.sub(r"[^a-z0-9_]+", "", str(voice_id or "").lower())
    lang = re.sub(r"[^a-z]+", "", str(language or "").lower())[:2]
    if name and lang:
        candidate = base / f"voz_ref_{name}_{lang}.wav"
        if candidate.exists():
            return candidate
    if name:
        candidate = base / f"voz_ref_{name}.wav"
        if candidate.exists():
            return candidate
    return default


def _xtts_tts_save(
    text: str, language: str, audio_path: Path, voice_id: str = "marco"
) -> tuple[list[dict[str, Any]], str]:
    """Synthesize with a local XTTS cloned voice (per-studio) via the isolated
    tts_test venv (subprocess), then convert WAV -> MP3. The reference is chosen by
    voice_id. No native word timings (caller aligns with Whisper)."""
    import subprocess

    text = _normalize_for_speech(text, language)
    python_exe = Path(config.GENERATION_XTTS_PYTHON)
    script = Path(config.GENERATION_XTTS_SCRIPT)
    ref = _xtts_ref_for(voice_id, language)
    for needed, label in ((python_exe, "python"), (script, "script"), (ref, "referência")):
        if not needed.exists():
            raise RuntimeError(f"xtts_missing_{label}:{needed}")

    wav_out = audio_path.with_suffix(".xtts.wav")
    text_file = audio_path.with_suffix(".xtts.txt")
    text_file.write_text(text, encoding="utf-8")
    cmd = [
        str(python_exe), str(script),
        "--text-file", str(text_file),
        "--lang", _xtts_lang(language),
        "--ref", str(ref),
        "--out", str(wav_out),
        "--speed", str(config.GENERATION_XTTS_SPEED),
        "--temperature", str(config.GENERATION_XTTS_TEMPERATURE),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0 or not wav_out.exists():
        raise RuntimeError(f"xtts_failed:{(result.stderr or '')[-300:]}")

    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        raise RuntimeError("xtts_no_ffmpeg")
    conv_cmd = [ffmpeg, "-y", "-i", str(wav_out)]
    if config.GENERATION_XTTS_CLEAN_AUDIO and config.GENERATION_XTTS_CLEAN_FILTER:
        # Denoise leve + presença (treble) + normalização: fundo limpo sem abafar.
        conv_cmd += ["-af", config.GENERATION_XTTS_CLEAN_FILTER]
    conv_cmd += ["-c:a", "libmp3lame", "-b:a", "192k", str(audio_path)]
    conv = subprocess.run(conv_cmd, capture_output=True, text=True, timeout=120)
    try:
        wav_out.unlink()
        text_file.unlink()
    except OSError:
        pass
    if conv.returncode != 0 or not audio_path.exists():
        raise RuntimeError("xtts_mp3_convert_failed")
    # XTTS gives no word timings; transcribe the result with Whisper so captions
    # lock to the speech (real per-word timestamps). Falls back to approximate.
    words = align_words_with_whisper(audio_path, _xtts_lang(language))
    return (words, "xtts_whisper") if words else ([], "xtts")


def _rate_to_speed(rate: str) -> float:
    match = re.search(r"(-?\d+)", str(rate or ""))
    pct = int(match.group(1)) if match else 0
    return max(0.7, min(1.3, round(1.0 + pct / 100.0, 2)))


def _openai_tts_save(text: str, voice: str, rate: str, audio_path: Path, language: str = "") -> tuple[list[dict[str, Any]], str]:
    """OpenAI TTS (realistic). The TTS API returns no word timings, so we transcribe
    the generated audio with Whisper to get real word-level timestamps and keep the
    subtitles locked to the speech. Falls back to approximate timing if alignment is
    off or fails."""
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    kwargs: dict[str, Any] = {
        "model": config.GENERATION_OPENAI_TTS_MODEL, "voice": voice,
        "input": text, "response_format": "mp3",
    }
    try:
        resp = client.audio.speech.create(speed=_rate_to_speed(rate), **kwargs)
    except Exception:
        resp = client.audio.speech.create(**kwargs)  # some models reject 'speed'
    audio_bytes = getattr(resp, "content", None) or (resp.read() if hasattr(resp, "read") else b"")
    if not audio_bytes:
        raise RuntimeError("openai_tts_empty_audio")
    audio_path.write_bytes(audio_bytes)
    words = align_words_with_whisper(audio_path, _xtts_lang(language))
    return (words, "openai_whisper") if words else ([], "openai")


def align_words_with_whisper(audio_path: Path, language: str = "") -> list[dict[str, Any]]:
    """Transcribe audio with OpenAI Whisper, returning real per-word timings
    ``[{text,start,end}]``. Passing ``language`` (e.g. 'en'/'pt') forces Whisper to
    transcribe in that language — important because a cloned PT voice speaking English
    can otherwise be auto-detected as Portuguese, producing a wrong-language caption.
    Returns ``[]`` on any failure so callers can fall back — never raises."""
    if not config.GENERATION_ALIGN_CAPTIONS or not config.OPENAI_API_KEY:
        return []
    if not audio_path.exists():
        return []
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY)
        kwargs: dict[str, Any] = {
            "model": config.GENERATION_OPENAI_TRANSCRIBE_MODEL,
            "response_format": "verbose_json",
            "timestamp_granularities": ["word"],
        }
        code = str(language or "").strip().lower()[:2]
        if code:
            kwargs["language"] = code
        with audio_path.open("rb") as audio_file:
            result = client.audio.transcriptions.create(file=audio_file, **kwargs)
    except Exception:  # noqa: BLE001 - alignment is best-effort
        return []

    raw = getattr(result, "words", None)
    if raw is None and isinstance(result, dict):
        raw = result.get("words")
    words: list[dict[str, Any]] = []
    for item in raw or []:
        text = getattr(item, "word", None)
        start = getattr(item, "start", None)
        end = getattr(item, "end", None)
        if text is None and isinstance(item, dict):
            text, start, end = item.get("word"), item.get("start"), item.get("end")
        text = str(text or "").strip()
        if not text or start is None or end is None:
            continue
        try:
            words.append({"text": text, "start": round(float(start), 3), "end": round(float(end), 3)})
        except (TypeError, ValueError):
            continue
    return words


def _elevenlabs_tts_save(text: str, voice_id: str, audio_path: Path) -> tuple[list[dict[str, Any]], str]:
    """ElevenLabs (most human) with character timestamps → real word timings."""
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
        headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": config.GENERATION_ELEVENLABS_MODEL},
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    audio_b64 = data.get("audio_base64") or ""
    if not audio_b64:
        raise RuntimeError("elevenlabs_no_audio")
    audio_path.write_bytes(base64.b64decode(audio_b64))
    alignment = data.get("alignment") or data.get("normalized_alignment") or {}
    words = _words_from_char_alignment(alignment)
    return words, ("elevenlabs_timestamps" if words else "elevenlabs")


def _words_from_char_alignment(alignment: dict[str, Any]) -> list[dict[str, Any]]:
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not (len(chars) == len(starts) == len(ends)) or not chars:
        return []
    words: list[dict[str, Any]] = []
    buf, w_start, w_end = "", None, 0.0
    for index, ch in enumerate(chars):
        if str(ch).strip() == "":
            if buf and w_start is not None:
                words.append({"text": buf, "start": round(float(w_start), 3), "end": round(float(w_end), 3)})
            buf, w_start = "", None
        else:
            if not buf:
                w_start = starts[index]
            buf += str(ch)
            w_end = ends[index]
    if buf and w_start is not None:
        words.append({"text": buf, "start": round(float(w_start), 3), "end": round(float(w_end), 3)})
    return words


def _fail_voice(project_id: str, project: dict[str, Any], voice: str, rate: str, pitch: str, error: Exception) -> None:
    update_project(
        project_id,
        {
            **project,
            "voice_status": "failed",
            "voice_name": voice,
            "voice_rate": rate,
            "voice_pitch": pitch,
            "voice_error": str(error),
        },
    )


def _safe_project_id(project_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", project_id).strip("._-") or "project"


class VoiceGenerationError(Exception):
    def __init__(self, message: str, project: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.project = project
