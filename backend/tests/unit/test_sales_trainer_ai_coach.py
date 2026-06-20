"""Unit tests for AI coach scoring schema and session service."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from common.error_handling.result import Result
from prompt_templates.compiled_contract import CompiledPromptContract
from sales_trainer.ai_coach_api import (
    _serialize_turn_feedback_public,
    submit_ai_coach_turn_v1,
)
from sales_trainer.models import SalesTrainerAiCoachSession, SalesTrainerAiCoachTurn
from sales_trainer.path_config_api import _changed_ai_coach_high_risk_fields
from sales_trainer.schemas import (
    AiCoachAnswerPayloadV1,
    AiCoachConfig,
    AiCoachInteractionInternalV1,
    AiCoachScoringPointV1,
    AiCoachScoringRubricV1,
    AiCoachTurnSubmitV1,
    NewcomerPathConfigSaveRequest,
)
from sales_trainer.services.ai_coach_scoring_service import (
    AiCoachScoreOutputV1,
    AiCoachScoringService,
)
from sales_trainer.services.ai_coach_session_service import (
    AiCoachSessionService,
    AiCoachSessionServiceError,
)
from sales_trainer.services.prompt_template_revision_resolver import (
    RESULT_OK,
    PromptRevisionResolution,
    PromptRevisionSnapshot,
)


class _StubLLM:
    is_configured = True

    def __init__(self, value: str | None) -> None:
        self._value = value

    async def generate(self, **kwargs):  # noqa: ANN003
        if self._value is None:
            return Result.fail("[LLM_NOT_CONFIGURED]")
        return Result.ok(self._value)


class _FakeDb:
    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def refresh(self, _instance: object) -> None:
        return None


def _compiled_contract() -> CompiledPromptContract:
    return CompiledPromptContract(
        contract_version="prompt_contract_v1",
        prompt_source="test",
        template_id="11111111-1111-1111-1111-111111111111",
        template_name="AI Coach Test",
        prompt_type="scoring",
        rendered_prompt="rendered prompt",
        system_message="system",
        runtime_consumer="ai_coach.generate_interaction",
        contract_hash="hash-1",
    )


def _prompt_resolution() -> PromptRevisionResolution:
    return PromptRevisionResolution(
        status=RESULT_OK,
        snapshot=PromptRevisionSnapshot(
            template_id="11111111-1111-1111-1111-111111111111",
            prompt_revision_id="head",
            resolved_from="head",
            updated_at_iso="2026-06-10T00:00:00Z",
            template=SimpleNamespace(id="11111111-1111-1111-1111-111111111111", name="AI Coach Test"),
        ),
    )


def _short_answer_interaction_payload() -> dict[str, object]:
    return {
        "schema_version": "ai_coach_interaction_v1",
        "interaction_type": "short_answer",
        "stem": "客户到访前，你会如何确认接待安排？",
        "options": None,
        "answer_key": {
            "option_ids": [],
            "reference_answer": "确认客户到访时间、目的和接待负责人。",
        },
        "scoring_rubric": {
            "max_score": 100,
            "points": [
                {
                    "key": "confirm-arrival",
                    "score": 100,
                    "description": "确认客户到访时间、目的和接待负责人",
                }
            ],
            "partial_credit_policy": "all_or_nothing",
        },
        "feedback_guidance": {
            "correct": "回答完整。",
            "incorrect": "需要补充客户到访目的和接待安排。",
        },
        "source_evidence": None,
    }


def test_ai_coach_output_v1_accepts_minimal_payload() -> None:
    payload = {"score": 80, "feedback": "ok"}
    result = AiCoachScoreOutputV1.model_validate(payload)
    assert result.score == 80
    assert result.max_score == 100
    assert result.missed_points == []
    assert result.passed is False


def test_ai_coach_output_v1_accepts_structured_feedback_payload() -> None:
    payload = {
        "score": 80,
        "feedback": "整体方向正确。",
        "structured_feedback": {
            "did_well": ["能主动道歉"],
            "main_issue": "没有说明补救动作。",
            "why_inappropriate": "客户会担心你的时间管理和可靠性。",
            "suggested_response": "非常抱歉，我预计晚到 10 分钟，已重新确认资料并到场后优先补齐。",
            "next_step": "再试一版，把预计到达时间和补救动作说清楚。",
        },
    }

    result = AiCoachScoreOutputV1.model_validate(payload)

    assert result.structured_feedback is not None
    assert result.structured_feedback.main_issue == "没有说明补救动作。"


def test_ai_coach_output_v1_rejects_invalid_score() -> None:
    with pytest.raises(ValidationError):
        AiCoachScoreOutputV1.model_validate({"score": 150, "feedback": "x"})


def test_ai_coach_output_v1_rejects_missing_feedback() -> None:
    with pytest.raises(ValidationError):
        AiCoachScoreOutputV1.model_validate({"score": 50})


def test_ai_coach_config_default_is_valid_without_short_answer_scoring_prompt() -> None:
    config = AiCoachConfig()

    assert config.allowed_interaction_types == ["single_choice", "multiple_choice"]
    assert config.scoring_prompt_template_id is None


def test_ai_coach_config_requires_scoring_prompt_when_short_answer_is_enabled() -> None:
    with pytest.raises(ValidationError):
        AiCoachConfig(
            allowed_interaction_types=[
                "single_choice",
                "multiple_choice",
                "short_answer",
            ],
        )


def test_ai_coach_config_allows_short_answer_when_scoring_prompt_is_bound() -> None:
    config = AiCoachConfig(
        allowed_interaction_types=[
            "single_choice",
            "multiple_choice",
            "short_answer",
        ],
        scoring_prompt_template_id="22222222-2222-2222-2222-222222222222",
    )

    assert "short_answer" in config.allowed_interaction_types
    assert config.scoring_prompt_template_id == "22222222-2222-2222-2222-222222222222"


def test_ai_coach_config_rejects_short_answer_card_without_short_answer_type() -> None:
    with pytest.raises(ValidationError):
        AiCoachConfig(allowed_training_card_types=["expression_rewrite"])


def test_ai_coach_config_rejects_non_uuid_prompt_template_ids() -> None:
    with pytest.raises(ValidationError):
        AiCoachConfig(prompt_template_id="not-a-uuid")

    with pytest.raises(ValidationError):
        AiCoachConfig(
            allowed_interaction_types=["short_answer"],
            scoring_prompt_template_id="not-a-uuid",
        )


def test_serialize_session_public_accepts_turn_models_without_internal_leak() -> None:
    service = AiCoachSessionService(_FakeDb())  # type: ignore[arg-type]
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
        status="in_progress",
        mastery_state=None,
        total_score=None,
        max_score=None,
        config_snapshot={"min_turns": 3, "max_turns": 5, "mastery_threshold": 70},
        created_at=datetime(2026, 6, 10, tzinfo=UTC),
        updated_at=datetime(2026, 6, 10, tzinfo=UTC),
    )
    turn = SalesTrainerAiCoachTurn(
        turn_id="turn-1",
        session_id="session-1",
        turn_number=1,
        question="客户到访前最应该确认哪项信息？",
        user_answer="",
        public_interaction={
            "schema_version": "ai_coach_interaction_public_v1",
            "interaction_id": "session-1:1",
            "session_id": "session-1",
            "turn_number": 1,
            "interaction_type": "single_choice",
            "stem": "客户到访前最应该确认哪项信息？",
            "options": [
                {"option_id": "A", "text": "客户到访时间"},
                {"option_id": "B", "text": "天气"},
            ],
            "answer_constraints": {"min_selected": 1, "max_selected": 1},
        },
        answer_payload={"variant": "choice", "option_ids": ["A"]},
        score=None,
        max_score=100,
        ai_feedback=None,
        missed_points=[],
    )

    payload = service.serialize_session_public(
        session,
        [turn],
    ).model_dump(mode="json")

    assert payload["turns"][0]["public_interaction"]["stem"] == "客户到访前最应该确认哪项信息？"
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "answer_key" not in encoded
    assert "is_distractor" not in encoded
    assert "scoring_rubric" not in encoded


def test_project_to_public_multiple_choice_does_not_reveal_correct_count() -> None:
    service = AiCoachSessionService(_FakeDb())  # type: ignore[arg-type]
    internal = AiCoachInteractionInternalV1.model_validate(
        {
            "schema_version": "ai_coach_interaction_v1",
            "interaction_type": "multiple_choice",
            "stem": "哪些是客户到访前需要确认的信息？",
            "options": [
                {"option_id": "A", "text": "到访时间"},
                {"option_id": "B", "text": "接待人数"},
                {"option_id": "C", "text": "天气"},
            ],
            "answer_key": {"option_ids": ["A", "B"], "reference_answer": None},
            "scoring_rubric": {
                "max_score": 100,
                "points": [
                    {"key": "A", "score": 50, "description": "确认时间"},
                    {"key": "B", "score": 50, "description": "确认人数"},
                ],
                "partial_credit_policy": "tiered",
            },
            "feedback_guidance": {
                "correct": "回答正确。",
                "incorrect": "请补充到访安排。",
            },
        }
    )
    session = SalesTrainerAiCoachSession(
        session_id="session-1",
        user_id="user-1",
        module_key="business_skills",
    )
    turn = SalesTrainerAiCoachTurn(
        turn_id="turn-1",
        session_id="session-1",
        turn_number=1,
        question="哪些是客户到访前需要确认的信息？",
        user_answer="",
    )

    public = service._project_to_public(internal, session=session, turn=turn)

    assert public.answer_constraints == {"min_selected": 1, "max_selected": 3}
    encoded = public.model_dump_json()
    assert "answer_key" not in encoded
    assert "is_distractor" not in encoded


def test_path_config_ai_coach_rbac_detects_high_risk_changes() -> None:
    current_path = _path_payload_with_ai_coach(mastery_threshold=80)
    incoming = NewcomerPathConfigSaveRequest.model_validate(
        _path_payload_with_ai_coach(mastery_threshold=90) | {"reason": "更新阈值"}
    )

    changed = _changed_ai_coach_high_risk_fields(current_path, incoming)

    assert changed == {"mastery_threshold"}


def test_path_config_ai_coach_rbac_ignores_unchanged_high_risk_fields() -> None:
    current_path = _path_payload_with_ai_coach(mastery_threshold=80)
    incoming_payload = _path_payload_with_ai_coach(mastery_threshold=80)
    incoming_payload["title"] = "新人训练路径新标题"
    incoming = NewcomerPathConfigSaveRequest.model_validate(
        incoming_payload | {"reason": "只改路径标题"}
    )

    changed = _changed_ai_coach_high_risk_fields(current_path, incoming)

    assert changed == set()


def test_path_config_ai_coach_rbac_treats_config_removal_as_high_risk_change() -> None:
    current_path = _path_payload_with_ai_coach(mastery_threshold=80)
    incoming_payload = _path_payload_with_ai_coach(mastery_threshold=80)
    modules = incoming_payload["modules"]
    assert isinstance(modules, list)
    module = modules[0]
    assert isinstance(module, dict)
    module["ai_coach"] = None
    incoming = NewcomerPathConfigSaveRequest.model_validate(
        incoming_payload | {"reason": "移除 AI 教练配置"}
    )

    changed = _changed_ai_coach_high_risk_fields(current_path, incoming)

    assert "mastery_threshold" in changed
    assert "prompt_template_id" in changed
    assert "allowed_interaction_types" in changed


def test_generate_interaction_accepts_resolver_ok_status_and_active_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_variables: dict[str, object] = {}

    class FakeResolver:
        def __init__(self, db: object) -> None:
            self._db = db

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
        def __init__(self, db: object) -> None:
            self._db = db

        def compile_runtime_prompt_contract(self, **kwargs):  # noqa: ANN003
            captured_variables.update(kwargs["variables"])
            return Result.ok(_compiled_contract())

    class FakeLLMService:
        async def generate(self, **kwargs):  # noqa: ANN003
            return Result.ok(json.dumps(_short_answer_interaction_payload()))

    async def fake_previous_turns(
        self: AiCoachSessionService,
        session_id: str,
    ) -> list[dict[str, object]]:
        assert session_id == "session-1"
        return []

    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.PromptTemplateRevisionResolver",
        FakeResolver,
    )
    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.PromptTemplateService",
        FakePromptTemplateService,
    )
    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.LLMService",
        FakeLLMService,
    )
    monkeypatch.setattr(
        AiCoachSessionService,
        "_get_previous_turns",
        fake_previous_turns,
    )

    session = SimpleNamespace(
        session_id="session-1",
        module_key="business_skills",
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        prompt_revision_id=None,
        prompt_contract_hash=None,
        article_snapshot={"title": "商务技巧", "summary": "摘要", "chapters": []},
        config_snapshot={
            "enabled": True,
            "coach_mode": "mixed_drill",
            "allowed_interaction_types": ["short_answer"],
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
            "pinned_schema_version": "ai_coach_interaction_v1",
            "active_coach_mode": "short_answer_drill",
        },
    )
    turn = SimpleNamespace(turn_number=1)
    service = AiCoachSessionService(_FakeDb())  # type: ignore[arg-type]

    internal = asyncio.run(
        service.generate_interaction(
            session,  # pyright: ignore[reportArgumentType]
            turn,  # pyright: ignore[reportArgumentType]
        )
    )

    assert internal.interaction_type == "short_answer"
    assert session.prompt_contract_hash == "hash-1"
    assert turn.schema_version == "ai_coach_interaction_v1"
    assert turn.public_interaction["interaction_type"] == "short_answer"
    assert captured_variables["coach_mode"] == "short_answer_drill"
    assert captured_variables["allowed_interaction_types"] == ["short_answer"]


def test_generate_interaction_rejects_mixed_drill_type_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResolver:
        def __init__(self, db: object) -> None:
            self._db = db

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
        def __init__(self, db: object) -> None:
            self._db = db

        def compile_runtime_prompt_contract(self, **kwargs):  # noqa: ANN003
            return Result.ok(_compiled_contract())

    class FakeLLMService:
        async def generate(self, **kwargs):  # noqa: ANN003
            return Result.ok(json.dumps(_short_answer_interaction_payload()))

    async def fake_previous_turns(
        self: AiCoachSessionService,
        session_id: str,
    ) -> list[dict[str, object]]:
        assert session_id == "session-1"
        return []

    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.PromptTemplateRevisionResolver",
        FakeResolver,
    )
    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.PromptTemplateService",
        FakePromptTemplateService,
    )
    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.LLMService",
        FakeLLMService,
    )
    monkeypatch.setattr(
        AiCoachSessionService,
        "_get_previous_turns",
        fake_previous_turns,
    )
    session = SimpleNamespace(
        session_id="session-1",
        module_key="business_skills",
        prompt_template_id="11111111-1111-1111-1111-111111111111",
        prompt_revision_id=None,
        prompt_contract_hash=None,
        article_snapshot={"title": "商务技巧", "summary": "摘要", "chapters": []},
        config_snapshot={
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
            "mastery_threshold": 80,
            "output_schema_version": "ai_coach_interaction_v1",
            "generation_model": None,
            "scoring_model": None,
            "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
            "failure_behavior": "skip_turn",
            "pinned_schema_version": "ai_coach_interaction_v1",
            "active_coach_mode": "mixed_drill",
        },
    )
    turn = SimpleNamespace(turn_number=1)
    service = AiCoachSessionService(_FakeDb())  # type: ignore[arg-type]

    with pytest.raises(AiCoachSessionServiceError) as exc_info:
        asyncio.run(
            service.generate_interaction(
                session,  # pyright: ignore[reportArgumentType]
                turn,  # pyright: ignore[reportArgumentType]
            )
        )

    assert exc_info.value.code == "[AI_COACH_INTERACTION_INVALID]"
    assert not hasattr(turn, "interaction_snapshot")


def test_score_short_answer_accepts_resolver_ok_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_compile_kwargs: dict[str, object] = {}
    captured_llm_configs: list[object] = []

    class FakeResolver:
        def __init__(self, db: object) -> None:
            self._db = db

        async def resolve(
            self,
            *,
            template_id: str,
            prompt_revision_id: str | None,
        ) -> PromptRevisionResolution:
            assert template_id == "22222222-2222-2222-2222-222222222222"
            assert prompt_revision_id is None
            return _prompt_resolution()

    class FakePromptTemplateService:
        def __init__(self, db: object) -> None:
            self._db = db

        def compile_runtime_prompt_contract(self, **kwargs):  # noqa: ANN003
            captured_compile_kwargs.update(kwargs)
            return Result.ok(_compiled_contract())

    class FakeLLMService:
        def __init__(self, config: object | None = None) -> None:
            captured_llm_configs.append(config)

        @property
        def provider(self) -> str:
            return "openai"

        @property
        def model_name(self) -> str:
            return "coach-score-model"

        async def generate(self, **kwargs):  # noqa: ANN003
            return Result.ok(
                json.dumps(
                    {
                        "score": 86,
                        "feedback": "回答完整。",
                        "missed_points": ["补充客户称呼"],
                    }
                )
            )

    model_config = SimpleNamespace(
        id="model-config-1",
        provider="openai",
        base_url="https://llm.example/v1",
        model_name="coach-score-model",
        extra_config={"temperature": 0.1},
    )

    def fake_resolve_model(model_name: str | None) -> object | None:
        assert model_name == "coach-score-model"
        return model_config

    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.PromptTemplateRevisionResolver",
        FakeResolver,
    )
    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.PromptTemplateService",
        FakePromptTemplateService,
    )
    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.LLMService",
        FakeLLMService,
    )
    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.resolve_ai_coach_llm_model_config",
        fake_resolve_model,
    )
    service = AiCoachSessionService(_FakeDb())  # type: ignore[arg-type]
    runtime_metadata: dict[str, object] = {}

    result = asyncio.run(
        service.score_short_answer(
            answer_text="先确认客户来访目的，再安排接待。",
            reference_answer="确认目的并安排接待。",
            scoring_rubric=AiCoachScoringRubricV1(
                max_score=100,
                points=[
                    AiCoachScoringPointV1(
                        key="confirm-purpose",
                        score=100,
                        description="确认客户来访目的",
                    )
                ],
                partial_credit_policy="all_or_nothing",
            ),
            session_id="session-1",
            scoring_prompt_template_id="22222222-2222-2222-2222-222222222222",
            scoring_model="coach-score-model",
            runtime_metadata_out=runtime_metadata,
        )
    )

    assert result.is_success
    assert result.value is not None
    assert result.value.score == 86
    assert result.value.feedback == "回答完整。"
    assert captured_llm_configs == [model_config]
    assert captured_compile_kwargs["model_config"] == {
        "provider": "openai",
        "base_url": "https://llm.example/v1",
        "model_name": "coach-score-model",
        "extra_config": {"temperature": 0.1},
    }
    assert runtime_metadata == {
        "prompt_template_id": "11111111-1111-1111-1111-111111111111",
        "prompt_revision_id": "head",
        "contract_hash": "hash-1",
        "requested_model": "coach-score-model",
        "model_config_id": "model-config-1",
        "model_provider": "openai",
        "model_name": "coach-score-model",
    }


def test_create_session_v1_rejects_disallowed_coach_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePathConfigService:
        def __init__(self, db: object) -> None:
            self._db = db

        async def get_config(self) -> dict[str, object]:
            return {
                "path": _path_payload_with_ai_coach(mastery_threshold=80),
                "active_revision_id": None,
                "active_revision_no": None,
            }

    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.SalesTrainerPathConfigService",
        FakePathConfigService,
    )
    service = AiCoachSessionService(_FakeDb())  # type: ignore[arg-type]

    with pytest.raises(AiCoachSessionServiceError) as exc_info:
        asyncio.run(
            service.create_session_v1(
                user_id="user-1",
                module_key="business_skills",
                coach_mode="short_answer_drill",
            )
        )

    assert exc_info.value.code == "[AI_COACH_INTERACTION_TYPE_NOT_ALLOWED]"
    assert exc_info.value.status_code == 403


def test_create_session_v1_rejects_disallowed_explicit_interaction_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePathConfigService:
        def __init__(self, db: object) -> None:
            self._db = db

        async def get_config(self) -> dict[str, object]:
            return {
                "path": _path_payload_with_ai_coach(mastery_threshold=80),
                "active_revision_id": None,
                "active_revision_no": None,
            }

    monkeypatch.setattr(
        "sales_trainer.services.ai_coach_session_service.SalesTrainerPathConfigService",
        FakePathConfigService,
    )
    service = AiCoachSessionService(_FakeDb())  # type: ignore[arg-type]

    with pytest.raises(AiCoachSessionServiceError) as exc_info:
        asyncio.run(
            service.create_session_v1(
                user_id="user-1",
                module_key="business_skills",
                interaction_type="short_answer",
            )
        )

    assert exc_info.value.code == "[AI_COACH_INTERACTION_TYPE_NOT_ALLOWED]"
    assert exc_info.value.status_code == 403


def test_submit_feedback_projection_drops_contaminated_public_interaction() -> None:
    session = SimpleNamespace(
        session_id="session-1",
        mastery_state=None,
    )
    turn = SimpleNamespace(
        turn_id="turn-1",
        turn_number=1,
        public_interaction={
            "schema_version": "ai_coach_interaction_public_v1",
            "interaction_id": "session-1:1",
            "session_id": "session-1",
            "turn_number": 1,
            "interaction_type": "single_choice",
            "stem": "客户到访前最应该确认哪项信息？",
            "options": [
                {"option_id": "A", "text": "客户到访时间"},
                {"option_id": "B", "text": "天气"},
            ],
            "answer_constraints": {"min_selected": 1, "max_selected": 1},
            "answer_key": {"option_ids": ["A"]},
        },
        answer_payload={"variant": "choice", "option_ids": ["A"]},
        score=100,
        max_score=100,
        ai_feedback="回答正确。",
        missed_points=[],
    )

    payload = _serialize_turn_feedback_public(
        session=session,
        turn=turn,
        score_result=None,
        next_turn_available=False,
    )

    assert payload["turn"]["public_interaction"] is None
    assert "answer_key" not in json.dumps(payload, ensure_ascii=False)


def test_validate_output_v1_roundtrip() -> None:
    service = AiCoachScoringService()
    raw = {
        "score": 88,
        "max_score": 100,
        "feedback": "掌握良好",
        "missed_points": ["细节一"],
        "next_question": "下一步？",
        "passed": True,
        "reasoning": "完整回答",
    }
    result = service.validate_output(raw, "v1")
    assert result.is_success
    assert result.value is not None
    assert result.value.passed is True
    assert result.value.missed_points == ["细节一"]


def test_validate_output_unknown_schema_version_fails() -> None:
    service = AiCoachScoringService()
    result = service.validate_output({"score": 10, "feedback": "x"}, "v99")
    assert not result.is_success
    assert "UNKNOWN_SCHEMA_VERSION" in (result.fallback or "")


def test_score_turn_not_configured() -> None:
    service = AiCoachScoringService()
    service._llm_service = _StubLLM(None)  # type: ignore[attr-defined]
    result = asyncio.run(
        service.score_turn(
            question="q",
            user_answer="a",
            config={"mastery_threshold": 70, "output_schema_version": "v1"},
            session_id="s1",
        )
    )
    assert not result.is_success
    assert "LLM_NOT_CONFIGURED" in (result.fallback or "")


def test_score_turn_invalid_json_response() -> None:
    service = AiCoachScoringService()
    service._llm_service = _StubLLM("not-json at all")  # type: ignore[attr-defined]
    result = asyncio.run(
        service.score_turn(
            question="q",
            user_answer="a",
            config={"output_schema_version": "v1"},
            session_id="s1",
        )
    )
    assert not result.is_success
    assert result.fallback == "[AI_COACH_SCORING_RESPONSE_INVALID]"


def test_score_turn_schema_validation_failure() -> None:
    service = AiCoachScoringService()
    service._llm_service = _StubLLM('{"score": 200, "feedback": "x"}')  # type: ignore[attr-defined]
    result = asyncio.run(
        service.score_turn(
            question="q",
            user_answer="a",
            config={"output_schema_version": "v1"},
            session_id="s1",
        )
    )
    assert not result.is_success
    assert "VALIDATION" in (result.fallback or "")


def test_score_turn_success_returns_normalized_dict() -> None:
    service = AiCoachScoringService()
    raw = {
        "score": 75,
        "max_score": 100,
        "feedback": "良好",
        "missed_points": ["a"],
        "next_question": "next?",
        "passed": False,
        "reasoning": None,
    }
    import json as _json

    service._llm_service = _StubLLM(_json.dumps(raw))  # type: ignore[attr-defined]
    result = asyncio.run(
        service.score_turn(
            question="q",
            user_answer="a",
            config={"output_schema_version": "v1"},
            session_id="s1",
        )
    )
    assert result.is_success
    assert result.value is not None
    assert result.value["score"] == 75
    assert result.value["feedback"] == "良好"
    assert result.value["missed_points"] == ["a"]
    assert result.value["raw_model_output"] == raw


def test_validate_answer_payload_rejects_unknown_choice_option() -> None:
    interaction = _single_choice_interaction()
    payload = AiCoachAnswerPayloadV1.model_validate(
        {"variant": "choice", "option_ids": ["Z"]}
    )

    with pytest.raises(AiCoachSessionServiceError) as exc_info:
        AiCoachSessionService._validate_answer_payload(interaction, payload)

    assert exc_info.value.code == "[AI_COACH_ANSWER_OPTION_INVALID]"


def test_validate_answer_payload_rejects_text_for_choice_interaction() -> None:
    interaction = _single_choice_interaction()
    payload = AiCoachAnswerPayloadV1.model_validate(
        {"variant": "text", "text": "我选 A"}
    )

    with pytest.raises(AiCoachSessionServiceError) as exc_info:
        AiCoachSessionService._validate_answer_payload(interaction, payload)

    assert exc_info.value.code == "[AI_COACH_ANSWER_PAYLOAD_INVALID]"


def test_submit_ai_coach_turn_v1_returns_submitted_turn_feedback_when_next_turn_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted_turn = SimpleNamespace(
        turn_id="turn-1",
        turn_number=1,
        public_interaction={"stem": "已提交题目"},
        answer_payload={"variant": "choice", "option_ids": ["A"]},
        score=88,
        max_score=100,
        ai_feedback="回答正确。",
        missed_points=[],
    )
    next_turn = SimpleNamespace(
        turn_id="turn-2",
        turn_number=2,
        public_interaction={"stem": "下一题"},
        answer_payload=None,
        score=None,
        max_score=100,
        ai_feedback=None,
        missed_points=[],
    )
    session = SimpleNamespace(
        session_id="session-1",
        user_id="user-1",
        mastery_state=None,
        status="in_progress",
    )

    class FakeAiCoachSessionService:
        def __init__(self, db: object) -> None:
            self._latest_calls = 0

        async def get_session(
            self,
            session_id: str,
            user_id: str,
        ) -> object:
            assert session_id == "session-1"
            assert user_id == "user-1"
            return session

        async def _get_latest_turn(self, session_id: str) -> object:
            assert session_id == "session-1"
            self._latest_calls += 1
            return submitted_turn if self._latest_calls == 1 else next_turn

        async def submit_turn_v1(
            self,
            *,
            session_id: str,
            answer_payload: object,
            actor: object,
        ) -> object:
            assert session_id == "session-1"
            assert actor is current_user
            assert answer_payload is payload.answer_payload
            return submitted_turn

    current_user = SimpleNamespace(user_id="user-1")
    payload = AiCoachTurnSubmitV1.model_validate(
        {"answer_payload": {"variant": "choice", "option_ids": ["A"]}}
    )
    monkeypatch.setattr(
        "sales_trainer.ai_coach_api.AiCoachSessionService",
        FakeAiCoachSessionService,
    )

    response = asyncio.run(
        submit_ai_coach_turn_v1(
            "session-1",
            "turn-1",
            payload,
            db=object(),  # type: ignore[arg-type]
            current_user=current_user,  # type: ignore[arg-type]
        )
    )

    body = json.loads(response.body)
    assert body["data"]["turn"]["turn_id"] == "turn-1"
    assert body["data"]["score_result"]["score"] == 88
    assert body["data"]["next_turn_available"] is True


def _single_choice_interaction() -> AiCoachInteractionInternalV1:
    return AiCoachInteractionInternalV1.model_validate(
        {
            "schema_version": "ai_coach_interaction_v1",
            "interaction_type": "single_choice",
            "stem": "客户到访前最应该确认哪项信息？",
            "options": [
                {"option_id": "A", "text": "客户到访时间"},
                {"option_id": "B", "text": "天气"},
            ],
            "answer_key": {"option_ids": ["A"], "reference_answer": None},
            "scoring_rubric": {
                "max_score": 100,
                "points": [
                    {"key": "A", "score": 100, "description": "确认到访时间"}
                ],
                "partial_credit_policy": "all_or_nothing",
            },
            "feedback_guidance": {
                "correct": "回答正确。",
                "incorrect": "请先确认客户到访安排。",
            },
        }
    )


def _path_payload_with_ai_coach(*, mastery_threshold: int) -> dict[str, object]:
    return {
        "path_key": "newcomer_training_path_v1",
        "title": "新人训练路径",
        "goal_title": "完成新人训练",
        "description": None,
        "enabled": True,
        "modules": [
            {
                "module_key": "business_skills",
                "module_type": "article_exam",
                "enabled": True,
                "order_index": 1,
                "title": "商务技巧",
                "description": "商务技巧说明",
                "target_unit_id": None,
                "learning_content_id": None,
                "exam_paper_id": None,
                "disabled_reason": None,
                "unlock_after_unit_ids": [],
                "completion_rule": "passed",
                "primary_action_label": "开始学习",
                "retry_action_label": None,
                "review_action_label": None,
                "guidance_templates": {},
                "ai_coach": {
                    "enabled": True,
                    "coach_mode": "mixed_drill",
                    "allowed_interaction_types": [
                        "single_choice",
                        "multiple_choice",
                    ],
                    "prompt_template_id": "11111111-1111-1111-1111-111111111111",
                    "prompt_revision_id": None,
                    "prompt_contract_hash": None,
                    "scoring_prompt_template_id": None,
                    "scoring_prompt_revision_id": None,
                    "scoring_contract_hash": None,
                    "min_turns": 3,
                    "max_turns": 10,
                    "mastery_threshold": mastery_threshold,
                    "output_schema_version": "ai_coach_interaction_v1",
                    "generation_model": None,
                    "scoring_model": None,
                    "retry_policy": {"max_retries": 2, "retry_backoff": 1.0},
                    "failure_behavior": "skip_turn",
                },
            }
        ],
    }
