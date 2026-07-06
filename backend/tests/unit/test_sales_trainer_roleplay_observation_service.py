from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from common.monitoring.logger import REDACTED_VALUE, sanitize_log_kwargs
from sales_trainer.schemas import SalesTrainerRoleplayObservationWrite
from sales_trainer.services.roleplay_observation_service import (
    RoleplayObservationService,
    resolve_roleplay_observation_policy,
)


def _user(role: str = "user", *, department: str | None = "销售一部") -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"roleplay-observation-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Roleplay Observation {role}",
        email=f"roleplay-observation-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        department=department,
    )


def _scenario() -> Scenario:
    return Scenario(
        scenario_id=str(uuid.uuid4()),
        name="新人实时对练",
        description="新人实时对练",
        scenario_type="sales",
    )


def _session(learner: User, scenario: Scenario) -> PracticeSession:
    return PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=scenario.scenario_id,
        voice_mode="stepfun_realtime",
        status="completed",
        start_time=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 2, 10, 12, tzinfo=UTC),
        voice_policy_snapshot={
            "external_binding": {
                "owner": "sales_trainer",
                "path_key": "newcomer_training_path_v1",
                "path_revision_id": "path-rev-001",
                "path_revision_no": 1,
                "module_key": "realtime_roleplay",
                "binding_key": "newcomer_realtime_roleplay_v1",
            }
        },
    )


def test_should_resolve_default_roleplay_observation_policy_when_snapshot_missing() -> (
    None
):
    resolution = resolve_roleplay_observation_policy(None)

    assert resolution.source == "default"
    assert resolution.fallback_applied is False
    assert resolution.policy.heuristic.enabled is True
    assert resolution.policy.llm.enabled is False


def test_should_merge_roleplay_observation_policy_override_from_snapshot() -> None:
    resolution = resolve_roleplay_observation_policy(
        {
            "roleplay_observation_policy": {
                "llm": {
                    "enabled": True,
                    "model_name": "observer-model",
                    "timeout_seconds": 7.5,
                }
            }
        }
    )

    assert resolution.source == "snapshot"
    assert resolution.fallback_applied is False
    assert resolution.policy.heuristic.enabled is True
    assert resolution.policy.llm.enabled is True
    assert resolution.policy.llm.model_name == "observer-model"
    assert resolution.policy.llm.timeout_seconds == 7.5


@pytest.mark.asyncio
async def test_should_append_roleplay_observation_idempotently(
    test_db: AsyncSession,
) -> None:
    learner = _user()
    scenario = _scenario()
    session = _session(learner, scenario)
    test_db.add_all([learner, scenario, session])
    await test_db.commit()

    service = RoleplayObservationService(test_db)
    payload = SalesTrainerRoleplayObservationWrite(
        session_id=session.session_id,
        source="heuristic",
        turn_index=1,
        evaluator_status="completed",
        dimensions=[{"key": "discovery", "score": 82.0}],
        signals=[{"signal_type": "knowledge_gap", "value": "low"}],
    )

    first = await service.append_observation(payload)
    second = await service.append_observation(payload)
    summary = await service.get_session_summary(session_id=session.session_id)

    assert first.stored is True
    assert first.deduplicated is False
    assert first.observation_id is not None
    assert second.stored is True
    assert second.deduplicated is True
    assert second.observation_id == first.observation_id
    assert summary["total"] == 1
    assert summary["source_counts"]["heuristic"] == 1
    assert summary["status_counts"]["completed"] == 1
    assert summary["items"][0]["turn_index"] == 1


@pytest.mark.asyncio
async def test_should_sanitize_sensitive_observation_payload_before_store(
    test_db: AsyncSession,
) -> None:
    learner = _user()
    scenario = _scenario()
    session = _session(learner, scenario)
    test_db.add_all([learner, scenario, session])
    await test_db.commit()

    service = RoleplayObservationService(test_db)
    payload = SalesTrainerRoleplayObservationWrite(
        session_id=session.session_id,
        source="heuristic",
        turn_index=2,
        evaluator_status="completed",
        dimensions=[
            {
                "key": "instruction_boundary",
                "api_key": "sk-should-not-store",
                "metadata": {
                    "authorization": "Bearer should-not-store",
                    "safe_note": "Authorization: Bearer should-not-store",
                },
            }
        ],
        signals=[
            {
                "signal_type": "prompt_leak_risk",
                "value": "system prompt: should-not-store",
                "payload": {"cookie": "session=should-not-store"},
                "jwt_sample": (
                    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJub3Qtc2FmZSJ9."
                    "abcdabcdabcdabcd"
                ),
            }
        ],
        error={
            "code": "[LLM_EVALUATOR_FAILED]",
            "message": "secret=should-not-store",
            "thinking": "should-not-store",
        },
    )

    result = await service.append_observation(payload)
    summary = await service.get_session_summary(session_id=session.session_id)
    encoded = json.dumps(summary, ensure_ascii=False, default=str).lower()

    assert result.stored is True
    assert "should-not-store" not in encoded
    assert "api_key" not in encoded
    assert "authorization" not in encoded
    assert "cookie" not in encoded
    assert "thinking" not in encoded
    assert "<redacted" in encoded
    assert summary["items"][0]["dimensions"][0]["metadata"]["safe_note"].endswith(
        "<redacted>"
    )


def test_should_redact_extended_sensitive_log_markers() -> None:
    sanitized = sanitize_log_kwargs(
        {
            "api_key": "key",
            "apikey": "key",
            "secret": "secret",
            "authorization": "Bearer token",
            "bearer": "token",
            "nested": {"Authorization": "Bearer nested"},
        }
    )

    assert sanitized["api_key"] == REDACTED_VALUE
    assert sanitized["apikey"] == REDACTED_VALUE
    assert sanitized["secret"] == REDACTED_VALUE
    assert sanitized["authorization"] == REDACTED_VALUE
    assert sanitized["bearer"] == REDACTED_VALUE
    assert sanitized["nested"]["Authorization"] == REDACTED_VALUE


@pytest.mark.asyncio
async def test_should_aggregate_heuristic_and_llm_observations_by_session(
    test_db: AsyncSession,
) -> None:
    learner = _user()
    scenario = _scenario()
    session = _session(learner, scenario)
    test_db.add_all([learner, scenario, session])
    await test_db.commit()

    service = RoleplayObservationService(test_db)
    heuristic = SalesTrainerRoleplayObservationWrite(
        session_id=session.session_id,
        source="heuristic",
        turn_index=1,
        evaluator_status="completed",
        dimensions=[{"name": "推进下一步", "score": 76.0}],
        signals=[{"signal_type": "quality_flag", "value": "knowledge_gap_degradation"}],
    )
    llm = SalesTrainerRoleplayObservationWrite(
        session_id=session.session_id,
        source="llm_evaluator",
        turn_index=2,
        evaluator_status="failed",
        dimensions=[],
        signals=[{"signal_type": "manual_review_required", "value": True}],
        error={"code": "[LLM_EVALUATOR_TIMEOUT]", "message": "LLM evaluator timed out"},
    )

    await service.append_observation(heuristic)
    await service.append_observation(llm)
    summary = await service.get_session_summary(session_id=session.session_id)

    assert summary["session_id"] == session.session_id
    assert summary["source_record_id"] == session.session_id
    assert summary["total"] == 2
    assert summary["latest_turn_index"] == 2
    assert summary["source_counts"] == {"heuristic": 1, "llm_evaluator": 1}
    assert summary["status_counts"]["completed"] == 1
    assert summary["status_counts"]["failed"] == 1
    assert summary["items"][0]["source"] == "heuristic"
    assert summary["items"][1]["source"] == "llm_evaluator"
    assert summary["items"][1]["error"]["code"] == "[LLM_EVALUATOR_TIMEOUT]"


@pytest.mark.asyncio
async def test_should_allow_non_blocking_store_failure_without_poisoning_main_flow(
    test_db: AsyncSession,
) -> None:
    learner = _user()
    scenario = _scenario()
    session = _session(learner, scenario)
    test_db.add_all([learner, scenario, session])
    await test_db.commit()

    service = RoleplayObservationService(test_db)

    failed = await service.append_observation(
        SalesTrainerRoleplayObservationWrite(
            session_id=str(uuid.uuid4()),
            source="heuristic",
            turn_index=1,
            evaluator_status="completed",
            dimensions=[{"key": "discovery", "score": 70.0}],
        ),
        non_blocking=True,
    )
    stored = await service.append_observation(
        SalesTrainerRoleplayObservationWrite(
            session_id=session.session_id,
            source="heuristic",
            turn_index=3,
            evaluator_status="completed",
            dimensions=[{"key": "closing", "score": 88.0}],
        )
    )
    summary = await service.get_session_summary(session_id=session.session_id)

    assert failed.stored is False
    assert failed.error_code == "[ROLEPLAY_OBSERVATION_SESSION_NOT_FOUND]"
    assert stored.stored is True
    assert stored.observation_id is not None
    assert summary["total"] == 1
    assert summary["items"][0]["turn_index"] == 3
