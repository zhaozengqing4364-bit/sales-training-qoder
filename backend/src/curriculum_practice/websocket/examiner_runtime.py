from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import time
from typing import Any, Protocol

from common.monitoring.logger import get_logger
from common.websocket.base_handler import BaseWebSocketHandler
from common.websocket.session_state_service import SessionStateSnapshot

logger = get_logger(__name__)


class ExamScorer(Protocol):
    async def __call__(
        self,
        *,
        question: FrozenExamQuestion,
        answer_text: str,
    ) -> dict[str, object]: ...


class ExamCompletionWriter(Protocol):
    async def __call__(
        self,
        *,
        session_id: str,
        answers: list[dict[str, Any]],
        reason: str,
    ) -> str: ...


async def _default_scorer(
    *,
    question: FrozenExamQuestion,
    answer_text: str,
) -> dict[str, object]:
    reference_answer = (question.reference_answer or "").strip()
    answer = answer_text.strip()
    if not answer:
        return {"score": 0, "feedback": "未作答，无法评分", "reason": "EMPTY_ANSWER"}
    if not reference_answer:
        return {"score": 60, "feedback": "已提交答案，题目未配置参考答案，按基础完成度给分"}

    reference_terms = [term for term in reference_answer.replace("，", " ").replace("。", " ").split() if term]
    if not reference_terms:
        return {"score": 60, "feedback": "已提交答案，参考答案过短，按基础完成度给分"}

    matched_terms = [term for term in reference_terms if term in answer]
    coverage = len(matched_terms) / len(reference_terms)
    length_bonus = 0.15 if len(answer) >= min(len(reference_answer), 80) else 0
    score = min(100, round((coverage + length_bonus) * 100))
    if score >= 80:
        feedback = "答案覆盖了多数参考要点。"
    elif score >= 50:
        feedback = "答案覆盖了部分参考要点，还需要补充关键细节。"
    else:
        feedback = "答案与参考要点匹配较少，请围绕题干重新组织回答。"
    return {"score": score, "feedback": feedback, "matched_terms": matched_terms}


@dataclass(frozen=True)
class FrozenExamQuestion:
    question_id: str
    title: str
    stem: str
    reference_answer: str | None
    scoring_criteria: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FrozenExamQuestion:
        return cls(
            question_id=str(data["question_id"]),
            title=str(data["title"]),
            stem=str(data["stem"]),
            reference_answer=data.get("reference_answer"),
            scoring_criteria=dict(data.get("scoring_criteria") or {}),
        )


@dataclass(frozen=True)
class ExaminerSessionState:
    session_id: str
    examiner_agent_id: str
    timeout_seconds: int
    started_at: float
    current_question_index: int
    questions: list[FrozenExamQuestion]
    answers: list[dict[str, Any]] = field(default_factory=list)
    status: str = "in_progress"
    completed_reason: str | None = None
    remaining_seconds: int = 0
    report_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "examiner_agent_id": self.examiner_agent_id,
            "timeout_seconds": self.timeout_seconds,
            "started_at": self.started_at,
            "current_question_index": self.current_question_index,
            "questions": [question.to_dict() for question in self.questions],
            "answers": list(self.answers),
            "status": self.status,
            "completed_reason": self.completed_reason,
            "remaining_seconds": self.remaining_seconds,
            "report_path": self.report_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExaminerSessionState:
        questions = [
            FrozenExamQuestion.from_dict(question)
            for question in data.get("questions", [])
            if isinstance(question, dict)
        ]
        answers = [
            dict(answer) for answer in data.get("answers", []) if isinstance(answer, dict)
        ]
        return cls(
            session_id=str(data["session_id"]),
            examiner_agent_id=str(data["examiner_agent_id"]),
            timeout_seconds=int(data.get("timeout_seconds") or 0),
            started_at=float(data.get("started_at") or 0),
            current_question_index=int(data.get("current_question_index") or 0),
            questions=questions,
            answers=answers,
            status=str(data.get("status") or "in_progress"),
            completed_reason=data.get("completed_reason"),
            remaining_seconds=int(data.get("remaining_seconds") or 0),
            report_path=data.get("report_path") if data.get("report_path") else None,
        )


class ExaminerRuntime:
    def __init__(
        self,
        *,
        session_id: str,
        examiner_agent_id: str,
        timeout_seconds: int,
        questions: list[FrozenExamQuestion],
        scorer: ExamScorer | None = None,
        completion_writer: ExamCompletionWriter | None = None,
        started_at: float | None = None,
    ) -> None:
        self._session_id = session_id
        self._examiner_agent_id = examiner_agent_id
        self._timeout_seconds = timeout_seconds
        self._questions = questions
        self._scorer = scorer or _default_scorer
        self._completion_writer = completion_writer
        self._started_at = started_at if started_at is not None else time()
        self._current_question_index = 0
        self._answered_count = 0
        self._answers: list[dict[str, Any]] = []
        self._completed = False
        self._completed_reason: str | None = None
        self._report_path: str | None = None

    @classmethod
    def from_state(
        cls,
        state: ExaminerSessionState,
        *,
        scorer: ExamScorer | None = None,
        completion_writer: ExamCompletionWriter | None = None,
    ) -> ExaminerRuntime:
        runtime = cls(
            session_id=state.session_id,
            examiner_agent_id=state.examiner_agent_id,
            timeout_seconds=state.timeout_seconds,
            questions=state.questions,
            scorer=scorer,
            completion_writer=completion_writer,
            started_at=state.started_at,
        )
        runtime._current_question_index = state.current_question_index
        runtime._answers = list(state.answers)
        runtime._answered_count = len(state.answers)
        runtime._completed = state.status == "completed"
        runtime._completed_reason = state.completed_reason
        runtime._report_path = state.report_path
        return runtime

    async def connect(self) -> list[dict[str, Any]]:
        if not self._questions:
            return [
                self._session_init_message(),
                await self._completed_message("empty_question_bank"),
            ]
        if self._completed:
            return [
                self._session_init_message(),
                await self._completed_message(self._completed_reason or "reconnected"),
            ]
        return [
            self._session_init_message(),
            self._question_message(self._current_question_index),
        ]

    async def handle_client_message(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        if self._completed:
            return []
        if message.get("type") != "exam.answer":
            return []

        data = message.get("data")
        if not isinstance(data, dict):
            return []
        question_index = data.get("question_index")
        if question_index != self._current_question_index:
            return []

        question = self._questions[self._current_question_index]
        try:
            result = await self._scorer(
                question=question,
                answer_text=str(data.get("answer_text") or ""),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Examiner scoring failed; degraded to safe feedback",
                session_id=self._session_id,
                question_id=question.question_id,
                reason="SCORING_EXCEPTION",
                error_type=type(exc).__name__,
            )
            result = {
                "score": 0,
                "feedback": "scoring_unavailable",
                "reason": "SCORING_EXCEPTION",
            }
        feedback_data = {
            "question_index": self._current_question_index,
            "question_id": question.question_id,
            "score": result.get("score", 0),
            "feedback": result.get("feedback", ""),
            **(
                {"reason": result["reason"]}
                if isinstance(result.get("reason"), str)
                else {}
            ),
        }
        self._answers.append(
            {
                "question_index": feedback_data["question_index"],
                "question_id": feedback_data["question_id"],
                "answer_text": str(data.get("answer_text") or ""),
                "score": feedback_data["score"],
                "feedback": feedback_data["feedback"],
            }
        )
        messages = [
            {
                "type": "exam.feedback",
                "data": feedback_data,
            }
        ]
        self._answered_count += 1
        self._current_question_index += 1
        if self._current_question_index < len(self._questions):
            messages.append(self._question_message(self._current_question_index))
        else:
            messages.append(await self._completed_message("all_questions_answered"))
        return messages

    def serialize_state(self, *, now: float | None = None) -> dict[str, Any]:
        state = ExaminerSessionState(
            session_id=self._session_id,
            examiner_agent_id=self._examiner_agent_id,
            timeout_seconds=self._timeout_seconds,
            started_at=self._started_at,
            current_question_index=self._current_question_index,
            questions=list(self._questions),
            answers=list(self._answers),
            status="completed" if self._completed else "in_progress",
            completed_reason=self._completed_reason,
            remaining_seconds=self._remaining_seconds(now=now),
            report_path=self._report_path,
        )
        return state.to_dict()

    def _remaining_seconds(self, *, now: float | None = None) -> int:
        current_time = now if now is not None else time()
        elapsed = int(current_time - self._started_at)
        return max(0, self._timeout_seconds - elapsed)

    async def complete_if_timed_out(
        self, *, now: float | None = None
    ) -> list[dict[str, Any]]:
        current_time = now if now is not None else time()
        if self._completed or current_time - self._started_at < self._timeout_seconds:
            return []
        return [await self._completed_message("timed_out")]

    def _session_init_message(self) -> dict[str, Any]:
        return {
            "type": "session.init",
            "data": {
                "session_id": self._session_id,
                "examiner_agent_id": self._examiner_agent_id,
                "current_question_index": self._current_question_index,
                "total_questions": len(self._questions),
                "remaining_seconds": self._remaining_seconds(),
                "status": "in_progress",
            },
        }

    def _question_message(self, question_index: int) -> dict[str, Any]:
        question = self._questions[question_index]
        return {
            "type": "exam.question",
            "data": {
                "question_index": question_index,
                "question_id": question.question_id,
                "title": question.title,
                "stem": question.stem,
                "remaining_seconds": self._remaining_seconds(),
            },
        }

    async def _completed_message(self, reason: str) -> dict[str, Any]:
        self._completed = True
        if self._completed_reason is None:
            self._completed_reason = reason
        if self._report_path is None and self._completion_writer is not None:
            try:
                self._report_path = await self._completion_writer(
                    session_id=self._session_id,
                    answers=list(self._answers),
                    reason=self._completed_reason,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Examiner completion report marker write failed",
                    session_id=self._session_id,
                    reason="COMPLETION_REPORT_WRITE_EXCEPTION",
                    error_type=type(exc).__name__,
                )
        data: dict[str, Any] = {
            "session_id": self._session_id,
            "status": "completed",
            "answered_count": self._answered_count,
            "total_questions": len(self._questions),
            "reason": self._completed_reason,
        }
        if self._report_path is not None:
            data["report_path"] = self._report_path
        return {
            "type": "exam.completed",
            "data": data,
        }


class ExaminerWebSocketHandler(BaseWebSocketHandler):
    def __init__(self, runtime: ExaminerRuntime) -> None:
        super().__init__("curriculum_examiner")
        self._runtime = runtime

    async def on_connect(self) -> None:
        for message in await self._runtime.connect():
            await self.send_message(message)

    async def handle_message(self, message: dict[str, Any]) -> None:
        for response in await self._runtime.handle_client_message(message):
            await self.send_message(response)
        for response in await self._runtime.complete_if_timed_out():
            await self.send_message(response)

    def _create_state_snapshot(self) -> SessionStateSnapshot:
        return SessionStateSnapshot(
            session_id=self.session_id or "",
            scenario=self.scenario,
            user_id=self.user_id,
            runtime_state={"examiner": self._runtime.serialize_state()},
        )

    async def _restore_session_state(self, state: SessionStateSnapshot) -> None:
        await super()._restore_session_state(state)
        runtime_state = state.runtime_state if isinstance(state.runtime_state, dict) else {}
        examiner_state = runtime_state.get("examiner")
        if isinstance(examiner_state, dict):
            self._runtime = ExaminerRuntime.from_state(
                ExaminerSessionState.from_dict(examiner_state),
                scorer=self._runtime._scorer,
                completion_writer=self._runtime._completion_writer,
            )
