from __future__ import annotations

from typing import Any

import pytest

from common.websocket.session_state_service import SessionStateSnapshot
from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    ExaminerSessionState,
    ExaminerWebSocketHandler,
    FrozenExamQuestion,
)


def _question(
    question_id: str = "question-1",
    *,
    title: str = "预算确认",
    stem: str = "你会如何确认客户预算？",
) -> FrozenExamQuestion:
    return FrozenExamQuestion(
        question_id=question_id,
        title=title,
        stem=stem,
        reference_answer="先确认预算区间，再确认决策流程。",
        scoring_criteria={"dimensions": [{"id": "discovery", "max": 100}]},
    )


@pytest.mark.asyncio
async def test_should_send_session_init_and_first_question_on_connect() -> None:
    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question()],
    )

    messages = await runtime.connect()

    assert [message["type"] for message in messages] == [
        "session.init",
        "exam.question",
    ]
    assert messages[0]["data"] == {
        "session_id": "session-1",
        "examiner_agent_id": "examiner-1",
        "current_question_index": 0,
        "total_questions": 1,
        "remaining_seconds": 600,
        "status": "in_progress",
    }
    assert messages[1]["data"] == {
        "question_index": 0,
        "question_id": "question-1",
        "title": "预算确认",
        "stem": "你会如何确认客户预算？",
        "remaining_seconds": 600,
    }


@pytest.mark.asyncio
async def test_should_emit_feedback_and_next_question_for_current_answer() -> None:
    async def scorer(*, question: FrozenExamQuestion, answer_text: str) -> dict[str, object]:
        assert question.reference_answer == "先确认预算区间，再确认决策流程。"
        assert question.scoring_criteria == {
            "dimensions": [{"id": "discovery", "max": 100}]
        }
        assert answer_text == "我会先确认预算，再确认谁审批。"
        return {"score": 88, "feedback": "覆盖预算和决策链"}

    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question("question-1"), _question("question-2", title="决策链", stem="你会如何确认决策链？")],
        scorer=scorer,
    )
    await runtime.connect()

    messages = await runtime.handle_client_message(
        {
            "type": "exam.answer",
            "data": {"question_index": 0, "answer_text": "我会先确认预算，再确认谁审批。"},
        }
    )

    assert [message["type"] for message in messages] == [
        "exam.feedback",
        "exam.question",
    ]
    assert messages[0]["data"] == {
        "question_index": 0,
        "question_id": "question-1",
        "score": 88,
        "feedback": "覆盖预算和决策链",
    }
    assert messages[1]["data"]["question_index"] == 1
    assert messages[1]["data"]["question_id"] == "question-2"


@pytest.mark.asyncio
async def test_should_emit_completed_after_final_answer() -> None:
    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question()],
    )
    await runtime.connect()

    messages = await runtime.handle_client_message(
        {
            "type": "exam.answer",
            "data": {"question_index": 0, "answer_text": "我会确认预算。"},
        }
    )

    assert [message["type"] for message in messages] == [
        "exam.feedback",
        "exam.completed",
    ]
    assert messages[1]["data"] == {
        "session_id": "session-1",
        "status": "completed",
        "answered_count": 1,
        "total_questions": 1,
        "reason": "all_questions_answered",
    }


@pytest.mark.asyncio
async def test_should_ignore_wrong_question_index_without_advancing_or_scoring() -> None:
    scoring_calls = 0

    async def scorer(*, question: FrozenExamQuestion, answer_text: str) -> dict[str, object]:
        nonlocal scoring_calls
        scoring_calls += 1
        return {"score": 100, "feedback": "should not run"}

    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question("question-1"), _question("question-2")],
        scorer=scorer,
    )
    await runtime.connect()

    ignored = await runtime.handle_client_message(
        {
            "type": "exam.answer",
            "data": {"question_index": 1, "answer_text": "跳题回答"},
        }
    )
    accepted = await runtime.handle_client_message(
        {
            "type": "exam.answer",
            "data": {"question_index": 0, "answer_text": "当前题回答"},
        }
    )

    assert ignored == []
    assert scoring_calls == 1
    assert accepted[0]["type"] == "exam.feedback"
    assert accepted[0]["data"]["question_index"] == 0


@pytest.mark.asyncio
async def test_should_ignore_duplicate_answer_without_rescoring() -> None:
    scoring_calls = 0

    async def scorer(*, question: FrozenExamQuestion, answer_text: str) -> dict[str, object]:
        nonlocal scoring_calls
        scoring_calls += 1
        return {"score": 75, "feedback": "已评分"}

    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question("question-1"), _question("question-2")],
        scorer=scorer,
    )
    await runtime.connect()

    first = await runtime.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "首次"}}
    )
    duplicate = await runtime.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "重复"}}
    )

    assert first[0]["type"] == "exam.feedback"
    assert duplicate == []
    assert scoring_calls == 1


@pytest.mark.asyncio
async def test_should_fail_gracefully_when_question_bank_is_empty() -> None:
    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[],
    )

    messages = await runtime.connect()

    assert [message["type"] for message in messages] == [
        "session.init",
        "exam.completed",
    ]
    assert messages[1]["data"] == {
        "session_id": "session-1",
        "status": "completed",
        "answered_count": 0,
        "total_questions": 0,
        "reason": "empty_question_bank",
    }


@pytest.mark.asyncio
async def test_should_degrade_scoring_exception_with_stable_reason() -> None:
    async def scorer(*, question: FrozenExamQuestion, answer_text: str) -> dict[str, object]:
        raise RuntimeError("llm timeout with provider internals")

    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question()],
        scorer=scorer,
    )
    await runtime.connect()

    messages = await runtime.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "回答"}}
    )

    assert messages[0]["type"] == "exam.feedback"
    assert messages[0]["data"] == {
        "question_index": 0,
        "question_id": "question-1",
        "score": 0,
        "feedback": "scoring_unavailable",
        "reason": "SCORING_EXCEPTION",
    }


@pytest.mark.asyncio
async def test_should_complete_when_timed_out() -> None:
    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=1,
        questions=[_question()],
        started_at=100.0,
    )
    await runtime.connect()

    messages = await runtime.complete_if_timed_out(now=101.5)

    assert messages == [
        {
            "type": "exam.completed",
            "data": {
                "session_id": "session-1",
                "status": "completed",
                "answered_count": 0,
                "total_questions": 1,
                "reason": "timed_out",
            },
        }
    ]


@pytest.mark.asyncio
async def test_should_serialize_state_for_reconnect_without_rescoring_completed_question() -> None:
    scoring_calls = 0

    async def scorer(*, question: FrozenExamQuestion, answer_text: str) -> dict[str, object]:
        nonlocal scoring_calls
        scoring_calls += 1
        return {"score": 82, "feedback": "已完成第一题"}

    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question("question-1"), _question("question-2")],
        scorer=scorer,
        started_at=100.0,
    )
    await runtime.connect()
    await runtime.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "首次"}}
    )

    snapshot = runtime.serialize_state(now=160.0)
    restored = ExaminerRuntime.from_state(ExaminerSessionState.from_dict(snapshot), scorer=scorer)
    reconnect_messages = await restored.connect()
    duplicate = await restored.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "重复"}}
    )

    assert snapshot["current_question_index"] == 1
    assert snapshot["remaining_seconds"] == 540
    assert snapshot["answers"] == [
        {
            "question_index": 0,
            "question_id": "question-1",
            "answer_text": "首次",
            "score": 82,
            "feedback": "已完成第一题",
        }
    ]
    assert [message["type"] for message in reconnect_messages] == [
        "session.init",
        "exam.question",
    ]
    assert reconnect_messages[1]["data"]["question_index"] == 1
    assert duplicate == []
    assert scoring_calls == 1


@pytest.mark.asyncio
async def test_should_keep_completed_exam_idempotent() -> None:
    scoring_calls = 0

    async def scorer(*, question: FrozenExamQuestion, answer_text: str) -> dict[str, object]:
        nonlocal scoring_calls
        scoring_calls += 1
        return {"score": 90, "feedback": "完成"}

    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question()],
        scorer=scorer,
    )
    await runtime.connect()
    completed = await runtime.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "回答"}}
    )

    after_completed_answer = await runtime.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "再次回答"}}
    )
    after_completed_timeout = await runtime.complete_if_timed_out(now=999999.0)

    assert completed[-1]["type"] == "exam.completed"
    assert after_completed_answer == []
    assert after_completed_timeout == []
    assert scoring_calls == 1


@pytest.mark.asyncio
async def test_should_write_completion_report_path_once_when_exam_completes() -> None:
    scoring_calls = 0
    report_writes: list[dict[str, object]] = []

    async def scorer(*, question: FrozenExamQuestion, answer_text: str) -> dict[str, object]:
        nonlocal scoring_calls
        scoring_calls += 1
        return {"score": 90, "feedback": "完成"}

    async def completion_writer(
        *,
        session_id: str,
        answers: list[dict[str, object]],
        reason: str,
    ) -> str:
        report_writes.append(
            {"session_id": session_id, "answers": list(answers), "reason": reason}
        )
        return f"/api/v1/evaluation/sessions/{session_id}/report"

    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question()],
        scorer=scorer,
        completion_writer=completion_writer,
    )
    await runtime.connect()

    completed = await runtime.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "回答"}}
    )
    restored = ExaminerRuntime.from_state(
        ExaminerSessionState.from_dict(runtime.serialize_state()),
        scorer=scorer,
        completion_writer=completion_writer,
    )
    reconnected = await restored.connect()
    after_completed_answer = await restored.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "再次回答"}}
    )

    assert completed[-1]["type"] == "exam.completed"
    assert completed[-1]["data"]["report_path"] == (
        "/api/v1/evaluation/sessions/session-1/report"
    )
    assert reconnected[-1]["data"]["report_path"] == (
        "/api/v1/evaluation/sessions/session-1/report"
    )
    assert after_completed_answer == []
    assert scoring_calls == 1
    assert len(report_writes) == 1
    assert report_writes[0]["reason"] == "all_questions_answered"


@pytest.mark.asyncio
async def test_should_preserve_completion_writer_when_handler_restores_mid_exam(
    monkeypatch,
) -> None:
    report_writes: list[dict[str, object]] = []
    sent_messages: list[dict[str, Any]] = []

    async def completion_writer(
        *,
        session_id: str,
        answers: list[dict[str, object]],
        reason: str,
    ) -> str:
        report_writes.append(
            {"session_id": session_id, "answers": list(answers), "reason": reason}
        )
        return f"/api/v1/evaluation/sessions/{session_id}/report"

    first_runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question("question-1"), _question("question-2")],
        completion_writer=completion_writer,
        started_at=100.0,
    )
    await first_runtime.connect()
    await first_runtime.handle_client_message(
        {"type": "exam.answer", "data": {"question_index": 0, "answer_text": "第一题"}}
    )
    snapshot = SessionStateSnapshot(
        session_id="session-1",
        scenario="curriculum_examiner",
        user_id="user-1",
        runtime_state={"examiner": first_runtime.serialize_state(now=120.0)},
    )
    reconnect_runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[_question("question-1"), _question("question-2")],
        completion_writer=completion_writer,
        started_at=100.0,
    )
    handler = ExaminerWebSocketHandler(reconnect_runtime)

    async def send_message(message: dict[str, Any]) -> None:
        sent_messages.append(message)

    monkeypatch.setattr(handler, "send_message", send_message)

    await handler._restore_session_state(snapshot)
    await handler.handle_message(
        {"type": "exam.answer", "data": {"question_index": 1, "answer_text": "第二题"}}
    )

    completed = sent_messages[-1]
    assert completed["type"] == "exam.completed"
    assert completed["data"]["report_path"] == (
        "/api/v1/evaluation/sessions/session-1/report"
    )
    assert len(report_writes) == 1
    assert report_writes[0]["reason"] == "all_questions_answered"
