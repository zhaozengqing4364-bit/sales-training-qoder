from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from sales_trainer.services.journey_sqlalchemy_adapter import (
    SqlAlchemyJourneyReadRepository,
)


def _learner(
    learner_id: str,
    *,
    role: str = "user",
    is_active: bool = True,
) -> User:
    return User(
        user_id=learner_id,
        wechat_user_id=f"journey-repository-{learner_id}",
        name=f"Learner {learner_id}",
        role=role,
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_journey_repository_returns_frozen_learner_or_none(
    test_db: AsyncSession,
) -> None:
    learner = _learner("learner-found")
    test_db.add(learner)
    await test_db.commit()

    repository = SqlAlchemyJourneyReadRepository(test_db)
    projection = await repository.learner("learner-found")

    assert projection is not None
    assert projection.learner_id == "learner-found"
    assert await repository.learner("learner-missing") is None
    with pytest.raises(FrozenInstanceError):
        projection.name = "mutated"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_journey_repository_applies_authorized_ids_active_and_role_scope(
    test_db: AsyncSession,
) -> None:
    test_db.add_all(
        [
            _learner("active-a"),
            _learner("active-b"),
            _learner("inactive", is_active=False),
            _learner("outside-authorized-scope"),
            _learner("foreign-role", role="admin"),
        ]
    )
    await test_db.commit()
    repository = SqlAlchemyJourneyReadRepository(test_db)

    page = await repository.learners(
        learner_ids=frozenset({"active-a", "active-b", "inactive", "foreign-role"}),
        limit=None,
        include_development_admin=False,
    )
    blocked = await repository.learners(
        learner_ids=frozenset(),
        limit=None,
        include_development_admin=False,
    )

    assert {item.learner_id for item in page.items} == {"active-a", "active-b"}
    assert page.total == 2
    assert blocked.items == ()
    assert blocked.total == 0


@pytest.mark.asyncio
async def test_journey_repository_returns_ordered_recursively_frozen_sessions(
    test_db: AsyncSession,
) -> None:
    learner = _learner("roleplay-learner")
    scenario = Scenario(
        scenario_id="journey-repository-scenario",
        scenario_type="sales",
        name="场景",
    )
    sessions = [
        PracticeSession(
            session_id=session_id,
            user_id=str(learner.user_id),
            scenario_id=str(scenario.scenario_id),
            voice_mode="stepfun_realtime",
            voice_policy_snapshot={
                "external_binding": {
                    "owner": "sales_trainer",
                    "path_revision_id": "revision-1",
                },
                "signals": ["stable"],
            },
        )
        for session_id in ("z-session", "a-session")
    ]
    test_db.add_all([learner, scenario, *sessions])
    await test_db.commit()

    repository = SqlAlchemyJourneyReadRepository(test_db)
    projections = await repository.roleplay_sessions(
        learner_ids=frozenset({"roleplay-learner"})
    )

    assert [item.session_id for item in projections] == ["a-session", "z-session"]
    binding = projections[0].voice_policy_snapshot["external_binding"]
    assert isinstance(binding, Mapping)
    with pytest.raises(TypeError):
        binding["owner"] = "mutated"  # type: ignore[index]
    assert projections[0].voice_policy_snapshot["signals"] == ("stable",)
