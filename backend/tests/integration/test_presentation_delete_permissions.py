"""
Integration tests for presentation delete permission boundaries.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import Page, Presentation, User


async def _create_user(test_db: AsyncSession, *, role: str, name: str) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"ppt_delete_{uuid.uuid4().hex[:10]}",
        name=name,
        department="QA",
        email=f"{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}@example.com",
        role=role,
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_presentation_enforces_admin_only(
    async_client,
    test_db: AsyncSession,
) -> None:
    uploader = await _create_user(test_db, role="user", name="Uploader")
    other_user = await _create_user(test_db, role="user", name="Other User")
    admin_user = await _create_user(test_db, role="admin", name="Admin User")

    presentation_for_uploader = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="Uploader Deck",
        file_url="/tmp/uploader.pptx",
        status="ready",
        uploaded_by_admin_id=uploader.user_id,
        total_pages=1,
    )
    presentation_for_admin = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="Admin Deck",
        file_url="/tmp/admin.pptx",
        status="ready",
        uploaded_by_admin_id=uploader.user_id,
        total_pages=1,
    )
    test_db.add_all([presentation_for_uploader, presentation_for_admin])
    await test_db.commit()

    forbidden_response = await async_client.delete(
        f"/api/v1/presentations/{presentation_for_uploader.presentation_id}",
        headers=_auth_headers(other_user),
    )
    assert forbidden_response.status_code == 403

    still_exists = (
        await test_db.execute(
            select(Presentation).where(
                Presentation.presentation_id
                == presentation_for_uploader.presentation_id
            )
        )
    ).scalar_one_or_none()
    assert still_exists is not None

    owner_delete_response = await async_client.delete(
        f"/api/v1/presentations/{presentation_for_uploader.presentation_id}",
        headers=_auth_headers(uploader),
    )
    assert owner_delete_response.status_code == 403

    admin_delete_response = await async_client.delete(
        f"/api/v1/presentations/{presentation_for_admin.presentation_id}",
        headers=_auth_headers(admin_user),
    )
    assert admin_delete_response.status_code == 204

    deleted_owner_record = (
        await test_db.execute(
            select(Presentation).where(
                Presentation.presentation_id
                == presentation_for_uploader.presentation_id
            )
        )
    ).scalar_one_or_none()
    deleted_admin_record = (
        await test_db.execute(
            select(Presentation).where(
                Presentation.presentation_id == presentation_for_admin.presentation_id
            )
        )
    ).scalar_one_or_none()
    assert deleted_owner_record is not None
    assert deleted_admin_record is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_presentation_governance_writes_require_admin(
    async_client,
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(test_db, role="user", name="Learner User")
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="Governed Deck",
        file_url="/tmp/governed.pptx",
        status="ready",
        uploaded_by_admin_id=learner.user_id,
        total_pages=1,
    )
    page = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=1,
        ocr_extracted_text="Page text",
    )
    test_db.add_all([presentation, page])
    await test_db.commit()

    talking_point_response = await async_client.post(
        f"/api/v1/presentations/{presentation.presentation_id}/pages/1/talking-points",
        headers=_auth_headers(learner),
        json={"description": "Cover the core value proposition."},
    )
    assert talking_point_response.status_code == 403

    forbidden_word_response = await async_client.post(
        f"/api/v1/presentations/{presentation.presentation_id}/forbidden-words",
        headers=_auth_headers(learner),
        json={"phrase": "maybe", "suggested_alternative": "specifically"},
    )
    assert forbidden_word_response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_presentation_upload_rejects_disguised_file_for_admin(
    async_client,
    test_db: AsyncSession,
) -> None:
    admin_user = await _create_user(test_db, role="admin", name="Upload Admin")

    response = await async_client.post(
        "/api/v1/presentations",
        headers=_auth_headers(admin_user),
        data={"title": "Disguised PPT"},
        files={
            "file": (
                "disguised.pptx",
                b"not a zip payload",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )

    assert response.status_code == 400
    assert "PPTX" in response.text
