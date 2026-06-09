from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class RoleplayFaultCandidate:
    severity: str
    kind: str
    summary: str
    detected_at: datetime | str | None
    diagnostics: dict[str, Any]


def build_roleplay_fault_candidate(
    *,
    roleplay_diagnostics: dict[str, Any],
    session_started_at: datetime | str | None,
    session_finished_at: datetime | str | None,
) -> RoleplayFaultCandidate | None:
    raw_summary = roleplay_diagnostics.get("summary")
    summary = raw_summary if isinstance(raw_summary, dict) else {}
    roleplay_status = str(summary.get("status") or "")
    blocking_roleplay_count = int(summary.get("blocking_violation_count") or 0)

    match roleplay_status:
        case "missing":
            return None
        case "invalid":
            return RoleplayFaultCandidate(
                severity="blocking",
                kind="roleplay_contract_invalid",
                summary="Roleplay Contract 非法，角色一致性运行时只能降级诊断。",
                detected_at=session_started_at,
                diagnostics={"roleplay": summary},
            )
        case "legacy":
            return RoleplayFaultCandidate(
                severity="warning",
                kind="roleplay_contract_legacy",
                summary="会话使用 legacy Roleplay Contract，无法完整执行情景边界守门。",
                detected_at=session_started_at,
                diagnostics={"roleplay": summary},
            )
        case _:
            if blocking_roleplay_count <= 0:
                return None
            return RoleplayFaultCandidate(
                severity="warning",
                kind="roleplay_blocking_violation",
                summary="会话触发 Roleplay Contract 阻断级违规，已由运行时守门修复或标记。",
                detected_at=summary.get("last_action_at")
                or session_finished_at
                or session_started_at,
                diagnostics={"roleplay": summary},
            )
