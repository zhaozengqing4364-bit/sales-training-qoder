"""
Admin API - Voice Runtime Policies

Manages:
- Runtime profiles (global presets)
- Agent-level runtime policy overrides
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService

logger = get_logger(__name__)


class RuntimeProfilePayload(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    is_default: bool = False
    is_active: bool = True
    voice_mode: str = Field(default="stepfun_realtime")
    model_name: str = Field(default="step-audio-2", max_length=100)
    voice_name: str = Field(default="qingchunshaonv", max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    input_audio_format: str = Field(default="pcm16", max_length=20)
    output_audio_format: str = Field(default="pcm16", max_length=20)
    output_sample_rate: int = Field(default=24000, ge=8000, le=48000)
    turn_detection: str | None = Field(default=None)
    system_instruction_template: str | None = None
    tool_policy: dict[str, Any] = Field(default_factory=dict)


class RuntimeProfileUpdatePayload(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None
    is_active: bool | None = None
    voice_mode: str | None = None
    model_name: str | None = Field(default=None, max_length=100)
    voice_name: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    input_audio_format: str | None = Field(default=None, max_length=20)
    output_audio_format: str | None = Field(default=None, max_length=20)
    output_sample_rate: int | None = Field(default=None, ge=8000, le=48000)
    turn_detection: str | None = Field(default=None)
    system_instruction_template: str | None = None
    tool_policy: dict[str, Any] | None = None


class AgentVoicePolicyPayload(BaseModel):
    enabled: bool = True
    runtime_profile_id: str | None = None
    voice_mode_override: str | None = None
    model_override: str | None = None
    voice_override: str | None = None
    temperature_override: float | None = Field(default=None, ge=0, le=2)
    instructions_override: str | None = None
    tool_policy_override: dict[str, Any] = Field(default_factory=dict)


router = APIRouter(
    prefix="/voice-runtime",
    tags=["voice-runtime"],
    dependencies=[Depends(get_current_admin_user)],
)


def _success(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "trace_id": get_trace_id()}


@router.get("/profiles")
async def list_runtime_profiles(
    only_active: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    service = VoiceRuntimePolicyService(db)
    profiles = await service.list_profiles(only_active=only_active)
    return _success({"items": profiles, "total": len(profiles)})


@router.post("/profiles")
async def create_runtime_profile(
    payload: RuntimeProfilePayload,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = VoiceRuntimePolicyService(db)
    try:
        created = await service.create_profile(payload.model_dump())
        await db.commit()
        return _success(created)
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Failed to create runtime profile: {exc}")
        raise HTTPException(status_code=500, detail="[VOICE_RUNTIME_PROFILE_CREATE_FAILED]") from exc


@router.put("/profiles/{profile_id}")
async def update_runtime_profile(
    profile_id: str,
    payload: RuntimeProfileUpdatePayload,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = VoiceRuntimePolicyService(db)
    try:
        updated = await service.update_profile(profile_id, payload.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=404, detail="[VOICE_RUNTIME_PROFILE_NOT_FOUND]")
        await db.commit()
        return _success(updated)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Failed to update runtime profile: {exc}")
        raise HTTPException(status_code=500, detail="[VOICE_RUNTIME_PROFILE_UPDATE_FAILED]") from exc


@router.delete("/profiles/{profile_id}")
async def delete_runtime_profile(
    profile_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = VoiceRuntimePolicyService(db)
    try:
        deleted = await service.delete_profile(profile_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="[VOICE_RUNTIME_PROFILE_NOT_FOUND]")
        await db.commit()
        return _success({"deleted": True})
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Failed to delete runtime profile: {exc}")
        raise HTTPException(status_code=500, detail="[VOICE_RUNTIME_PROFILE_DELETE_FAILED]") from exc


@router.get("/agents/{agent_id}/policy")
async def get_agent_voice_policy(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = VoiceRuntimePolicyService(db)
    data = await service.get_agent_policy(agent_id)
    return _success(data)


@router.put("/agents/{agent_id}/policy")
async def upsert_agent_voice_policy(
    agent_id: str,
    payload: AgentVoicePolicyPayload,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = VoiceRuntimePolicyService(db)
    try:
        data = await service.upsert_agent_policy(agent_id, payload.model_dump(exclude_unset=True))
        await db.commit()
        return _success(data)
    except ValueError as exc:
        await db.rollback()
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=f"[{message}]") from exc
        raise HTTPException(status_code=400, detail=f"[{message}]") from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Failed to upsert agent voice policy: {exc}")
        raise HTTPException(status_code=500, detail="[AGENT_VOICE_POLICY_UPSERT_FAILED]") from exc


@router.get("/agents/{agent_id}/effective")
async def preview_effective_agent_policy(
    agent_id: str,
    persona_id: str | None = Query(None),
    voice_mode_override: str | None = Query(None),
    runtime_profile_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = VoiceRuntimePolicyService(db)
    data = await service.resolve_effective_policy(
        agent_id=agent_id,
        persona_id=persona_id,
        voice_mode_override=voice_mode_override,
        runtime_profile_override=runtime_profile_id,
    )
    return _success(data)
