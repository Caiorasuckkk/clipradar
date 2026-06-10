from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.approved_generation_service import (
    generation_status,
    trigger_approved_generation,
)
from app.services.generation_workspace_service import (
    create_project,
    delete_project,
    generate_ideas,
    generate_script,
    get_project,
    list_projects,
    update_project,
)
from app.services.generation_voice_service import (
    VoiceGenerationError,
    delete_voice_file,
    generate_voice_for_project,
    get_voice_file,
    list_voices,
)


router = APIRouter(prefix="/generation", tags=["generation"])


class TriggerApprovedGenerationPayload(BaseModel):
    candidate_id: str | None = None
    run_async: bool = True
    retry_failed: bool = False


class GenerationIdeaPayload(BaseModel):
    niche: str
    topic: str = ""
    language: str = "pt-BR"
    tone: str = "curioso"


class GenerationScriptPayload(BaseModel):
    idea: str
    niche: str = ""
    duration_seconds: int = 45
    tone: str = "curioso"
    language: str = "pt-BR"


class GenerationProjectPayload(BaseModel):
    title: str = ""
    niche: str = ""
    language: str = "pt-BR"
    tone: str = "curioso"
    status: str = "idea"
    idea: str = ""
    hook: str = ""
    script_lines: list[str] = Field(default_factory=list)
    cta: str = ""
    hashtags: list[str] = Field(default_factory=list)
    visual_context: list[str] = Field(default_factory=list)
    voice_status: str = "none"
    voice_name: str = ""
    voice_provider: str = ""
    voice_rate: str = ""
    voice_pitch: str = ""
    voice_audio_path: str = ""
    voice_audio_url: str = ""
    voice_duration_seconds: float | None = None
    voice_generated_at: str = ""
    voice_error: str = ""


class GenerationVoicePayload(BaseModel):
    voice: str = "pt-BR-AntonioNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"


@router.post("/approved/trigger")
def trigger_generation(payload: TriggerApprovedGenerationPayload) -> dict[str, Any]:
    return trigger_approved_generation(
        candidate_id=payload.candidate_id,
        run_async=payload.run_async,
        force_failed=payload.retry_failed,
    )


@router.get("/approved/status")
def get_generation_status() -> dict[str, Any]:
    return generation_status()


@router.post("/ideas")
def post_generation_ideas(payload: GenerationIdeaPayload) -> dict[str, Any]:
    return {
        "ideas": generate_ideas(
            niche=payload.niche,
            topic=payload.topic,
            language=payload.language,
            tone=payload.tone,
        )
    }


@router.post("/scripts")
def post_generation_script(payload: GenerationScriptPayload) -> dict[str, Any]:
    return generate_script(
        idea=payload.idea,
        niche=payload.niche,
        duration_seconds=payload.duration_seconds,
        tone=payload.tone,
        language=payload.language,
    )


@router.get("/projects")
def get_generation_projects() -> dict[str, Any]:
    return {"projects": list_projects()}


@router.post("/projects")
def post_generation_project(payload: GenerationProjectPayload) -> dict[str, Any]:
    return create_project(payload.dict())


@router.get("/projects/{project_id}")
def get_generation_project(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.put("/projects/{project_id}")
def put_generation_project(project_id: str, payload: GenerationProjectPayload) -> dict[str, Any]:
    project = update_project(project_id, payload.dict())
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.delete("/projects/{project_id}")
def delete_generation_project(project_id: str) -> dict[str, Any]:
    deleted = delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return {"deleted": True, "project_id": project_id}


@router.get("/voices")
def get_generation_voices() -> dict[str, Any]:
    return list_voices()


@router.post("/projects/{project_id}/voice")
def post_generation_project_voice(project_id: str, payload: GenerationVoicePayload) -> dict[str, Any]:
    try:
        return generate_voice_for_project(
            project_id=project_id,
            voice=payload.voice,
            rate=payload.rate,
            pitch=payload.pitch,
        )
    except VoiceGenerationError as error:
        status_code = 404 if "não encontrado" in error.message.lower() else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": error.message,
                "project": error.project,
            },
        ) from error


@router.get("/projects/{project_id}/voice/audio")
def get_generation_project_voice_audio(project_id: str) -> FileResponse:
    try:
        path = get_voice_file(project_id)
    except VoiceGenerationError as error:
        status_code = 404 if "não encontrado" in error.message.lower() or "áudio" in error.message.lower() else 400
        raise HTTPException(status_code=status_code, detail=error.message) from error
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


@router.delete("/projects/{project_id}/voice")
def delete_generation_project_voice(project_id: str) -> dict[str, Any]:
    try:
        return delete_voice_file(project_id)
    except VoiceGenerationError as error:
        status_code = 404 if "não encontrado" in error.message.lower() else 400
        raise HTTPException(status_code=status_code, detail=error.message) from error
