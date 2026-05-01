from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api import model_configs as model_configs_api
from common.ai import encryption as encryption_module
from common.ai.models import ModelConfig
from common.auth.service import create_access_token


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

    assert response.status_code == 200
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

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    created_id = body["data"]["id"]

    result = await test_db.execute(
        select(ModelConfig).where(ModelConfig.id == created_id)
    )
    config = result.scalar_one()
    assert config.base_url == "https://api.openai.com/v1"
    assert config.api_key_encrypted != plaintext_key
    assert encryption_module.decrypt_api_key(config.api_key_encrypted).value == plaintext_key
