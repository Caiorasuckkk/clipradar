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
from app.services.generation_creation_service import (
    create_project_from_idea,
    create_project_from_opportunity,
    create_project_from_script,
    create_projects_from_opportunities_batch,
)
from app.services.generation_opportunity_service import search_opportunities
from app.services.generation_engine_service import engine_status
from app.services.generation_llm_provider_service import generate_research_brief
from app.services.generation_guardrail_service import analyze_generation_project
from app.services.generation_voice_service import (
    VoiceGenerationError,
    delete_voice_file,
    generate_voice_for_project,
    get_voice_file,
    list_voices,
)
from app.services.generation_stock_media_service import search_stock_media
from app.services.generation_visual_service import (
    add_visual_item,
    mark_visual_item_selected,
    mark_visuals_ready,
    reject_visual_item,
    remove_visual_item,
    suggest_visuals_for_project,
    update_visual_items,
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
    idea: str = ""
    niche: str = ""
    topic: str = ""
    duration_seconds: int = 45
    duration_preset: str = ""
    tone: str = "curioso"
    language: str = "pt-BR"
    force_research: bool = False
    provider: str = "auto"
    script_depth: str = "normal"
    narrative_style: str = ""
    content_format: str = "manual_topic"
    extra_context: str = ""
    opportunity_data: dict[str, Any] = Field(default_factory=dict)


class GenerationFactualBriefPayload(BaseModel):
    niche: str = ""
    topic: str = ""
    idea: str = ""
    language: str = "pt-BR"
    tone: str = "curioso"
    force_research: bool = False
    provider: str = "auto"


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
    factual_brief: dict[str, Any] = Field(default_factory=dict)
    research_brief: dict[str, Any] = Field(default_factory=dict)
    research_cache_hit: bool = False
    source_urls: list[str] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)
    grounding_used: bool = False
    grounding_available: bool = False
    search_queries: list[str] = Field(default_factory=list)
    factual_grounding_used: bool = False
    factual_grounding_confidence: str = "low"
    specificity_score: float | None = None
    script_depth: str = "normal"
    script_depth_label: str = "Normal"
    narrative_style: str = "dramatic"
    narrative_style_label: str = "Dramático"
    narrative_plan: dict[str, Any] = Field(default_factory=dict)
    story_beats: list[dict[str, Any]] = Field(default_factory=list)
    claim_evidence_pairs: list[dict[str, Any]] = Field(default_factory=list)
    depth_score: float | None = None
    narrative_score: float | None = None
    retention_score: float | None = None
    shallow_script_detected: bool = False
    narrative_repair_applied: bool = False
    narrative_repair_reason: str = ""
    requested_duration_seconds: float | None = None
    duration_preset_label: str = ""
    script_word_count: int = 0
    narration_word_count: int = 0
    narration_text_preview: str = ""
    force_research_used: bool = False
    llm_call_count: int = 0
    research_call_count: int = 0
    script_call_count: int = 0
    last_llm_error: str = ""
    last_llm_provider: str = ""
    last_llm_model: str = ""
    engine_mode: str = "local"
    provider: str = "none"
    fallback_used: bool = False
    fact_check_notes: list[str] = Field(default_factory=list)
    estimated_duration_seconds: float | None = None
    voice_style: str = ""
    pacing: str = ""
    script_quality_score: float | None = None
    script_quality_tier: str = ""
    script_positive_signals: list[str] = Field(default_factory=list)
    script_negative_signals: list[str] = Field(default_factory=list)
    script_reject_reason: str = ""
    script_repair_applied: bool = False
    script_repair_reason: str = ""
    guardrail_status: str = ""
    guardrail_risks: list[str] = Field(default_factory=list)
    disclosure_recommended: bool = False
    fact_check_required: bool = False
    copyright_review_required: bool = False
    platform_notes: list[str] = Field(default_factory=list)
    visual_status: str = "none"
    visual_items: list[dict[str, Any]] = Field(default_factory=list)
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
    voice_outdated: bool = False
    creation_mode: str = "legacy"
    creation_mode_label: str = "Legado"
    input_topic: str = ""
    input_idea: str = ""
    input_script: str = ""
    input_niche: str = ""
    input_language: str = "pt-BR"
    input_tone: str = "curioso"
    input_created_at: str = ""
    opportunity_data: dict[str, Any] = Field(default_factory=dict)
    script_import_status: str = "none"
    creation_warnings: list[str] = Field(default_factory=list)
    content_format: str = "manual_topic"
    content_format_label: str = "Tema manual"
    concrete_promise: str = ""
    viewer_reason_to_watch: str = ""
    watchability_score: float | None = None
    needs_more_context: bool = False
    missing_context_fields: list[str] = Field(default_factory=list)
    opportunity_script_repair_applied: bool = False
    opportunity_script_repair_reason: str = ""
    extra_context: str = ""
    watchability_positive_signals: list[str] = Field(default_factory=list)
    watchability_negative_signals: list[str] = Field(default_factory=list)


class GenerationProjectFromIdeaPayload(BaseModel):
    idea: str
    niche: str = ""
    language: str = "pt-BR"
    tone: str = "curioso"
    duration_seconds: int = 90
    script_depth: str = "normal"
    narrative_style: str = "dramatic"
    auto_generate_script: bool = True
    auto_generate_voice: bool = False
    auto_suggest_visuals: bool = False
    force_research: bool = False
    content_format: str = "manual_topic"
    extra_context: str = ""


class GenerationProjectFromScriptPayload(BaseModel):
    script: str
    title: str = ""
    niche: str = ""
    language: str = "pt-BR"
    tone: str = "curioso"
    duration_seconds: int = 90
    auto_generate_voice: bool = False
    auto_suggest_visuals: bool = True


class GenerationOpportunitySearchPayload(BaseModel):
    niche: str
    language: str = "pt-BR"
    region: str = "BR"
    time_window: str = "week"
    query: str = ""
    count: int = 5
    provider: str = "auto"
    use_grounding: bool = True


class GenerationProjectFromOpportunityPayload(BaseModel):
    opportunity: dict[str, Any]
    duration_seconds: int = 90
    script_depth: str = "normal"
    narrative_style: str = "documentary"
    auto_generate_script: bool = True
    auto_generate_voice: bool = False
    auto_suggest_visuals: bool = False
    force_research: bool = False
    extra_context: str = ""


class GenerationProjectsFromOpportunitiesBatchPayload(BaseModel):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    duration_seconds: int = 90
    script_depth: str = "normal"
    narrative_style: str = "documentary"
    auto_generate_script: bool = True
    auto_generate_voice: bool = False
    auto_suggest_visuals: bool = False
    max_projects: int = 3


class GenerationProjectScriptRegeneratePayload(BaseModel):
    duration_seconds: int = 60
    duration_preset: str = ""
    force_research: bool = False
    tone: str = ""
    language: str = "pt-BR"
    provider: str = "auto"
    script_depth: str = "normal"
    narrative_style: str = ""


class GenerationProjectScriptImprovePayload(BaseModel):
    script_depth: str = "deep"
    narrative_style: str = "dramatic"
    duration_seconds: int = 90
    preserve_facts: bool = True
    force_research: bool = False
    provider: str = "auto"


class GenerationProjectResearchRegeneratePayload(BaseModel):
    force_research: bool = True
    provider: str = "auto"


class GenerationVoicePayload(BaseModel):
    voice: str = "pt-BR-AntonioNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"


class GenerationVisualItemsPayload(BaseModel):
    visual_items: list[dict[str, Any]] = Field(default_factory=list)


class GenerationVisualItemPayload(BaseModel):
    visual_id: str = ""
    order: int = 0
    script_line_index: int = 0
    story_beat_id: str = ""
    beat_role: str = ""
    type: str = "placeholder"
    query: str = ""
    description: str = ""
    suggested_prompt: str = ""
    source: str = "manual"
    license_lane: str = "unknown"
    media_url: str = ""
    thumbnail_url: str = ""
    media_path: str = ""
    duration_seconds: float = 0
    start_at_seconds: float = 0
    end_at_seconds: float = 0
    status: str = "suggestion"
    notes: str = ""
    risk_notes: str = ""


class GenerationStockSearchPayload(BaseModel):
    query: str
    orientation: str = "portrait"


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


@router.get("/engine/status")
def get_generation_engine_status() -> dict[str, Any]:
    return engine_status()


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


@router.post("/research-brief")
def post_generation_research_brief(payload: GenerationFactualBriefPayload) -> dict[str, Any]:
    return generate_research_brief(
        niche=payload.niche,
        topic=payload.topic or payload.idea,
        language=payload.language,
        tone=payload.tone,
        force_research=payload.force_research,
        provider_override=payload.provider,
    )


@router.post("/factual-brief")
def post_generation_factual_brief(payload: GenerationFactualBriefPayload) -> dict[str, Any]:
    return post_generation_research_brief(payload)


@router.post("/scripts")
def post_generation_script(payload: GenerationScriptPayload) -> dict[str, Any]:
    return generate_script(
        idea=payload.idea,
        niche=payload.niche,
        topic=payload.topic,
        duration_seconds=payload.duration_seconds,
        duration_preset=payload.duration_preset,
        tone=payload.tone,
        language=payload.language,
        force_research=payload.force_research,
        provider=payload.provider,
        script_depth=payload.script_depth,
        narrative_style=payload.narrative_style,
        content_format=payload.content_format,
        extra_context=payload.extra_context,
        opportunity_data=payload.opportunity_data,
    )


@router.get("/projects")
def get_generation_projects() -> dict[str, Any]:
    return {"projects": list_projects()}


@router.post("/opportunities/search")
def post_generation_opportunities_search(
    payload: GenerationOpportunitySearchPayload,
) -> dict[str, Any]:
    return search_opportunities(
        niche=payload.niche,
        language=payload.language,
        region=payload.region,
        time_window=payload.time_window,
        query=payload.query,
        count=payload.count,
        provider=payload.provider,
        use_grounding=payload.use_grounding,
    )


@router.post("/projects/from-idea")
def post_generation_project_from_idea(
    payload: GenerationProjectFromIdeaPayload,
) -> dict[str, Any]:
    return create_project_from_idea(**payload.dict())


@router.post("/projects/from-script")
def post_generation_project_from_script(
    payload: GenerationProjectFromScriptPayload,
) -> dict[str, Any]:
    return create_project_from_script(**payload.dict())


@router.post("/projects/from-opportunity")
def post_generation_project_from_opportunity(
    payload: GenerationProjectFromOpportunityPayload,
) -> dict[str, Any]:
    return create_project_from_opportunity(**payload.dict())


@router.post("/projects/from-opportunities-batch")
def post_generation_projects_from_opportunities_batch(
    payload: GenerationProjectsFromOpportunitiesBatchPayload,
) -> dict[str, Any]:
    projects = create_projects_from_opportunities_batch(**payload.dict())
    return {"projects": projects, "count": len(projects)}


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


@router.post("/projects/{project_id}/script/regenerate")
def post_generation_project_script_regenerate(
    project_id: str,
    payload: GenerationProjectScriptRegeneratePayload,
) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    script = generate_script(
        idea=project.get("idea") or project.get("title") or "",
        niche=project.get("niche") or "",
        topic=project.get("idea") or project.get("title") or "",
        duration_seconds=payload.duration_seconds,
        duration_preset=payload.duration_preset,
        tone=payload.tone or project.get("tone") or "curioso",
        language=payload.language or project.get("language") or "pt-BR",
        force_research=payload.force_research,
        provider=payload.provider,
        script_depth=payload.script_depth or project.get("script_depth") or "normal",
        narrative_style=payload.narrative_style or project.get("narrative_style") or "",
        content_format=project.get("content_format") or "manual_topic",
        extra_context=project.get("extra_context") or "",
        opportunity_data=project.get("opportunity_data") or {},
    )
    voice_outdated = bool(project.get("voice_status") == "ready" or project.get("voice_audio_path"))
    updated = update_project(
        project_id,
        {
            **project,
            **script,
            "idea": project.get("idea") or script.get("title") or "",
            "status": "script",
            "voice_outdated": voice_outdated,
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return updated


@router.post("/projects/{project_id}/script/improve")
def post_generation_project_script_improve(
    project_id: str,
    payload: GenerationProjectScriptImprovePayload,
) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    script = generate_script(
        idea=project.get("idea") or project.get("title") or "",
        niche=project.get("niche") or "",
        topic=project.get("idea") or project.get("title") or "",
        duration_seconds=payload.duration_seconds,
        duration_preset="",
        tone=project.get("tone") or "curioso",
        language=project.get("language") or "pt-BR",
        force_research=payload.force_research,
        provider=payload.provider,
        script_depth=payload.script_depth,
        narrative_style=payload.narrative_style,
        content_format=project.get("content_format") or "manual_topic",
        extra_context=project.get("extra_context") or "",
        opportunity_data=project.get("opportunity_data") or {},
    )
    if payload.preserve_facts:
        script["research_brief"] = script.get("research_brief") or project.get("research_brief") or {}
        script["factual_brief"] = script.get("factual_brief") or project.get("factual_brief") or {}
    voice_outdated = bool(project.get("voice_status") == "ready" or project.get("voice_audio_path"))
    updated = update_project(
        project_id,
        {
            **project,
            **script,
            "idea": project.get("idea") or script.get("title") or "",
            "status": "script",
            "voice_outdated": voice_outdated,
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return updated


@router.post("/projects/{project_id}/research/regenerate")
def post_generation_project_research_regenerate(
    project_id: str,
    payload: GenerationProjectResearchRegeneratePayload,
) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    brief = generate_research_brief(
        niche=project.get("niche") or "",
        topic=project.get("idea") or project.get("title") or "",
        language=project.get("language") or "pt-BR",
        tone=project.get("tone") or "curioso",
        force_research=payload.force_research,
        provider_override=payload.provider,
    )
    updated = update_project(
        project_id,
        {
            **project,
            "research_brief": brief,
            "factual_brief": brief,
            "research_cache_hit": bool(brief.get("research_cache_hit")),
            "force_research_used": bool(brief.get("force_research_used")),
            "source_urls": brief.get("source_urls", []),
            "source_titles": brief.get("source_titles", []),
            "grounding_used": bool(brief.get("grounding_used")),
            "grounding_available": bool(brief.get("grounding_available")),
            "search_queries": brief.get("search_queries", []),
            "factual_grounding_confidence": brief.get("confidence", "low"),
            "last_llm_error": brief.get("last_llm_error", ""),
            "last_llm_provider": brief.get("last_llm_provider", ""),
            "last_llm_model": brief.get("last_llm_model", ""),
            "research_call_count": int(project.get("research_call_count") or 0)
            + int(brief.get("research_call_count") or 0),
            "llm_call_count": int(project.get("llm_call_count") or 0)
            + int(brief.get("research_call_count") or 0),
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return updated


@router.post("/projects/{project_id}/guardrail")
def post_generation_project_guardrail(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    guardrail = analyze_generation_project(project)
    updated = update_project(project_id, {**project, **guardrail})
    if not updated:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return updated


@router.post("/projects/{project_id}/visuals/suggest")
def post_generation_project_visuals_suggest(project_id: str) -> dict[str, Any]:
    project = suggest_visuals_for_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.put("/projects/{project_id}/visuals")
def put_generation_project_visuals(project_id: str, payload: GenerationVisualItemsPayload) -> dict[str, Any]:
    project = update_visual_items(project_id, payload.visual_items)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.post("/projects/{project_id}/visuals")
def post_generation_project_visual(project_id: str, payload: GenerationVisualItemPayload) -> dict[str, Any]:
    project = add_visual_item(project_id, payload.dict())
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.delete("/projects/{project_id}/visuals/{visual_id}")
def delete_generation_project_visual(project_id: str, visual_id: str) -> dict[str, Any]:
    project = remove_visual_item(project_id, visual_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.post("/projects/{project_id}/visuals/{visual_id}/select")
def post_generation_project_visual_select(project_id: str, visual_id: str) -> dict[str, Any]:
    project = mark_visual_item_selected(project_id, visual_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.post("/projects/{project_id}/visuals/{visual_id}/reject")
def post_generation_project_visual_reject(project_id: str, visual_id: str) -> dict[str, Any]:
    project = reject_visual_item(project_id, visual_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.post("/projects/{project_id}/visuals/mark-ready")
def post_generation_project_visuals_mark_ready(project_id: str) -> dict[str, Any]:
    project = mark_visuals_ready(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="generation_project_not_found")
    return project


@router.post("/visuals/search-stock")
def post_generation_visuals_search_stock(payload: GenerationStockSearchPayload) -> dict[str, Any]:
    return search_stock_media(query=payload.query, orientation=payload.orientation)


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
