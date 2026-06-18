"""Trending-topic suggester for the história/curiosidades niche.

Surfaces the topics that are most searched / most viewed right now on YouTube and
TikTok in this niche, so the creator picks themes that already have hype. Uses the
OpenAI web-search tool when available, falls back to a plain LLM call, then to a
curated evergreen list. Results are cached for a few hours (trends move slowly day
to day and web search is the most expensive call in the app)."""
from __future__ import annotations

import time
from typing import Any

from app import config
from app.services.generation_llm_provider_service import (
    _active_provider,
    _make_provider,
    safe_json_parse,
)

# language -> (fetched_at, topics)
_CACHE: dict[str, tuple[float, list[dict[str, str]]]] = {}
_CACHE_TTL_SECONDS = 60 * 60 * 6  # 6h

_MAX_TOPICS = 12


def trending_topics(
    language: str = "pt-BR", limit: int = 10, refresh: bool = False
) -> dict[str, Any]:
    """Top trending história/curiosidades topics. Returns {topics, source, cached}."""
    limit = max(1, min(int(limit or 10), _MAX_TOPICS))
    key = (language or "pt-BR").strip().lower()
    now = time.time()

    if not refresh:
        cached = _CACHE.get(key)
        if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
            return {"topics": cached[1][:limit], "source": "cache", "cached": True}

    topics, source = _fetch(language, _MAX_TOPICS)
    if not topics:
        topics, source = _fallback(language), "fallback"
    if topics:
        _CACHE[key] = (now, topics)
    return {"topics": topics[:limit], "source": source, "cached": False}


def _fetch(language: str, limit: int) -> tuple[list[dict[str, str]], str]:
    """Try web search first (real hype), then a plain LLM call. Never raises."""
    if _active_provider() != "openai":
        return [], "none"
    prompt = _prompt(language, limit)
    provider = _make_provider("openai")

    if config.GENERATION_OPENAI_USE_WEB_SEARCH:
        try:
            text = provider._web_search(config.GENERATION_OPENAI_RESEARCH_MODEL, prompt)
            topics = _parse(text)
            if topics:
                return topics, "web_search"
        except Exception:  # noqa: BLE001 - fall through to cheaper path
            pass

    try:
        text = provider._chat(config.GENERATION_OPENAI_CHEAP_MODEL, prompt, json_object=False)
        topics = _parse(text)
        if topics:
            return topics, "llm"
    except Exception:  # noqa: BLE001 - fall through to static fallback
        pass
    return [], "none"


def _prompt(language: str, limit: int) -> str:
    return (
        f"Liste os {limit} temas de HISTÓRIA e CURIOSIDADES que estão MAIS em alta AGORA — "
        f"os mais pesquisados e mais assistidos no YouTube e no TikTok. "
        f"Escreva tudo no idioma {language}. "
        "Priorize temas com forte potencial viral para vídeos verticais curtos (Shorts/Reels): "
        "fatos chocantes, mistérios, 'você sabia', histórias pouco conhecidas. "
        "\n\nREGRA MAIS IMPORTANTE — SEJA ESPECÍFICO E NOMEADO: cada tema DEVE citar um "
        "personagem, evento, lugar ou fato CONCRETO e com nome próprio. NUNCA entregue "
        "categorias, listas ou temas guarda-chuva. "
        "RUIM (proibido): 'Fatos bizarros da antiguidade', 'Personagens históricos omitidos', "
        "'Mistérios não resolvidos', 'Curiosidades sobre o Egito', 'Top 5 imperadores'. "
        "BOM (faça assim): 'Calígula nomeou seu cavalo Incitatus como senador', "
        "'Hiroo Onoda se escondeu na selva por 29 anos após a guerra', "
        "'A maldição de Tutancâmon matou quem abriu a tumba', "
        "'Cleópatra falava 9 idiomas e era uma gênia da política'. "
        "Cada title deve ser uma frase com um SUJEITO NOMEADO específico, pronta para virar um vídeo sozinha. "
        "Varie os personagens/épocas — não repita o mesmo personagem. "
        "\n\nResponda APENAS com um array JSON, sem texto antes ou depois, com objetos no formato: "
        '{"title": "...", "hook": "...", "why": "..."} '
        "onde title é o tema específico e nomeado, hook é uma primeira frase que prende em 2 segundos, "
        "e why explica em uma frase curta por que está em alta."
    )


def _parse(text: str) -> list[dict[str, str]]:
    data = safe_json_parse(text)
    if isinstance(data, dict):
        # tolerate {"topics": [...]} or {"items": [...]}
        for key in ("topics", "items", "data", "results"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        return []
    out: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            if isinstance(item, str) and item.strip():
                out.append({"title": item.strip(), "hook": "", "why": ""})
            continue
        title = str(item.get("title") or item.get("tema") or item.get("topic") or "").strip()
        if not title:
            continue
        out.append(
            {
                "title": title[:120],
                "hook": str(item.get("hook") or item.get("gancho") or "").strip()[:160],
                "why": str(item.get("why") or item.get("porque") or item.get("motivo") or "").strip()[:160],
            }
        )
    return out


def _fallback(language: str) -> list[dict[str, str]]:
    lang = (language or "pt-BR").strip().lower()
    return _FALLBACK_EN if lang.startswith("en") else _FALLBACK_PT


_FALLBACK_PT: list[dict[str, str]] = [
    {"title": "O imperador romano que nomeou seu cavalo senador", "hook": "Esse imperador era tão louco que deu um cargo público pro próprio cavalo.", "why": "História bizarra de fácil viralização."},
    {"title": "A rainha do Egito que falava 9 idiomas", "hook": "Cleópatra não era só bonita — era um gênio que dominava 9 línguas.", "why": "Cleópatra é busca eterna e rende ganchos."},
    {"title": "O homem que sobreviveu a duas bombas atômicas", "hook": "Ele estava em Hiroshima. Três dias depois, em Nagasaki.", "why": "Fato histórico chocante e pouco conhecido."},
    {"title": "Por que os egípcios removiam o cérebro pelo nariz", "hook": "Na mumificação, o cérebro saía por um lugar inesperado.", "why": "Curiosidade macabra de alto engajamento."},
    {"title": "A cidade que foi soterrada em segundos por um vulcão", "hook": "Pompeia parou no tempo — corpos congelados pelo vulcão.", "why": "Pompeia tem apelo visual e mistério."},
    {"title": "O soldado que se escondeu na selva por 29 anos", "hook": "A guerra acabou, mas ninguém avisou esse soldado.", "why": "História real surpreendente."},
    {"title": "A verdade sobre os gladiadores que ninguém conta", "hook": "Gladiador quase nunca lutava até a morte — e o motivo é dinheiro.", "why": "Quebra de expectativa sobre tema popular."},
    {"title": "O faraó menino e a maldição de Tutancâmon", "hook": "Quem abriu a tumba dele começou a morrer misteriosamente.", "why": "Mistério clássico que sempre rende."},
    {"title": "A mulher que viveu em 3 séculos diferentes", "hook": "Ela nasceu no século 19 e morreu no século 21.", "why": "Curiosidade que parece impossível."},
    {"title": "Por que a Muralha da China não é visível do espaço", "hook": "Todo mundo repete isso — e está completamente errado.", "why": "Desmonte de mito muito buscado."},
    {"title": "O banquete que durou 10 anos no império persa", "hook": "Um rei deu uma festa que não parou por uma década.", "why": "Exagero histórico fascinante."},
    {"title": "A bactéria que pode estar viva há milhões de anos", "hook": "Cientistas acordaram algo que dormia desde os dinossauros.", "why": "Cruzamento de história e ciência viral."},
]

_FALLBACK_EN: list[dict[str, str]] = [
    {"title": "The Roman emperor who made his horse a senator", "hook": "This emperor was so insane he gave his horse a government job.", "why": "Bizarre history, easy to go viral."},
    {"title": "The queen of Egypt who spoke 9 languages", "hook": "Cleopatra wasn't just beautiful — she was a genius fluent in 9 languages.", "why": "Cleopatra is an evergreen search."},
    {"title": "The man who survived two atomic bombs", "hook": "He was in Hiroshima. Three days later, in Nagasaki.", "why": "Shocking, little-known fact."},
    {"title": "Why Egyptians removed the brain through the nose", "hook": "During mummification, the brain came out a surprising way.", "why": "Macabre curiosity, high engagement."},
    {"title": "The city buried in seconds by a volcano", "hook": "Pompeii froze in time — bodies preserved by the eruption.", "why": "Strong visual appeal and mystery."},
    {"title": "The soldier who hid in the jungle for 29 years", "hook": "The war ended, but no one told this soldier.", "why": "Astonishing true story."},
    {"title": "The truth about gladiators nobody tells you", "hook": "Gladiators rarely fought to the death — and the reason is money.", "why": "Subverts a popular belief."},
    {"title": "The boy pharaoh and the curse of Tutankhamun", "hook": "Everyone who opened his tomb started dying mysteriously.", "why": "Classic mystery that always performs."},
    {"title": "The woman who lived across three centuries", "hook": "She was born in the 1800s and died in the 2000s.", "why": "Sounds impossible — pure curiosity."},
    {"title": "Why the Great Wall of China isn't visible from space", "hook": "Everyone repeats this — and it's completely wrong.", "why": "Debunks a widely searched myth."},
    {"title": "The banquet that lasted 10 years in Persia", "hook": "A king threw a party that didn't stop for a decade.", "why": "Fascinating historical excess."},
    {"title": "The bacteria that may have been alive for millions of years", "hook": "Scientists woke up something that slept since the dinosaurs.", "why": "History-meets-science viral combo."},
]
