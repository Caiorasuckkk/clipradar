from __future__ import annotations

import ast
import base64
import importlib.util
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from app import config
from app.services.generation_factual_grounding_service import generate_factual_brief


RESEARCH_CACHE_PATH = config.STORAGE_GENERATION_DIR / "research_cache.json"

# Retry transient Gemini overloads (503/UNAVAILABLE/429) — short backoff so the
# whole pipeline (research, script, judge, visuals) survives demand spikes.
_MAX_TRANSIENT_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 2.0


def _is_transient_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in ["503", "unavailable", "overloaded", "high demand", "429", "rate limit", "resource_exhausted"]
    )


def get_provider_status() -> dict[str, Any]:
    provider = _provider()
    gemini_package_available = importlib.util.find_spec("google.genai") is not None
    gemini_available = _gemini_ready()
    openai_available = _openai_ready()
    if provider == "openai":
        models = {
            "research": config.GENERATION_OPENAI_RESEARCH_MODEL,
            "script": config.GENERATION_OPENAI_SCRIPT_MODEL,
            "cheap": config.GENERATION_OPENAI_CHEAP_MODEL,
        }
        grounding_enabled = config.GENERATION_OPENAI_USE_WEB_SEARCH
        external_available = openai_available
    else:
        models = {
            "research": config.GEMINI_RESEARCH_MODEL,
            "script": config.GEMINI_SCRIPT_MODEL,
        }
        grounding_enabled = config.GENERATION_USE_WEB_GROUNDING
        external_available = gemini_available
    return {
        "provider": provider,
        "external_available": external_available,
        "gemini_available": gemini_available,
        "gemini_package_available": gemini_package_available,
        "gemini_configured": bool(config.GEMINI_API_KEY),
        "openai_available": openai_available,
        "openai_configured": bool(config.OPENAI_API_KEY),
        "grounding_enabled": grounding_enabled,
        "grounding_supported": None if not external_available else grounding_enabled,
        "models": models,
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
                "fallback_used": bool(brief.get("fallback_used", provider not in {"gemini", "openai"})),
            }
        )
        return brief

    if _provider_ready(provider):
        try:
            brief = _make_provider(provider).generate_research_brief(
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
                raise RuntimeError(f"{provider}_research_failed: {error}") from error
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
    critique: str = "",
    scriptwriter: str = "",
) -> dict[str, Any]:
    name = _active_provider(provider_override)
    if name != "none":
        try:
            return _make_provider(name).generate_script_from_research(
                research_brief=research_brief,
                narrative_plan=narrative_plan,
                niche=niche,
                topic=topic,
                duration_seconds=duration_seconds,
                tone=tone,
                language=language,
                script_depth=script_depth,
                narrative_style=narrative_style,
                critique=critique,
                scriptwriter=scriptwriter,
            )
        except Exception as error:
            if config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise RuntimeError(f"{name}_script_failed: {error}") from error
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
    name = _active_provider(provider_override)
    if name != "none":
        try:
            return _make_provider(name).generate_narrative_plan(
                research_brief=research_brief,
                duration_seconds=duration_seconds,
                script_depth=script_depth,
                narrative_style=narrative_style,
            )
        except Exception as error:
            if config.GENERATION_REQUIRE_EXTERNAL_AI:
                raise RuntimeError(f"{name}_narrative_plan_failed: {error}") from error
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
    name = _active_provider(provider_override)
    if name != "none":
        try:
            return _make_provider(name).generate_ideas(niche, topic, language, tone)
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
    # Trim to the outermost balanced JSON value (drops trailing prose/garbage).
    balanced = _balanced_slice(content)
    if balanced:
        content = balanced
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Most common LLM slip: trailing commas before } or ].
        cleaned = re.sub(r",(\s*[}\]])", r"\1", content)
        return json.loads(cleaned)


def _balanced_slice(content: str) -> str:
    if not content:
        return ""
    open_char = content[0]
    close_char = {"{": "}", "[": "]"}.get(open_char)
    if not close_char:
        return ""
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(content):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return content[: index + 1]
    return ""


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
        critique: str = "",
        scriptwriter: str = "",
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
            critique=critique,
            scriptwriter=scriptwriter,
        )
        text = self._generate_content(config.GEMINI_SCRIPT_MODEL, prompt, use_grounding=False)
        payload = safe_json_parse(text)
        if not isinstance(payload, dict):
            raise ValueError("gemini_script_not_object")
        return _build_script_result(payload, research_brief, narrative_plan, "gemini", config.GEMINI_SCRIPT_MODEL)

    def generate_visual_queries(
        self,
        script_lines: list[str],
        contexts: list[str],
        niche: str,
        title: str,
        language: str,
        research_brief: dict[str, Any],
    ) -> list[dict[str, Any]]:
        prompt = _visual_queries_prompt(script_lines, contexts, niche, title, research_brief)
        text = self._generate_content(config.GEMINI_SCRIPT_MODEL, prompt, use_grounding=False)
        data = safe_json_parse(text)
        if not isinstance(data, list):
            raise ValueError("gemini_visual_queries_not_list")
        return _build_visual_plan(data)

    def judge_script(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = _judge_prompt(payload)
        text = self._generate_content(config.GEMINI_JUDGE_MODEL, prompt, use_grounding=False)
        data = safe_json_parse(text)
        if not isinstance(data, dict):
            raise ValueError("gemini_judge_not_object")
        return _build_judge_result(data, config.GEMINI_JUDGE_MODEL)

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
        return _finalize_narrative_plan(
            payload, "gemini", config.GEMINI_SCRIPT_MODEL, script_depth, narrative_style
        )

    def generate_ideas(self, niche: str, topic: str, language: str, tone: str) -> list[dict[str, Any]]:
        prompt = _IDEAS_PROMPT.format(niche=niche, topic=topic, language=language, tone=tone)
        text = self._generate_content(config.GEMINI_RESEARCH_MODEL, prompt, use_grounding=False)
        payload = safe_json_parse(text)
        if not isinstance(payload, list):
            raise ValueError("gemini_ideas_not_list")
        return _build_ideas(payload, "gemini")

    def _generate_content(self, model: str, prompt: str, use_grounding: bool = False) -> str:
        kwargs: dict[str, Any] = {}
        if use_grounding:
            # The SDK grounding shape changes by model/version. Keep this isolated so
            # unsupported installations can fall back to a normal Gemini call.
            from google.genai import types  # type: ignore

            kwargs["config"] = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        last_error: Exception | None = None
        for attempt in range(_MAX_TRANSIENT_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    **kwargs,
                )
                return str(getattr(response, "text", "") or "")
            except Exception as error:  # noqa: BLE001 - retry only transient overloads
                last_error = error
                if attempt >= _MAX_TRANSIENT_RETRIES or not _is_transient_error(error):
                    raise
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
        if last_error:
            raise last_error
        return ""


def _narration_lines(value: object, cta: str = "") -> list[str]:
    """Coerce script_lines into clean spoken sentences.

    The model occasionally returns objects (e.g. {factual, interpretation}) or
    nested structures inside script_lines; flatten those to their text instead of
    leaking a dict repr into the narration. Also drops a trailing line that just
    duplicates the CTA.
    """
    raw = value if isinstance(value, list) else [value]
    lines: list[str] = []
    for item in raw:
        # A repair step may have already stringified a dict ({'factual': ...});
        # recover the real object so we extract its text, not its repr.
        if isinstance(item, str) and item.strip().startswith("{") and item.strip().endswith("}"):
            parsed = _try_parse_mapping(item)
            if parsed is not None:
                item = parsed
        text = ""
        if isinstance(item, dict):
            for key in ("line", "text", "content", "narration", "sentence", "factual", "interpretation"):
                if str(item.get(key) or "").strip():
                    text = str(item.get(key)).strip()
                    break
            if not text:
                text = " ".join(str(v).strip() for v in item.values() if isinstance(v, str) and str(v).strip())
        elif isinstance(item, str):
            text = item
        else:
            text = str(item or "")
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
    normalized_cta = re.sub(r"\s+", " ", str(cta or "")).strip().lower()
    if lines and normalized_cta and lines[-1].lower() == normalized_cta:
        lines.pop()
    return lines


def _try_parse_mapping(text: str) -> dict[str, Any] | None:
    """Recover a dict from its JSON or Python-repr string; None if not a mapping."""
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


# Public alias so other services (engine finalize, repairs) can flatten any
# object/dict that leaked into script_lines as a final safety net.
def sanitize_narration_lines(value: object, cta: str = "") -> list[str]:
    return _narration_lines(value, cta)


def _build_script_result(
    payload: dict[str, Any],
    research_brief: dict[str, Any],
    narrative_plan: dict[str, Any],
    provider: str,
    model: str,
) -> dict[str, Any]:
    cta = str(payload.get("cta") or "").strip()
    return {
        "title": str(payload.get("title") or "").strip(),
        "hook": str(payload.get("hook") or "").strip(),
        "script_lines": _narration_lines(payload.get("script_lines") or payload.get("lines"), cta),
        "cta": cta,
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
        "provider": provider,
        "fallback_used": False,
        "grounding_used": bool(research_brief.get("grounding_used")),
        "grounding_available": bool(research_brief.get("grounding_available")),
        "grounding_warning": str(research_brief.get("grounding_warning") or ""),
        "last_llm_provider": provider,
        "last_llm_model": model,
        "last_llm_error": "",
        "script_call_count": 1,
        "llm_call_count": 1,
    }


def _build_judge_result(data: dict[str, Any], model: str) -> dict[str, Any]:
    def _score(key: str) -> float:
        try:
            return max(0.0, min(10.0, round(float(data.get(key)), 1)))
        except (TypeError, ValueError):
            return 0.0

    overall = _score("overall")
    verdict = str(data.get("verdict") or "").strip().lower()
    if verdict not in {"keep", "rewrite"}:
        verdict = "rewrite" if overall < config.GENERATION_JUDGE_REWRITE_THRESHOLD else "keep"
    tier = str(data.get("tier") or "").strip().lower()
    if tier not in {"excellent", "good", "average", "weak", "reject"}:
        tier = _tier_from_score(overall)
    return {
        "overall": overall,
        "hook_score": _score("hook_score"),
        "retention_score": _score("retention_score"),
        "specificity_score": _score("specificity_score"),
        "naturalness_score": _score("naturalness_score"),
        "tier": tier,
        "verdict": verdict,
        "strengths": _string_list(data.get("strengths")),
        "weaknesses": _string_list(data.get("weaknesses")),
        "critique": str(data.get("critique") or "").strip(),
        "suggested_hook": str(data.get("suggested_hook") or "").strip(),
        "model": model,
    }


def _build_visual_plan(data: list[Any]) -> list[dict[str, Any]]:
    max_queries = max(1, int(config.GENERATION_MAX_VISUAL_QUERIES_PER_ITEM))
    plan: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            plan.append({})
            continue
        queries = [_clean_query(q) for q in _string_list(item.get("queries")) if _clean_query(q)]
        media_type = str(item.get("type") or "broll").strip().lower()
        if media_type not in {"broll", "image"}:
            media_type = "broll"
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in {"specific", "generic"}:
            kind = "generic"
        plan.append(
            {
                "order": int(item.get("order") or index + 1),
                "scene": str(item.get("scene") or "").strip(),
                "subject": str(item.get("subject") or "").strip(),
                "kind": kind,
                "queries": list(dict.fromkeys(queries))[:max_queries],
                "type": media_type,
            }
        )
    return plan


def _build_ideas(payload: list[Any], provider: str) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    for index, item in enumerate(payload[:6], start=1):
        if not isinstance(item, dict):
            continue
        ideas.append(
            {
                **item,
                "idea_id": str(item.get("idea_id") or f"idea_{index}"),
                "engine_mode": "canal_dark",
                "provider": provider,
                "fallback_used": False,
                "suggested_hashtags": _string_list(item.get("suggested_hashtags")),
            }
        )
    return ideas


def _finalize_narrative_plan(
    payload: dict[str, Any], provider: str, model: str, script_depth: str, narrative_style: str
) -> dict[str, Any]:
    payload["script_depth"] = script_depth
    payload["narrative_style"] = narrative_style
    payload["narrative_plan_fallback_used"] = False
    payload["last_llm_provider"] = provider
    payload["last_llm_model"] = model
    payload["llm_call_count"] = int(payload.get("llm_call_count") or 0) + 1
    payload["story_beats"] = [item for item in payload.get("story_beats", []) if isinstance(item, dict)]
    return payload


_IDEAS_PROMPT = (
    "Gere 6 ideias de shorts faceless em JSON array. Campos: idea_id,title,niche,topic,"
    "angle,hook,why_it_might_work,target_emotion,curiosity_gap,risk_level,"
    "fact_check_needed,suggested_hashtags,visual_direction. Use ângulos específicos, "
    "fact-checkable e com potencial de curiosidade.\n"
    "Nicho: {niche}\nTema: {topic}\nIdioma: {language}\nTom: {tone}"
)


class OpenAIProvider:
    def __init__(self) -> None:
        if not config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY não configurada.")
        if importlib.util.find_spec("openai") is None:
            raise RuntimeError("Pacote openai não instalado.")
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(api_key=config.OPENAI_API_KEY)

    def generate_research_brief(self, niche: str, topic: str, language: str, tone: str) -> dict[str, Any]:
        prompt = _research_prompt(niche, topic, language, tone)
        grounding_available = config.GENERATION_OPENAI_USE_WEB_SEARCH
        grounding_used = False
        grounding_warning = ""
        text = ""
        if grounding_available:
            try:
                text = self._web_search(config.GENERATION_OPENAI_RESEARCH_MODEL, prompt)
                grounding_used = True
            except Exception as error:  # noqa: BLE001 - web search may be unsupported
                grounding_warning = f"web_search_unavailable: {error}"
        if not text:
            text = self._chat(config.GENERATION_OPENAI_RESEARCH_MODEL, prompt, json_object=True)
        payload = safe_json_parse(text)
        if not isinstance(payload, dict):
            raise ValueError("openai_research_not_object")
        return _normalize_research_payload(
            payload=payload,
            provider="openai",
            fallback_used=False,
            grounding_used=grounding_used,
            grounding_available=grounding_available,
            grounding_warning=grounding_warning,
            model=config.GENERATION_OPENAI_RESEARCH_MODEL,
        )

    def generate_narrative_plan(
        self, research_brief: dict[str, Any], duration_seconds: int, script_depth: str, narrative_style: str
    ) -> dict[str, Any]:
        prompt = _narrative_plan_prompt(research_brief, duration_seconds, script_depth, narrative_style)
        text = self._chat(config.GENERATION_OPENAI_CHEAP_MODEL, prompt, json_object=True)
        payload = safe_json_parse(text)
        if not isinstance(payload, dict):
            raise ValueError("openai_narrative_plan_not_object")
        return _finalize_narrative_plan(
            payload, "openai", config.GENERATION_OPENAI_CHEAP_MODEL, script_depth, narrative_style
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
        critique: str = "",
        scriptwriter: str = "",
    ) -> dict[str, Any]:
        prompt = _script_prompt(
            research_brief, narrative_plan, niche, topic, duration_seconds,
            tone, language, script_depth, narrative_style, critique=critique, scriptwriter=scriptwriter,
        )
        text = self._chat(config.GENERATION_OPENAI_SCRIPT_MODEL, prompt, json_object=True)
        payload = safe_json_parse(text)
        if not isinstance(payload, dict):
            raise ValueError("openai_script_not_object")
        return _build_script_result(
            payload, research_brief, narrative_plan, "openai", config.GENERATION_OPENAI_SCRIPT_MODEL
        )

    def judge_script(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = _judge_prompt(payload)
        text = self._chat(config.GENERATION_OPENAI_JUDGE_MODEL, prompt, json_object=True)
        data = safe_json_parse(text)
        if not isinstance(data, dict):
            raise ValueError("openai_judge_not_object")
        return _build_judge_result(data, config.GENERATION_OPENAI_JUDGE_MODEL)

    def generate_visual_queries(
        self, script_lines: list[str], contexts: list[str], niche: str, title: str, language: str, research_brief: dict[str, Any]
    ) -> list[dict[str, Any]]:
        prompt = _visual_queries_prompt(script_lines, contexts, niche, title, research_brief)
        # Arrays don't fit json_object mode; rely on lenient parsing instead.
        text = self._chat(config.GENERATION_OPENAI_CHEAP_MODEL, prompt, json_object=False)
        data = safe_json_parse(text)
        if not isinstance(data, list):
            raise ValueError("openai_visual_queries_not_list")
        return _build_visual_plan(data)

    def generate_ideas(self, niche: str, topic: str, language: str, tone: str) -> list[dict[str, Any]]:
        prompt = _IDEAS_PROMPT.format(niche=niche, topic=topic, language=language, tone=tone)
        text = self._chat(config.GENERATION_OPENAI_CHEAP_MODEL, prompt, json_object=False)
        payload = safe_json_parse(text)
        if not isinstance(payload, list):
            raise ValueError("openai_ideas_not_list")
        return _build_ideas(payload, "openai")

    def _chat(self, model: str, prompt: str, json_object: bool = False) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_object:
            kwargs["response_format"] = {"type": "json_object"}
        last_error: Exception | None = None
        for attempt in range(_MAX_TRANSIENT_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(**kwargs)
                return str(response.choices[0].message.content or "")
            except Exception as error:  # noqa: BLE001 - retry only transient overloads
                last_error = error
                if attempt >= _MAX_TRANSIENT_RETRIES or not _is_transient_error(error):
                    raise
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
        if last_error:
            raise last_error
        return ""

    def _web_search(self, model: str, prompt: str) -> str:
        response = self._client.responses.create(
            model=model,
            input=prompt,
            tools=[{"type": "web_search"}],
        )
        return str(getattr(response, "output_text", "") or "")

    def generate_image(self, prompt: str, size: str, quality: str) -> bytes | None:
        response = self._client.images.generate(
            model=config.GENERATION_OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
        data = getattr(response, "data", None) or []
        if not data:
            return None
        b64 = getattr(data[0], "b64_json", None)
        return base64.b64decode(b64) if b64 else None


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
        "engine_mode": "canal_dark" if provider in {"gemini", "openai"} else _engine_mode(),
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


_SCRIPT_LANG_NAMES = {
    "pt": "português (Brasil)",
    "en": "inglês (English)",
    "es": "espanhol (español)",
}


def _lang_name(language: str) -> str:
    return _SCRIPT_LANG_NAMES.get(
        str(language or "").strip().lower()[:2], str(language or "português")
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
    critique: str = "",
    scriptwriter: str = "",
) -> str:
    persona_block = (
        f"PERSONA DO ROTEIRISTA: {str(scriptwriter).strip()} Mantenha essa voz/estilo em todo o "
        "roteiro (sem perder a clareza e a linguagem simples).\n"
        if str(scriptwriter or "").strip()
        else ""
    )
    line_hint = "8 a 12 linhas" if duration_seconds <= 60 else "12 a 18 linhas" if duration_seconds <= 90 else "18 a 26 linhas"
    pacing_hint = (
        "direto, sem detalhes secundários"
        if duration_seconds <= 60
        else "com contexto, conflito, virada e consequência"
        if duration_seconds <= 90
        else "mais completo, com tensão, contexto e fechamento forte"
    )
    revision_block = ""
    if str(critique or "").strip():
        revision_block = (
            "\n\nESTA É UMA REVISÃO. Uma versão anterior do roteiro foi reprovada. "
            "Reescreva do zero corrigindo exatamente os problemas abaixo, mantendo os fatos do "
            "brief. Não repita os mesmos erros. Evite frases picotadas, listas de fatos soltas e "
            "linguagem genérica; escreva narração fluida com tensão e uma virada clara.\n"
            f"Crítica a corrigir: {str(critique).strip()}"
        )
    lang_name = _lang_name(language)
    return (
        f"IDIOMA OBRIGATÓRIO: escreva TODO o roteiro — title, hook, script_lines, cta e hashtags — "
        f"em {lang_name}. NÃO escreva em nenhum outro idioma. Esta regra vale acima de tudo.\n"
        f"{persona_block}"
        f"LINGUAGEM (regra principal): escreva para o grande público, em {lang_name} simples e "
        "popular, como se explicasse para um amigo na conversa. Frases curtas (no máximo ~14 "
        "palavras), uma ideia por frase. PROIBIDO jargão, termos acadêmicos ou rebuscados; se um "
        "termo for inevitável, explique em palavras do dia a dia. Evite palavras como 'helenística', "
        "'anexado', 'culminou', 'esfera', 'paradigma'. Use voz ativa, ritmo de short viral, e crie "
        "curiosidade/emoção para gerar engajamento. Texto fácil de entender em uma primeira escuta.\n"
        "CONTEÚDO (substância): linguagem simples NÃO é linguagem vazia. Use de 2 a 4 fatos "
        "concretos do research_brief (nomes, números, datas, lugares) e entregue UM insight claro: "
        "o detalhe surpreendente, o 'porquê importa' ou a virada que pouca gente sabe. O espectador "
        "tem que aprender algo real e específico, não ouvir generalidades ('foi importante', 'mudou "
        "tudo') sem dizer o quê. Cada frase avança a história; nada de enrolação.\n"
        "Você é roteirista de shorts faceless. Responda somente JSON válido com title,hook,"
        "script_lines,cta,hashtags,visual_context,fact_check_notes,estimated_duration_seconds,"
        "voice_style,pacing. script_lines deve conter apenas falas finais de narração, com frases "
        "curtas e naturais. Cada item de script_lines é uma STRING simples (uma frase falada), "
        "NUNCA um objeto/dicionário/JSON aninhado — não use chaves como factual/interpretation "
        "dentro das linhas. Cada linha deve ser uma frase completa e falável por si só (não comece "
        "uma linha no meio de uma ideia). Nada de metalinguagem, nada de 'o roteiro deve', nada de "
        "'use uma imagem' dentro de script_lines. Use fatos do research_brief e a estrutura do narrative_plan; "
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
        f"{revision_block}"
    )


def judge_script(
    payload: dict[str, Any],
    provider_override: str = "auto",
) -> dict[str, Any] | None:
    """Score a finished script with one LLM call. Returns None if unavailable."""
    if not config.GENERATION_ENABLE_LLM_JUDGE:
        return None
    name = _active_provider(provider_override)
    if name == "none":
        return None
    try:
        return _make_provider(name).judge_script(payload)
    except Exception:
        return None


def generate_visual_queries(
    script_lines: list[str],
    contexts: list[str],
    niche: str,
    title: str,
    language: str,
    research_brief: dict[str, Any],
    provider_override: str = "auto",
) -> list[dict[str, Any]] | None:
    """Map each script beat to generic English stock-search queries. None if unavailable."""
    if not config.GENERATION_ENABLE_LLM_VISUAL_QUERIES:
        return None
    name = _active_provider(provider_override)
    if name == "none":
        return None
    if not script_lines:
        return None
    try:
        return _make_provider(name).generate_visual_queries(
            script_lines=script_lines,
            contexts=contexts,
            niche=niche,
            title=title,
            language=language,
            research_brief=research_brief if isinstance(research_brief, dict) else {},
        )
    except Exception:
        return None


def generate_ai_image(
    prompt: str,
    size: str | None = None,
    quality: str | None = None,
    provider_override: str = "auto",
) -> bytes | None:
    """Generate an image (PNG bytes) for a scene. Tries Runware (Flux) FIRST because
    it's much cheaper; OpenAI is the last resort. None if disabled/unavailable/error."""
    if not config.GENERATION_ENABLE_AI_IMAGE_FALLBACK:
        return None
    prompt = str(prompt or "").strip()
    if not prompt:
        return None
    size = size or config.GENERATION_IMAGE_SIZE

    # 1) Runware (Flux) — principal (mais barato).
    img = generate_runware_image(prompt, size)
    if img:
        return img

    # 2) OpenAI — último recurso.
    if _openai_ready():
        try:
            return OpenAIProvider().generate_image(
                prompt=prompt[:900],
                size=size,
                quality=quality or config.GENERATION_IMAGE_QUALITY,
            )
        except Exception:  # noqa: BLE001
            return None
    return None


def _parse_size(size: str) -> tuple[int, int]:
    try:
        w, h = str(size or "").lower().split("x", 1)
        return int(w), int(h)
    except (ValueError, AttributeError):
        return 1024, 1536


def generate_runware_image(prompt: str, size: str | None = None) -> bytes | None:
    """Generate one image via the Runware API (Flux). Returns PNG bytes or None
    (disabled / no key / error). Never raises."""
    if not config.GENERATION_RUNWARE_ENABLED or not config.RUNWARE_API_KEY:
        return None
    prompt = str(prompt or "").strip()
    if not prompt:
        return None
    try:
        import uuid

        import requests

        width, height = _parse_size(size or config.GENERATION_IMAGE_SIZE)
        payload = [
            {
                "taskType": "imageInference",
                "taskUUID": str(uuid.uuid4()),
                "positivePrompt": prompt[:1500],
                "width": width,
                "height": height,
                "model": config.GENERATION_RUNWARE_MODEL,
                "numberResults": 1,
                "outputType": "base64Data",
                "outputFormat": "PNG",
            }
        ]
        response = requests.post(
            "https://api.runware.ai/v1",
            json=payload,
            headers={
                "Authorization": f"Bearer {config.RUNWARE_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data") if isinstance(data, dict) else None
        for item in items or []:
            b64 = item.get("imageBase64Data") if isinstance(item, dict) else None
            if b64:
                return base64.b64decode(b64)
    except Exception:  # noqa: BLE001 - best-effort; falls back to OpenAI
        return None
    return None


def _visual_queries_prompt(
    script_lines: list[str],
    contexts: list[str],
    niche: str,
    title: str,
    research_brief: dict[str, Any],
) -> str:
    facts = _string_list(research_brief.get("key_facts"))
    central = str(research_brief.get("subject") or title or "").strip()
    entities = _string_list(research_brief.get("key_entities"))
    numbered = []
    for index, line in enumerate(script_lines):
        ctx = contexts[index] if index < len(contexts) else ""
        suffix = f"  (contexto: {ctx})" if ctx else ""
        numbered.append(f"{index + 1}. {line}{suffix}")
    lines_block = "\n".join(numbered)
    return (
        "Você é um diretor de arte de vídeos verticais (9:16). Para cada linha de narração "
        "abaixo, escolha a melhor imagem/vídeo de banco de imagens (estilo Pexels) que represente "
        "VISUALMENTE aquele momento da história.\n"
        "ÂNCORA NO TEMA (regra mais importante): TODAS as cenas têm que se relacionar visualmente "
        f"com o TEMA CENTRAL e as ENTIDADES abaixo. Mantenha o assunto principal presente em cada "
        "cena (a pessoa, povo, lugar, época ou objeto do tema). É PROIBIDO desviar para assuntos "
        "não relacionados (animais, pássaros, natureza/paisagem genérica, objetos aleatórios) só "
        "porque combinam com a 'época' ou um clima — a menos que a narração fale explicitamente "
        "disso. Ex (tema Gêngis Khan): use 'Mongol warrior on horseback', 'Mongol empire map', "
        "'Genghis Khan portrait', 'steppe cavalry' — NUNCA uma pintura antiga de pássaros. Toda "
        "query/subject deve carregar o assunto central (povo/lugar/figura), não só a época.\n"
        "REGRA CRÍTICA: bancos de imagens NÃO têm pessoas específicas, times, jogadores, marcas, "
        "logos nem eventos nomeados. Traduza o sentido para uma cena GENÉRICA, visualmente rica e "
        "filmável (cenário, ação, objeto, clima/emoção). Ex: 'gol de Vini Jr contra Marrocos' -> "
        "'soccer player celebrating goal in packed stadium'. Nunca coloque nomes próprios, times "
        "ou marcas nas queries.\n"
        "ASSUNTO REAL NOMEADO (prioridade máxima): se a cena é sobre algo REAL e específico — uma "
        "pessoa (Pelé, Messi), uma seleção/time/clube (Seleção Brasileira, Marrocos, Santos FC), ou "
        "um evento nomeado (Copa do Mundo 2026) — use kind='specific' e subject = o NOME REAL em "
        "inglês (ex: 'Brazil national football team', 'Morocco national football team', 'Lionel "
        "Messi', 'Pelé', 'FIFA World Cup 2026'). A busca real (Wikimedia/enciclopédia) tem FOTOS "
        "LIVRES de times, jogadores e eventos. PRIORIZE o time/seleção/pessoa que está SENDO FALADO "
        "na cena — NÃO use figuras secundárias (árbitros, comentaristas) como assunto visual. Numa "
        "análise de jogo, mostre as seleções envolvidas.\n"
        "REGRA DE IDENTIDADE (só para cenas genéricas, sem assunto real nomeado): aí o clipe pode "
        "ser de qualquer país, então EVITE revelar nacionalidade errada — use planos neutros: "
        "torcida e arquibancada, estádio/gramado, bola e chuteira em close, silhueta de jogador, "
        "comemoração de costas, placar, mãos/pés, luzes do estádio.\n"
        "ÉPOCA (regra forte para temas históricos): se o tema se passa numa época do passado "
        "(antiguidade, Roma/Egito/Grécia, idade média, etc.) ou trata de figura/evento histórico, "
        "TODAS as cenas devem ser fiéis àquela época. É PROIBIDO usar imagens modernas — nada de "
        "bandas, palco moderno, saxofone, festa atual, roupas/cidades/tecnologia modernas. Ex: 'Nero "
        "tocando música' NÃO é 'musician on stage' (vira banda moderna); é 'ancient Roman lyre player "
        "fresco' / 'Roman mosaic musician'. Para CADA cena de tema histórico, dê um subject real da "
        "época e use kind='specific'. O subject de cena histórica deve ser um ARTEFATO ou "
        "representação real que exista em museu/enciclopédia: relevo, estátua, busto, afresco, "
        "mosaico, pintura, papiro, ruína, moeda, manuscrito (ex: 'ancient Egyptian relief of a "
        "queen', 'Roman fresco of a banquet', 'ancient papyrus scroll', 'marble bust of Nero'). "
        "Inclua pelo menos uma query também nesse formato de artefato. Mesmo nas queries genéricas, "
        "use marcadores de época ('ancient roman', 'classical fresco', 'marble statue', 'medieval'), "
        "nunca termos modernos.\n"
        "ASSUNTO REAL (subject): quando a cena se refere a uma pessoa, lugar, evento, obra ou objeto "
        "REAL e específico (ex: imperadores romanos, Egito antigo, a Roma de Nero, um quadro/busto, "
        "um monumento), preencha 'subject' com esse assunto em inglês, PERMITINDO nomes próprios e a "
        "época (ex: 'Roman emperor Nero bust', 'Ancient Rome forum', 'Great Fire of Rome painting'). "
        "Isso é usado numa busca enciclopédica (Wikimedia) que TEM essas imagens reais. Defina "
        "kind='specific' nesse caso. Se a cena for só clima/ação genérica (sem pessoa/lugar real "
        "definido), deixe subject vazio e kind='generic'. As 'queries' continuam SEMPRE genéricas "
        "(sem nomes próprios) para o banco de stock.\n"
        "FIDELIDADE À LINHA (regra forte): cada 'scene' deve ilustrar o CONTEÚDO ESPECÍFICO "
        "daquela linha de narração — a ação, o objeto, a pessoa ou o momento EXATO que a frase "
        "descreve — e não uma cena genérica do tema. Se a linha fala de uma batalha, mostre a "
        "batalha; se fala de uma carta, mostre a carta; se fala de uma fuga, mostre a fuga. Cada "
        "linha vira uma cena DIFERENTE e concreta. Descreva sujeito + ação + cenário + época.\n"
        "Responda SOMENTE com um JSON array, um objeto por linha, NA MESMA ORDEM, com as chaves: "
        "order (int, 1-based), scene (descrição em inglês de 8 a 18 palavras, CONCRETA e específica "
        "do que ESSA linha narra: sujeito + ação + cenário + época), subject (assunto real "
        "em inglês ou vazio), kind ('specific' ou 'generic'), queries (lista de 2 a 3 buscas curtas "
        "em inglês, genéricas, sem nomes próprios), type ('broll' para vídeo ou 'image' para foto). "
        "Para temas históricos/biográficos, prefira kind='specific' com um subject forte.\n"
        f"TEMA CENTRAL: {central}\n"
        f"Entidades principais (mantenha presentes nas cenas): {json.dumps(entities, ensure_ascii=False)}\n"
        f"Nicho: {niche}\nTítulo: {title}\n"
        f"Fatos (apenas para contexto, não cite nomes nas queries): {json.dumps(facts, ensure_ascii=False)}\n"
        f"Linhas de narração:\n{lines_block}"
    )


def _judge_prompt(payload: dict[str, Any]) -> str:
    brief = payload.get("research_brief") if isinstance(payload.get("research_brief"), dict) else {}
    facts = _string_list(brief.get("key_facts"))
    script = {
        "hook": str(payload.get("hook") or ""),
        "script_lines": _string_list(payload.get("script_lines")),
        "cta": str(payload.get("cta") or ""),
    }
    duration = int(payload.get("requested_duration_seconds") or payload.get("estimated_duration_seconds") or 60)
    return (
        "Você é um editor sênior de shorts/reels virais (futebol, história, crimes). Avalie o "
        "roteiro abaixo de forma JUSTA e calibrada (não avarento). CALIBRAÇÃO da nota overall: "
        "9-10 = excepcional/viral; 8 = bom e pronto para publicar; 7 = aceitável com 1-2 ressalvas; "
        "5-6 = fraco; abaixo de 5 = ruim. Um roteiro com linguagem simples, fatos concretos, bom "
        "hook e que prende MERECE 8 — não ancore tudo em 7. Reserve notas baixas para roteiros "
        "realmente fracos. Responda SOMENTE com JSON válido, sem texto fora do JSON, com as chaves: "
        "overall (0-10), hook_score (0-10), retention_score (0-10), specificity_score (0-10), "
        "naturalness_score (0-10), tier (excellent|good|average|weak|reject), verdict (keep|rewrite), "
        "strengths (lista curta), weaknesses (lista curta), critique (parágrafo acionável em "
        "português com instruções concretas de reescrita), suggested_hook (string, opcional).\n"
        "Critérios: a LINGUAGEM é simples e popular, fácil para o grande público entender numa "
        "primeira escuta (penalize FORTE jargão, termos acadêmicos/rebuscados e frases longas)? O "
        "hook prende nos primeiros 3 segundos e cria curiosidade real? A narração é fluida e natural "
        "em pt-BR falado (penalize frases picotadas e listas de fatos soltas)? Tem tensão e uma "
        "virada/insight, não só cronologia? Gera engajamento? Os fatos são coerentes com o brief "
        "(sem inventar)? O tamanho combina com a duração alvo? "
        "Use verdict=rewrite sempre que overall < 7.5 OU a linguagem for difícil/acadêmica. Na "
        "critique, diga O QUE simplificar e dê exemplos de como reescrever em linguagem simples.\n"
        f"Duração alvo: {duration}s\n"
        f"Fatos do brief (verdade base): {json.dumps(facts, ensure_ascii=False)}\n"
        f"Roteiro: {json.dumps(script, ensure_ascii=False)}"
    )


def _summary_from_brief(brief: dict[str, Any]) -> str:
    facts = _string_list(brief.get("key_facts"))
    if facts:
        return " ".join(facts[:2])
    return str(brief.get("subject") or "")


def _gemini_ready() -> bool:
    return bool(config.GEMINI_API_KEY) and importlib.util.find_spec("google.genai") is not None


def _openai_ready() -> bool:
    return bool(config.OPENAI_API_KEY) and importlib.util.find_spec("openai") is not None


def _can_use_gemini(provider: str | None = None) -> bool:
    active_provider = provider or _provider()
    return active_provider == "gemini" and _gemini_ready()


def _provider_ready(name: str) -> bool:
    if name == "openai":
        return _openai_ready()
    if name == "gemini":
        return _gemini_ready()
    return False


def _active_provider(provider_override: str = "auto") -> str:
    """Resolved provider that is actually usable right now ('openai'/'gemini'/'none')."""
    name = _provider(provider_override)
    return name if _provider_ready(name) else "none"


def _make_provider(name: str) -> Any:
    if name == "openai":
        return OpenAIProvider()
    if name == "gemini":
        return GeminiProvider()
    raise RuntimeError(f"unknown_provider:{name}")


def _provider(provider_override: str = "auto") -> str:
    if provider_override in {"gemini", "openai"}:
        return provider_override
    if provider_override == "local" or provider_override == "none":
        return "none"
    configured = config.GENERATION_AI_PROVIDER
    return configured if configured in {"none", "gemini", "openai"} else "none"


def _engine_mode() -> str:
    return config.GENERATION_ENGINE if config.GENERATION_ENGINE in {"local", "canal_dark"} else "local"


def _confidence(value: object) -> str:
    text = str(value or "low").strip().lower()
    return text if text in {"high", "medium", "low"} else "low"


def _tier_from_score(score: float) -> str:
    if score >= 8.0:
        return "excellent"
    if score >= 6.5:
        return "good"
    if score >= 5.0:
        return "average"
    if score >= 3.5:
        return "weak"
    return "reject"


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _clean_query(value: object) -> str:
    text = re.sub(r"[\"'`]+", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return " ".join(text.split()[:5])
