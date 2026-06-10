# Canal Dark Engine Mapping

ClipRadar/DarkFlow 0.5.47 inspected `viniciuszenatti/canal-dark` as a reference for a future faceless-short generation engine. This document records what was adapted now and what remains out of scope.

## Reference Patterns Adapted

- Trend scout criteria: ideas should be specific, searchable, underserved, hookable, globally understandable, and fact-checkable.
- Roteirista structure: hook first, one clear angle, compact context, surprising insight, takeaway, and CTA.
- Visual planning: generation returns `visual_context` / `visual_direction` so later stages can choose b-roll safely.
- Fact-check awareness: scripts and ideas can mark `fact_check_needed` and `fact_check_notes`.
- Guardrail shape: a lightweight local guardrail evaluates facts, AI disclosure, visual/copyright risk, and platform notes.
- Engine fallback: `canal_dark` mode can call Gemini only when configured, otherwise it falls back to local templates.

## Implemented In ClipRadar 0.5.47

- `generation_engine_service.py` with `local` and `canal_dark` modes.
- Optional Gemini provider through `GENERATION_AI_PROVIDER=gemini` and `GEMINI_API_KEY`.
- `/generation/engine/status` endpoint.
- Enriched `/generation/ideas` and `/generation/scripts` payloads.
- Script quality scoring with tier, positive signals, negative signals, and reject reason.
- Optional project guardrail endpoint at `POST /generation/projects/{project_id}/guardrail`.
- Backward-compatible generation project fields for old saved projects.

## Not Integrated Now

- n8n workflow automation.
- Postiz publishing.
- Telegram checkpoints.
- Google Sheets tracking.
- Pexels/Pollinations image providers.
- FFmpeg rendering for generated shorts.
- Subtitle generation for generated shorts.
- Automatic posting or scheduling.

## Future Candidates

- Human checkpoint workflow inspired by Telegram approvals, but inside the existing app.
- Real b-roll provider abstraction with license metadata.
- Render stage from script + voice + visual plan.
- Stronger Gemini guardrail that can block high-risk projects before render.
- Structured AI disclosure metadata for generated videos.

## Risks To Manage

- Gemini availability, quota, latency, and key configuration.
- Stock/b-roll licensing and accidental use of identifiable people or brands.
- Fact-checking burden for news, health, politics, crime, finance, and claims about people.
- Platform risk around low-effort faceless AI content; mitigation requires original scripts, clear persona, human review, and disclosure where appropriate.
