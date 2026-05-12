from __future__ import annotations

import uuid
from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.integration.test_curriculum_practice_session_snapshot import (
    _create_published_template,
    _seed_runtime_entities,
)

from common.db.models import PracticeSession, Scenario, User
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.services.session_snapshots import (
    apply_curriculum_snapshot_to_session,
)


@pytest.mark.asyncio
async def test_should_keep_session_curriculum_snapshot_immutable_after_template_v2_publish(
    test_db: AsyncSession,
) -> None:
    agent, persona, runtime_profile, ruleset, knowledge_base = await _seed_runtime_entities(
        test_db
    )
    template = await _create_published_template(
        test_db,
        agent=agent,
        persona=persona,
        runtime_profile=runtime_profile,
        ruleset=ruleset,
        knowledge_base=knowledge_base,
    )
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="snapshot_immutability_user",
        name="Snapshot Immutability User",
        role="user",
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="snapshot_immutability_sales",
        is_active=True,
    )
    session = PracticeSession(
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        agent_id=agent.id,
        persona_id=persona.id,
        voice_mode="stepfun_realtime",
        status="preparing",
    )
    test_db.add_all([user, scenario, session])
    await test_db.flush()

    await apply_curriculum_snapshot_to_session(
        db=test_db,
        session=session,
        practice_template_id=UUID(str(template.template_id)),
        scenario_type_value="sales",
        actor_id=str(user.user_id),
    )
    await test_db.commit()
    session_id = session.session_id
    original_snapshot = deepcopy(session.curriculum_snapshot)

    stored_template = await test_db.get(PracticeTemplate, template.template_id)
    assert stored_template is not None
    stored_template.name = "课程化客户异议训练 v2"
    stored_template.description = "template v2 should not rewrite old sessions"
    stored_template.version = 2
    stored_template.content_hash = "sha256:template-v2"
    stored_template.status = "published"
    await test_db.commit()

    refreshed = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
    ).scalar_one()

    assert refreshed.curriculum_snapshot == original_snapshot
    assert refreshed.curriculum_snapshot["practice_template"] == original_snapshot[
        "practice_template"
    ]
