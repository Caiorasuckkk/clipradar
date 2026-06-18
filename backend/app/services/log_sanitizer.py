"""Mask secrets before they are persisted to disk (job logs, job errors).

Captured stderr/stdout or exception messages from SDKs can echo request
details that include API keys. Any text written to durable storage
(job_runs/*.txt, the jobs table error/result columns) should pass through
``sanitize`` first.
"""

from __future__ import annotations

import re

from app import config


_PLACEHOLDER = "***REDACTED***"

# Generic key-ish token patterns as a backstop for keys not in the env yet.
_GENERIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),          # Google API keys
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),            # OpenAI-style keys
    re.compile(r"(?i)(api[_-]?key\"?\s*[:=]\s*\"?)[A-Za-z0-9\-_]{16,}"),
)


def _known_secrets() -> list[str]:
    secrets: list[str] = []
    secrets.extend(config.YOUTUBE_API_KEYS_LIST)
    for value in (
        config.GEMINI_API_KEY,
        config.OPENAI_API_KEY,
        config.PEXELS_API_KEY,
        config.REDDIT_CLIENT_SECRET,
        config.REDDIT_CLIENT_ID,
    ):
        if value:
            secrets.append(value)
    # Longest first so substrings of a key don't get half-masked.
    return sorted({s for s in secrets if s and len(s) >= 6}, key=len, reverse=True)


def sanitize(text: str | None) -> str:
    if not text:
        return ""
    cleaned = str(text)
    for secret in _known_secrets():
        if secret in cleaned:
            cleaned = cleaned.replace(secret, _PLACEHOLDER)
    for pattern in _GENERIC_PATTERNS:
        cleaned = pattern.sub(
            lambda match: (match.group(1) + _PLACEHOLDER) if match.groups() else _PLACEHOLDER,
            cleaned,
        )
    return cleaned
