from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

from common.db.models import User
from foundation_standard_pack import PACK_KEY, install_or_verify_standard_pack
from newcomer_training.application import CommandActor, PathEnrollmentService
from newcomer_training.models import NewcomerPath

SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "bootstrap_newcomer_foundation_smoke.py"
)


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location(
        "bootstrap_newcomer_foundation_smoke_test_module",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.bootstrap_foundation_smoke


@pytest.mark.asyncio
async def test_foundation_smoke_bootstrap_is_idempotent(test_db) -> None:
    learner = User(
        user_id="foundation-smoke-learner",
        wechat_user_id="foundation-smoke-wechat",
        email="newcomer.training.learner@example.com",
        name="新人训练学员",
        role="user",
        is_active=True,
    )
    test_db.add(learner)
    await install_or_verify_standard_pack(test_db, organization_id="default")
    await test_db.flush()

    bootstrap = _load_bootstrap()
    first = await bootstrap(
        test_db,
        organization_id="default",
        learner_email=learner.email,
    )
    replay = await bootstrap(
        test_db,
        organization_id="default",
        learner_email=learner.email,
    )

    assert replay == first
    assert first["learner_id"] == learner.user_id
    assert first["path_revision_id"]


@pytest.mark.asyncio
async def test_foundation_smoke_bootstrap_reuses_matching_active_enrollment(
    test_db,
) -> None:
    learner = User(
        user_id="foundation-smoke-existing-learner",
        wechat_user_id="foundation-smoke-existing-wechat",
        email="newcomer.training.existing@example.com",
        name="已有训练学员",
        role="user",
        is_active=True,
    )
    test_db.add(learner)
    await install_or_verify_standard_pack(test_db, organization_id="default")
    await test_db.flush()
    path = await test_db.scalar(
        select(NewcomerPath)
        .where(NewcomerPath.organization_id == "default")
        .where(NewcomerPath.stable_key == PACK_KEY)
    )
    assert path is not None and path.published_revision_id is not None
    actor = CommandActor(
        organization_id="default",
        actor_id="system:test",
        capabilities=frozenset(
            {"newcomer.cohort.manage", "newcomer.enrollment.manage"}
        ),
    )
    service = PathEnrollmentService(test_db)
    cohort = await service.create_cohort(
        actor=actor,
        stable_key="preexisting-foundation-smoke",
        name="已有训练班",
        path_revision_id=path.published_revision_id,
        idempotency_key="preexisting-foundation-smoke:create",
    )
    existing = await service.enroll(
        actor=actor,
        cohort_id=cohort.cohort_id,
        learner_id=learner.user_id,
        idempotency_key="preexisting-foundation-smoke:enroll",
    )

    result = await _load_bootstrap()(
        test_db,
        organization_id="default",
        learner_email=learner.email,
    )

    assert result == {
        "learner_id": learner.user_id,
        "cohort_id": cohort.cohort_id,
        "enrollment_id": existing.enrollment_id,
        "path_revision_id": path.published_revision_id,
    }
