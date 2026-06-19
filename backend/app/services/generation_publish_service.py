"""Publish pack: per-video title options, description/caption, hashtags and best
posting times — ready to copy-paste. Language-aware (one pack per video/language).

The titles/description/hashtags come from a cheap LLM call grounded in the video's
own theme/script; best-times is a curated static guide by language/region (there is
no reliable live "trending hashtags/times" API, so we don't fake one)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app import config
from app.services.generation_llm_provider_service import (
    _active_provider,
    _make_provider,
    safe_json_parse,
)
from app.services.generation_workspace_service import get_project, update_project


_BEST_TIMES = {
    "pt": (
        "📱 TikTok / Reels: 12h–13h e 19h–22h (horário de Brasília)\n"
        "▶️ YouTube Shorts: 12h–15h e 18h–21h; fim de semana de manhã\n"
        "💡 Ajuste pelo seu YouTube Studio / TikTok depois de ~2 semanas de dados."
    ),
    "en": (
        "📱 TikTok / Reels: 6–9am and 7–10pm (ET)\n"
        "▶️ YouTube Shorts: 12–3pm and 7–9pm ET; Tue–Thu tend to peak\n"
        "💡 Refine with your YouTube Studio / TikTok analytics after ~2 weeks."
    ),
}


def _lang_key(language: str) -> str:
    return "en" if str(language or "").strip().lower().startswith("en") else "pt"


def publish_package(project_id: str, refresh: bool = False) -> dict[str, Any] | None:
    """Return (and cache) the publish pack for a project. Generates on first call."""
    project = get_project(project_id)
    if not project:
        return None
    if not refresh and project.get("publish_titles"):
        return _pack_from_project(project)

    pack = _generate(project)
    update_project(
        project_id,
        {
            **project,
            "publish_titles": pack["titles"],
            "publish_description": pack["description"],
            "publish_hashtags": pack["hashtags"],
            "publish_best_times": pack["best_times"],
            "publish_generated_at": datetime.utcnow().isoformat(),
        },
    )
    return pack


def _pack_from_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "titles": list(project.get("publish_titles") or []),
        "description": str(project.get("publish_description") or ""),
        "hashtags": list(project.get("publish_hashtags") or []),
        "best_times": str(project.get("publish_best_times") or "")
        or _BEST_TIMES[_lang_key(project.get("language"))],
        "language": str(project.get("language") or "pt-BR"),
    }


def _generate(project: dict[str, Any]) -> dict[str, Any]:
    language = str(project.get("language") or "pt-BR")
    titles, description, hashtags = _llm_pack(project, language)
    if not titles:  # fallback when no LLM
        titles = [t for t in [str(project.get("title") or "").strip()] if t]
        description = str(project.get("hook") or project.get("title") or "").strip()
        hashtags = _norm_hashtags(project.get("hashtags") or [])
    return {
        "titles": titles[:3],
        "description": description,
        "hashtags": hashtags[:15],
        "best_times": _BEST_TIMES[_lang_key(language)],
        "language": language,
    }


def _llm_pack(project: dict[str, Any], language: str) -> tuple[list[str], str, list[str]]:
    if _active_provider() != "openai":
        return [], "", []
    try:
        provider = _make_provider("openai")
        text = provider._chat(config.GENERATION_OPENAI_CHEAP_MODEL, _prompt(project, language), json_object=True)
        data = safe_json_parse(text)
        if not isinstance(data, dict):
            return [], "", []
        titles = [str(t).strip() for t in (data.get("titles") or []) if str(t).strip()]
        description = str(data.get("description") or "").strip()
        hashtags = _norm_hashtags(data.get("hashtags") or [])
        return titles, description, hashtags
    except Exception:  # noqa: BLE001 - best-effort; caller falls back
        return [], "", []


def _norm_hashtags(raw: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        tag = re.sub(r"\s+", "", str(item or "").strip())
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag.lstrip("#")
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            out.append(tag)
    return out


def _prompt(project: dict[str, Any], language: str) -> str:
    title = str(project.get("title") or project.get("idea") or "").strip()
    niche = str(project.get("niche") or "").strip()
    parts = [str(project.get("hook") or "")]
    parts += [str(x) for x in (project.get("script_lines") or [])]
    parts.append(str(project.get("cta") or ""))
    script = " ".join(p for p in parts if p).strip()[:700]
    return (
        "Você é especialista em viralizar vídeos curtos (Shorts/TikTok/Reels). "
        f"Com base no vídeo abaixo, gere um pacote de publicação TODO no idioma {language}.\n"
        f"TÍTULO/TEMA: {title}\nNICHO: {niche}\nROTEIRO (resumo): {script}\n\n"
        "Gere: (a) 3 TÍTULOS curtos e chamativos com gancho/curiosidade (até ~70 caracteres, "
        "sem aspas), variando o ângulo; (b) 1 DESCRIÇÃO/legenda de 1-2 frases (gancho + chamada "
        "pra seguir), no tom do vídeo; (c) 10 a 15 HASHTAGS relevantes misturando ESPECÍFICAS do "
        "nicho + AMPLAS de alto alcance (ex.: #fyp #viral #shorts #reels), todas começando com # "
        "e sem espaços.\n"
        'Responda APENAS um JSON: {"titles": ["..."], "description": "...", "hashtags": ["#..."]}.'
    )
