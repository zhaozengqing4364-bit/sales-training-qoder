from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from common.services.session_runtime_repair_service import (
    SessionRuntimeRepairService,
)


class _FakeRuntimePolicyService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def resolve_effective_policy(
        self,
        *,
        agent_id: str | None = None,
        persona_id: str | None = None,
        voice_mode_override: str | None = None,
        runtime_profile_override: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "agent_id": agent_id,
                "persona_id": persona_id,
                "voice_mode_override": voice_mode_override,
                "runtime_profile_override": runtime_profile_override,
            }
        )
        return {
            "agent_id": agent_id,
            "persona_id": persona_id,
            "runtime_profile_id": runtime_profile_override or "profile-repaired",
            "voice_mode": voice_mode_override or "stepfun_realtime",
            "instructions": "repaired instructions",
            "instruction_contract_hash": "sha256:repaired",
        }


async def _seed_user_and_scenario(
    db: AsyncSession,
    *,
    scenario_type: str = "sales",
) -> tuple[User, Scenario]:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"runtime_repair_{uuid.uuid4().hex[:8]}",
        name="Runtime Repair User",
        role="user",
        is_active=True,
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type=scenario_type,
        name=f"runtime repair {scenario_type}",
        is_active=True,
    )
    db.add_all([user, scenario])
    await db.commit()
    return user, scenario


@pytest.mark.asyncio
async def test_runtime_repair_dry_run_reports_missing_voice_snapshot_without_mutation(
    test_db: AsyncSession,
) -> None:
    user, scenario = await _seed_user_and_scenario(test_db)
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="in_progress",
        agent_id="agent-1",
        persona_id="persona-1",
        voice_runtime_profile_id="profile-1",
        voice_policy_snapshot=None,
    )
    test_db.add(session)
    await test_db.commit()

    fake_policy = _FakeRuntimePolicyService()
    result = await SessionRuntimeRepairService(
        test_db,
        runtime_policy_service=fake_policy,  # type: ignore[arg-type]
    ).run(session_ids=[session.session_id])

    assert result.dry_run is True
    assert result.repaired_sessions == 0
    assert [finding.code for finding in result.findings] == [
        "VOICE_POLICY_SNAPSHOT_MISSING"
    ]
    assert session.voice_policy_snapshot is None
    assert fake_policy.calls == []


@pytest.mark.asyncio
async def test_runtime_repair_apply_rebuilds_missing_voice_snapshot_explicitly(
    test_db: AsyncSession,
) -> None:
    user, scenario = await _seed_user_and_scenario(test_db)
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="paused",
        agent_id="agent-1",
        persona_id="persona-1",
        voice_runtime_profile_id="profile-1",
        voice_policy_snapshot=None,
    )
    test_db.add(session)
    await test_db.commit()

    fake_policy = _FakeRuntimePolicyService()
    result = await SessionRuntimeRepairService(
        test_db,
        runtime_policy_service=fake_policy,  # type: ignore[arg-type]
    ).run(apply=True, session_ids=[session.session_id])

    assert result.dry_run is False
    assert result.repaired_sessions == 1
    assert session.voice_policy_snapshot is not None
    assert session.voice_policy_snapshot["instruction_contract_hash"] == "sha256:repaired"
    assert fake_policy.calls == [
        {
            "agent_id": "agent-1",
            "persona_id": "persona-1",
            "voice_mode_override": "stepfun_realtime",
            "runtime_profile_override": "profile-1",
        }
    ]


@pytest.mark.asyncio
async def test_runtime_repair_aligns_session_identity_to_frozen_curriculum_runtime(
    test_db: AsyncSession,
) -> None:
    user, scenario = await _seed_user_and_scenario(test_db)
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="in_progress",
        agent_id="agent-live",
        persona_id="persona-live",
        voice_runtime_profile_id="profile-live",
        voice_policy_snapshot={"instruction_contract_hash": "sha256:old"},
        curriculum_snapshot={
            "runtime": {
                "agent_id": "agent-frozen",
                "persona_id": "persona-frozen",
                "runtime_profile_id": "profile-frozen",
            }
        },
    )
    test_db.add(session)
    await test_db.commit()

    result = await SessionRuntimeRepairService(test_db).run(
        apply=True,
        session_ids=[session.session_id],
    )

    assert result.repaired_sessions == 1
    assert [finding.code for finding in result.findings] == [
        "CURRICULUM_RUNTIME_IDENTITY_MISMATCH"
    ]
    assert session.agent_id == "agent-frozen"
    assert session.persona_id == "persona-frozen"
    assert session.voice_runtime_profile_id == "profile-frozen"
    assert session.curriculum_snapshot["runtime"]["agent_id"] == "agent-frozen"


@pytest.mark.asyncio
async def test_runtime_repair_does_not_recreate_missing_curriculum_runtime_from_live_template(
    test_db: AsyncSession,
) -> None:
    user, scenario = await _seed_user_and_scenario(test_db)
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status="preparing",
        agent_id="agent-1",
        persona_id="persona-1",
        voice_policy_snapshot={"instruction_contract_hash": "sha256:stable"},
        curriculum_snapshot={"practice_template": {"asset_id": "template-1"}},
    )
    test_db.add(session)
    await test_db.commit()

    result = await SessionRuntimeRepairService(test_db).run(
        apply=True,
        session_ids=[session.session_id],
    )

    assert result.repaired_sessions == 0
    assert [finding.code for finding in result.findings] == [
        "CURRICULUM_RUNTIME_MISSING"
    ]
    assert result.findings[0].repairable is False
    assert session.curriculum_snapshot == {"practice_template": {"asset_id": "template-1"}}
