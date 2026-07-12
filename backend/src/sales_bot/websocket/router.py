"""
Sales Bot WebSocket Router.

Routes WebSocket connections for persona-centered sales sessions.
Legacy simple-handler mode is disabled to prevent policy bypass.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Callable
from types import MappingProxyType
from typing import Any, cast

from fastapi import APIRouter, Query, WebSocket
from sqlalchemy import select

from common.auth.service import JWTError, resolve_websocket_auth
from common.db.models import PracticeSession, Scenario, User
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger, get_trace_id
from common.monitoring.trace_context import normalize_trace_id
from common.services.runtime_gate import (
    RuntimeAdmissionDecision,
    RuntimeGate,
    runtime_admission_failure,
)
from common.services.session_runtime_lifecycle_hooks import (
    mark_session_runtime_failed,
)
from common.websocket.session_manager import get_session_manager
from sales_bot.websocket.stepfun_realtime_handler import (
    create_stepfun_realtime_handler,
)
from training_runtime import (
    RuntimeHandlerFactoryKey,
    TrainingRuntimeDescriptor,
    dispatch_scenario_plugin,
)

logger = get_logger(__name__)

router = APIRouter()

RUNTIME_HANDLER_FACTORIES = MappingProxyType(
    {RuntimeHandlerFactoryKey.SALES_STEPFUN: create_stepfun_realtime_handler}
)

# M020/S01/T01 current sales websocket auth posture.
# This is an explicit inventory of the shipped behavior before T02 tightens the authority line.
SALES_WS_AUTH_POLICY: dict[str, list[str] | str] = {
    "formal": ["authorization_bearer", "session_cookie"],
    "compatibility": ["query_token"],
    "current_resolution_order": "authorization_header -> session_cookie -> query_token_compatibility",
}

ROLEPLAY_OBSERVATION_CAPTURE_SCHEMA_VERSION = "roleplay_observation_capture_v1"
ROLEPLAY_OBSERVATION_MAIN_CHAIN_EFFECT = "none"


@router.websocket("/ws/sales")
async def sales_websocket(
    websocket: WebSocket,
    session_id: str | None = Query(None, description="Practice session UUID"),
    token: str = Query(
        "",
        description="JWT authentication token (deprecated; use Authorization header)",
    ),
    agent_id: str | None = Query(None, description="Agent UUID for enhanced mode"),
    persona_id: str | None = Query(None, description="Persona UUID for enhanced mode"),
    voice_mode: str = Query("", description="Voice mode: legacy | stepfun_realtime"),
    trace_id: str = Query("", description="Request trace id for observability"),
) -> None:
    await _handle_sales_websocket(
        websocket=websocket,
        session_id=session_id,
        token=token,
        agent_id=agent_id,
        persona_id=persona_id,
        voice_mode=voice_mode,
        trace_id=trace_id,
    )


@router.websocket("/ws/sales/{session_id}")
async def sales_websocket_with_path(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(
        "",
        description="JWT authentication token (deprecated; use Authorization header)",
    ),
    agent_id: str | None = Query(None, description="Agent UUID for enhanced mode"),
    persona_id: str | None = Query(None, description="Persona UUID for enhanced mode"),
    voice_mode: str = Query("", description="Voice mode: legacy | stepfun_realtime"),
    trace_id: str = Query("", description="Request trace id for observability"),
) -> None:
    await _handle_sales_websocket(
        websocket=websocket,
        session_id=session_id,
        token=token,
        agent_id=agent_id,
        persona_id=persona_id,
        voice_mode=voice_mode,
        trace_id=trace_id,
    )


def _parse_session_id(session_id: str | None) -> str | None:
    candidate = (session_id or "").strip()
    if not candidate:
        return None

    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return None


async def _reject_invalid_session_id(
    websocket: WebSocket, session_id: str | None
) -> None:
    logger.warning(
        "Rejected /ws/sales connection due to invalid session_id", session_id=session_id
    )
    await websocket.accept()
    await websocket.close(code=4400, reason="INVALID_SESSION_ID")


async def _reject_sales_websocket(
    websocket: WebSocket,
    *,
    code: int,
    reason: str,
    log_message: str,
    session_id: str | None = None,
    mark_runtime_failed: bool = True,
    **log_fields: Any,
) -> None:
    logger.warning(log_message, **log_fields)
    if session_id and mark_runtime_failed:
        await mark_session_runtime_failed(
            session_id,
            failure_code=reason,
            source="sales_websocket_reject",
        )
    await websocket.accept()
    await websocket.close(code=code, reason=reason)


async def _reject_sales_admission(
    websocket: WebSocket,
    decision: RuntimeAdmissionDecision,
    *,
    session_id: str,
    **log_fields: Any,
) -> None:
    reason = decision.close_reason or decision.code or "RUNTIME_NOT_RUNNABLE"
    logger.warning(
        "Rejected /ws/sales connection due to runtime admission decision",
        session_id=session_id,
        runtime_type=decision.runtime_type,
        classification=decision.classification,
        failure_code=decision.code,
        missing=decision.missing,
        **log_fields,
    )
    if decision.mark_runtime_failed:
        await mark_session_runtime_failed(
            session_id,
            failure_code=reason,
            source="sales_websocket_reject",
        )
    await websocket.accept()
    await websocket.close(code=decision.close_code or 4413, reason=reason)


async def _handle_sales_websocket(
    websocket: WebSocket,
    session_id: str | None,
    token: str,
    agent_id: str | None,
    persona_id: str | None,
    voice_mode: str,
    trace_id: str,
) -> None:
    """
    WebSocket endpoint for sales practice.

    Supports StepFun realtime mode only when the persisted session voice_mode is
    stepfun_realtime. Legacy Sales handlers are disabled on this path.

    Query Parameters:
        session_id: Practice session UUID (path parameter)
        token: JWT authentication token
        agent_id: Optional Agent UUID for enhanced mode
        persona_id: Optional Persona UUID for enhanced mode

    WebSocket Messages:
        See docs/api-contract/websocket.md for message formats.
    """
    resolved_session_id = _parse_session_id(session_id)
    if not resolved_session_id:
        await _reject_invalid_session_id(websocket, session_id)
        return

    (
        persisted_voice_mode,
        persisted_agent_id,
        persisted_persona_id,
    ) = await _resolve_sales_runtime_identity(resolved_session_id)
    admission = await _resolve_sales_admission_decision(resolved_session_id)
    if admission is not None and not admission.allowed:
        await _reject_sales_admission(
            websocket,
            admission,
            session_id=resolved_session_id,
        )
        return

    # Enforce voice mode lock from persisted session snapshot.
    normalized_voice_mode = _normalize_requested_voice_mode(voice_mode)
    if normalized_voice_mode and normalized_voice_mode != persisted_voice_mode:
        logger.warning(
            "Ignoring mismatched ws voice_mode override",
            session_id=resolved_session_id,
            requested=normalized_voice_mode,
            persisted=persisted_voice_mode,
        )
    normalized_voice_mode = persisted_voice_mode
    if normalized_voice_mode != "stepfun_realtime":
        await _reject_sales_admission(
            websocket,
            runtime_admission_failure(
                runtime_type="sales",
                code="LEGACY_SALES_RUNTIME_DISABLED",
                missing=["voice_mode"],
            ),
            session_id=resolved_session_id,
            persisted_voice_mode=persisted_voice_mode,
        )
        return

    if agent_id and persisted_agent_id and agent_id != persisted_agent_id:
        logger.warning(
            "Ignoring mismatched ws agent_id override",
            session_id=resolved_session_id,
            requested=agent_id,
            persisted=persisted_agent_id,
        )
    if persona_id and persisted_persona_id and persona_id != persisted_persona_id:
        logger.warning(
            "Ignoring mismatched ws persona_id override",
            session_id=resolved_session_id,
            requested=persona_id,
            persisted=persisted_persona_id,
        )

    auth_token = _resolve_ws_token(websocket, token)
    user_id = _extract_user_id_from_token(auth_token)
    if user_id is None:
        await _reject_sales_websocket(
            websocket,
            code=4001,
            reason="Unauthorized",
            log_message="Rejected /ws/sales connection due to invalid token",
            session_id=resolved_session_id,
            mark_runtime_failed=False,
        )
        return

    session_owner_id = await _resolve_session_owner_id(resolved_session_id)
    if (
        session_owner_id
        and session_owner_id != user_id
        and not await _is_admin_user_id(user_id)
    ):
        await _reject_sales_websocket(
            websocket,
            code=4003,
            reason="ACCESS_DENIED",
            log_message="Rejected /ws/sales connection due to owner mismatch",
            session_id=resolved_session_id,
            mark_runtime_failed=False,
            request_user_id=user_id,
            session_owner_id=session_owner_id,
        )
        return

    resolved_agent_id = persisted_agent_id or agent_id
    resolved_persona_id = persisted_persona_id or persona_id

    if not (resolved_agent_id and resolved_persona_id):
        await _reject_sales_admission(
            websocket,
            runtime_admission_failure(
                runtime_type="sales",
                code="AGENT_PERSONA_REQUIRED",
                missing=["agent_id", "persona_id"],
            ),
            session_id=resolved_session_id,
            persisted_agent_id=persisted_agent_id,
            persisted_persona_id=persisted_persona_id,
        )
        return

    await _handle_stepfun_realtime_connection(
        websocket=websocket,
        session_id=resolved_session_id,
        token=auth_token,
        trace_id=normalize_trace_id(trace_id),
    )


async def _resolve_sales_admission_decision(
    session_id: str,
) -> RuntimeAdmissionDecision | None:
    async with AsyncSessionLocal() as db:
        return await RuntimeGate(db).admit_session(
            session_id,
            expected_runtime_type="sales",
        )


async def _resolve_sales_runtime_identity(
    session_id: str,
) -> tuple[str, str | None, str | None]:
    _scenario_type, voice_mode, agent_id, persona_id = await _resolve_session_runtime(
        session_id
    )
    return voice_mode, agent_id, persona_id


async def _is_kb_lock_unbound_session(session_id: str) -> bool:
    """Evaluate the sales KB lock through the shared runtime gate authority."""

    async with AsyncSessionLocal() as db:
        return cast(
            bool,
            await RuntimeGate(db).is_kb_lock_unbound_for_session_id(session_id),
        )


def _resolve_ws_token(websocket: WebSocket, query_token: str) -> str:
    """Resolve sales websocket auth with cookie preference and explicit compatibility logging."""
    resolution = resolve_websocket_auth(
        query_token=query_token,
        authorization_header=websocket.headers.get("authorization", ""),
        cookie_header=websocket.headers.get("cookie", ""),
    )
    if resolution["compatibility_mode"]:
        logger.warning(
            "Accepted /ws/sales connection via compatibility auth transport",
            transport=resolution["transport"],
        )
    return str(resolution["token"])


def _normalize_requested_voice_mode(voice_mode: str | None) -> str | None:
    mode = (voice_mode or "").strip().lower()
    if mode in {"legacy", "stepfun_realtime"}:
        return mode
    return None


def _default_voice_mode() -> str:
    default_mode = os.getenv("DEFAULT_VOICE_MODE", "stepfun_realtime").strip().lower()
    if default_mode not in {"legacy", "stepfun_realtime"}:
        default_mode = "stepfun_realtime"
    return default_mode


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


async def _resolve_session_runtime(
    session_id: str,
) -> tuple[str | None, str, str | None, str | None]:
    default_mode = _default_voice_mode()
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(
                    Scenario.scenario_type,
                    PracticeSession.voice_mode,
                    PracticeSession.agent_id,
                    PracticeSession.persona_id,
                )
                .join(
                    Scenario,
                    Scenario.scenario_id == PracticeSession.scenario_id,
                    isouter=True,
                )
                .where(PracticeSession.session_id == session_id)
            )
            row = result.first()
            if row:
                scenario_type, resolved_mode, agent_id, persona_id = row
                mode = str(resolved_mode or "").strip().lower()
                if mode in {"legacy", "stepfun_realtime"}:
                    return (
                        str(scenario_type or "").lower() or None,
                        mode,
                        str(agent_id) if agent_id else None,
                        str(persona_id) if persona_id else None,
                    )
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning(
            f"Failed to resolve session runtime from session {session_id}: {exc}"
        )

    return None, default_mode, None, None


async def _resolve_session_owner_id(session_id: str) -> str | None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession.user_id).where(
                    PracticeSession.session_id == session_id
                )
            )
            owner_id = result.scalar_one_or_none()
            return str(owner_id) if owner_id else None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve session owner before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return None


async def _is_admin_user_id(user_id: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User.role).where(User.user_id == user_id))
            role = result.scalar_one_or_none()
            return str(role or "").lower() == "admin"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve websocket user role before session access check",
            user_id=user_id,
            error=str(exc),
        )
        return False


async def _resolve_sales_trainer_observation_sink(
    session_id: str,
) -> Callable[[dict[str, Any]], Any] | None:
    try:
        if not await _is_sales_trainer_roleplay_observation_session(session_id):
            return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sales_trainer_roleplay_observation_sink_precheck_failed",
            session_id=session_id,
            error=str(exc),
        )
        return None
    return _build_sales_trainer_roleplay_observation_sink()


async def _is_sales_trainer_roleplay_observation_session(session_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PracticeSession.voice_policy_snapshot).where(
                PracticeSession.session_id == session_id
            )
        )
        snapshot = result.scalar_one_or_none()
    return _external_binding_owner(snapshot) == "sales_trainer"


def _build_sales_trainer_roleplay_observation_sink() -> Callable[[dict[str, Any]], Any]:
    async def sink(capture_payload: dict[str, Any]) -> None:
        try:
            await _store_sales_trainer_roleplay_observation(capture_payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "sales_trainer_roleplay_observation_sink_failed",
                session_id=_safe_string(capture_payload.get("session_id")),
                turn_index=_safe_int(capture_payload.get("turn_index")),
                source_event_type=_safe_string(
                    capture_payload.get("source_event_type")
                ),
                error=str(exc),
            )

    return sink


async def _store_sales_trainer_roleplay_observation(
    capture_payload: dict[str, Any],
) -> None:
    from sales_trainer.schemas import SalesTrainerRoleplayObservationWrite
    from sales_trainer.services.roleplay_observation_service import (
        RoleplayObservationService,
    )

    session_id = _safe_string(capture_payload.get("session_id"))
    if not session_id:
        return
    source_record_id = (
        _safe_string(capture_payload.get("source_record_id")) or session_id
    )
    speaker = _safe_string(capture_payload.get("speaker")).lower()
    transcript = _safe_string(capture_payload.get("transcript"), limit=6000)
    turn_index = max(0, _safe_int(capture_payload.get("turn_index")) or 0)
    trace_id = _safe_string(capture_payload.get("trace_id")) or get_trace_id()
    grounding_metadata = _safe_grounding_metadata(
        capture_payload.get("grounding_metadata")
    )
    current_stage = _safe_string(capture_payload.get("template_stage_key"))
    evaluation_request = _build_roleplay_observation_request_payload(
        speaker=speaker,
        transcript=transcript,
        turn_index=turn_index,
        trace_id=trace_id,
        source_event_type=_safe_string(capture_payload.get("source_event_type")),
        current_stage=current_stage,
        grounding_metadata=grounding_metadata,
    )
    evaluator = _build_roleplay_observation_evaluator()
    background_payload: dict[str, Any] | None = None

    async with AsyncSessionLocal() as db:
        service = RoleplayObservationService(db)
        policy_resolution = await service.resolve_session_observation_policy(
            session_id=session_id
        )
        if policy_resolution.policy.heuristic.enabled:
            evaluation = evaluator.evaluate_signals(
                {
                    **evaluation_request,
                    "llm": {"enabled": False},
                }
            )
            dimensions = [
                _capture_context_dimension(
                    capture_payload,
                    grounding_metadata=grounding_metadata,
                ),
                _evaluation_runtime_dimension(
                    evaluation,
                    policy_resolution=policy_resolution,
                ),
            ]
            signals = [
                signal.model_dump(mode="json", exclude_none=True)
                for signal in evaluation.signals
            ]
            evaluator_status = "completed" if speaker == "assistant" else "ignored"
            await service.append_observation(
                SalesTrainerRoleplayObservationWrite(
                    session_id=session_id,
                    source_record_id=source_record_id,
                    source="heuristic",
                    turn_index=turn_index,
                    evaluator_status=evaluator_status,
                    dimensions=dimensions,
                    signals=signals,
                    trace_id=trace_id,
                ),
                non_blocking=True,
            )
        if speaker == "assistant" and policy_resolution.policy.llm.enabled:
            background_payload = {
                "capture_payload": capture_payload,
                "source_record_id": source_record_id,
                "trace_id": trace_id,
                "turn_index": turn_index,
                "evaluation_request": evaluation_request,
                "grounding_metadata": grounding_metadata,
                "policy_resolution": policy_resolution,
            }
    if background_payload is not None:
        _schedule_sales_trainer_roleplay_observation_background(**background_payload)


def _build_roleplay_observation_evaluator() -> Any:
    from sales_trainer.services.roleplay_observation_evaluator import (
        RoleplayObservationEvaluator,
    )

    return RoleplayObservationEvaluator()


def _build_roleplay_observation_request_payload(
    *,
    speaker: str,
    transcript: str,
    turn_index: int,
    trace_id: str,
    source_event_type: str,
    current_stage: str,
    grounding_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "assistant_text": transcript if speaker == "assistant" else "",
        "conversation_history": [
            {
                "speaker": speaker or "unknown",
                "text": transcript,
                "metadata": {
                    "source_event_type": source_event_type,
                    "turn_index": turn_index,
                },
            }
        ],
        "current_stage": current_stage or None,
        "knowledge_evidence": _knowledge_evidence_from_grounding_metadata(
            grounding_metadata
        ),
        "turn_count": turn_index,
    }


def _schedule_sales_trainer_roleplay_observation_background(
    *,
    capture_payload: dict[str, Any],
    source_record_id: str,
    trace_id: str,
    turn_index: int,
    evaluation_request: dict[str, Any],
    grounding_metadata: dict[str, Any] | None,
    policy_resolution: Any,
) -> None:
    asyncio.create_task(
        _store_sales_trainer_roleplay_observation_llm(
            capture_payload=capture_payload,
            source_record_id=source_record_id,
            trace_id=trace_id,
            turn_index=turn_index,
            evaluation_request=evaluation_request,
            grounding_metadata=grounding_metadata,
            policy_resolution=policy_resolution,
        )
    )


async def _store_sales_trainer_roleplay_observation_llm(
    *,
    capture_payload: dict[str, Any],
    source_record_id: str,
    trace_id: str,
    turn_index: int,
    evaluation_request: dict[str, Any],
    grounding_metadata: dict[str, Any] | None,
    policy_resolution: Any,
) -> None:
    from sales_trainer.schemas import SalesTrainerRoleplayObservationWrite
    from sales_trainer.services.roleplay_observation_service import (
        RoleplayObservationService,
    )

    session_id = _safe_string(capture_payload.get("session_id"))
    if not session_id:
        return

    evaluation: Any | None = None
    error_payload: dict[str, Any] | None = None
    evaluator_status = "completed"
    signals: list[dict[str, Any]] = []
    try:
        evaluator = _build_roleplay_observation_evaluator()
        evaluation = await evaluator.evaluate_background(
            {
                **evaluation_request,
                "llm": policy_resolution.policy.llm.model_dump(mode="json"),
            }
        )
        signals = [
            signal.model_dump(mode="json", exclude_none=True)
            for signal in evaluation.signals
            if signal.source == "llm"
        ]
        evaluator_status = _llm_observation_status(evaluation.llm.status)
        error_payload = _llm_observation_error_payload(evaluation)
    except Exception as exc:  # noqa: BLE001
        evaluator_status = "failed"
        error_payload = {
            "code": f"[ROLEPLAY_OBSERVATION_LLM_EVALUATION_FAILED:{type(exc).__name__}]",
            "message": "LLM background observation failed before persistence.",
        }
        logger.warning(
            "sales_trainer_roleplay_observation_llm_background_failed",
            session_id=session_id,
            turn_index=turn_index,
            error_type=type(exc).__name__,
        )

    dimensions = [
        _capture_context_dimension(
            capture_payload, grounding_metadata=grounding_metadata
        ),
        _evaluation_runtime_dimension(
            evaluation,
            policy_resolution=policy_resolution,
            fallback_error=error_payload,
        ),
    ]
    try:
        async with AsyncSessionLocal() as db:
            await RoleplayObservationService(db).append_observation(
                SalesTrainerRoleplayObservationWrite(
                    session_id=session_id,
                    source_record_id=source_record_id,
                    source="llm_evaluator",
                    turn_index=turn_index,
                    evaluator_status=evaluator_status,
                    dimensions=dimensions,
                    signals=signals,
                    error=error_payload,
                    trace_id=trace_id,
                ),
                non_blocking=True,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sales_trainer_roleplay_observation_llm_store_failed",
            session_id=session_id,
            turn_index=turn_index,
            error_type=type(exc).__name__,
        )


def _evaluation_runtime_dimension(
    evaluation: Any | None,
    *,
    policy_resolution: Any,
    fallback_error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if evaluation is None:
        llm_payload: dict[str, Any] = {"enabled": True, "status": "failed"}
        if fallback_error:
            llm_payload["error"] = fallback_error.get("code")
        return {
            "key": "evaluation_runtime",
            "schema_version": "roleplay_observation_evaluation_v1",
            "realtime_disposition": "record_only",
            "main_chain_effect": ROLEPLAY_OBSERVATION_MAIN_CHAIN_EFFECT,
            "blocking": False,
            "heuristic_signal_count": 0,
            "llm_signal_count": 0,
            "llm": llm_payload,
            "total_latency_ms": 0,
            "policy": _roleplay_observation_policy_payload(policy_resolution),
        }
    return {
        "key": "evaluation_runtime",
        "schema_version": evaluation.schema_version,
        "realtime_disposition": evaluation.realtime_disposition,
        "main_chain_effect": ROLEPLAY_OBSERVATION_MAIN_CHAIN_EFFECT,
        "blocking": bool(evaluation.blocking),
        "heuristic_signal_count": evaluation.heuristic_signal_count,
        "llm_signal_count": evaluation.llm_signal_count,
        "llm": evaluation.llm.model_dump(mode="json", exclude_none=True),
        "total_latency_ms": evaluation.total_latency_ms,
        "policy": _roleplay_observation_policy_payload(policy_resolution),
    }


def _roleplay_observation_policy_payload(policy_resolution: Any) -> dict[str, Any]:
    policy = policy_resolution.policy
    return {
        "version": policy.version,
        "source": policy_resolution.source,
        "fallback_applied": bool(policy_resolution.fallback_applied),
        "fallback_reason": policy_resolution.fallback_reason,
        "heuristic_enabled": bool(policy.heuristic.enabled),
        "llm_enabled": bool(policy.llm.enabled),
        "llm_model_config_id": policy.llm.model_config_id,
        "llm_model_name": policy.llm.model_name,
    }


def _llm_observation_status(llm_status: str) -> str:
    if llm_status in {"success", "skipped"}:
        return "completed"
    if llm_status == "disabled":
        return "ignored"
    return "failed"


def _llm_observation_error_payload(evaluation: Any) -> dict[str, Any] | None:
    if _llm_observation_status(evaluation.llm.status) != "failed":
        return None
    return {
        "code": evaluation.llm.error or "[ROLEPLAY_OBSERVATION_LLM_FAILED]",
        "message": f"LLM evaluator status={evaluation.llm.status}",
    }


def _capture_context_dimension(
    capture_payload: dict[str, Any],
    *,
    grounding_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "key": "capture_context",
        "schema_version": ROLEPLAY_OBSERVATION_CAPTURE_SCHEMA_VERSION,
        "main_chain_effect": ROLEPLAY_OBSERVATION_MAIN_CHAIN_EFFECT,
        "speaker": _safe_string(capture_payload.get("speaker")) or "unknown",
        "source_event_type": _safe_string(capture_payload.get("source_event_type")),
        "response_id": _safe_string(capture_payload.get("response_id")) or None,
        "turn_id": _safe_string(capture_payload.get("turn_id")) or None,
        "template_stage_key": _safe_string(capture_payload.get("template_stage_key"))
        or None,
        "instruction_contract_hash": _safe_string(
            capture_payload.get("instruction_contract_hash")
        )
        or None,
        "captured_at": _safe_string(capture_payload.get("captured_at")) or None,
        "grounding_metadata": grounding_metadata,
    }


def _knowledge_evidence_from_grounding_metadata(
    grounding_metadata: dict[str, Any] | None,
) -> list[str]:
    if not grounding_metadata:
        return []
    evidence: list[str] = []
    for item in grounding_metadata.get("citations") or []:
        if not isinstance(item, dict):
            continue
        for key in ("document_title", "knowledge_base_name", "knowledge_base_id"):
            value = _safe_string(item.get(key))
            if value:
                evidence.append(value)
    return evidence


def _safe_grounding_metadata(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    metadata: dict[str, Any] = {}
    for key in (
        "mode",
        "answerability",
        "source_status",
        "audit_run_id",
        "live_audit_run_id",
        "shadow_audit_run_id",
    ):
        text = _safe_string(value.get(key))
        if text:
            metadata[key] = text

    kb_ids = value.get("knowledge_base_ids")
    if isinstance(kb_ids, list):
        normalized_kb_ids = [_safe_string(item) for item in kb_ids]
        metadata["knowledge_base_ids"] = [item for item in normalized_kb_ids if item]

    citation_count = _safe_int(value.get("citation_count"))
    if citation_count is not None:
        metadata["citation_count"] = citation_count

    citations: list[dict[str, Any]] = []
    raw_citations = value.get("citations")
    if isinstance(raw_citations, list):
        for item in raw_citations[:5]:
            if not isinstance(item, dict):
                continue
            citation: dict[str, Any] = {}
            for key in (
                "knowledge_base_id",
                "knowledge_base_name",
                "document_title",
            ):
                text = _safe_string(item.get(key))
                if text:
                    citation[key] = text
            score = item.get("score")
            if isinstance(score, (int, float)):
                citation["score"] = float(score)
            if citation:
                citations.append(citation)
    if citations:
        metadata["citations"] = citations
        metadata.setdefault("citation_count", len(citations))
    return metadata or None


def _external_binding_owner(snapshot: Any) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    binding = snapshot.get("external_binding")
    if not isinstance(binding, dict):
        return None
    return _safe_string(binding.get("owner")) or None


def _safe_string(value: Any, *, limit: int = 500) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    return text[:limit]


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _instantiate_runtime_handler(
    selection: Any,
    *,
    transcript_capture_sink: Callable[[dict[str, Any]], Any] | None = None,
) -> Any:
    try:
        resolved_key = RuntimeHandlerFactoryKey(selection.factory_key)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("unknown_runtime_handler_factory_key") from exc
    factory = RUNTIME_HANDLER_FACTORIES.get(resolved_key)
    if factory is None or resolved_key is not RuntimeHandlerFactoryKey.SALES_STEPFUN:
        raise ValueError("unknown_runtime_handler_factory_key")
    return factory(transcript_capture_sink=transcript_capture_sink)


async def _handle_stepfun_realtime_connection(
    websocket: WebSocket,
    session_id: str,
    token: str,
    trace_id: str | None = None,
) -> None:
    """Handle connection with StepFun realtime end-to-end voice model."""
    descriptor = TrainingRuntimeDescriptor(
        session_id=session_id,
        scenario_type="sales",
        voice_mode="stepfun_realtime",
    )
    selection = dispatch_scenario_plugin(descriptor).select_runtime_handler(descriptor)
    transcript_capture_sink = await _resolve_sales_trainer_observation_sink(session_id)
    handler = _instantiate_runtime_handler(
        selection,
        transcript_capture_sink=transcript_capture_sink,
    )

    logger.info(
        f"Using StepFunRealtimeHandler for session {session_id}",
        session_id=session_id,
    )

    session_manager = get_session_manager()
    await session_manager.register_session(session_id, handler)
    try:
        await handler.handle_connection(
            websocket,
            session_id,
            token,
            trace_id=trace_id,
        )
    finally:
        await session_manager.unregister_session(session_id)


def _extract_user_id_from_token(token: str) -> str | None:
    """
    Extract user_id from JWT token.

    Returns None if token is invalid so the caller can reject the connection.
    """
    try:
        from common.auth.service import verify_token

        payload = verify_token(token)
        if payload and "sub" in payload:
            return str(payload["sub"])
    except (JWTError, RuntimeError, ValueError, OSError) as e:
        logger.warning(f"Failed to decode token: {e}")

    return None
