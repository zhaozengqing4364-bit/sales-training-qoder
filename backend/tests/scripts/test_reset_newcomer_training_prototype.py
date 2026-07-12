from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

from sales_trainer.models import SalesTrainerAssetRevision


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"test_{name}", Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reset_newcomer_prototype = _load(
    "reset_newcomer_training_prototype"
).reset_newcomer_prototype
seed = _load("seed_newcomer_training_path").seed


@pytest.mark.asyncio
async def test_should_report_without_mutating_in_dry_run(test_db):
    await seed(test_db)
    before = int(
        await test_db.scalar(
            select(func.count()).select_from(SalesTrainerAssetRevision)
        )
        or 0
    )
    report = await reset_newcomer_prototype(test_db, apply=False)
    after = int(
        await test_db.scalar(
            select(func.count()).select_from(SalesTrainerAssetRevision)
        )
        or 0
    )

    assert report.total_rows > 0
    assert after == before


@pytest.mark.asyncio
async def test_should_delete_only_bounded_prototype_authority(test_db):
    await seed(test_db)
    report = await reset_newcomer_prototype(test_db, apply=True)
    assert report.applied is True
    assert report.counts["sales_trainer_asset_revisions"] > 0
