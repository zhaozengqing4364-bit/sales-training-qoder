from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.db.models import PromptTemplate, User
from curriculum_practice.models import LearningContent
from prompt_templates.models import PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerAudioSubmission,
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerOperationLog,
    SalesTrainerUnit,
)
from sales_trainer.services.newcomer_dead_data_diagnostics_service import (
    NewcomerDeadDataDiagnosticsService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    suffix = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-path-config-api-{role}-{suffix}",
        name=f"新人路径配置 API {role}",
        email=f"newcomer-path-config-api-{role}-{suffix}@example.com",
        role=role,
    )


def _unit(unit_id: str, title: str) -> SalesTrainerUnit:
    return SalesTrainerUnit(
        unit_id=unit_id,
        name=title,
        description=f"{title}说明",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "path_title": "新人训练路径",
                "goal_title": "完成新人训练",
                "module_key": "business_skills",
                "module_type": "article_exam",
                "order_index": 1,
                "completion_rule": "submitted",
            }
        },
    )


def _path_payload(
    unit_id: str,
    title: str,
    *,
    learning_content_id: str | None = None,
    exam_paper_id: str | None = None,
) -> dict[str, object]:
    module: dict[str, object] = {
        "module_key": "business_skills",
        "module_type": "article_exam",
        "enabled": True,
        "order_index": 1,
        "title": title,
        "description": f"{title}说明",
        "target_unit_id": unit_id,
        "completion_rule": "submitted",
        "primary_action_label": "开始学习",
    }
    if learning_content_id:
        module["learning_content_id"] = learning_content_id
    if exam_paper_id:
        module["exam_paper_id"] = exam_paper_id
    return {
        "path_key": "newcomer_training_path_v1",
        "title": "新人训练路径",
        "goal_title": "完成新人训练",
        "reason": f"{title}保存为待发布修订",
        "modules": [module],
    }


def _path_payload_with_ai_coach(
    unit_id: str,
    title: str,
    *,
    learning_content_id: str | None = None,
    exam_paper_id: str | None = None,
) -> dict[str, object]:
    payload = _path_payload(
        unit_id,
        title,
        learning_content_id=learning_content_id,
        exam_paper_id=exam_paper_id,
    )
    modules = payload["modules"]
    assert isinstance(modules, list)
    first_module = modules[0]
    assert isinstance(first_module, dict)
    first_module["ai_coach"] = {
        "enabled": True,
        "coach_mode": "mixed_drill",
        "allowed_interaction_types": ["single_choice", "multiple_choice"],
        "prompt_template_id": "11111111-1111-1111-1111-111111111111",
        "prompt_revision_id": None,
        "prompt_contract_hash": None,
        "scoring_prompt_template_id": None,
        "scoring_prompt_revision_id": None,
        "scoring_contract_hash": None,
        "min_turns": 3,
        "max_turns": 10,
        "mastery_threshold": 90,
        "output_schema_version": "ai_coach_interaction_v1",
        "generation_model": None,
        "scoring_model": None,
        "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
        "failure_behavior": "skip_turn",
    }
    return payload


async def _seed_business_bindings(
    test_db: AsyncSession,
    *,
    admin: User,
    unit: SalesTrainerUnit,
    key_prefix: str,
) -> tuple[LearningContent, SalesTrainerExamPaper]:
    content = LearningContent(
        learning_content_id=f"{key_prefix}-content",
        title=f"{unit.name}学习内容",
        summary="发布配置测试用学习内容。",
        owner="新人训练路径",
        source="integration_test",
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    paper = SalesTrainerExamPaper(
        paper_id=str(uuid.uuid4()),
        paper_key=f"{key_prefix}-paper",
        title=f"{unit.name}考卷",
        module_key="business_skills",
        unit_id=unit.unit_id,
        pass_threshold=60,
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([content, paper])
    await test_db.commit()
    return content, paper


async def _seed_ai_coach_prompt_templates(
    test_db: AsyncSession,
    *,
    generation_prompt_type: str = "stage",
    generation_business_purpose: str | None = (
        PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
    ),
    generation_category: str = "sales_trainer_ai_coach",
    generation_is_active: bool = True,
    scoring_prompt_type: str = "scoring",
    scoring_business_purpose: str | None = (
        PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
    ),
    scoring_category: str = "sales_trainer_ai_coach",
    scoring_is_active: bool = True,
) -> tuple[PromptTemplate, PromptTemplate]:
    generation = PromptTemplate(
        id="11111111-1111-1111-1111-111111111111",
        name="商务技巧 AI 教练对话生成",
        prompt_type=generation_prompt_type,
        business_purpose=generation_business_purpose,
        category=generation_category,
        template="请根据 {{ module_key }} 和 {{ coach_mode }} 生成教练回复。",
        variables=["module_key", "coach_mode"],
        is_active=generation_is_active,
        is_default=False,
        is_system=False,
    )
    scoring = PromptTemplate(
        id="22222222-2222-2222-2222-222222222222",
        name="商务技巧 AI 教练简答评分",
        prompt_type=scoring_prompt_type,
        business_purpose=scoring_business_purpose,
        category=scoring_category,
        template="请根据 {{ answer_text }} 和 {{ reference_answer }} 评分。",
        variables=["answer_text", "reference_answer"],
        is_active=scoring_is_active,
        is_default=False,
        is_system=False,
    )
    test_db.add_all([generation, scoring])
    await test_db.commit()
    return generation, scoring


@pytest.mark.asyncio
async def test_should_publish_and_rollback_newcomer_path_config_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = _unit("newcomer-path-config-api-unit", "商务技巧旧版")
    test_db.add_all([admin, learner, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(test_db)
    content, paper = await _seed_business_bindings(
        test_db,
        admin=admin,
        unit=unit,
        key_prefix="newcomer-path-config-api",
    )

    backfill_response = await async_client.get(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
    )
    assert backfill_response.status_code == 200
    assert backfill_response.json()["data"]["source"] == "legacy_migration_snapshot"
    assert backfill_response.json()["data"]["fallback_reason"] == "active_revision_missing"
    assert backfill_response.json()["data"]["legacy_snapshot_only"] is True
    diagnostics = backfill_response.json()["data"]["diagnostics"]
    assert diagnostics["surface_key"] == NEWCOMER_PATH_LOGICAL_ID
    assert diagnostics["permission_policy"]["rollback"] == (
        "sales_trainer.manage_modules"
    )
    assert diagnostics["high_risk_actions"]["publish"]["preview_endpoint"] == (
        "/api/v1/admin/newcomer-training/path-config/publish/preview"
    )
    assert diagnostics["high_risk_actions"]["regrade"]["history_overwrite"] is False

    save_first_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(
            unit.unit_id,
            "商务技巧第一版",
            learning_content_id=content.learning_content_id,
            exam_paper_id=paper.paper_id,
        ),
    )
    assert save_first_response.status_code == 200
    assert save_first_response.json()["data"]["has_unpublished_revision"] is True

    before_publish_response = await async_client.get(
        "/api/v1/sales-trainer/paths",
        headers=_auth_headers(learner),
    )
    assert before_publish_response.status_code == 200
    assert before_publish_response.json()["data"]["items"] == []
    assert before_publish_response.json()["data"]["total"] == 0

    publish_first_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "第一版生效"},
    )
    assert publish_first_response.status_code == 200
    first_revision_id = publish_first_response.json()["data"]["active_revision_id"]
    assert publish_first_response.json()["data"]["fallback_reason"] is None
    assert publish_first_response.json()["data"]["legacy_snapshot_only"] is False
    assert publish_first_response.json()["data"]["active_revision_snapshot"][
        "revision_id"
    ] == first_revision_id

    save_second_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(
            unit.unit_id,
            "商务技巧第二版",
            learning_content_id=content.learning_content_id,
            exam_paper_id=paper.paper_id,
        ),
    )
    assert save_second_response.status_code == 200

    publish_preview_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish/preview",
        headers=_auth_headers(admin),
    )
    assert publish_preview_response.status_code == 200
    publish_preview = publish_preview_response.json()["data"]
    assert publish_preview["action"] == "newcomer_path_config.publish"
    assert publish_preview["permission"] == "sales_trainer.manage_modules"
    assert publish_preview["requires_reason"] is True
    assert publish_preview["requires_trace_id"] is True
    assert publish_preview["future_only"] is True
    assert publish_preview["risk_level"] == "medium"
    assert "module_configuration_changed" in publish_preview["risk_reasons"]
    assert publish_preview["change_class"] == "semantic"
    assert publish_preview["target_revision_id"] == save_second_response.json()["data"][
        "working_revision_id"
    ]
    assert publish_preview["impact_scope"]["active_revision_id"] == first_revision_id
    assert publish_preview["impact_scope"]["working_revision_id"] == (
        save_second_response.json()["data"]["working_revision_id"]
    )
    assert publish_preview["impact_scope"]["will_change_active_revision"] is True
    assert publish_preview["impact_scope"]["future_learner_paths_changed"] is True
    assert publish_preview["impact_scope"]["historical_attempts_changed"] is False
    assert publish_preview["impact_scope"]["historical_submissions_changed"] is False
    assert publish_preview["impact_scope"]["historical_regrade_required"] is False
    assert publish_preview["impact_scope"]["affected_module_keys"] == [
        "business_skills"
    ]
    assert publish_preview["impact_scope"]["changed_module_keys"] == [
        "business_skills"
    ]
    assert publish_preview["impact_scope"]["rollback_available"] is True
    assert publish_preview["before_snapshot"]["revision_id"] == first_revision_id
    assert publish_preview["after_snapshot"]["revision_id"] == (
        save_second_response.json()["data"]["working_revision_id"]
    )
    assert publish_preview["rollback_hint"]["available"] is True
    assert publish_preview["rollback_hint"]["target_revision_id"] == first_revision_id
    assert publish_preview["rollback_hint"]["preview_endpoint"] == (
        "/api/v1/admin/newcomer-training/path-config/rollback/preview"
    )
    assert "impact_scope" in publish_preview["audit_event"]["required_fields"]

    publish_second_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "第二版生效"},
    )
    assert publish_second_response.status_code == 200

    after_second_publish_response = await async_client.get(
        "/api/v1/sales-trainer/paths",
        headers=_auth_headers(learner),
    )
    assert after_second_publish_response.status_code == 200
    second_path = after_second_publish_response.json()["data"]["items"][0]
    assert second_path["path_revision_id"] == publish_second_response.json()["data"]["active_revision_id"]
    assert second_path["path_revision_no"] == 2
    assert second_path["levels"][0]["level_title"] == "商务技巧第二版"
    assert second_path["levels"][0]["module_key"] == "business_skills"
    assert second_path["levels"][0]["module_type"] == "article_exam"

    revisions_response = await async_client.get(
        "/api/v1/admin/newcomer-training/path-config/revisions",
        headers=_auth_headers(admin),
    )
    assert revisions_response.status_code == 200
    assert revisions_response.json()["data"]["total"] == 2

    preview_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/rollback/preview",
        headers=_auth_headers(admin),
        json={"revision_id": first_revision_id},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["action"] == "newcomer_path_config.rollback"
    assert preview["permission"] == "sales_trainer.manage_modules"
    assert preview["requires_reason"] is True
    assert preview["requires_trace_id"] is True
    assert preview["future_only"] is True
    assert preview["impact_scope"]["future_learner_paths_changed"] is True
    assert preview["impact_scope"]["historical_attempts_changed"] is False
    assert preview["impact_scope"]["historical_regrade_required"] is False
    assert preview["before_snapshot"]["revision_id"] == publish_second_response.json()[
        "data"
    ]["active_revision_id"]
    assert preview["after_snapshot"]["revision_id"] == first_revision_id
    assert "impact_scope" in preview["audit_event"]["required_fields"]

    rollback_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/rollback",
        headers=_auth_headers(admin),
        json={"revision_id": first_revision_id, "reason": "回滚第一版"},
    )
    assert rollback_response.status_code == 200
    rollback_trace_id = rollback_response.json()["trace_id"]

    after_rollback_response = await async_client.get(
        "/api/v1/sales-trainer/paths",
        headers=_auth_headers(learner),
    )
    assert after_rollback_response.status_code == 200
    rollback_path = after_rollback_response.json()["data"]["items"][0]
    assert rollback_path["levels"][0]["level_title"] == "商务技巧第一版"

    logs = await test_db.execute(
        select(SalesTrainerOperationLog).where(
            SalesTrainerOperationLog.action == "newcomer_path_config.rollback"
        )
    )
    rollback_log = logs.scalar_one()
    assert rollback_log.request_id == rollback_trace_id
    assert rollback_log.metadata_json["trace_id"] == rollback_trace_id


@pytest.mark.asyncio
async def test_should_report_newcomer_path_dead_data_diagnostics(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = _unit("newcomer-path-dead-data-unit", "商务技巧")
    test_db.add_all([admin, learner, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(test_db)
    content, paper = await _seed_business_bindings(
        test_db,
        admin=admin,
        unit=unit,
        key_prefix="newcomer-path-dead-data",
    )

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(
            unit.unit_id,
            "商务技巧",
            learning_content_id=content.learning_content_id,
            exam_paper_id=paper.paper_id,
        ),
    )
    assert save_response.status_code == 200
    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "发布 dead data 诊断基线"},
    )
    assert publish_response.status_code == 200

    content.status = "archived"
    test_db.add(
        SalesTrainerAudioSubmission(
            submission_id=str(uuid.uuid4()),
            unit_id=None,
            user_id=str(learner.user_id),
            purpose="ppt_pitch",
            original_filename="legacy.wav",
            content_type="audio/wav",
            size_bytes=128,
            storage_key="/tmp/legacy.wav",
            file_hash="legacy-hash",
            score_scheme_snapshot={
                "prompt_id": "legacy-prompt-id",
                "version": 1,
                "pass_threshold": 80,
            },
            status="scored",
        )
    )
    missing_revision_submission_id = str(uuid.uuid4())
    replay_material_id = str(uuid.uuid4())
    replay_version_id = str(uuid.uuid4())
    test_db.add(
        SalesTrainerAudioSubmission(
            submission_id=missing_revision_submission_id,
            unit_id=None,
            user_id=str(learner.user_id),
            purpose="ppt_pitch",
            original_filename="lineage.wav",
            content_type="audio/wav",
            size_bytes=128,
            storage_key="/tmp/lineage.wav",
            file_hash="lineage-hash",
            score_scheme_snapshot={
                "prompt_id": "lineage-prompt-id",
                "version": 1,
                "pass_threshold": 80,
                "prompt_snapshot": {
                    "prompt_id": "lineage-prompt-id",
                    "system_prompt": "系统提示",
                    "scoring_template": "评分模板",
                    "version": 1,
                    "status": "published",
                },
            },
            task_brief_snapshot={
                "module_key": "elevator_pitch",
                "submission_context": {
                    "path_key": NEWCOMER_PATH_LOGICAL_ID,
                    "path_revision_id": str(uuid.uuid4()),
                    "path_revision_no": 999,
                    "module_key": "elevator_pitch",
                    "module_type": "audio_scoring",
                    "legacy_snapshot_only": False,
                },
            },
            status="uploaded",
        )
    )
    test_db.add(
        SalesTrainerMaterial(
            material_id=replay_material_id,
            material_key=f"historical-replay-material-{uuid.uuid4().hex[:8]}",
            name="历史回放材料",
            material_type="ppt_deck",
            purpose="ppt_pitch",
            status="published",
            current_version_id=replay_version_id,
            created_by=str(admin.user_id),
            updated_by=str(admin.user_id),
        )
    )
    test_db.add(
        SalesTrainerMaterialVersion(
            version_id=replay_version_id,
            material_id=replay_material_id,
            version_label="v1",
            title="历史回放材料 v1",
            file_name="historical-replay.pdf",
            content_type="application/pdf",
            file_size_bytes=100,
            storage_key="/tmp/historical-replay.pdf",
            status="published",
            created_by=str(admin.user_id),
            published_by=str(admin.user_id),
        )
    )
    missing_material_reference_submission_id = str(uuid.uuid4())
    missing_material_file_submission_id = str(uuid.uuid4())
    test_db.add(
        SalesTrainerAudioSubmission(
            submission_id=missing_material_reference_submission_id,
            unit_id=None,
            user_id=str(learner.user_id),
            purpose="ppt_pitch",
            original_filename="material-reference.wav",
            content_type="audio/wav",
            size_bytes=128,
            storage_key="/tmp/material-reference.wav",
            file_hash="material-reference-hash",
            material_snapshot={
                "version": 1,
                "items": [
                    {
                        "material_id": replay_material_id,
                        "current_version": {"version_id": replay_version_id},
                    }
                ],
                "confirmed_material_version_id": None,
            },
            status="uploaded",
        )
    )
    test_db.add(
        SalesTrainerAudioSubmission(
            submission_id=missing_material_file_submission_id,
            unit_id=None,
            user_id=str(learner.user_id),
            purpose="ppt_pitch",
            original_filename="material-file.wav",
            content_type="audio/wav",
            size_bytes=128,
            storage_key="/tmp/material-file.wav",
            file_hash="material-file-hash",
            confirmed_material_version_id=replay_version_id,
            material_snapshot={
                "version": 1,
                "confirmed_material_version_id": replay_version_id,
            },
            status="uploaded",
        )
    )
    test_db.add(
        SalesTrainerMaterial(
            material_id=str(uuid.uuid4()),
            material_key="orphan-current-version-missing",
            name="未引用且缺少当前版本的材料",
            material_type="ppt_deck",
            purpose="ppt_pitch",
            status="published",
            created_by=str(admin.user_id),
            updated_by=str(admin.user_id),
        )
    )
    await test_db.commit()

    denied_response = await async_client.get(
        "/api/v1/admin/newcomer-training/path-config/dead-data-diagnostics",
        headers=_auth_headers(learner),
    )
    assert denied_response.status_code == 403

    diagnostics_response = await async_client.get(
        "/api/v1/admin/newcomer-training/path-config/dead-data-diagnostics",
        headers=_auth_headers(admin),
    )
    assert diagnostics_response.status_code == 200
    report = diagnostics_response.json()["data"]
    codes = {issue["code"] for issue in report["issues"]}

    assert report["mode"] == "dry_run"
    assert report["mutates_history"] is False
    assert report["requires_manual_approval"] is True
    assert report["permission"] == "sales_trainer.manage_modules"
    assert report["summary"]["total"] >= 2
    assert "LEARNING_CONTENT_NOT_PUBLISHED" in codes
    assert "AUDIO_PROMPT_SNAPSHOT_MISSING" in codes
    assert "AUDIO_SUBMISSION_LINEAGE_MISSING" in codes
    assert "AUDIO_SUBMISSION_PATH_REVISION_NOT_FOUND" in codes
    assert "AUDIO_SCORE_PROMPT_REVISION_MISSING" in codes
    assert "HISTORICAL_MATERIAL_REPLAY_MISSING_REFERENCE" in codes
    assert "HISTORICAL_MATERIAL_REPLAY_MISSING_FILE" in codes
    assert "MATERIAL_CURRENT_VERSION_MISSING" in codes
    assert "ORPHAN_MATERIAL" in codes
    learning_issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "LEARNING_CONTENT_NOT_PUBLISHED"
    )
    assert learning_issue["source"] == "active_revision"
    assert learning_issue["resource_id"] == content.learning_content_id
    audio_issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "AUDIO_PROMPT_SNAPSHOT_MISSING"
    )
    assert audio_issue["metadata"]["legacy_snapshot_only"] is True
    assert audio_issue["metadata"]["regrade_unavailable"] is True
    lineage_issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "AUDIO_SUBMISSION_LINEAGE_MISSING"
    )
    assert lineage_issue["metadata"]["legacy_snapshot_only"] is True
    path_revision_issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "AUDIO_SUBMISSION_PATH_REVISION_NOT_FOUND"
    )
    assert path_revision_issue["resource_id"] == missing_revision_submission_id
    prompt_revision_issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "AUDIO_SCORE_PROMPT_REVISION_MISSING"
    )
    assert prompt_revision_issue["resource_id"] == missing_revision_submission_id
    assert prompt_revision_issue["metadata"]["regrade_unavailable"] is True
    material_reference_issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "HISTORICAL_MATERIAL_REPLAY_MISSING_REFERENCE"
    )
    assert material_reference_issue["resource_id"] == (
        missing_material_reference_submission_id
    )
    assert material_reference_issue["metadata"]["material_version_ids"] == [
        replay_version_id
    ]
    material_file_issue = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "HISTORICAL_MATERIAL_REPLAY_MISSING_FILE"
    )
    assert material_file_issue["resource_id"] == missing_material_file_submission_id
    assert material_file_issue["metadata"]["confirmed_material_version_id"] == (
        replay_version_id
    )
    candidate_actions = {
        action["issue_code"]: action for action in report["candidate_actions"]
    }
    assert candidate_actions["LEARNING_CONTENT_NOT_PUBLISHED"]["action"] == (
        "restore_or_replace_asset_reference"
    )
    assert candidate_actions["LEARNING_CONTENT_NOT_PUBLISHED"]["mutates_history"] is False
    assert (
        candidate_actions["AUDIO_PROMPT_SNAPSHOT_MISSING"]["action"]
        == "preserve_read_only_replay_and_mark_legacy"
    )
    assert (
        candidate_actions["AUDIO_PROMPT_SNAPSHOT_MISSING"]["safe_to_apply_automatically"]
        is False
    )
    assert candidate_actions["AUDIO_SUBMISSION_LINEAGE_MISSING"]["action"] == (
        "preserve_read_only_replay_and_mark_legacy"
    )
    assert candidate_actions["AUDIO_SUBMISSION_PATH_REVISION_NOT_FOUND"]["action"] == (
        "preserve_read_only_replay_and_mark_legacy"
    )
    assert candidate_actions["AUDIO_SCORE_PROMPT_REVISION_MISSING"]["action"] == (
        "preserve_read_only_replay_and_mark_legacy"
    )
    assert candidate_actions["HISTORICAL_MATERIAL_REPLAY_MISSING_REFERENCE"][
        "action"
    ] == "preserve_read_only_replay_and_mark_legacy"
    assert candidate_actions["HISTORICAL_MATERIAL_REPLAY_MISSING_FILE"]["action"] == (
        "preserve_read_only_replay_and_mark_legacy"
    )
    assert report["rollback_plan"] == {
        "required": False,
        "reason": "diagnostics_only_no_mutation",
        "apply_endpoint": None,
        "rollback_endpoint": None,
    }
    decisions = {item["decision_key"]: item for item in report["manual_decisions"]}
    assert "legacy_history_backfill_policy" in decisions
    assert decisions["legacy_history_backfill_policy"]["required_before"] == (
        "production_backfill"
    )
    assert "HISTORICAL_MATERIAL_REPLAY_MISSING_FILE" in decisions[
        "legacy_history_backfill_policy"
    ]["issue_codes"]
    assert "active_path_repair_policy" in decisions


@pytest.mark.asyncio
async def test_should_limit_material_inventory_scan_in_dead_data_diagnostics(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    material_one_id = str(uuid.uuid4())
    material_two_id = str(uuid.uuid4())
    version_one_id = str(uuid.uuid4())
    version_two_id = str(uuid.uuid4())
    material_one = SalesTrainerMaterial(
        material_id=material_one_id,
        material_key=f"diagnostics-limit-material-{uuid.uuid4().hex[:8]}-one",
        name="诊断容量材料一",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        current_version_id=version_one_id,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    material_two = SalesTrainerMaterial(
        material_id=material_two_id,
        material_key=f"diagnostics-limit-material-{uuid.uuid4().hex[:8]}-two",
        name="诊断容量材料二",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        current_version_id=version_two_id,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    version_one = SalesTrainerMaterialVersion(
        version_id=version_one_id,
        material_id=material_one_id,
        version_label="v1",
        title="诊断容量材料一 v1",
        file_name="material-one.pdf",
        content_type="application/pdf",
        file_size_bytes=100,
        storage_key="/tmp/material-one.pdf",
        status="published",
        created_by=str(admin.user_id),
        published_by=str(admin.user_id),
    )
    version_two = SalesTrainerMaterialVersion(
        version_id=version_two_id,
        material_id=material_two_id,
        version_label="v1",
        title="诊断容量材料二 v1",
        file_name="material-two.pdf",
        content_type="application/pdf",
        file_size_bytes=100,
        storage_key="/tmp/material-two.pdf",
        status="published",
        created_by=str(admin.user_id),
        published_by=str(admin.user_id),
    )
    test_db.add_all([admin, material_one, material_two, version_one, version_two])
    await test_db.commit()

    report = await NewcomerDeadDataDiagnosticsService(
        test_db,
        audio_scan_limit=1,
        material_scan_limit=1,
    ).build_report()

    scanned_materials = report["scanned"]["materials"]
    assert scanned_materials["materials"] == 1
    assert scanned_materials["versions"] == 1
    assert scanned_materials["total_materials"] == 2
    assert scanned_materials["total_versions"] == 2
    assert scanned_materials["limit"] == 1
    assert scanned_materials["truncated"] is True
    assert report["scanned"]["material_scan_limit"] == 1


@pytest.mark.asyncio
async def test_should_not_report_orphan_material_when_referenced_version_is_outside_scan_limit(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    material_id = str(uuid.uuid4())
    current_version_id = str(uuid.uuid4())
    historical_version_id = str(uuid.uuid4())
    material = SalesTrainerMaterial(
        material_id=material_id,
        material_key=f"diagnostics-referenced-material-{uuid.uuid4().hex[:8]}",
        name="被历史版本引用的材料",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        current_version_id=current_version_id,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    current_version = SalesTrainerMaterialVersion(
        version_id=current_version_id,
        material_id=material_id,
        version_label="current",
        title="当前版本",
        file_name="current.pdf",
        content_type="application/pdf",
        file_size_bytes=100,
        storage_key="/tmp/current.pdf",
        status="published",
        created_by=str(admin.user_id),
        published_by=str(admin.user_id),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    historical_version = SalesTrainerMaterialVersion(
        version_id=historical_version_id,
        material_id=material_id,
        version_label="historical",
        title="历史引用版本",
        file_name="historical.pdf",
        content_type="application/pdf",
        file_size_bytes=100,
        storage_key="/tmp/historical.pdf",
        status="published",
        created_by=str(admin.user_id),
        published_by=str(admin.user_id),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=None,
        user_id=str(learner.user_id),
        purpose="ppt_pitch",
        original_filename="legacy.wav",
        content_type="audio/wav",
        size_bytes=128,
        storage_key="/tmp/legacy.wav",
        file_hash="legacy-hash",
        confirmed_material_version_id=historical_version_id,
        material_snapshot={"version_id": historical_version_id},
        score_scheme_snapshot={"prompt": {"prompt_id": "prompt-1"}},
        status="uploaded",
    )
    test_db.add_all([admin, learner, material, current_version, historical_version, submission])
    await test_db.commit()

    report = await NewcomerDeadDataDiagnosticsService(
        test_db,
        audio_scan_limit=1,
        material_scan_limit=1,
    ).build_report()
    material_issues = [
        issue
        for issue in report["issues"]
        if issue["resource_id"] == material_id
    ]

    assert report["scanned"]["materials"]["truncated"] is True
    assert "ORPHAN_MATERIAL" not in {issue["code"] for issue in material_issues}
    assert "MATERIAL_CURRENT_VERSION_MISSING" not in {
        issue["code"] for issue in material_issues
    }


@pytest.mark.asyncio
async def test_should_persist_path_config_revision_across_request_sessions(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_engine: AsyncEngine,
) -> None:
    admin = _user("admin")
    unit = _unit("path-config-api-persist-unit", "商务技巧可持久化")
    test_db.add_all([admin, unit])
    await test_db.commit()

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload(unit.unit_id, "商务技巧持久化修订"),
    )
    assert save_response.status_code == 200, save_response.text

    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        revisions = await session.execute(
            select(SalesTrainerAssetRevision).where(
                SalesTrainerAssetRevision.resource_type
                == NEWCOMER_PATH_RESOURCE_TYPE,
                SalesTrainerAssetRevision.logical_id == NEWCOMER_PATH_LOGICAL_ID,
            )
        )

    saved_revisions = list(revisions.scalars().all())
    assert len(saved_revisions) == 1
    assert saved_revisions[0].status == "working"


@pytest.mark.asyncio
async def test_should_reject_ai_coach_high_risk_fields_via_path_config_for_content_admin(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    content_admin = _user("content_admin")
    unit = _unit("path-config-ai-coach-rbac-unit", "商务技巧")
    test_db.add_all([content_admin, unit])
    await test_db.commit()

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(content_admin),
        json=_path_payload_with_ai_coach(unit.unit_id, "商务技巧"),
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "[PERMISSION_DENIED]"
    assert "mastery_threshold" in body["message"]


@pytest.mark.asyncio
async def test_should_reject_ai_coach_high_risk_publish_for_content_admin(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    content_admin = _user("content_admin")
    unit = _unit("ai-coach-publish-rbac-unit", "商务技巧")
    test_db.add_all([admin, content_admin, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(test_db)

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(unit.unit_id, "商务技巧"),
    )
    assert save_response.status_code == 200, save_response.text

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(content_admin),
        json={"reason": "发布 AI 教练高风险配置"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "[PERMISSION_DENIED]"
    assert "mastery_threshold" in body["message"]


@pytest.mark.asyncio
async def test_should_reject_path_publish_without_working_revision_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "不允许直接从 backfill 发布"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]"


@pytest.mark.asyncio
async def test_should_reject_path_publish_preview_without_working_revision_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish/preview",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 409
    assert response.json()["error"] == "[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]"


@pytest.mark.asyncio
async def test_should_return_typed_error_when_ai_coach_module_binding_is_missing(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/newcomer-training/modules/business_skills/ai-coach/config",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 404
    assert response.json()["error"] == "[NEWCOMER_MODULE_NOT_FOUND]"


@pytest.mark.asyncio
async def test_should_return_typed_error_when_ai_coach_active_revision_is_invalid(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("ai-coach-invalid-revision-unit", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(test_db)
    content, paper = await _seed_business_bindings(
        test_db,
        admin=admin,
        unit=unit,
        key_prefix="ai-coach-invalid-revision",
    )

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(
            unit.unit_id,
            "商务技巧",
            learning_content_id=content.learning_content_id,
            exam_paper_id=paper.paper_id,
        ),
    )
    assert save_response.status_code == 200, save_response.text

    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "发布 AI 教练配置"},
    )
    assert publish_response.status_code == 200, publish_response.text

    active_revision = (
        await test_db.execute(
            select(SalesTrainerAssetRevision).where(
                SalesTrainerAssetRevision.resource_type
                == NEWCOMER_PATH_RESOURCE_TYPE,
                SalesTrainerAssetRevision.logical_id == NEWCOMER_PATH_LOGICAL_ID,
                SalesTrainerAssetRevision.status == "published",
            )
        )
    ).scalar_one()
    active_revision.payload_json = {
        "path_key": "newcomer_training_path_v1",
        "title": "损坏的 AI 教练配置",
        "enabled": True,
        "modules": [
            {
                "module_key": "business_skills",
                "module_type": "article_exam",
                "enabled": True,
                "order_index": 1,
                "title": "商务技巧",
                "ai_coach": "broken",
            }
        ],
    }
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/newcomer-training/modules/business_skills/ai-coach/config",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 500
    assert response.json()["error"] == "[NEWCOMER_PATH_REVISION_INVALID]"


@pytest.mark.asyncio
async def test_should_reject_ai_coach_high_risk_rollback_for_content_admin(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    content_admin = _user("content_admin")
    unit = _unit("ai-coach-rollback-rbac-unit", "商务技巧")
    test_db.add_all([admin, content_admin, unit])
    await test_db.commit()
    content, paper = await _seed_business_bindings(
        test_db,
        admin=admin,
        unit=unit,
        key_prefix="ai-coach-rollback-rbac",
    )
    await _seed_ai_coach_prompt_templates(test_db)

    save_first_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(
            unit.unit_id,
            "商务技巧第一版",
            learning_content_id=content.learning_content_id,
            exam_paper_id=paper.paper_id,
        ),
    )
    assert save_first_response.status_code == 200, save_first_response.text
    publish_first_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "第一版生效"},
    )
    assert publish_first_response.status_code == 200, publish_first_response.text
    first_revision_id = publish_first_response.json()["data"]["active_revision_id"]

    second_payload = _path_payload_with_ai_coach(
        unit.unit_id,
        "商务技巧第二版",
        learning_content_id=content.learning_content_id,
        exam_paper_id=paper.paper_id,
    )
    second_modules = second_payload["modules"]
    assert isinstance(second_modules, list)
    second_ai_coach = second_modules[0]["ai_coach"]
    assert isinstance(second_ai_coach, dict)
    second_ai_coach["mastery_threshold"] = 75
    save_second_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=second_payload,
    )
    assert save_second_response.status_code == 200, save_second_response.text
    publish_second_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "第二版生效"},
    )
    assert publish_second_response.status_code == 200, publish_second_response.text

    preview_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/rollback/preview",
        headers=_auth_headers(content_admin),
        json={"revision_id": first_revision_id},
    )
    assert preview_response.status_code == 403
    preview_body = preview_response.json()
    assert preview_body["error"] == "[PERMISSION_DENIED]"
    assert "mastery_threshold" in preview_body["message"]

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/rollback",
        headers=_auth_headers(content_admin),
        json={"revision_id": first_revision_id, "reason": "回滚到无 AI 教练配置"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "[PERMISSION_DENIED]"
    assert "mastery_threshold" in body["message"]


@pytest.mark.asyncio
async def test_should_not_echo_fake_ai_coach_prompt_hash_on_admin_save(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("path-config-ai-coach-admin-save-unit", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(test_db)

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/ai-coach/config",
        headers=_auth_headers(admin),
        json={
            "enabled": True,
            "coach_mode": "mixed_drill",
            "allowed_interaction_types": ["single_choice", "multiple_choice"],
            "prompt_template_id": "11111111-1111-1111-1111-111111111111",
            "prompt_revision_id": None,
            "prompt_contract_hash": "client-must-not-pin",
            "scoring_prompt_template_id": None,
            "scoring_prompt_revision_id": None,
            "scoring_contract_hash": "client-must-not-pin-scoring",
            "min_turns": 3,
            "max_turns": 10,
            "mastery_threshold": 80,
            "output_schema_version": "client-version",
            "generation_model": None,
            "scoring_model": None,
            "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
            "failure_behavior": "skip_turn",
        },
    )

    assert response.status_code == 200, response.text
    ai_coach = response.json()["data"]["ai_coach"]
    assert ai_coach["output_schema_version"] == "ai_coach_interaction_v1"
    assert ai_coach["prompt_contract_hash"] is None
    assert ai_coach["scoring_contract_hash"] is None

    revision = (
        await test_db.execute(
            select(SalesTrainerAssetRevision).where(
                SalesTrainerAssetRevision.resource_type
                == NEWCOMER_PATH_RESOURCE_TYPE,
                SalesTrainerAssetRevision.logical_id == NEWCOMER_PATH_LOGICAL_ID,
            )
        )
    ).scalar_one()
    module = revision.payload_json["modules"][0]
    assert module["ai_coach"]["prompt_contract_hash"] is None
    assert module["ai_coach"]["scoring_contract_hash"] is None


@pytest.mark.asyncio
async def test_should_reject_missing_ai_coach_generation_prompt_on_admin_save(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("ai-coach-missing-prompt-unit", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/ai-coach/config",
        headers=_auth_headers(admin),
        json={
            "enabled": True,
            "coach_mode": "mixed_drill",
            "allowed_interaction_types": ["single_choice", "multiple_choice"],
            "prompt_template_id": "33333333-3333-3333-3333-333333333333",
            "prompt_revision_id": None,
            "prompt_contract_hash": None,
            "scoring_prompt_template_id": None,
            "scoring_prompt_revision_id": None,
            "scoring_contract_hash": None,
            "min_turns": 3,
            "max_turns": 10,
            "mastery_threshold": 80,
            "output_schema_version": "ai_coach_interaction_v1",
            "generation_model": None,
            "scoring_model": None,
            "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
            "failure_behavior": "skip_turn",
        },
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "[AI_COACH_PROMPT_REVISION_NOT_FOUND]"
    assert "PromptTemplate 不存在" in body["message"]


@pytest.mark.asyncio
async def test_should_reject_scoring_prompt_purpose_mismatch_on_admin_save(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("ai-coach-score-purpose-unit", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(
        test_db,
        scoring_business_purpose="business_etiquette_question_generation",
    )

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/ai-coach/config",
        headers=_auth_headers(admin),
        json={
            "enabled": True,
            "coach_mode": "mixed_drill",
            "allowed_interaction_types": [
                "single_choice",
                "multiple_choice",
                "short_answer",
            ],
            "prompt_template_id": "11111111-1111-1111-1111-111111111111",
            "prompt_revision_id": None,
            "prompt_contract_hash": None,
            "scoring_prompt_template_id": "22222222-2222-2222-2222-222222222222",
            "scoring_prompt_revision_id": None,
            "scoring_contract_hash": None,
            "min_turns": 3,
            "max_turns": 10,
            "mastery_threshold": 80,
            "output_schema_version": "ai_coach_interaction_v1",
            "generation_model": None,
            "scoring_model": None,
            "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
            "failure_behavior": "skip_turn",
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "[AI_COACH_PROMPT_CONFIG_INVALID]"
    assert "scoring_prompt_template_id" in body["message"]


@pytest.mark.asyncio
async def test_should_reject_ai_coach_prompt_revision_fallback_on_admin_save(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("ai-coach-revision-fallback", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(test_db)

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/ai-coach/config",
        headers=_auth_headers(admin),
        json={
            "enabled": True,
            "coach_mode": "mixed_drill",
            "allowed_interaction_types": ["single_choice", "multiple_choice"],
            "prompt_template_id": "11111111-1111-1111-1111-111111111111",
            "prompt_revision_id": "2026-06-01T00:00:00Z",
            "prompt_contract_hash": None,
            "scoring_prompt_template_id": None,
            "scoring_prompt_revision_id": None,
            "scoring_contract_hash": None,
            "min_turns": 3,
            "max_turns": 10,
            "mastery_threshold": 80,
            "output_schema_version": "ai_coach_interaction_v1",
            "generation_model": None,
            "scoring_model": None,
            "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
            "failure_behavior": "skip_turn",
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "[AI_COACH_PROMPT_REVISION_FALLBACK]"
    assert "prompt_revision_id" in body["message"]


@pytest.mark.asyncio
async def test_should_publish_business_skills_path_without_legacy_ai_coach_gate(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("ai-coach-required-publish-unit", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()
    content, paper = await _seed_business_bindings(
        test_db,
        admin=admin,
        unit=unit,
        key_prefix="ai-coach-required-publish",
    )

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload(
            unit.unit_id,
            "商务技巧",
            learning_content_id=content.learning_content_id,
            exam_paper_id=paper.paper_id,
        ),
    )
    assert save_response.status_code == 200, save_response.text

    preview_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish/preview",
        headers=_auth_headers(admin),
    )
    assert preview_response.status_code == 200, preview_response.text

    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "验证路径配置与学习专题 AI Coach 解耦"},
    )
    assert publish_response.status_code == 200, publish_response.text
    active_modules = publish_response.json()["data"]["active_revision_snapshot"][
        "payload"
    ]["modules"]
    assert active_modules[0]["module_key"] == "business_skills"
    assert active_modules[0]["ai_coach"] is None


@pytest.mark.asyncio
async def test_should_reject_invalid_ai_coach_prompt_binding_before_publish(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("ai-coach-invalid-publish-unit", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(test_db)

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(unit.unit_id, "商务技巧"),
    )
    assert save_response.status_code == 200, save_response.text

    working_revision = (
        await test_db.execute(
            select(SalesTrainerAssetRevision).where(
                SalesTrainerAssetRevision.resource_type
                == NEWCOMER_PATH_RESOURCE_TYPE,
                SalesTrainerAssetRevision.logical_id == NEWCOMER_PATH_LOGICAL_ID,
                SalesTrainerAssetRevision.status == "working",
            )
        )
    ).scalar_one()
    working_revision.payload_json["modules"][0]["ai_coach"]["prompt_template_id"] = (
        "33333333-3333-3333-3333-333333333333"
    )
    await test_db.commit()

    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "验证发布前 prompt 仍然有效"},
    )

    assert publish_response.status_code == 404
    body = publish_response.json()
    assert body["error"] == "[AI_COACH_PROMPT_REVISION_NOT_FOUND]"
    assert "PromptTemplate 不存在" in body["message"]


@pytest.mark.asyncio
async def test_should_reject_invalid_ai_coach_prompt_binding_before_publish_preview(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("ai-coach-invalid-preview-unit", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()
    await _seed_ai_coach_prompt_templates(test_db)

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(unit.unit_id, "商务技巧"),
    )
    assert save_response.status_code == 200, save_response.text

    working_revision = (
        await test_db.execute(
            select(SalesTrainerAssetRevision).where(
                SalesTrainerAssetRevision.resource_type
                == NEWCOMER_PATH_RESOURCE_TYPE,
                SalesTrainerAssetRevision.logical_id == NEWCOMER_PATH_LOGICAL_ID,
                SalesTrainerAssetRevision.status == "working",
            )
        )
    ).scalar_one()
    working_revision.payload_json["modules"][0]["ai_coach"]["prompt_template_id"] = (
        "33333333-3333-3333-3333-333333333333"
    )
    await test_db.commit()

    preview_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish/preview",
        headers=_auth_headers(admin),
    )

    assert preview_response.status_code == 404
    body = preview_response.json()
    assert body["error"] == "[AI_COACH_PROMPT_REVISION_NOT_FOUND]"
    assert "PromptTemplate 不存在" in body["message"]


@pytest.mark.asyncio
async def test_should_allow_content_admin_to_save_low_risk_ai_coach_fields(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    content_admin = _user("content_admin")
    unit = _unit("ai-coach-low-risk-content-admin-unit", "商务技巧")
    test_db.add_all([content_admin, unit])
    await test_db.commit()

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/ai-coach/config",
        headers=_auth_headers(content_admin),
        json={"enabled": True},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["ai_coach"]["enabled"] is True
    assert body["data"]["ai_coach"]["prompt_template_id"] is None
