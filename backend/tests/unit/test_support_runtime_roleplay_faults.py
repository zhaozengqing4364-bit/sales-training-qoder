from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from support.services.runtime_status_service import (
    RuntimeSessionRecord,
    RuntimeStatusService,
)


def _make_session(*, now: datetime) -> SimpleNamespace:
    scenario = SimpleNamespace(scenario_type="sales", name="sales-scenario")
    return SimpleNamespace(
        session_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        scenario_id=str(uuid.uuid4()),
        scenario=scenario,
        presentation_id=None,
        status="completed",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=50),
        total_duration_seconds=600,
        logic_score=82.0,
        accuracy_score=84.0,
        completeness_score=86.0,
        voice_mode="stepfun_realtime",
        voice_policy_snapshot=None,
        effectiveness_snapshot=None,
        report_status="completed",
        report_error=None,
        report_generated_at=now - timedelta(minutes=45),
    )


def _make_record(
    *,
    session: SimpleNamespace,
    roleplay_status: str,
) -> RuntimeSessionRecord:
    return RuntimeSessionRecord(
        session=session,
        scenario_type="sales",
        voice_policy_snapshot={},
        knowledge_diagnostics={},
        projection=SimpleNamespace(evaluable=True, not_evaluable_reason=None),
        roleplay_diagnostics={
            "summary": {
                "status": roleplay_status,
                "situation_code": None,
                "violation_count": 0,
                "blocking_violation_count": 0,
            }
        },
    )


def test_roleplay_contract_missing_is_summary_only_not_release_fault() -> None:
    now = datetime(2026, 6, 4, 10, 45, tzinfo=UTC)
    session = _make_session(now=now)
    records = [_make_record(session=session, roleplay_status="missing")]

    faults = RuntimeStatusService.build_faults_payload(
        records,
        now=now,
        limit=20,
        supplemental_logs=[],
    )
    overview = RuntimeStatusService.build_overview_payload(
        records,
        fault_items=faults["items"],
        now=now,
        window_hours=24,
        supplemental_logs=[],
    )

    fault_kinds = {item["kind"] for item in faults["items"]}
    assert "roleplay_contract_missing" not in fault_kinds
    assert overview["release_health"]["blocking_count"] == 0
    assert overview["roleplay"]["missing_sessions"] == 1
