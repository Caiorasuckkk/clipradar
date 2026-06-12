from __future__ import annotations

import importlib.util
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from app import config
from app.services.generation_factual_grounding_service import generate_factual_brief


RESEARCH_CACHE_PATH = config.STORAGE_GENERATION_DIR / "research_cache.json"


def get_provider_status() -> dict[str, Any]:
    gemini_package_available = importlib.util.find_spec("google.genai") is not None
    gemini_available = bool(config.GEMINI_API_KEY) and gemini_package_available
    return {
        "provider": _provider(),
        "gemini_available": gemini_available,
        "gemini_package_available": gemini_package_available,
        "gemini_configured": bool(config.GEMINI_API_KEY),
        "grounding_enabled": config.GENERATION_USE_WEB_GROUNDING,
        "grounding_supported": None if not gemini_available else config.GENERATION_USE_WEB_GROUNDING,
        "models": {
            "research": config.GEMINI_RESEARCH_MODEL,
            "script": config.GEMINI_SCRIPT_MODEL,
        },
        "limits": {
            "max_research_calls_per_project": config.GENERATION_MAX_RESEARCH_CALLS_PER_PROJECT,
            "max_script_calls_per_project": config.GENERATION_MAX_SCRIPT_CALLS_PER_PROJECT,
        },
    }


def generate_research_brief(
    niche: str,
    topic: str,
    language: str = "pt-BR",
    tone: str = "curioso",
    force_research: bool = False,
    provider_override: str = "auto",
) -> dict[str, Any]:
    provider = _provider(provider_override)
    grounding_requested = config.GENERATION_USE_WEB_GROUNDING
    cached = None if force_research else _cache_get(niche, topic, language, tone, provider, grounding_requested)
    if cached:
        brief = dict(cached.get("research_brief") or {})
        brief.update(
            {
                "research_cache_hit": True,
                "force_research_used": False,
                "engine_mode": config.GENERATION_ENGINE if config.GENERATION_ENGINE in {"local", "canal_dark"} else "local",
                "provider": provider,
                "fallback_used": bool(brief.get("fallback_used", provider != "gemini")),
            }
        )
        return brief

    if _can_use_gemini(provider):
        try:
            brief = GeminiProvider().generate_research_brief(
                niche=niche,
                topic=topic,
                language=language,
                tone=tone,
            )
            brief["research_cache_hit"] = False
            brief["force_research_used"] = bool(force_research)
            _cache_put(niche, topic, language, tone, provider, bool(brief.get("grounding_used")), brief)
            return brief
        except Exception as error:
            if config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise RuntimeError(f"gemini_research_failed: {error}") from error
            brief = LocalProvider().generate_research_brief(niche, topic, language, tone)
            brief["fallback_used"] = True
            brief["last_llm_error"] = str(error)
            brief["research_cache_hit"] = False
            brief["force_research_used"] = bool(force_research)
            _cache_put(niche, topic, language, tone, "local", False, brief)
            return brief

    brief = LocalProvider().generate_research_brief(niche, topic, language, tone)
    brief["research_cache_hit"] = False
    brief["force_research_used"] = bool(force_research)
    _cache_put(niche, topic, language, tone, provider, False, brief)
    return brief


def generate_script_from_research(
    research_brief: dict[str, Any],
    narrative_plan: dict[str, Any],
    niche: str,
    topic: str,
    duration_seconds: int,
    tone: str,
    language: str,
    script_depth: str,
    narrative_style: str,
    local_fallback: Callable[[], dict[str, Any]],
    provider_override: str = "auto",
) -> dict[str, Any]:
    if _can_use_gemini(_provider(provider_override)):
        try:
            return GeminiProvider().generate_script_from_research(
                research_brief=research_brief,
                narrative_plan=narrative_plan,
                niche=niche,
                topic=topic,
                duration_seconds=duration_seconds,
                tone=tone,
                language=language,
                script_depth=script_depth,
                narrative_style=narrative_style,
            )
        except Exception as error:
            if config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise RuntimeError(f"gemini_script_failed: {error}") from error
            payload = local_fallback()
            payload["fallback_used"] = True
            payload["last_llm_error"] = str(error)
            return payload
    return local_fallback()


def generate_narrative_plan(
    research_brief: dict[str, Any],
    duration_seconds: int,
    script_depth: str,
    narrative_style: str,
    local_fallback: Callable[[], dict[str, Any]],
    provider_override: str = "auto",
) -> dict[str, Any]:
    if _can_use_gemini(_provider(provider_override)):
        try:
            return GeminiProvider().generate_narrative_plan(
                research_brief=research_brief,
                duration_seconds=duration_seconds,
                script_depth=script_depth,
                narrative_style=narrative_style,
            )
        except Exception as error:
            if config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise RuntimeError(f"gemini_narrative_plan_failed: {error}") from error
            payload = local_fallback()
            payload["narrative_plan_fallback_used"] = True
            payload["last_narrative_plan_error"] = str(error)
            return payload
    return local_fallback()


def generate_ideas(
    niche: str,
    topic: str,
    language: str,
    tone: str,
    local_fallback: Callable[[], list[dict[str, Any]]],
    provider_override: str = "auto",
) -> list[dict[str, Any]]:
    if _can_use_gemini(_provider(provider_override)):
        try:
            return GeminiProvider().generate_ideas(niche, topic, language, tone)
        except Exception:
            if config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise
    return local_fallback()


def safe_json_parse(text: str) -> Any:
    content = str(text or "").strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.S)
    if match:
        content = match.group(1).strip()
    start = min([idx for idx in [content.find("{"), content.find("[")] if idx >= 0], default=0)
    content = content[start:]
    return json.loads(content)


def fallback_on_error(error: Exception, fallback: Callable[[], Any]) -> Any:
    if config.GENERATION_REQUIRE_EXTERNAL_AI:
        raise error
    return fallback()


class LocalProvider:
    def generate_research_brief(
        self,
        niche: str,
        topic: str,
        language: str,
        tone: str,
    ) -> dict[str, Any]:
        brief = generate_factual_brief(niche=niche, topic=topic, idea=topic, language=language)
        return {
            **brief,
            "summary": _summary_from_brief(brief),
            "content_angle": brief.get("emotional_angle") or brief.get("conflict") or "",
            "engine_mode": _engine_mode(),
            "provider": "none",
            "fallback_used": True,
            "grounding_used": False,
            "grounding_available": False,
            "grounding_warning": "Gemini indisponível; usando factual grounding local.",
            "source_urls": [],
            "source_titles": [],
            "search_queries": [],
            "research_call_count": 0,
            "last_llm_provider": "none",
            "last_llm_model": "",
            "last_llm_error": "",
        }


class GeminiProvider:
    def __init__(self) -> None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY não configurada.")
        if importlib.util.find_spec("google.genai") is None:
            raise RuntimeError("Pacote google-genai não instalado.")
        from google import genai  # type: ignore

        self._client = genai.Client(api_key=config.GEMINI_API_KEY)

    def generate_research_brief(
        self,
        niche: str,
        topic: str,
        language: str,
        tone: str,
    ) -> dict[str, Any]:
        prompt = _research_prompt(niche, topic, language, tone)
        grounding_warning = ""
        grounding_used = False
        grounding_available = config.GENERATION_USE_WEB_GROUNDING
        try:
            text = self._generate_content(config.GEMINI_RESEARCH_MODEL, prompt, use_grounding=config.GENERATION_USE_WEB_GROUNDING)
            grounding_used = config.GENERATION_USE_WEB_GROUNDING
        except TypeError as error:
            grounding_warning = f"grounding_not_supported: {error}"
            text = self._generate_content(config.GEMINI_RESEARCH_MODEL, prompt, use_grounding=False)
        payload = safe_json_parse(text)
        if not isinstance(payload, dict):
            raise ValueError("gemini_research_not_object")
        return _normalize_research_payload(
            payload=payload,
            provider="gemini",
            fallback_used=False,
            grounding_used=grounding_used,
            grounding_available=grounding_available,
            grounding_warning=grounding_warning,
            model=config.GEMINI_RESEARCH_MODEL,
        )

    def generate_script_from_research(
        self,
        research_brief: dict[str, Any],
        narrative_plan: dict[str, Any],
        niche: str,
        topic: str,
        duration_seconds: int,
        tone: str,
        language: str,
        script_depth: str,
        narrative_style: str,
    ) -> dict[str, Any]:
        prompt = _script_prompt(
            research_brief,
            narrative_plan,
            niche,
            topic,
            duration_seconds,
            tone,
            language,
            script_depth,
            narrative_style,
        )
        text = self._generate_content(config.GEMINI_SCRIPT_MODEL, prompt, use_grounding=False)
        payload = safe_json_parse(text)
        if not isinstance(payload, dict):
            raise ValueError("gemini_script_not_object")
        return {
            "title": str(payload.get("title") or "").strip(),
            "hook": str(payload.get("hook") or "").strip(),
            "script_lines": _string_list(payload.get("script_lines") or payload.get("lines")),
            "cta": str(payload.get("cta") or "").strip(),
            "hashtags": _string_list(payload.get("hashtags")),
            "visual_context": _string_list(payload.get("visual_context")),
            "fact_check_notes": _string_list(payload.get("fact_check_notes")),
            "research_brief": research_brief,
            "narrative_plan": narrative_plan,
            "story_beats": narrative_plan.get("story_beats", []) if isinstance(narrative_plan, dict) else [],
            "source_urls": _string_list(research_brief.get("source_urls")),
            "source_titles": _string_list(research_brief.get("source_titles")),
            "search_queries": _string_list(research_brief.get("search_queries")),
            "engine_mode": "canal_dark",
            "provider": "gemini",
            "fallback_used": False,
            "grounding_used": bool(research_brief.get("grounding_used")),
            "grounding_available": bool(research_brief.get("grounding_available")),
            "grounding_warning": str(research_brief.get("grounding_warning") or ""),
            "last_llm_provider": "gemini",
            "last_llm_model": config.GEMINI_SCRIPT_MODEL,
            "last_llm_error": "",
            "script_call_count": 1,
            "llm_call_count": 1,
        }

    def generate_narrative_plan(
        self,
        research_brief: dict[str, Any],
        duration_seconds: int,
        script_depth: str,
        narrative_style: str,
    ) -> dict[str, Any]:
        prompt = _narrative_plan_prompt(research_brief, duration_seconds, script_depth, narrative_style)
        text = self._generate_content(config.GEMINI_SCRIPT_MODEL, prompt, use_grounding=False)
        payload = safe_json_parse(text)
        if not isinstance(payload, dict):
            raise ValueError("gemini_narrative_plan_not_object")
        payload["script_depth"] = script_depth
        payload["narrative_style"] = narrative_style
        payload["narrative_plan_fallback_used"] = False
        payload["last_llm_provider"] = "gemini"
        payload["last_llm_model"] = config.GEMINI_SCRIPT_MODEL
        payload["llm_call_count"] = int(payload.get("llm_call_count") or 0) + 1
        payload["story_beats"] = [
            item for item in payload.get("story_beats", []) if isinstance(item, dict)
        ]
        return payload

    def generate_ideas(self, niche: str, topic: str, language: str, tone: str) -> list[dict[str, Any]]:
        prompt = (
            "Gere 6 ideias de shorts faceless em JSON array. Campos: idea_id,title,niche,topic,"
            "angle,hook,why_it_might_work,target_emotion,curiosity_gap,risk_level,"
            "fact_check_needed,suggested_hashtags,visual_direction. Use ângulos específicos, "
            "fact-checkable e com potencial de curiosidade.\n"
            f"Nicho: {niche}\nTema: {topic}\nIdioma: {language}\nTom: {tone}"
        )
        text = self._generate_content(config.GEMINI_RESEARCH_MODEL, prompt, use_grounding=False)
        payload = safe_json_parse(text)
        if not isinstance(payload, list):
            raise ValueError("gemini_ideas_not_list")
        ideas: list[dict[str, Any]] = []
        for index, item in enumerate(payload[:6], start=1):
            if not isinstance(item, dict):
                continue
            ideas.append(
                {
                    **item,
                    "idea_id": str(item.get("idea_id") or f"idea_{index}"),
                    "engine_mode": "canal_dark",
                    "provider": "gemini",
                    "fallback_used": False,
                    "suggested_hashtags": _string_list(item.get("suggested_hashtags")),
                }
            )
        return ideas

    def _generate_content(self, model: str, prompt: str, use_grounding: bool = False) -> str:
        kwargs: dict[str, Any] = {}
        if use_grounding:
            # The SDK grounding shape changes by model/version. Keep this isolated so
            # unsupported installations can fall back to a normal Gemini call.
            from google.genai import types  # type: ignore

            kwargs["config"] = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            **kwargs,
        )
        return str(getattr(response, "text", "") or "")


def _normalize_research_payload(
    payload: dict[str, Any],
    provider: str,
    fallback_used: bool,
    grounding_used: bool,
    grounding_available: bool,
    grounding_warning: str,
    model: str,
) -> dict[str, Any]:
    return {
        "engine_mode": "canal_dark" if provider == "gemini" else _engine_mode(),
        "provider": provider,
        "fallback_used": fallback_used,
        "grounding_used": grounding_used,
        "grounding_available": grounding_available,
        "grounding_warning": grounding_warning,
        "subject": str(payload.get("subject") or "").strip(),
        "summary": str(payload.get("summary") or "").strip(),
        "key_entities": _string_list(payload.get("key_entities")),
        "timeline": _string_list(payload.get("timeline")),
        "key_facts": _string_list(payload.get("key_facts")),
        "conflict": str(payload.get("conflict") or "").strip(),
        "consequence": str(payload.get("consequence") or "").strip(),
        "emotional_angle": str(payload.get("emotional_angle") or "").strip(),
        "content_angle": str(payload.get("content_angle") or payload.get("emotional_angle") or "").strip(),
        "fact_check_notes": _string_list(payload.get("fact_check_notes")),
        "source_urls": _string_list(payload.get("source_urls")),
        "source_titles": _string_list(payload.get("source_titles")),
        "search_queries": _string_list(payload.get("search_queries")),
        "confidence": _confidence(payload.get("confidence")),
        "source_mode": "ai_generated",
        "research_call_count": 1,
        "last_llm_provider": provider,
        "last_llm_model": model,
        "last_llm_error": "",
    }


def _cache_get(niche: str, topic: str, language: str, tone: str, provider: str, grounding: bool) -> dict[str, Any] | None:
    cache = _load_cache()
    item = cache.get(_cache_key(niche, topic, language, tone, provider, grounding))
    if not isinstance(item, dict):
        return None
    try:
        expires_at = datetime.fromisoformat(str(item.get("expires_at") or ""))
    except ValueError:
        return None
    if expires_at < datetime.utcnow():
        return None
    return item


def _cache_put(niche: str, topic: str, language: str, tone: str, provider: str, grounding: bool, brief: dict[str, Any]) -> None:
    now = datetime.utcnow()
    cache = _load_cache()
    cache[_cache_key(niche, topic, language, tone, provider, grounding)] = {
        "research_brief": brief,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "source_urls": brief.get("source_urls", []),
        "confidence": brief.get("confidence", "low"),
        "expires_at": (now + timedelta(days=config.GENERATION_RESEARCH_CACHE_TTL_DAYS)).isoformat(),
    }
    RESEARCH_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESEARCH_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_cache() -> dict[str, Any]:
    if not RESEARCH_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(RESEARCH_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _cache_key(niche: str, topic: str, language: str, tone: str, provider: str, grounding: bool) -> str:
    raw = "|".join([niche, topic, language, tone, provider, str(grounding)]).lower()
    return re.sub(r"[^a-z0-9À-ÿ|_-]+", "_", raw).strip("_")


def _research_prompt(niche: str, topic: str, language: str, tone: str) -> str:
    return (
        "Você está criando um brief factual para um short narrado/faceless, não o roteiro final. "
        "Pesquise ou organize fatos concretos, entidades principais, linha do tempo, conflito, "
        "consequência, ângulo emocional e gancho de short. Retorne somente JSON válido com: "
        "subject,summary,key_entities,timeline,key_facts,conflict,consequence,emotional_angle,"
        "content_angle,fact_check_notes,source_urls,source_titles,search_queries,confidence. "
        "Não invente nomes, placares, datas ou acusações sem base. Se não tiver fontes, deixe "
        "source_urls vazio e marque fact_check_notes. Separe fatos de interpretação.\n"
        f"Nicho: {niche}\nTema: {topic}\nIdioma: {language}\nTom: {tone}"
    )


def _narrative_plan_prompt(
    research_brief: dict[str, Any],
    duration_seconds: int,
    script_depth: str,
    narrative_style: str,
) -> str:
    return (
        "Você recebeu um research_brief factual. Sua tarefa NÃO é escrever o roteiro ainda. "
        "Sua tarefa é transformar os fatos em uma estrutura narrativa de short. Retorne somente "
        "JSON válido com: main_claim, central_question, emotional_core, conflict, stakes, "
        "hidden_detail, turning_point, consequence, interpretation, closing_question, story_beats. "
        "story_beats deve ser lista de objetos com beat_id, role, content, facts_used e emotional_goal. "
        "Regras: não invente fatos fora do research_brief; não exagere afirmações sem fonte; "
        "separe fato de interpretação; crie tensão narrativa; identifique por que o tema importa; "
        "evite roteiro raso que só lista acontecimentos; cada story beat deve usar pelo menos um "
        "fato ou interpretação do brief; não escreva script_lines nesta etapa.\n"
        f"Duração alvo: {duration_seconds}s\nProfundidade: {script_depth}\nEstilo: {narrative_style}\n"
        f"Research brief: {json.dumps(research_brief, ensure_ascii=False)}"
    )


def _script_prompt(
    research_brief: dict[str, Any],
    narrative_plan: dict[str, Any],
    niche: str,
    topic: str,
    duration_seconds: int,
    tone: str,
    language: str,
    script_depth: str,
    narrative_style: str,
) -> str:
    line_hint = "8 a 12 linhas" if duration_seconds <= 60 else "12 a 18 linhas" if duration_seconds <= 90 else "18 a 26 linhas"
    pacing_hint = (
        "direto, sem detalhes secundários"
        if duration_seconds <= 60
        else "com contexto, conflito, virada e consequência"
        if duration_seconds <= 90
        else "mais completo, com tensão, contexto e fechamento forte"
    )
    return (
        "Você é roteirista de shorts faceless. Responda somente JSON válido com title,hook,"
        "script_lines,cta,hashtags,visual_context,fact_check_notes,estimated_duration_seconds,"
        "voice_style,pacing. script_lines deve conter apenas falas finais de narração, com frases "
        "curtas e naturais. Nada de metalinguagem, nada de 'o roteiro deve', nada de 'use uma imagem' "
        "dentro de script_lines. Use fatos do research_brief e a estrutura do narrative_plan; "
        "não invente dados fora deles. Não faça apenas fato 1, fato 2, fato 3. O roteiro deve "
        "respeitar content_format, concrete_promise e viewer_reason_to_watch do research_brief. "
        "Para player_watchlist ou match_preview, é obrigatório nomear evento, times e pessoas atuais "
        "confirmadas no brief, explicar por que importam agora e entregar uma promessa específica nos "
        "primeiros 3 segundos. Se faltarem nomes ou evento, não invente: marque a limitação em "
        "fact_check_notes e produza apenas o formato suportado pelos fatos. É proibido escrever ensaio "
        "genérico sobre jogadores, genialidade, explosão ou legado. Não cite Pelé, Maradona, Ronaldo, "
        "Cruyff, Beckenbauer ou Messi sem relação direta e comprovada com o evento atual. "
        "transformar fatos em contexto, tensão, detalhe pouco percebido, virada, consequência "
        "e reflexão/pergunta final. "
        "Antes de responder, verifique se cada item de script_lines poderia ser lido por um narrador "
        "em voz alta no vídeo. Se não puder, reescreva. Visual deve ir apenas em visual_context; "
        "hashtags e CTA separados; fact-check separado.\n"
        f"Nicho: {niche}\nTema: {topic}\nDuração alvo: {duration_seconds}s\n"
        f"Tamanho esperado: {line_hint}; ritmo: {pacing_hint}. Evite enrolação.\n"
        f"Idioma: {language}\nTom: {tone}\nProfundidade: {script_depth}\nEstilo narrativo: {narrative_style}\n"
        f"Research brief: {json.dumps(research_brief, ensure_ascii=False)}\n"
        f"Narrative plan: {json.dumps(narrative_plan, ensure_ascii=False)}"
    )


def _summary_from_brief(brief: dict[str, Any]) -> str:
    facts = _string_list(brief.get("key_facts"))
    if facts:
        return " ".join(facts[:2])
    return str(brief.get("subject") or "")


def _can_use_gemini(provider: str | None = None) -> bool:
    active_provider = provider or _provider()
    return active_provider == "gemini" and bool(config.GEMINI_API_KEY) and importlib.util.find_spec("google.genai") is not None


def _provider(provider_override: str = "auto") -> str:
    if provider_override == "gemini":
        return "gemini"
    if provider_override == "local":
        return "none"
    return config.GENERATION_AI_PROVIDER if config.GENERATION_AI_PROVIDER in {"none", "gemini"} else "none"


def _engine_mode() -> str:
    return config.GENERATION_ENGINE if config.GENERATION_ENGINE in {"local", "canal_dark"} else "local"


def _confidence(value: object) -> str:
    text = str(value or "low").strip().lower()
    return text if text in {"high", "medium", "low"} else "low"


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []
