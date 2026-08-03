from __future__ import annotations

import pytest

import foundation_task_bootstrap as task_bootstrap
from ai_coach.task_definitions import (
    CoachAnswerEvaluationTaskHandler,
    CoachAssistanceTaskHandler,
    CoachCardGenerationTaskHandler,
)
from ai_coach.task_types import (
    COACH_ANSWER_EVALUATION_TASK_TYPE,
    COACH_ASSISTANCE_TASK_TYPE,
    COACH_CARD_GENERATION_TASK_TYPE,
)
from ai_platform import (
    GovernedAIInvocationService,
    PublishedPromptRevisionSnapshot,
    StrictPromptCompiler,
    compute_prompt_revision_content_hash,
)
from common.db.session import AsyncSessionLocal
from foundation_ai_composition import build_foundation_ai_invocation_factory
from learning.ai_schemas import build_learning_ai_schema_registry
from learning.contracts import QuestionGenerationRequest
from learning.task_definitions import (
    QuestionGenerationTaskHandler,
    ShortAnswerScoringTaskHandler,
)
from task_runtime import TaskRegistry


@pytest.mark.parametrize(
    ("provider", "base_url"),
    [
        ("openai", "https://api.openai.com/v1"),
        (
            "alibaba",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    ],
)
def test_foundation_ai_factory_builds_real_governed_composition(
    provider: str,
    base_url: str,
) -> None:
    factory = build_foundation_ai_invocation_factory(
        session_factory=AsyncSessionLocal,
        effective_config={
            "provider": provider,
            "base_url": base_url,
            "api_key": "test-only-key",
            "model_name": "ignored-in-favor-of-published-route",
            "extra_config": {"currency": "CNY"},
        },
    )

    assert isinstance(factory(), GovernedAIInvocationService)
    assert factory() is factory()


@pytest.mark.parametrize(
    "config",
    [
        None,
        {
            "provider": "openai",
            "base_url": "http://127.0.0.1:9999/v1",
            "api_key": "secret",
        },
        {
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "api_key": "secret",
        },
    ],
)
def test_foundation_ai_factory_fails_closed_for_missing_or_unsafe_config(
    config,
) -> None:
    with pytest.raises(RuntimeError):
        build_foundation_ai_invocation_factory(
            session_factory=AsyncSessionLocal,
            effective_config=config,
        )


def test_learning_ai_contract_accepts_real_compiler_hash_and_context_schemas() -> None:
    template = (
        "学习单元：{{ learning_unit_json }}\n"
        "来源：{{ source_anchors_json }}\n"
        "生成数量：{{ requested_count }}"
    )
    variables = (
        "learning_unit_json",
        "requested_count",
        "source_anchors_json",
    )
    prompt = PublishedPromptRevisionSnapshot(
        template_id="question-generation",
        business_purpose="newcomer_question_generation",
        revision_id="prompt-revision-1",
        revision_no=1,
        status="published",
        template=template,
        variables=variables,
        input_schema_version="question-generation-input-v1",
        output_schema_version="question-generation-output-v1",
        content_hash=compute_prompt_revision_content_hash(
            template_id="question-generation",
            business_purpose="newcomer_question_generation",
            revision_id="prompt-revision-1",
            revision_no=1,
            template=template,
            variables=variables,
            input_schema_version="question-generation-input-v1",
            output_schema_version="question-generation-output-v1",
        ),
    )
    compiled = StrictPromptCompiler().compile(
        revision=prompt,
        variables={
            "learning_unit_json": '{"title":"理解客户风险"}',
            "requested_count": 2,
            "source_anchors_json": '[{"label":"风险澄清方法"}]',
        },
        runtime_consumer="learning.question_generation.v1",
        model_routing_revision_id="routing-revision-1",
    )

    request = QuestionGenerationRequest(
        source_revision_id="source-revision-1",
        learning_unit_revision_id="learning-unit-revision-1",
        requested_count=2,
        prompt_template_id=prompt.template_id,
        prompt_revision_id=prompt.revision_id,
        prompt_contract_hash=compiled.contract_hash,
        model_routing_profile_id="question-generation-models",
        model_routing_revision_id="routing-revision-1",
        input_schema_version=prompt.input_schema_version,
        output_schema_version=prompt.output_schema_version,
    )
    assert request.prompt_contract_hash.startswith("sha256:")
    assert len(request.prompt_contract_hash) == 71

    schemas = build_learning_ai_schema_registry()
    question_input = schemas.validate_input(
        request.input_schema_version,
        {
            "source_revision_id": request.source_revision_id,
            "learning_unit_revision_id": request.learning_unit_revision_id,
            "requested_count": request.requested_count,
            "learning_unit": {
                "revision_label": "2026.07",
                "title": "理解客户风险",
                "objectives": ["识别客户对交付风险的真实担忧"],
                "key_concepts": [
                    {
                        "concept_id": "risk-clarification",
                        "title": "风险澄清",
                        "content": "先确认风险场景、业务影响和判断标准。",
                        "source_anchor_ids": ["anchor-1"],
                    }
                ],
                "examples": [],
                "checkpoints": [
                    {
                        "checkpoint_id": "checkpoint-1",
                        "prompt": "说明客户担忧及其业务影响。",
                        "required": True,
                    }
                ],
                "practice_hints": ["先澄清，再回应"],
            },
            "source_anchors": [
                {
                    "anchor_id": "anchor-1",
                    "label": "客户风险澄清方法",
                    "locator_type": "paragraph",
                }
            ],
        },
    )
    short_answer_input = schemas.validate_input(
        "short-answer-input-v1",
        {
            "quiz_revision_id": "quiz-revision-1",
            "answers": [
                {
                    "question_revision_id": "question-revision-1",
                    "stem": "客户担忧交付风险时应先做什么？",
                    "reference_answer": "澄清风险场景、影响和判断标准。",
                    "rubric": {"criterion": "风险澄清"},
                    "max_points": 1.0,
                    "learner_answer": "先确认担忧及其业务影响。",
                }
            ],
        },
    )

    assert question_input["learning_unit"]["title"] == "理解客户风险"
    assert short_answer_input["answers"][0]["learner_answer"] == (
        "先确认担忧及其业务影响。"
    )


def test_worker_registration_uses_default_production_ai_composition(
    monkeypatch,
) -> None:
    registry = TaskRegistry()
    built_with = []
    monkeypatch.setattr(task_bootstrap, "_application_ai_factory", None)

    class _AI:
        async def invoke(self, request):  # pragma: no cover - composition only
            raise AssertionError(request)

    ai_factory = _AI

    def build_default(*, session_factory):
        built_with.append(session_factory)
        return ai_factory

    monkeypatch.setattr(
        task_bootstrap,
        "build_foundation_ai_invocation_factory",
        build_default,
    )
    monkeypatch.setattr(
        task_bootstrap,
        "get_application_task_registry",
        lambda: registry,
    )

    task_bootstrap.register_foundation_worker_tasks(
        session_factory=AsyncSessionLocal,
    )

    assert built_with == [AsyncSessionLocal]
    assert isinstance(
        registry.resolve("learning.question_generation.generate", 1).handler,
        QuestionGenerationTaskHandler,
    )
    assert isinstance(
        registry.resolve("learning.quiz.short_answer_score", 1).handler,
        ShortAnswerScoringTaskHandler,
    )
    assert isinstance(
        registry.resolve(COACH_CARD_GENERATION_TASK_TYPE, 1).handler,
        CoachCardGenerationTaskHandler,
    )
    assert isinstance(
        registry.resolve(COACH_ANSWER_EVALUATION_TASK_TYPE, 1).handler,
        CoachAnswerEvaluationTaskHandler,
    )
    assert isinstance(
        registry.resolve(COACH_ASSISTANCE_TASK_TYPE, 1).handler,
        CoachAssistanceTaskHandler,
    )
