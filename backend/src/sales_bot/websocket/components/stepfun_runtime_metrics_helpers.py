"""Helper utilities for StepFun runtime-metrics recording and persistence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from common.db.models import PracticeSession
from common.db.session import AsyncSessionLocal
from sales_bot.websocket.components.stepfun_helpers import (
    ensure_knowledge_runtime_metrics,
    update_knowledge_runtime_metrics,
)
from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    merge_runtime_metrics_snapshot,
)


def apply_knowledge_runtime_metric(
    *,
    effective_policy: dict[str, Any],
    query: str,
    result_count: int,
    status: str,
    knowledge_base_ids: list[str],
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    error_message: str | None = None,
    retrieval_mode: str | None = None,
) -> dict[str, Any]:
    """Apply one retrieval metric update on in-memory effective policy."""
    metrics = ensure_knowledge_runtime_metrics(effective_policy)
    update_knowledge_runtime_metrics(
        metrics,
        query=query,
        result_count=result_count,
        status=status,
        knowledge_base_ids=knowledge_base_ids,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        error_message=error_message,
        retrieval_mode=retrieval_mode,
    )
    return metrics


async def persist_runtime_metrics_to_session(
    *,
    session_id: str | None,
    effective_policy: dict[str, Any],
    session_factory: Callable[[], Any] = AsyncSessionLocal,
) -> bool:
    """Persist in-memory runtime metrics to `practice_sessions.voice_policy_snapshot`."""
    runtime_metrics = effective_policy.get("runtime_metrics")
    if not session_id or not isinstance(runtime_metrics, dict):
        return False

    async with session_factory() as db:
        result = await db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return False

        base_snapshot = (
            session.voice_policy_snapshot
            if isinstance(session.voice_policy_snapshot, dict)
            else {}
        )
        merged_snapshot = merge_runtime_metrics_snapshot(
            base_snapshot=base_snapshot,
            runtime_metrics=runtime_metrics,
        )
        if merged_snapshot is None:
            return False

        session.voice_policy_snapshot = merged_snapshot
        await db.commit()
        return True
