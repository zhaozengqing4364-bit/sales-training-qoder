from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.services.roleplay.dual_read_observability import (
    build_config_asset_center_overview_payload,
)
from curriculum_practice.services.roleplay.dual_read_promotion_gate import (
    DualReadPromotionGateService,
)
from curriculum_practice.services.roleplay_contracts import (
    ROLEPLAY_COMPLIANCE_METRICS_KEY,
    roleplay_compliance_summary_from_session,
)
from support.services.runtime_contributors import (
    register_config_asset_center_contributor,
    register_roleplay_diagnostics_contributor,
)

CURRICULUM_PRACTICE_CONFIG_ASSET_CENTER_CONTRIBUTOR = (
    "curriculum_practice.config_asset_center"
)
CURRICULUM_PRACTICE_ROLEPLAY_DIAGNOSTICS_CONTRIBUTOR = (
    "curriculum_practice.roleplay_diagnostics"
)


async def build_curriculum_practice_config_asset_center(
    db: AsyncSession,
    now: datetime,
) -> dict[str, object]:
    promotion_gate = await DualReadPromotionGateService(db).evaluate(
        write_audit=False,
        now=now,
    )
    return build_config_asset_center_overview_payload(
        promotion_gate=promotion_gate.to_payload()
    )


def build_curriculum_practice_roleplay_diagnostics(
    session: Any,
    voice_policy_snapshot: dict[str, Any],
) -> dict[str, Any]:
    runtime_state = getattr(session, "runtime_state", None)
    curriculum_snapshot = getattr(session, "curriculum_snapshot", None)
    summary = roleplay_compliance_summary_from_session(
        curriculum_snapshot=curriculum_snapshot,
        voice_policy_snapshot=voice_policy_snapshot,
        runtime_state=runtime_state,
    )
    runtime_metrics = (
        voice_policy_snapshot.get("runtime_metrics")
        if isinstance(voice_policy_snapshot, dict)
        else None
    )
    roleplay_metrics = (
        runtime_metrics.get(ROLEPLAY_COMPLIANCE_METRICS_KEY)
        if isinstance(runtime_metrics, dict)
        else None
    )
    if not isinstance(roleplay_metrics, dict):
        roleplay_metrics = {}
    config_asset_runtime = (
        summary.get("config_asset_runtime")
        if isinstance(summary.get("config_asset_runtime"), dict)
        else {}
    )
    return {
        "summary": summary,
        "asset_resolution": summary.get("asset_resolution"),
        "config_asset_runtime": config_asset_runtime,
        "timeline_count": len(roleplay_metrics.get("timeline") or [])
        if isinstance(roleplay_metrics.get("timeline"), list)
        else 0,
    }


def register_curriculum_practice_support_runtime_contributors() -> None:
    register_config_asset_center_contributor(
        CURRICULUM_PRACTICE_CONFIG_ASSET_CENTER_CONTRIBUTOR,
        build_curriculum_practice_config_asset_center,
    )
    register_roleplay_diagnostics_contributor(
        CURRICULUM_PRACTICE_ROLEPLAY_DIAGNOSTICS_CONTRIBUTOR,
        build_curriculum_practice_roleplay_diagnostics,
    )
