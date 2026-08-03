from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from common.db.models import User
from common.db.session import get_db
from common.storage import DocumentStorageService
from common.teams import TeamDataScope
from foundation_admin_api import (
    get_foundation_admin_actors,
    get_foundation_admin_scope,
    get_foundation_task_registry,
    router,
)
from foundation_admin_permissions import FoundationAdminActors
from learning.application import LearningGovernanceService
from learning.contracts import LearningActor
from learning.models import LearningSourceDocumentRevision
from learning.task_definitions import register_learning_task_definitions
from newcomer_training.application import CommandActor
from newcomer_training.models import (
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)
from task_runtime.models import (
    DurableTask,
    TaskOperatorScopeGrant,
    TaskPayloadArtifact,
)
from task_runtime.registry import TaskRegistry


def _actors(*, allowed: bool = True) -> FoundationAdminActors:
    newcomer = (
        {
            "newcomer.path.manage",
            "newcomer.path.publish",
            "newcomer.cohort.manage",
            "newcomer.enrollment.manage",
            "newcomer.enrollment.migrate",
            "newcomer.activity.invalidate",
        }
        if allowed
        else set()
    )
    learning = (
        {
            "learning.source.manage",
            "learning.content.manage",
            "learning.question.generate",
            "learning.question.manage",
            "learning.question.review",
            "learning.question.publish",
            "learning.question.risk_review",
            "learning.quiz.manage",
            "learning.lesson.invalidate",
        }
        if allowed
        else set()
    )
    return FoundationAdminActors(
        newcomer=CommandActor(
            organization_id="org-1",
            actor_id="admin-1",
            capabilities=frozenset(newcomer),
        ),
        learning=LearningActor(
            organization_id="org-1",
            actor_id="admin-1",
            capabilities=frozenset(learning),
        ),
        capabilities=(
            frozenset(
                {
                    "view_overview",
                    "edit_paths",
                    "edit_content",
                    "review_questions",
                    "manage_cohorts",
                    "retry_assessments",
                    "regrade_results",
                    "review_readiness",
                    "publish_releases",
                    "govern_ai",
                    "view_sensitive_audit",
                }
            )
            if allowed
            else frozenset()
        ),
    )


async def _client(
    test_db,
    *,
    allowed: bool = True,
    registry: TaskRegistry | None = None,
    scope: TeamDataScope | None = None,
) -> AsyncClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_foundation_admin_actors] = lambda: _actors(
        allowed=allowed
    )
    app.dependency_overrides[get_foundation_admin_scope] = lambda: (
        scope or TeamDataScope.unrestricted_scope()
    )
    if registry is not None:
        app.dependency_overrides[get_foundation_task_registry] = lambda: registry
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


def _source_payload() -> dict[str, object]:
    return {
        "resource_type": "source_document",
        "stable_key": "foundation-handbook",
        "title": "新人销售基础手册",
        "working_revision": {
            "revision_label": "2026.07",
            "source_type": "file",
            "source_uri": "artifact://learning/foundation-handbook-v1",
            "file_hash": "a" * 64,
            "parser_version": "parser-v1",
            "parse_status": "ready",
        },
    }


def _journey_snapshot() -> dict[str, object]:
    return {
        "contract_version": "newcomer_training_path_v2",
        "title": "新人销售基础训练",
        "revision_label": "首发版",
        "stages": [
            {
                "stage_id": "stage-foundation",
                "sequence": 1,
                "title": "产品基础",
                "objective": "建立产品知识",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "lesson-foundation",
                        "type": "lesson",
                        "title": "学习产品知识",
                        "objective": "理解产品价值",
                        "why_it_matters": "支持客户沟通",
                        "steps": ["学习", "完成检查点"],
                        "success_criteria": ["完成全部检查点"],
                        "estimated_minutes": 20,
                        "required": True,
                        "prerequisite_activity_ids": [],
                        "ai_dependency": "none",
                        "retry_policy": {
                            "max_attempts": 0,
                            "retry_interval_seconds": 0,
                        },
                        "config": {
                            "learning_unit_revision_id": "learning-revision-1",
                            "required_checkpoint_ids": ["checkpoint-1"],
                        },
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_source_upload_creates_pending_revision_and_durable_parse_task(
    test_db,
    monkeypatch,
    tmp_path,
) -> None:
    storage = DocumentStorageService(str(tmp_path))
    monkeypatch.setattr(
        "foundation_admin_api.get_document_storage_service",
        lambda: storage,
    )
    registry = TaskRegistry()
    register_learning_task_definitions(registry)
    request = {
        "headers": {"Idempotency-Key": "upload-source-one"},
        "data": {
            "stable_key": "uploaded-handbook",
            "title": "新人销售基础手册",
            "revision_label": "首发材料",
        },
        "files": {
            "file": (
                "foundation-handbook.txt",
                "新人销售训练材料正文，包含产品价值和客户沟通要点。".encode(),
                "text/plain",
            )
        },
    }
    async with await _client(test_db, registry=registry) as client:
        first = await client.post(
            "/api/v1/admin/newcomer-training/resources/source_document/uploads",
            **request,
        )
        replay = await client.post(
            "/api/v1/admin/newcomer-training/resources/source_document/uploads",
            **request,
        )

    assert first.status_code == 200
    assert replay.status_code == 200
    first_data = first.json()["data"]
    replay_data = replay.json()["data"]
    assert first_data["working_revision"]["parse_status"] == "pending"
    assert first_data["task"]["state"] == "queued"
    assert first_data["task"]["task_id"] == replay_data["task"]["task_id"]
    revision = await test_db.get(
        LearningSourceDocumentRevision,
        first_data["working_revision"]["revision_id"],
    )
    task = await test_db.get(DurableTask, first_data["task"]["task_id"])
    assert revision is not None and revision.source_uri.startswith(
        "artifact://learning/source/"
    )
    assert task is not None
    assert task.task_type == "learning.source_document.parse"
    assert task.resource_type == "source_document_revision"


@pytest.mark.asyncio
async def test_direct_path_publish_is_a_release_plan_tombstone(test_db) -> None:
    async with await _client(test_db) as client:
        response = await client.post(
            "/api/v1/admin/newcomer-training/path-revisions/working-revision/commands/publish",
            headers={"Idempotency-Key": "direct-path-publish", "If-Match": 'W/"1"'},
            json={"reason": "不得绕过发布计划"},
        )

    assert response.status_code == 409
    assert response.json()["error"] == "[NEWCOMER_RELEASE_PLAN_REQUIRED]"


@pytest.mark.asyncio
async def test_resource_command_is_transactional_idempotent_and_etag_guarded(
    test_db,
) -> None:
    async with await _client(test_db) as client:
        first = await client.post(
            "/api/v1/admin/newcomer-training/resources/source_document",
            headers={"Idempotency-Key": "create-source"},
            json=_source_payload(),
        )
        replay = await client.post(
            "/api/v1/admin/newcomer-training/resources/source_document",
            headers={"Idempotency-Key": "create-source"},
            json=_source_payload(),
        )

        assert first.status_code == 200
        assert replay.status_code == 200
        assert first.json()["data"]["resource"]["document_id"] == (
            replay.json()["data"]["resource"]["document_id"]
        )
        assert first.headers["etag"] == 'W/"2"'
        document_id = first.json()["data"]["resource"]["document_id"]

        stale = await client.put(
            f"/api/v1/admin/newcomer-training/resources/source_document/{document_id}/working-revision",
            headers={
                "Idempotency-Key": "save-source-v2",
                "If-Match": 'W/"1"',
            },
            json={
                "resource_type": "source_document",
                "working_revision": {
                    **_source_payload()["working_revision"],
                    "revision_label": "2026.08",
                },
            },
        )

    assert stale.status_code == 412
    assert stale.json()["error"] == "[LEARNING_VERSION_CONFLICT]"
    assert stale.json()["details"] == {
        "expected_version": 1,
        "actual_version": 2,
    }


@pytest.mark.asyncio
async def test_admin_write_permission_fails_closed_without_mutation(test_db) -> None:
    async with await _client(test_db, allowed=False) as client:
        response = await client.post(
            "/api/v1/admin/newcomer-training/resources/source_document",
            headers={"Idempotency-Key": "forbidden-source"},
            json=_source_payload(),
        )

    assert response.status_code == 403
    assert response.json()["error"] == "[LEARNING_PERMISSION_DENIED]"


@pytest.mark.asyncio
async def test_enrollment_import_resolves_email_template_and_reports_missing_rows(
    test_db,
) -> None:
    now = datetime.now(UTC)
    path = NewcomerPath(
        path_id="path-email-import",
        organization_id="org-1",
        stable_key="email-import-path",
        title="新人销售基础训练",
        status="active",
        published_revision_id="revision-email-import",
        version=1,
        creation_idempotency_key_hash="a" * 64,
        creation_fingerprint="b" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    revision = NewcomerPathRevision(
        revision_id="revision-email-import",
        path_id=path.path_id,
        organization_id="org-1",
        revision_no=1,
        revision_label="首发版",
        status="published",
        snapshot_json={"title": "新人销售基础训练", "stages": []},
        content_hash="c" * 64,
        version=1,
        save_idempotency_key_hash="d" * 64,
        save_fingerprint="e" * 64,
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    cohort = NewcomerCohort(
        cohort_id="cohort-email-import",
        organization_id="org-1",
        stable_key="email-import-cohort",
        name="七月新人班",
        path_revision_id=revision.revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash="f" * 64,
        creation_fingerprint="1" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    learner = User(
        user_id="learner-email-import",
        wechat_user_id="wechat-email-import",
        name="王小明",
        email="ready@example.com",
        role="user",
        is_active=True,
    )
    test_db.add_all([path, revision, cohort, learner])
    await test_db.flush()

    async with await _client(test_db) as client:
        response = await client.post(
            "/api/v1/admin/newcomer-training/cohorts/cohort-email-import/enrollment-imports/preview",
            json={
                "emails": ["READY@example.com", "missing@example.com"],
                "reason": "七月新人班批量入班",
            },
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["eligible_count"] == 1
    assert data["failure_count"] == 1
    assert data["items"] == [
        {
            "learner_id": "learner-email-import",
            "learner_name": "王小明",
            "status": "eligible",
            "enrollment_id": None,
            "reason": None,
        },
        {
            "learner_id": "",
            "learner_name": "missing@example.com",
            "status": "failed",
            "enrollment_id": None,
            "reason": "learner_email_not_found_or_inactive",
        },
    ]


@pytest.mark.asyncio
async def test_resource_detail_validation_and_archive_preserve_revision_history(
    test_db,
) -> None:
    async with await _client(test_db) as client:
        created = await client.post(
            "/api/v1/admin/newcomer-training/resources/source_document",
            headers={"Idempotency-Key": "create-source-for-archive"},
            json=_source_payload(),
        )
        assert created.status_code == 200
        document_id = created.json()["data"]["resource"]["document_id"]
        revision_id = created.json()["data"]["working_revision"]["revision_id"]

        detail = await client.get(
            f"/api/v1/admin/newcomer-training/resources/source_document/{document_id}"
        )
        validation = await client.post(
            f"/api/v1/admin/newcomer-training/resources/source_document/{document_id}/commands/validate"
        )

        assert detail.status_code == 200
        assert detail.headers["etag"] == 'W/"2"'
        assert detail.json()["data"]["working_revision"]["revision_id"] == (
            revision_id
        )
        assert validation.status_code == 200
        assert validation.json()["data"]["valid"] is True

        revision = await test_db.get(LearningSourceDocumentRevision, revision_id)
        assert revision is not None
        await LearningGovernanceService(test_db).publish_source_revision(
            actor=_actors().learning,
            revision_id=revision_id,
            expected_revision_version=revision.version,
            idempotency_key="release-plan-resource-source",
        )
        await test_db.commit()

        archived = await client.post(
            f"/api/v1/admin/newcomer-training/resources/source_document/{document_id}/commands/archive",
            headers={
                "Idempotency-Key": "archive-source",
                "If-Match": 'W/"3"',
            },
            json={"reason": "材料已经由新版替代"},
        )
        replay = await client.post(
            f"/api/v1/admin/newcomer-training/resources/source_document/{document_id}/commands/archive",
            headers={
                "Idempotency-Key": "archive-source",
                "If-Match": 'W/"3"',
            },
            json={"reason": "材料已经由新版替代"},
        )
        after = await client.get(
            f"/api/v1/admin/newcomer-training/resources/source_document/{document_id}"
        )

    assert archived.status_code == 200
    assert replay.status_code == 200
    assert archived.json() == replay.json()
    assert archived.headers["etag"] == 'W/"4"'
    assert after.json()["data"]["resource"]["status"] == "archived"
    assert after.json()["data"]["published_revision"]["status"] == "archived"


@pytest.mark.asyncio
async def test_learner_options_use_safe_labels_and_fail_closed(test_db) -> None:
    learner = User(
        user_id="learner-option-1",
        wechat_user_id="learner-option-wechat-1",
        name="李明",
        email="liming@example.com",
        role="user",
        is_active=True,
    )
    test_db.add(learner)
    await test_db.flush()

    async with await _client(test_db) as client:
        allowed = await client.get(
            "/api/v1/admin/newcomer-training/learner-options?search=李明"
        )
    async with await _client(test_db, allowed=False) as client:
        denied = await client.get(
            "/api/v1/admin/newcomer-training/learner-options"
        )

    assert allowed.status_code == 200
    assert allowed.json()["data"]["items"] == [
        {
            "learner_id": "learner-option-1",
            "name": "李明",
            "email": "liming@example.com",
            "already_enrolled": False,
        }
    ]
    assert denied.status_code == 403
    assert denied.json()["error"] == "[NEWCOMER_PERMISSION_DENIED]"


@pytest.mark.asyncio
async def test_resource_references_show_governed_consumers_without_payloads(
    test_db,
) -> None:
    async with await _client(test_db) as client:
        created_source = await client.post(
            "/api/v1/admin/newcomer-training/resources/source_document",
            headers={"Idempotency-Key": "create-reference-source"},
            json=_source_payload(),
        )
        source_id = created_source.json()["data"]["resource"]["document_id"]
        source_revision_id = created_source.json()["data"]["working_revision"][
            "revision_id"
        ]
        anchor = await client.post(
            f"/api/v1/admin/newcomer-training/source-revisions/{source_revision_id}/anchors",
            headers={"Idempotency-Key": "create-reference-anchor"},
            json={
                "anchor_key": "reference-anchor",
                "label": "客户风险说明",
                "locator": {
                    "type": "page",
                    "page": 1,
                    "start_offset": 0,
                    "end_offset": 30,
                },
                "excerpt_hash": "b" * 64,
            },
        )
        assert anchor.status_code == 200
        anchor_id = anchor.json()["data"]["anchor_id"]
        created_unit = await client.post(
            "/api/v1/admin/newcomer-training/resources/learning_unit",
            headers={"Idempotency-Key": "create-referencing-unit"},
            json={
                "resource_type": "learning_unit",
                "stable_key": "referencing-unit",
                "title": "引用来源的学习单元",
                "working_revision": {
                    "revision_label": "初始草稿",
                    "title": "引用来源的学习单元",
                    "objectives": ["理解客户风险"],
                    "key_concepts": [
                        {
                            "concept_id": "risk",
                            "title": "风险识别",
                            "content": "先确认客户担忧。",
                            "source_anchor_ids": [anchor_id],
                        }
                    ],
                    "examples": [],
                    "checkpoints": [
                        {
                            "checkpoint_id": "risk-check",
                            "prompt": "说明客户风险",
                            "required": True,
                        }
                    ],
                    "practice_hints": [],
                },
            },
        )
        assert created_unit.status_code == 200

        references = await client.get(
            f"/api/v1/admin/newcomer-training/resources/source_document/{source_id}/references"
        )

    assert references.status_code == 200
    payload = references.json()["data"]
    assert payload["is_partial"] is False
    assert payload["archive_behavior"] == "preserve_revisions"
    assert payload["items"] == [
        {
            "reference_type": "learning_unit",
            "title": "引用来源的学习单元",
            "revision_label": "初始草稿",
            "status": "working",
            "href": "/admin/newcomer-training/content",
        }
    ]
    assert "snapshot" not in payload


@pytest.mark.asyncio
async def test_assessment_workspace_applies_exact_server_object_scope(
    test_db,
) -> None:
    now = datetime.now(UTC)
    allowed_artifact = TaskPayloadArtifact(
        artifact_id="artifact-allowed",
        organization_id="org-1",
        data_classification="internal",
        content_hash="a" * 64,
        payload_json={"safe": True},
        created_at=now,
    )
    denied_artifact = TaskPayloadArtifact(
        artifact_id="artifact-denied",
        organization_id="org-1",
        data_classification="internal",
        content_hash="b" * 64,
        payload_json={"safe": True},
        created_at=now,
    )
    tasks = [
        DurableTask(
            task_id="task-allowed",
            task_type="audio_assessment.evaluate",
            schema_version=1,
            organization_id="org-1",
            actor_id="learner-1",
            resource_type="audio_attempt",
            resource_id="attempt-allowed",
            idempotency_key_hash="c" * 64,
            idempotency_fingerprint="d" * 64,
            input_artifact_id=allowed_artifact.artifact_id,
            state="queued",
            priority=50,
            attempt_count=0,
            max_attempts=3,
            timeout_seconds=300,
            retry_policy_json={"strategy": "fixed", "delay_seconds": 5},
            next_run_at=now,
            correlation_id="corr-allowed",
            created_at=now,
            updated_at=now,
        ),
        DurableTask(
            task_id="task-denied",
            task_type="audio_assessment.evaluate",
            schema_version=1,
            organization_id="org-1",
            actor_id="learner-2",
            resource_type="audio_attempt",
            resource_id="attempt-denied",
            idempotency_key_hash="e" * 64,
            idempotency_fingerprint="f" * 64,
            input_artifact_id=denied_artifact.artifact_id,
            state="queued",
            priority=50,
            attempt_count=0,
            max_attempts=3,
            timeout_seconds=300,
            retry_policy_json={"strategy": "fixed", "delay_seconds": 5},
            next_run_at=now,
            correlation_id="corr-denied",
            created_at=now,
            updated_at=now,
        ),
    ]
    test_db.add_all(
        [
            allowed_artifact,
            denied_artifact,
            *tasks,
            TaskOperatorScopeGrant(
                grant_id="grant-allowed-task",
                actor_id="admin-1",
                organization_id="org-1",
                resource_type="audio_attempt",
                resource_id="attempt-allowed",
                can_read=True,
                can_operate=True,
                is_active=True,
                expires_at=now + timedelta(days=1),
                granted_by="security-admin",
                reason="处理指定录音评测任务",
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    await test_db.flush()

    async with await _client(test_db) as client:
        response = await client.get(
            "/api/v1/admin/newcomer-training/assessment-tasks"
        )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert [item["task_id"] for item in items] == ["task-allowed"]
    assert items[0]["resource_type"] == "audio_attempt"
    assert items[0]["available_actions"] == ["查看详情", "申请取消"]


@pytest.mark.asyncio
async def test_foundation_learner_list_and_detail_use_v2_journey_and_scope(
    test_db,
    test_engine,
) -> None:
    now = datetime.now(UTC)
    learner = User(
        user_id="foundation-learner-1",
        wechat_user_id="wechat-foundation-learner-1",
        name="张三",
        email="foundation-learner@example.com",
        role="user",
        is_active=True,
    )
    path = NewcomerPath(
        path_id="foundation-path-1",
        organization_id="org-1",
        stable_key="foundation-path",
        title="新人销售基础训练",
        status="active",
        published_revision_id="foundation-revision-1",
        version=1,
        creation_idempotency_key_hash="a" * 64,
        creation_fingerprint="b" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    revision = NewcomerPathRevision(
        revision_id="foundation-revision-1",
        path_id=path.path_id,
        organization_id="org-1",
        revision_no=1,
        revision_label="首发版",
        status="published",
        snapshot_json=_journey_snapshot(),
        content_hash="c" * 64,
        version=1,
        save_idempotency_key_hash="d" * 64,
        save_fingerprint="e" * 64,
        publish_idempotency_key_hash="f" * 64,
        publish_fingerprint="1" * 64,
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    cohort = NewcomerCohort(
        cohort_id="foundation-cohort-1",
        organization_id="org-1",
        stable_key="foundation-cohort",
        name="七月新人班",
        path_revision_id=revision.revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash="2" * 64,
        creation_fingerprint="3" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    enrollment = NewcomerEnrollment(
        enrollment_id="foundation-enrollment-1",
        organization_id="org-1",
        learner_id=learner.user_id,
        cohort_id=cohort.cohort_id,
        path_revision_id=revision.revision_id,
        status="active",
        version=1,
        creation_idempotency_key_hash="4" * 64,
        creation_fingerprint="5" * 64,
        assigned_by="admin-1",
        assigned_at=now,
        updated_at=now,
    )
    test_db.add_all([learner, path, revision, cohort, enrollment])
    await test_db.flush()

    async with await _client(test_db) as client:
        listed = await client.get(
            "/api/v1/admin/newcomer-training/learners?limit=20&offset=0"
        )
        detail = await client.get(
            f"/api/v1/admin/newcomer-training/learners/{learner.user_id}"
        )

    assert listed.status_code == 200
    list_data = listed.json()["data"]
    assert list_data["total"] == 1
    assert list_data["items"][0]["learner"] == {
        "learner_id": learner.user_id,
        "name": "张三",
    }
    assert list_data["items"][0]["progress"] == {
        "completed_required": 0,
        "total_required": 1,
        "percentage": 0,
    }
    assert list_data["items"][0]["current_activity"]["activity_id"] == (
        "lesson-foundation"
    )
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["cohort"]["name"] == "七月新人班"
    assert detail_data["journey"]["contract_version"] == "journey_projection_v1"
    assert detail_data["journey"]["stages"][0]["stage_id"] == "stage-foundation"
    assert "phases" not in detail_data["journey"]

    def capture_selects(target: list[str]):
        def listener(
            _connection,
            _cursor,
            statement: str,
            _parameters,
            _context,
            _executemany,
        ) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                target.append(statement)

        return listener

    one_learner_queries: list[str] = []
    one_learner_listener = capture_selects(one_learner_queries)
    event.listen(
        test_engine.sync_engine,
        "before_cursor_execute",
        one_learner_listener,
    )
    try:
        async with await _client(test_db) as client:
            one_learner_page = await client.get(
                "/api/v1/admin/newcomer-training/learners?limit=20&offset=0"
            )
    finally:
        event.remove(
            test_engine.sync_engine,
            "before_cursor_execute",
            one_learner_listener,
        )
    assert one_learner_page.status_code == 200

    for index in range(2, 8):
        extra_learner = User(
            user_id=f"foundation-learner-{index}",
            wechat_user_id=f"wechat-foundation-learner-{index}",
            name=f"学员{index}",
            email=f"foundation-learner-{index}@example.com",
            role="user",
            is_active=True,
        )
        test_db.add_all(
            [
                extra_learner,
                NewcomerEnrollment(
                    enrollment_id=f"foundation-enrollment-{index}",
                    organization_id="org-1",
                    learner_id=extra_learner.user_id,
                    cohort_id=cohort.cohort_id,
                    path_revision_id=revision.revision_id,
                    status="active",
                    version=1,
                    creation_idempotency_key_hash=f"{index:x}" * 64,
                    creation_fingerprint=f"{index + 8:x}" * 64,
                    assigned_by="admin-1",
                    assigned_at=now,
                    updated_at=now,
                ),
            ]
        )
    await test_db.flush()

    seven_learner_queries: list[str] = []
    seven_learner_listener = capture_selects(seven_learner_queries)
    event.listen(
        test_engine.sync_engine,
        "before_cursor_execute",
        seven_learner_listener,
    )
    try:
        async with await _client(test_db) as client:
            seven_learner_page = await client.get(
                "/api/v1/admin/newcomer-training/learners?limit=20&offset=0"
            )
    finally:
        event.remove(
            test_engine.sync_engine,
            "before_cursor_execute",
            seven_learner_listener,
        )
    assert seven_learner_page.status_code == 200
    assert seven_learner_page.json()["data"]["total"] == 7
    assert len(seven_learner_queries) == len(one_learner_queries)

    restricted_scope = TeamDataScope.restricted(learner_ids={"another-learner"})
    async with await _client(test_db, scope=restricted_scope) as client:
        hidden_list = await client.get("/api/v1/admin/newcomer-training/learners")
        hidden_detail = await client.get(
            f"/api/v1/admin/newcomer-training/learners/{learner.user_id}"
        )

    assert hidden_list.status_code == 200
    assert hidden_list.json()["data"]["items"] == []
    assert hidden_detail.status_code == 404
