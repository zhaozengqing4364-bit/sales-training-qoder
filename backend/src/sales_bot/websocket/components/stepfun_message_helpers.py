"""Helper utilities for StepFun message persistence flow."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select

from common.conversation.models import ConversationMessage
from common.conversation.storage import MessageStorageService, normalize_objection_ledger
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


def _coerce_bounded_score(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, normalized))


def normalize_score_snapshot(score_snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Canonicalize score snapshots to the stable `overall_score` contract."""
    if not isinstance(score_snapshot, dict):
        return None

    normalized: dict[str, Any] = {}

    dimension_scores_raw = score_snapshot.get("dimension_scores")
    normalized_dimensions: dict[str, float] = {}
    if isinstance(dimension_scores_raw, dict):
        for key, raw_value in dimension_scores_raw.items():
            if not isinstance(key, str) or not key:
                continue
            normalized_value = _coerce_bounded_score(raw_value)
            if normalized_value is None:
                continue
            normalized_dimensions[key] = normalized_value

    overall_score = _coerce_bounded_score(score_snapshot.get("overall_score"))
    if overall_score is None:
        overall_score = _coerce_bounded_score(score_snapshot.get("overall"))
    if overall_score is None and normalized_dimensions:
        overall_score = round(
            sum(normalized_dimensions.values()) / len(normalized_dimensions),
            2,
        )

    if overall_score is not None:
        normalized["overall_score"] = overall_score
    if normalized_dimensions:
        normalized["dimension_scores"] = normalized_dimensions

    stage_name = score_snapshot.get("stage_name")
    if isinstance(stage_name, str) and stage_name.strip():
        normalized["stage_name"] = stage_name.strip()

    suggestions = score_snapshot.get("suggestions")
    if isinstance(suggestions, list):
        normalized_suggestions = [
            item.strip()
            for item in suggestions
            if isinstance(item, str) and item.strip()
        ]
        if normalized_suggestions:
            normalized["suggestions"] = normalized_suggestions

    canonical_kernel = score_snapshot.get("canonical_evaluation_kernel")
    if isinstance(canonical_kernel, dict) and canonical_kernel:
        normalized["canonical_evaluation_kernel"] = canonical_kernel

    compatibility_readers = score_snapshot.get("compatibility_readers")
    if isinstance(compatibility_readers, dict) and compatibility_readers:
        normalized["compatibility_readers"] = compatibility_readers

    return normalized or None


def _normalize_analysis_payload(
    *,
    sales_stage: str | None,
    analysis_data: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = analysis_data if isinstance(analysis_data, dict) else {}
    normalized: dict[str, Any] = {}

    resolved_sales_stage = sales_stage
    if not (isinstance(resolved_sales_stage, str) and resolved_sales_stage.strip()):
        resolved_sales_stage = payload.get("sales_stage")
    if isinstance(resolved_sales_stage, str) and resolved_sales_stage.strip():
        normalized["sales_stage"] = resolved_sales_stage.strip()

    fuzzy_words = payload.get("fuzzy_words")
    if isinstance(fuzzy_words, list):
        normalized["fuzzy_words"] = fuzzy_words

    score_snapshot = normalize_score_snapshot(payload.get("score_snapshot"))
    if score_snapshot is not None:
        normalized["score_snapshot"] = score_snapshot

    ai_feedback = payload.get("ai_feedback")
    if isinstance(ai_feedback, str) and ai_feedback.strip():
        normalized["ai_feedback"] = ai_feedback.strip()

    transcript_metadata = payload.get("transcript_metadata")
    if isinstance(transcript_metadata, dict):
        normalized["transcript_metadata"] = transcript_metadata

    objection_ledger = normalize_objection_ledger(payload.get("objection_ledger"))
    if objection_ledger is not None:
        normalized["objection_ledger"] = objection_ledger

    return normalized


def normalize_message_persistence_payload(
    *,
    turn_number: int,
    content: str,
    sales_stage: str | None,
    analysis_data: dict[str, Any] | None,
) -> tuple[int, str, dict[str, Any]] | None:
    """Normalize persistence input into stable `(turn, content, analysis)` tuple."""
    normalized_content = content.strip()
    if not normalized_content:
        return None

    normalized_turn = max(1, int(turn_number))
    analysis_payload = _normalize_analysis_payload(
        sales_stage=sales_stage,
        analysis_data=analysis_data,
    )

    return normalized_turn, normalized_content, analysis_payload


def extract_analysis_patch_fields(
    analysis_payload: dict[str, Any],
) -> dict[str, Any]:
    """Extract typed patch fields from one analysis payload dict."""
    normalized_payload = _normalize_analysis_payload(
        sales_stage=None,
        analysis_data=analysis_payload,
    )
    return {
        "sales_stage": normalized_payload.get("sales_stage"),
        "fuzzy_words": normalized_payload.get("fuzzy_words"),
        "score_snapshot": normalized_payload.get("score_snapshot"),
        "ai_feedback": normalized_payload.get("ai_feedback"),
        "transcript_metadata": normalized_payload.get("transcript_metadata"),
        "objection_ledger": normalized_payload.get("objection_ledger"),
    }


async def patch_existing_message_analysis(
    *,
    session_id: str,
    turn_number: int,
    role: str,
    content: str,
    sales_stage: str | None,
    fuzzy_words: list[dict[str, Any]] | None,
    score_snapshot: dict[str, Any] | None,
    ai_feedback: str | None,
    transcript_metadata: dict[str, Any] | None,
    objection_ledger: dict[str, Any] | None,
    db_lock: asyncio.Lock,
) -> bool:
    """Patch analysis fields for an already persisted duplicate message."""
    normalized_fields = extract_analysis_patch_fields(
        {
            "sales_stage": sales_stage,
            "fuzzy_words": fuzzy_words,
            "score_snapshot": score_snapshot,
            "ai_feedback": ai_feedback,
            "transcript_metadata": transcript_metadata,
            "objection_ledger": objection_ledger,
        }
    )

    async with db_lock:
        try:
            async with AsyncSessionLocal() as db:
                statement = (
                    select(ConversationMessage.id)
                    .where(ConversationMessage.session_id == session_id)
                    .where(ConversationMessage.turn_number == turn_number)
                    .where(ConversationMessage.role == role)
                    .where(ConversationMessage.content == content)
                    .order_by(ConversationMessage.timestamp.desc())
                    .limit(1)
                )
                result = await db.execute(statement)
                message_id = result.scalar_one_or_none()
                if not message_id:
                    return False

                storage = MessageStorageService(db)
                update_result = await storage.update_analysis(
                    message_id,
                    sales_stage=normalized_fields["sales_stage"],
                    fuzzy_words=normalized_fields["fuzzy_words"],
                    score_snapshot=normalized_fields["score_snapshot"],
                    ai_feedback=normalized_fields["ai_feedback"],
                    transcript_metadata=normalized_fields["transcript_metadata"],
                    objection_ledger=normalized_fields["objection_ledger"],
                )
                if not update_result.is_success:
                    logger.warning(
                        "Failed to patch analysis on duplicate message",
                        session_id=session_id,
                        turn_number=turn_number,
                        role=role,
                        sales_stage=normalized_fields["sales_stage"],
                    )
                    return False

                logger.info(
                    "practice_session_evidence_persisted",
                    session_id=session_id,
                    turn_number=turn_number,
                    role=role,
                    evidence_scope="turn_patch",
                    sales_stage=normalized_fields["sales_stage"],
                    overall_score=(normalized_fields["score_snapshot"] or {}).get(
                        "overall_score"
                    ),
                )
                return True
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning(
                "Error patching analysis on duplicate message",
                session_id=session_id,
                turn_number=turn_number,
                role=role,
                sales_stage=normalized_fields["sales_stage"],
                error=str(exc),
            )
            return False


async def save_stepfun_message(
    *,
    session_id: str,
    turn_number: int,
    role: str,
    content: str,
    analysis_payload: dict[str, Any],
    db_lock: asyncio.Lock,
) -> bool:
    """Persist one StepFun conversation message into storage."""
    normalized_analysis = {
        key: value
        for key, value in extract_analysis_patch_fields(analysis_payload or {}).items()
        if value is not None
    }

    async with db_lock:
        try:
            async with AsyncSessionLocal() as db:
                storage = MessageStorageService(db)
                save_result = await storage.save_message(
                    session_id=session_id,
                    turn_number=turn_number,
                    role=role,
                    content=content,
                    analysis_data=normalized_analysis or None,
                )
                if not save_result.is_success:
                    logger.warning(
                        "Failed to persist StepFun realtime message",
                        session_id=session_id,
                        turn_number=turn_number,
                        role=role,
                    )
                    return False

                logger.info(
                    "practice_session_evidence_persisted",
                    session_id=session_id,
                    turn_number=turn_number,
                    role=role,
                    evidence_scope="turn",
                    sales_stage=normalized_analysis.get("sales_stage"),
                    overall_score=(normalized_analysis.get("score_snapshot") or {}).get(
                        "overall_score"
                    ),
                )
                return True
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning(
                "Error persisting StepFun realtime message",
                session_id=session_id,
                turn_number=turn_number,
                role=role,
                error=str(exc),
            )
            return False
