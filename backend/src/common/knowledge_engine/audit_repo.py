from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from common.db.models import KnowledgeAnswerRun, KnowledgeAnswerRunStep
from common.knowledge_engine.schemas import KnowledgeAuditStep


class KnowledgeAnswerAuditRepository:
    """Persist one knowledge-answer run and its ordered audit steps."""

    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def create_run(
        self,
        *,
        session_id: str,
        config_version_id: str | None,
        entrypoint: str,
        query_text: str,
        answerability: str,
        final_status: str,
        blocked_reason: str | None,
        citations: list[dict[str, Any]] | None,
        retrieval_summary: dict[str, Any] | None,
        steps: list[KnowledgeAuditStep] | None,
    ) -> KnowledgeAnswerRun:
        answer_run = KnowledgeAnswerRun(
            session_id=session_id,
            config_version_id=config_version_id,
            entrypoint=str(entrypoint or "unknown"),
            query_text=str(query_text or ""),
            answerability=str(answerability or "insufficient"),
            final_status=str(final_status or "completed"),
            blocked_reason=_normalize_optional_text(blocked_reason),
            citations_json=_normalize_dict_list(citations),
            retrieval_summary_json=_normalize_dict(retrieval_summary),
        )
        self._db_session.add(answer_run)
        self._db_session.flush()

        for index, step in enumerate(steps or [], start=1):
            self._db_session.add(
                KnowledgeAnswerRunStep(
                    answer_run_id=answer_run.id,
                    step_name=str(step.step_name or f"step_{index}"),
                    step_order=index,
                    status=str(step.status or "completed"),
                    input_payload=_normalize_dict(step.input_payload),
                    output_payload=_normalize_dict(step.output_payload),
                    duration_ms=max(0, int(step.duration_ms or 0)),
                )
            )

        self._db_session.commit()
        self._db_session.refresh(answer_run)
        return answer_run


def _normalize_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _normalize_optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
