"""Frozen quiz attempts, deterministic objective grading, and async short answers."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Never

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform import (
    AIInvocationPort,
    AIInvocationResult,
    AIInvocationStatus,
    BudgetScope,
    DataClassification,
    GovernedAIRequest,
)
from learning.contracts import QuizRevisionDraft
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningQuestionRevision,
    LearningQuizAttempt,
    LearningQuizCommand,
    LearningQuizRevision,
)
from learning.ports import ActivityOutcomePayload, ActivityOutcomeWriterPort
from task_runtime import TaskCommand, TaskRuntimePort


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class QuizAttemptContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    learner_id: str = Field(min_length=1, max_length=120)
    enrollment_id: str = Field(min_length=1, max_length=160)
    path_revision_id: str = Field(min_length=1, max_length=160)
    activity_id: str = Field(min_length=1, max_length=160)
    attempt_id: str = Field(min_length=1, max_length=160)
    quiz_revision_id: str = Field(min_length=1, max_length=160)
    trace_id: str | None = Field(default=None, max_length=160)


class QuizAnswerInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_revision_id: str = Field(min_length=1, max_length=160)
    selected_option_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    text_answer: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def require_one_answer_shape(self) -> QuizAnswerInput:
        has_options = bool(self.selected_option_ids)
        has_text = bool(self.text_answer and self.text_answer.strip())
        if has_options == has_text:
            raise ValueError("provide selected options or a text answer")
        if len(self.selected_option_ids) != len(set(self.selected_option_ids)):
            raise ValueError("selected_option_ids must be unique")
        return self


class QuizAttemptSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detail_id: str
    attempt_id: str
    organization_id: str
    learner_id: str
    activity_id: str
    quiz_revision_id: str
    status: str
    version: int
    questions: tuple[dict[str, Any], ...]
    rule_snapshot: dict[str, Any]
    answers: tuple[dict[str, Any], ...]
    score: float | None
    max_score: float
    passed: bool | None
    task_id: str | None
    started_at: datetime
    last_saved_at: datetime
    submitted_at: datetime | None
    completed_at: datetime | None


class ShortAnswerRubricEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    criterion: str = Field(min_length=1, max_length=240)
    met: bool
    reason: str = Field(min_length=1, max_length=2_000)


class ShortAnswerGrade(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_revision_id: str
    awarded_points: float = Field(ge=0)
    max_points: float = Field(gt=0)
    rubric_evidence: tuple[ShortAnswerRubricEvidence, ...] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def points_within_max(self) -> ShortAnswerGrade:
        if self.awarded_points > self.max_points:
            raise ValueError("awarded_points cannot exceed max_points")
        return self


class ShortAnswerScoringOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    answers: tuple[ShortAnswerGrade, ...] = Field(min_length=1, max_length=200)


class ShortAnswerScoringPlan(BaseModel):
    """Frozen scoring request committed before the Provider is invoked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    detail_id: str
    task_id: str
    request: GovernedAIRequest


class QuizRuntimeService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        task_runtime: TaskRuntimePort | None = None,
        outcomes: ActivityOutcomeWriterPort | None = None,
    ) -> None:
        self._session = session
        self._task_runtime = task_runtime
        self._outcomes = outcomes

    async def start_or_resume(
        self, *, context: QuizAttemptContext, idempotency_key: str
    ) -> QuizAttemptSummary:
        fingerprint = _canonical_hash(context.model_dump(mode="json"))
        existing = await self._session.scalar(
            select(LearningQuizAttempt)
            .where(LearningQuizAttempt.attempt_id == context.attempt_id)
            .limit(1)
        )
        if existing is not None:
            if (
                existing.organization_id != context.organization_id
                or existing.learner_id != context.learner_id
            ):
                self._not_found()
            if (
                existing.start_idempotency_key_hash != _secret_hash(idempotency_key)
                or existing.start_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return self._summary(existing)
        revision = await self._session.get(
            LearningQuizRevision, context.quiz_revision_id
        )
        if (
            revision is None
            or revision.organization_id != context.organization_id
            or revision.status not in {"published", "archived"}
        ):
            raise LearningGovernanceError(
                "[QUIZ_REVISION_NOT_FOUND]", "测验修订不存在或不可访问。", 404
            )
        draft = QuizRevisionDraft.model_validate(revision.snapshot_json)
        rows = (
            await self._session.execute(
                select(LearningQuestionRevision)
                .where(
                    LearningQuestionRevision.organization_id
                    == context.organization_id
                )
                .where(
                    LearningQuestionRevision.revision_id.in_(
                        revision.question_revision_ids_json
                    )
                )
            )
        ).scalars().all()
        by_id = {row.revision_id: row for row in rows}
        if set(by_id) != set(revision.question_revision_ids_json):
            raise LearningGovernanceError(
                "[QUIZ_QUESTION_SNAPSHOT_UNAVAILABLE]",
                "测验题目修订不完整，请联系培训负责人。",
                409,
            )
        question_snapshot: list[dict[str, Any]] = []
        for binding in draft.questions:
            question = by_id[binding.question_revision_id]
            content = dict(question.content_json)
            question_snapshot.append(
                {
                    **content,
                    "question_revision_id": question.revision_id,
                    "question_content_hash": question.content_hash,
                    "points": binding.points,
                }
            )
        full_rules = draft.model_dump(mode="json")
        frozen = {"questions": question_snapshot, "rules": full_rules}
        now = _now()
        row = LearningQuizAttempt(
            detail_id=_id(),
            organization_id=context.organization_id,
            learner_id=context.learner_id,
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity_id,
            attempt_id=context.attempt_id,
            quiz_revision_id=context.quiz_revision_id,
            status="in_progress",
            version=1,
            question_snapshot_json=question_snapshot,
            rule_snapshot_json=full_rules,
            snapshot_hash=_canonical_hash(frozen),
            answers_json=[],
            objective_score=0,
            max_score=sum(float(item.points) for item in draft.questions),
            start_idempotency_key_hash=_secret_hash(idempotency_key),
            start_fingerprint=fingerprint,
            started_at=now,
            last_saved_at=now,
        )
        self._session.add(row)
        await self._session.flush([row])
        return self._summary(row)

    async def save_answers(
        self,
        *,
        organization_id: str,
        learner_id: str,
        detail_id: str,
        answers: tuple[QuizAnswerInput, ...],
        expected_version: int,
        idempotency_key: str,
    ) -> QuizAttemptSummary:
        request = {
            "answers": [answer.model_dump(mode="json") for answer in answers],
            "expected_version": expected_version,
        }
        row = await self._load_for_update(
            organization_id=organization_id,
            learner_id=learner_id,
            detail_id=detail_id,
        )
        replay = await self._command_replay(
            organization_id=organization_id,
            detail_id=detail_id,
            command_type="save_answers",
            idempotency_key=idempotency_key,
            request=request,
        )
        if replay is not None:
            return replay
        self._require_version(row.version, expected_version)
        if row.status != "in_progress":
            raise LearningGovernanceError(
                "[QUIZ_ATTEMPT_STATE_CONFLICT]", "当前测验不能继续保存答案。", 409
            )
        self._validate_answers(row, answers, require_all=False)
        row.answers_json = [answer.model_dump(mode="json") for answer in answers]
        row.version += 1
        row.last_saved_at = _now()
        await self._session.flush([row])
        await self._record_command(
            row=row,
            command_type="save_answers",
            idempotency_key=idempotency_key,
            request=request,
        )
        return self._summary(row)

    async def submit(
        self,
        *,
        organization_id: str,
        learner_id: str,
        detail_id: str,
        expected_version: int,
        idempotency_key: str,
    ) -> QuizAttemptSummary:
        request = {"expected_version": expected_version}
        row = await self._load_for_update(
            organization_id=organization_id,
            learner_id=learner_id,
            detail_id=detail_id,
        )
        replay = await self._command_replay(
            organization_id=organization_id,
            detail_id=detail_id,
            command_type="submit",
            idempotency_key=idempotency_key,
            request=request,
        )
        if replay is not None:
            return replay
        self._require_version(row.version, expected_version)
        if row.status != "in_progress":
            raise LearningGovernanceError(
                "[QUIZ_ATTEMPT_STATE_CONFLICT]", "当前测验不能重复提交。", 409
            )
        answers = tuple(
            QuizAnswerInput.model_validate(item) for item in row.answers_json
        )
        self._validate_answers(row, answers, require_all=True)
        objective_score, has_short_answer = self._grade_objective(row, answers)
        row.objective_score = objective_score
        row.submitted_at = _now()
        row.last_saved_at = row.submitted_at
        if has_short_answer:
            if self._task_runtime is None:
                raise LearningGovernanceError(
                    "[LEARNING_TASK_RUNTIME_UNAVAILABLE]",
                    "简答题评分任务暂不可用，答案已保留，请稍后重试。",
                    503,
                )
            row.status = "scoring_pending"
            row.version += 1
            await self._session.flush([row])
            task = await self._task_runtime.enqueue(
                TaskCommand(
                    task_type="learning.quiz.short_answer_score",
                    schema_version=1,
                    organization_id=row.organization_id,
                    actor_id=row.learner_id,
                    resource_type="quiz_attempt",
                    resource_id=row.detail_id,
                    idempotency_key=idempotency_key,
                    input_payload={"detail_id": row.detail_id},
                    correlation_id=row.attempt_id,
                    causation_id=row.quiz_revision_id,
                    trace_id=None,
                    data_classification="internal",
                )
            )
            row.task_id = task.task_id
        else:
            if self._outcomes is None:
                raise LearningGovernanceError(
                    "[ACTIVITY_OUTCOME_WRITER_UNAVAILABLE]",
                    "测验结果暂时无法保存，答案已保留，请稍后重试。",
                    503,
                )
            row.status = "scored"
            row.score = objective_score
            threshold = float(row.rule_snapshot_json["pass_threshold"])
            row.passed = (
                float(objective_score) * 100 / float(row.max_score) >= threshold
            )
            row.version += 1
            row.completed_at = _now()
            await self._record_objective_outcome(row)
        await self._session.flush([row])
        await self._record_command(
            row=row,
            command_type="submit",
            idempotency_key=idempotency_key,
            request=request,
        )
        return self._summary(row)

    async def _record_objective_outcome(self, row: LearningQuizAttempt) -> None:
        assert self._outcomes is not None
        source_anchor_ids = tuple(
            dict.fromkeys(
                str(anchor_id)
                for question in row.question_snapshot_json
                for anchor_id in question.get("source_anchor_ids", [])
            )
        )
        competency_keys = tuple(
            dict.fromkeys(
                str(key)
                for question in row.question_snapshot_json
                for key in question.get("competency_keys", [])
            )
        )
        await self._outcomes.record(
            ActivityOutcomePayload(
                organization_id=row.organization_id,
                actor_id=row.learner_id,
                attempt_id=row.attempt_id,
                lifecycle_result="completed",
                assessment_result="passed" if row.passed else "not_passed",
                result_type="quiz_attempt",
                result_id=row.detail_id,
                score=float(row.score) if row.score is not None else None,
                max_score=float(row.max_score),
                passed=row.passed,
                source_refs=tuple(
                    {
                        "resource_type": "source_anchor",
                        "resource_id": anchor_id,
                    }
                    for anchor_id in source_anchor_ids
                ),
                lineage={
                    "quiz_revision_id": row.quiz_revision_id,
                    "question_revision_ids": [
                        item["question_revision_id"]
                        for item in row.question_snapshot_json
                    ],
                    "scoring_method": "deterministic",
                    "competency_keys": list(competency_keys),
                },
                confidence=1.0,
                next_action=(
                    None
                    if row.passed
                    else {
                        "type": "remediation",
                        "competency_keys": list(competency_keys),
                    }
                ),
                idempotency_key=f"quiz-score:{row.detail_id}",
                trace_id=None,
            )
        )

    @staticmethod
    def _grade_objective(
        row: LearningQuizAttempt, answers: tuple[QuizAnswerInput, ...]
    ) -> tuple[float, bool]:
        by_answer = {item.question_revision_id: item for item in answers}
        score = 0.0
        has_short_answer = False
        for question in row.question_snapshot_json:
            answer = by_answer[str(question["question_revision_id"])]
            if question["question_type"] == "short_answer":
                has_short_answer = True
                continue
            correct = {
                str(option["option_id"])
                for option in question.get("options", [])
                if option.get("is_correct") is True
            }
            if set(answer.selected_option_ids) == correct:
                score += float(question["points"])
        return score, has_short_answer

    @staticmethod
    def _validate_answers(
        row: LearningQuizAttempt,
        answers: tuple[QuizAnswerInput, ...],
        *,
        require_all: bool,
    ) -> None:
        expected = {
            str(item["question_revision_id"]): str(item["question_type"])
            for item in row.question_snapshot_json
        }
        by_id = {item.question_revision_id: item for item in answers}
        if len(by_id) != len(answers) or not set(by_id).issubset(expected):
            raise LearningGovernanceError(
                "[QUIZ_ANSWER_INVALID]", "答案包含重复或不属于当前快照的题目。", 422
            )
        if require_all and set(by_id) != set(expected):
            raise LearningGovernanceError(
                "[QUIZ_ANSWERS_INCOMPLETE]", "请完成全部题目后再提交。", 409
            )
        for revision_id, answer in by_id.items():
            is_short = expected[revision_id] == "short_answer"
            if is_short != bool(answer.text_answer and answer.text_answer.strip()):
                raise LearningGovernanceError(
                    "[QUIZ_ANSWER_TYPE_MISMATCH]", "答案形式与题型不匹配。", 422
                )

    async def _command_replay(
        self,
        *,
        organization_id: str,
        detail_id: str,
        command_type: str,
        idempotency_key: str,
        request: dict[str, Any],
    ) -> QuizAttemptSummary | None:
        command = await self._session.scalar(
            select(LearningQuizCommand)
            .where(LearningQuizCommand.detail_id == detail_id)
            .where(LearningQuizCommand.command_type == command_type)
            .where(
                LearningQuizCommand.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if command is None:
            return None
        if command.organization_id != organization_id:
            self._not_found()
        if command.request_fingerprint != _canonical_hash(request):
            self._idempotency_conflict()
        replay: QuizAttemptSummary = QuizAttemptSummary.model_validate(
            command.result_snapshot_json
        )
        return replay

    async def _record_command(
        self,
        *,
        row: LearningQuizAttempt,
        command_type: str,
        idempotency_key: str,
        request: dict[str, Any],
    ) -> None:
        self._session.add(
            LearningQuizCommand(
                command_id=_id(),
                detail_id=row.detail_id,
                organization_id=row.organization_id,
                command_type=command_type,
                idempotency_key_hash=_secret_hash(idempotency_key),
                request_fingerprint=_canonical_hash(request),
                result_version=row.version,
                result_snapshot_json=self._summary(row).model_dump(mode="json"),
                created_at=_now(),
            )
        )
        await self._session.flush()

    async def _load_for_update(
        self,
        *,
        organization_id: str,
        learner_id: str,
        detail_id: str,
    ) -> LearningQuizAttempt:
        row = await self._session.scalar(
            select(LearningQuizAttempt)
            .where(LearningQuizAttempt.detail_id == detail_id)
            .with_for_update()
            .limit(1)
        )
        if (
            row is None
            or row.organization_id != organization_id
            or row.learner_id != learner_id
        ):
            self._not_found()
        return row

    @staticmethod
    def _summary(row: LearningQuizAttempt) -> QuizAttemptSummary:
        public_questions: list[dict[str, Any]] = []
        for question in row.question_snapshot_json:
            public_questions.append(
                {
                    "question_revision_id": question["question_revision_id"],
                    "question_type": question["question_type"],
                    "stem": question["stem"],
                    "options": [
                        {
                            "option_id": option["option_id"],
                            "text": option["text"],
                        }
                        for option in question.get("options", [])
                    ],
                    "points": question["points"],
                }
            )
        rules = {
            key: row.rule_snapshot_json[key]
            for key in (
                "pass_threshold",
                "max_attempts",
                "retry_interval_seconds",
                "feedback_policy",
                "time_limit_minutes",
                "shuffle_questions",
                "shuffle_options",
            )
        }
        return QuizAttemptSummary(
            detail_id=row.detail_id,
            attempt_id=row.attempt_id,
            organization_id=row.organization_id,
            learner_id=row.learner_id,
            activity_id=row.activity_id,
            quiz_revision_id=row.quiz_revision_id,
            status=row.status,
            version=row.version,
            questions=tuple(public_questions),
            rule_snapshot=rules,
            answers=tuple(dict(item) for item in row.answers_json),
            score=float(row.score) if row.score is not None else None,
            max_score=float(row.max_score),
            passed=row.passed,
            task_id=row.task_id,
            started_at=row.started_at,
            last_saved_at=row.last_saved_at,
            submitted_at=row.submitted_at,
            completed_at=row.completed_at,
        )

    @staticmethod
    def _require_version(actual: int, expected: int) -> None:
        if actual != expected:
            raise LearningGovernanceError(
                "[LEARNING_VERSION_CONFLICT]", "测验尝试已更新，请刷新后重试。", 412,
                details={"expected_version": expected, "actual_version": actual},
            )

    @staticmethod
    def _not_found() -> Never:
        raise LearningGovernanceError(
            "[QUIZ_ATTEMPT_NOT_FOUND]", "测验尝试不存在或不可访问。", 404
        )

    @staticmethod
    def _idempotency_conflict() -> Never:
        raise LearningGovernanceError(
            "[LEARNING_IDEMPOTENCY_CONFLICT]", "相同幂等键对应了不同测验命令。", 409
        )


class ShortAnswerScoringProcessor:
    def __init__(
        self,
        session: AsyncSession,
        *,
        ai: AIInvocationPort,
        outcomes: ActivityOutcomeWriterPort,
    ) -> None:
        self._session = session
        self._ai = ai
        self._outcomes = outcomes

    async def process_attempt(
        self, *, detail_id: str, task_id: str | None
    ) -> QuizAttemptSummary:
        prepared = await self.prepare_attempt(detail_id=detail_id, task_id=task_id)
        if isinstance(prepared, QuizAttemptSummary):
            return prepared
        result = await self._ai.invoke(prepared.request)
        return await self.apply_result(plan=prepared, result=result)

    async def prepare_attempt(
        self, *, detail_id: str, task_id: str | None
    ) -> ShortAnswerScoringPlan | QuizAttemptSummary:
        if task_id is None:
            raise LearningGovernanceError(
                "[QUIZ_SHORT_ANSWER_TASK_MISSING]", "简答题评分任务缺失。", 409
            )
        row = await self._session.scalar(
            select(LearningQuizAttempt)
            .where(LearningQuizAttempt.detail_id == detail_id)
            .with_for_update()
            .limit(1)
        )
        if row is None:
            raise LearningGovernanceError(
                "[QUIZ_ATTEMPT_NOT_FOUND]", "测验尝试不存在。", 404
            )
        if row.task_id != task_id:
            raise LearningGovernanceError(
                "[QUIZ_SHORT_ANSWER_TASK_MISMATCH]", "评分任务与测验尝试不匹配。", 409
            )
        if row.status == "scored":
            return QuizRuntimeService._summary(row)
        if row.status not in {"scoring_pending", "needs_review"}:
            raise LearningGovernanceError(
                "[QUIZ_ATTEMPT_STATE_CONFLICT]", "当前测验尝试不能执行简答题评分。", 409
            )
        policy = row.rule_snapshot_json.get("short_answer_scoring")
        if not isinstance(policy, dict):
            raise LearningGovernanceError(
                "[QUIZ_SHORT_ANSWER_POLICY_MISSING]", "简答题评分合同缺失。", 409
            )
        answers = {
            str(item["question_revision_id"]): item for item in row.answers_json
        }
        short_questions = [
            item
            for item in row.question_snapshot_json
            if item["question_type"] == "short_answer"
        ]
        scoring_answers = [
            {
                "question_revision_id": item["question_revision_id"],
                "stem": item["stem"],
                "reference_answer": item["reference_answer"],
                "rubric": item["rubric"],
                "max_points": item["points"],
                "learner_answer": answers[
                    str(item["question_revision_id"])
                ]["text_answer"],
            }
            for item in short_questions
        ]
        return ShortAnswerScoringPlan(
            detail_id=row.detail_id,
            task_id=task_id,
            request=GovernedAIRequest(
                business_purpose="newcomer_quiz_short_answer_scoring",
                task_id=task_id,
                organization_id=row.organization_id,
                actor_id=row.learner_id,
                object_type="quiz_attempt",
                object_id=row.detail_id,
                prompt_template_id=str(policy["prompt_template_id"]),
                prompt_revision_id=str(policy["prompt_revision_id"]),
                prompt_contract_hash=str(policy["prompt_contract_hash"]),
                model_routing_profile_id=str(policy["model_routing_profile_id"]),
                model_routing_revision_id=str(policy["model_routing_revision_id"]),
                input_schema_version=str(policy["input_schema_version"]),
                output_schema_version=str(policy["output_schema_version"]),
                input_payload={
                    "quiz_revision_id": row.quiz_revision_id,
                    "answers": scoring_answers,
                },
                prompt_variables={
                    "quiz_revision_id": row.quiz_revision_id,
                    "answer_count": len(short_questions),
                    "answers_json": json.dumps(
                        scoring_answers,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
                idempotency_key=f"quiz-short-answer:{row.detail_id}",
                data_classification=DataClassification.CONFIDENTIAL,
                trace_id=task_id,
                correlation_id=row.attempt_id,
                causation_id=row.quiz_revision_id,
                runtime_consumer="learning.quiz.short_answer.v1",
                timeout_policy_ref="quiz-short-answer-default",
                retry_policy_ref="quiz-short-answer-default",
                budget_scope=BudgetScope.ORGANIZATION,
                formal_scoring=True,
                allow_fallback=True,
            ),
        )

    async def apply_result(
        self,
        *,
        plan: ShortAnswerScoringPlan,
        result: AIInvocationResult,
    ) -> QuizAttemptSummary:
        row = await self._session.scalar(
            select(LearningQuizAttempt)
            .where(LearningQuizAttempt.detail_id == plan.detail_id)
            .with_for_update()
            .execution_options(populate_existing=True)
            .limit(1)
        )
        if row is None:
            raise LearningGovernanceError(
                "[QUIZ_ATTEMPT_NOT_FOUND]", "测验尝试不存在。", 404
            )
        if row.task_id != plan.task_id:
            raise LearningGovernanceError(
                "[QUIZ_SHORT_ANSWER_TASK_MISMATCH]", "评分任务与测验尝试不匹配。", 409
            )
        if row.status == "scored":
            return QuizRuntimeService._summary(row)
        if row.status not in {"scoring_pending", "needs_review"}:
            raise LearningGovernanceError(
                "[QUIZ_ATTEMPT_STATE_CONFLICT]", "当前测验尝试不能保存简答题评分。", 409
            )
        short_questions = [
            item
            for item in row.question_snapshot_json
            if item["question_type"] == "short_answer"
        ]
        if result.status not in {
            AIInvocationStatus.SUCCEEDED,
            AIInvocationStatus.PARTIAL,
        } or result.validated_output is None:
            row.status = "needs_review"
            row.scoring_error_code = (
                result.failure.code if result.failure is not None else "ai_scoring_failed"
            )
            row.scoring_invocation_id = result.invocation_id
            row.version += 1
            await self._session.flush([row])
            raise LearningGovernanceError(
                "[QUIZ_SHORT_ANSWER_SCORING_FAILED]",
                "简答题评分暂未完成，答案和尝试已保留，可稍后重试或人工处理。",
                503,
                details={"retryable": bool(result.failure and result.failure.retryable)},
            )
        output = ShortAnswerScoringOutput.model_validate(result.validated_output)
        expected = {
            str(item["question_revision_id"]): float(item["points"])
            for item in short_questions
        }
        by_id = {item.question_revision_id: item for item in output.answers}
        if set(by_id) != set(expected) or any(
            abs(by_id[key].max_points - expected[key]) > 0.0001 for key in expected
        ):
            row.status = "needs_review"
            row.scoring_error_code = "scoring_contract_mismatch"
            row.scoring_invocation_id = result.invocation_id
            row.version += 1
            await self._session.flush([row])
            raise LearningGovernanceError(
                "[QUIZ_SHORT_ANSWER_SCHEMA_INVALID]", "简答题评分结果与冻结试卷不匹配。", 503
            )
        evidence = [item.model_dump(mode="json") for item in output.answers]
        score = float(row.objective_score) + sum(
            item.awarded_points for item in output.answers
        )
        threshold = float(row.rule_snapshot_json["pass_threshold"])
        passed = score * 100 / float(row.max_score) >= threshold
        row.status = "scored"
        row.score = score
        row.passed = passed
        row.scoring_evidence_json = evidence
        row.scoring_error_code = None
        row.scoring_invocation_id = result.invocation_id
        row.version += 1
        row.completed_at = _now()
        await self._session.flush([row])
        source_anchor_ids = tuple(
            dict.fromkeys(
                str(anchor_id)
                for question in row.question_snapshot_json
                for anchor_id in question.get("source_anchor_ids", [])
            )
        )
        competency_keys = tuple(
            dict.fromkeys(
                str(key)
                for question in row.question_snapshot_json
                for key in question.get("competency_keys", [])
            )
        )
        confidence = sum(item.confidence for item in output.answers) / len(
            output.answers
        )
        await self._outcomes.record(
            ActivityOutcomePayload(
                organization_id=row.organization_id,
                actor_id=row.learner_id,
                attempt_id=row.attempt_id,
                lifecycle_result="completed",
                assessment_result="passed" if passed else "not_passed",
                result_type="quiz_attempt",
                result_id=row.detail_id,
                score=score,
                max_score=float(row.max_score),
                passed=passed,
                source_refs=tuple(
                    {
                        "resource_type": "source_anchor",
                        "resource_id": anchor_id,
                    }
                    for anchor_id in source_anchor_ids
                ),
                lineage={
                    "quiz_revision_id": row.quiz_revision_id,
                    "question_revision_ids": [
                        item["question_revision_id"]
                        for item in row.question_snapshot_json
                    ],
                    "ai_invocation_id": result.invocation_id,
                    "competency_keys": list(competency_keys),
                },
                confidence=confidence,
                next_action=(
                    None
                    if passed
                    else {
                        "type": "remediation",
                        "competency_keys": list(competency_keys),
                    }
                ),
                idempotency_key=f"quiz-score:{row.detail_id}",
                trace_id=plan.task_id,
            )
        )
        return QuizRuntimeService._summary(row)


__all__ = [
    "QuizAnswerInput",
    "QuizAttemptContext",
    "QuizAttemptSummary",
    "QuizRuntimeService",
    "ShortAnswerScoringProcessor",
]
