from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerOperationLog,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    NewcomerPathConfigSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.material_service import (
    MaterialServiceError,
    SalesTrainerMaterialService,
)
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


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


def _published_prompt(admin: User) -> SalesTrainerAudioScorePrompt:
    return SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="材料文件访问评分方案",
        purpose="ppt_pitch",
        system_prompt="你是销售训练评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )


def _audio_unit(
    admin: User,
    *,
    prompt_id: str,
    title: str,
    purpose: str = "ppt_pitch",
) -> SalesTrainerUnit:
    return SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name=title,
        description=f"{title}说明",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": prompt_id,
                "pass_threshold": 80,
                "purpose": purpose,
            }
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )


def _material_with_version(
    admin: User,
    *,
    storage_root: Path,
    key_prefix: str,
    body: bytes,
    status: str = "published",
    purpose: str = "ppt_pitch",
) -> tuple[SalesTrainerMaterial, SalesTrainerMaterialVersion]:
    stored_path = storage_root / f"{key_prefix}-{uuid.uuid4().hex[:8]}.pdf"
    stored_path.write_bytes(body)
    material = SalesTrainerMaterial(
        material_id=str(uuid.uuid4()),
        material_key=f"{key_prefix}-{uuid.uuid4().hex[:8]}",
        name=f"{key_prefix} 材料",
        material_type="attachment",
        purpose=purpose,
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    version = SalesTrainerMaterialVersion(
        version_id=str(uuid.uuid4()),
        material_id=material.material_id,
        version_label=f"{key_prefix}-v1",
        title=f"{key_prefix} v1",
        file_name=f"{key_prefix}.pdf",
        content_type="application/pdf",
        file_size_bytes=len(body),
        storage_key=str(stored_path),
        status=status,
        created_by=admin.user_id,
        published_by=admin.user_id if status == "published" else None,
    )
    if status == "published":
        material.current_version_id = version.version_id
    return material, version


async def _publish_audio_material_path(
    test_db: AsyncSession,
    *,
    admin: User,
    first_unit: SalesTrainerUnit,
    first_material: SalesTrainerMaterial,
    first_version: SalesTrainerMaterialVersion,
    second_unit: SalesTrainerUnit,
    second_material: SalesTrainerMaterial,
    second_version: SalesTrainerMaterialVersion,
) -> str:
    service = SalesTrainerPathConfigService(test_db)
    await service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="材料文件访问授权测试",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="ppt_explanation",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=1,
                    title="PPT 讲解",
                    description="第一阶段材料",
                    target_unit_id=first_unit.unit_id,
                    material_id=first_material.material_id,
                    material_version_id=first_version.version_id,
                    completion_rule="scored",
                ),
                NewcomerPathModuleConfig(
                    module_key="company_product_demo",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=2,
                    title="公司产品 Demo",
                    description="第二阶段材料",
                    target_unit_id=second_unit.unit_id,
                    material_id=second_material.material_id,
                    material_version_id=second_version.version_id,
                    unlock_after_unit_ids=[first_unit.unit_id],
                    completion_rule="passed",
                ),
            ],
        ),
        actor=admin,
    )
    result = await service.publish_config(actor=admin, reason="材料文件访问路径生效")
    return str(result.revision.revision_id)


async def _seed_passed_audio_evidence(
    test_db: AsyncSession,
    *,
    learner: User,
    prompt: SalesTrainerAudioScorePrompt,
    unit: SalesTrainerUnit,
    revision_id: str,
) -> None:
    submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="material-prerequisite.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/material-prerequisite.wav",
        task_brief_snapshot={
            "submission_context": {
                "path_key": "newcomer_training_path_v1",
                "path_revision_id": revision_id,
                "path_revision_no": 1,
                "module_key": "ppt_explanation",
                "legacy_snapshot_only": False,
            }
        },
        status="scored",
    )
    score = SalesTrainerAudioScoreResult(
        score_id=str(uuid.uuid4()),
        submission_id=submission.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="material-prerequisite-hash",
        total_score=88,
        passed=True,
        strengths=[],
        improvements=[],
        dimension_scores={},
    )
    test_db.add_all([submission, score])
    await test_db.commit()


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
async def test_should_preview_and_rollback_material_version_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()

    create_response = await async_client.post(
        "/api/v1/admin/sales-trainer/materials",
        headers=_auth_headers(admin),
        json={
            "material_key": f"rollback_deck_api_{uuid.uuid4().hex[:8]}",
            "name": "可回滚材料",
            "material_type": "ppt_deck",
            "description": "用于版本回滚",
            "purpose": "ppt_pitch",
        },
    )
    assert create_response.status_code == 200
    material_id = create_response.json()["data"]["material_id"]

    first_version_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/{material_id}/versions",
        headers=_auth_headers(admin),
        json={
            "version_label": "v1",
            "title": "第一版材料",
            "file_name": "deck-v1.pptx",
            "content_type": (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
            "file_size_bytes": 128,
            "storage_key": "/tmp/deck-v1.pptx",
        },
    )
    assert first_version_response.status_code == 200
    first_version_id = first_version_response.json()["data"]["version_id"]
    first_publish = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/versions/{first_version_id}/publish",
        headers=_auth_headers(admin),
    )
    assert first_publish.status_code == 200

    second_version_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/{material_id}/versions",
        headers=_auth_headers(admin),
        json={
            "version_label": "v2",
            "title": "第二版材料",
            "file_name": "deck-v2.pptx",
            "content_type": (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
            "file_size_bytes": 256,
            "storage_key": "/tmp/deck-v2.pptx",
        },
    )
    assert second_version_response.status_code == 200
    second_version_id = second_version_response.json()["data"]["version_id"]
    second_publish = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/versions/{second_version_id}/publish",
        headers=_auth_headers(admin),
    )
    assert second_publish.status_code == 200

    denied_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/{material_id}/versions/rollback/preview",
        headers=_auth_headers(learner),
        json={"target_version_id": first_version_id},
    )
    assert denied_response.status_code == 403

    preview_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/{material_id}/versions/rollback/preview",
        headers=_auth_headers(admin),
        json={"target_version_id": first_version_id},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["action"] == "material_version.rollback"
    assert preview["permission"] == "sales_trainer.manage_modules"
    assert preview["requires_reason"] is True
    assert preview["future_only"] is True
    assert preview["mutates_history"] is False
    assert preview["target_version"]["version_id"] == first_version_id
    assert preview["future_material_current_version_changed"] is True
    assert preview["historical_submissions_changed"] is False
    assert preview["historical_replay_preserved"] is True

    material_after_preview = await test_db.get(SalesTrainerMaterial, material_id)
    assert material_after_preview is not None
    assert material_after_preview.current_version_id == second_version_id

    rollback_response = await async_client.post(
        f"/api/v1/admin/sales-trainer/materials/{material_id}/versions/rollback",
        headers=_auth_headers(admin),
        json={
            "target_version_id": first_version_id,
            "reason": "回滚到第一版材料",
        },
    )
    assert rollback_response.status_code == 200
    rollback_trace_id = rollback_response.json()["trace_id"]
    rolled_back = rollback_response.json()["data"]
    assert rolled_back["version_id"] == first_version_id
    assert rolled_back["status"] == "published"

    material = await test_db.get(SalesTrainerMaterial, material_id)
    first_version = await test_db.get(SalesTrainerMaterialVersion, first_version_id)
    second_version = await test_db.get(SalesTrainerMaterialVersion, second_version_id)
    assert material is not None
    assert first_version is not None
    assert second_version is not None
    await test_db.refresh(material)
    await test_db.refresh(first_version)
    await test_db.refresh(second_version)
    assert material.current_version_id == first_version_id
    assert first_version.status == "published"
    assert second_version.status == "archived"

    logs = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.target_type == "sales_trainer_material_version",
            SalesTrainerOperationLog.target_id == first_version_id,
            SalesTrainerOperationLog.action == "material_version_rolled_back",
        )
    )
    rollback_log = logs.scalar_one()
    assert rollback_log.request_id == rollback_trace_id
    assert rollback_log.metadata_json["trace_id"] == rollback_trace_id
    assert rollback_log.metadata_json["before_version_id"] == second_version_id
    assert rollback_log.metadata_json["after_version_id"] == first_version_id
    assert rollback_log.metadata_json["future_only"] is True
    assert rollback_log.metadata_json["historical_submissions_changed"] is False
    assert rollback_log.metadata_json["historical_replay_preserved"] is True


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_unlock_dependent_material_only_with_active_revision_evidence(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SALES_TRAINER_MATERIAL_STORAGE_PATH", str(tmp_path))

    admin = _user("admin")
    learner = _user("user")
    prompt = _published_prompt(admin)
    first_unit = _audio_unit(admin, prompt_id=prompt.prompt_id, title="PPT 讲解")
    second_unit = _audio_unit(
        admin,
        prompt_id=prompt.prompt_id,
        title="公司产品 Demo",
        purpose="company_product_demo",
    )
    first_material, first_version = _material_with_version(
        admin,
        storage_root=tmp_path,
        key_prefix="prerequisite-material",
        body=b"prerequisite-material",
    )
    dependent_material, dependent_version = _material_with_version(
        admin,
        storage_root=tmp_path,
        key_prefix="dependent-material",
        body=b"dependent-material",
        purpose="company_product_demo",
    )
    test_db.add_all(
        [
            admin,
            learner,
            prompt,
            first_unit,
            second_unit,
            first_material,
            first_version,
            dependent_material,
            dependent_version,
        ]
    )
    await test_db.commit()
    active_revision_id = await _publish_audio_material_path(
        test_db,
        admin=admin,
        first_unit=first_unit,
        first_material=first_material,
        first_version=first_version,
        second_unit=second_unit,
        second_material=dependent_material,
        second_version=dependent_version,
    )

    locked = await async_client.get(
        f"/api/v1/sales-trainer/materials/versions/{dependent_version.version_id}/file",
        headers=_auth_headers(learner),
    )
    assert locked.status_code == 404
    assert locked.json()["error"] == "[MATERIAL_FILE_NOT_FOUND]"

    await _seed_passed_audio_evidence(
        test_db,
        learner=learner,
        prompt=prompt,
        unit=first_unit,
        revision_id="old-path-revision",
    )
    stale_evidence = await async_client.get(
        f"/api/v1/sales-trainer/materials/versions/{dependent_version.version_id}/file",
        headers=_auth_headers(learner),
    )
    assert stale_evidence.status_code == 404
    assert stale_evidence.json()["error"] == "[MATERIAL_FILE_NOT_FOUND]"

    await _seed_passed_audio_evidence(
        test_db,
        learner=learner,
        prompt=prompt,
        unit=first_unit,
        revision_id=active_revision_id,
    )
    unlocked = await async_client.get(
        f"/api/v1/sales-trainer/materials/versions/{dependent_version.version_id}/file",
        headers=_auth_headers(learner),
    )
    assert unlocked.status_code == 200
    assert unlocked.content == b"dependent-material"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_should_enforce_object_scope_for_material_file_download(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SALES_TRAINER_MATERIAL_STORAGE_PATH", str(tmp_path))

    admin = _user("admin")
    learner = _user("user")
    manager = _user("support")
    manager.department = "华东销售"
    content_admin = _user("content_admin")
    ops_user = _user("operations")
    prompt = _published_prompt(admin)
    first_unit = _audio_unit(admin, prompt_id=prompt.prompt_id, title="PPT 讲解")
    second_unit = _audio_unit(
        admin,
        prompt_id=prompt.prompt_id,
        title="公司产品 Demo",
        purpose="company_product_demo",
    )
    bound_material, bound_version = _material_with_version(
        admin,
        storage_root=tmp_path,
        key_prefix="bound-material",
        body=b"bound-material",
    )
    locked_material, locked_version = _material_with_version(
        admin,
        storage_root=tmp_path,
        key_prefix="locked-material",
        body=b"locked-material",
        purpose="company_product_demo",
    )
    extra_material, extra_version = _material_with_version(
        admin,
        storage_root=tmp_path,
        key_prefix="extra-material",
        body=b"extra-material",
    )
    draft_material, draft_version = _material_with_version(
        admin,
        storage_root=tmp_path,
        key_prefix="draft-material",
        body=b"draft-material",
        status="draft",
    )
    test_db.add_all(
        [
            admin,
            learner,
            manager,
            content_admin,
            ops_user,
            prompt,
            first_unit,
            second_unit,
            bound_material,
            bound_version,
            locked_material,
            locked_version,
            extra_material,
            extra_version,
            draft_material,
            draft_version,
        ]
    )
    await test_db.commit()
    await _publish_audio_material_path(
        test_db,
        admin=admin,
        first_unit=first_unit,
        first_material=bound_material,
        first_version=bound_version,
        second_unit=second_unit,
        second_material=locked_material,
        second_version=locked_version,
    )

    learner_allowed = await async_client.get(
        f"/api/v1/sales-trainer/materials/versions/{bound_version.version_id}/file",
        headers=_auth_headers(learner),
    )
    assert learner_allowed.status_code == 200
    assert learner_allowed.content == b"bound-material"

    learner_locked = await async_client.get(
        f"/api/v1/sales-trainer/materials/versions/{locked_version.version_id}/file",
        headers=_auth_headers(learner),
    )
    assert learner_locked.status_code == 404
    assert learner_locked.json()["error"] == "[MATERIAL_FILE_NOT_FOUND]"

    learner_unbound = await async_client.get(
        f"/api/v1/sales-trainer/materials/versions/{extra_version.version_id}/file",
        headers=_auth_headers(learner),
    )
    assert learner_unbound.status_code == 404
    assert learner_unbound.json()["error"] == "[MATERIAL_FILE_NOT_FOUND]"

    manager_forbidden = await async_client.get(
        f"/api/v1/sales-trainer/materials/versions/{bound_version.version_id}/file",
        headers=_auth_headers(manager),
    )
    assert manager_forbidden.status_code == 403
    manager_error = str(manager_forbidden.json()["error"])
    assert "PERMISSION_DENIED" in manager_error or "ROLE_REQUIRED" in manager_error

    content_admin_allowed = await async_client.get(
        f"/api/v1/admin/sales-trainer/materials/versions/{extra_version.version_id}/file",
        headers=_auth_headers(content_admin),
    )
    assert content_admin_allowed.status_code == 200
    assert content_admin_allowed.content == b"extra-material"

    ops_allowed = await async_client.get(
        f"/api/v1/admin/sales-trainer/materials/versions/{locked_version.version_id}/file",
        headers=_auth_headers(ops_user),
    )
    assert ops_allowed.status_code == 200
    assert ops_allowed.content == b"locked-material"

    draft_denied = await async_client.get(
        f"/api/v1/admin/sales-trainer/materials/versions/{draft_version.version_id}/file",
        headers=_auth_headers(content_admin),
    )
    assert draft_denied.status_code == 404
    assert draft_denied.json()["error"] == "[MATERIAL_VERSION_NOT_PUBLISHED]"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_platform_admin_public_material_route_permission_baseline(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
    tmp_path: Path,
) -> None:
    """Keep the pre-existing admin/learner-route decision visible and isolated."""

    monkeypatch.setenv("SALES_TRAINER_MATERIAL_STORAGE_PATH", str(tmp_path))
    admin = _user("admin")
    prompt = _published_prompt(admin)
    unit = _audio_unit(admin, prompt_id=prompt.prompt_id, title="PPT 讲解")
    material, version = _material_with_version(
        admin,
        storage_root=tmp_path,
        key_prefix="admin-public-route",
        body=b"admin-public-route",
    )
    test_db.add_all([admin, prompt, unit, material, version])
    await test_db.commit()

    service = SalesTrainerPathConfigService(test_db)
    await service.save_config(
        NewcomerPathConfigSaveRequest(
            title="新人训练路径",
            reason="隔离平台管理员 learner 路由权限基线",
            modules=[
                NewcomerPathModuleConfig(
                    module_key="ppt_explanation",
                    module_type="audio_scoring",
                    enabled=True,
                    order_index=1,
                    title="PPT 讲解",
                    target_unit_id=unit.unit_id,
                    material_id=material.material_id,
                    material_version_id=version.version_id,
                    completion_rule="scored",
                )
            ],
        ),
        actor=admin,
    )
    await service.publish_config(actor=admin, reason="管理员权限基线路径生效")

    response = await async_client.get(
        f"/api/v1/sales-trainer/materials/versions/{version.version_id}/file",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 403
    assert response.json()["error"] == "[NEWCOMER_LEARNER_ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_should_replay_archived_material_version_from_training_record(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_db: AsyncSession,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SALES_TRAINER_MATERIAL_STORAGE_PATH", str(tmp_path))

    admin = _user("admin")
    learner = _user("user")
    learner.department = "华东销售"
    manager = _user("support")
    manager.department = "华东销售"
    outside_manager = _user("support")
    outside_manager.department = "华南销售"
    material, version = _material_with_version(
        admin,
        storage_root=tmp_path,
        key_prefix="archived-history-material",
        body=b"archived-history-material",
    )
    version.status = "archived"
    submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="history.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key=str(tmp_path / "history.wav"),
        status="uploaded",
        confirmed_material_version_id=version.version_id,
        material_snapshot={
            "version": 1,
            "confirmed_material_version_id": version.version_id,
        },
    )
    test_db.add_all(
        [admin, learner, manager, outside_manager, material, version, submission]
    )
    await test_db.commit()

    normal_admin_route = await async_client.get(
        f"/api/v1/admin/sales-trainer/materials/versions/{version.version_id}/file",
        headers=_auth_headers(admin),
    )
    history_route = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records/detail/"
        f"audio_submission/{submission.submission_id}/materials/{version.version_id}/file",
        headers=_auth_headers(manager),
    )
    outside_scope = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records/detail/"
        f"audio_submission/{submission.submission_id}/materials/{version.version_id}/file",
        headers=_auth_headers(outside_manager),
    )
    wrong_version = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records/detail/"
        f"audio_submission/{submission.submission_id}/materials/{uuid.uuid4()}/file",
        headers=_auth_headers(manager),
    )

    assert normal_admin_route.status_code == 404
    assert normal_admin_route.json()["error"] == "[MATERIAL_VERSION_NOT_PUBLISHED]"
    assert history_route.status_code == 200
    assert history_route.content == b"archived-history-material"
    assert outside_scope.status_code == 404
    assert outside_scope.json()["error"] == "[TRAINING_RECORD_NOT_FOUND]"
    assert wrong_version.status_code == 404
    assert wrong_version.json()["error"] == "[MATERIAL_VERSION_NOT_PUBLISHED]"

    service = SalesTrainerMaterialService(test_db)
    same_scope_access = await service.resolve_historical_file_access(
        version.version_id,
        record_type="audio_submission",
        record_id=submission.submission_id,
        viewer=manager,
        team_department=manager.department,
    )
    assert same_scope_access.filename == version.file_name
    with pytest.raises(MaterialServiceError) as denied:
        await service.resolve_historical_file_access(
            version.version_id,
            record_type="audio_submission",
            record_id=submission.submission_id,
            viewer=outside_manager,
            team_department=outside_manager.department,
        )
    assert denied.value.code == "[TRAINING_RECORD_NOT_FOUND]"

    with pytest.raises(MaterialServiceError) as unsupported:
        await service.resolve_historical_file_access(
            version.version_id,
            record_type="quiz_attempt",
            record_id=submission.submission_id,
            viewer=manager,
            team_department=manager.department,
        )
    assert unsupported.value.code == "[TRAINING_RECORD_MATERIAL_REPLAY_UNSUPPORTED]"
    assert unsupported.value.status_code == 400


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
