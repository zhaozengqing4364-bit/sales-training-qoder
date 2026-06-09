from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import SalesTrainerOperationLog


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str = "admin") -> User:
    suffix = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-material-api-{role}-{suffix}",
        name=f"Newcomer Material API {role}",
        email=f"newcomer-material-api-{role}-{suffix}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_should_audit_published_material_metadata_update_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/materials",
        headers=_auth_headers(admin),
        json={
            "material_key": f"company_deck_api_{uuid.uuid4().hex[:8]}",
            "name": "旧版材料",
            "material_type": "ppt_deck",
            "description": "旧说明",
            "purpose": "ppt_pitch",
        },
    )
    assert create_response.status_code == 200
    material_id = create_response.json()["data"]["material_id"]

    version_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/{material_id}/versions",
        headers=_auth_headers(admin),
        json={
            "version_label": "v2026.06",
            "title": "主胶片 v2026.06",
            "file_name": "deck-api.pptx",
            "content_type": (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
            "file_size_bytes": 128,
            "storage_key": "/tmp/deck-api.pptx",
        },
    )
    assert version_response.status_code == 200
    version_id = version_response.json()["data"]["version_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/versions/{version_id}/publish",
        headers=_auth_headers(admin),
    )
    assert publish_response.status_code == 200

    update_response = await async_client.put(
        f"/api/v1/admin/sales-trainer/materials/{material_id}",
        headers=_auth_headers(admin),
        json={
            "name": "新版材料",
            "description": "新版说明",
            "purpose": "elevator_pitch",
        },
    )
    assert update_response.status_code == 200
    update_trace_id = update_response.json()["trace_id"]
    data = update_response.json()["data"]
    assert data["status"] == "published"
    assert data["name"] == "新版材料"

    audit_log = await _latest_material_log(test_db, material_id)
    assert audit_log.request_id == update_trace_id
    assert audit_log.metadata_json["trace_id"] == update_trace_id
    assert audit_log.metadata_json["future_only"] is True
    assert audit_log.metadata_json["impact_scope"] == "future_submissions_only"
    assert audit_log.metadata_json["changed_fields"] == [
        "name",
        "description",
        "purpose",
    ]
    assert audit_log.metadata_json["before"]["name"] == "旧版材料"
    assert audit_log.metadata_json["after"]["name"] == "新版材料"


@pytest.mark.asyncio
async def test_should_upload_material_file_and_create_draft_version_via_api(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
    tmp_path: Path,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    monkeypatch.setenv("SALES_TRAINER_MATERIAL_STORAGE_PATH", str(tmp_path))

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/materials",
        headers=_auth_headers(admin),
        json={
            "material_key": f"company_upload_api_{uuid.uuid4().hex[:8]}",
            "name": "上传材料",
            "material_type": "ppt_deck",
            "purpose": "ppt_pitch",
        },
    )
    assert create_response.status_code == 200
    material_id = create_response.json()["data"]["material_id"]

    upload_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/{material_id}/versions/upload",
        headers=_auth_headers(admin),
        data={
            "version_label": "v2026.06-upload",
            "title": "上传材料 2026-06",
            "release_notes": "首次上传",
        },
        files={
            "file": (
                "company-upload.pptx",
                b"pptx-bytes",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
        },
    )

    assert upload_response.status_code == 200
    data = upload_response.json()["data"]
    assert data["status"] == "draft"
    assert data["file_name"] == "company-upload.pptx"
    assert data["file_size_bytes"] == len(b"pptx-bytes")
    assert data["file_hash"] is not None

    stored_path = Path(data["storage_key"])
    assert stored_path.exists()
    assert tmp_path.resolve() in (stored_path.resolve(), *stored_path.resolve().parents)
    assert stored_path.read_bytes() == b"pptx-bytes"

    upload_log = await _latest_version_upload_log(test_db, data["version_id"])
    assert upload_log.metadata_json["material_id"] == material_id
    assert upload_log.metadata_json["file_name"] == "company-upload.pptx"
    assert upload_log.metadata_json["file_size_bytes"] == len(b"pptx-bytes")


async def _latest_material_log(
    test_db: AsyncSession,
    material_id: str,
) -> SalesTrainerOperationLog:
    result = await test_db.execute(
        select(SalesTrainerOperationLog)
        .where(
            SalesTrainerOperationLog.target_type == "sales_trainer_material",
            SalesTrainerOperationLog.target_id == material_id,
            SalesTrainerOperationLog.action == "material_metadata_updated",
        )
        .order_by(SalesTrainerOperationLog.created_at.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _latest_version_upload_log(
    test_db: AsyncSession,
    version_id: str,
) -> SalesTrainerOperationLog:
    result = await test_db.execute(
        select(SalesTrainerOperationLog)
        .where(
            SalesTrainerOperationLog.target_type == "sales_trainer_material_version",
            SalesTrainerOperationLog.target_id == version_id,
            SalesTrainerOperationLog.action == "material_version_uploaded",
        )
        .order_by(SalesTrainerOperationLog.created_at.desc())
        .limit(1)
    )
    return result.scalar_one()
