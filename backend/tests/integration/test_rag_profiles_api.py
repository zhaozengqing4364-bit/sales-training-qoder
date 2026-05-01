from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai import encryption as encryption_module
from common.auth.service import create_access_token
from common.knowledge.rag_profile_models import RagProfile
from common.knowledge.rag_profile_service import resolve_rag_profile


def _admin_headers(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


def _reset_encryption_key(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())
    encryption_module.get_encryption.cache_clear()
    encryption_module._encryption = None


@pytest.mark.asyncio
async def test_create_rag_profile_encrypts_api_key_and_redacts_response(
    async_client,
    test_db: AsyncSession,
    test_user,
    monkeypatch,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _admin_headers(str(test_user.user_id))
    _reset_encryption_key(monkeypatch)

    plaintext_key = "plain-reranker-key"
    response = await async_client.post(
        "/api/v1/admin/rag-profiles",
        headers=headers,
        json={
            "name": "secure-rag-profile",
            "description": "profile used to verify encryption",
            "is_system_default": True,
            "chunking": {
                "strategy": "element_boundary",
                "chunk_size": 500,
                "chunk_overlap": 50,
            },
            "semantic_cache": {
                "enabled": True,
                "similarity_threshold": 0.95,
                "ttl_seconds": 300,
            },
            "cross_encoder": {
                "backend": "local",
                "model": "cross-encoder-small",
                "device": "cpu",
                "api_key": plaintext_key,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["cross_encoder"]["has_api_key"] is True
    assert plaintext_key not in response.text

    created_id = body["data"]["id"]
    result = await test_db.execute(select(RagProfile).where(RagProfile.id == created_id))
    row = result.scalar_one()
    assert row.cross_encoder_api_key != plaintext_key

    resolved = await resolve_rag_profile(
        test_db,
        SimpleNamespace(rag_profile_id=created_id),
    )
    assert resolved is not None
    assert resolved.cross_encoder_api_key == plaintext_key


@pytest.mark.asyncio
async def test_resolve_rag_profile_lazily_reencrypts_legacy_plaintext(
    test_db: AsyncSession,
    monkeypatch,
):
    _reset_encryption_key(monkeypatch)

    profile = RagProfile(
        id=str(uuid.uuid4()),
        name="legacy-profile",
        description="seeded legacy plaintext",
        is_system_default=0,
        chunking_strategy="element_boundary",
        chunk_size=500,
        chunk_overlap=50,
        semantic_cache_enabled=1,
        semantic_cache_similarity_threshold=0.95,
        semantic_cache_ttl_seconds=300,
        cross_encoder_backend="local",
        cross_encoder_model="legacy-reranker",
        cross_encoder_device="cpu",
        cross_encoder_api_key="legacy-plaintext-key",
    )
    test_db.add(profile)
    await test_db.commit()

    resolved = await resolve_rag_profile(
        test_db,
        SimpleNamespace(rag_profile_id=profile.id),
    )

    assert resolved is not None
    assert resolved.cross_encoder_api_key == "legacy-plaintext-key"

    result = await test_db.execute(select(RagProfile).where(RagProfile.id == profile.id))
    stored = result.scalar_one()
    assert stored.cross_encoder_api_key != "legacy-plaintext-key"
