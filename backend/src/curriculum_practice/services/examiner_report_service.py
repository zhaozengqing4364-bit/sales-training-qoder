from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession
from common.error_handling.result import Result
from curriculum_practice.models import QuestionItem
from curriculum_practice.websocket.examiner_runtime import FrozenExamQuestion


def examiner_report_frontend_path(session_id: str) -> str:
    return f"/exam/{session_id}/report"


def _questions_from_snapshot(session: PracticeSession) -> dict[str, FrozenExamQuestion]:
    snapshot = session.curriculum_snapshot if isinstance(session.curriculum_snapshot, dict) else {}
    assets = snapshot.get("content_assets")
    if not isinstance(assets, list):
        return {}

    questions: dict[str, FrozenExamQuestion] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if asset.get("asset_type") != "question_item":
            continue
        asset_id = str(asset.get("asset_id") or "").strip()
        if not asset_id:
            continue
        questions[asset_id] = FrozenExamQuestion(
            question_id=asset_id,
            title=str(asset.get("name") or asset_id),
            stem=str(asset.get("name") or ""),
            reference_answer=None,
            scoring_criteria={},
        )
    return questions


def _merge_question_metadata(
    *,
    questions_by_id: dict[str, FrozenExamQuestion],
    question_rows: dict[str, QuestionItem],
) -> dict[str, FrozenExamQuestion]:
    merged = dict(questions_by_id)
    for question_id, row in question_rows.items():
        merged[question_id] = FrozenExamQuestion(
            question_id=question_id,
            title=str(row.title or ""),
            stem=str(row.stem or ""),
            reference_answer=getattr(row, "reference_answer", None),
            scoring_criteria=dict(row.scoring_criteria or {}),
        )
    return merged


def build_examiner_report_payload(
    *,
    session_id: str,
    answers: list[dict[str, Any]],
    reason: str,
    questions_by_id: dict[str, FrozenExamQuestion],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    total_score = 0
    for answer in sorted(answers, key=lambda item: int(item.get("question_index") or 0)):
        question_id = str(answer.get("question_id") or "")
        question = questions_by_id.get(question_id)
        score = int(answer.get("score") or 0)
        total_score += score
        items.append(
            {
                "question_index": int(answer.get("question_index") or 0),
                "question_id": question_id,
                "title": question.title if question else "",
                "stem": question.stem if question else "",
                "answer_text": str(answer.get("answer_text") or ""),
                "score": score,
                "feedback": str(answer.get("feedback") or ""),
            }
        )

    answered_count = len(items)
    total_questions = len(questions_by_id) or answered_count or 0
    overall_score = round(total_score / answered_count, 1) if answered_count else 0.0

    return {
        "session_id": session_id,
        "completion_reason": reason,
        "overall_score": overall_score,
        "answered_count": answered_count,
        "total_questions": total_questions,
        "passed": overall_score >= 60.0,
        "generated_at": datetime.now(UTC).isoformat(),
        "items": items,
    }


class ExaminerReportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def persist_completion_report(
        self,
        *,
        session_id: str,
        answers: list[dict[str, Any]],
        reason: str,
    ) -> Result[dict[str, Any]]:
        session = await self._db.get(PracticeSession, session_id)
        if session is None:
            return Result.fail("[SESSION_NOT_FOUND]")

        questions_by_id = _questions_from_snapshot(session)
        question_ids = [
            str(answer.get("question_id") or "")
            for answer in answers
            if str(answer.get("question_id") or "").strip()
        ]
        if question_ids:
            rows = {
                str(row.question_id): row
                for row in (
                    await self._db.execute(
                        select(QuestionItem).where(
                            QuestionItem.question_id.in_(question_ids)
                        )
                    )
                ).scalars()
            }
            questions_by_id = _merge_question_metadata(
                questions_by_id=questions_by_id,
                question_rows=rows,
            )

        report = build_examiner_report_payload(
            session_id=session_id,
            answers=answers,
            reason=reason,
            questions_by_id=questions_by_id,
        )

        runtime_state = (
            dict(session.runtime_state) if isinstance(session.runtime_state, dict) else {}
        )
        runtime_state["examiner_report"] = report
        session.runtime_state = runtime_state
        session.status = "completed"
        session.logic_score = report["overall_score"]
        session.accuracy_score = report["overall_score"]
        session.completeness_score = report["overall_score"]
        if getattr(session, "report_status", None) != "completed":
            now = datetime.now(UTC)
            session.report_status = "completed"
            session.report_status_updated_at = now
            session.report_retryable = False
            session.report_generated_at = now
            session.report_error = None

        await self._db.commit()

        from common.services.session_runtime_lifecycle_hooks import (
            mark_session_runtime_completed,
        )

        await mark_session_runtime_completed(
            session_id,
            source="examiner_report_completed",
        )
        return Result.ok(report)

    async def get_report_for_user(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> Result[dict[str, Any]]:
        session = await self._db.get(PracticeSession, session_id)
        if session is None:
            return Result.fail("[SESSION_NOT_FOUND]")
        if str(session.user_id) != user_id:
            return Result.fail("[ACCESS_DENIED]")

        snapshot = (
            session.curriculum_snapshot if isinstance(session.curriculum_snapshot, dict) else {}
        )
        if snapshot.get("kind") != "curriculum_examiner_session":
            return Result.fail("[EXAMINER_REPORT_NOT_AVAILABLE]")

        runtime_state = session.runtime_state if isinstance(session.runtime_state, dict) else {}
        report = runtime_state.get("examiner_report")
        if isinstance(report, dict) and report.get("items"):
            return Result.ok(report)

        examiner_state = runtime_state.get("examiner")
        if isinstance(examiner_state, dict):
            answers = examiner_state.get("answers")
            if isinstance(answers, list) and answers:
                questions_by_id = _questions_from_snapshot(session)
                payload = build_examiner_report_payload(
                    session_id=session_id,
                    answers=[item for item in answers if isinstance(item, dict)],
                    reason=str(examiner_state.get("completed_reason") or "in_progress"),
                    questions_by_id=questions_by_id,
                )
                return Result.ok(payload)

        if getattr(session, "report_status", None) == "completed":
            return Result.fail("[EXAMINER_REPORT_PENDING]")
        return Result.fail("[EXAMINER_REPORT_NOT_FOUND]")
