"""Bounded dry-run/apply reset for newcomer path prototype authority."""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common.db.session import AsyncSessionLocal  # noqa: E402
from sales_trainer.models import (  # noqa: E402
    NewcomerTrainingActivityAttempt,
    NewcomerTrainingEnrollment,
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
)

CONFIRMATION = "RESET_NEWCOMER_PROTOTYPE"
RESOURCE_TYPES = frozenset(
    {
        "newcomer_training_path_orchestration",
        "newcomer_training_path",
        "newcomer_training_learning_topics",
    }
)


@dataclass(frozen=True, slots=True)
class ResetReport:
    counts: dict[str, int]
    applied: bool

    @property
    def total_rows(self) -> int:
        return sum(self.counts.values())


async def reset_newcomer_prototype(db: AsyncSession, *, apply: bool) -> ResetReport:
    revision_ids = select(SalesTrainerAssetRevision.revision_id).where(
        SalesTrainerAssetRevision.resource_type.in_(RESOURCE_TYPES)
    )
    counts = {
        "newcomer_training_activity_attempts": int(
            await db.scalar(
                select(func.count()).select_from(NewcomerTrainingActivityAttempt)
            )
            or 0
        ),
        "newcomer_training_enrollments": int(
            await db.scalar(
                select(func.count()).select_from(NewcomerTrainingEnrollment)
            )
            or 0
        ),
        "sales_trainer_asset_active_revisions": int(
            await db.scalar(
                select(func.count())
                .select_from(SalesTrainerAssetActiveRevision)
                .where(
                    SalesTrainerAssetActiveRevision.resource_type.in_(RESOURCE_TYPES)
                )
            )
            or 0
        ),
        "sales_trainer_asset_revisions": int(
            await db.scalar(
                select(func.count())
                .select_from(SalesTrainerAssetRevision)
                .where(SalesTrainerAssetRevision.resource_type.in_(RESOURCE_TYPES))
            )
            or 0
        ),
    }
    if not apply:
        return ResetReport(counts=counts, applied=False)
    try:
        await db.execute(delete(NewcomerTrainingActivityAttempt))
        await db.execute(delete(NewcomerTrainingEnrollment))
        await db.execute(
            delete(SalesTrainerAssetActiveRevision).where(
                SalesTrainerAssetActiveRevision.resource_type.in_(RESOURCE_TYPES)
            )
        )
        await db.execute(
            delete(SalesTrainerAssetRevision).where(
                SalesTrainerAssetRevision.revision_id.in_(revision_ids)
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return ResetReport(counts=counts, applied=True)


async def _run(*, apply: bool) -> ResetReport:
    async with AsyncSessionLocal() as db:
        return await reset_newcomer_prototype(db, apply=apply)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset bounded newcomer prototype data."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRMATION:
        parser.error(f"--apply requires --confirm {CONFIRMATION}")
    report = asyncio.run(_run(apply=bool(args.apply)))
    for table, count in report.counts.items():
        print(f"{table}={count}")
    print(f"total_rows={report.total_rows}")
    print(f"applied={str(report.applied).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
