from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from re import compile as compile_pattern
from typing import Any, cast

ENGINE_STATE_VERSION = 1
GROUNDING_DIAGNOSTICS_SCHEMA_VERSION = 1
GroundingDiagnosticValue = str | int | float | bool
_GROUNDING_DIAGNOSTIC_STRING_VOCABULARY = {
    "status": frozenset(
        {"ready", "blocked", "degraded", "skipped", "failed", "unavailable", "healthy"}
    ),
    "reason_code": frozenset(
        {
            "not_applicable",
            "policy_missing",
            "policy_blocked",
            "kb_lock_blocked",
            "retrieval_ready",
            "retrieval_timeout",
            "retrieval_error",
            "retrieval_no_hit",
            "provider_unavailable",
            "snapshot_restored",
            "presentation_feedback_ready",
        }
    ),
    "source": frozenset(
        {
            "runtime",
            "snapshot",
            "policy",
            "knowledge",
            "provider",
            "cache",
            "presentation",
            "sales",
            "unknown",
        }
    ),
    "mode": frozenset(
        {
            "grounded",
            "blocked",
            "degraded",
            "skipped",
            "unrestricted",
            "kb_lock",
            "not_applicable",
        }
    ),
    "error_type": frozenset(
        {
            "timeout",
            "connection",
            "validation",
            "provider",
            "retrieval",
            "configuration",
            "unknown",
            "none",
        }
    ),
    "fallback_reason": frozenset(
        {
            "none",
            "timeout",
            "no_hit",
            "unavailable",
            "policy_blocked",
            "provider_error",
            "not_applicable",
        }
    ),
}
_GROUNDING_DIAGNOSTIC_IDENTIFIER_FIELDS = tuple(_GROUNDING_DIAGNOSTIC_STRING_VOCABULARY)
_GROUNDING_DIAGNOSTIC_NON_NEGATIVE_NUMBER_FIELDS = (
    "latency_ms",
    "result_count",
    "kb_count",
    "hit_count",
    "miss_count",
    "cache_size",
)
_GROUNDING_DIAGNOSTIC_BOOLEAN_FIELDS = (
    "cache_hit",
    "timeout",
    "degraded",
    "blocked",
)
_GROUNDING_DIAGNOSTIC_UNIT_INTERVAL_FIELDS = (
    "confidence",
    "answerability_score",
)
_GROUNDING_DIAGNOSTIC_ALLOWED_FIELDS = frozenset(
    (
        "schema_version",
        *_GROUNDING_DIAGNOSTIC_IDENTIFIER_FIELDS,
        *_GROUNDING_DIAGNOSTIC_NON_NEGATIVE_NUMBER_FIELDS,
        *_GROUNDING_DIAGNOSTIC_BOOLEAN_FIELDS,
        *_GROUNDING_DIAGNOSTIC_UNIT_INTERVAL_FIELDS,
    )
)
_GROUNDING_DIAGNOSTIC_IDENTIFIER_PATTERN = compile_pattern(r"[A-Za-z0-9._:-]{1,128}")


class RealtimeStateTransitionError(ValueError):
    """Raised when a realtime state invariant would be violated."""


class ConnectionPhase(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    CLOSING = "closing"


class TurnPhase(StrEnum):
    IDLE = "idle"
    RECEIVING = "receiving"
    GENERATING = "generating"
    STREAMING = "streaming"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    TIMED_OUT = "timed_out"


class GroundingPhase(StrEnum):
    EMPTY = "empty"
    PREPARING = "preparing"
    READY = "ready"
    BLOCKED = "blocked"
    DEGRADED = "degraded"


def _require_non_empty(value: object, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ValueError(f"{field_name}_must_be_string")
    if not value.strip():
        raise ValueError(f"{field_name}_must_be_non_empty")


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_must_be_mapping")
    return value


def _validate_engine_state_version(value: object) -> int:
    if type(value) is not int:
        raise ValueError("engine_state_version_must_be_integer")
    if value != ENGINE_STATE_VERSION:
        raise ValueError("unsupported_engine_state_version")
    return value


def _require_boolean(value: object, field_name: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{field_name}_must_be_boolean")


def _require_non_negative_integer(
    value: object,
    field_name: str,
    *,
    optional: bool = False,
) -> None:
    if optional and value is None:
        return
    if type(value) is not int:
        raise ValueError(f"{field_name}_must_be_integer")
    if value < 0:
        raise ValueError(f"{field_name}_must_be_non_negative")


def _require_json_string_list(
    value: object,
    field_name: str,
    item_field_name: str,
) -> set[str]:
    if type(value) is not list:
        raise ValueError(f"{field_name}_must_be_list")
    validated: set[str] = set()
    for item in cast(list[object], value):
        if type(item) is not str:
            raise ValueError(f"{item_field_name}_must_be_string")
        if not item.strip():
            raise ValueError(f"{item_field_name}_must_be_non_empty")
        validated.add(item)
    return validated


def _is_finite_number(value: object) -> bool:
    if type(value) is int:
        return True
    return type(value) is float and isfinite(value)


@dataclass(slots=True)
class ConnectionState:
    phase: ConnectionPhase = ConnectionPhase.DISCONNECTED
    session_id: str | None = None
    healthy: bool = False
    reconnecting: bool = False
    epoch: int = 0
    reason: str | None = None

    def __post_init__(self) -> None:
        self.phase = ConnectionPhase(self.phase)
        _require_non_empty(self.session_id, "connection_session_id")
        _require_non_empty(self.reason, "connection_reason")
        _require_boolean(self.healthy, "connection_healthy")
        _require_boolean(self.reconnecting, "connection_reconnecting")
        _require_non_negative_integer(self.epoch, "connection_epoch")

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase.value,
            "session_id": self.session_id,
            "healthy": self.healthy,
            "reconnecting": self.reconnecting,
            "epoch": self.epoch,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ConnectionState:
        return cls(
            phase=ConnectionPhase(payload.get("phase", ConnectionPhase.DISCONNECTED)),
            session_id=payload.get("session_id"),
            healthy=payload.get("healthy", False),
            reconnecting=payload.get("reconnecting", False),
            epoch=payload.get("epoch", 0),
            reason=payload.get("reason"),
        )


@dataclass(slots=True)
class TurnState:
    phase: TurnPhase = TurnPhase.IDLE
    request_id: int | None = None
    response_id: str | None = None
    stream_id: str | None = None
    interruption_reason: str | None = None
    timeout_reason: str | None = None
    completion_reason: str | None = None

    def __post_init__(self) -> None:
        self.phase = TurnPhase(self.phase)
        _require_non_negative_integer(
            self.request_id,
            "turn_request_id",
            optional=True,
        )
        _require_non_empty(self.response_id, "turn_response_id")
        _require_non_empty(self.stream_id, "turn_stream_id")
        _require_non_empty(self.interruption_reason, "turn_interruption_reason")
        _require_non_empty(self.timeout_reason, "turn_timeout_reason")
        _require_non_empty(self.completion_reason, "turn_completion_reason")

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase.value,
            "request_id": self.request_id,
            "response_id": self.response_id,
            "stream_id": self.stream_id,
            "interruption_reason": self.interruption_reason,
            "timeout_reason": self.timeout_reason,
            "completion_reason": self.completion_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TurnState:
        raw_request_id = payload.get("request_id")
        return cls(
            phase=TurnPhase(payload.get("phase", TurnPhase.IDLE)),
            request_id=raw_request_id,
            response_id=payload.get("response_id"),
            stream_id=payload.get("stream_id"),
            interruption_reason=payload.get("interruption_reason"),
            timeout_reason=payload.get("timeout_reason"),
            completion_reason=payload.get("completion_reason"),
        )


@dataclass(slots=True)
class GroundingState:
    phase: GroundingPhase = GroundingPhase.EMPTY
    decision_id: str | None = None
    frozen_policy_hash: str | None = None
    mode: str | None = None
    diagnostics: dict[str, GroundingDiagnosticValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.phase = GroundingPhase(self.phase)
        _require_non_empty(self.decision_id, "grounding_decision_id")
        _require_non_empty(self.frozen_policy_hash, "grounding_frozen_policy_hash")
        _require_non_empty(self.mode, "grounding_mode")
        self.diagnostics = self.validate_diagnostics(self.diagnostics)

    @staticmethod
    def validate_diagnostics(
        diagnostics: Mapping[Any, Any],
    ) -> dict[str, GroundingDiagnosticValue]:
        if not diagnostics:
            return {}
        for key in diagnostics:
            if not isinstance(key, str):
                raise ValueError("grounding_diagnostic_field_must_be_string")
        unknown_fields = sorted(set(diagnostics) - _GROUNDING_DIAGNOSTIC_ALLOWED_FIELDS)
        if unknown_fields:
            raise ValueError(f"grounding_diagnostic_field_unknown:{unknown_fields[0]}")
        if "schema_version" not in diagnostics:
            raise ValueError("grounding_diagnostics_schema_version_required")
        schema_version = diagnostics["schema_version"]
        if type(schema_version) is not int:
            raise ValueError("grounding_diagnostics_schema_version_must_be_integer")
        if schema_version != GROUNDING_DIAGNOSTICS_SCHEMA_VERSION:
            raise ValueError("unsupported_grounding_diagnostics_schema_version")

        validated: dict[str, GroundingDiagnosticValue] = {
            "schema_version": schema_version
        }
        for field_name in _GROUNDING_DIAGNOSTIC_IDENTIFIER_FIELDS:
            if field_name not in diagnostics:
                continue
            value = diagnostics[field_name]
            if not isinstance(value, str) or not (
                _GROUNDING_DIAGNOSTIC_IDENTIFIER_PATTERN.fullmatch(value)
            ):
                raise ValueError(
                    f"grounding_diagnostic_identifier_invalid:{field_name}"
                )
            if value not in _GROUNDING_DIAGNOSTIC_STRING_VOCABULARY[field_name]:
                raise ValueError(
                    f"grounding_diagnostic_vocabulary_invalid:{field_name}"
                )
            validated[field_name] = value
        for field_name in _GROUNDING_DIAGNOSTIC_NON_NEGATIVE_NUMBER_FIELDS:
            if field_name not in diagnostics:
                continue
            value = diagnostics[field_name]
            if not _is_finite_number(value) or value < 0:
                raise ValueError(
                    f"grounding_diagnostic_non_negative_number_invalid:{field_name}"
                )
            validated[field_name] = cast(int | float, value)
        for field_name in _GROUNDING_DIAGNOSTIC_BOOLEAN_FIELDS:
            if field_name not in diagnostics:
                continue
            value = diagnostics[field_name]
            if type(value) is not bool:
                raise ValueError(f"grounding_diagnostic_boolean_invalid:{field_name}")
            validated[field_name] = value
        for field_name in _GROUNDING_DIAGNOSTIC_UNIT_INTERVAL_FIELDS:
            if field_name not in diagnostics:
                continue
            value = diagnostics[field_name]
            if not _is_finite_number(value) or not 0 <= value <= 1:
                raise ValueError(
                    f"grounding_diagnostic_unit_interval_invalid:{field_name}"
                )
            validated[field_name] = cast(int | float, value)
        return validated

    def to_dict(self) -> dict[str, object]:
        diagnostics = self.validate_diagnostics(self.diagnostics)
        return {
            "phase": self.phase.value,
            "decision_id": self.decision_id,
            "frozen_policy_hash": self.frozen_policy_hash,
            "mode": self.mode,
            "diagnostics": deepcopy(diagnostics),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GroundingState:
        diagnostics = _mapping(payload.get("diagnostics", {}), "grounding_diagnostics")
        return cls(
            phase=GroundingPhase(payload.get("phase", GroundingPhase.EMPTY)),
            decision_id=payload.get("decision_id"),
            frozen_policy_hash=payload.get("frozen_policy_hash"),
            mode=payload.get("mode"),
            diagnostics=deepcopy(dict(diagnostics)),
        )


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_key: str
    evidence_type: str
    turn_number: int
    payload_digest: str

    def __post_init__(self) -> None:
        _require_non_empty(self.evidence_key, "evidence_key")
        _require_non_empty(self.evidence_type, "evidence_type")
        _require_non_empty(self.payload_digest, "evidence_payload_digest")
        _require_non_negative_integer(self.turn_number, "evidence_turn_number")

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_key": self.evidence_key,
            "evidence_type": self.evidence_type,
            "turn_number": self.turn_number,
            "payload_digest": self.payload_digest,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceRecord:
        return cls(
            evidence_key=payload.get("evidence_key", ""),
            evidence_type=payload.get("evidence_type", ""),
            turn_number=payload.get("turn_number", 0),
            payload_digest=payload.get("payload_digest", ""),
        )


@dataclass(slots=True)
class EvidenceState:
    records: dict[str, EvidenceRecord] = field(default_factory=dict)
    pending_flush_keys: set[str] = field(default_factory=set)
    acknowledged_keys: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        for key, record in self.records.items():
            if key != record.evidence_key:
                raise ValueError("evidence_record_key_mismatch")
        known_keys = set(self.records)
        if not self.pending_flush_keys <= known_keys:
            raise ValueError("pending_evidence_key_unknown")
        if not self.acknowledged_keys <= known_keys:
            raise ValueError("acknowledged_evidence_key_unknown")
        if self.pending_flush_keys & self.acknowledged_keys:
            raise ValueError("evidence_key_pending_and_acknowledged")

    def record(
        self,
        *,
        evidence_key: str,
        evidence_type: str,
        turn_number: int,
        payload_digest: str,
    ) -> bool:
        candidate = EvidenceRecord(
            evidence_key=evidence_key,
            evidence_type=evidence_type,
            turn_number=turn_number,
            payload_digest=payload_digest,
        )
        existing = self.records.get(evidence_key)
        if existing is None:
            self.records[evidence_key] = candidate
            return True
        if existing != candidate:
            raise RealtimeStateTransitionError("evidence_key_conflict")
        return False

    def mark_pending(self, evidence_key: str) -> bool:
        if evidence_key not in self.records:
            raise RealtimeStateTransitionError("unknown_evidence_key")
        if evidence_key in self.acknowledged_keys:
            return False
        previous_count = len(self.pending_flush_keys)
        self.pending_flush_keys.add(evidence_key)
        return len(self.pending_flush_keys) != previous_count

    def acknowledge(self, evidence_key: str) -> bool:
        if evidence_key in self.acknowledged_keys:
            return False
        if evidence_key not in self.pending_flush_keys:
            raise RealtimeStateTransitionError("evidence_not_pending")
        self.pending_flush_keys.remove(evidence_key)
        self.acknowledged_keys.add(evidence_key)
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "records": {
                key: record.to_dict() for key, record in sorted(self.records.items())
            },
            "pending_flush_keys": sorted(self.pending_flush_keys),
            "acknowledged_keys": sorted(self.acknowledged_keys),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceState:
        raw_records = _mapping(payload.get("records", {}), "evidence_records")
        records: dict[str, EvidenceRecord] = {}
        for key, record in raw_records.items():
            if type(key) is not str:
                raise ValueError("evidence_record_key_must_be_string")
            if not key.strip():
                raise ValueError("evidence_record_key_must_be_non_empty")
            records[key] = EvidenceRecord.from_dict(_mapping(record, "evidence_record"))
        return cls(
            records=records,
            pending_flush_keys=_require_json_string_list(
                payload.get("pending_flush_keys", []),
                "pending_flush_keys",
                "pending_flush_key",
            ),
            acknowledged_keys=_require_json_string_list(
                payload.get("acknowledged_keys", []),
                "acknowledged_keys",
                "acknowledged_key",
            ),
        )


@dataclass(slots=True)
class RealtimeSessionState:
    scenario_type: str
    version: int = ENGINE_STATE_VERSION
    connection: ConnectionState = field(default_factory=ConnectionState)
    turn: TurnState = field(default_factory=TurnState)
    grounding: GroundingState = field(default_factory=GroundingState)
    evidence: EvidenceState = field(default_factory=EvidenceState)

    def __post_init__(self) -> None:
        _require_non_empty(self.scenario_type, "scenario_type")
        self.version = _validate_engine_state_version(self.version)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "scenario_type": self.scenario_type,
            "connection": self.connection.to_dict(),
            "turn": self.turn.to_dict(),
            "grounding": self.grounding.to_dict(),
            "evidence": self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RealtimeSessionState:
        version = _validate_engine_state_version(
            payload.get("version", ENGINE_STATE_VERSION)
        )
        return cls(
            scenario_type=payload.get("scenario_type", ""),
            version=version,
            connection=ConnectionState.from_dict(
                _mapping(payload.get("connection", {}), "connection")
            ),
            turn=TurnState.from_dict(_mapping(payload.get("turn", {}), "turn")),
            grounding=GroundingState.from_dict(
                _mapping(payload.get("grounding", {}), "grounding")
            ),
            evidence=EvidenceState.from_dict(
                _mapping(payload.get("evidence", {}), "evidence")
            ),
        )
