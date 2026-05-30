from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from common.business_rules.defaults import ROLEPLAY_SITUATION_PACKS_KEY
from common.config import Settings
from common.db.models import ConfigBundleAuditLog, SystemLog
from common.monitoring.logger import configure_logging, get_trace_id, set_trace_id
from common.monitoring.metrics import situation_pack_dual_read_mismatch
from curriculum_practice.services.roleplay.adapters.business_rule_config_adapter import (
    BusinessRuleConfigSituationPackAdapter,
)
from curriculum_practice.services.roleplay.adapters.entity_projection_adapter import (
    EntitySituationPackProjectionAdapter,
)
from curriculum_practice.services.roleplay.dual_read_observability import (
    get_dual_read_observability_snapshot,
    record_dual_read_mismatch,
    reset_dual_read_observability_for_tests,
)
from curriculum_practice.services.roleplay.dual_read_promotion_gate import (
    B1_AUTHORITY_BLOCKED_ACTION,
    DUAL_READ_MISMATCH_ACTION,
    DualReadPromotionGateService,
)
from curriculum_practice.services.roleplay.dual_read_repository import (
    DualReadCompareResult,
    DualReadSituationPackRepository,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)


def _pack(
    *,
    code: str,
    label: str,
    status: str = "published",
    forbidden_claim_patterns: list[str] | None = None,
) -> SituationPackDTO:
    return SituationPackDTO.from_ruleset_entry(
        {
            "code": code,
            "label": label,
            "status": status,
            "default_relationship_context": {"prior_interactions": "none"},
            "default_visible_information_scope": {"initial_visible_keys": ["industry"]},
            "default_forbidden_claim_patterns": forbidden_claim_patterns or [],
        }
    )


@pytest.fixture(autouse=True)
def _reset_dual_read_observability() -> None:
    reset_dual_read_observability_for_tests()
    situation_pack_dual_read_mismatch._metrics.clear()  # type: ignore[attr-defined]


def test_situation_pack_dual_read_flag_defaults_to_disabled(monkeypatch) -> None:
    monkeypatch.delenv("SITUATION_PACK_DUAL_READ", raising=False)
    monkeypatch.delenv("SITUATION_PACK_B1_AUTHORITY", raising=False)

    settings = Settings()

    assert settings.SITUATION_PACK_DUAL_READ is False
    assert settings.SITUATION_PACK_B1_AUTHORITY is False


def test_situation_pack_b1_authority_requires_dual_read_flag(monkeypatch) -> None:
    monkeypatch.setenv("SITUATION_PACK_B1_AUTHORITY", "true")
    monkeypatch.delenv("SITUATION_PACK_DUAL_READ", raising=False)

    settings = Settings()

    assert settings.SITUATION_PACK_B1_AUTHORITY is True
    assert settings.SITUATION_PACK_DUAL_READ is False


def test_situation_pack_b1_approval_id_defaults_to_empty(monkeypatch) -> None:
    monkeypatch.delenv("SITUATION_PACK_B1_APPROVAL_ID", raising=False)

    settings = Settings()

    assert settings.SITUATION_PACK_B1_APPROVAL_ID == ""


def test_situation_pack_content_hash_ignores_label_metadata() -> None:
    left = _pack(code="first_visit", label="首次拜访")
    right = _pack(code="first_visit", label="首次拜访-Projection")

    assert situation_pack_content_hash(left) == situation_pack_content_hash(right)


def test_dual_read_returns_phase_a_pack_when_hashes_match() -> None:
    shared = _pack(code="first_visit", label="首次拜访")
    phase_a = BusinessRuleConfigSituationPackAdapter({"first_visit": shared})
    phase_b1 = EntitySituationPackProjectionAdapter.from_in_memory(
        {
            "first_visit": _pack(
                code="first_visit",
                label="首次拜访-Projection",
                forbidden_claim_patterns=[],
            )
        }
    )
    mismatches: list[DualReadCompareResult] = []
    repo = DualReadSituationPackRepository(
        phase_a=phase_a,
        phase_b1=phase_b1,
        on_mismatch=mismatches.append,
    )

    pack = repo.get_published("first_visit")

    assert pack is shared
    assert repo.mismatch_count == 0
    assert mismatches == []


def test_dual_read_serves_b1_on_match_when_b1_authority_enabled() -> None:
    phase_a_pack = _pack(code="first_visit", label="Phase A")
    phase_b1_pack = _pack(code="first_visit", label="Phase B1 Projection")
    repo = DualReadSituationPackRepository(
        phase_a=BusinessRuleConfigSituationPackAdapter({"first_visit": phase_a_pack}),
        phase_b1=EntitySituationPackProjectionAdapter.from_in_memory(
            {"first_visit": phase_b1_pack}
        ),
        authority="phase_b1",
    )

    pack = repo.get_published("first_visit")

    assert pack is phase_b1_pack
    assert repo.authority == "phase_b1"
    assert repo.mismatch_count == 0


def test_dual_read_reports_mismatch_and_keeps_phase_a_authority() -> None:
    phase_a_pack = _pack(code="first_visit", label="Phase A", forbidden_claim_patterns=["上次拜访"])
    phase_b1_pack = _pack(
        code="first_visit",
        label="Phase B1",
        forbidden_claim_patterns=["之前报价"],
    )
    phase_a = BusinessRuleConfigSituationPackAdapter({"first_visit": phase_a_pack})
    phase_b1 = EntitySituationPackProjectionAdapter.from_in_memory(
        {"first_visit": phase_b1_pack}
    )
    mismatches: list[DualReadCompareResult] = []
    repo = DualReadSituationPackRepository(
        phase_a=phase_a,
        phase_b1=phase_b1,
        authority="phase_a",
        on_mismatch=mismatches.append,
    )

    pack = repo.get_published("first_visit")

    assert pack is phase_a_pack
    assert repo.mismatch_count == 1
    assert len(mismatches) == 1
    assert mismatches[0].matched is False
    assert mismatches[0].phase_a_hash != mismatches[0].phase_b1_hash


def test_dual_read_b1_authority_falls_back_to_phase_a_on_mismatch() -> None:
    phase_a_pack = _pack(code="first_visit", label="Phase A", forbidden_claim_patterns=["上次拜访"])
    phase_b1_pack = _pack(
        code="first_visit",
        label="Phase B1",
        forbidden_claim_patterns=["之前报价"],
    )
    repo = DualReadSituationPackRepository(
        phase_a=BusinessRuleConfigSituationPackAdapter({"first_visit": phase_a_pack}),
        phase_b1=EntitySituationPackProjectionAdapter.from_in_memory(
            {"first_visit": phase_b1_pack}
        ),
        authority="phase_b1",
    )

    pack = repo.get_published("first_visit")

    assert pack is phase_a_pack
    assert repo.mismatch_count == 1


def test_dual_read_list_published_detects_missing_projection_pack() -> None:
    phase_a = BusinessRuleConfigSituationPackAdapter(
        {
            "first_visit": _pack(code="first_visit", label="A"),
            "follow_up": _pack(code="follow_up", label="A follow"),
        }
    )
    phase_b1 = EntitySituationPackProjectionAdapter.from_in_memory(
        {"first_visit": _pack(code="first_visit", label="B1")}
    )
    repo = DualReadSituationPackRepository(phase_a=phase_a, phase_b1=phase_b1)

    published = repo.list_published()

    assert [item.code for item in published] == ["first_visit", "follow_up"]
    assert repo.mismatch_count == 1


@pytest.mark.asyncio
async def test_from_database_uses_phase_a_only_when_dual_read_disabled(
    test_db,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.situation_pack_repository.settings",
        Settings(),
    )
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.dual_read_promotion_gate.settings",
        Settings(),
    )

    repo = await SituationPackRepository.from_database(test_db)

    assert isinstance(repo, BusinessRuleConfigSituationPackAdapter)
    assert repo.get_published("first_visit") is not None


@pytest.mark.asyncio
async def test_from_database_wraps_dual_read_when_flag_enabled(
    test_db,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SITUATION_PACK_DUAL_READ", "true")
    monkeypatch.delenv("SITUATION_PACK_B1_AUTHORITY", raising=False)
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.situation_pack_repository.settings",
        Settings(),
    )
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.dual_read_promotion_gate.settings",
        Settings(),
    )

    repo = await SituationPackRepository.from_database(test_db)

    assert isinstance(repo, DualReadSituationPackRepository)
    assert repo.authority == "phase_a"
    assert repo.mismatch_count == 0
    assert repo.get_published("first_visit") is not None


@pytest.mark.asyncio
async def test_from_database_blocks_b1_authority_without_approval(
    test_db,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SITUATION_PACK_DUAL_READ", "true")
    monkeypatch.setenv("SITUATION_PACK_B1_AUTHORITY", "true")
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.situation_pack_repository.settings",
        Settings(),
    )

    repo = await SituationPackRepository.from_database(test_db)

    assert isinstance(repo, DualReadSituationPackRepository)
    assert repo.authority == "phase_a"


@pytest.mark.asyncio
async def test_from_database_uses_b1_authority_when_gate_is_ready(
    test_db,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SITUATION_PACK_DUAL_READ", "true")
    monkeypatch.setenv("SITUATION_PACK_B1_AUTHORITY", "true")
    monkeypatch.setenv("SITUATION_PACK_B1_APPROVAL_ID", "hitl-approval-96")
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.situation_pack_repository.settings",
        Settings(),
    )
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.dual_read_promotion_gate.settings",
        Settings(),
    )

    repo = await SituationPackRepository.from_database(test_db)

    assert isinstance(repo, DualReadSituationPackRepository)
    assert repo.authority == "phase_b1"


@pytest.mark.asyncio
async def test_b1_promotion_gate_blocks_when_mismatch_exists_in_window(
    test_db,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SITUATION_PACK_DUAL_READ", "true")
    monkeypatch.setenv("SITUATION_PACK_B1_AUTHORITY", "true")
    monkeypatch.setenv("SITUATION_PACK_B1_APPROVAL_ID", "hitl-approval-96")
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.dual_read_promotion_gate.settings",
        Settings(),
    )
    test_db.add(
        SystemLog(
            action=DUAL_READ_MISMATCH_ACTION,
            user_identifier="system",
            status="warning",
            details=json.dumps(
                {
                    "code": "first_visit",
                    "phase_a_hash": "hash-a",
                    "phase_b1_hash": "hash-b1",
                    "trace_id": "trace-1",
                    "scope": "lookup",
                }
            ),
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await test_db.flush()

    decision = await DualReadPromotionGateService(test_db).evaluate(write_audit=True)

    assert decision.authority == "phase_a"
    assert decision.promotion_ready is False
    assert decision.blocked_reasons == ["dual_read_mismatch_in_window"]
    log = await test_db.scalar(
        select(SystemLog).where(SystemLog.action == B1_AUTHORITY_BLOCKED_ACTION).limit(1)
    )
    assert log is not None


@pytest.mark.asyncio
async def test_b1_promotion_gate_blocks_unresolved_projection_sync_failure(
    test_db,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SITUATION_PACK_DUAL_READ", "true")
    monkeypatch.setenv("SITUATION_PACK_B1_AUTHORITY", "true")
    monkeypatch.setenv("SITUATION_PACK_B1_APPROVAL_ID", "hitl-approval-96")
    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.dual_read_promotion_gate.settings",
        Settings(),
    )
    test_db.add(
        ConfigBundleAuditLog(
            bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
            action="publish",
            actor_id=None,
            before_version=None,
            after_version=1,
            before_snapshot_json=None,
            after_snapshot_json={
                "version": 1,
                "projection_sync": {"status": "failed", "error": "boom"},
            },
            reason="test",
            trace_id="trace-1",
            created_at=datetime.now(UTC),
        )
    )
    await test_db.flush()

    decision = await DualReadPromotionGateService(test_db).evaluate(write_audit=False)

    assert decision.authority == "phase_a"
    assert decision.blocked_reasons == ["projection_sync_failure_unresolved"]


def test_dual_read_match_does_not_emit_observability_signals() -> None:
    shared = _pack(code="first_visit", label="首次拜访")
    repo = DualReadSituationPackRepository(
        phase_a=BusinessRuleConfigSituationPackAdapter({"first_visit": shared}),
        phase_b1=EntitySituationPackProjectionAdapter.from_in_memory(
            {
                "first_visit": _pack(
                    code="first_visit",
                    label="首次拜访-Projection",
                )
            }
        ),
    )

    repo.get_published("first_visit")

    snapshot = get_dual_read_observability_snapshot()
    assert snapshot["mismatch_count"] == 0
    assert snapshot["lookup_count"] == 1
    assert snapshot["matched_count"] == 1
    assert snapshot["last_mismatch"] is None
    assert situation_pack_dual_read_mismatch._metrics == {}  # type: ignore[attr-defined]


def test_dual_read_mismatch_records_structured_log_metric_and_snapshot(
    monkeypatch,
) -> None:
    configure_logging(log_level="DEBUG")
    set_trace_id("dual-read-trace-95")
    emitted: list[dict[str, object]] = []

    def _capture_warning(msg: str, **kwargs: object) -> None:
        emitted.append({"msg": msg, **kwargs})

    monkeypatch.setattr(
        "curriculum_practice.services.roleplay.dual_read_observability.logger.warning",
        _capture_warning,
    )

    record_dual_read_mismatch(
        code="first_visit",
        scope="lookup",
        phase_a_hash="hash-a",
        phase_b1_hash="hash-b1",
    )

    snapshot = get_dual_read_observability_snapshot()
    assert snapshot["mismatch_count"] == 1
    assert snapshot["lookup_count"] == 0
    assert snapshot["last_mismatch"] == {
        "code": "first_visit",
        "scope": "lookup",
        "phase_a_hash": "hash-a",
        "phase_b1_hash": "hash-b1",
        "trace_id": "dual-read-trace-95",
        "detected_at": snapshot["last_mismatch"]["detected_at"],
    }
    assert emitted == [
        {
            "msg": "situation_pack_dual_read_mismatch",
            "code": "first_visit",
            "scope": "lookup",
            "phase_a_hash": "hash-a",
            "phase_b1_hash": "hash-b1",
        }
    ]
    assert (
        situation_pack_dual_read_mismatch.labels(
            code="first_visit",
            scope="lookup",
        )._value.get()
        == 1.0
    )


def test_dual_read_repository_increments_global_observability_on_mismatch() -> None:
    phase_a_pack = _pack(code="first_visit", label="Phase A", forbidden_claim_patterns=["上次拜访"])
    phase_b1_pack = _pack(
        code="first_visit",
        label="Phase B1",
        forbidden_claim_patterns=["之前报价"],
    )
    repo = DualReadSituationPackRepository(
        phase_a=BusinessRuleConfigSituationPackAdapter({"first_visit": phase_a_pack}),
        phase_b1=EntitySituationPackProjectionAdapter.from_in_memory(
            {"first_visit": phase_b1_pack}
        ),
    )

    repo.get_published("first_visit")

    snapshot = get_dual_read_observability_snapshot()
    assert repo.mismatch_count == 1
    assert snapshot["mismatch_count"] == 1
    assert snapshot["lookup_count"] == 1
    assert snapshot["matched_count"] == 0
    assert snapshot["last_mismatch"]["code"] == "first_visit"
    assert get_trace_id()
