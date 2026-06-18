"""Narration polishing for the render pipeline (0.5.53, Part 2).

Turns the structured script (hook + script_lines + cta) into a *spoken*
``narration_text`` that sounds like a person telling a story to a friend:
short sentences, natural pauses, conversational connectors. Pause markers
(``[pause:short|medium|long]``) live only in narration_text — they become
silence-creating punctuation for edge-tts and are stripped from captions.

Uses Gemini when available; otherwise a deterministic local polisher. Never
fails the pipeline — falls back gracefully.
"""

from __future__ import annotations

import re
from typing import Any

from app import config


# narration_style -> edge-tts defaults + behaviour
NARRATION_PRESETS: dict[str, dict[str, Any]] = {
    "conversational_story": {"label": "Conversa (história)", "rate": "-2%", "pitch": "+0Hz"},
    "conversational": {"label": "Conversa", "rate": "+0%", "pitch": "+0Hz"},
    "documentary": {"label": "Documentário", "rate": "-2%", "pitch": "-2Hz"},
    "energetic_short": {"label": "Energético", "rate": "+8%", "pitch": "+2Hz"},
    "dramatic_story": {"label": "Dramático", "rate": "-5%", "pitch": "-3Hz"},
}
DEFAULT_STYLE = config.GENERATION_DEFAULT_NARRATION_STYLE

_PAUSE_TOKENS = {
    "[pause:short]": ", ",
    "[pause:medium]": "... ",
    "[pause:long]": "... ... ",
}
_PAUSE_RE = re.compile(r"\[pause:(short|medium|long)\]")

_OPENERS = ["Olha só.", "Presta atenção nisso.", "Deixa eu te contar.", "Pensa comigo."]
_CONNECTORS = ["E tem mais.", "Mas calma.", "Agora vem o detalhe.", "E aí está o ponto."]


def normalize_style(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in NARRATION_PRESETS else DEFAULT_STYLE


def preset_for(style: Any) -> dict[str, Any]:
    return NARRATION_PRESETS[normalize_style(style)]


def list_presets() -> list[dict[str, Any]]:
    return [
        {"style": key, "label": value["label"], "rate": value["rate"], "pitch": value["pitch"]}
        for key, value in NARRATION_PRESETS.items()
    ]


def polish_narration(project: dict[str, Any], style: str | None = None) -> dict[str, Any]:
    """Return a polished narration plan: narration_text (+ pause markers),
    style and suggested edge-tts rate/pitch."""
    resolved_style = normalize_style(style or project.get("narration_style"))
    preset = NARRATION_PRESETS[resolved_style]
    source = _source_segments(project)
    if not source:
        return {
            "narration_text": "",
            "narration_style": resolved_style,
            "narration_style_label": preset["label"],
            "voice_rate": preset["rate"],
            "voice_pitch": preset["pitch"],
            "narration_polished_by": "none",
        }

    narration_text = ""
    polished_by = "local"
    if _gemini_available():
        try:
            narration_text = _polish_with_gemini(project, source, resolved_style)
            if narration_text:
                polished_by = "gemini"
        except Exception:
            narration_text = ""
    if not narration_text:
        narration_text = _polish_locally(source, resolved_style)

    return {
        "narration_text": narration_text,
        "narration_style": resolved_style,
        "narration_style_label": preset["label"],
        "voice_rate": preset["rate"],
        "voice_pitch": preset["pitch"],
        "narration_polished_by": polished_by,
    }


def apply_narration_polish(project_id: str, style: str | None = None) -> dict[str, Any] | None:
    """Polish a project's narration and persist it. Marks voice outdated and any
    existing render stale, since the spoken text changed."""
    from app.services.generation_workspace_service import get_project, update_project

    project = get_project(project_id)
    if not project:
        return None
    plan = polish_narration(project, style)
    stale = (
        {"render_status": "stale"}
        if str(project.get("render_status") or "") in {"ready", "queued", "rendering"}
        else {}
    )
    updated = update_project(
        project_id,
        {
            **project,
            "narration_text": plan["narration_text"],
            "narration_style": plan["narration_style"],
            "narration_style_label": plan["narration_style_label"],
            "narration_polished_by": plan["narration_polished_by"],
            "voice_rate": plan["voice_rate"],
            "voice_pitch": project.get("voice_pitch") or plan["voice_pitch"],
            "voice_outdated": str(project.get("voice_status") or "") == "ready",
            **stale,
        },
    )
    return updated or project


def tts_text(narration_text: str) -> str:
    """Spoken text for edge-tts: pause markers become natural punctuation."""
    text = str(narration_text or "")
    for token, replacement in _PAUSE_TOKENS.items():
        text = text.replace(token, replacement)
    text = _PAUSE_RE.sub("... ", text)
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[*_`>\[\](){}]", " ", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    # Collapse punctuation collisions introduced by pause->punctuation swaps.
    text = re.sub(r"[,;:]+\s*([.!?])", r"\1", text)
    text = re.sub(r"(,\s*){2,}", ", ", text)
    text = re.sub(r"\.{4,}", "...", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_pause_markers(narration_text: str) -> str:
    return re.sub(r"\s+", " ", _PAUSE_RE.sub(" ", str(narration_text or ""))).strip()


# ---------------------------------------------------------------------------
# Local polisher
# ---------------------------------------------------------------------------

def _source_segments(project: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    if project.get("hook"):
        parts.append(str(project["hook"]))
    parts.extend(str(line or "") for line in project.get("script_lines") or [])
    if project.get("cta"):
        parts.append(str(project["cta"]))
    return [p.strip() for p in parts if p.strip()]


def _polish_locally(source: list[str], style: str) -> str:
    sentences: list[str] = []
    for segment in source:
        sentences.extend(_split_into_short_sentences(segment))
    if not sentences:
        return ""

    energetic = style == "energetic_short"
    pieces: list[str] = []
    for index, sentence in enumerate(sentences):
        sentence = _humanize_sentence(sentence)
        pieces.append(sentence)
        if index == len(sentences) - 1:
            break
        # Heavier pause at the hook boundary and before the closing line.
        if index == 0:
            pieces.append("[pause:short]")
        elif index == len(sentences) - 2:
            pieces.append("[pause:medium]")
        elif not energetic and index % 2 == 1:
            pieces.append("[pause:short]")
        else:
            pieces.append("[pause:short]" if energetic else "[pause:medium]")
    text = " ".join(pieces)
    return re.sub(r"\s+", " ", text).strip()


def _split_into_short_sentences(segment: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+", segment.strip())
    out: list[str] = []
    for sentence in raw:
        sentence = sentence.strip()
        if not sentence:
            continue
        words = sentence.split()
        if len(words) <= 16:
            out.append(sentence)
            continue
        # Long sentence: break at a comma / conjunction near the middle.
        chunks = re.split(r",\s+|\s+(?:mas|porque|e que|então|que)\s+", sentence)
        buffer = ""
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            candidate = f"{buffer} {chunk}".strip()
            if len(candidate.split()) > 14 and buffer:
                out.append(_ensure_terminal(buffer))
                buffer = chunk
            else:
                buffer = candidate
        if buffer:
            out.append(_ensure_terminal(buffer))
    return out


def _humanize_sentence(sentence: str) -> str:
    return _ensure_terminal(sentence.strip())


def _ensure_terminal(sentence: str) -> str:
    sentence = sentence.strip()
    if sentence and sentence[-1] not in ".!?":
        sentence += "."
    return sentence


# ---------------------------------------------------------------------------
# Gemini polisher (optional)
# ---------------------------------------------------------------------------

def _gemini_available() -> bool:
    return bool(config.GEMINI_API_KEY) and config.GENERATION_AI_PROVIDER in {"gemini", "auto"}


def _polish_with_gemini(project: dict[str, Any], source: list[str], style: str) -> str:
    from google import genai  # type: ignore

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = _gemini_prompt(project, source, style)
    response = client.models.generate_content(
        model=config.GEMINI_SCRIPT_MODEL,
        contents=prompt,
    )
    text = str(getattr(response, "text", "") or "").strip()
    text = re.sub(r"^```.*?\n|```$", "", text).strip()
    return text


def _gemini_prompt(project: dict[str, Any], source: list[str], style: str) -> str:
    style_hint = {
        "conversational_story": "conversa natural, contando uma história para um amigo",
        "conversational": "conversa natural e leve",
        "documentary": "documentário calmo e claro",
        "energetic_short": "enérgico e direto, ritmo rápido",
        "dramatic_story": "dramático, com tensão e pausas",
    }.get(style, "conversa natural")
    joined = " ".join(source)
    language = project.get("language") or "pt-BR"
    return (
        "Reescreva o texto abaixo como NARRAÇÃO falada para um vídeo curto vertical.\n"
        f"Estilo: {style_hint}. Idioma: {language}.\n"
        "Regras: frases curtas; soe como pessoa conversando, não enciclopédico; "
        "mantenha os fatos; mantenha gancho e retenção; sem markdown; sem hashtags.\n"
        "Use marcadores de pausa [pause:short] e [pause:medium] onde uma pessoa "
        "naturalmente pausaria. NÃO use outros colchetes.\n"
        "Responda apenas com o texto da narração.\n\n"
        f"TEXTO:\n{joined}"
    )
