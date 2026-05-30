from __future__ import annotations

import json
from typing import Any

from app import config


class ReferenceClipBenchmarkService:
    FILE_NAME = "reference_good_clips.json"
    CHECKLIST = [
        "strong_hook",
        "clear_context",
        "complete_thought",
        "story_or_argument_progression",
        "clear_ending",
        "no_merchandising",
        "no_superchat",
        "no_filler",
        "works_standalone",
        "emotional_or_curiosity_trigger",
    ]
    LEGACY_FEATURES = [
        "good_pacing",
        "viral_potential",
    ]

    def __init__(self) -> None:
        self.path = config.STORAGE_REFERENCE_DIR / self.FILE_NAME

    def list_references(self) -> list[dict[str, Any]]:
        references = self._read()
        return [self._normalize(reference) for reference in references]

    def expected_checklist(self) -> list[str]:
        return list(self.CHECKLIST)

    def update_reference(
        self,
        url: str,
        features: dict[str, bool | int | None],
        notes: str | None = None,
    ) -> dict[str, Any]:
        references = self._read()
        for index, reference in enumerate(references):
            if reference.get("url") != url:
                continue
            normalized = self._normalize(reference)
            normalized_features = normalized["features"]
            for key, value in features.items():
                if value is not None:
                    normalized_features[key] = value
            if notes is not None:
                normalized["notes"] = notes
            references[index] = normalized
            self._write(references)
            return normalized
        raise ValueError(f"Referência não encontrada: {url}")

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("reference_good_clips.json deve conter uma lista")
        return data

    def _write(self, references: list[dict[str, Any]]) -> None:
        config.STORAGE_REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(references, file, ensure_ascii=False, indent=2)

    def _normalize(self, reference: dict[str, Any]) -> dict[str, Any]:
        required = {
            "url": str(reference.get("url", "")),
            "label": str(reference.get("label", "good")),
            "source": str(reference.get("source", "user_reference")),
            "style": str(reference.get("style", "podcast_cut")),
            "notes": str(reference.get("notes", "")),
            "features": dict(reference.get("features") or {}),
        }
        if not required["url"]:
            raise ValueError("Referência sem URL")
        for key in self.CHECKLIST + self.LEGACY_FEATURES:
            required["features"].setdefault(key, None)
        return required
