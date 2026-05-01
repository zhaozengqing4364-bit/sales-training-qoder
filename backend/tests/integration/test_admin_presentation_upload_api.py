from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token


def _admin_headers(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_presentation_upload_rejects_traversal_filename(
    async_client,
    test_db: AsyncSession,
    test_user,
    monkeypatch,
    tmp_path,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _admin_headers(str(test_user.user_id))
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("PPT_UPLOAD_DIR", str(upload_dir))

    response = await async_client.post(
        "/api/v1/admin/presentations/upload",
        headers=headers,
        data={"title": "Traversal attempt"},
        files={
            "file": (
                "../evil.pptx",
                b"PK\x03\x04",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )

    assert response.status_code == 400
    assert "traversal" in response.json()["detail"].lower()
    assert not upload_dir.exists() or list(upload_dir.rglob("*")) == []
