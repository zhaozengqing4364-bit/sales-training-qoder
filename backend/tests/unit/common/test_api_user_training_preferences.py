"""Tests for current-user scoped training preferences."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User, UserTrainingPreference


@pytest.mark.asyncio
async def test_get_training_preferences_returns_empty_payload_without_record(
    async_client: AsyncClient,
    auth_headers: dict,
):
    response = await async_client.get(
        "/api/v1/users/me/training-preferences",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload == {
        "voice_mode": None,
        "agent_id": None,
        "persona_id": None,
        "presentation_id": None,
        "updated_at": None,
    }


@pytest.mark.asyncio
async def test_patch_training_preferences_upserts_current_user_only(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    response = await async_client.patch(
        "/api/v1/users/me/training-preferences",
        headers=auth_headers,
        json={
            "voice_mode": "legacy",
            "agent_id": " agent-1 ",
            "persona_id": "persona-1",
            "presentation_id": "",
            "updated_at": "2020-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["voice_mode"] == "legacy"
    assert payload["agent_id"] == "agent-1"
    assert payload["persona_id"] == "persona-1"
    assert payload["presentation_id"] is None
    assert payload["updated_at"] != "2020-01-01T00:00:00Z"

    saved = await test_db.get(UserTrainingPreference, str(test_user.user_id))
    assert saved is not None
    assert saved.voice_mode == "legacy"
    assert saved.agent_id == "agent-1"
    assert saved.persona_id == "persona-1"
    assert saved.presentation_id is None


@pytest.mark.asyncio
async def test_patch_training_preferences_rejects_user_id_and_invalid_voice_mode(
    async_client: AsyncClient,
    auth_headers: dict,
):
    user_id_response = await async_client.patch(
        "/api/v1/users/me/training-preferences",
        headers=auth_headers,
        json={"user_id": "other-user", "voice_mode": "legacy"},
    )
    assert user_id_response.status_code == 422

    voice_mode_response = await async_client.patch(
        "/api/v1/users/me/training-preferences",
        headers=auth_headers,
        json={"voice_mode": "unsupported"},
    )
    assert voice_mode_response.status_code == 422


@pytest.mark.asyncio
async def test_training_preferences_are_scoped_to_authenticated_user(
    async_client: AsyncClient,
    test_db: AsyncSession,
    another_user: User,
    auth_headers: dict,
):
    test_db.add(
        UserTrainingPreference(
            user_id=str(another_user.user_id),
            voice_mode="legacy",
            agent_id="other-agent",
            persona_id="other-persona",
            presentation_id="other-ppt",
        )
    )
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/users/me/training-preferences",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["agent_id"] is None
    assert payload["persona_id"] is None
    assert payload["presentation_id"] is None
