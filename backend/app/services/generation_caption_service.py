"""Caption block builder for the render pipeline (0.5.53, Part 1).

Turns per-word timings (real edge-tts WordBoundary, or an approximate fallback)
into short on-screen caption blocks (3-6 words) that break on natural pauses,
validates the timeline, and persists debug artifacts (captions.json,
render_timing_report.json). The ASS subtitles are built from these blocks so the
text follows the speech instead of fixed per-segment slots.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app import config


AUDIO_DIR = config.STORAGE_GENERATION_DIR / "audio"
MIN_WORDS = max(1, config.GENERATION_CAPTION_MIN_WORDS)
MAX_WORDS = max(MIN_WORDS, config.GENERATION_CAPTION_MAX_WORDS)
OVERLAP_TOLERANCE = 0.12
END_TOLERANCE = 0.6

_SENTENCE_END = re.compile(r"[.!?…]+[\"')\]]?$")
_SOFT_BREAK = re.compile(r"[,;:—–]$")


def captions_path(project_id: str) -> Path:
    return AUDIO_DIR / f"{_safe(project_id)}.captions.json"


def load_words(words_path: str | Path) -> list[dict[str, Any]]:
    path = Path(words_path)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    words = payload.get("words") if isinstance(payload, dict) else payload
    return [w for w in words if isinstance(w, dict) and w.get("start") is not None] if isinstance(words, list) else []


def build_caption_blocks(
    words: list[dict[str, Any]],
    audio_duration: float | None = None,
    min_words: int = MIN_WORDS,
    max_words: int = MAX_WORDS,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    group: list[dict[str, Any]] = []

    def flush() -> None:
        if not group:
            return
        text = _clean_text(" ".join(str(w.get("text") or "") for w in group))
        if text:
            word_meta = [
                {
                    "text": str(w.get("text") or "").strip(),
                    "start": round(float(w["start"]), 3),
                    "end": round(float(w["end"]), 3),
                }
                for w in group
                if w.get("start") is not None and w.get("end") is not None and str(w.get("text") or "").strip()
            ]
            blocks.append(
                {
                    "start": round(float(group[0]["start"]), 3),
                    "end": round(float(group[-1]["end"]), 3),
                    "text": text,
                    "words": word_meta,
                }
            )
        group.clear()

    pause_gap = max(0.0, float(config.GENERATION_CAPTION_PAUSE_GAP))
    prev_end = 0.0
    for word in words:
        start = float(word.get("start") or prev_end)
        # A real pause in the speech is a natural place to break the caption,
        # so phrases stay whole instead of being cut by raw word count.
        if group and prev_end and (start - prev_end) >= pause_gap and len(group) >= min_words:
            flush()
        group.append(word)
        token = str(word.get("text") or "").strip()
        count = len(group)
        sentence_end = bool(_SENTENCE_END.search(token))
        soft_break = bool(_SOFT_BREAK.search(token))
        if count >= max_words or sentence_end or (soft_break and count >= min_words):
            flush()
        prev_end = float(word.get("end") or start)
    flush()
    return validate_and_fix(blocks, audio_duration)


def validate_and_fix(
    captions: list[dict[str, Any]], audio_duration: float | None
) -> list[dict[str, Any]]:
    fixed: list[dict[str, Any]] = []
    previous_end = 0.0
    for cue in captions:
        start = max(0.0, float(cue.get("start") or 0.0))
        end = float(cue.get("end") or 0.0)
        # Resolve large overlaps by nudging the start forward.
        if start < previous_end - OVERLAP_TOLERANCE:
            start = max(start, previous_end)
        if end <= start:
            end = start + 0.4
        if audio_duration:
            limit = float(audio_duration) + END_TOLERANCE
            start = min(start, limit)
            end = min(end, limit)
            if end <= start:
                end = min(start + 0.3, limit)
        text = _clean_text(str(cue.get("text") or ""))
        if not text:
            continue
        entry = {"start": round(start, 3), "end": round(end, 3), "text": text}
        if isinstance(cue.get("words"), list) and cue["words"]:
            entry["words"] = cue["words"]
        fixed.append(entry)
        previous_end = end
    return fixed


def write_captions(project_id: str, captions: list[dict[str, Any]]) -> Path | None:
    if not captions:
        return None
    path = captions_path(project_id)
    try:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump({"captions": captions}, file, ensure_ascii=False)
        return path
    except OSError:
        return None


def ensure_captions(project: dict[str, Any]) -> dict[str, Any]:
    """Build captions from the project's words.json and persist captions.json.
    Returns ``{captions, captions_path, caption_count, last_end}`` (no project save)."""
    words_path = str(project.get("voice_words_path") or "")
    words = load_words(words_path) if words_path else []
    if not words:
        return {"captions": [], "captions_path": "", "caption_count": 0, "last_end": 0.0}
    duration = _safe_float(project.get("voice_duration_seconds"))
    captions = build_caption_blocks(words, duration)
    path = write_captions(str(project.get("project_id") or ""), captions)
    last_end = captions[-1]["end"] if captions else 0.0
    return {
        "captions": captions,
        "captions_path": str(path) if path else "",
        "caption_count": len(captions),
        "last_end": last_end,
    }


def write_timing_report(
    report_path: Path,
    audio_duration: float,
    word_count: int,
    captions: list[dict[str, Any]],
    source: str,
) -> None:
    if not config.GENERATION_RENDER_DEBUG:
        return
    last_end = captions[-1]["end"] if captions else 0.0
    payload = {
        "audio_duration_seconds": round(float(audio_duration), 3),
        "word_count": word_count,
        "caption_count": len(captions),
        "caption_source": source,
        "last_caption_end": round(last_end, 3),
        "caption_audio_delta": round(float(audio_duration) - last_end, 3),
        "issues": _timing_issues(captions, audio_duration),
    }
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _timing_issues(captions: list[dict[str, Any]], audio_duration: float) -> list[str]:
    issues: list[str] = []
    previous_end = 0.0
    for cue in captions:
        if cue["start"] < 0:
            issues.append("negative_start")
        if cue["end"] <= cue["start"]:
            issues.append("non_positive_duration")
        if cue["start"] < previous_end - OVERLAP_TOLERANCE:
            issues.append("overlap")
        previous_end = cue["end"]
    if captions and audio_duration and captions[-1]["end"] > float(audio_duration) + END_TOLERANCE:
        issues.append("caption_past_audio")
    return sorted(set(issues))


def _clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe(project_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(project_id)).strip("._-") or "project"
