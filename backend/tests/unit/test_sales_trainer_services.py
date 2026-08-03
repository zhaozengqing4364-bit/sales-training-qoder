from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioSubmission,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    QuizAnswerSubmit,
    QuizAttemptCreate,
    SalesTrainerMaterialCreate,
    SalesTrainerMaterialVersionCreate,
    SalesTrainerUnitCreate,
    SalesTrainerUnitUpdate,
    UnitQuestionBinding,
)
from sales_trainer.services.deucate_scoring_service import (
    DeucateScoringService,
    HttpDeucateClient,
)
from sales_trainer.services.material_service import SalesTrainerMaterialService
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.question_bank import QuestionBankAdapter
from sales_trainer.services.quiz_service import QuizService, QuizServiceError
from sales_trainer.services.short_answer_scoring_service import (
    ShortAnswerScoreOutcome,
    ShortAnswerScoringService,
)
from sales_trainer.services.transcription_service import TranscriptionService
from sales_trainer.services.unit_service import SalesTrainerUnitError, UnitService


class FakeShortAnswerScoringService:
    async def score(self, question: QuestionItem, *, answer_text: str):
        assert question.title == "客户价值理解"
        assert "数据流动治理" in answer_text
        return Result.ok(
            ShortAnswerScoreOutcome(
                score=80,
                passed=True,
                feedback="回答覆盖核心价值，但可以补充客户场景。",
                reason="命中数据流动治理和客户价值。",
                raw_response={"score": 80},
            )
        )


class FailingShortAnswerLLMService:
    async def generate(self, **kwargs):
        raise RuntimeError("invalid token")


class FakeShortAnswerLLMService:
    provider = "deepseek"
    model_name = "deepseek-chat"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        return Result.ok(
            '{"score": 0, "feedback": "AI 判断该答案没有提供具体做法。", '
            '"reason": "answer_has_no_action"}'
        )


class FakeAsrService:
    provider_name = "fake-asr"

    async def transcribe_file(self, audio_file: str):
        assert Path(audio_file).exists()
        return Result.ok("远程录音转写成功")


class FakeRemoteSigner:
    def generate_get_url(self, object_key: str, expires: int = 3600) -> str:
        assert object_key == "sales-trainer/audio/user/remote.wav"
        assert expires == 3600
        return "https://signed.example.com/remote.wav"


class FlakyJsonClient:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "fake-deucate"

    async def score(self, *, system_prompt: str, prompt: str):
        self.calls += 1
        if self.calls == 1:
            return Result.fail("[DEUCATE_RESPONSE_INVALID]")
        return Result.ok({"total_score": 75, "summary": "ok"})


class OutOfRangeScoreClient:
    @property
    def model_name(self) -> str:
        return "fake-deucate"

    async def score(self, *, system_prompt: str, prompt: str):
        return Result.ok({"total_score": 150, "summary": "too high"})


def _user(role: str = "user") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"sales-trainer-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Sales Trainer {role}",
        email=f"sales-trainer-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_should_publish_quiz_unit_and_score_choice_answer(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    category = QuestionCategory(
        category_id="sales-trainer-category",
        name="石犀题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="sales-trainer-question-1",
        category_id=category.category_id,
        title="产品定位",
        stem="石犀核心定位是什么？",
        reference_answer="治理一切数据流动",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "数据流动治理"},
                {"value": "B", "label": "招聘管理"},
            ],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    test_db.add_all([category, question])
    await test_db.commit()

    unit_service = UnitService(test_db)
    unit = await unit_service.create_unit(
        SalesTrainerUnitCreate(
            name="产品基础做题",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=test_user,
    )
    unit = await unit_service.publish_unit(unit, actor=test_user)

    attempt = await QuizService(test_db).submit_attempt(
        QuizAttemptCreate(
            unit_id=unit.unit_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=question.question_id,
                    answer_payload="A",
                )
            ],
        ),
        actor=test_user,
    )

    assert attempt.status == "scored"
    assert float(attempt.total_score) == 10
    assert attempt.passed is True

    serialized = await QuizService(test_db).serialize_attempt(attempt)
    answer = serialized["answers"][0]
    assert answer["question_title"] == "产品定位"
    assert answer["question_stem"] == "石犀核心定位是什么？"
    assert answer["answer_payload"] == "A"
    assert answer["correct_answer"] == "A"
    assert answer["options"] == [
        {"value": "A", "label": "数据流动治理"},
        {"value": "B", "label": "招聘管理"},
    ]


@pytest.mark.asyncio
async def test_should_reject_incomplete_quiz_attempt_before_creating_snapshot(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    category = QuestionCategory(
        category_id="sales-trainer-quiz-incomplete-category",
        name="空卷边界题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="quiz-incomplete-question-1",
        category_id=category.category_id,
        title="产品定位",
        stem="石犀核心定位是什么？",
        reference_answer="A",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [
                {"value": "A", "label": "数据流动治理"},
                {"value": "B", "label": "招聘管理"},
            ],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    test_db.add_all([category, question])
    await test_db.commit()

    unit_service = UnitService(test_db)
    unit = await unit_service.create_unit(
        SalesTrainerUnitCreate(
            name="产品基础空卷边界",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=test_user,
    )
    unit = await unit_service.publish_unit(unit, actor=test_user)

    with pytest.raises(QuizServiceError) as error:
        await QuizService(test_db).submit_attempt(
            QuizAttemptCreate(
                unit_id=unit.unit_id,
                answers=[
                    QuizAnswerSubmit(
                        question_id=question.question_id,
                        answer_payload="",
                    )
                ],
            ),
            actor=test_user,
        )

    assert error.value.code == "[QUIZ_ANSWER_INCOMPLETE]"
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_should_score_short_answer_with_ai_and_store_feedback_snapshot(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    category = QuestionCategory(
        category_id="sales-trainer-short-answer-category",
        name="简答题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="short-answer-question-1",
        category_id=category.category_id,
        title="客户价值理解",
        stem="请说明石犀如何帮助客户治理数据流动。",
        reference_answer="石犀帮助客户围绕数据流动建立可控、可审计、可运营的治理体系。",
        scoring_criteria={
            "question_type": "short_answer",
            "dimensions": ["value_logic", "customer_context"],
            "explanation": "优秀答案应同时说明客户场景、数据流动治理价值和下一步行动。",
            "ai_scoring": {"enabled": True, "pass_threshold": 70},
        },
        scoring_dimensions=["value_logic", "customer_context"],
        status="published",
        usage_scope="sales_trainer",
    )
    test_db.add_all([category, question])
    await test_db.commit()

    unit_service = UnitService(test_db)
    unit = await unit_service.create_unit(
        SalesTrainerUnitCreate(
            name="客户价值简答",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 8}},
            questions=[
                UnitQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=test_user,
    )
    unit = await unit_service.publish_unit(unit, actor=test_user)

    quiz_service = QuizService(
        test_db,
        short_answer_scoring_service=FakeShortAnswerScoringService(),
    )
    attempt = await quiz_service.submit_attempt(
        QuizAttemptCreate(
            unit_id=unit.unit_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=question.question_id,
                    answer_payload="石犀能围绕数据流动治理帮助客户形成可审计的管理闭环。",
                )
            ],
        ),
        actor=test_user,
    )

    assert attempt.status == "scored"
    assert float(attempt.total_score) == 8
    assert attempt.passed is True

    serialized = await quiz_service.serialize_attempt(attempt)
    answer = serialized["answers"][0]
    assert answer["question_title"] == "客户价值理解"
    assert answer["reference_answer"] == question.reference_answer
    assert (
        answer["explanation"]
        == "优秀答案应同时说明客户场景、数据流动治理价值和下一步行动。"
    )
    assert answer["normalized_score"] == 80
    assert answer["score"] == 8
    assert answer["is_correct"] is True
    assert answer["scoring_feedback"] == "回答覆盖核心价值，但可以补充客户场景。"
    assert answer["scoring_reason"] == "命中数据流动治理和客户价值。"


@pytest.mark.asyncio
async def test_should_call_llm_for_non_empty_low_quality_short_answer() -> None:
    question = QuestionItem(
        question_id="short-answer-low-quality-q1",
        category_id="short-answer-low-quality-category",
        title="客户拜访要点",
        stem="请说明商务拜访时需要注意的两个要点。",
        reference_answer="提前确认客户背景与目标，准时到达并保持尊重、清晰表达。",
        scoring_criteria={
            "question_type": "short_answer",
            "ai_scoring": {"enabled": True, "pass_threshold": 70},
        },
        scoring_dimensions=["respect_boundaries"],
        status="published",
        usage_scope="sales_trainer",
    )
    fake_llm = FakeShortAnswerLLMService()
    service = ShortAnswerScoringService(llm_service=fake_llm)

    result = await service.score(question, answer_text="哈哈")

    assert result.is_success
    assert result.value is not None
    assert len(fake_llm.calls) == 1
    assert "哈哈" in str(fake_llm.calls[0]["prompt"])
    assert result.value.score == 0
    assert result.value.passed is False
    assert result.value.reason == "answer_has_no_action"
    assert result.value.feedback == "AI 判断该答案没有提供具体做法。"
    assert result.value.scoring_source == "ai_llm"
    assert result.value.scoring_provider == "deepseek"
    assert result.value.scoring_model == "deepseek-chat"
    assert isinstance(result.value.scoring_latency_ms, int)


@pytest.mark.asyncio
async def test_should_submit_short_answer_attempt_when_ai_scoring_provider_fails(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    category = QuestionCategory(
        category_id="sales-trainer-short-answer-failed-provider-category",
        name="简答题评分失败题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="short-answer-provider-fails-q1",
        category_id=category.category_id,
        title="客户价值理解",
        stem="请说明石犀如何帮助客户治理数据流动。",
        reference_answer="石犀帮助客户围绕数据流动建立可控、可审计、可运营的治理体系。",
        scoring_criteria={
            "question_type": "short_answer",
            "ai_scoring": {"enabled": True, "pass_threshold": 70},
        },
        scoring_dimensions=["value_logic"],
        status="published",
        usage_scope="sales_trainer",
    )
    test_db.add_all([category, question])
    await test_db.commit()

    unit_service = UnitService(test_db)
    unit = await unit_service.create_unit(
        SalesTrainerUnitCreate(
            name="客户价值简答评分失败",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 8}},
            questions=[
                UnitQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=test_user,
    )
    unit = await unit_service.publish_unit(unit, actor=test_user)
    quiz_service = QuizService(
        test_db,
        short_answer_scoring_service=ShortAnswerScoringService(
            llm_service=FailingShortAnswerLLMService(),
        ),
    )

    attempt = await quiz_service.submit_attempt(
        QuizAttemptCreate(
            unit_id=unit.unit_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=question.question_id,
                    answer_payload="石犀能围绕数据流动治理帮助客户形成可审计的管理闭环。",
                )
            ],
        ),
        actor=test_user,
    )

    assert attempt.status == "submitted"
    assert attempt.total_score is None
    assert attempt.max_score is None
    assert attempt.passed is None

    serialized = await quiz_service.serialize_attempt(attempt)
    answer = serialized["answers"][0]
    assert answer["question_title"] == "客户价值理解"
    assert (
        answer["answer_payload"]
        == "石犀能围绕数据流动治理帮助客户形成可审计的管理闭环。"
    )
    assert answer["score"] is None
    assert answer["normalized_score"] is None
    assert answer["scoring_feedback"] is None


@pytest.mark.asyncio
async def test_should_reject_and_audit_unsupported_quiz_question_structure(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    category = QuestionCategory(
        category_id="sales-trainer-unsupported-category",
        name="不完整题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="sales-trainer-unsupported-question-1",
        category_id=category.category_id,
        title="缺少选项结构",
        stem="石犀核心定位是什么？",
        reference_answer="治理一切数据流动",
        scoring_criteria={
            "question_type": "single_choice",
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    test_db.add_all([category, question])
    await test_db.commit()

    with pytest.raises(SalesTrainerUnitError) as exc:
        await UnitService(test_db).create_unit(
            SalesTrainerUnitCreate(
                name="不完整题型做题",
                unit_type="quiz",
                questions=[
                    UnitQuestionBinding(
                        question_id=question.question_id,
                        order_index=1,
                        points=10,
                    )
                ],
            ),
            actor=test_user,
        )

    assert exc.value.code == "[QUESTION_TYPE_UNSUPPORTED]"

    logs, total = await OperationLogService(test_db).list_logs(
        actor_id=str(test_user.user_id),
        target_type="sales_trainer_unit",
    )
    assert total == 1
    assert logs[0].action == "question_type_unsupported"
    assert logs[0].metadata_json["questions"][0]["reason"] == "missing_choice_options"


@pytest.mark.asyncio
async def test_should_reject_invalid_quiz_pass_threshold_before_publish(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    category = QuestionCategory(
        category_id="sales-trainer-threshold-category",
        name="阈值题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="sales-trainer-threshold-question-1",
        category_id=category.category_id,
        title="产品定位",
        stem="石犀核心定位是什么？",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "数据流动治理"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    test_db.add_all([category, question])
    await test_db.commit()

    with pytest.raises(SalesTrainerUnitError) as exc:
        await UnitService(test_db).create_unit(
            SalesTrainerUnitCreate(
                name="非法阈值做题",
                unit_type="quiz",
                config={"quiz": {"pass_threshold": "not-a-number"}},
                questions=[
                    UnitQuestionBinding(
                        question_id=question.question_id,
                        order_index=1,
                        points=10,
                    )
                ],
            ),
            actor=test_user,
        )

    assert exc.value.code == "[QUIZ_PASS_THRESHOLD_INVALID]"


@pytest.mark.asyncio
async def test_should_reject_invalid_quiz_pass_threshold_on_config_only_update(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    category = QuestionCategory(
        category_id="sales-trainer-threshold-update-category",
        name="阈值更新题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="threshold-update-question-1",
        category_id=category.category_id,
        title="产品定位",
        stem="石犀核心定位是什么？",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "数据流动治理"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status="published",
        usage_scope="sales_trainer",
    )
    test_db.add_all([category, question])
    await test_db.commit()

    service = UnitService(test_db)
    unit = await service.create_unit(
        SalesTrainerUnitCreate(
            name="阈值更新做题",
            unit_type="quiz",
            config={"quiz": {"pass_threshold": 10}},
            questions=[
                UnitQuestionBinding(
                    question_id=question.question_id,
                    order_index=1,
                    points=10,
                )
            ],
        ),
        actor=test_user,
    )

    with pytest.raises(SalesTrainerUnitError) as exc:
        await service.update_unit(
            unit,
            SalesTrainerUnitUpdate(config={"quiz": {"pass_threshold": "bad"}}),
            actor=test_user,
        )

    assert exc.value.code == "[QUIZ_PASS_THRESHOLD_INVALID]"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question_status", "usage_scope"),
    [
        ("published", "general"),
        ("draft", "sales_trainer"),
        ("archived", "sales_trainer"),
    ],
)
async def test_should_reject_quiz_unit_binding_outside_published_sales_scope(
    test_db: AsyncSession,
    test_user: User,
    question_status: str,
    usage_scope: str,
) -> None:
    category = QuestionCategory(
        category_id=f"{usage_scope}-{question_status}-category",
        name="绑定边界题库",
        order_index=1,
        usage_scope=usage_scope,
    )
    question = QuestionItem(
        question_id=f"{usage_scope}-{question_status}-question",
        category_id=category.category_id,
        title="绑定边界",
        stem="只有已发布销售训练题可绑定。",
        scoring_criteria={
            "question_type": "single_choice",
            "options": [{"value": "A", "label": "合规"}],
            "correct_answer": "A",
        },
        scoring_dimensions=["content_accuracy"],
        status=question_status,
        usage_scope=usage_scope,
    )
    test_db.add_all([category, question])
    await test_db.commit()

    with pytest.raises(SalesTrainerUnitError) as exc:
        await UnitService(test_db).create_unit(
            SalesTrainerUnitCreate(
                name="绑定边界训练单元",
                unit_type="quiz",
                questions=[
                    UnitQuestionBinding(
                        question_id=question.question_id,
                        order_index=1,
                        points=10,
                    )
                ],
            ),
            actor=test_user,
        )

    assert exc.value.code == "[QUESTION_ITEM_NOT_FOUND_OR_UNPUBLISHED]"


@pytest.mark.asyncio
async def test_should_bridge_remote_audio_key_to_local_asr_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SALES_TRAINER_ASR_MODE", "legacy")

    async def fake_fetcher(signed_url: str, local_path: Path) -> None:
        assert signed_url == "https://signed.example.com/remote.wav"
        local_path.write_bytes(b"remote audio")

    service = TranscriptionService(
        asr_service=FakeAsrService(),
        remote_audio_fetcher=fake_fetcher,
        signer_factory=lambda: FakeRemoteSigner(),
    )

    result = await service.transcribe_file("oss://sales-trainer/audio/user/remote.wav")

    assert result.provider == "fake-asr"
    assert result.transcript_text == "远程录音转写成功"
    assert result.raw_payload == {
        "source": "asr_service.transcribe_file",
        "remote_storage_key": "oss://sales-trainer/audio/user/remote.wav",
    }


def test_should_parse_false_string_for_true_false_question() -> None:
    question = QuestionItem(
        question_id="sales-trainer-question-true-false",
        category_id="sales-trainer-category",
        title="判断题",
        stem="石犀是招聘管理系统。",
        scoring_criteria={"question_type": "true_false", "correct_bool": False},
        scoring_dimensions=[],
        status="published",
    )

    is_correct, score = QuestionBankAdapter(None).grade(
        question,
        answer_payload="false",
        points=5,
    )

    assert is_correct is True
    assert score == 5


@pytest.mark.asyncio
async def test_should_retry_once_when_deucate_returns_non_json() -> None:
    client = FlakyJsonClient()
    scoring = DeucateScoringService(client=client)
    submission = SalesTrainerAudioSubmission(
        purpose="general_audio_scoring",
        original_filename="audio.wav",
        content_type="audio/wav",
        size_bytes=1,
        storage_key="/tmp/audio.wav",
        user_id="user-1",
    )
    prompt = SalesTrainerAudioScorePrompt(
        system_prompt="system",
        scoring_template="transcript={transcript}",
    )

    outcome = await scoring.score_audio(
        submission=submission,
        prompt=prompt,
        transcript_text="hello",
        unit_name="unit",
        pass_threshold=70,
    )

    assert client.calls == 2
    assert outcome.total_score == 75
    assert outcome.error_code is None


@pytest.mark.asyncio
async def test_should_normalize_out_of_range_deucate_total_score() -> None:
    scoring = DeucateScoringService(client=OutOfRangeScoreClient())
    submission = SalesTrainerAudioSubmission(
        purpose="general_audio_scoring",
        original_filename="audio.wav",
        content_type="audio/wav",
        size_bytes=1,
        storage_key="/tmp/audio.wav",
        user_id="user-1",
    )
    prompt = SalesTrainerAudioScorePrompt(
        system_prompt="system",
        scoring_template="transcript={transcript}",
    )

    outcome = await scoring.score_audio(
        submission=submission,
        prompt=prompt,
        transcript_text="hello",
        unit_name="unit",
        pass_threshold=70,
    )

    assert outcome.total_score == 100
    assert outcome.passed is True
    assert outcome.raw_response == {"total_score": 150, "summary": "too high"}


@pytest.mark.asyncio
async def test_should_return_typed_error_when_deucate_timeout_config_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEUCATE_TIMEOUT_SECONDS", "not-a-number")
    scoring = DeucateScoringService(
        client=HttpDeucateClient(
            base_url="https://deucate.example.com",
            api_key="secret",
        )
    )
    submission = SalesTrainerAudioSubmission(
        purpose="general_audio_scoring",
        original_filename="audio.wav",
        content_type="audio/wav",
        size_bytes=1,
        storage_key="/tmp/audio.wav",
        user_id="user-1",
    )
    prompt = SalesTrainerAudioScorePrompt(
        system_prompt="system",
        scoring_template="transcript={transcript}",
    )

    outcome = await scoring.score_audio(
        submission=submission,
        prompt=prompt,
        transcript_text="hello",
        unit_name="unit",
        pass_threshold=70,
    )

    assert outcome.error_code == "[DEUCATE_CONFIG_INVALID]"


@pytest.mark.asyncio
async def test_should_publish_material_version_as_single_current_version(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    service = SalesTrainerMaterialService(test_db)
    material = await service.create_material(
        SalesTrainerMaterialCreate(
            material_key="company_master_deck",
            name="公司主胶片",
            material_type="ppt_deck",
            purpose="ppt_pitch",
        ),
        actor=admin,
    )
    first = await service.create_version(
        material,
        SalesTrainerMaterialVersionCreate(
            version_label="v2026.05",
            title="公司主胶片 2026-05",
            file_name="deck-v1.pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            file_size_bytes=100,
            storage_key="/tmp/deck-v1.pptx",
        ),
        actor=admin,
    )
    second = await service.create_version(
        material,
        SalesTrainerMaterialVersionCreate(
            version_label="v2026.06",
            title="公司主胶片 2026-06",
            file_name="deck-v2.pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            file_size_bytes=120,
            storage_key="/tmp/deck-v2.pptx",
        ),
        actor=admin,
    )

    await service.publish_version(first, actor=admin)
    await service.publish_version(second, actor=admin)
    refreshed_material = await service.get_material(material.material_id)
    refreshed_first = await service.get_version(first.version_id)

    assert refreshed_material is not None
    assert refreshed_material.current_version_id == second.version_id
    assert refreshed_material.status == "published"
    assert refreshed_first is not None
    assert refreshed_first.status == "archived"


@pytest.mark.asyncio
async def test_find_attempt_by_client_token_returns_existing_attempt(
    test_db: AsyncSession,
) -> None:
    """R7: 同一 client_token 重复提交时，helper 应命中已存在 attempt（幂等）。"""

    from sales_trainer.services.quiz_service import find_attempt_by_client_token

    owner = _user("user")
    other = _user("user")
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="做题单元",
        unit_type="quiz",
        config={"quiz": {"pass_threshold": 10}},
        status="published",
        created_by=owner.user_id,
        updated_by=owner.user_id,
    )
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=owner.user_id,
        status="scored",
        client_token="token-abc",
    )
    test_db.add_all([owner, other, unit, attempt])
    await test_db.commit()

    found = await find_attempt_by_client_token(
        test_db, client_token="token-abc", user_id=str(owner.user_id)
    )
    assert found is not None
    assert found.attempt_id == attempt.attempt_id

    # 他人提交同一 token 不应命中（防越权）
    other_found = await find_attempt_by_client_token(
        test_db, client_token="token-abc", user_id=str(other.user_id)
    )
    assert other_found is None


@pytest.mark.asyncio
async def test_find_attempt_by_client_token_returns_none_for_empty_token(
    test_db: AsyncSession,
) -> None:
    """R7: 无 client_token（旧客户端/旧数据）时返回 None，调用方正常新建。"""

    from sales_trainer.services.quiz_service import find_attempt_by_client_token

    owner = _user("user")
    test_db.add(owner)
    await test_db.commit()

    assert (
        await find_attempt_by_client_token(
            test_db, client_token=None, user_id=str(owner.user_id)
        )
        is None
    )
    assert (
        await find_attempt_by_client_token(
            test_db, client_token="", user_id=str(owner.user_id)
        )
        is None
    )


@pytest.mark.asyncio
async def test_quiz_attempt_client_token_column_persists(
    test_db: AsyncSession,
) -> None:
    """R7: client_token 列可读写，向后兼容 nullable（无 token 时为 None）。"""

    owner = _user("user")
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="做题单元",
        unit_type="quiz",
        config={"quiz": {"pass_threshold": 10}},
        status="published",
        created_by=owner.user_id,
        updated_by=owner.user_id,
    )
    attempt_with_token = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=owner.user_id,
        status="scored",
        client_token="persist-token",
    )
    attempt_without_token = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=owner.user_id,
        status="scored",
        client_token=None,
    )
    test_db.add_all([owner, unit, attempt_with_token, attempt_without_token])
    await test_db.commit()

    refreshed_with = await test_db.get(
        SalesTrainerQuizAttempt, attempt_with_token.attempt_id
    )
    refreshed_without = await test_db.get(
        SalesTrainerQuizAttempt, attempt_without_token.attempt_id
    )
    assert refreshed_with is not None
    assert refreshed_with.client_token == "persist-token"
    assert refreshed_without is not None
    assert refreshed_without.client_token is None
