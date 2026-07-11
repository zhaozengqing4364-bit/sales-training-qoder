from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import SalesTrainerAiCoachSession, SalesTrainerUnit
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    CAPABILITY_SNAPSHOT_KEY,
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.learning_topic_config_service import (
    BUSINESS_ETIQUETTE_TOPIC_KEY,
    BUSINESS_SKILLS_SOURCE_MODULE_KEY,
    NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
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
        wechat_user_id=f"business-etiquette-release-api-{role}-{suffix}",
        name=f"Business Etiquette Release API {role}",
        email=f"business-etiquette-release-api-{role}-{suffix}@example.com",
        role=role,
    )


def _capability_snapshot() -> dict[str, object]:
    snapshot = default_business_etiquette_capability_snapshot()
    return {
        "schema_version": 1,
        "capabilities": [
            {**item, "status": "published"}
            for item in snapshot["capabilities"]
        ],
        "chapter_bindings": [{
            "chapter_order": 1,
            "capability_keys": ["respect_boundaries"],
        }],
    }


def _training_pack_payload(*, chapter_hash: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        "book_title": "商务礼仪",
        "original_chapter_count": 1,
        "original_chapters": [{
            "title": "第一章：礼仪的底层逻辑",
            "order_index": 1,
            "content_hash": chapter_hash,
        }],
        CAPABILITY_SNAPSHOT_KEY: _capability_snapshot(),
    }


def _ai_coach_config() -> dict[str, object]:
    return {
        "enabled": True,
        "chat_enabled": True,
        "streaming_enabled": True,
        "prompt_template_id": "11111111-1111-1111-1111-111111111111",
        "session_start_behavior": "welcome_only",
        "auto_advance_enabled": False,
    }


def _learning_unit() -> dict[str, object]:
    return {
        "unit_key": "trust_foundation",
        "title": "职业信任底座",
        "description": "尊重分寸、第一印象。",
        "order_index": 1,
        "enabled": True,
        "source_chapter_orders": [1],
        "capability_keys": ["respect_boundaries"],
        "unlock_after_unit_keys": [],
        "require_reading": True,
        "require_quiz": True,
        "require_ai_coach": True,
        "quiz_question_count": 1,
        "quiz_pass_threshold": None,
        "quiz_allow_retake": True,
        "quiz_max_attempts": None,
        "quiz_question_type_weights": {"single_choice": 1},
        "allow_skip_reading": False,
        "block_next_until_complete": True,
        "empty_state_message": None,
    }


async def _seed_active_path(
    test_db: AsyncSession,
    *,
    admin: User,
    learner_level_required: list[str] | None = None,
) -> None:
    unit = SalesTrainerUnit(
        unit_id=f"be-release-{uuid.uuid4().hex[:8]}",
        name="商务礼仪考试",
        unit_type="quiz",
        status="published",
        config={},
    )
    test_db.add(unit)
    await test_db.flush()
    payload = {
        "path_key": NEWCOMER_PATH_LOGICAL_ID,
        "title": "新人训练路径",
        "goal_title": "完成商务礼仪训练",
        "description": None,
        "enabled": True,
        "modules": [
            {
                "module_key": "business_skills",
                "module_type": "article_exam",
                "enabled": True,
                "order_index": 1,
                "title": "商务礼仪",
                "description": "按小单元完成商务礼仪训练。",
                "target_unit_id": unit.unit_id,
                "learning_content_id": None,
                "learner_level_required": learner_level_required or [],
                "exam_paper_id": None,
                "material_id": None,
                "material_version_id": None,
                "scoring_prompt_id": None,
                "disabled_reason": None,
                "unlock_after_unit_ids": [],
                "completion_rule": "passed",
                "primary_action_label": "开始训练",
                "retry_action_label": None,
                "review_action_label": None,
                "guidance_templates": {},
                "ai_coach": _ai_coach_config(),
                "learning_units": [_learning_unit()],
            }
        ],
    }
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload=payload,
        actor=admin,
        change_class="binding",
        reason="发布商务礼仪路径配置",
    )
    await test_db.commit()


async def _seed_active_learning_topic(
    test_db: AsyncSession,
    *,
    admin: User,
) -> None:
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        payload={
            "schema_version": "newcomer_learning_topics_v1",
            "topics": [
                {
                    "topic_key": BUSINESS_ETIQUETTE_TOPIC_KEY,
                    "source_module_key": BUSINESS_SKILLS_SOURCE_MODULE_KEY,
                    "content_kind": "article",
                    "enabled": True,
                    "title": "商务礼仪规范",
                    "order_index": 1,
                    "ai_coach": _ai_coach_config(),
                    "learning_units": [_learning_unit()],
                    "required": False,
                    "blocks_next": False,
                    "score_display_policy": "quiz_attempt_score",
                }
            ],
        },
        actor=admin,
        change_class="binding",
        reason="发布商务礼仪重练学习专题",
    )
    await test_db.commit()


async def _seed_training_pack_revisions(
    test_db: AsyncSession,
    *,
    admin: User,
) -> None:
    service = SalesTrainerAssetRevisionService(test_db)
    active = await service.create_published_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=_training_pack_payload(chapter_hash="hash-v1"),
        actor=admin,
        change_class="semantic",
        reason="发布商务礼仪训练包 v1",
    )
    await service.save_working_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=_training_pack_payload(chapter_hash="hash-v2"),
        actor=admin,
        change_class="semantic",
        source_revision_id=active.revision.revision_id,
        reason="生成商务礼仪训练包 v2",
    )
    await test_db.commit()


@pytest.mark.asyncio
async def test_should_preview_and_publish_business_etiquette_release_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    await _seed_active_path(test_db, admin=admin)
    await _seed_training_pack_revisions(test_db, admin=admin)

    impact_response = await async_client.get(
        "/api/v1/admin/newcomer-training/business-etiquette/release-impact",
        headers=_auth_headers(admin),
        params={"training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY},
    )

    assert impact_response.status_code == 200, impact_response.text
    impact = impact_response.json()["data"]
    assert impact["summary"]["changed_chapter_count"] == 1
    assert impact["summary"]["impacted_learning_unit_count"] == 1
    assert impact["impacted_learning_units"][0]["unit_key"] == "trust_foundation"
    assert impact["config"]["default_strategy"] == "future_learners_only"

    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/business-etiquette/release",
        headers=_auth_headers(admin),
        json={
            "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
            "strategy": "future_learners_only",
            "assigned_user_ids": [],
            "reason": "发布商务礼仪训练包 v2",
        },
    )

    assert publish_response.status_code == 200, publish_response.text
    published = publish_response.json()["data"]
    assert published["active_revision_no"] == 2
    assert published["strategy"] == "future_learners_only"
    assert published["created_session_ids"] == []


@pytest.mark.asyncio
async def test_should_start_voluntary_retraining_session_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(test_db, admin=admin)
    await _seed_active_learning_topic(test_db, admin=admin)

    response = await async_client.post(
        "/api/v1/newcomer-training/business-etiquette/retraining-sessions",
        headers=_auth_headers(learner),
        json={"reason": "自愿重练新版商务礼仪"},
    )

    assert response.status_code == 200, response.text
    session_id = response.json()["data"]["session_id"]
    session = await test_db.scalar(
        select(SalesTrainerAiCoachSession).where(
            SalesTrainerAiCoachSession.session_id == session_id
        )
    )
    assert session is not None
    assert session.user_id == str(learner.user_id)
    assert session.module_key == "business_skills"


@pytest.mark.asyncio
async def test_should_fail_closed_voluntary_retraining_when_module_locked(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_active_path(
        test_db,
        admin=admin,
        learner_level_required=["ready"],
    )

    response = await async_client.post(
        "/api/v1/newcomer-training/business-etiquette/retraining-sessions",
        headers=_auth_headers(learner),
        json={"reason": "尝试绕过锁定模块"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"] == "[SALES_TRAINER_UNIT_NOT_FOUND]"
    session = await test_db.scalar(select(SalesTrainerAiCoachSession))
    assert session is None


@pytest.mark.asyncio
async def test_should_reject_content_admin_retraining_assignment(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    content_admin = _user("content_admin")
    learner = _user("user")
    test_db.add_all([content_admin, learner])
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/business-etiquette/retraining-assignments",
        headers=_auth_headers(content_admin),
        json={
            "user_ids": [str(learner.user_id)],
            "reason": "内容管理员不得指定学员重练",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"] == "[ROLE_REQUIRED]"
    session = await test_db.scalar(select(SalesTrainerAiCoachSession))
    assert session is None
