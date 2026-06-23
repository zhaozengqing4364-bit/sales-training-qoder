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
from sales_bot.websocket.components.stepfun_roleplay_runtime_helpers import (
    build_roleplay_runtime_state_patch,
    merge_runtime_metrics_snapshot_with_roleplay,
    record_v1_knowledge_degradation,
    sync_roleplay_runtime_observability,
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
    ledger_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        ledger_event=ledger_event,
    )
    record_v1_knowledge_degradation(
        effective_policy,
        status=status,
        error_message=error_message,
    )
    sync_roleplay_runtime_observability(effective_policy)
    return metrics


async def persist_runtime_metrics_to_session(
    *,
    session_id: str | None,
    effective_policy: dict[str, Any],
    session_factory: Callable[[], Any] = AsyncSessionLocal,
) -> bool:
    sync_roleplay_runtime_observability(effective_policy)
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
        merged_snapshot = merge_runtime_metrics_snapshot_with_roleplay(
            base_snapshot=base_snapshot,
            runtime_metrics=runtime_metrics,
            effective_policy=effective_policy,
        )
        if merged_snapshot is None:
            return False

        runtime_state_patch = build_roleplay_runtime_state_patch(effective_policy)
        if runtime_state_patch:
            existing_runtime_state = getattr(session, "runtime_state", None)
            runtime_state = (
                dict(existing_runtime_state)
                if isinstance(existing_runtime_state, dict)
                else {}
            )
            runtime_state.update(runtime_state_patch)
            session.runtime_state = runtime_state
        session.voice_policy_snapshot = merged_snapshot
        await db.commit()
        return True
