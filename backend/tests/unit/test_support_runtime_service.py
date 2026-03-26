from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from support.services.runtime_status_service import (
    RuntimeSessionRecord,
    RuntimeStatusService,
)


def _make_effectiveness_snapshot(
    *,
    evaluable: bool,
    not_evaluable_reason: str | None = None,
) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": evaluable,
            "pass_5turn_defense": evaluable,
            "pass_4step_structure": evaluable,
        },
        "main_capability_passed": evaluable,
        "overall_result": "pass" if evaluable else "fail",
        "metrics": {
            "continuous_speech_seconds": 180.0 if evaluable else 0.0,
            "filler_rate_per_100_words": 4.0,
            "offtopic_turn_count": 0.0,
            "offtopic_max_streak": 0.0,
            "structure_coverage": 0.9 if evaluable else 0.0,
        },
        "main_issue": {
            "issue_type": "insufficient_turn_data"
            if not evaluable
            else "main_capability_not_passed",
            "issue_text": "当前互动不足，暂时无法评估。"
            if not evaluable
            else "继续保持。",
            "recovery_rule": "补齐有效互动后再结束。"
            if not evaluable
            else "保持当前节奏。",
        },
        "next_goal": {
            "goal_type": "collect_more_evidence"
            if not evaluable
            else "main_capability_focus",
            "goal_text": "先补齐有效互动，再继续诊断。"
            if not evaluable
            else "维持当前表现。",
            "rule": "至少完成 1 次往返对话。"
            if not evaluable
            else "继续按当前节奏推进。",
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": not_evaluable_reason,
    }


def _make_session(
    *,
    status: str,
    start_time: datetime,
    scenario_type: str,
    logic_score: float | None = 82.0,
    accuracy_score: float | None = 84.0,
    completeness_score: float | None = 86.0,
    end_time: datetime | None = None,
    report_status: str = "completed",
    report_error: str | None = None,
    effectiveness_snapshot: dict[str, object] | None = None,
) -> SimpleNamespace:
    scenario = SimpleNamespace(scenario_type=scenario_type, name=f"{scenario_type}-scenario")
    return SimpleNamespace(
        session_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        scenario_id=str(uuid.uuid4()),
        scenario=scenario,
        presentation_id=str(uuid.uuid4()) if scenario_type == "presentation" else None,
        status=status,
        start_time=start_time,
        end_time=end_time,
        total_duration_seconds=300 if status == "completed" else None,
        logic_score=logic_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        voice_mode="stepfun_realtime",
        voice_policy_snapshot=None,
        effectiveness_snapshot=effectiveness_snapshot,
        report_status=report_status,
        report_error=report_error,
        report_generated_at=end_time,
    )


def _make_record(
    *,
    session: SimpleNamespace,
    knowledge_diagnostics: dict[str, object] | None = None,
    projection: object | None = None,
    projection_error: str | None = None,
    presentation_review: dict[str, object] | None = None,
) -> RuntimeSessionRecord:
    return RuntimeSessionRecord(
        session=session,
        scenario_type=session.scenario.scenario_type,
        voice_policy_snapshot={},
        knowledge_diagnostics=knowledge_diagnostics or {},
        projection=projection,
        projection_error=projection_error,
        presentation_review=presentation_review,
    )


def test_build_fault_items_classifies_blocking_and_warning_release_anomalies() -> None:
    now = datetime(2026, 3, 24, 12, 0, tzinfo=UTC)

    stuck_scoring_session = _make_session(
        status="scoring",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=35),
        scenario_type="sales",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        report_status="processing",
    )
    projection_failed_session = _make_session(
        status="completed",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=2, minutes=-5),
        scenario_type="sales",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        report_status="completed",
    )
    not_evaluable_session = _make_session(
        status="completed",
        start_time=now - timedelta(hours=3),
        end_time=now - timedelta(hours=3, minutes=-4),
        scenario_type="sales",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=False,
            not_evaluable_reason="INSUFFICIENT_TURN_DATA",
        ),
    )
    kb_locked_session = _make_session(
        status="completed",
        start_time=now - timedelta(hours=4),
        end_time=now - timedelta(hours=4, minutes=-6),
        scenario_type="sales",
    )
    upstream_unstable_session = _make_session(
        status="completed",
        start_time=now - timedelta(hours=5),
        end_time=now - timedelta(hours=5, minutes=-7),
        scenario_type="sales",
    )
    presentation_degraded_session = _make_session(
        status="completed",
        start_time=now - timedelta(hours=6),
        end_time=now - timedelta(hours=6, minutes=-8),
        scenario_type="presentation",
        report_status="failed",
        report_error="[REPORT_GENERATION_FAILED]",
    )

    records = [
        _make_record(session=stuck_scoring_session),
        _make_record(
            session=projection_failed_session,
            projection_error="[SESSION_EVIDENCE_FAILED] projection exploded",
        ),
        _make_record(
            session=not_evaluable_session,
            knowledge_diagnostics={
                "status": "search_failed",
                "summary": "知识检索触发失败，请检查知识库或 Embedding 服务",
                "last_status": "search_failed",
                "last_error": "[KNOWLEDGE_SEARCH_UNAVAILABLE]",
                "kb_lock_required": False,
                "kb_lock_status": "pass",
                "upstream_unstable": False,
                "updated_at": (now - timedelta(hours=3)).isoformat(),
            },
            projection=SimpleNamespace(
                evaluable=False,
                not_evaluable_reason="INSUFFICIENT_TURN_DATA",
            ),
        ),
        _make_record(
            session=kb_locked_session,
            knowledge_diagnostics={
                "status": "kb_not_ready",
                "summary": "知识库文档尚未处理完成",
                "last_status": "kb_not_ready",
                "last_error": "",
                "kb_lock_required": True,
                "kb_lock_status": "blocked_not_ready",
                "upstream_unstable": False,
                "updated_at": (now - timedelta(hours=4)).isoformat(),
            },
            projection=SimpleNamespace(evaluable=True, not_evaluable_reason=None),
        ),
        _make_record(
            session=upstream_unstable_session,
            knowledge_diagnostics={
                "status": "hit",
                "summary": "知识检索已触发并命中知识库",
                "last_status": "hit",
                "last_error": "",
                "kb_lock_required": False,
                "kb_lock_status": "pass",
                "upstream_disconnect_count_5m": 4,
                "upstream_unstable": True,
                "updated_at": (now - timedelta(hours=5)).isoformat(),
            },
            projection=SimpleNamespace(evaluable=True, not_evaluable_reason=None),
        ),
        _make_record(
            session=presentation_degraded_session,
            projection=SimpleNamespace(evaluable=None, not_evaluable_reason=None),
            presentation_review={
                "diagnostics": {"degraded_reasons": ["missing_page_metadata"]}
            },
        ),
    ]

    payload = RuntimeStatusService.build_faults_payload(
        records,
        now=now,
        limit=20,
        supplemental_logs=[],
    )

    assert payload["count"] == len(payload["items"])
    by_kind = {item["kind"]: item for item in payload["items"]}

    assert by_kind["stuck_scoring"]["severity"] == "blocking"
    assert by_kind["stuck_scoring"]["session_id"] == stuck_scoring_session.session_id

    assert by_kind["projection_failed"]["severity"] == "blocking"
    assert "projection" in by_kind["projection_failed"]["summary"]

    assert by_kind["knowledge_search_failed"]["severity"] == "blocking"
    assert by_kind["knowledge_search_failed"]["diagnostics"]["last_status"] == "search_failed"

    assert by_kind["not_evaluable_completed"]["severity"] == "blocking"
    assert (
        by_kind["not_evaluable_completed"]["diagnostics"]["not_evaluable_reason"]
        == "INSUFFICIENT_TURN_DATA"
    )

    assert by_kind["kb_lock_blocked_not_ready"]["severity"] == "blocking"
    assert by_kind["kb_lock_blocked_not_ready"]["summary"].startswith("知识库锁阻塞")

    assert by_kind["upstream_unstable"]["severity"] == "warning"
    assert by_kind["upstream_unstable"]["diagnostics"]["upstream_disconnect_count_5m"] == 4

    assert (
        by_kind["presentation_degraded_missing_page_metadata"]["severity"]
        == "warning"
    )
    assert by_kind["optional_report_failed"]["severity"] == "warning"


def test_build_overview_payload_tracks_scoring_separately_from_completed() -> None:
    now = datetime(2026, 3, 24, 12, 0, tzinfo=UTC)

    completed_session = _make_session(
        status="completed",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=2, minutes=-5),
        scenario_type="sales",
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=True,
            not_evaluable_reason=None,
        ),
    )
    short_scoring_session = _make_session(
        status="scoring",
        start_time=now - timedelta(minutes=25),
        end_time=now - timedelta(minutes=2),
        scenario_type="sales",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        report_status="processing",
    )
    stuck_scoring_session = _make_session(
        status="scoring",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=35),
        scenario_type="sales",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        report_status="processing",
    )

    records = [
        _make_record(
            session=completed_session,
            projection=SimpleNamespace(evaluable=True, not_evaluable_reason=None),
        ),
        _make_record(session=short_scoring_session),
        _make_record(session=stuck_scoring_session),
    ]

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

    assert overview["session_health"] == {
        "active_sessions": 0,
        "total_sessions_window": 3,
        "completed_sessions_window": 1,
        "scoring_sessions": 2,
        "stuck_scoring_sessions": 1,
        "not_evaluable_completed_sessions_window": 0,
        "completion_rate": pytest.approx(33.33),
    }
    assert overview["release_health"]["status"] == "blocking"
    assert overview["release_health"]["blocking_count"] == 1
    assert overview["release_health"]["warning_count"] == 0
    assert overview["anomaly_summary"]["blocking"] == [{"kind": "stuck_scoring", "count": 1}]
    assert overview["anomaly_summary"]["warning"] == []
