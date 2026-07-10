from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from sales_trainer.schemas import (
    CustomerFaqShortAnswerSubmit,
    CustomerFaqShortAnswerSubmitRequest,
    NewcomerLearningTopicConfig,
    NewcomerLearningTopicsPayload,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.customer_faq_parser import parse_customer_faq_material
from sales_trainer.services.customer_faq_short_answer_service import (
    CustomerFaqShortAnswerService,
)
from sales_trainer.services.learning_topic_config_service import (
    CUSTOMER_FAQ_TOPIC_KEY,
    NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
    NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
)
from sales_trainer.services.short_answer_scoring_service import ShortAnswerScoreOutcome

CUSTOMER_FAQ_SAMPLE = """
场景一：初次拜访
1. 问题：石犀科技公司是做什么的？
详细答案：石犀科技是一家专注于数据流动治理的平台提供商，总部位于深圳，团队规模300余人，其中研发人员占比60%。
3. 问题：石犀科技的价格是多少？
详细答案：价格需要根据客户 API 数量、部署范围、服务要求正式报价，不应现场承诺固定折扣。案例：深圳航空先完成 POC 后再确认采购范围。
"""


class FakeCustomerFaqShortAnswerScoringService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def score(self, question, *, answer_text: str):
        self.calls.append(
            {
                "question_id": question.question_id,
                "title": question.title,
                "reference_answer": question.reference_answer,
                "scoring_criteria": question.scoring_criteria,
                "answer_text": answer_text,
            }
        )
        return Result.ok(
            ShortAnswerScoreOutcome(
                score=86,
                passed=True,
                feedback="回答覆盖公司定位、总部和团队规模，表达可以再补充研发占比。",
                reason="covered_core_answer",
                raw_response={"score": 86, "reason": "covered_core_answer"},
                scoring_source="ai_llm",
                scoring_provider="fake",
                scoring_model="unit-test",
                scoring_latency_ms=12,
            )
        )


def _admin() -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"customer-faq-short-answer-{uuid.uuid4().hex[:8]}",
        name="Customer FAQ Admin",
        email=f"customer-faq-short-answer-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_should_score_customer_faq_unit_short_answers_against_card_reference(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    parsed = parse_customer_faq_material(CUSTOMER_FAQ_SAMPLE)
    topic = NewcomerLearningTopicConfig(
        topic_key=CUSTOMER_FAQ_TOPIC_KEY,
        source_module_key="customer_faq",
        content_kind="faq_cards",
        enabled=True,
        title="客户常见问答",
        order_index=1,
        faq_cards=parsed.cards,
        evidence_cases=parsed.evidence_cases,
        learning_units=[
            {
                "unit_key": "company_value",
                "title": "公司与核心价值",
                "description": "学习公司介绍类客户问答。",
                "order_index": 1,
                "enabled": True,
                "source_card_keys": ["customer_faq_q001"],
                "source_chapter_orders": [],
                "capability_keys": ["customer_perspective"],
                "unlock_after_unit_keys": [],
                "require_reading": True,
                "require_quiz": True,
                "require_ai_coach": False,
                "quiz_question_count": 1,
                "quiz_pass_threshold": 80,
                "quiz_allow_retake": True,
                "quiz_max_attempts": None,
                "quiz_question_type_weights": {},
                "allow_skip_reading": True,
                "block_next_until_complete": False,
                "empty_state_message": None,
            }
        ],
        required=False,
        blocks_next=False,
        score_display_policy="quiz_attempt_score",
    )
    test_db.add(admin)
    await test_db.commit()
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        payload=NewcomerLearningTopicsPayload(topics=[topic]).model_dump(mode="json"),
        actor=admin,
        change_class="binding",
        reason="发布客户问答学习专题",
    )
    scorer = FakeCustomerFaqShortAnswerScoringService()

    response = await CustomerFaqShortAnswerService(
        test_db,
        short_answer_scoring_service=scorer,
    ).submit_unit_short_answer_attempt(
        "company_value",
        CustomerFaqShortAnswerSubmitRequest(
            answers=[
                CustomerFaqShortAnswerSubmit(
                    card_key="customer_faq_q001",
                    answer_text="石犀是做数据流动治理的平台，总部在深圳，团队大概 300 多人。",
                )
            ]
        ),
    )

    assert response.learning_unit_key == "company_value"
    assert response.total_score == 86
    assert response.max_score == 100
    assert response.passed is True
    assert response.answers[0].card_key == "customer_faq_q001"
    assert response.answers[0].question == "石犀科技公司是做什么的？"
    assert response.answers[0].feedback.startswith("回答覆盖公司定位")
    assert scorer.calls[0]["reference_answer"] == parsed.cards[0].detailed_answer
    assert scorer.calls[0]["scoring_criteria"]["forbidden_claims"] == [
        "不得把历史案例效果直接承诺给当前客户。"
    ]


@pytest.mark.asyncio
async def test_should_reject_customer_faq_answer_for_card_outside_unit(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    parsed = parse_customer_faq_material(CUSTOMER_FAQ_SAMPLE)
    topic = NewcomerLearningTopicConfig(
        topic_key=CUSTOMER_FAQ_TOPIC_KEY,
        source_module_key="customer_faq",
        content_kind="faq_cards",
        enabled=True,
        title="客户常见问答",
        order_index=1,
        faq_cards=parsed.cards,
        learning_units=[
            {
                "unit_key": "company_value",
                "title": "公司与核心价值",
                "description": "学习公司介绍类客户问答。",
                "order_index": 1,
                "enabled": True,
                "source_card_keys": ["customer_faq_q001"],
                "source_chapter_orders": [],
                "capability_keys": ["customer_perspective"],
                "unlock_after_unit_keys": [],
                "require_reading": True,
                "require_quiz": True,
                "require_ai_coach": False,
                "quiz_question_count": 1,
                "quiz_pass_threshold": 80,
                "quiz_allow_retake": True,
                "quiz_max_attempts": None,
                "quiz_question_type_weights": {},
                "allow_skip_reading": True,
                "block_next_until_complete": False,
                "empty_state_message": None,
            }
        ],
        required=False,
        blocks_next=False,
        score_display_policy="quiz_attempt_score",
    )
    test_db.add(admin)
    await test_db.commit()
    await SalesTrainerAssetRevisionService(test_db).create_published_revision(
        resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
        logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        payload=NewcomerLearningTopicsPayload(topics=[topic]).model_dump(mode="json"),
        actor=admin,
        change_class="binding",
        reason="发布客户问答学习专题",
    )

    with pytest.raises(Exception) as exc_info:
        await CustomerFaqShortAnswerService(
            test_db,
            short_answer_scoring_service=FakeCustomerFaqShortAnswerScoringService(),
        ).submit_unit_short_answer_attempt(
            "company_value",
            CustomerFaqShortAnswerSubmitRequest(
                answers=[
                    CustomerFaqShortAnswerSubmit(
                        card_key="customer_faq_q003",
                        answer_text="直接说一个固定价格。",
                    )
                ]
            ),
        )

    assert getattr(exc_info.value, "code") == "[CUSTOMER_FAQ_QUIZ_CARD_NOT_IN_UNIT]"
