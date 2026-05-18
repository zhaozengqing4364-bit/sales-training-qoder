from __future__ import annotations

import pytest

from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    FrozenExamQuestion,
)


@pytest.mark.asyncio
async def test_should_score_answer_against_reference_answer() -> None:
    runtime = ExaminerRuntime(
        session_id="session-1",
        examiner_agent_id="examiner-1",
        timeout_seconds=600,
        questions=[
            FrozenExamQuestion(
                question_id="question-1",
                title="信任建立",
                stem="如何建立客户信任？",
                reference_answer="确认 背景 需求 案例",
                scoring_criteria={"keywords": ["确认", "背景", "需求", "案例"]},
            )
        ],
    )

    messages = await runtime.handle_client_message(
        {
            "type": "exam.answer",
            "data": {
                "question_index": 0,
                "answer_text": "先确认客户背景，再结合需求给出案例。",
            },
        }
    )

    feedback = messages[0]["data"]
    assert feedback["score"] >= 80
    assert feedback["feedback"] != "not_scored"
