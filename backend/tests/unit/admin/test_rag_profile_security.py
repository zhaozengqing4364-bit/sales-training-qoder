from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

import common.ai.encryption as encryption_module
from admin.api.rag_profiles import (
    CreateRagProfileRequest,
    CrossEncoderSettings,
    UpdateRagProfileRequest,
    create_rag_profile,
    get_rag_profile,
    update_rag_profile,
)
from common.knowledge.models import KnowledgeBase  # noqa: F401
from common.knowledge.rag_profile_models import RagProfile
from common.knowledge.rag_profile_service import resolve_rag_profile


@pytest.fixture(autouse=True)
def configured_encryption_key(monkeypatch):
    monkeypatch.setenv("MODEL_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())
    encryption_module._encryption = None
    encryption_module.get_encryption.cache_clear()
    yield
    encryption_module._encryption = None
    encryption_module.get_encryption.cache_clear()


@pytest.mark.asyncio
async def test_rag_profile_create_encrypts_key_and_response_redacts_plaintext(test_db):
    plaintext = "cohere-secret-value"
    response = await create_rag_profile(
        CreateRagProfileRequest(
            name="secure-profile",
            cross_encoder=CrossEncoderSettings(
                backend="cohere",
                model="rerank-v3",
                api_key=plaintext,
            ),
        ),
        test_db,
    )

    profile = (
        await test_db.execute(
            select(RagProfile).where(RagProfile.name == "secure-profile")
        )
    ).scalar_one()

    assert profile.cross_encoder_api_key != plaintext
    assert response["data"]["cross_encoder"] == {
        "backend": "cohere",
        "model": "rerank-v3",
        "device": None,
        "has_api_key": True,
    }
    assert plaintext not in str(response)

    resolved = await resolve_rag_profile(
        test_db, SimpleNamespace(rag_profile_id=profile.id)
    )
    assert resolved is not None
    assert resolved.cross_encoder_api_key == plaintext


@pytest.mark.asyncio
async def test_rag_profile_update_omitted_key_keeps_existing_and_empty_key_clears(
    test_db,
):
    plaintext = "cohere-secret-value"
    await create_rag_profile(
        CreateRagProfileRequest(
            name="update-profile",
            cross_encoder=CrossEncoderSettings(backend="cohere", api_key=plaintext),
        ),
        test_db,
    )
    profile = (
        await test_db.execute(
            select(RagProfile).where(RagProfile.name == "update-profile")
        )
    ).scalar_one()
    original_encrypted = profile.cross_encoder_api_key

    await update_rag_profile(
        profile.id,
        UpdateRagProfileRequest(cross_encoder=CrossEncoderSettings(model="rerank-v4")),
        test_db,
    )
    await test_db.refresh(profile)
    assert profile.cross_encoder_api_key == original_encrypted

    response = await update_rag_profile(
        profile.id,
        UpdateRagProfileRequest(cross_encoder=CrossEncoderSettings(api_key="")),
        test_db,
    )
    await test_db.refresh(profile)

    assert profile.cross_encoder_api_key is None
    assert response["data"]["cross_encoder"]["has_api_key"] is False


@pytest.mark.asyncio
async def test_rag_profile_get_response_never_returns_plaintext_key(test_db):
    plaintext = "cohere-secret-value"
    await create_rag_profile(
        CreateRagProfileRequest(
            name="read-profile",
            cross_encoder=CrossEncoderSettings(backend="cohere", api_key=plaintext),
        ),
        test_db,
    )
    profile = (
        await test_db.execute(
            select(RagProfile).where(RagProfile.name == "read-profile")
        )
    ).scalar_one()

    response = await get_rag_profile(profile.id, test_db)

    assert response["data"]["cross_encoder"]["has_api_key"] is True
    assert plaintext not in str(response)


@pytest.mark.asyncio
async def test_rag_profile_runtime_lazily_reencrypts_legacy_plaintext(test_db):
    legacy_key = "legacy-plaintext-key"
    profile = RagProfile(
        name="legacy-profile",
        cross_encoder_backend="cohere",
        cross_encoder_api_key=legacy_key,
    )
    test_db.add(profile)
    await test_db.commit()
    await test_db.refresh(profile)

    resolved = await resolve_rag_profile(
        test_db, SimpleNamespace(rag_profile_id=profile.id)
    )
    await test_db.refresh(profile)

    assert resolved is not None
    assert resolved.cross_encoder_api_key == legacy_key
    assert profile.cross_encoder_api_key != legacy_key
