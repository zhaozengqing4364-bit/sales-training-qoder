from __future__ import annotations

from curriculum_practice.services.examiner_report_service import (
    build_examiner_report_payload,
    examiner_report_frontend_path,
)
from curriculum_practice.websocket.examiner_runtime import FrozenExamQuestion


def test_examiner_report_frontend_path() -> None:
    assert examiner_report_frontend_path("abc") == "/exam/abc/report"


def test_build_examiner_report_payload_computes_overall_score() -> None:
    questions = {
        "q1": FrozenExamQuestion(
            question_id="q1",
            title="题一",
            stem="题干一",
            reference_answer="参考答案",
            scoring_criteria={"dimensions": ["discovery"]},
        )
    }
    payload = build_examiner_report_payload(
        session_id="session-1",
        answers=[
            {
                "question_index": 0,
                "question_id": "q1",
                "answer_text": "我的答案",
                "score": 80,
                "feedback": "不错",
            }
        ],
        reason="all_questions_answered",
        questions_by_id=questions,
    )

    assert payload["session_id"] == "session-1"
    assert payload["overall_score"] == 80.0
    assert payload["passed"] is True
    assert payload["items"][0]["title"] == "题一"
    assert payload["items"][0]["stem"] == "题干一"
