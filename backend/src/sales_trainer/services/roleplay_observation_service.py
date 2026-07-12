from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession
from common.monitoring.logger import get_logger, get_trace_id
from sales_trainer.models import SalesTrainerRoleplayObservation
from sales_trainer.schemas import (
    SalesTrainerRoleplayObservationSessionResponse,
    SalesTrainerRoleplayObservationStatus,
    SalesTrainerRoleplayObservationWrite,
    SalesTrainerRoleplayObservationWriteResult,
)
from sales_trainer.services.roleplay_observation_evaluator import (
    ObservationPolicy,
    sanitize_observation_payload,
)

ROLEPLAY_OBSERVATION_SALES_TRAINER_OWNER = "newcomer_training"
ROLEPLAY_OBSERVATION_FAILURE_CODE = "[ROLEPLAY_OBSERVATION_STORE_FAILED]"
ROLEPLAY_OBSERVATION_POLICY_SNAPSHOT_KEY = "roleplay_observation_policy"

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RoleplayObservationPolicyResolution:
    policy: ObservationPolicy
    source: str
    fallback_applied: bool
    fallback_reason: str | None = None


class RoleplayObservationServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class RoleplayObservationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def resolve_session_observation_policy(
        self,
        *,
        session_id: str,
    ) -> RoleplayObservationPolicyResolution:
        session = await self._db.get(PracticeSession, session_id)
        snapshot = getattr(session, "voice_policy_snapshot", None) if session else None
        return resolve_roleplay_observation_policy(snapshot)

    async def append_observation(
        self,
        payload: SalesTrainerRoleplayObservationWrite,
        *,
        commit: bool = True,
        non_blocking: bool = False,
    ) -> SalesTrainerRoleplayObservationWriteResult:
        safe_payload = _sanitize_observation_write(payload)
        try:
            return await self._append_observation(
                safe_payload,
                commit=commit,
            )
        except RoleplayObservationServiceError as exc:
            if non_blocking:
                return self._log_non_blocking_failure(
                    safe_payload,
                    error_code=exc.code,
                    error_message=exc.message,
                )
            raise
        except SQLAlchemyError as exc:
            await self._safe_rollback()
            if non_blocking:
                return self._log_non_blocking_failure(
                    safe_payload,
                    error_code=ROLEPLAY_OBSERVATION_FAILURE_CODE,
                    error_message=exc.__class__.__name__,
                )
            raise RoleplayObservationServiceError(
                ROLEPLAY_OBSERVATION_FAILURE_CODE,
                "角色扮演观测写入失败。",
                status_code=500,
            ) from exc

    async def list_session_observations(
        self,
        *,
        session_id: str,
        source_record_id: str | None = None,
    ) -> list[SalesTrainerRoleplayObservation]:
        stmt = select(SalesTrainerRoleplayObservation).where(
            SalesTrainerRoleplayObservation.session_id == session_id
        )
        if source_record_id:
            stmt = stmt.where(
                SalesTrainerRoleplayObservation.source_record_id == source_record_id
            )
        result = await self._db.execute(
            stmt.order_by(
                SalesTrainerRoleplayObservation.turn_index.asc(),
                SalesTrainerRoleplayObservation.created_at.asc(),
                SalesTrainerRoleplayObservation.observation_id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_session_summary(
        self,
        *,
        session_id: str,
        source_record_id: str | None = None,
    ) -> dict[str, Any]:
        observations = await self.list_session_observations(
            session_id=session_id,
            source_record_id=source_record_id,
        )
        source_counts = {
            "heuristic": 0,
            "llm_evaluator": 0,
        }
        status_counts = {
            "pending": 0,
            "completed": 0,
            "failed": 0,
            "ignored": 0,
        }
        latest_turn_index: int | None = None
        for observation in observations:
            source = cast(str, observation.source)
            turn_index = cast(int, observation.turn_index)
            source_counts[source] = source_counts.get(source, 0) + 1
            status = _observation_status(cast(str, observation.evaluator_status))
            status_counts[status] = status_counts.get(status, 0) + 1
            if latest_turn_index is None or turn_index > latest_turn_index:
                latest_turn_index = turn_index
        if source_record_id:
            effective_source_record_id = source_record_id
        elif observations:
            effective_source_record_id = cast(str, observations[0].source_record_id)
        else:
            effective_source_record_id = session_id
        payload = {
            "session_id": session_id,
            "source_record_id": effective_source_record_id,
            "total": len(observations),
            "latest_turn_index": latest_turn_index,
            "source_counts": source_counts,
            "status_counts": status_counts,
            "items": [serialize_roleplay_observation(item) for item in observations],
        }
        return cast(
            dict[str, Any],
            SalesTrainerRoleplayObservationSessionResponse.model_validate(
                payload
            ).model_dump(),
        )

    async def _append_observation(
        self,
        payload: SalesTrainerRoleplayObservationWrite,
        *,
        commit: bool,
    ) -> SalesTrainerRoleplayObservationWriteResult:
        session = await self._db.get(PracticeSession, payload.session_id)
        if session is None:
            raise RoleplayObservationServiceError(
                "[ROLEPLAY_OBSERVATION_SESSION_NOT_FOUND]",
                "实时对练会话不存在，无法写入观测。",
                status_code=404,
            )
        if str(getattr(session, "voice_mode", "") or "") != "stepfun_realtime":
            raise RoleplayObservationServiceError(
                "[ROLEPLAY_OBSERVATION_SESSION_MODE_INVALID]",
                "该会话不是 StepFun realtime 会话，无法写入观测。",
                status_code=409,
            )
        owner = _external_binding_owner(session.voice_policy_snapshot)
        if owner != ROLEPLAY_OBSERVATION_SALES_TRAINER_OWNER:
            raise RoleplayObservationServiceError(
                "[ROLEPLAY_OBSERVATION_SESSION_SCOPE_INVALID]",
                "该会话不属于新人训练路径实时对练，无法写入观测。",
                status_code=409,
            )

        source_record_id = payload.source_record_id or payload.session_id
        dimensions = _safe_dict_list(payload.dimensions)
        signals = _safe_dict_list(payload.signals)
        error_payload = _error_payload(payload.error)
        payload_hash = _payload_hash(
            {
                "source_record_id": source_record_id,
                "source": payload.source,
                "turn_index": payload.turn_index,
                "evaluator_status": payload.evaluator_status,
                "dimensions": dimensions,
                "signals": signals,
                "error": error_payload,
            }
        )
        existing_result = await self._db.execute(
            select(SalesTrainerRoleplayObservation).where(
                SalesTrainerRoleplayObservation.source_record_id == source_record_id,
                SalesTrainerRoleplayObservation.source == payload.source,
                SalesTrainerRoleplayObservation.turn_index == payload.turn_index,
                SalesTrainerRoleplayObservation.payload_hash == payload_hash,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return SalesTrainerRoleplayObservationWriteResult(
                stored=True,
                deduplicated=True,
                observation_id=existing.observation_id,
            )

        observation = SalesTrainerRoleplayObservation(
            session_id=payload.session_id,
            source_record_id=source_record_id,
            source=payload.source,
            turn_index=payload.turn_index,
            evaluator_status=payload.evaluator_status,
            dimensions_json=dimensions,
            signals_json=signals,
            error_json=error_payload,
            payload_hash=payload_hash,
            trace_id=payload.trace_id or get_trace_id(),
        )
        self._db.add(observation)
        await self._db.flush()
        if commit:
            await self._db.commit()
            await self._db.refresh(observation)
        return SalesTrainerRoleplayObservationWriteResult(
            stored=True,
            deduplicated=False,
            observation_id=observation.observation_id,
        )

    async def _safe_rollback(self) -> None:
        if self._db.in_transaction():
            await self._db.rollback()

    def _log_non_blocking_failure(
        self,
        payload: SalesTrainerRoleplayObservationWrite,
        *,
        error_code: str,
        error_message: str,
    ) -> SalesTrainerRoleplayObservationWriteResult:
        logger.warning(
            "sales_trainer_roleplay_observation_non_blocking_failed",
            session_id=payload.session_id,
            source_record_id=payload.source_record_id or payload.session_id,
            source=payload.source,
            turn_index=payload.turn_index,
            evaluator_status=payload.evaluator_status,
            error_code=error_code,
            error_message=error_message,
        )
        return SalesTrainerRoleplayObservationWriteResult(
            stored=False,
            deduplicated=False,
            error_code=error_code,
            error_message=error_message,
        )


def serialize_roleplay_observation(
    observation: SalesTrainerRoleplayObservation,
) -> dict[str, Any]:
    return {
        "observation_id": observation.observation_id,
        "session_id": observation.session_id,
        "source_record_id": observation.source_record_id,
        "source": observation.source,
        "turn_index": observation.turn_index,
        "evaluator_status": _observation_status(observation.evaluator_status),
        "dimensions": _safe_dict_list(observation.dimensions_json or []),
        "signals": _safe_dict_list(observation.signals_json or []),
        "error": _safe_optional_dict(observation.error_json),
        "trace_id": observation.trace_id,
        "created_at": observation.created_at,
        "updated_at": observation.updated_at,
    }


def _external_binding_owner(snapshot: Any) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    binding = snapshot.get("external_binding")
    if not isinstance(binding, dict):
        return None
    owner = binding.get("owner")
    if owner is None:
        return None
    text = str(owner).strip()
    return text or None


def resolve_roleplay_observation_policy(
    voice_policy_snapshot: Any,
) -> RoleplayObservationPolicyResolution:
    default_policy = ObservationPolicy()
    if not isinstance(voice_policy_snapshot, dict):
        return RoleplayObservationPolicyResolution(
            policy=default_policy,
            source="default",
            fallback_applied=False,
        )

    raw_policy = voice_policy_snapshot.get(ROLEPLAY_OBSERVATION_POLICY_SNAPSHOT_KEY)
    if raw_policy is None:
        return RoleplayObservationPolicyResolution(
            policy=default_policy,
            source="default",
            fallback_applied=False,
        )
    if not isinstance(raw_policy, dict):
        logger.warning(
            "sales_trainer_roleplay_observation_policy_invalid",
            reason="policy_not_object",
        )
        return RoleplayObservationPolicyResolution(
            policy=default_policy,
            source="default",
            fallback_applied=True,
            fallback_reason="policy_not_object",
        )

    merged = _merge_roleplay_observation_policy_value(
        default_policy.model_dump(mode="json"),
        raw_policy,
    )
    try:
        policy = ObservationPolicy.model_validate(merged)
    except ValidationError as exc:
        logger.warning(
            "sales_trainer_roleplay_observation_policy_invalid",
            reason="policy_validation_failed",
            error=str(exc),
        )
        return RoleplayObservationPolicyResolution(
            policy=default_policy,
            source="default",
            fallback_applied=True,
            fallback_reason="policy_validation_failed",
        )

    return RoleplayObservationPolicyResolution(
        policy=policy,
        source="snapshot",
        fallback_applied=False,
    )


def _merge_roleplay_observation_policy_value(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    merged = deepcopy(base)
    version = override.get("version")
    if version is not None:
        merged["version"] = version
    heuristic = override.get("heuristic")
    if isinstance(heuristic, dict):
        merged["heuristic"].update(heuristic)
    llm = override.get("llm")
    if isinstance(llm, dict):
        merged["llm"].update(llm)
    return merged


def _sanitize_observation_write(
    payload: SalesTrainerRoleplayObservationWrite,
) -> SalesTrainerRoleplayObservationWrite:
    return payload.model_copy(
        update={
            "dimensions": _safe_dict_list(payload.dimensions),
            "signals": _safe_dict_list(payload.signals),
            "error": _safe_optional_dict(_error_payload(payload.error)),
            "trace_id": _safe_optional_text(payload.trace_id),
        }
    )


def _safe_dict_list(value: Any) -> list[dict[str, Any]]:
    sanitized = sanitize_observation_payload(value)
    if not isinstance(sanitized, list):
        return []
    return [item for item in sanitized if isinstance(item, dict)]


def _safe_optional_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    sanitized = sanitize_observation_payload(value)
    return sanitized if isinstance(sanitized, dict) and sanitized else None


def _safe_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    sanitized = sanitize_observation_payload(str(value))
    text = str(sanitized or "").strip()
    return text or None


def _error_payload(error: Any) -> dict[str, Any] | None:
    if error is None:
        return None
    if hasattr(error, "model_dump"):
        payload = error.model_dump(exclude_none=True)
        return _safe_optional_dict(payload)
    if isinstance(error, dict):
        return _safe_optional_dict({str(key): value for key, value in error.items()})
    return None


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _observation_status(value: object) -> SalesTrainerRoleplayObservationStatus:
    status = str(value or "").strip() or "completed"
    if status not in {"pending", "completed", "failed", "ignored"}:
        return "completed"
    return status  # type: ignore[return-value]
