from __future__ import annotations

import json
import sys
import types
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api import model_configs as model_configs_api
from common.ai import encryption as encryption_module
from common.ai.models import ModelConfig
from common.auth.service import create_access_token
from common.db.models import SystemLog


def _admin_headers(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


def _reset_encryption_key(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())
    encryption_module.get_encryption.cache_clear()
    encryption_module._encryption = None


@pytest.mark.asyncio
async def test_create_model_config_rejects_private_endpoint_and_keeps_db_empty(
    async_client,
    test_db: AsyncSession,
    test_user,
    monkeypatch,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _admin_headers(str(test_user.user_id))
    _reset_encryption_key(monkeypatch)
    monkeypatch.setattr(
        model_configs_api,
        "_refresh_runtime_services",
        AsyncMock(return_value=None),
    )

    response = await async_client.post(
        "/api/v1/admin/model-configs",
        headers=headers,
        json={
            "name": "OpenAI test config",
            "model_type": "llm",
            "provider": "openai",
            "base_url": "https://127.0.0.1:8443/v1",
            "api_key": "test-openai-key-12345",
            "model_name": "gpt-4o-mini",
            "extra_config": {},
            "is_default": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "[MODEL_CONFIG_ENDPOINT_POLICY_VIOLATION]"

    result = await test_db.execute(select(ModelConfig))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_create_model_config_normalizes_endpoint_and_encrypts_key(
    async_client,
    test_db: AsyncSession,
    test_user,
    monkeypatch,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _admin_headers(str(test_user.user_id))
    _reset_encryption_key(monkeypatch)
    monkeypatch.setattr(
        model_configs_api,
        "_refresh_runtime_services",
        AsyncMock(return_value=None),
    )

    plaintext_key = "test-openai-key-12345"
    response = await async_client.post(
        "/api/v1/admin/model-configs",
        headers=headers,
        json={
            "name": "OpenAI test config",
            "model_type": "llm",
            "provider": "openai",
            "base_url": "https://api.openai.com/v1/",
            "api_key": plaintext_key,
            "model_name": "gpt-4o-mini",
            "extra_config": {},
            "is_default": False,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    created_id = body["data"]["id"]

    result = await test_db.execute(
        select(ModelConfig).where(ModelConfig.id == created_id)
    )
    config = result.scalar_one()
    assert config.base_url == "https://api.openai.com/v1"
    assert config.api_key_encrypted != plaintext_key
    assert (
        encryption_module.decrypt_api_key(config.api_key_encrypted).value
        == plaintext_key
    )


@pytest.mark.asyncio
async def test_should_return_conflict_when_creating_duplicate_model_config(
    async_client,
    test_db: AsyncSession,
    test_user,
    monkeypatch,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _admin_headers(str(test_user.user_id))
    _reset_encryption_key(monkeypatch)
    monkeypatch.setattr(
        model_configs_api,
        "_refresh_runtime_services",
        AsyncMock(return_value=None),
    )
    payload = {
        "name": "DeepSeek Flash",
        "model_type": "llm",
        "provider": "openai",
        "base_url": "https://api.deepseek.com/v1/",
        "api_key": "test-openai-key-12345",
        "model_name": "deepseek-v4-flash",
        "extra_config": {},
        "is_default": False,
    }

    created = await async_client.post(
        "/api/v1/admin/model-configs",
        headers=headers,
        json=payload,
    )
    duplicate = await async_client.post(
        "/api/v1/admin/model-configs",
        headers=headers,
        json={**payload, "name": "DeepSeek Flash duplicate"},
    )

    assert created.status_code == 201
    assert duplicate.status_code == 409
    body = duplicate.json()
    assert body["success"] is False
    assert body["error_code"] == "[MODEL_CONFIG_DUPLICATE]"


@pytest.mark.asyncio
async def test_model_config_crud_and_persisted_test_write_audit_logs(
    async_client,
    test_db: AsyncSession,
    test_user,
    monkeypatch,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _admin_headers(str(test_user.user_id))
    _reset_encryption_key(monkeypatch)
    monkeypatch.setattr(
        model_configs_api,
        "_refresh_runtime_services",
        AsyncMock(return_value=None),
    )

    response = await async_client.post(
        "/api/v1/admin/model-configs",
        headers=headers,
        json={
            "name": "Local TTS",
            "model_type": "tts",
            "provider": "local",
            "base_url": "",
            "api_key": "",
            "model_name": "zh-CN-XiaoxiaoNeural",
            "extra_config": {"voice": "zh-CN-XiaoxiaoNeural"},
            "is_default": False,
        },
    )
    assert response.status_code == 201
    created_id = response.json()["data"]["id"]

    update_response = await async_client.patch(
        f"/api/v1/admin/model-configs/{created_id}",
        headers=headers,
        json={"name": "Local TTS v2"},
    )
    assert update_response.status_code == 200

    test_response = await async_client.post(
        f"/api/v1/admin/model-configs/{created_id}/test",
        headers=headers,
    )
    assert test_response.status_code == 200
    assert test_response.json()["data"]["success"] is True

    delete_response = await async_client.delete(
        f"/api/v1/admin/model-configs/{created_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200

    rows = (
        await test_db.execute(
            select(SystemLog)
            .where(SystemLog.user_id == str(test_user.user_id))
            .where(
                SystemLog.action.in_(
                    [
                        "model_config_create",
                        "model_config_update",
                        "model_config_test",
                        "model_config_delete",
                    ]
                )
            )
            .order_by(SystemLog.created_at.asc())
        )
    ).scalars().all()
    assert [row.action for row in rows] == [
        "model_config_create",
        "model_config_update",
        "model_config_test",
        "model_config_delete",
    ]

    details_by_action = {
        row.action: json.loads(row.details or "{}")
        for row in rows
    }
    create_details = details_by_action["model_config_create"]
    assert create_details["target_config_id"] == created_id
    assert create_details["before"] is None
    assert create_details["after"]["name"] == "Local TTS"
    assert create_details["after"]["api_key_configured"] is False
    assert create_details["trace_id"]
    assert create_details["source"] == "admin.api.model_configs"

    update_details = details_by_action["model_config_update"]
    assert update_details["before"]["name"] == "Local TTS"
    assert update_details["after"]["name"] == "Local TTS v2"

    test_details = details_by_action["model_config_test"]
    assert test_details["before"]["last_test_status"] is None
    assert test_details["after"]["last_test_status"] == "success"
    assert test_details["success"] is True
    assert test_details["test_kind"] == "persisted"
    assert isinstance(test_details["latency_ms"], int)

    delete_details = details_by_action["model_config_delete"]
    assert delete_details["before"]["id"] == created_id
    assert delete_details["after"] is None
    assert all("api_key_encrypted" not in (row.details or "") for row in rows)


@pytest.mark.asyncio
async def test_tts_preview_writes_audit_without_recording_preview_text(
    async_client,
    test_db: AsyncSession,
    test_user,
    monkeypatch,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _admin_headers(str(test_user.user_id))

    class FakeCommunicate:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def stream(self):
            yield {"type": "audio", "data": b"mp3-bytes"}

    fake_edge_tts = types.SimpleNamespace(Communicate=FakeCommunicate)
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge_tts)

    response = await async_client.post(
        "/api/v1/admin/model-configs/tts/preview",
        headers=headers,
        params={
            "text": "这段内容不应该进入审计详情",
            "voice": "zh-CN-XiaoxiaoNeural",
        },
    )

    assert response.status_code == 200
    assert response.content == b"mp3-bytes"

    audit = (
        await test_db.execute(
            select(SystemLog).where(SystemLog.action == "model_config_tts_preview")
        )
    ).scalar_one()
    details = json.loads(audit.details or "{}")
    assert audit.user_id == str(test_user.user_id)
    assert details["success"] is True
    assert details["after"]["voice"] == "zh-CN-XiaoxiaoNeural"
    assert details["after"]["audio_size_bytes"] == len(b"mp3-bytes")
    assert "这段内容" not in (audit.details or "")
    assert details["source"] == "admin.api.model_configs.tts_preview"
