from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerOperationLog,
    SalesTrainerUnit,
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


def _path_payload(unit_id: str, title: str) -> dict[str, object]:
    return {
        "path_key": "newcomer_training_path_v1",
        "title": "新人训练路径",
        "goal_title": "完成新人训练",
        "reason": f"{title}保存为待发布修订",
        "modules": [
            {
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
        ],
    }


def _path_payload_with_ai_coach(unit_id: str, title: str) -> dict[str, object]:
    payload = _path_payload(unit_id, title)
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

    backfill_response = await async_client.get(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
    )
    assert backfill_response.status_code == 200
    assert backfill_response.json()["data"]["source"] == "unit_backfill"

    save_first_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload(unit.unit_id, "商务技巧第一版"),
    )
    assert save_first_response.status_code == 200
    assert save_first_response.json()["data"]["has_unpublished_revision"] is True

    before_publish_response = await async_client.get(
        "/api/v1/sales-trainer/paths",
        headers=_auth_headers(learner),
    )
    assert before_publish_response.status_code == 200
    before_publish_path = before_publish_response.json()["data"]["items"][0]
    assert before_publish_path["levels"][0]["level_title"] == "商务技巧旧版"

    publish_first_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "第一版生效"},
    )
    assert publish_first_response.status_code == 200
    first_revision_id = publish_first_response.json()["data"]["active_revision_id"]

    save_second_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload(unit.unit_id, "商务技巧第二版"),
    )
    assert save_second_response.status_code == 200
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
async def test_should_reject_ai_coach_high_risk_rollback_for_content_admin(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    content_admin = _user("content_admin")
    unit = _unit("ai-coach-rollback-rbac-unit", "商务技巧")
    test_db.add_all([admin, content_admin, unit])
    await test_db.commit()

    save_first_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload(unit.unit_id, "商务技巧第一版"),
    )
    assert save_first_response.status_code == 200, save_first_response.text
    publish_first_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "第一版生效"},
    )
    assert publish_first_response.status_code == 200, publish_first_response.text
    first_revision_id = publish_first_response.json()["data"]["active_revision_id"]

    save_second_response = await async_client.put(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
        json=_path_payload_with_ai_coach(unit.unit_id, "商务技巧第二版"),
    )
    assert save_second_response.status_code == 200, save_second_response.text
    publish_second_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "第二版生效"},
    )
    assert publish_second_response.status_code == 200, publish_second_response.text

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/rollback",
        headers=_auth_headers(content_admin),
        json={"revision_id": first_revision_id, "reason": "回滚到无 AI 教练配置"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "[PERMISSION_DENIED]"
    assert "prompt_template_id" in body["message"]


@pytest.mark.asyncio
async def test_should_not_echo_fake_ai_coach_prompt_hash_on_admin_save(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    unit = _unit("path-config-ai-coach-admin-save-unit", "商务技巧")
    test_db.add_all([admin, unit])
    await test_db.commit()

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
