from __future__ import annotations

import pytest
from scripts.bootstrap_smoke_practice_evidence import (
    SMOKE_RUNTIME_PROFILE_ID,
    SMOKE_RUNTIME_PROFILE_NAME,
    _get_or_create_runtime_profile,
    _get_or_create_scoring_ruleset,
)

from agent.models import VoiceRuntimeProfile
from common.db.models import ScoringRuleset


@pytest.mark.asyncio
async def test_should_reuse_named_smoke_runtime_profile_when_id_changed(test_db) -> None:
    existing = VoiceRuntimeProfile(
        id="existing-smoke-runtime-profile",
        name=SMOKE_RUNTIME_PROFILE_NAME,
    )
    test_db.add(existing)
    await test_db.flush()

    resolved = await _get_or_create_runtime_profile(test_db)

    assert resolved.id == existing.id
    assert resolved is existing


@pytest.mark.asyncio
async def test_should_create_smoke_runtime_profile_with_stable_id_when_absent(
    test_db,
) -> None:
    resolved = await _get_or_create_runtime_profile(test_db)

    assert resolved.id == SMOKE_RUNTIME_PROFILE_ID
    assert resolved.name == SMOKE_RUNTIME_PROFILE_NAME


@pytest.mark.asyncio
async def test_should_reuse_smoke_scoring_ruleset_when_natural_key_exists(
    test_db,
) -> None:
    existing = ScoringRuleset(
        ruleset_id="existing-smoke-sales-ruleset",
        scenario_type="sales",
        version="smoke-phase4-v1",
        display_name="Smoke Phase 4 Sales Scoring Ruleset",
    )
    test_db.add(existing)
    await test_db.flush()

    resolved = await _get_or_create_scoring_ruleset(test_db)

    assert resolved.ruleset_id == existing.ruleset_id
    assert resolved is existing
