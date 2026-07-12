from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService

_SPEC = importlib.util.spec_from_file_location(
    "newcomer_orchestration_seed_script",
    Path(__file__).resolve().parents[2] / "scripts" / "seed_newcomer_training_path.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
seed = _MODULE.seed
parse_args = _MODULE.parse_args


@pytest.mark.asyncio
async def test_should_seed_three_composable_product_modules(test_db):
    summary = await seed(test_db)
    active = await TrainingPathRevisionService(test_db).active_revision()

    assert active is not None
    payload = TrainingPathPayload.model_validate(active.payload_json)
    product_modules = payload.phases[1].modules
    assert [module.title for module in product_modules] == [
        "产品 A 核心功能",
        "产品 B 核心功能",
        "标准产品 Demo",
    ]
    assert [activity.type for activity in product_modules[0].activities] == [
        "lesson",
        "quiz",
        "audio_assessment",
    ]
    assert summary.verified is True


@pytest.mark.asyncio
async def test_seed_is_idempotent(test_db):
    first = await seed(test_db)
    second = await seed(test_db)
    assert second.active_revision_id == first.active_revision_id
    assert second.verified is True


def test_seed_cli_applies_by_default_and_supports_verify_only() -> None:
    assert parse_args([]).verify_only is False
    assert parse_args(["--verify-only"]).verify_only is True
