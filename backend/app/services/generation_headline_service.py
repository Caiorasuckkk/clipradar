"""Big on-screen HEADLINES (the editorial punch text like NO RESPECT / ISSO DIZ
TUDO that football edits overlay on top of the word-by-word captions).

The LLM derives 2-3 short uppercase phrases from the finished script, in the
SAME language as the narration. Falls back to a simple heuristic if no external
LLM is available (OpenAI is the primary; other providers without a chat method
get the heuristic). The render overlays these as a separate ASS style.
"""

from __future__ import annotations

import re
from typing import Any

from app import config
from app.services import generation_llm_provider_service as llm

MAX_HEADLINES = 3
_MAX_WORDS = 4


def generate_headlines(project: dict[str, Any]) -> list[str]:
    hook = str(project.get("hook") or "").strip()
    lines = [str(line or "").strip() for line in (project.get("script_lines") or []) if str(line or "").strip()]
    cta = str(project.get("cta") or "").strip()
    language = str(project.get("language") or "pt-BR")
    if not hook and not lines:
        return []
    body = " ".join([hook, *lines, cta]).strip()
    try:
        text = _llm_json(_prompt(body, language))
        data = llm.safe_json_parse(text)
        heads = _clean_headlines(data.get("headlines") if isinstance(data, dict) else data)
        if heads:
            return heads[:MAX_HEADLINES]
    except Exception:
        pass
    return _heuristic(hook, lines, cta)


def _prompt(body: str, language: str) -> str:
    return (
        "Você cria MANCHETES curtas de impacto para sobrepor num vídeo vertical curto "
        "de futebol (estilo edit viral). A partir do roteiro abaixo, devolva um JSON "
        '{"headlines": ["...", "..."]} com 2 a 3 manchetes que marcam os momentos-chave '
        "(o contraste, a polêmica, a virada). REGRAS: cada manchete tem 1 a 4 palavras, em "
        f"CAIXA ALTA, no MESMO idioma do roteiro ({language}), forte e direta (ex.: 'SEM "
        "RESPEITO', 'PURO RESPEITO', 'ISSO DIZ TUDO'). Sem hashtags, sem emojis, sem "
        "pontuação no fim. Roteiro:\n" + body
    )


def _llm_json(prompt: str) -> str:
    name = llm._active_provider("auto")
    if name == "none":
        raise RuntimeError("no_provider")
    provider = llm._make_provider(name)
    chat = getattr(provider, "_chat", None)
    if not callable(chat):
        raise RuntimeError("provider_without_chat")
    model = getattr(config, "GENERATION_OPENAI_CHEAP_MODEL", "gpt-4o-mini")
    return chat(model, prompt, json_object=True)


def _clean_headlines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = re.sub(r"\s+", " ", str(item or "")).strip().strip(".,;:!?\"'").upper()
        if not text:
            continue
        if len(text.split()) > _MAX_WORDS:
            text = " ".join(text.split()[:_MAX_WORDS])
        key = text.lower()
        if key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _heuristic(hook: str, lines: list[str], cta: str) -> list[str]:
    """No LLM: derive a couple of punch phrases from the hook and the last line
    (usually the moral/payoff). Weak but better than a bare screen."""
    candidates: list[str] = []
    if hook:
        candidates.append(hook)
    if lines:
        candidates.append(lines[-1])
    heads: list[str] = []
    for text in candidates:
        words = re.sub(r"[^\w\sÀ-ÿ]", "", text).split()
        if words:
            heads.append(" ".join(words[:_MAX_WORDS]).upper())
    return _clean_headlines(heads)
