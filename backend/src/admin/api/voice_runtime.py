"""
Admin API - Voice Runtime Policies

Manages:
- Runtime profiles (global presets)
- Agent-level runtime policy overrides
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.server_error import build_server_error
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService
from support.services.runtime_status_service import RuntimeStatusService

logger = get_logger(__name__)


class RuntimeProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    is_default: bool = False
    is_active: bool = True
    voice_mode: Literal["legacy", "stepfun_realtime"] = Field(
        default="stepfun_realtime"
    )
    model_name: str = Field(default="step-audio-r1.1", max_length=100)
    voice_name: str = Field(default="qingchunshaonv", max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    input_audio_format: str = Field(default="pcm16", max_length=20)
    output_audio_format: str = Field(default="pcm16", max_length=20)
    output_sample_rate: int = Field(default=24000, ge=8000, le=48000)
    turn_detection: str | None = Field(default=None)
    tool_policy: dict[str, Any] = Field(default_factory=dict)


class RuntimeProfileUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None
    is_active: bool | None = None
    voice_mode: Literal["legacy", "stepfun_realtime"] | None = None
    model_name: str | None = Field(default=None, max_length=100)
    voice_name: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    input_audio_format: str | None = Field(default=None, max_length=20)
    output_audio_format: str | None = Field(default=None, max_length=20)
    output_sample_rate: int | None = Field(default=None, ge=8000, le=48000)
    turn_detection: str | None = Field(default=None)
    tool_policy: dict[str, Any] | None = None


class AgentVoicePolicyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    runtime_profile_id: str | None = None
    voice_mode_override: Literal["legacy", "stepfun_realtime"] | None = None
    model_override: str | None = None
    voice_override: str | None = None
    temperature_override: float | None = Field(default=None, ge=0, le=2)
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
    runtime_service = RuntimeStatusService(db)
    governance_indexes = await runtime_service.build_asset_governance_indexes()
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    for profile in profiles:
        updated_at = RuntimeStatusService._coerce_datetime(profile.get("updated_at"))
        extra_anomalies: list[dict[str, Any]] = []
        if profile.get("is_active") is False:
            extra_anomalies.append(
                {
                    "source": "asset",
                    "kind": "runtime_profile_inactive",
                    "severity": "warning",
                    "summary": "运行时配置已停用，新增会话不会继续使用它。",
                    "detected_at": updated_at,
                    "session_id": None,
                }
            )

        latest_change_label = (
            "默认运行时配置已更新"
            if profile.get("is_default")
            else "运行时配置已更新"
        )
        profile["governance_summary"] = runtime_service.build_asset_governance_summary(
            governance_indexes.get("runtime_profile", {}).get(str(profile.get("id") or "")),
            last_changed_at=updated_at,
            latest_change_type="runtime_profile_updated",
            latest_change_label=latest_change_label,
            change_count_7d=1 if updated_at and updated_at >= seven_days_ago else 0,
            extra_anomalies=extra_anomalies,
        )

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
        created = await service.create_profile(payload.model_dump(exclude_unset=True))
        await db.commit()
        return _success(created)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[VOICE_RUNTIME_PROFILE_CREATE_FAILED]",
            message="Failed to create runtime profile",
            exc=exc,
        )


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
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[VOICE_RUNTIME_PROFILE_UPDATE_FAILED]",
            message="Failed to update runtime profile",
            exc=exc,
            profile_id=profile_id,
        )


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
        return build_server_error(
            "[VOICE_RUNTIME_PROFILE_DELETE_FAILED]",
            message="Failed to delete runtime profile",
            exc=exc,
            profile_id=profile_id,
        )


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
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[AGENT_VOICE_POLICY_UPSERT_FAILED]",
            message="Failed to upsert agent voice policy",
            exc=exc,
            agent_id=agent_id,
        )


@router.get("/agents/{agent_id}/effective")
async def preview_effective_agent_policy(
    agent_id: str,
    persona_id: str | None = Query(None),
    voice_mode_override: Literal["legacy", "stepfun_realtime"] | None = Query(None),
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
