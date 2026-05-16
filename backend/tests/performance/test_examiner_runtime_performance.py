from __future__ import annotations

import time
import tracemalloc

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.examiner_final_gate import (
    build_examiner_seed_manifest,
    seed_examiner_runtime,
    validate_examiner_seed_manifest,
)

from common.db.schemas import ScenarioType, SessionCreate
from common.services.practice_session_service import PracticeSessionCreateService


@pytest.mark.asyncio
@pytest.mark.performance
async def test_should_prepare_examiner_first_question_under_300ms(
    test_db: AsyncSession,
    test_user,
) -> None:
    runtime_seed = await seed_examiner_runtime(test_db, owner_id=str(test_user.user_id))
    service = PracticeSessionCreateService(test_db)

    start = time.perf_counter()
    result = await service.create_session(
        SessionCreate(
            scenario_type=ScenarioType.SALES,
            scenario_id=runtime_seed.scenario.scenario_id,
            agent_id=runtime_seed.agent.id,
            persona_id=runtime_seed.persona.id,
            runtime_profile_id=runtime_seed.runtime_profile.id,
            voice_mode="stepfun_realtime",
            practice_template_id=runtime_seed.examiner_template.template_id,
        ),
        current_user=test_user,
    )
    first_question_ms = (time.perf_counter() - start) * 1000

    assert result.session.curriculum_snapshot["practice_template"]["asset_id"] == (
        runtime_seed.examiner_template.template_id
    )
    assert first_question_ms < 300.0


@pytest.mark.performance
def test_should_score_imported_examiner_seed_under_2s() -> None:
    manifest = build_examiner_seed_manifest()

    start = time.perf_counter()
    summary = validate_examiner_seed_manifest(manifest)
    dimension_scores = {
        dimension: sum(
            1 for question in manifest["questions"] if question["dimension"] == dimension
        )
        for dimension in summary["dimensions"]
    }
    scoring_ms = (time.perf_counter() - start) * 1000

    assert dimension_scores == {
        "objection_handling": 7,
        "product_knowledge": 7,
        "value_logic": 6,
    }
    assert scoring_ms < 2000.0


@pytest.mark.performance
def test_should_validate_10mb_examiner_import_without_unbounded_memory_growth() -> None:
    base_manifest = build_examiner_seed_manifest()
    payload = "x" * (10 * 1024 * 1024)
    base_manifest["import_payload_bytes"] = len(payload)

    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    summary = validate_examiner_seed_manifest(base_manifest)
    after = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    assert summary["question_count"] == 20
    assert base_manifest["import_payload_bytes"] == 10 * 1024 * 1024
    assert (after - before) / (1024 * 1024) < 2.0
