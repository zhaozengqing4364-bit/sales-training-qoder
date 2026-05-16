from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.services.learner_profiles import LearnerProfileService


@pytest.mark.asyncio
async def test_should_return_conservative_default_level_when_profile_missing(
    test_db: AsyncSession,
) -> None:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="learner_default_user",
        name="Learner Default User",
        role="user",
    )
    test_db.add(user)
    await test_db.commit()

    result = await LearnerProfileService(test_db).get_or_create_for_user(user.user_id)

    assert result.is_success is True
    assert result.value is not None
    assert result.value.user_id == user.user_id
    assert result.value.self_assessed_level is None
    assert result.value.admin_overridden_level is None
    assert result.value.effective_level == "conservative"


@pytest.mark.asyncio
async def test_should_use_first_self_assessment_as_effective_level(
    test_db: AsyncSession,
) -> None:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="learner_self_assessment_user",
        name="Learner Self Assessment User",
        role="user",
    )
    test_db.add(user)
    await test_db.commit()

    result = await LearnerProfileService(test_db).record_self_assessment(
        user.user_id, "intermediate"
    )

    assert result.is_success is True
    assert result.value is not None
    assert result.value.self_assessed_level == "intermediate"
    assert result.value.effective_level == "intermediate"
    assert result.value.self_assessed_at is not None


@pytest.mark.asyncio
async def test_should_keep_admin_override_as_effective_level_after_self_assessment(
    test_db: AsyncSession,
) -> None:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="learner_override_user",
        name="Learner Override User",
        role="user",
    )
    admin = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="learner_override_admin",
        name="Learner Override Admin",
        role="admin",
    )
    test_db.add_all([user, admin])
    await test_db.commit()

    override = await LearnerProfileService(test_db).apply_admin_override(
        user.user_id, "beginner", actor_id=admin.user_id
    )
    reassessment = await LearnerProfileService(test_db).record_self_assessment(
        user.user_id, "advanced"
    )

    assert override.is_success is True
    assert reassessment.is_success is True
    assert reassessment.value is not None
    assert reassessment.value.self_assessed_level == "advanced"
    assert reassessment.value.admin_overridden_level == "beginner"
    assert reassessment.value.effective_level == "beginner"
    assert reassessment.value.overridden_by == admin.user_id
