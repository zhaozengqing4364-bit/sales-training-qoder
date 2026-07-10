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
from sales_trainer.services.customer_faq_parser import parse_customer_faq_material
from sales_trainer.services.learning_topic_config_service import (
    BUSINESS_ETIQUETTE_TOPIC_KEY,
    CUSTOMER_FAQ_AUDIO_SCENARIO_KEY,
    CUSTOMER_FAQ_TOPIC_KEY,
    NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
    NewcomerLearningTopicConfigService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)
from sales_trainer.services.training_journey_service import TrainingJourneyService

CUSTOMER_FAQ_SAMPLE = """
场景一：初次拜访
3. 问题：石犀科技的价格是多少？
详细答案：价格需要根据客户 API 数量、部署范围、服务要求正式报价，不应现场承诺固定折扣。案例：深圳航空先完成 POC 后再确认采购范围。
10. 问题：石犀和 WAF 是替代关系吗？
详细答案：石犀不是简单替代 WAF，而是补齐 API 资产发现、数据流动治理、风险审计和业务侧解释能力。
23. 问题：已经有 WAF 了还需要石犀吗？
详细答案：WAF 侧重流量防护，石犀侧重 API 资产、敏感数据、访问行为和合规治理，两者可以协同。
场景二：部署架构
35. 问题：多云环境能统一治理吗？
详细答案：可以按租户、业务系统、云账号和 API 资产统一纳管，但具体网络接入和权限边界需要售前确认。
"""


def _user(role: str = "admin") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"learning-topic-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Learning Topic {role}",
        email=f"learning-topic-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )


def _business_unit(
    unit_key: str = "trust_foundation",
) -> BusinessEtiquetteTrainingUnitConfig:
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


def test_parse_customer_faq_material_extracts_cards_risks_and_duplicates() -> None:
    parsed = parse_customer_faq_material(CUSTOMER_FAQ_SAMPLE)

    assert parsed.total_questions == 4
    assert parsed.high_risk_count == 1
    assert parsed.escalation_count == 1
    assert [group.group_key for group in parsed.duplicate_groups] == ["waf_boundary"]
    assert parsed.duplicate_groups[0].card_keys == [
        "customer_faq_q010",
        "customer_faq_q023",
    ]
    price_card = next(
        card for card in parsed.cards if card.card_key == "customer_faq_q003"
    )
    assert price_card.category == "商务政策"
    assert price_card.difficulty_level == "high_risk"
    assert price_card.escalation_required is True
    assert (
        "不得给出固定价格或折扣承诺，需按项目范围正式报价。"
        in price_card.forbidden_claims
    )
    assert parsed.evidence_cases[0].title == "深圳航空"


@pytest.mark.asyncio
async def test_generate_customer_faq_topic_draft_from_material(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    service = NewcomerLearningTopicConfigService(test_db)
    await service.generate_customer_faq_draft(
        raw_text=CUSTOMER_FAQ_SAMPLE,
        actor=admin,
    )
    response = await service.get_config()

    assert response["management_entry"] == "/admin/sales-trainer/learning-topics"
    assert response["active_revision_id"] is None
    assert response["working_revision_id"] is not None
    topic = next(
        item
        for item in response["payload"]["topics"]
        if item["topic_key"] == CUSTOMER_FAQ_TOPIC_KEY
    )
    assert topic["source_module_key"] == "customer_faq"
    assert topic["content_kind"] == "faq_cards"
    assert topic["audio_scenario_key"] == CUSTOMER_FAQ_AUDIO_SCENARIO_KEY
    assert topic["required"] is False
    assert topic["blocks_next"] is False
    assert len(topic["faq_cards"]) == 4
    assert topic["duplicate_groups"][0]["group_key"] == "waf_boundary"
    assert topic["evidence_cases"][0]["title"] == "深圳航空"
    assert len(topic["learning_units"]) == 8
    assert any(unit["source_card_keys"] for unit in topic["learning_units"])


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

    assert {module["module_key"] for module in journey["modules"]} == {
        "ppt_explanation"
    }
    assert journey["overall_progress"]["total_modules"] == 1
    assert journey["training_stage"] == "not_started"
    assert journey["learning_topics"][0]["topic_key"] == BUSINESS_ETIQUETTE_TOPIC_KEY
    assert journey["learning_topics"][0]["status"] == "needs_remediation"
    assert journey["learning_topics"][0]["units"][0]["score"] == 60.0
    assert journey["learning_topics"][0]["units"][0]["max_score"] == 100.0
