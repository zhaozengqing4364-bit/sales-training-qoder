from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.schemas import RoleProfileCreate, RoleProfileResponse
from curriculum_practice.services.content_assets import (
    ContentAssetService,
    role_profile_content_hash,
)
from curriculum_practice.services.voice_clone import VoiceCloneResult
from sales_bot.websocket.components.stepfun_voice_selection import resolve_session_voice


class _SuccessfulVoiceCloneService:
    async def create_voice(
        self,
        *,
        voice_name: str,
        audio_bytes: bytes,
        content_type: str,
    ) -> VoiceCloneResult:
        return VoiceCloneResult(
            ok=True,
            voice_id="custom_voice_cto",
            retryable=False,
            fallback_voice=None,
            reason_code=None,
        )


def _role_profile_payload(*, content_hash: str = "sha256:pending") -> dict[str, object]:
    return {
        "role_type": "customer",
        "role_name": "谨慎型 CTO",
        "persona_ref": None,
        "communication_style": "直接、重视技术细节和风险控制",
        "pressure_level": "high",
        "knowledge_boundary": ["了解内部预算流程", "不知道最终采购时间"],
        "behavior_rules": ["只回答被直接提问的问题", "价格问题上先反驳再让步"],
        "voice_style_hint": "语速偏快，语调克制",
        "voice_id": None,
        "voice_sample_url": None,
        "content_hash": content_hash,
    }


@pytest.mark.asyncio
async def test_should_register_voice_and_update_role_profile(
    test_db: AsyncSession,
) -> None:
    payload = _role_profile_payload()
    payload["content_hash"] = role_profile_content_hash(payload)
    service = ContentAssetService(test_db)
    role_profile = await service.create_role_profile(
        RoleProfileCreate.model_validate(payload), actor_id="admin-1"
    )

    result = await service.register_role_profile_voice(
        role_profile,
        voice_service=_SuccessfulVoiceCloneService(),
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
        voice_sample_url="oss://role-voices/cto.wav",
        actor_id="admin-1",
    )

    refreshed = await service.get_role_profile(role_profile.role_profile_id)
    assert result.ok is True
    assert refreshed is not None
    assert refreshed.voice_id == "custom_voice_cto"
    assert refreshed.voice_sample_url == "oss://role-voices/cto.wav"
    assert refreshed.content_hash == role_profile_content_hash(
        RoleProfileResponse.model_validate(refreshed)
    )


async def test_should_initialize_stepfun_session_with_role_profile_voice_id() -> None:
    voice = resolve_session_voice(
        default_voice="default_voice",
        runtime_snapshot={"role_profile_voice_id": "custom_voice_cto"},
    )

    assert voice == "custom_voice_cto"


async def test_should_fallback_to_default_voice_when_role_voice_unavailable() -> None:
    voice = resolve_session_voice(
        default_voice="default_voice",
        runtime_snapshot={"role_profile_voice_id": "custom_voice_cto"},
        unavailable_voice_ids={"custom_voice_cto"},
    )

    assert voice == "default_voice"


async def test_should_not_attempt_voice_hot_switching_during_runtime() -> None:
    voice = resolve_session_voice(
        default_voice="default_voice",
        runtime_snapshot={
            "role_profile_voice_id": "custom_voice_cto",
            "stage_snapshots": {
                "opening": {"runtime_payload": {"role_profile_voice_id": "voice_a"}},
                "closing": {"runtime_payload": {"role_profile_voice_id": "voice_b"}},
            },
        },
        current_stage_key="closing",
        allow_hot_switch=False,
    )

    assert voice == "custom_voice_cto"
