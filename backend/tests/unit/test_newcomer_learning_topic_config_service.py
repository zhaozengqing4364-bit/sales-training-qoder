from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import LearningContent
from sales_trainer.models import (
    SalesTrainerBusinessEtiquetteQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    BusinessEtiquetteTrainingUnitConfig,
    NewcomerLearningTopicConfig,
    NewcomerLearningTopicsPayload,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.learning_topic_config_service import (
    BUSINESS_ETIQUETTE_TOPIC_KEY,
    NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
    NewcomerLearningTopicConfigService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.training_journey_service import TrainingJourneyService


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"learning-topic-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Learning Topic {role}",
        email=f"learning-topic-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )


def _business_unit(unit_key: str = "trust_foundation") -> BusinessEtiquetteTrainingUnitConfig:
    return BusinessEtiquetteTrainingUnitConfig(
        unit_key=unit_key,
        title="职业信任底座",
        order_index=1,
        enabled=True,
        source_chapter_orders=[1],
        capability_keys=["respect_boundaries"],
        require_reading=True,
        require_quiz=True,
        require_ai_coach=False,
        quiz_question_count=3,
        quiz_pass_threshold=80,
        quiz_allow_retake=True,
        quiz_question_type_weights={},
        block_next_until_complete=False,
    )


async def _publish_path_with_business_skills(
    test_db: AsyncSession,
    *,
    admin: User,
    ppt_unit_id: str = "learning-topic-ppt-unit",
    learning_content_id: str = "learning-topic-content",
) -> str:
    test_db.add(
        SalesTrainerUnit(
            unit_id=ppt_unit_id,
            name="PPT 讲解录音",
            unit_type="audio_scoring",
            status="published",
            config={},
        )
    )
    result = await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
        logical_id=NEWCOMER_PATH_LOGICAL_ID,
        payload={
            "path_key": NEWCOMER_PATH_LOGICAL_ID,
            "title": "新人训练路径",
            "enabled": True,
            "modules": [
                {
                    "module_key": "ppt_explanation",
                    "module_type": "audio_scoring",
                    "enabled": True,
                    "order_index": 1,
                    "title": "PPT 讲解录音",
                    "target_unit_id": ppt_unit_id,
                    "completion_rule": "passed",
                },
                {
                    "module_key": "business_skills",
                    "module_type": "article_exam",
                    "enabled": True,
                    "order_index": 2,
                    "title": "商务技巧",
                    "learning_content_id": learning_content_id,
                    "completion_rule": "passed",
                    "learning_units": [_business_unit().model_dump(mode="json")],
                },
            ],
        },
        actor=admin,
        change_class="binding",
        reason="发布含商务技巧的路径",
    )
    await test_db.commit()
    return str(result.revision.revision_id)


@pytest.mark.asyncio
async def test_generate_learning_topic_draft_from_active_business_skills(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    content = LearningContent(
        learning_content_id="learning-topic-content",
        title="商务礼仪规范",
        summary="学习内容",
        owner="新人训练路径",
        source="unit_test",
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([admin, content])
    await test_db.commit()
    await _publish_path_with_business_skills(test_db, admin=admin)

    service = NewcomerLearningTopicConfigService(test_db)
    await service.generate_business_etiquette_draft(actor=admin)
    response = await service.get_config()

    assert response["active_revision_id"] is None
    assert response["working_revision_id"] is not None
    topic = response["payload"]["topics"][0]
    assert topic["topic_key"] == BUSINESS_ETIQUETTE_TOPIC_KEY
    assert topic["title"] == "商务礼仪规范"
    assert topic["source_module_key"] == "business_skills"
    assert topic["required"] is False
    assert topic["blocks_next"] is False
    assert topic["score_display_policy"] == "quiz_attempt_score"


@pytest.mark.asyncio
async def test_learning_topic_is_projected_separately_and_not_path_blocking(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    content = LearningContent(
        learning_content_id="learning-topic-content",
        title="商务礼仪规范",
        summary="学习内容",
        owner="新人训练路径",
        source="unit_test",
        status="published",
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add_all([admin, learner, content])
    await test_db.commit()
    await _publish_path_with_business_skills(test_db, admin=admin)
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        payload=NewcomerLearningTopicsPayload(
            topics=[
                NewcomerLearningTopicConfig(
                    topic_key=BUSINESS_ETIQUETTE_TOPIC_KEY,
                    source_module_key="business_skills",
                    enabled=True,
                    title="商务礼仪规范",
                    order_index=1,
                    learning_content_id=content.learning_content_id,
                    learning_units=[_business_unit()],
                    required=False,
                    blocks_next=False,
                    score_display_policy="quiz_attempt_score",
                )
            ]
        ).model_dump(mode="json"),
        actor=admin,
        change_class="binding",
        reason="发布学习专题",
    )
    test_db.add(
        SalesTrainerBusinessEtiquetteQuizAttempt(
            training_pack_key="default_business_etiquette",
            learning_unit_key="trust_foundation",
            learning_unit_title="职业信任底座",
            user_id=str(learner.user_id),
            total_score=Decimal("60"),
            max_score=Decimal("100"),
            passed=False,
            status="scored",
        )
    )
    await test_db.commit()

    journey = await TrainingJourneyService(test_db).get_learner_journey(
        str(learner.user_id),
        viewer=learner,
    )

    assert {module["module_key"] for module in journey["modules"]} == {"ppt_explanation"}
    assert journey["overall_progress"]["total_modules"] == 1
    assert journey["training_stage"] == "not_started"
    assert journey["learning_topics"][0]["topic_key"] == BUSINESS_ETIQUETTE_TOPIC_KEY
    assert journey["learning_topics"][0]["status"] == "needs_remediation"
    assert journey["learning_topics"][0]["units"][0]["score"] == 60.0
    assert journey["learning_topics"][0]["units"][0]["max_score"] == 100.0
