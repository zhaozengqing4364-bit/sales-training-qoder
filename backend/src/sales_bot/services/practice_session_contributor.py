from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from common.monitoring.logger import get_logger
from common.services.practice_session_ports import (
    PracticeSessionPortError,
    PracticeSessionTerminalContext,
    PracticeSessionTerminalResult,
    register_practice_session_terminal_handler,
    register_runtime_policy_resolver_factory,
)
from common.services.practice_session_service import (
    _apply_sales_summary_scores_if_missing,
    _log_sales_terminal_evidence_state,
    _session_has_persisted_scores,
    _sync_sales_realtime_terminal_evidence,
    ensure_effectiveness_snapshot,
)
from sales_bot.services.bot_service import sales_bot_service
from sales_bot.services.summary_service import summary_service
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService

logger = get_logger(__name__)


async def finish_sales_practice_session(
    db: AsyncSession,
    context: PracticeSessionTerminalContext,
) -> PracticeSessionTerminalResult:
    session = context.session
    summary = None
    evidence_source: str | None = None
    if _session_has_persisted_scores(session):
        evidence_source = "session_scores"
    else:
        evidence_source = await _sync_sales_realtime_terminal_evidence(
            session_id=context.session_id,
            session=session,
            db=db,
        )
        if evidence_source is None:
            summary_result = await summary_service.generate_summary(
                uuid.UUID(context.session_id)
            )
            if not summary_result.is_success:
                logger.warning(
                    "practice_session_summary_generation_failed",
                    session_id=context.session_id,
                    voice_mode=getattr(session, "voice_mode", None),
                    summary_fallback=summary_result.fallback,
                )
                raise PracticeSessionPortError(
                    "[SUMMARY_GENERATION_FAILED]",
                    status_code=500,
                    message="总结生成失败",
                )
            summary = summary_result.value
            _apply_sales_summary_scores_if_missing(session, summary)
            evidence_source = "summary"

    snapshot = ensure_effectiveness_snapshot(session)
    if evidence_source is not None:
        _log_sales_terminal_evidence_state(
            session_id=context.session_id,
            session=session,
            snapshot=snapshot,
            evidence_source=evidence_source,
        )

    end_result = await sales_bot_service.end_session(uuid.UUID(context.session_id))
    if not end_result.is_success:
        logger.warning(
            "Sales bot end_session returned non-success",
            session_id=context.session_id,
            fallback=end_result.fallback,
        )

    return PracticeSessionTerminalResult(
        session=session,
        snapshot=snapshot,
        summary=summary,
    )


def register_sales_bot_practice_session_contributor() -> None:
    register_runtime_policy_resolver_factory(VoiceRuntimePolicyService)
    register_practice_session_terminal_handler("sales", finish_sales_practice_session)
