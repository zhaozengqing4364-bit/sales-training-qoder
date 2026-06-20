from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.models import ModelConfig
from common.db.models import PromptTemplate, User
from common.error_handling.result import Result
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    QuestionCategory,
    QuestionItem,
)
from prompt_templates.models import (
    PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION,
)
from sales_trainer.models import SalesTrainerBusinessEtiquetteQuestionDraft
from sales_trainer.schemas import (
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteChapterCapabilityBinding,
    BusinessEtiquetteQuestionDraftApproveRequest,
    BusinessEtiquetteQuestionDraftGenerateRequest,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.business_etiquette_question_draft_service import (
    QUESTION_DRAFT_JSON_RESPONSE_FORMAT,
    BusinessEtiquetteQuestionDraftService,
    BusinessEtiquetteQuestionDraftServiceError,
)
from sales_trainer.services.question_bank.contracts import SALES_TRAINER_QUESTION_SCOPE


class _FakeLlmService:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs: object) -> Result[str]:
        self.calls.append(kwargs)
        return Result.ok(json.dumps(self.payload, ensure_ascii=False))


def _admin() -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-q-draft-admin-{uuid.uuid4().hex[:8]}",
        name="Business Etiquette Question Draft Admin",
        email=f"business-etiquette-q-draft-admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
    )


async def _seed_training_pack(
    test_db: AsyncSession,
    *,
    admin: User,
) -> tuple[LearningContent, LearningChapter]:
    content = LearningContent(
        title="商务礼仪：新人的第一本职业素养手册",
        summary="商务礼仪题目草稿测试资料",
        owner="新人训练路径",
        source="unit-test",
        status="draft",
        content_hash=uuid.uuid4().hex,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(content)
    await test_db.flush()
    chapter = LearningChapter(
        learning_content_id=content.learning_content_id,
        title="第 1 章 商务礼仪的核心原则",
        content="尊重、守时、边界感是商务礼仪的基础。迟到需要提前说明并表达歉意。",
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(chapter)
    await test_db.flush()
    payload = {
        "schema_version": 1,
        "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        "learning_content_id": content.learning_content_id,
        "book_title": content.title,
        "original_chapter_count": 1,
        "original_chapters": [
            {"title": chapter.title, "order_index": 1, "line_number": 1}
        ],
    }
    await SalesTrainerAssetRevisionService(test_db).save_working_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=payload,
        actor=admin,
        change_class="semantic",
        reason="导入商务礼仪测试资料",
    )
    await test_db.commit()
    await _save_capability_snapshot(test_db, admin=admin)
    return content, chapter


async def _save_capability_snapshot(
    test_db: AsyncSession,
    *,
    admin: User,
) -> None:
    seed = default_business_etiquette_capability_snapshot()
    capabilities = [
        BusinessEtiquetteCapabilityConfig.model_validate(item)
        for item in seed["capabilities"]
    ]
    chapter_bindings = [
        BusinessEtiquetteChapterCapabilityBinding(
            chapter_order=1,
            capability_keys=["respect_boundaries"],
        )
    ]
    from sales_trainer.services.business_etiquette_capability_service import (
        BusinessEtiquetteCapabilityService,
    )

    await BusinessEtiquetteCapabilityService(test_db).save_snapshot(
        capabilities=capabilities,
        chapter_bindings=chapter_bindings,
        actor=admin,
        reason="保存商务礼仪能力点测试快照",
    )


async def _seed_prompt_template(test_db: AsyncSession) -> PromptTemplate:
    template = PromptTemplate(
        id=str(uuid.uuid4()),
        name="商务礼仪题目草稿生成",
        prompt_type="scoring",
        business_purpose=PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION,
        category="sales_trainer",
        template=(
            "请基于 {{ chapter_title }} 和 {{ chapter_content }} 生成题目。"
            "能力点：{{ capabilities_json }}。"
            "题型：{{ question_types_json }}。"
            "数量：{{ draft_count }}。"
            "输出：{{ output_schema }}。"
        ),
        variables=[
            "chapter_title",
            "chapter_content",
            "capabilities_json",
            "question_types_json",
            "draft_count",
            "output_schema",
        ],
        is_active=True,
    )
    test_db.add(template)
    await test_db.commit()
    return template


async def _seed_generic_prompt_template(test_db: AsyncSession) -> PromptTemplate:
    template = PromptTemplate(
        id=str(uuid.uuid4()),
        name="Sales Conversation Summary",
        prompt_type="summary",
        category="sales",
        template="Summarize {{ conversation }}.",
        variables=["conversation"],
        is_active=True,
    )
    test_db.add(template)
    await test_db.commit()
    return template


async def _seed_structured_question_prompt_template(
    test_db: AsyncSession,
) -> PromptTemplate:
    template = PromptTemplate(
        id=str(uuid.uuid4()),
        name="自定义章节生成模板 A",
        prompt_type="stage",
        business_purpose=PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION,
        category="sales_trainer_ai_coach",
        template=(
            "请基于 {{ chapter_title }} 和 {{ chapter_content }} 生成草稿。"
            "{{ capabilities_json }} {{ question_types_json }} {{ draft_count }} {{ output_schema }}"
        ),
        variables=[
            "chapter_title",
            "chapter_content",
            "capabilities_json",
            "question_types_json",
            "draft_count",
            "output_schema",
        ],
        is_active=True,
    )
    test_db.add(template)
    await test_db.commit()
    return template


async def _seed_misclassified_ai_coach_question_prompt_template(
    test_db: AsyncSession,
) -> PromptTemplate:
    template = PromptTemplate(
        id=str(uuid.uuid4()),
        name="新人训练路径商务技巧 AI 教练题目生成 v1",
        prompt_type="stage",
        business_purpose=PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION,
        category="sales_trainer_ai_coach",
        template=(
            "你正在生成第 {{ turn_number }} 轮互动题。"
            "允许题型：{{ allowed_interaction_types | join(', ') }}。"
            "请输出 {\"schema_version\":\"ai_coach_interaction_v1\"}。"
        ),
        variables=[
            "turn_number",
            "allowed_interaction_types",
            "module_key",
            "previous_turns",
        ],
        is_active=True,
    )
    test_db.add(template)
    await test_db.commit()
    return template


async def _seed_missing_variable_question_prompt_template(
    test_db: AsyncSession,
) -> PromptTemplate:
    template = PromptTemplate(
        id=str(uuid.uuid4()),
        name="商务礼仪缺变量题目生成",
        prompt_type="scoring",
        business_purpose=PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION,
        category="business_etiquette",
        template="请基于 {{ chapter_content }} 和 {{ unsupported_runtime_var }} 生成题目。",
        variables=["chapter_content", "unsupported_runtime_var"],
        is_active=True,
    )
    test_db.add(template)
    await test_db.commit()
    return template


def _generate_request(template: PromptTemplate) -> BusinessEtiquetteQuestionDraftGenerateRequest:
    return BusinessEtiquetteQuestionDraftGenerateRequest(
        chapter_order=1,
        prompt_template_id=str(template.id),
        question_types=["single_choice", "short_answer"],
        draft_count=2,
        capability_keys=["respect_boundaries"],
        model_config={
            "provider": "openai",
            "base_url": "https://example.com/v1",
            "model_name": "unit-test",
        },
    )


@pytest.mark.asyncio
async def test_should_generate_business_etiquette_question_drafts(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_prompt_template(test_db)
    llm = _FakeLlmService(
        {
            "drafts": [
                {
                    "question_type": "single_choice",
                    "title": "迟到处理",
                    "stem": "商务拜访即将迟到时，最合适的做法是什么？",
                    "options": [
                        {"value": "A", "label": "提前说明并表达歉意"},
                        {"value": "B", "label": "到场后再随口解释"},
                    ],
                    "correct_answer": "A",
                    "explanation": "守时和尊重边界是商务礼仪基础。",
                    "capability_keys": ["respect_boundaries"],
                    "source_excerpt": "尊重、守时、边界感是商务礼仪的基础。",
                },
                {
                    "question_type": "short_answer",
                    "title": "边界感说明",
                    "stem": "请说明商务礼仪中边界感的重要性。",
                    "reference_answer": "边界感体现尊重，能降低沟通冒犯和合作摩擦。",
                    "capability_keys": ["respect_boundaries"],
                },
            ]
        }
    )

    result = await BusinessEtiquetteQuestionDraftService(
        test_db,
        llm_service=llm,
    ).generate_drafts(
        _generate_request(template),
        actor=admin,
        trace_id="trace-question-draft-generate",
    )

    assert result.total == 2
    assert result.items[0].status == "pending_review"
    assert result.items[0].prompt_template_id == str(template.id)
    assert result.items[0].capability_keys == ["respect_boundaries"]
    assert llm.calls
    assert llm.calls[0]["response_format"] == QUESTION_DRAFT_JSON_RESPONSE_FORMAT
    persisted = await test_db.execute(select(SalesTrainerBusinessEtiquetteQuestionDraft))
    assert len(persisted.scalars().all()) == 2


@pytest.mark.asyncio
async def test_should_reject_non_question_generation_prompt_template(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_generic_prompt_template(test_db)

    with pytest.raises(BusinessEtiquetteQuestionDraftServiceError) as error:
        await BusinessEtiquetteQuestionDraftService(
            test_db,
            llm_service=_FakeLlmService({"drafts": []}),
        ).generate_drafts(
            _generate_request(template),
            actor=admin,
            trace_id="trace-question-draft-prompt-purpose",
        )

    assert error.value.code == "[BUSINESS_ETIQUETTE_QUESTION_PROMPT_PURPOSE_MISMATCH]"
    persisted = await test_db.execute(select(SalesTrainerBusinessEtiquetteQuestionDraft))
    assert persisted.scalars().all() == []


@pytest.mark.asyncio
async def test_should_accept_structured_question_prompt_without_keyword_name(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_structured_question_prompt_template(test_db)
    llm = _FakeLlmService(
        {
            "drafts": [
                {
                    "question_type": "single_choice",
                    "title": "守时礼仪",
                    "stem": "商务拜访即将迟到时，最合适的做法是什么？",
                    "options": [
                        {"value": "A", "label": "提前说明并表达歉意"},
                        {"value": "B", "label": "到场后再解释"},
                    ],
                    "correct_answer": "A",
                    "capability_keys": ["respect_boundaries"],
                }
            ]
        }
    )

    result = await BusinessEtiquetteQuestionDraftService(
        test_db,
        llm_service=llm,
    ).generate_drafts(
        _generate_request(template).model_copy(
            update={"question_types": ["single_choice"], "draft_count": 1}
        ),
        actor=admin,
        trace_id="trace-structured-question-prompt-purpose",
    )

    assert result.total == 1
    assert result.items[0].prompt_template_id == str(template.id)


@pytest.mark.asyncio
async def test_should_reject_misclassified_ai_coach_interaction_prompt(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_misclassified_ai_coach_question_prompt_template(test_db)

    with pytest.raises(BusinessEtiquetteQuestionDraftServiceError) as error:
        await BusinessEtiquetteQuestionDraftService(
            test_db,
            llm_service=_FakeLlmService({"drafts": []}),
        ).generate_drafts(
            _generate_request(template),
            actor=admin,
            trace_id="trace-misclassified-ai-coach-prompt",
        )

    assert error.value.code == "[BUSINESS_ETIQUETTE_QUESTION_PROMPT_SCHEMA_MISMATCH]"
    assert "AI 教练互动卡片模板" in error.value.message
    persisted = await test_db.execute(select(SalesTrainerBusinessEtiquetteQuestionDraft))
    assert persisted.scalars().all() == []


@pytest.mark.asyncio
async def test_should_explain_missing_question_prompt_variables(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_missing_variable_question_prompt_template(test_db)

    with pytest.raises(BusinessEtiquetteQuestionDraftServiceError) as error:
        await BusinessEtiquetteQuestionDraftService(
            test_db,
            llm_service=_FakeLlmService({"drafts": []}),
        ).generate_drafts(
            _generate_request(template),
            actor=admin,
            trace_id="trace-question-prompt-missing-vars",
        )

    assert error.value.code == (
        "[BUSINESS_ETIQUETTE_QUESTION_PROMPT_COMPILE_FAILED:"
        "[PROMPT_CONTRACT_MISSING_VARIABLES:unsupported_runtime_var]]"
    )
    assert "unsupported_runtime_var" in error.value.message
    assert "商务礼仪题目草稿生成 v1" in error.value.message
    persisted = await test_db.execute(select(SalesTrainerBusinessEtiquetteQuestionDraft))
    assert persisted.scalars().all() == []


@pytest.mark.asyncio
async def test_should_use_selected_llm_model_config_for_generation(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_prompt_template(test_db)
    model_config = ModelConfig(
        id=str(uuid.uuid4()),
        name="商务礼仪出题专用模型",
        model_type="llm",
        provider="openai",
        base_url="https://selected-model.example/v1",
        api_key_encrypted="encrypted-key",
        model_name="selected-question-model",
        extra_config={"temperature": 0.1},
        is_active=True,
    )
    test_db.add(model_config)
    await test_db.commit()
    llm = _FakeLlmService(
        {
            "drafts": [
                {
                    "question_type": "single_choice",
                    "title": "守时礼仪",
                    "stem": "商务拜访即将迟到时，最合适的做法是什么？",
                    "options": [
                        {"value": "A", "label": "提前说明并表达歉意"},
                        {"value": "B", "label": "到场后再解释"},
                    ],
                    "correct_answer": "A",
                    "capability_keys": ["respect_boundaries"],
                }
            ]
        }
    )
    selected_configs: list[ModelConfig] = []

    def fake_create_llm_service(config: ModelConfig) -> _FakeLlmService:
        selected_configs.append(config)
        return llm

    monkeypatch.setattr(
        "sales_trainer.services.business_etiquette_question_draft_service."
        "create_llm_service",
        fake_create_llm_service,
    )

    result = await BusinessEtiquetteQuestionDraftService(test_db).generate_drafts(
        BusinessEtiquetteQuestionDraftGenerateRequest(
            chapter_order=1,
            prompt_template_id=str(template.id),
            question_types=["single_choice"],
            draft_count=1,
            capability_keys=["respect_boundaries"],
            model_config={"model_config_id": model_config.id},
        ),
        actor=admin,
        trace_id="trace-selected-question-model",
    )

    assert result.total == 1
    assert selected_configs == [model_config]
    assert llm.calls
    assert result.items[0].llm_model_config["model_config_id"] == model_config.id
    assert result.items[0].llm_model_config["model_name"] == "selected-question-model"


@pytest.mark.asyncio
async def test_should_reject_invalid_ai_output_without_partial_draft_write(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_prompt_template(test_db)
    llm = _FakeLlmService(
        {
            "drafts": [
                {
                    "question_type": "single_choice",
                    "title": "无选项题目",
                    "stem": "这道题缺少选项。",
                    "correct_answer": "A",
                    "capability_keys": ["respect_boundaries"],
                }
            ]
        }
    )

    with pytest.raises(BusinessEtiquetteQuestionDraftServiceError) as error:
        await BusinessEtiquetteQuestionDraftService(
            test_db,
            llm_service=llm,
        ).generate_drafts(
            _generate_request(template),
            actor=admin,
        )

    assert error.value.code == "[BUSINESS_ETIQUETTE_QUESTION_GENERATION_INVALID_SCHEMA]"
    persisted = await test_db.execute(select(SalesTrainerBusinessEtiquetteQuestionDraft))
    assert persisted.scalars().all() == []


@pytest.mark.asyncio
async def test_should_convert_approved_draft_to_formal_question_without_publishing(
    test_db: AsyncSession,
) -> None:
    admin = _admin()
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack(test_db, admin=admin)
    template = await _seed_prompt_template(test_db)
    category = QuestionCategory(
        name="商务礼仪",
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        order_index=1,
        created_by=str(admin.user_id),
        updated_by=str(admin.user_id),
    )
    test_db.add(category)
    await test_db.commit()
    llm = _FakeLlmService(
        {
            "drafts": [
                {
                    "question_type": "single_choice",
                    "title": "迟到处理",
                    "stem": "商务拜访即将迟到时，最合适的做法是什么？",
                    "options": [
                        {"value": "A", "label": "提前说明并表达歉意"},
                        {"value": "B", "label": "到场后再解释"},
                    ],
                    "correct_answer": "A",
                    "capability_keys": ["respect_boundaries"],
                }
            ]
        }
    )
    service = BusinessEtiquetteQuestionDraftService(test_db, llm_service=llm)
    generated = await service.generate_drafts(
        _generate_request(template).model_copy(update={"draft_count": 1}),
        actor=admin,
    )

    approved = await service.approve_draft(
        generated.items[0].draft_id,
        BusinessEtiquetteQuestionDraftApproveRequest(
            category_id=str(category.category_id),
            review_notes="题干和答案可用",
        ),
        actor=admin,
        trace_id="trace-question-draft-approve",
    )

    assert approved.status == "converted"
    assert approved.question_id is not None
    question = await test_db.get(QuestionItem, approved.question_id)
    assert question is not None
    assert question.status == "draft"
    assert question.usage_scope == SALES_TRAINER_QUESTION_SCOPE
    assert "business_etiquette" in question.tags
    assert "capability:respect_boundaries" in question.tags
    assert question.scoring_criteria["question_type"] == "single_choice"
    assert question.scoring_criteria["correct_answer"] == "A"
