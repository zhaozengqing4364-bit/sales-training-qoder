from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from common.ai.llm_service import LLMService
from common.error_handling.result import Result
from prompt_templates.compiled_contract import CompiledPromptContract
from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachCoachAction
from sales_trainer.ai_coach_chat_schemas import (
    AI_COACH_CHAT_RESPONSE_SCHEMA_VERSION,
    AiCoachChatMessageCreate,
    AiCoachChatResponseInternalV1,
    AiCoachChatSessionCreate,
    AiCoachChatSessionPublicV1,
    AiCoachChatUiEventInternalV1,
    AiCoachExplanationCardPayloadV1,
    AiCoachQuizCardPayloadInternalV1,
)
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import (
    AiCoachAnswerPayloadV1,
    AiCoachConfig,
    AiCoachInteractionInternalV1,
    AiCoachScoreResultV1,
)
from sales_trainer.services import (
    ai_coach_chat_auto_advance as chat_auto_advance_module,
)
from sales_trainer.services import (
    ai_coach_chat_generation as chat_generation_module,
)
from sales_trainer.services import (
    ai_coach_chat_generation_prompt as chat_generation_prompt_module,
)
from sales_trainer.services import (
    ai_coach_chat_service as chat_service_module,
)
from sales_trainer.services import (
    ai_coach_chat_session_creator as chat_session_creator_module,
)
from sales_trainer.services.ai_coach_chat_coach_state import (
    AiCoachCoachStateV1,
    update_state_after_action,
)
from sales_trainer.services.ai_coach_chat_errors import AiCoachChatGenerationError
from sales_trainer.services.ai_coach_chat_generation import AiCoachChatGenerator
from sales_trainer.services.ai_coach_chat_generation_parser import (
    AiCoachChatResponseParser,
)
from sales_trainer.services.ai_coach_chat_generation_prompt import (
    AiCoachChatPromptCompiler,
)
from sales_trainer.services.ai_coach_chat_generation_streaming import (
    AI_COACH_JSON_RESPONSE_FORMAT,
    AiCoachAssistantTextDraftExtractor,
    AiCoachGenerationDelta,
    AiCoachQuizCardDraftExtractor,
    emit_streamed_response,
)
from sales_trainer.services.ai_coach_chat_next_action import AiCoachNextActionDecider
from sales_trainer.services.ai_coach_chat_next_action_generation import (
    AiCoachChatNextActionGenerator,
)
from sales_trainer.services.ai_coach_chat_projection import AiCoachChatProjection
from sales_trainer.services.ai_coach_chat_scoring import AiCoachChatScorer
from sales_trainer.services.ai_coach_chat_service import (
    AiCoachChatService,
    AiCoachChatServiceError,
)
from sales_trainer.services.ai_coach_chat_session_creator import (
    AiCoachChatSessionCreator,
)
from sales_trainer.services.ai_coach_chat_stream_service import AiCoachChatStreamService
from sales_trainer.services.prompt_template_revision_resolver import (
    RESULT_OK,
    PromptRevisionResolution,
    PromptRevisionSnapshot,
)


class _FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_count = 0
        self.rollback_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1
        return None

    async def rollback(self) -> None:
        self.rollback_count += 1
        return None

    async def refresh(self, _instance: object) -> None:
        return None


def _choice_interaction(
    stem: str,
    correct_option: str = "A",
    training_card_type: str = "scenario_judgment",
) -> dict[str, object]:
    return {
        "schema_version": "ai_coach_interaction_v1",
        "training_card_type": training_card_type,
        "interaction_type": "single_choice",
        "stem": stem,
        "options": [
            {"option_id": "A", "text": "先确认到访时间、人数和接待安排"},
            {"option_id": "B", "text": "直接发送公司宣传册"},
        ],
        "answer_key": {"option_ids": [correct_option], "reference_answer": None},
        "scoring_rubric": {
            "max_score": 100,
            "points": [
                {
                    "key": correct_option,
                    "score": 100,
                    "description": "命中关键商务礼仪动作",
                }
            ],
            "partial_credit_policy": "all_or_nothing",
        },
        "feedback_guidance": {
            "correct": "处理得当。",
            "incorrect": "先确认拜访安排，再进入介绍。",
        },
        "source_evidence": None,
    }


def _short_answer_interaction(
    stem: str = "请把这句客户接待话术改得更专业。",
) -> dict[str, object]:
    return {
        "schema_version": "ai_coach_interaction_v1",
        "training_card_type": "expression_rewrite",
        "interaction_type": "short_answer",
        "stem": stem,
        "options": None,
        "answer_key": {
            "option_ids": [],
            "reference_answer": "我会先确认您的到访目的和人数，再安排合适的接待动线。",
        },
        "scoring_rubric": {
            "max_score": 100,
            "points": [
                {
                    "key": "respect-and-clarity",
                    "score": 100,
                    "description": "表达尊重、清晰确认接待关键事项",
                }
            ],
            "partial_credit_policy": "proportional",
        },
        "feedback_guidance": {
            "correct": "表达清楚且尊重客户。",
            "incorrect": "需要说明具体动作，避免空泛回答。",
        },
        "source_evidence": None,
    }


def _chat_response(card_count: int = 2) -> dict[str, object]:
    return {
        "schema_version": AI_COACH_CHAT_RESPONSE_SCHEMA_VERSION,
        "assistant_text": "可以，我们先做一组商务礼仪情境卡。",
        "ui_events": [
            {
                "type": "quiz_card",
                "payload": {
                    "interaction": _choice_interaction(
                        f"第 {index + 1} 张：客户拜访前应该先做什么？"
                    ),
                    "explanation": "拜访前准备优先确认具体接待条件。",
                },
            }
            for index in range(card_count)
        ],
    }


def _compiled_chat_contract() -> CompiledPromptContract:
    return CompiledPromptContract(
        contract_version="prompt_contract_v1",
        prompt_source="test",
        template_id="11111111-1111-1111-1111-111111111111",
        template_name="AI Coach Chat Test",
        prompt_type="stage",
        rendered_prompt="rendered chat prompt",
        system_message="system",
        runtime_consumer="ai_coach.chat.generate",
        contract_hash="hash-chat-1",
    )


def _prompt_resolution() -> PromptRevisionResolution:
    return PromptRevisionResolution(
        status=RESULT_OK,
        snapshot=PromptRevisionSnapshot(
            template_id="11111111-1111-1111-1111-111111111111",
            prompt_revision_id="head",
            resolved_from="head",
            updated_at_iso="2026-06-10T00:00:00Z",
            template=SimpleNamespace(
                id="11111111-1111-1111-1111-111111111111",
                name="AI Coach Chat Test",
            ),
        ),
    )


def _score_result(score: float) -> dict[str, object]:
    return {
        "score": score,
        "max_score": 100,
        "feedback": "ok",
        "missed_points": [],
        "next_turn_available": True,
        "finished": False,
    }


def test_ai_coach_proactive_config_defaults_are_safe() -> None:
    config = AiCoachConfig()

    assert config.allowed_training_card_types == [
        "scenario_judgment",
    ]
    assert config.proactive_coaching_enabled is False
    assert config.session_start_behavior == "welcome_only"
    assert config.auto_advance_enabled is False
    assert config.max_auto_steps_per_session == 5
    assert config.correct_streak_to_increase_difficulty == 2
    assert config.incorrect_streak_to_remediate == 1
    assert config.incorrect_streak_to_pause == 2
    assert config.remediation_strategy == "explain_then_retry"
    assert config.summary_when_mastery_reached is True
    assert "remediate" in config.allowed_next_actions
    assert config.streaming_enabled is True
    assert config.entry_resume_policy == "latest_active_or_new"
    assert config.generation_timeout_seconds == 120
    assert config.retry_policy.max_retries == 1
    assert config.empty_response_recovery_prompts == ["继续下一题", "换个场景", "总结本轮"]
    assert config.generation_failure_recovery_message == (
        "我已保留当前训练局，但下一步训练生成失败。你可以让我重试、换主题，或先总结一下。"
    )
    assert config.generation_failure_recovery_prompts == ["重试下一题", "换主题", "总结一下"]


def test_streaming_quiz_card_draft_exposes_only_public_fields() -> None:
    model_json = json.dumps(_chat_response(card_count=1), ensure_ascii=False)

    draft = AiCoachQuizCardDraftExtractor(
        session_id="session-1",
    ).extract_changed(model_json)

    assert draft is not None
    interaction = draft.interaction
    assert interaction.interaction_id == "stream-session-1"
    assert interaction.training_card_type == "scenario_judgment"
    assert interaction.interaction_type == "single_choice"
    assert interaction.stem == "第 1 张：客户拜访前应该先做什么？"
    assert interaction.options is not None
    assert [option.option_id for option in interaction.options] == ["A", "B"]
    assert [option.text for option in interaction.options] == [
        "先确认到访时间、人数和接待安排",
        "直接发送公司宣传册",
    ]
    serialized = draft.model_dump_json()
    assert "answer_key" not in serialized
    assert "scoring_rubric" not in serialized
    assert "source_evidence" not in serialized


def test_streaming_quiz_card_draft_exposes_partial_stem_before_json_closes() -> None:
    partial_model_json = (
        '{"quiz_card":{"training_card_type":"scenario_judgment",'
        '"interaction":{"interaction_type":"single_choice",'
        '"stem":"在商务场合第一次见客户时，称呼对方'
    )

    draft = AiCoachQuizCardDraftExtractor(
        session_id="session-1",
    ).extract_changed(partial_model_json)

    assert draft is not None
    interaction = draft.interaction
    assert interaction.training_card_type == "scenario_judgment"
    assert interaction.interaction_type == "single_choice"
    assert interaction.stem == "在商务场合第一次见客户时，称呼对方"
    assert interaction.options is None
    assert interaction.answer_constraints == {"min_selected": 1, "max_selected": 1}


def test_streaming_assistant_text_delta_exposes_partial_markdown() -> None:
    extractor = AiCoachAssistantTextDraftExtractor()
    first = extractor.extract_changed('{"assistant_text":"**先判断**客户')
    duplicate = extractor.extract_changed('{"assistant_text":"**先判断**客户')
    second = extractor.extract_changed('{"assistant_text":"**先判断**客户意图\\n- 再给建议')

    assert first == "**先判断**客户"
    assert duplicate is None
    assert second == "**先判断**客户意图\n- 再给建议"


def test_ai_coach_config_rejects_empty_generation_failure_recovery_prompt() -> None:
    with pytest.raises(ValidationError):
        AiCoachConfig(generation_failure_recovery_prompts=["重试下一题", " "])


def test_ai_coach_interaction_rejects_rewrite_card_without_short_answer() -> None:
    with pytest.raises(ValidationError):
        AiCoachInteractionInternalV1.model_validate(
            _choice_interaction(
                "请把这句不专业表达改写得更合适。",
                training_card_type="expression_rewrite",
            )
        )


def test_chat_response_rejects_training_card_type_outside_config() -> None:
    payload = _chat_response(card_count=1)
    config = AiCoachConfig(
        allowed_interaction_types=["single_choice", "short_answer"],
        allowed_training_card_types=["expression_rewrite"],
        scoring_prompt_template_id="22222222-2222-2222-2222-222222222222",
    )

    with pytest.raises(AiCoachChatGenerationError) as exc_info:
        AiCoachChatResponseParser().parse_model_response(
            json.dumps(payload),
            config,
        )

    assert exc_info.value.code == "[AI_COACH_TRAINING_CARD_TYPE_NOT_ALLOWED]"


def test_prompt_variables_include_business_etiquette_training_card_context() -> None:
    config = AiCoachConfig(
        allowed_interaction_types=["single_choice", "short_answer"],
        allowed_training_card_types=["scenario_judgment", "expression_rewrite"],
        scoring_prompt_template_id="22222222-2222-2222-2222-222222222222",
    )
    session = SimpleNamespace(
        module_key="business_skills",
        article_snapshot={"title": "商务礼仪", "summary": "摘要", "chapters": []},
        path_config_snapshot={
            "learning_units": [{
                "unit_key": "trust_foundation",
                "title": "职业信任底座",
                "source_chapter_orders": [1, 2],
                "capability_keys": ["respect_boundaries"],
                "require_ai_coach": True,
            }],
        },
    )

    variables = AiCoachChatPromptCompiler(_FakeDb())._generation_variables(
        session,  # type: ignore[arg-type]
        config,
        user_message="开始练习",
        history=[],
    )

    assert variables["business_etiquette_capability_keys"] == [
        "respect_boundaries"
    ]
    assert variables["business_etiquette_learning_units"] == [{
        "unit_key": "trust_foundation",
        "title": "职业信任底座",
        "source_chapter_orders": [1, 2],
        "capability_keys": ["respect_boundaries"],
        "require_ai_coach": True,
    }]
    assert variables["allowed_training_card_types"] == [
        "scenario_judgment",
        "expression_rewrite",
    ]
    assert variables["feedback_schema"]["suggested_response"] == "可以怎么说"


def test_chat_prompt_system_message_names_scoring_policy_values() -> None:
    system_message = AiCoachChatPromptCompiler.system_message(AiCoachConfig(enabled=True))

    assert "all_or_nothing" in system_message
    assert "proportional" in system_message
    assert "tiered" in system_message
    assert "不得使用 partial" in system_message


def test_chat_request_models_accept_resume_strategy_and_commands() -> None:
    create_payload = AiCoachChatSessionCreate.model_validate(
        {
            "module_key": "business_skills",
            "resume_strategy": "latest_in_progress",
        }
    )
    message_payload = AiCoachChatMessageCreate.model_validate(
        {
            "command": "explain",
            "event_id": "event-1",
        }
    )

    assert create_payload.resume_strategy == "latest_in_progress"
    assert message_payload.command == "explain"
    assert message_payload.content is None
    default_create_payload = AiCoachChatSessionCreate.model_validate(
        {"module_key": "business_skills"}
    )
    assert default_create_payload.resume_strategy is None


def test_chat_message_requires_content_or_command() -> None:
    with pytest.raises(ValidationError):
        AiCoachChatMessageCreate.model_validate({})


def test_next_action_continues_after_first_correct_answer() -> None:
    config = AiCoachConfig(
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
    )
    state = AiCoachCoachStateV1(
        auto_step_count=1,
        answered_card_count=1,
        correct_streak=1,
        incorrect_streak=0,
    )

    decision = AiCoachNextActionDecider().decide_after_score(
        config=config,
        state=state,
        score_result=_score_result(100),
    )

    assert decision.action == "continue_drill"
    assert decision.should_generate is True


def test_score_result_adds_mastery_context_for_learner_projection() -> None:
    score_result = AiCoachScoreResultV1(
        score=70,
        max_score=100,
        feedback="还需要补强。",
    )

    projected = AiCoachChatService._with_mastery_context(
        score_result,
        threshold=80,
    )

    assert projected.score == 70
    assert projected.max_score == 100
    assert projected.mastery_threshold == 80
    assert projected.mastered is False


def test_next_action_increases_difficulty_after_correct_streak() -> None:
    config = AiCoachConfig(
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
    )
    state = AiCoachCoachStateV1(
        auto_step_count=2,
        answered_card_count=2,
        correct_streak=2,
        incorrect_streak=0,
    )

    decision = AiCoachNextActionDecider().decide_after_score(
        config=config,
        state=state,
        score_result=_score_result(100),
    )

    assert decision.action == "increase_difficulty"
    assert decision.should_generate is True


def test_next_action_remediates_after_wrong_answer() -> None:
    config = AiCoachConfig(
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
    )
    state = AiCoachCoachStateV1(
        auto_step_count=1,
        answered_card_count=1,
        correct_streak=0,
        incorrect_streak=1,
    )

    decision = AiCoachNextActionDecider().decide_after_score(
        config=config,
        state=state,
        score_result=_score_result(0),
    )

    assert decision.action == "remediate"
    assert decision.should_generate is True


def test_next_action_asks_user_choice_after_wrong_streak_pause() -> None:
    config = AiCoachConfig(
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        incorrect_streak_to_pause=2,
    )
    state = AiCoachCoachStateV1(
        auto_step_count=2,
        answered_card_count=2,
        correct_streak=0,
        incorrect_streak=2,
    )

    decision = AiCoachNextActionDecider().decide_after_score(
        config=config,
        state=state,
        score_result=_score_result(0),
    )

    assert decision.action == "ask_user_choice"
    assert decision.should_generate is True


def test_next_action_respects_ask_user_choice_remediation_strategy() -> None:
    config = AiCoachConfig(
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        remediation_strategy="ask_user_choice",
    )
    state = AiCoachCoachStateV1(
        auto_step_count=1,
        answered_card_count=1,
        correct_streak=0,
        incorrect_streak=1,
    )

    decision = AiCoachNextActionDecider().decide_after_score(
        config=config,
        state=state,
        score_result=_score_result(0),
    )

    assert decision.action == "ask_user_choice"
    assert "补救策略" in decision.reason


def test_terminal_or_choice_action_stops_auto_advance() -> None:
    state = AiCoachCoachStateV1(auto_step_count=1)

    choice_state = update_state_after_action(
        state,
        action="ask_user_choice",
        can_auto_advance=True,
    )
    summary_state = update_state_after_action(
        state,
        action="summarize",
        can_auto_advance=True,
    )
    continue_state = update_state_after_action(
        state,
        action="continue_drill",
        can_auto_advance=True,
    )

    assert choice_state.can_auto_advance is False
    assert choice_state.auto_step_count == 1
    assert summary_state.can_auto_advance is False
    assert summary_state.auto_step_count == 2
    assert continue_state.can_auto_advance is True
    assert continue_state.auto_step_count == 2


def test_next_action_summarizes_at_auto_step_limit() -> None:
    config = AiCoachConfig(
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        max_auto_steps_per_session=3,
    )
    state = AiCoachCoachStateV1(
        auto_step_count=3,
        answered_card_count=3,
        correct_streak=1,
        incorrect_streak=0,
    )

    decision = AiCoachNextActionDecider().decide_after_score(
        config=config,
        state=state,
        score_result=_score_result(100),
    )

    assert decision.action == "summarize"
    assert decision.should_generate is True


def test_next_action_falls_back_to_allowed_action() -> None:
    config = AiCoachConfig(
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        allowed_next_actions=["ask_user_choice"],
    )
    state = AiCoachCoachStateV1(
        auto_step_count=1,
        answered_card_count=1,
        correct_streak=1,
        incorrect_streak=0,
    )

    decision = AiCoachNextActionDecider().decide_after_score(
        config=config,
        state=state,
        score_result=_score_result(100),
    )

    assert decision.action == "ask_user_choice"
    assert decision.should_generate is True


def test_next_action_generation_rejects_multiple_quiz_cards_for_chat_first_action() -> None:
    response = AiCoachChatResponseInternalV1.model_validate(_chat_response(card_count=2))

    with pytest.raises(AiCoachChatGenerationError) as exc_info:
        AiCoachChatNextActionGenerator._validate_response_for_action(
            response,
            "remediate",
        )

    assert exc_info.value.code == "[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]"


def test_next_action_generation_allows_chat_only_continue_drill() -> None:
    response = AiCoachChatResponseInternalV1(
        assistant_text="你先把客户第一次来访的准备动作说一遍，我再决定是否给你一张练习卡。",
        ui_events=[],
    )

    AiCoachChatNextActionGenerator._validate_response_for_action(
        response,
        "continue_drill",
    )


def test_next_action_generation_accepts_remediate_contract() -> None:
    response = AiCoachChatResponseInternalV1(
        assistant_text="先看解析，再做一道相似题。",
        ui_events=[
            AiCoachChatUiEventInternalV1(
                type="explanation_card",
                payload=AiCoachExplanationCardPayloadV1(
                    title="拜访前准备",
                    body="先确认客户到访时间、人数和接待安排。",
                ),
            ),
            AiCoachChatUiEventInternalV1(
                type="quiz_card",
                payload=AiCoachQuizCardPayloadInternalV1(
                    interaction=_choice_interaction("客户临时改期时应该先做什么？"),
                    explanation="先确认新时间和接待资源。",
                ),
            ),
        ],
    )

    AiCoachChatNextActionGenerator._validate_response_for_action(response, "remediate")


def test_chat_response_accepts_multiple_quiz_cards() -> None:
    payload = _chat_response(card_count=3)

    parsed = AiCoachChatResponseInternalV1.model_validate(payload)

    assert parsed.assistant_text == "可以，我们先做一组商务礼仪情境卡。"
    assert len(parsed.ui_events) == 3
    assert parsed.ui_events[0].type == "quiz_card"


def test_chat_response_rejects_unknown_ui_event_type() -> None:
    payload = _chat_response(card_count=1)
    events = payload["ui_events"]
    assert isinstance(events, list)
    events[0]["type"] = "unsafe_component"  # type: ignore[index]

    with pytest.raises(ValidationError):
        AiCoachChatResponseInternalV1.model_validate(payload)


def test_public_quiz_card_projection_drops_internal_answer_key() -> None:
    service = AiCoachChatService(_FakeDb())  # type: ignore[arg-type]
    internal = AiCoachChatResponseInternalV1.model_validate(_chat_response(card_count=1))
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
    )

    stored_payload = service.build_stored_event_payload(
        event_id="event-1",
        session=session,
        event=internal.ui_events[0],
        card_number=1,
    )
    public_payload = service.public_payload_for_event("quiz_card", stored_payload)

    encoded = json.dumps(public_payload.model_dump(mode="json"), ensure_ascii=False)
    assert "answer_key" not in encoded
    assert "scoring_rubric" not in encoded
    assert "source_evidence" not in encoded
    assert public_payload.interaction.stem == "第 1 张：客户拜访前应该先做什么？"


def test_generate_chat_response_retries_when_model_output_breaks_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_compile_kwargs: dict[str, object] = {}
    captured_llm_configs: list[object] = []

    class FakeResolver:
        def __init__(self, _db: object) -> None:
            return None

        async def resolve(
            self,
            *,
            template_id: str,
            prompt_revision_id: str | None,
        ) -> PromptRevisionResolution:
            assert template_id == "11111111-1111-1111-1111-111111111111"
            assert prompt_revision_id is None
            return _prompt_resolution()

    class FakePromptTemplateService:
        def __init__(self, _db: object) -> None:
            return None

        def compile_runtime_prompt_contract(self, **kwargs: object) -> Result:
            captured_compile_kwargs.update(kwargs)
            return Result.ok(_compiled_chat_contract())

    class FakeLLMService:
        prompts: list[str] = []
        response_formats: list[object] = []
        outputs = ["not json", json.dumps(_chat_response(card_count=1))]

        def __init__(self, config: object | None = None) -> None:
            captured_llm_configs.append(config)

        async def generate(self, **kwargs: object) -> Result:
            prompt = kwargs.get("prompt")
            assert isinstance(prompt, str)
            self.prompts.append(prompt)
            self.response_formats.append(kwargs.get("response_format"))
            return Result.ok(self.outputs.pop(0))

    model_config = SimpleNamespace(
        id="model-config-1",
        provider="openai",
        base_url="https://llm.example/v1",
        model_name="coach-generation-model",
        extra_config={"temperature": 0.2},
    )

    def fake_resolve_model(model_name: str | None) -> object | None:
        assert model_name == "coach-generation-model"
        return model_config

    monkeypatch.setattr(
        chat_generation_prompt_module,
        "PromptTemplateRevisionResolver",
        FakeResolver,
    )
    monkeypatch.setattr(
        chat_generation_prompt_module,
        "PromptTemplateService",
        FakePromptTemplateService,
    )
    monkeypatch.setattr(chat_generation_module, "LLMService", FakeLLMService)
    monkeypatch.setattr(
        chat_generation_prompt_module,
        "resolve_ai_coach_llm_model_config",
        fake_resolve_model,
    )
    monkeypatch.setattr(
        chat_generation_module,
        "resolve_ai_coach_llm_model_config",
        fake_resolve_model,
    )
    config = AiCoachConfig(
        enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        generation_model="coach-generation-model",
        retry_policy={"max_retries": 1, "retry_backoff": 1.0},
    )
    session = SimpleNamespace(
        session_id="session-1",
        module_key="business_skills",
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        prompt_revision_id=None,
        prompt_contract_hash=None,
        article_snapshot={"title": "商务技巧", "summary": "摘要", "chapters": []},
    )

    parsed = asyncio.run(
        AiCoachChatGenerator(_FakeDb()).generate(
            session=session,  # pyright: ignore[reportArgumentType]
            config=config,
            user_message="出 1 道题",
            history=[],
        )
    )

    assert parsed.assistant_text == "可以，我们先做一组商务礼仪情境卡。"
    assert len(parsed.ui_events) == 1
    assert session.prompt_contract_hash == "hash-chat-1"
    assert captured_llm_configs == [model_config, model_config]
    assert captured_compile_kwargs["model_config"] == {
        "provider": "openai",
        "base_url": "https://llm.example/v1",
        "model_name": "coach-generation-model",
        "extra_config": {"temperature": 0.2},
    }
    assert len(FakeLLMService.prompts) == 2
    assert FakeLLMService.response_formats == [
        AI_COACH_JSON_RESPONSE_FORMAT,
        AI_COACH_JSON_RESPONSE_FORMAT,
    ]
    assert "上一轮输出字段类型或结构不符合要求" in FakeLLMService.prompts[1]
    assert "错误码" not in FakeLLMService.prompts[1]
    assert "[AI_COACH_INTERACTION_INVALID]" not in FakeLLMService.prompts[1]


def test_streamed_chat_generation_requests_json_response_format() -> None:
    captured: dict[str, object] = {}
    model_json = json.dumps(_chat_response(card_count=0), ensure_ascii=False)

    class FakeLLM:
        async def stream_generate(self, **kwargs: object):
            captured.update(kwargs)
            yield model_json

    async def ignore_delta(_delta: object) -> None:
        return None

    async def collect() -> AiCoachChatResponseInternalV1:
        result = await emit_streamed_response(
            llm=FakeLLM(),
            parser=AiCoachChatResponseParser(),
            contract=_compiled_chat_contract(),
            config=AiCoachConfig(enabled=True),
            session_id="session-1",
            max_attempts=1,
            failure_message="生成失败",
            on_generation_delta=ignore_delta,
        )
        return result.response

    parsed = asyncio.run(collect())

    assert parsed.assistant_text == "可以，我们先做一组商务礼仪情境卡。"
    assert captured["response_format"] == AI_COACH_JSON_RESPONSE_FORMAT


def test_streamed_chat_generation_emits_reasoning_delta() -> None:
    model_json = json.dumps(_chat_response(card_count=0), ensure_ascii=False)
    deltas: list[AiCoachGenerationDelta] = []

    class FakeLLM:
        async def stream_generate_chunks(self, **_kwargs: object):
            yield SimpleNamespace(text="", reasoning_text="先判断客户场景。")
            yield SimpleNamespace(text=model_json, reasoning_text="")

    async def collect_delta(delta: AiCoachGenerationDelta) -> None:
        deltas.append(delta)

    async def collect() -> AiCoachChatResponseInternalV1:
        result = await emit_streamed_response(
            llm=FakeLLM(),
            parser=AiCoachChatResponseParser(),
            contract=_compiled_chat_contract(),
            config=AiCoachConfig(enabled=True),
            session_id="session-1",
            max_attempts=1,
            failure_message="生成失败",
            on_generation_delta=collect_delta,
        )
        return result.response

    parsed = asyncio.run(collect())

    assert parsed.assistant_text == "可以，我们先做一组商务礼仪情境卡。"
    assert deltas[0].delta_type == "reasoning_text"
    assert deltas[0].text == "先判断客户场景。"


def test_streamed_chat_generation_does_not_emit_unvalidated_quiz_card_delta() -> None:
    model_json = json.dumps(_chat_response(card_count=1), ensure_ascii=False)
    deltas: list[AiCoachGenerationDelta] = []

    class FakeLLM:
        async def stream_generate_chunks(self, **_kwargs: object):
            yield SimpleNamespace(text=model_json, reasoning_text="")

    async def collect_delta(delta: AiCoachGenerationDelta) -> None:
        deltas.append(delta)

    async def collect() -> AiCoachChatResponseInternalV1:
        result = await emit_streamed_response(
            llm=FakeLLM(),
            parser=AiCoachChatResponseParser(),
            contract=_compiled_chat_contract(),
            config=AiCoachConfig(enabled=True),
            session_id="session-1",
            max_attempts=1,
            failure_message="生成失败",
            on_generation_delta=collect_delta,
        )
        return result.response

    parsed = asyncio.run(collect())

    assert len(parsed.ui_events) == 1
    assert {delta.delta_type for delta in deltas} == {"assistant_text"}


def test_streamed_chat_generation_hides_retry_reasoning() -> None:
    model_json = json.dumps(_chat_response(card_count=0), ensure_ascii=False)
    deltas: list[AiCoachGenerationDelta] = []

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def stream_generate_chunks(self, **_kwargs: object):
            self.calls += 1
            if self.calls == 1:
                yield SimpleNamespace(text="", reasoning_text="先拟一张训练卡。")
                yield SimpleNamespace(text="not json", reasoning_text="")
                return
            yield SimpleNamespace(text="", reasoning_text="根据错误码修复 JSON。")
            yield SimpleNamespace(text=model_json, reasoning_text="")

    async def collect_delta(delta: AiCoachGenerationDelta) -> None:
        deltas.append(delta)

    async def collect() -> AiCoachChatResponseInternalV1:
        result = await emit_streamed_response(
            llm=FakeLLM(),
            parser=AiCoachChatResponseParser(),
            contract=_compiled_chat_contract(),
            config=AiCoachConfig(enabled=True),
            session_id="session-1",
            max_attempts=2,
            failure_message="生成失败",
            on_generation_delta=collect_delta,
        )
        return result.response

    parsed = asyncio.run(collect())

    assert parsed.assistant_text == "可以，我们先做一组商务礼仪情境卡。"
    assert [delta.text for delta in deltas] == ["先拟一张训练卡。"]


def test_llm_chunk_extracts_deepseek_reasoning_shapes() -> None:
    assert LLMService._chunk_reasoning_to_text(
        SimpleNamespace(additional_kwargs={"reasoning_content": "先分析。"})
    ) == "先分析。"
    assert LLMService._chunk_reasoning_to_text(
        SimpleNamespace(content=[{"type": "reasoning", "text": "再判断。"}])
    ) == "再判断。"
    assert LLMService._chunk_reasoning_to_text(
        SimpleNamespace(response_metadata={"delta": {"reasoning_content": "后输出。"}})
    ) == "后输出。"
    assert LLMService._openai_stream_chunk_to_llm_chunk(
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        reasoning_content="官方流式思考。",
                    )
                )
            ]
        )
    ).reasoning_text == "官方流式思考。"


def test_score_event_rejects_duplicate_submission() -> None:
    service = AiCoachChatService(_FakeDb())  # type: ignore[arg-type]
    event = SimpleNamespace(
        event_id="event-1",
        event_type="quiz_card",
        status="scored",
        payload_json={
            "interaction_snapshot": _choice_interaction("客户拜访前应该先做什么？"),
            "public_interaction": {},
        },
        answer_payload={"variant": "choice", "option_ids": ["A"]},
    )

    with pytest.raises(AiCoachChatServiceError) as exc_info:
        asyncio.run(
            service.score_quiz_event(
                event,  # pyright: ignore[reportArgumentType]
                answer_payload={"variant": "choice", "option_ids": ["A"]},
            )
        )

    assert exc_info.value.code == "[AI_COACH_CHAT_EVENT_ALREADY_SUBMITTED]"


def test_score_text_quiz_event_calls_ai_short_answer_scoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDb(_FakeDb):
        async def get(self, _model: object, session_id: str) -> object:
            assert session_id == "session-1"
            return SimpleNamespace(
                config_snapshot={
                    "scoring_prompt_template_id": "22222222-2222-2222-2222-222222222222",
                    "scoring_prompt_revision_id": "rev-1",
                    "scoring_contract_hash": "hash-score-1",
                }
            )

    captured: dict[str, object] = {}

    async def fake_score_short_answer(self, **kwargs: object) -> Result:
        captured.update(kwargs)
        return Result.ok(
            AiCoachScoreResultV1(
                score=82,
                max_score=100,
                feedback="回答能体现尊重和确认动作。",
                missed_points=[],
            )
        )

    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.AiCoachSessionService.score_short_answer",
        fake_score_short_answer,
    )
    event = SimpleNamespace(
        event_id="event-1",
        session_id="session-1",
        event_type="quiz_card",
        status="pending",
        payload_json={
            "interaction_snapshot": _short_answer_interaction(),
            "public_interaction": {},
        },
        answer_payload=None,
    )
    scorer = AiCoachChatScorer(FakeDb())  # type: ignore[arg-type]

    result = asyncio.run(
        scorer.score_quiz_event(
            event,  # pyright: ignore[reportArgumentType]
            answer_payload={"variant": "text", "text": "我会先确认来访目的和人数，再安排接待。"},
        )
    )

    assert result.score == 82
    assert captured["answer_text"] == "我会先确认来访目的和人数，再安排接待。"
    assert captured["scoring_prompt_template_id"] == "22222222-2222-2222-2222-222222222222"
    assert captured["scoring_prompt_revision_id"] == "rev-1"
    assert captured["scoring_contract_hash"] == "hash-score-1"
    assert "runtime_metadata_out" in captured


def test_score_and_persist_event_answer_stores_scoring_runtime_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    session = SimpleNamespace(
        session_id="session-1",
        user_id="user-1",
        module_key="other_module",
        config_snapshot={"mastery_threshold": 80},
    )
    event = SimpleNamespace(
        event_id="event-1",
        session_id="session-1",
        event_type="quiz_card",
        status="pending",
        payload_json={
            "interaction_snapshot": _short_answer_interaction(),
            "public_interaction": {},
        },
        answer_payload=None,
        score_result=None,
        created_at=now,
        updated_at=now,
    )

    class FakeRuntime:
        def config_from_session(self, _session: object) -> AiCoachConfig:
            return AiCoachConfig(
                mastery_threshold=80,
                allowed_interaction_types=["single_choice", "short_answer"],
                scoring_prompt_template_id="22222222-2222-2222-2222-222222222222",
            )

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    async def fake_require_owned_session(
        self: AiCoachChatService,
        session_id: str,
        user_id: str,
    ) -> object:
        assert session_id == "session-1"
        assert user_id == "user-1"
        return session

    async def fake_event(
        self: AiCoachChatService,
        session_id: str,
        event_id: str,
    ) -> object:
        assert session_id == "session-1"
        assert event_id == "event-1"
        return event

    async def fake_score_quiz_event(
        self: AiCoachChatService,
        _event: object,
        *,
        answer_payload: AiCoachAnswerPayloadV1 | dict[str, object],
        runtime_metadata_out: dict[str, object] | None = None,
    ) -> AiCoachScoreResultV1:
        assert answer_payload
        assert runtime_metadata_out is not None
        runtime_metadata_out.update(
            {
                "prompt_template_id": "22222222-2222-2222-2222-222222222222",
                "prompt_revision_id": "rev-1",
                "contract_hash": "hash-score-1",
                "requested_model": "coach-score-model",
                "model_config_id": "model-config-1",
                "model_provider": "openai",
                "model_name": "coach-score-model",
            }
        )
        return AiCoachScoreResultV1(
            score=90,
            max_score=100,
            feedback="回答清楚。",
            missed_points=[],
        )

    monkeypatch.setattr(
        AiCoachChatService,
        "_require_owned_session",
        fake_require_owned_session,
    )
    monkeypatch.setattr(AiCoachChatService, "_event", fake_event)
    monkeypatch.setattr(AiCoachChatService, "score_quiz_event", fake_score_quiz_event)

    service = AiCoachChatService(
        _FakeDb(),  # type: ignore[arg-type]
        logs=FakeLogs(),  # type: ignore[arg-type]
        runtime=FakeRuntime(),  # type: ignore[arg-type]
    )

    asyncio.run(
        service.score_and_persist_event_answer(
            session_id="session-1",
            event_id="event-1",
            user_id="user-1",
            answer_payload=AiCoachAnswerPayloadV1(
                variant="text",
                text="我会先确认来访目的和人数，再安排接待。",
            ),
        )
    )

    assert event.status == "scored"
    assert event.score_result["runtime_audit"]["scoring"] == {
        "prompt_template_id": "22222222-2222-2222-2222-222222222222",
        "prompt_revision_id": "rev-1",
        "contract_hash": "hash-score-1",
        "requested_model": "coach-score-model",
        "model_config_id": "model-config-1",
        "model_provider": "openai",
        "model_name": "coach-score-model",
    }


def test_projection_exposes_active_event_and_answering_phase() -> None:
    now = datetime.now(UTC)
    session = SimpleNamespace(
        session_id="session-1",
        module_key="business_skills",
        status="in_progress",
        created_at=now,
        updated_at=now,
        coach_state={
            "auto_step_count": 1,
            "answered_card_count": 0,
            "correct_streak": 0,
            "incorrect_streak": 0,
            "difficulty": "warmup",
            "last_action": "continue_drill",
            "can_auto_advance": True,
        },
    )
    message = SimpleNamespace(
        message_id="message-1",
        role="assistant",
        content="第一题",
        order_index=1,
        created_at=now,
    )
    event = SimpleNamespace(
        event_id="event-1",
        message_id="message-1",
        event_type="quiz_card",
        status="pending",
        payload_json={
            "public_interaction": {
                "schema_version": "ai_coach_interaction_public_v1",
                "interaction_id": "event-1",
                "session_id": "session-1",
                "turn_number": 1,
                "interaction_type": "single_choice",
                "stem": "客户拜访前应该先做什么？",
                "options": [
                    {"option_id": "A", "text": "先确认到访时间"},
                    {"option_id": "B", "text": "直接介绍产品"},
                ],
                "answer_constraints": {"min_selected": 1, "max_selected": 1},
            },
            "explanation": "先确认接待条件。",
        },
        answer_payload=None,
        score_result=None,
        order_index=1,
        created_at=now,
    )

    projected = AiCoachChatProjection().project_session(
        session,  # type: ignore[arg-type]
        [message],  # type: ignore[list-item]
        [event],  # type: ignore[list-item]
    )

    assert projected.coach_state is not None
    assert projected.coach_state.session_phase == "answering"
    assert projected.coach_state.active_event_id == "event-1"


def test_projection_clears_active_event_when_summarizing() -> None:
    now = datetime.now(UTC)
    session = SimpleNamespace(
        session_id="session-1",
        module_key="business_skills",
        status="in_progress",
        created_at=now,
        updated_at=now,
        coach_state={
            "auto_step_count": 1,
            "answered_card_count": 1,
            "difficulty": "warmup",
            "last_action": "summarize",
            "can_auto_advance": True,
        },
    )
    message = SimpleNamespace(
        message_id="message-1",
        role="assistant",
        content="第一题",
        order_index=1,
        created_at=now,
    )
    event = SimpleNamespace(
        event_id="event-1",
        message_id="message-1",
        event_type="quiz_card",
        status="pending",
        payload_json={
            "public_interaction": {
                "schema_version": "ai_coach_interaction_public_v1",
                "interaction_id": "event-1",
                "session_id": "session-1",
                "turn_number": 1,
                "interaction_type": "single_choice",
                "stem": "客户拜访前应该先做什么？",
                "options": [
                    {"option_id": "A", "text": "先确认到访时间"},
                    {"option_id": "B", "text": "直接介绍产品"},
                ],
                "answer_constraints": {"min_selected": 1, "max_selected": 1},
            },
            "explanation": "先确认接待条件。",
        },
        answer_payload=None,
        score_result=None,
        order_index=1,
        created_at=now,
    )

    projected = AiCoachChatProjection().project_session(
        session,  # type: ignore[arg-type]
        [message],  # type: ignore[list-item]
        [event],  # type: ignore[list-item]
    )

    assert projected.coach_state is not None
    assert projected.coach_state.session_phase == "summarizing"
    assert projected.coach_state.active_event_id is None


def test_create_session_stores_ai_coach_config_snapshot_without_runtime_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AiCoachConfig(
        enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
    )
    fake_db = _FakeDb()

    class FakePathConfigService:
        def __init__(self, _db: object) -> None:
            return None

        async def get_config(self) -> dict[str, object]:
            return {
                "path": {"modules": []},
                "active_revision_id": "revision-1",
                "active_revision_no": 1,
            }

    class FakeRuntime:
        def module_ai_coach_config(
            self,
            _raw_path: object,
            module_key: str,
        ) -> tuple[SimpleNamespace, AiCoachConfig]:
            return (
                SimpleNamespace(
                    module_key=module_key,
                    model_dump=lambda mode="json": {"module_key": module_key},
                ),
                config,
            )

        def validate_chat_config(self, _config: AiCoachConfig) -> None:
            return None

        async def article_snapshot(self, _module: object) -> dict[str, object]:
            return {}

        def welcome_message(self, _config: AiCoachConfig) -> str:
            return "你好"

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    class FakeStore:
        async def messages(self, _session_id: str) -> list[object]:
            return []

        async def events(self, _session_id: str) -> list[object]:
            return []

        async def next_message_order(self, _session_id: str) -> int:
            return 1

        async def next_card_number(self, _session_id: str) -> int:
            return 1

    monkeypatch.setattr(
        chat_session_creator_module,
        "SalesTrainerPathConfigService",
        FakePathConfigService,
    )
    creator = AiCoachChatSessionCreator(
        fake_db,  # type: ignore[arg-type]
        FakeRuntime(),  # type: ignore[arg-type]
        FakeLogs(),  # type: ignore[arg-type]
        FakeStore(),  # type: ignore[arg-type]
        FakeStore(),  # type: ignore[arg-type]
    )

    asyncio.run(
        creator.create_session_id(
            user_id="user-1",
            module_key="business_skills",
            actor=None,
        )
    )

    sessions = [
        instance
        for instance in fake_db.added
        if isinstance(instance, SalesTrainerAiCoachSession)
    ]
    assert len(sessions) == 1
    snapshot = sessions[0].config_snapshot
    assert "active_runtime" not in snapshot
    assert AiCoachConfig.model_validate(snapshot).prompt_template_id == (
        "11111111-1111-1111-1111-111111111111"
    )


def test_create_session_can_resume_latest_in_progress_session() -> None:
    fake_db = _FakeDb()
    existing = SimpleNamespace(session_id="session-existing")

    class FakeStore:
        async def latest_in_progress_session(
            self,
            *,
            user_id: str,
            module_key: str,
        ) -> object:
            assert user_id == "user-1"
            assert module_key == "business_skills"
            return existing

    class FailingCreator:
        async def create_session_id(self, **_kwargs: object) -> str:
            raise AssertionError("resume should not create a new session")

    async def fake_public_session(session_id: str, user_id: str) -> object:
        assert session_id == "session-existing"
        assert user_id == "user-1"
        return SimpleNamespace(session_id=session_id)

    service = AiCoachChatService(  # type: ignore[arg-type]
        fake_db,
        store=FakeStore(),
        session_creator=FailingCreator(),
    )
    service.public_session = fake_public_session  # type: ignore[method-assign]

    resumed = asyncio.run(
        service.create_session(
            user_id="user-1",
            module_key="business_skills",
            resume_strategy="latest_in_progress",
        )
    )

    assert resumed.session_id == "session-existing"


def test_create_session_latest_active_or_new_skips_non_answering_session() -> None:
    fake_db = _FakeDb()
    existing = SimpleNamespace(session_id="session-existing")

    class FakeStore:
        async def latest_in_progress_session(
            self,
            *,
            user_id: str,
            module_key: str,
        ) -> object:
            assert user_id == "user-1"
            assert module_key == "business_skills"
            return existing

    class FakeCreator:
        async def create_session_id(self, **_kwargs: object) -> str:
            return "session-new"

    async def fake_public_session(session_id: str, _user_id: str) -> object:
        if session_id == "session-existing":
            return SimpleNamespace(
                session_id=session_id,
                coach_state=SimpleNamespace(
                    session_phase="summarizing",
                    active_event_id=None,
                ),
            )
        return SimpleNamespace(session_id=session_id, coach_state=None)

    service = AiCoachChatService(  # type: ignore[arg-type]
        fake_db,
        store=FakeStore(),
        session_creator=FakeCreator(),
    )
    service.public_session = fake_public_session  # type: ignore[method-assign]

    created = asyncio.run(
        service.create_session(
            user_id="user-1",
            module_key="business_skills",
            resume_strategy="latest_active_or_new",
        )
    )

    assert created.session_id == "session-new"


def test_create_session_uses_configured_resume_policy_when_request_omits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = _FakeDb()
    config = AiCoachConfig(
        enabled=True,
        chat_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        entry_resume_policy="latest_active_or_new",
    )

    class FakePathConfigService:
        def __init__(self, _db: object) -> None:
            return None

        async def get_config(self) -> dict[str, object]:
            return {"path": {"modules": []}}

    class FakeRuntime:
        def module_ai_coach_config(
            self,
            raw_path: object,
            module_key: str,
        ) -> tuple[object, AiCoachConfig]:
            assert raw_path == {"modules": []}
            assert module_key == "business_skills"
            return SimpleNamespace(), config

        def validate_chat_config(self, received: AiCoachConfig) -> None:
            assert received is config

    class FakeStore:
        async def latest_in_progress_session(
            self,
            *,
            user_id: str,
            module_key: str,
        ) -> object | None:
            assert user_id == "user-1"
            assert module_key == "business_skills"
            return None

    class FakeCreator:
        async def create_session_id(self, **_kwargs: object) -> str:
            return "session-created"

    async def fake_public_session(session_id: str, _user_id: str) -> object:
        return SimpleNamespace(session_id=session_id, coach_state=None)

    monkeypatch.setattr(
        chat_service_module,
        "SalesTrainerPathConfigService",
        FakePathConfigService,
    )
    service = AiCoachChatService(  # type: ignore[arg-type]
        fake_db,
        runtime=FakeRuntime(),
        store=FakeStore(),
        session_creator=FakeCreator(),
    )
    service.public_session = fake_public_session  # type: ignore[method-assign]

    created = asyncio.run(
        service.create_session(
            user_id="user-1",
            module_key="business_skills",
        )
    )

    assert created.session_id == "session-created"


def test_session_start_first_card_failure_returns_safe_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AiCoachConfig(
        enabled=True,
        proactive_coaching_enabled=True,
        session_start_behavior="plan_and_first_card",
        auto_advance_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
    )
    fake_db = _FakeDb()
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
        config_snapshot=config.model_dump(mode="json"),
        coach_state={},
        status="in_progress",
    )

    class FakeStore:
        async def messages(self, _session_id: str) -> list[object]:
            return []

        async def next_message_order(self, _session_id: str) -> int:
            return 2

        async def next_card_number(self, _session_id: str) -> int:
            return 1

    class FailingGenerator:
        def __init__(self, _db: object) -> None:
            return None

        async def generate(self, **_kwargs: object) -> AiCoachChatResponseInternalV1:
            raise AiCoachChatGenerationError(
                "[AI_COACH_LLM_GENERATION_FAILED]",
                "生成失败。",
                502,
            )

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(
        chat_auto_advance_module,
        "AiCoachChatGenerator",
        FailingGenerator,
    )

    from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance
    from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter

    store = FakeStore()
    auto_advance = AiCoachChatAutoAdvance(
        fake_db,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        AiCoachChatEventWriter(fake_db, AiCoachChatProjection(), store),  # type: ignore[arg-type]
        FakeLogs(),  # type: ignore[arg-type]
    )

    asyncio.run(
        auto_advance.start_session_if_configured(
            session=session,
            config=config,
            actor=None,
        )
    )

    assert session.coach_state["stopped_reason"] == "[AI_COACH_LLM_GENERATION_FAILED]"
    assert any(
        isinstance(item, SalesTrainerAiCoachCoachAction) and item.status == "failed"
        for item in fake_db.added
    )
    assert any(
        getattr(item, "content", "") == "我已保留当前训练局，但下一步训练生成失败。你可以让我重试、换主题，或先总结一下。"
        for item in fake_db.added
    )


def test_send_message_routes_explicit_command_to_auto_advance() -> None:
    fake_db = _FakeDb()
    config = AiCoachConfig(
        enabled=True,
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
    )
    session = SimpleNamespace(
        session_id="session-1",
        user_id="user-1",
        status="in_progress",
        coach_state={},
        config_snapshot=config.model_dump(mode="json"),
    )
    calls: list[dict[str, object]] = []

    class FakeStore:
        async def require_owned_session(self, session_id: str, user_id: str) -> object:
            assert session_id == "session-1"
            assert user_id == "user-1"
            return session

        async def event(self, session_id: str, event_id: str) -> object:
            assert session_id == "session-1"
            assert event_id == "event-1"
            return SimpleNamespace(event_id=event_id)

        async def next_message_order(self, _session_id: str) -> int:
            return 2

    class FakeRuntime:
        def config_from_session(self, _session: object) -> AiCoachConfig:
            return config

    class FakeAutoAdvance:
        async def advance_for_command(self, **kwargs: object) -> None:
            calls.append(kwargs)

    async def fake_public_session(session_id: str, user_id: str) -> object:
        return SimpleNamespace(session_id=session_id, user_id=user_id)

    service = AiCoachChatService(  # type: ignore[arg-type]
        fake_db,
        store=FakeStore(),
        runtime=FakeRuntime(),
        auto_advance=FakeAutoAdvance(),
    )
    service.public_session = fake_public_session  # type: ignore[method-assign]

    asyncio.run(
        service.send_message(
            session_id="session-1",
            user_id="user-1",
            payload=AiCoachChatMessageCreate.model_validate(
                {"command": "explain", "event_id": "event-1"}
            ),
        )
    )

    assert calls[0]["command"] == "explain"
    assert calls[0]["event_id"] == "event-1"
    assert any(getattr(item, "content", "") == "讲解一下" for item in fake_db.added)


def test_send_message_adds_recovery_prompt_when_model_returns_no_events() -> None:
    fake_db = _FakeDb()
    config = AiCoachConfig(
        enabled=True,
        chat_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        empty_response_recovery_prompts=["继续下一题", "换个场景"],
    )
    session = SimpleNamespace(
        session_id="session-1",
        user_id="user-1",
        status="in_progress",
        coach_state={},
        config_snapshot=config.model_dump(mode="json"),
    )
    persisted_events: list[AiCoachChatUiEventInternalV1] = []

    class FakeStore:
        async def require_owned_session(self, session_id: str, user_id: str) -> object:
            assert session_id == "session-1"
            assert user_id == "user-1"
            return session

        async def next_message_order(self, _session_id: str) -> int:
            return 2

        async def messages(self, _session_id: str) -> list[object]:
            return []

    class FakeRuntime:
        def config_from_session(self, _session: object) -> AiCoachConfig:
            return config

        async def generate_chat_response(self, **_kwargs: object) -> AiCoachChatResponseInternalV1:
            return AiCoachChatResponseInternalV1(
                assistant_text="好的，我们开始一道题目。",
                ui_events=[],
            )

    class FakeEvents:
        async def persist_ui_events(
            self,
            _session: object,
            _assistant: object,
            events: list[AiCoachChatUiEventInternalV1],
        ) -> None:
            persisted_events.extend(events)

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    async def fake_public_session(session_id: str, _user_id: str) -> object:
        return SimpleNamespace(session_id=session_id)

    service = AiCoachChatService(  # type: ignore[arg-type]
        fake_db,
        store=FakeStore(),
        runtime=FakeRuntime(),
        events=FakeEvents(),
        logs=FakeLogs(),
    )
    service.public_session = fake_public_session  # type: ignore[method-assign]

    asyncio.run(
        service.send_message(
            session_id="session-1",
            user_id="user-1",
            payload=AiCoachChatMessageCreate.model_validate(
                {"content": "出一道商务礼仪题"}
            ),
        )
    )

    assert len(persisted_events) == 1
    assert persisted_events[0].type == "followup_prompt"
    assert persisted_events[0].payload.prompts == ["继续下一题", "换个场景"]
    assert any(
        getattr(item, "content", "") == "好的，我们开始一道题目。"
        for item in fake_db.added
    )


def test_stream_submit_answer_manual_pace_skips_next_generation_statuses() -> None:
    config = AiCoachConfig(
        enabled=True,
        chat_enabled=True,
        streaming_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
    )
    scored_session = AiCoachChatSessionPublicV1.model_validate(
        {
            "session_id": "session-1",
            "module_key": "business_skills",
            "status": "in_progress",
            "created_at": "2026-06-12T00:00:00Z",
            "updated_at": "2026-06-12T00:00:01Z",
            "messages": [],
            "ui_events": [],
            "coach_state": None,
        }
    )
    completed_session = scored_session.model_copy(
        update={"updated_at": datetime(2026, 6, 12, 0, 0, 2, tzinfo=UTC)}
    )
    public_sessions = [scored_session, completed_session]
    calls: list[str] = []

    class FakeRuntime:
        def config_from_session(self, _session: object) -> AiCoachConfig:
            return config

    class FakeService:
        _runtime = FakeRuntime()

        async def _require_owned_session(self, session_id: str, user_id: str) -> object:
            assert session_id == "session-1"
            assert user_id == "user-1"
            return SimpleNamespace(config_snapshot=config.model_dump(mode="json"))

        async def score_and_persist_event_answer(self, **_kwargs: object) -> tuple[dict[str, object], AiCoachScoreResultV1]:
            calls.append("score")
            return {}, AiCoachScoreResultV1(score=100, max_score=100, feedback="ok")

        async def public_session(
            self,
            _session_id: str,
            _user_id: str,
        ) -> AiCoachChatSessionPublicV1:
            return public_sessions.pop(0)

        async def advance_after_scored_event(self, **_kwargs: object) -> None:
            calls.append("advance")
            on_generation_delta = _kwargs.get("on_generation_delta")
            if callable(on_generation_delta):
                await on_generation_delta(
                    AiCoachGenerationDelta(
                        delta_type="reasoning_text",
                        text="先判断是否继续同主题。",
                    )
                )
                await on_generation_delta(
                    AiCoachGenerationDelta(
                        delta_type="assistant_text",
                        text="**下一步**：继续练客户开场。",
                    )
                )

    async def collect_events() -> list[dict[str, object]]:
        service = AiCoachChatStreamService(  # type: ignore[arg-type]
            _FakeDb(),
            service=FakeService(),
        )
        chunks = []
        async for chunk in service.stream_submit_answer(
            session_id="session-1",
            event_id="event-1",
            payload=SimpleNamespace(
                answer_payload=AiCoachAnswerPayloadV1.model_validate(
                    {"variant": "choice", "option_ids": ["A"]}
                )
            ),
            actor=SimpleNamespace(user_id="user-1"),  # type: ignore[arg-type]
        ):
            chunks.append(json.loads(chunk.split("data: ", 1)[1]))
        return chunks

    events = asyncio.run(collect_events())

    phases = [event["phase"] for event in events]
    assert phases == [
        "scoring_answer",
        "answer_scored",
        "completed",
    ]
    assert calls == ["score", "advance"]


def test_stream_submit_answer_auto_advance_emits_next_generation_statuses() -> None:
    config = AiCoachConfig(
        enabled=True,
        chat_enabled=True,
        streaming_enabled=True,
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
    )
    scored_session = AiCoachChatSessionPublicV1.model_validate(
        {
            "session_id": "session-1",
            "module_key": "business_skills",
            "status": "in_progress",
            "created_at": "2026-06-12T00:00:00Z",
            "updated_at": "2026-06-12T00:00:01Z",
            "messages": [],
            "ui_events": [],
            "coach_state": None,
        }
    )
    completed_session = scored_session.model_copy(
        update={"updated_at": datetime(2026, 6, 12, 0, 0, 2, tzinfo=UTC)}
    )
    public_sessions = [scored_session, completed_session]
    calls: list[str] = []

    class FakeRuntime:
        def config_from_session(self, _session: object) -> AiCoachConfig:
            return config

    class FakeService:
        _runtime = FakeRuntime()

        async def _require_owned_session(self, session_id: str, user_id: str) -> object:
            assert session_id == "session-1"
            assert user_id == "user-1"
            return SimpleNamespace(config_snapshot=config.model_dump(mode="json"))

        async def score_and_persist_event_answer(self, **_kwargs: object) -> tuple[dict[str, object], AiCoachScoreResultV1]:
            calls.append("score")
            return {}, AiCoachScoreResultV1(score=100, max_score=100, feedback="ok")

        async def public_session(
            self,
            _session_id: str,
            _user_id: str,
        ) -> AiCoachChatSessionPublicV1:
            return public_sessions.pop(0)

        async def advance_after_scored_event(self, **_kwargs: object) -> None:
            calls.append("advance")
            on_generation_delta = _kwargs.get("on_generation_delta")
            if callable(on_generation_delta):
                await on_generation_delta(
                    AiCoachGenerationDelta(
                        delta_type="reasoning_text",
                        text="先判断是否继续同主题。",
                    )
                )
                await on_generation_delta(
                    AiCoachGenerationDelta(
                        delta_type="assistant_text",
                        text="**下一步**：继续练客户开场。",
                    )
                )

    async def collect_events() -> list[dict[str, object]]:
        service = AiCoachChatStreamService(  # type: ignore[arg-type]
            _FakeDb(),
            service=FakeService(),
        )
        chunks = []
        async for chunk in service.stream_submit_answer(
            session_id="session-1",
            event_id="event-1",
            payload=SimpleNamespace(
                answer_payload=AiCoachAnswerPayloadV1.model_validate(
                    {"variant": "choice", "option_ids": ["A"]}
                )
            ),
            actor=SimpleNamespace(user_id="user-1"),  # type: ignore[arg-type]
        ):
            chunks.append(json.loads(chunk.split("data: ", 1)[1]))
        return chunks

    events = asyncio.run(collect_events())

    assert [event["phase"] for event in events] == [
        "scoring_answer",
        "answer_scored",
        "deciding_next_action",
        "generating_next_card",
        "generating_next_card",
        "generating_next_card",
        "completed",
    ]
    assert [event["type"] for event in events] == [
        "status",
        "session_snapshot",
        "status",
        "status",
        "reasoning_text_delta",
        "assistant_text_delta",
        "session_snapshot",
    ]
    assert events[4]["text"] == "先判断是否继续同主题。"
    assert events[5]["text"] == "**下一步**：继续练客户开场。"
    assert calls == ["score", "advance"]


def test_stream_submit_answer_timeout_records_recoverable_fallback_snapshot() -> None:
    config = SimpleNamespace(
        streaming_enabled=True,
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        generation_timeout_seconds=0.01,
    )
    scored_session = AiCoachChatSessionPublicV1.model_validate(
        {
            "session_id": "session-1",
            "module_key": "business_skills",
            "status": "in_progress",
            "created_at": datetime(2026, 6, 12, tzinfo=UTC),
            "updated_at": datetime(2026, 6, 12, 0, 0, 1, tzinfo=UTC),
            "messages": [],
            "ui_events": [],
            "coach_state": None,
        }
    )
    fallback_session = scored_session.model_copy(
        update={"updated_at": datetime(2026, 6, 12, 0, 0, 2, tzinfo=UTC)}
    )
    public_sessions = [scored_session, fallback_session]
    calls: list[str] = []

    class ExpiringActor:
        expired = False
        user_id = "user-1"
        role = "learner"

        def expire(self) -> None:
            self.expired = True

    actor = ExpiringActor()

    class FakeRuntime:
        def config_from_session(self, _session: object) -> object:
            return config

    class FakeService:
        _runtime = FakeRuntime()

        async def _require_owned_session(self, session_id: str, user_id: str) -> object:
            assert session_id == "session-1"
            assert user_id == "user-1"
            return SimpleNamespace(config_snapshot={})

        async def score_and_persist_event_answer(self, **_kwargs: object) -> tuple[dict[str, object], AiCoachScoreResultV1]:
            calls.append("score")
            return {}, AiCoachScoreResultV1(score=100, max_score=100, feedback="ok")

        async def public_session(
            self,
            _session_id: str,
            _user_id: str,
        ) -> AiCoachChatSessionPublicV1:
            return public_sessions.pop(0)

        async def advance_after_scored_event(self, **_kwargs: object) -> None:
            calls.append("advance")
            await asyncio.sleep(0.05)

        async def rollback_cancelled_generation(self) -> None:
            calls.append("rollback")
            actor.expire()

        async def record_advance_timeout_after_scored_event(self, **kwargs: object) -> None:
            calls.append("timeout_fallback")
            fallback_actor = kwargs["actor"]
            assert fallback_actor is not actor
            assert getattr(fallback_actor, "user_id") == "user-1"
            assert getattr(fallback_actor, "role") == "learner"

    async def collect_events() -> list[dict[str, object]]:
        service = AiCoachChatStreamService(  # type: ignore[arg-type]
            _FakeDb(),
            service=FakeService(),
        )
        chunks = []
        async for chunk in service.stream_submit_answer(
            session_id="session-1",
            event_id="event-1",
            payload=SimpleNamespace(
                answer_payload=AiCoachAnswerPayloadV1.model_validate(
                    {"variant": "choice", "option_ids": ["A"]}
                )
            ),
            actor=actor,  # type: ignore[arg-type]
        ):
            chunks.append(json.loads(chunk.split("data: ", 1)[1]))
        return chunks

    events = asyncio.run(collect_events())

    assert [event["phase"] for event in events] == [
        "scoring_answer",
        "answer_scored",
        "deciding_next_action",
        "generating_next_card",
        "completed",
    ]
    assert events[-1]["type"] == "session_snapshot"
    assert calls == ["score", "advance", "rollback", "timeout_fallback"]


def test_summarize_command_uses_deterministic_summary_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AiCoachConfig(
        enabled=True,
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
    )
    fake_db = _FakeDb()
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
        config_snapshot=config.model_dump(mode="json"),
        coach_state={
            "answered_card_count": 1,
            "score_total": 100,
            "score_count": 1,
            "difficulty": "normal",
        },
        status="in_progress",
    )

    class FakeStore:
        async def next_message_order(self, _session_id: str) -> int:
            return 2

        async def next_card_number(self, _session_id: str) -> int:
            return 1

    class FailingGenerator:
        def __init__(self, _db: object) -> None:
            return None

        async def generate(self, **_kwargs: object) -> AiCoachChatResponseInternalV1:
            raise AssertionError("summary command should not call LLM")

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(
        chat_auto_advance_module,
        "AiCoachChatGenerator",
        FailingGenerator,
    )

    from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance
    from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter

    store = FakeStore()
    auto_advance = AiCoachChatAutoAdvance(
        fake_db,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        AiCoachChatEventWriter(fake_db, AiCoachChatProjection(), store),  # type: ignore[arg-type]
        FakeLogs(),  # type: ignore[arg-type]
    )

    asyncio.run(
        auto_advance.advance_for_command(
            session=session,
            config=config,
            command="summarize",
            event_id=None,
            actor=None,
        )
    )

    assert session.coach_state["last_action"] == "summarize"
    assert any(
        getattr(item, "content", "") == "这是本轮训练的阶段复盘。"
        for item in fake_db.added
    )
    assert any(
        getattr(item, "event_type", "") == "summary_card"
        for item in fake_db.added
    )


def test_auto_advance_after_answer_appends_next_quiz_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AiCoachConfig(
        enabled=True,
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
    )
    fake_db = _FakeDb()
    now = datetime.now(UTC)
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
        config_snapshot=config.model_dump(mode="json"),
        coach_state={},
        status="in_progress",
        created_at=now,
        updated_at=now,
    )
    message = SimpleNamespace(
        message_id="message-1",
        session_id="session-1",
        role="assistant",
        content="第一题",
        order_index=1,
        created_at=now,
    )
    event = SimpleNamespace(
        event_id="event-1",
        session_id="session-1",
        message_id="message-1",
        event_type="quiz_card",
        status="pending",
        payload_json={
            "interaction_snapshot": _choice_interaction("客户拜访前应该先做什么？"),
            "public_interaction": {
                "schema_version": "ai_coach_interaction_public_v1",
                "interaction_id": "event-1",
                "session_id": "session-1",
                "turn_number": 1,
                "interaction_type": "single_choice",
                "stem": "客户拜访前应该先做什么？",
                "options": [
                    {"option_id": "A", "text": "先确认到访时间、人数和接待安排"},
                    {"option_id": "B", "text": "直接发送公司宣传册"},
                ],
                "answer_constraints": {"min_selected": 1, "max_selected": 1},
            },
        },
        answer_payload=None,
        score_result=None,
        order_index=1,
        created_at=now,
    )

    class FakeStore:
        async def require_owned_session(
            self,
            session_id: str,
            user_id: str,
        ) -> SalesTrainerAiCoachSession:
            assert session_id == "session-1"
            assert user_id == "user-1"
            return session

        async def event(self, session_id: str, event_id: str) -> object:
            assert session_id == "session-1"
            assert event_id == "event-1"
            return event

        async def messages(self, _session_id: str) -> list[object]:
            return [message]

        async def events(self, _session_id: str) -> list[object]:
            return [event]

        async def next_message_order(self, _session_id: str) -> int:
            return 2

        async def next_card_number(self, _session_id: str) -> int:
            return 2

    class FakeScorer:
        async def score_quiz_event(
            self,
            _event: object,
            *,
            answer_payload: object,
            runtime_metadata_out: object | None = None,
        ):
            assert answer_payload is not None
            from sales_trainer.schemas import AiCoachScoreResultV1

            return AiCoachScoreResultV1(
                score=100,
                max_score=100,
                feedback="处理得当。",
                missed_points=[],
            )

    class FakeGenerator:
        def __init__(self, _db: object) -> None:
            return None

        async def generate(self, **_kwargs: object) -> AiCoachChatResponseInternalV1:
            assert fake_db.commit_count >= 1
            return AiCoachChatResponseInternalV1(
                assistant_text="很好，下一题我会加一点难度。",
                ui_events=[
                    AiCoachChatUiEventInternalV1(
                        type="quiz_card",
                        payload=AiCoachQuizCardPayloadInternalV1(
                            interaction=_choice_interaction("客户开始质疑价值时怎么回应？"),
                            explanation="先确认真实顾虑。",
                        ),
                    )
                ],
            )

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    progress_calls: list[str] = []

    class FakeProgressService:
        def __init__(self, _db: object, *, store: object, logs: object) -> None:
            assert store is store_instance
            assert logs is logs_instance

        async def update_session_progress_snapshot(
            self,
            _session: SalesTrainerAiCoachSession,
            *,
            actor: object | None,
        ) -> object:
            assert actor is None
            progress_calls.append("updated")
            return None

    monkeypatch.setattr(
        chat_auto_advance_module,
        "AiCoachChatNextActionGenerator",
        FakeGenerator,
    )
    monkeypatch.setattr(
        chat_service_module,
        "BusinessEtiquetteAiCoachProgressService",
        FakeProgressService,
    )
    store_instance = FakeStore()
    logs_instance = FakeLogs()
    from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance
    from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter
    from sales_trainer.services.ai_coach_chat_projection import AiCoachChatProjection

    projection = AiCoachChatProjection()
    event_writer = AiCoachChatEventWriter(fake_db, projection, store_instance)  # type: ignore[arg-type]
    auto_advance = AiCoachChatAutoAdvance(
        fake_db,  # type: ignore[arg-type]
        store_instance,  # type: ignore[arg-type]
        event_writer,
        logs_instance,  # type: ignore[arg-type]
    )
    service = AiCoachChatService(  # type: ignore[arg-type]
        fake_db,
        store=store_instance,
        scoring=FakeScorer(),
        logs=logs_instance,
        events=event_writer,
        auto_advance=auto_advance,
    )

    asyncio.run(
        service.submit_event_answer(
            session_id="session-1",
            event_id="event-1",
            user_id="user-1",
            answer_payload=AiCoachAnswerPayloadV1.model_validate(
                {"variant": "choice", "option_ids": ["A"]}
            ),
        )
    )

    assistant_messages = [
        added
        for added in fake_db.added
        if getattr(added, "content", None) == "很好，下一题我会加一点难度。"
    ]
    assert len(assistant_messages) == 1
    assert event.status == "scored"
    assert session.coach_state["last_action"] == "continue_drill"
    assert session.coach_state["answered_card_count"] == 1
    assert progress_calls == ["updated"]
    assert fake_db.commit_count >= 2


def test_auto_advance_records_failed_action_with_safe_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AiCoachConfig(
        enabled=True,
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        failure_behavior="skip_turn",
    )
    fake_db = _FakeDb()
    now = datetime.now(UTC)
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
        config_snapshot=config.model_dump(mode="json"),
        coach_state={},
        status="in_progress",
        created_at=now,
        updated_at=now,
    )
    message = SimpleNamespace(
        message_id="message-1",
        session_id="session-1",
        role="assistant",
        content="第一题",
        order_index=1,
        created_at=now,
    )

    class FakeStore:
        async def messages(self, _session_id: str) -> list[object]:
            return [message]

        async def next_message_order(self, _session_id: str) -> int:
            return 2

        async def next_card_number(self, _session_id: str) -> int:
            return 1

    class FailingGenerator:
        def __init__(self, _db: object) -> None:
            return None

        async def generate(self, **_kwargs: object) -> AiCoachChatResponseInternalV1:
            raise AiCoachChatGenerationError(
                "[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]",
                "动作卡片不符合约束。",
                502,
            )

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(
        chat_auto_advance_module,
        "AiCoachChatNextActionGenerator",
        FailingGenerator,
    )

    from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance
    from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter
    from sales_trainer.services.ai_coach_chat_projection import AiCoachChatProjection

    store = FakeStore()
    event_writer = AiCoachChatEventWriter(fake_db, AiCoachChatProjection(), store)  # type: ignore[arg-type]
    auto_advance = AiCoachChatAutoAdvance(
        fake_db,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        event_writer,
        FakeLogs(),  # type: ignore[arg-type]
    )

    asyncio.run(
        auto_advance.advance_after_answer(
            session=session,
            config=config,
            event_payload={"interaction_snapshot": _choice_interaction("第一题")},
            event_id="event-1",
            score_result=AiCoachScoreResultV1(
                score=100,
                max_score=100,
                feedback="ok",
                missed_points=[],
            ),
            answer_payload=AiCoachAnswerPayloadV1.model_validate(
                {"variant": "choice", "option_ids": ["A"]}
            ),
            actor=None,
        )
    )

    failed_actions = [
        item
        for item in fake_db.added
        if isinstance(item, SalesTrainerAiCoachCoachAction)
        and item.status == "failed"
    ]
    assert len(failed_actions) == 1
    assert failed_actions[0].error_code == "[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]"
    assert session.coach_state["stopped_reason"] == (
        "[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]"
    )
    assert session.coach_state["can_auto_advance"] is False
    assert any(
        getattr(item, "content", "") == "我已保留当前训练局，但下一步训练生成失败。你可以让我重试、换主题，或先总结一下。"
        for item in fake_db.added
    )


def test_auto_advance_timeout_fallback_updates_scored_state_and_audit() -> None:
    config = AiCoachConfig(
        enabled=True,
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        failure_behavior="skip_turn",
    )
    fake_db = _FakeDb()
    now = datetime.now(UTC)
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
        config_snapshot=config.model_dump(mode="json"),
        coach_state={},
        status="in_progress",
        created_at=now,
        updated_at=now,
    )

    class FakeStore:
        async def next_message_order(self, _session_id: str) -> int:
            return 2

        async def next_card_number(self, _session_id: str) -> int:
            return 1

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance
    from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter
    from sales_trainer.services.ai_coach_chat_projection import AiCoachChatProjection

    store = FakeStore()
    event_writer = AiCoachChatEventWriter(fake_db, AiCoachChatProjection(), store)  # type: ignore[arg-type]
    auto_advance = AiCoachChatAutoAdvance(
        fake_db,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        event_writer,
        FakeLogs(),  # type: ignore[arg-type]
    )

    asyncio.run(
        auto_advance.record_timeout_after_answer(
            session=session,
            config=config,
            event_id="event-1",
            score_result=AiCoachScoreResultV1(
                score=100,
                max_score=100,
                feedback="ok",
                missed_points=[],
            ),
            actor=None,
        )
    )

    failed_actions = [
        item
        for item in fake_db.added
        if isinstance(item, SalesTrainerAiCoachCoachAction)
        and item.status == "failed"
    ]
    assert len(failed_actions) == 1
    assert failed_actions[0].error_code == "[AI_COACH_STREAM_TIMEOUT]"
    assert failed_actions[0].trigger_event_id == "event-1"
    assert session.coach_state["answered_card_count"] == 1
    assert session.coach_state["stopped_reason"] == "[AI_COACH_STREAM_TIMEOUT]"
    assert session.coach_state["can_auto_advance"] is False
    assert any(
        getattr(item, "content", "") == "我已保留当前训练局，但下一步训练生成失败。你可以让我重试、换主题，或先总结一下。"
        for item in fake_db.added
    )


def test_auto_advance_abort_failure_surfaces_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AiCoachConfig(
        enabled=True,
        proactive_coaching_enabled=True,
        auto_advance_enabled=True,
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        failure_behavior="abort",
    )
    fake_db = _FakeDb()
    now = datetime.now(UTC)
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
        config_snapshot=config.model_dump(mode="json"),
        coach_state={},
        status="in_progress",
        created_at=now,
        updated_at=now,
    )

    class FakeStore:
        async def messages(self, _session_id: str) -> list[object]:
            return []

    class FailingGenerator:
        def __init__(self, _db: object) -> None:
            return None

        async def generate(self, **_kwargs: object) -> AiCoachChatResponseInternalV1:
            raise AiCoachChatGenerationError(
                "[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]",
                "动作卡片不符合约束。",
                502,
            )

    class FakeLogs:
        async def record(self, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(
        chat_auto_advance_module,
        "AiCoachChatNextActionGenerator",
        FailingGenerator,
    )

    from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance

    auto_advance = AiCoachChatAutoAdvance(
        fake_db,  # type: ignore[arg-type]
        FakeStore(),  # type: ignore[arg-type]
        SimpleNamespace(),
        FakeLogs(),  # type: ignore[arg-type]
    )

    with pytest.raises(AiCoachChatGenerationError) as exc_info:
        asyncio.run(
            auto_advance.advance_after_answer(
                session=session,
                config=config,
                event_payload={"interaction_snapshot": _choice_interaction("第一题")},
                event_id="event-1",
                score_result=AiCoachScoreResultV1(
                    score=100,
                    max_score=100,
                    feedback="ok",
                    missed_points=[],
                ),
                answer_payload=AiCoachAnswerPayloadV1.model_validate(
                    {"variant": "choice", "option_ids": ["A"]}
                ),
                actor=None,
            )
        )

    assert exc_info.value.code == "[AI_COACH_NEXT_ACTION_UI_EVENT_INVALID]"
    assert any(
        isinstance(item, SalesTrainerAiCoachCoachAction) and item.status == "failed"
        for item in fake_db.added
    )
