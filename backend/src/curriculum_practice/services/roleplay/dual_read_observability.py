from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock

from common.config import settings
from common.monitoring.logger import get_logger, get_trace_id
from common.monitoring.metrics import track_situation_pack_dual_read_mismatch
from curriculum_practice.services.roleplay.dual_read_promotion_gate import (
    build_default_promotion_gate_payload,
)

logger = get_logger(__name__)

_lock = Lock()
_lookup_count = 0
_matched_count = 0
_mismatch_count = 0
_last_mismatch: dict[str, str | None] | None = None
_sample_mismatches: list[dict[str, str | None]] = []
_MAX_SAMPLE_MISMATCHES = 5


def record_dual_read_lookup(*, matched: bool) -> None:
    with _lock:
        global _lookup_count, _matched_count
        _lookup_count += 1
        if matched:
            _matched_count += 1


def record_dual_read_mismatch(
    *,
    code: str,
    scope: str,
    phase_a_hash: str | None,
    phase_b1_hash: str | None,
) -> None:
    """Emit structured log + Prometheus metric for a Phase A vs B1 hash mismatch."""
    trace_id = get_trace_id()
    detected_at = datetime.now(UTC).isoformat()
    mismatch_event = {
        "code": code,
        "scope": scope,
        "phase_a_hash": phase_a_hash,
        "phase_b1_hash": phase_b1_hash,
        "trace_id": trace_id,
        "detected_at": detected_at,
    }
    sample_event = {
        "code": code,
        "phase_a_hash": phase_a_hash,
        "phase_b1_hash": phase_b1_hash,
    }

    with _lock:
        global _mismatch_count, _last_mismatch, _sample_mismatches
        _mismatch_count += 1
        _last_mismatch = mismatch_event
        _sample_mismatches = [sample_event, *_sample_mismatches][:_MAX_SAMPLE_MISMATCHES]

    track_situation_pack_dual_read_mismatch(code=code, scope=scope)
    logger.warning(
        "situation_pack_dual_read_mismatch",
        code=code,
        scope=scope,
        phase_a_hash=phase_a_hash,
        phase_b1_hash=phase_b1_hash,
    )


def resolve_dual_read_authority() -> str | None:
    if not settings.SITUATION_PACK_DUAL_READ:
        return None
    if settings.SITUATION_PACK_B1_AUTHORITY:
        return "phase_b1"
    return "phase_a"


def get_dual_read_observability_snapshot() -> dict[str, object]:
    with _lock:
        mismatch_rate = (
            round(_mismatch_count / _lookup_count, 4) if _lookup_count > 0 else None
        )
        return {
            "enabled": settings.SITUATION_PACK_DUAL_READ,
            "b1_authority_enabled": settings.SITUATION_PACK_B1_AUTHORITY,
            "authority": resolve_dual_read_authority(),
            "lookup_count": _lookup_count,
            "matched_count": _matched_count,
            "mismatch_count": _mismatch_count,
            "mismatch_rate": mismatch_rate,
            "sample_mismatches": [dict(item) for item in _sample_mismatches],
            "last_mismatch": dict(_last_mismatch) if _last_mismatch is not None else None,
        }


def build_config_asset_center_overview_payload(
    *,
    promotion_gate: dict[str, object] | None = None,
) -> dict[str, object]:
    dual_read = get_dual_read_observability_snapshot()
    gate_payload = promotion_gate or build_default_promotion_gate_payload()
    dual_read = {
        **dual_read,
        "promotion_ready": bool(gate_payload.get("promotion_ready")),
        "blocked_reasons": list(gate_payload.get("blocked_reasons") or []),
        "approval_id": gate_payload.get("approval_id"),
        "window_start": gate_payload.get("window_start"),
        "window_end": gate_payload.get("window_end"),
    }
    mismatch_count = int(dual_read.get("mismatch_count") or 0)
    enabled = bool(dual_read.get("enabled"))
    if not enabled:
        status = "unknown"
    elif dual_read.get("blocked_reasons"):
        status = "warning"
    elif mismatch_count > 0:
        status = "warning"
    else:
        status = "healthy"
    return {
        "status": status,
        "dual_read": dual_read,
    }


def reset_dual_read_observability_for_tests() -> None:
    with _lock:
        global _lookup_count, _matched_count, _mismatch_count, _last_mismatch, _sample_mismatches
        _lookup_count = 0
        _matched_count = 0
        _mismatch_count = 0
        _last_mismatch = None
        _sample_mismatches = []
