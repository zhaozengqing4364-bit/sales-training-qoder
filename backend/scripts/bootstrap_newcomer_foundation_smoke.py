#!/usr/bin/env python3
"""Create the idempotent local learner cohort/enrollment for Foundation smoke."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common.db.model_registry.registration import register_all_models  # noqa: E402
from common.db.models import User  # noqa: E402
from common.db.session import AsyncSessionLocal  # noqa: E402
from foundation_standard_pack import PACK_KEY  # noqa: E402
from newcomer_training.application import (  # noqa: E402
    CommandActor,
    PathEnrollmentService,
)
from newcomer_training.models import NewcomerEnrollment, NewcomerPath  # noqa: E402

SMOKE_COHORT_KEY = "newcomer-foundation-smoke"


async def bootstrap_foundation_smoke(
    session: AsyncSession,
    *,
    organization_id: str,
    learner_email: str,
) -> dict[str, str]:
    learner = await session.scalar(
        select(User).where(User.email == learner_email.strip().lower()).limit(1)
    )
    if learner is None or learner.is_active is False:
        raise RuntimeError("Foundation smoke learner is missing or inactive")

    path = await session.scalar(
        select(NewcomerPath)
        .where(NewcomerPath.organization_id == organization_id)
        .where(NewcomerPath.stable_key == PACK_KEY)
        .limit(1)
    )
    if path is None or path.published_revision_id is None:
        raise RuntimeError("Foundation standard pack must be installed before smoke enrollment")

    active_enrollment = await session.scalar(
        select(NewcomerEnrollment)
        .where(NewcomerEnrollment.organization_id == organization_id)
        .where(NewcomerEnrollment.learner_id == str(learner.user_id))
        .where(NewcomerEnrollment.status == "active")
        .limit(1)
    )
    if active_enrollment is not None:
        if active_enrollment.path_revision_id != path.published_revision_id:
            raise RuntimeError(
                "Foundation smoke learner is already active on a different path revision"
            )
        return {
            "learner_id": str(learner.user_id),
            "cohort_id": active_enrollment.cohort_id,
            "enrollment_id": active_enrollment.enrollment_id,
            "path_revision_id": active_enrollment.path_revision_id,
        }

    actor = CommandActor(
        organization_id=organization_id,
        actor_id="system:foundation-smoke",
        capabilities=frozenset(
            {"newcomer.cohort.manage", "newcomer.enrollment.manage"}
        ),
    )
    service = PathEnrollmentService(session)
    cohort = await service.create_cohort(
        actor=actor,
        stable_key=SMOKE_COHORT_KEY,
        name="新人基础训练 Smoke 班",
        path_revision_id=path.published_revision_id,
        idempotency_key=f"{SMOKE_COHORT_KEY}:create",
    )
    enrollment = await service.enroll(
        actor=actor,
        cohort_id=cohort.cohort_id,
        learner_id=str(learner.user_id),
        idempotency_key=f"{SMOKE_COHORT_KEY}:enroll:{learner.user_id}",
    )
    return {
        "learner_id": str(learner.user_id),
        "cohort_id": cohort.cohort_id,
        "enrollment_id": enrollment.enrollment_id,
        "path_revision_id": enrollment.path_revision_id,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="创建或校验本地 Foundation smoke 班级和学员分配。"
    )
    parser.add_argument(
        "--organization-id",
        default=os.getenv("NEWCOMER_FOUNDATION_ORGANIZATION_ID", "default"),
    )
    parser.add_argument(
        "--learner-email",
        default=os.getenv(
            "NEWCOMER_E2E_LEARNER_EMAIL",
            "newcomer.training.learner@example.com",
        ),
    )
    return parser.parse_args()


async def _run(arguments: argparse.Namespace) -> None:
    register_all_models()
    async with AsyncSessionLocal() as session:
        try:
            result = await bootstrap_foundation_smoke(
                session,
                organization_id=str(arguments.organization_id).strip(),
                learner_email=str(arguments.learner_email).strip().lower(),
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_run(_arguments()))
