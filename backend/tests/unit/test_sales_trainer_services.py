from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from curriculum_practice.models import LearningContent, QuestionCategory, QuestionItem
from sales_trainer.models import (
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerAudioTranscript,
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerUnit,
)
from sales_trainer.schemas import (
    AudioSubmissionCreate,
    NewcomerPathConfigSaveRequest,
    QuizAnswerSubmit,
    QuizAttemptCreate,
    SalesTrainerMaterialCreate,
    SalesTrainerMaterialVersionCreate,
    SalesTrainerUnitCreate,
    SalesTrainerUnitUpdate,
    UnitQuestionBinding,
)
from sales_trainer.services.audio_submission_service import (
    AudioSubmissionService,
    AudioSubmissionServiceError,
)
from sales_trainer.services.deucate_scoring_service import (
    AudioScoreOutcome,
    DeucateScoringService,
    HttpDeucateClient,
)
from sales_trainer.services.material_service import SalesTrainerMaterialService
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService
from sales_trainer.services.path_service import SalesTrainerPathService
from sales_trainer.services.question_bank import QuestionBankAdapter
from sales_trainer.services.quiz_service import QuizService, QuizServiceError
from sales_trainer.services.short_answer_scoring_service import (
    ShortAnswerScoreOutcome,
    ShortAnswerScoringService,
)
from sales_trainer.services.transcription_service import (
    TranscriptionResult,
    TranscriptionService,
)
from sales_trainer.services.unit_service import SalesTrainerUnitError, UnitService


class FakeTranscriptionService:
    async def transcribe_file(self, storage_key: str) -> TranscriptionResult:
        return TranscriptionResult(
            provider="fake-asr",
            transcript_text="我会先说明石犀的数据流动治理价值，再给出下一步安排。",
            raw_payload={"storage_key": storage_key},
        )


class FakeScoringService:
    async def score_audio(self, **kwargs) -> AudioScoreOutcome:
        assert kwargs["pass_threshold"] == 80
        return AudioScoreOutcome(
            prompt_hash="hash-audio-score",
            deucate_model="fake-deucate",
            total_score=88,
            passed=True,
            summary="讲解清楚。",
            strengths=["结构完整"],
            improvements=["补充案例"],
            dimension_scores={"content_accuracy": 88},
            raw_response={"total_score": 88},
            error_code=None,
            error_message=None,
            latency_ms=12,
        )


class PromptSnapshotScoringService:
    async def score_audio(self, **kwargs) -> AudioScoreOutcome:
        prompt = kwargs["prompt"]
        assert prompt.system_prompt == "你是销售训练评分员。"
        assert prompt.scoring_template == "请评分：{transcript}"
        assert prompt.version == 1
        assert kwargs["pass_threshold"] == 80
        return AudioScoreOutcome(
            prompt_hash="hash-snapshot-score",
            deucate_model="fake-deucate",
            total_score=86,
            passed=True,
            summary="使用提交时快照评分。",
            strengths=["快照稳定"],
            improvements=[],
            dimension_scores={"content_accuracy": 86},
            raw_response={"prompt_version": prompt.version},
            error_code=None,
            error_message=None,
            latency_ms=10,
        )


class RetryScoringService:
    def __init__(self) -> None:
        self.calls = 0

    async def score_audio(self, **kwargs) -> AudioScoreOutcome:
        self.calls += 1
        return AudioScoreOutcome(
            prompt_hash=f"retry-hash-{self.calls}",
            deucate_model="fake-deucate",
            total_score=90,
            passed=True,
            summary="重试评分成功。",
            strengths=[],
            improvements=[],
            dimension_scores={},
            raw_response={"total_score": 90},
            error_code=None,
            error_message=None,
            latency_ms=20,
        )


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


class FakeCosPutSigner:
    uploaded: list[dict[str, object]] = []

    def generate_put_url(self, object_key: str, content_type: str = "audio/webm"):
        return type(
            "Presigned",
            (),
            {
                "url": f"https://cos.example.com/{object_key}",
                "object_key": object_key,
                "expires_at": "2026-05-28T12:00:00+00:00",
            },
        )()

    def upload_object(
        self,
        object_key: str,
        body: bytes,
        *,
        content_type: str = "audio/webm",
    ) -> str:
        self.uploaded.append(
            {
                "object_key": object_key,
                "body": body,
                "content_type": content_type,
            }
        )
        return object_key

    def get_object_size(self, object_key: str) -> int:
        for item in reversed(self.uploaded):
            if item["object_key"] == object_key:
                return len(item["body"])  # type: ignore[arg-type]
        raise FileNotFoundError(object_key)


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
async def test_should_process_audio_submission_without_fixed_duration_limit(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="PPT 讲解评分",
        purpose="general_audio_scoring",
        system_prompt="你是销售训练评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 讲解录音",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": prompt.prompt_id,
                "pass_threshold": 80,
                "purpose": "general_audio_scoring",
            }
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, learner, prompt, unit])
    await test_db.commit()

    service = AudioSubmissionService(
        test_db,
        transcription_service=FakeTranscriptionService(),
        scoring_service=FakeScoringService(),
    )
    submission = await service.create_submission(
        AudioSubmissionCreate(
            unit_id=unit.unit_id,
            purpose="general_audio_scoring",
            original_filename="long-recording.wav",
            content_type="audio/wav",
            size_bytes=1024,
            storage_key="/tmp/long-recording.wav",
            duration_seconds=10800,
            source_page="sales_trainer_unit_detail",
            auto_process=True,
        ),
        actor=learner,
    )

    assert submission.status == "scored"
    assert float(submission.duration_seconds) == 10800

    serialized = await service.serialize_submission(submission)
    assert serialized["source_page"] == "sales_trainer_unit_detail"
    assert serialized["transcript"]["provider"] == "fake-asr"
    assert serialized["score_result"]["total_score"] == 88
    assert serialized["score_result"]["passed"] is True
    assert serialized["score_result"]["transcript_snapshot"] == (
        "我会先说明石犀的数据流动治理价值，再给出下一步安排。"
    )

    scores, score_total = await service.list_score_results(user_id=learner.user_id)
    assert score_total == 1
    assert scores[0].submission_id == submission.submission_id

    logs, _ = await OperationLogService(test_db).list_logs(
        target_type="sales_trainer_audio_submission",
        target_id=submission.submission_id,
    )
    assert {
        "audio_uploaded",
        "audio_transcription_succeeded",
        "audio_scoring_succeeded",
    }.issubset({log.action for log in logs})
    upload_log = next(log for log in logs if log.action == "audio_uploaded")
    assert upload_log.metadata_json["source_page"] == "sales_trainer_unit_detail"


@pytest.mark.asyncio
async def test_should_retry_scoring_failed_submission_when_transcript_exists(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="销售录音评分",
        purpose="general_audio_scoring",
        system_prompt="你是销售训练评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="销售录音",
        unit_type="audio_scoring",
        config={"audio": {"scoring_prompt_id": prompt.prompt_id, "pass_threshold": 80}},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    submission = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        purpose="general_audio_scoring",
        original_filename="pitch.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/pitch.wav",
        status="scoring_failed",
        error_code="[DEUCATE_TIMEOUT]",
        error_message="[DEUCATE_TIMEOUT]",
    )
    transcript = SalesTrainerAudioTranscript(
        submission_id=submission.submission_id,
        provider="fake-asr",
        transcript_text="这是可重试评分的转写文本。",
        raw_payload={},
    )
    failed_score = SalesTrainerAudioScoreResult(
        submission_id=submission.submission_id,
        prompt_id=prompt.prompt_id,
        prompt_version=1,
        prompt_hash="failed-hash",
        deucate_model="fake-deucate",
        transcript_snapshot=transcript.transcript_text,
        total_score=None,
        passed=None,
        summary=None,
        strengths=[],
        improvements=[],
        dimension_scores={},
        raw_response=None,
        error_code="[DEUCATE_TIMEOUT]",
        error_message="[DEUCATE_TIMEOUT]",
        latency_ms=30000,
    )
    test_db.add_all(
        [admin, learner, prompt, unit, submission, transcript, failed_score]
    )
    await test_db.commit()

    scoring = RetryScoringService()
    service = AudioSubmissionService(test_db, scoring_service=scoring)

    retried = await service.retry_scoring(submission.submission_id, actor=admin)

    assert scoring.calls == 1
    assert retried.status == "scored"
    assert retried.error_code is None
    scores, total = await service.list_score_results(
        submission_id=submission.submission_id
    )
    assert total == 2
    assert any(score.total_score == 90 for score in scores)


@pytest.mark.asyncio
async def test_should_reject_unsupported_audio_mime_type(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    service = AudioSubmissionService(test_db)

    with pytest.raises(AudioSubmissionServiceError) as exc:
        service.generate_upload_url(
            filename="not-audio.txt",
            content_type="text/plain",
            actor=test_user,
        )

    assert exc.value.code == "[AUDIO_TYPE_NOT_ALLOWED]"


@pytest.mark.asyncio
async def test_should_generate_cos_upload_url_when_configured(
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "cos")
    monkeypatch.setattr(
        "sales_trainer.services.audio_submission_service.get_cos_signing_service",
        lambda: FakeCosPutSigner(),
    )
    service = AudioSubmissionService(test_db)

    result = service.generate_upload_url(
        filename="recording.wav",
        content_type="audio/wav",
        actor=test_user,
    )

    assert result["storage_backend"] == "cos"
    assert result["storage_key"].startswith("cos://sales-trainer/audio/")
    assert result["upload_url"].startswith(
        "https://cos.example.com/sales-trainer/audio/"
    )


@pytest.mark.asyncio
async def test_should_store_multipart_upload_in_cos_when_backend_is_cos(
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeUploadFile:
        filename = "recording.wav"
        content_type = "audio/wav"

        async def read(self) -> bytes:
            return b"audio-bytes"

    signer = FakeCosPutSigner()
    signer.uploaded.clear()
    monkeypatch.setenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND", "cos")
    monkeypatch.setattr(
        "sales_trainer.services.audio_submission_service.get_cos_signing_service",
        lambda: signer,
    )

    service = AudioSubmissionService(
        test_db,
        transcription_service=FakeTranscriptionService(),
        scoring_service=FakeScoringService(),
    )
    submission = await service.save_uploaded_file(
        file=FakeUploadFile(),
        unit_id=None,
        purpose="general_audio_scoring",
        source_page="sales_trainer_audio_upload",
        confirmed_material_version_id=None,
        actor=test_user,
        auto_process=False,
    )

    assert submission.storage_key.startswith("cos://sales-trainer/audio/")
    assert signer.uploaded[0]["body"] == b"audio-bytes"
    assert signer.uploaded[0]["content_type"] == "audio/wav"


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
async def test_should_project_sales_trainer_path_with_unlock_progress(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    category = QuestionCategory(
        category_id="path-category",
        name="路径题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="path-question-1",
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
    first_content = LearningContent(
        learning_content_id=str(uuid.uuid4()),
        title="产品定位学习内容",
        summary="产品定位学习内容。",
        owner="新人销售闯关",
        source="unit_test",
        status="published",
        created_by=str(test_user.user_id),
        updated_by=str(test_user.user_id),
    )
    second_content = LearningContent(
        learning_content_id=str(uuid.uuid4()),
        title="价值表达学习内容",
        summary="价值表达学习内容。",
        owner="新人销售闯关",
        source="unit_test",
        status="published",
        created_by=str(test_user.user_id),
        updated_by=str(test_user.user_id),
    )
    first_unit = SalesTrainerUnit(
        unit_id="path-unit-1",
        name="第一关：产品定位",
        unit_type="quiz",
        config={
            "quiz": {"pass_threshold": 10},
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "path_title": "新人销售闯关",
                "goal_title": "掌握首次客户沟通",
                "level_title": "第一关：产品定位",
                "order_index": 1,
                "completion_rule": "passed",
            },
        },
        status="published",
        created_by=test_user.user_id,
        updated_by=test_user.user_id,
    )
    first_paper = SalesTrainerExamPaper(
        paper_id=str(uuid.uuid4()),
        paper_key="path-unit-1-paper",
        title="产品定位考卷",
        module_key="business_skills",
        unit_id=first_unit.unit_id,
        pass_threshold=10,
        status="published",
        created_by=test_user.user_id,
        updated_by=test_user.user_id,
    )
    second_unit = SalesTrainerUnit(
        unit_id="path-unit-2",
        name="第二关：价值表达",
        unit_type="quiz",
        config={
            "quiz": {"pass_threshold": 10},
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "path_title": "新人销售闯关",
                "goal_title": "掌握首次客户沟通",
                "level_title": "第二关：价值表达",
                "order_index": 2,
                "unlock_after_unit_ids": ["path-unit-1"],
                "completion_rule": "passed",
            },
        },
        status="published",
        created_by=test_user.user_id,
        updated_by=test_user.user_id,
    )
    second_paper = SalesTrainerExamPaper(
        paper_id=str(uuid.uuid4()),
        paper_key="path-unit-2-paper",
        title="价值表达考卷",
        module_key="elevator_pitch",
        unit_id=second_unit.unit_id,
        pass_threshold=10,
        status="published",
        created_by=test_user.user_id,
        updated_by=test_user.user_id,
    )
    test_db.add_all(
        [
            category,
            question,
            first_content,
            second_content,
            first_unit,
            second_unit,
            first_paper,
            second_paper,
        ]
    )
    await test_db.flush()
    await UnitService(test_db)._replace_questions(
        first_unit.unit_id,
        [
            UnitQuestionBinding(
                question_id=question.question_id, order_index=1, points=10
            )
        ],
    )
    await UnitService(test_db)._replace_questions(
        second_unit.unit_id,
        [
            UnitQuestionBinding(
                question_id=question.question_id, order_index=1, points=10
            )
        ],
    )
    await test_db.commit()

    path_config_service = SalesTrainerPathConfigService(test_db)
    await path_config_service.save_config(
        NewcomerPathConfigSaveRequest.model_validate(
            {
                "path_key": "newcomer_training_path_v1",
                "title": "新人销售闯关",
                "goal_title": "掌握首次客户沟通",
                "reason": "发布测试路径 active revision",
                "modules": [
                    {
                        "module_key": "business_skills",
                        "module_type": "article_exam",
                        "order_index": 1,
                        "title": "第一关：产品定位",
                        "target_unit_id": first_unit.unit_id,
                        "learning_content_id": first_content.learning_content_id,
                        "exam_paper_id": first_paper.paper_id,
                        "completion_rule": "passed",
                    },
                    {
                        "module_key": "elevator_pitch",
                        "module_type": "article_exam",
                        "order_index": 2,
                        "title": "第二关：价值表达",
                        "target_unit_id": second_unit.unit_id,
                        "learning_content_id": second_content.learning_content_id,
                        "exam_paper_id": second_paper.paper_id,
                        "unlock_after_unit_ids": [first_unit.unit_id],
                        "completion_rule": "passed",
                    },
                ],
            }
        ),
        actor=test_user,
    )
    await path_config_service.publish_config(
        actor=test_user,
        reason="测试路径 active revision 生效",
    )

    paths_before = await SalesTrainerPathService(test_db).list_paths_for_user(
        str(test_user.user_id)
    )

    assert paths_before[0]["current_level_id"] == "path-unit-1"
    assert paths_before[0]["levels"][1]["status"] == "locked"

    await QuizService(test_db).submit_attempt(
        QuizAttemptCreate(
            unit_id=first_unit.unit_id,
            answers=[
                QuizAnswerSubmit(
                    question_id=question.question_id,
                    answer_payload="A",
                )
            ],
        ),
        actor=test_user,
    )

    paths_after = await SalesTrainerPathService(test_db).list_paths_for_user(
        str(test_user.user_id)
    )

    assert paths_after[0]["completed_levels"] == 1
    assert paths_after[0]["current_level_id"] == "path-unit-2"
    assert paths_after[0]["levels"][0]["status"] == "completed"
    assert paths_after[0]["levels"][1]["status"] == "available"
    assert paths_after[0]["goal_context"]["score_basis"] == (
        "sales_trainer_path_projection_v1"
    )
    assert paths_after[0]["goal_context"]["evidence_items"][0]["evidence_type"] == (
        "quiz_attempt"
    )
    assert paths_after[0]["goal_context"]["weak_points"][0]["unit_id"] == "path-unit-2"
    assert paths_after[0]["goal_context"]["next_recommendation"] == {
        "title": "下一关：第二关：价值表达",
        "reason": "本关还没有训练证据。",
        "action_label": "开始做题",
        "target_path": "/sales-trainer/business-skills",
        "unit_id": "path-unit-2",
        "level_title": "第二关：价值表达",
        "recommendation_kind": "start_level",
    }


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
async def test_should_require_latest_material_confirmation_for_ppt_submission(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    material = SalesTrainerMaterial(
        material_id=str(uuid.uuid4()),
        material_key="company_master_deck",
        name="公司主胶片",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    version = SalesTrainerMaterialVersion(
        version_id=str(uuid.uuid4()),
        material_id=material.material_id,
        version_label="v2026.06",
        title="公司主胶片 2026-06",
        file_name="deck.pptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        file_size_bytes=100,
        storage_key="/tmp/deck.pptx",
        status="published",
        created_by=admin.user_id,
        published_by=admin.user_id,
    )
    material.current_version_id = version.version_id
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="PPT 讲解评分方案",
        purpose="ppt_pitch",
        system_prompt="你是销售训练评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        learner_rubric={
            "visible_to_learner": True,
            "criteria": [{"key": "structure", "label": "结构", "weight": 40}],
            "common_mistakes": ["没有讲清业务价值"],
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 演练",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": prompt.prompt_id,
                "pass_threshold": 80,
                "purpose": "ppt_pitch",
            },
            "task_brief": {
                "title": "PPT 演练",
                "purpose": "练习公司主胶片讲解。",
                "instructions": ["下载最新版 PPT", "按主线录音"],
            },
            "materials": {
                "bindings": [
                    {
                        "material_id": material.material_id,
                        "required": True,
                        "confirmation_required": True,
                        "version_policy": "current_published",
                        "display_order": 1,
                    }
                ]
            },
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, learner, material, version, prompt, unit])
    await test_db.commit()

    service = AudioSubmissionService(
        test_db,
        transcription_service=FakeTranscriptionService(),
        scoring_service=FakeScoringService(),
    )
    with pytest.raises(AudioSubmissionServiceError) as missing_confirmation:
        await service.create_submission(
            AudioSubmissionCreate(
                unit_id=unit.unit_id,
                purpose="ppt_pitch",
                original_filename="ppt-recording.wav",
                content_type="audio/wav",
                size_bytes=1024,
                storage_key="/tmp/ppt-recording.wav",
                auto_process=False,
            ),
            actor=learner,
        )
    assert missing_confirmation.value.code == "[MATERIAL_VERSION_CONFIRMATION_REQUIRED]"

    submission = await service.create_submission(
        AudioSubmissionCreate(
            unit_id=unit.unit_id,
            purpose="ppt_pitch",
            original_filename="ppt-recording.wav",
            content_type="audio/wav",
            size_bytes=1024,
            storage_key="/tmp/ppt-recording.wav",
            confirmed_material_version_id=version.version_id,
            auto_process=True,
        ),
        actor=learner,
    )

    assert submission.status == "scored"
    assert submission.confirmed_material_version_id == version.version_id
    assert (
        submission.material_snapshot["items"][0]["current_version"]["version_label"]
        == "v2026.06"
    )
    assert submission.task_brief_snapshot["title"] == "PPT 演练"
    assert (
        submission.score_scheme_snapshot["learner_rubric"]["criteria"][0]["label"]
        == "结构"
    )
    assert (
        submission.score_scheme_snapshot["prompt_snapshot"]["system_prompt"]
        == "你是销售训练评分员。"
    )
    assert (
        submission.score_scheme_snapshot["prompt_snapshot"]["scoring_template"]
        == "请评分：{transcript}"
    )


@pytest.mark.asyncio
async def test_should_score_audio_with_submission_prompt_snapshot(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    prompt = SalesTrainerAudioScorePrompt(
        prompt_id=str(uuid.uuid4()),
        name="PPT 讲解评分方案",
        purpose="ppt_pitch",
        system_prompt="你是销售训练评分员。",
        scoring_template="请评分：{transcript}",
        output_schema={},
        learner_rubric={
            "visible_to_learner": True,
            "criteria": [{"key": "structure", "label": "结构", "weight": 40}],
        },
        version=1,
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    unit = SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name="PPT 演练",
        unit_type="audio_scoring",
        config={
            "audio": {
                "scoring_prompt_id": prompt.prompt_id,
                "pass_threshold": 80,
                "purpose": "general_audio_scoring",
            }
        },
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    test_db.add_all([admin, learner, prompt, unit])
    await test_db.commit()

    service = AudioSubmissionService(
        test_db,
        transcription_service=FakeTranscriptionService(),
        scoring_service=PromptSnapshotScoringService(),
    )
    submission = await service.create_submission(
        AudioSubmissionCreate(
            unit_id=unit.unit_id,
            purpose="general_audio_scoring",
            original_filename="ppt-recording.wav",
            content_type="audio/wav",
            size_bytes=1024,
            storage_key="/tmp/ppt-recording.wav",
            auto_process=False,
        ),
        actor=learner,
    )

    prompt.system_prompt = "新版评分员指令。"
    prompt.scoring_template = "新版模板：{transcript}"
    prompt.version = 99
    await test_db.commit()

    scored = await service.process_submission(submission.submission_id, actor=learner)
    scores, total = await service.list_score_results(
        submission_id=submission.submission_id
    )

    assert scored.status == "scored"
    assert total == 1
    assert scores[0].prompt_version == 1
    assert scores[0].prompt_hash == "hash-snapshot-score"
