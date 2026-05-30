from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import ROLEPLAY_SITUATION_PACKS_KEY
from common.config import settings
from common.db.models import ConfigBundleAuditLog, SystemLog
from common.monitoring.logger import get_trace_id
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)

DUAL_READ_MISMATCH_ACTION = "situation_pack_dual_read_mismatch"
B1_AUTHORITY_BLOCKED_ACTION = "situation_pack_b1_authority_blocked"
B1_AUTHORITY_PROMOTED_ACTION = "situation_pack_b1_authority_promoted"
PROMOTION_WINDOW_DAYS = 14

SituationPackReadAuthority = Literal["phase_a", "phase_b1"]


@dataclass(frozen=True, slots=True)
class DualReadPromotionGateDecision:
    requested_b1_authority: bool
    authority: SituationPackReadAuthority
    promotion_ready: bool
    blocked_reasons: list[str]
    approval_id: str | None
    window_start: datetime
    window_end: datetime

    def to_payload(self) -> dict[str, object]:
        return {
            "requested_b1_authority": self.requested_b1_authority,
            "authority": self.authority,
            "promotion_ready": self.promotion_ready,
            "blocked_reasons": list(self.blocked_reasons),
            "approval_id": self.approval_id,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
        }


class DualReadPromotionGateService:
    """Hard gate for promoting SituationPack reads from Phase A to B1."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def evaluate(
        self,
        *,
        requested_b1_authority: bool | None = None,
        approval_id: str | None = None,
        now: datetime | None = None,
        write_audit: bool = False,
    ) -> DualReadPromotionGateDecision:
        window_end = now or datetime.now(UTC)
        window_start = window_end - timedelta(days=PROMOTION_WINDOW_DAYS)
        requested = (
            settings.SITUATION_PACK_B1_AUTHORITY
            if requested_b1_authority is None
            else requested_b1_authority
        )
        approval = (
            settings.SITUATION_PACK_B1_APPROVAL_ID
            if approval_id is None
            else approval_id
        ).strip()

        blocked_reasons: list[str] = []
        if not settings.SITUATION_PACK_DUAL_READ:
            blocked_reasons.append("dual_read_disabled")
        if not approval:
            blocked_reasons.append("approval_missing")
        if await self._has_mismatch_in_window(window_start=window_start):
            blocked_reasons.append("dual_read_mismatch_in_window")
        if await self._has_unresolved_projection_sync_failure():
            blocked_reasons.append("projection_sync_failure_unresolved")

        promotion_ready = not blocked_reasons
        authority: SituationPackReadAuthority = (
            "phase_b1" if requested and promotion_ready else "phase_a"
        )
        decision = DualReadPromotionGateDecision(
            requested_b1_authority=requested,
            authority=authority,
            promotion_ready=promotion_ready,
            blocked_reasons=blocked_reasons if requested or blocked_reasons else [],
            approval_id=approval or None,
            window_start=window_start,
            window_end=window_end,
        )
        if write_audit and requested:
            await self._record_gate_audit(decision)
        return decision

    async def _has_mismatch_in_window(self, *, window_start: datetime) -> bool:
        result = await self._db.execute(
            select(SystemLog.log_id)
            .where(
                SystemLog.action == DUAL_READ_MISMATCH_ACTION,
                SystemLog.created_at >= window_start,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _has_unresolved_projection_sync_failure(self) -> bool:
        result = await self._db.execute(
            select(ConfigBundleAuditLog)
            .where(ConfigBundleAuditLog.bundle_key == ROLEPLAY_SITUATION_PACKS_KEY)
            .order_by(ConfigBundleAuditLog.created_at.desc())
            .limit(50)
        )
        for audit in result.scalars().all():
            snapshot = _as_dict(audit.after_snapshot_json)
            projection_sync = _as_dict(snapshot.get("projection_sync"))
            status = str(projection_sync.get("status") or "").strip()
            if not status:
                continue
            return status == "failed"
        return False

    async def _record_gate_audit(
        self,
        decision: DualReadPromotionGateDecision,
    ) -> None:
        action = (
            B1_AUTHORITY_PROMOTED_ACTION
            if decision.authority == "phase_b1"
            else B1_AUTHORITY_BLOCKED_ACTION
        )
        details = {
            **decision.to_payload(),
            "trace_id": get_trace_id(),
        }
        self._db.add(
            SystemLog(
                action=action,
                user_identifier="system",
                status="success" if decision.authority == "phase_b1" else "warning",
                details=json.dumps(details, ensure_ascii=False, default=str),
            )
        )
        await self._db.flush()


async def record_dual_read_projection_mismatch_audits(
    db: AsyncSession,
    *,
    phase_a: SituationPackRepository,
    phase_b1: SituationPackRepository,
) -> int:
    """Persist current Phase A/B1 hash mismatches for HITL promotion queries."""

    phase_a_by_code = _packs_by_code(phase_a.list_all())
    phase_b1_by_code = _packs_by_code(phase_b1.list_all())
    mismatch_count = 0
    for code in sorted(set(phase_a_by_code) | set(phase_b1_by_code)):
        phase_a_hash = _pack_hash(phase_a_by_code.get(code))
        phase_b1_hash = _pack_hash(phase_b1_by_code.get(code))
        if phase_a_hash == phase_b1_hash:
            continue
        mismatch_count += 1
        details = {
            "code": code,
            "scope": "repository_load",
            "phase_a_hash": phase_a_hash,
            "phase_b1_hash": phase_b1_hash,
            "trace_id": get_trace_id(),
        }
        db.add(
            SystemLog(
                action=DUAL_READ_MISMATCH_ACTION,
                user_identifier="system",
                status="warning",
                details=json.dumps(details, ensure_ascii=False, default=str),
            )
        )
    if mismatch_count > 0:
        await db.flush()
    return mismatch_count


def build_default_promotion_gate_payload() -> dict[str, object]:
    now = datetime.now(UTC)
    decision = DualReadPromotionGateDecision(
        requested_b1_authority=settings.SITUATION_PACK_B1_AUTHORITY,
        authority="phase_a",
        promotion_ready=False,
        blocked_reasons=[],
        approval_id=settings.SITUATION_PACK_B1_APPROVAL_ID or None,
        window_start=now - timedelta(days=PROMOTION_WINDOW_DAYS),
        window_end=now,
    )
    return decision.to_payload()


def _packs_by_code(
    packs: Iterable[SituationPackDTO],
) -> dict[str, SituationPackDTO]:
    return {item.code: item for item in packs}


def _pack_hash(pack: SituationPackDTO | None) -> str | None:
    return situation_pack_content_hash(pack) if pack is not None else None


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
