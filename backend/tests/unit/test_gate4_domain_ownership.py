from __future__ import annotations

import ast
import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from scripts.architecture_dependency_guard import collect_edges

from common.business_rules.defaults import DEFAULT_ROLEPLAY_SITUATION_PACKS
from common.roleplay_contracts import check_roleplay_output
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.roleplay_contracts import (
    RoleplayContractCompiler,
    build_roleplay_turn_context,
    initial_roleplay_disclosure_state,
    resolve_roleplay_disclosure_state,
)
from evaluation.api import _build_response
from evaluation.services.comprehensive_report import (
    ComprehensiveReport,
    DimensionScore,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_ROOT = REPO_ROOT / "backend" / "tests" / "golden"
POLICY_PATH = REPO_ROOT / "docs" / "architecture" / "module-dependency-policy.yaml"
SRC_ROOT = REPO_ROOT / "backend" / "src"
GATE4_REVERSE_EDGES = {
    ("curriculum_practice", "admin"),
    ("evaluation", "admin"),
    ("evaluation", "curriculum_practice"),
    ("evaluation", "presentation_coach"),
    ("evaluation", "sales_bot"),
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _roleplay_payload() -> dict[str, Any]:
    persona = {
        "id": "gate4-persona",
        "persona_policy": {
            "roleplay_defaults": {
                "situation_code": "first_visit",
                "visible_information_keys": ["industry", "company_profile"],
                "hidden_information_keys": ["budget", "decision_chain"],
                "forbidden_claim_patterns": ["上次拜访"],
                "disclosure_policy": {
                    "phases": [
                        {
                            "keywords": ["预算"],
                            "disclose_keys": ["budget"],
                            "disclose": {"text": "预算仍需采购委员会确认。"},
                        }
                    ]
                },
            }
        },
    }
    contract = RoleplayContractCompiler().compile_from_persona_sync(
        persona,
        actor_id="gate4",
        compiled_at="2026-07-11T00:00:00+00:00",
    )
    initial = initial_roleplay_disclosure_state(
        contract,
        now_iso="2026-07-11T00:01:00+00:00",
    )
    triggered = resolve_roleplay_disclosure_state(
        contract=contract,
        previous_state=initial,
        learner_message="本次项目预算是多少？",
        current_sales_stage="discovery",
        turn_number=2,
        now_iso="2026-07-11T00:02:00+00:00",
    )
    first_pack = next(
        item
        for item in DEFAULT_ROLEPLAY_SITUATION_PACKS["packs"]
        if item["code"] == "first_visit"
    )
    pack = SituationPackDTO.from_ruleset_entry(first_pack)
    return {
        "contract": contract,
        "initial_disclosure": initial,
        "triggered_disclosure": triggered,
        "turn_context": build_roleplay_turn_context(
            contract=contract,
            disclosure_state=triggered,
            visible_payload={"industry": "制造业", "budget": "预算仍需确认"},
            current_sales_stage="discovery",
        ),
        "decisions": {
            "allow": check_roleplay_output(
                contract=contract,
                text="我们先了解当前业务挑战。",
                runtime_state=triggered,
            ),
            "block_or_record": check_roleplay_output(
                contract=contract,
                text="上次拜访时你已经确认预算。",
                runtime_state=triggered,
            ),
        },
        "situation_pack": {
            "payload": pack.as_canonical_dict(),
            "content_hash": situation_pack_content_hash(pack),
        },
    }


def _report_payload() -> dict[str, Any]:
    report = ComprehensiveReport(
        session_id="gate4-session",
        generated_at=datetime(2026, 7, 11, tzinfo=UTC),
        overall_score=82.5,
        dimension_scores=[
            DimensionScore(
                name="准确性",
                score=85.0,
                weight=0.6,
                description="事实准确",
                dimension_id="accuracy",
            ),
            DimensionScore(
                name="表达",
                score=78.75,
                weight=0.4,
                description="表达清晰",
                dimension_id="clarity",
            ),
        ],
        stage_summaries=[
            {
                "stage_number": 1,
                "start_turn": 1,
                "end_turn": 2,
                "average_score": 82.5,
                "key_points": ["价值表达"],
                "summary": "完成",
            }
        ],
        key_strengths=["事实准确"],
        key_improvements=["更简洁"],
        detailed_feedback="保持证据可追溯。",
        recommendations=["下一轮缩短开场"],
        ruleset_id="ruleset-gate4",
        ruleset_version="v1",
        score_basis="weighted_dimensions",
        ruleset_source="published",
        scoring_metadata={"source": "published"},
    )
    return _build_response(report).model_dump(mode="json")


def _actual_edges() -> set[tuple[str, str]]:
    policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    packages = {str(item) for item in policy["packages"]}
    return set(collect_edges(SRC_ROOT, packages))


def test_gate4_roleplay_golden_contract_is_byte_stable() -> None:
    expected = _load_json(GOLDEN_ROOT / "roleplay" / "gate4-roleplay-contracts.json")

    assert _roleplay_payload() == expected


def test_gate4_report_wire_projection_is_byte_stable() -> None:
    expected = _load_json(GOLDEN_ROOT / "evaluation" / "gate4-scenario-reports.json")

    assert _report_payload() == expected


def test_gate4_reverse_dependency_inventory_cannot_expand_during_migration() -> None:
    remaining = _actual_edges() & GATE4_REVERSE_EDGES

    assert remaining == set()


def test_roleplay_neutral_primitives_are_compatibility_authority() -> None:
    contracts = importlib.import_module("roleplay.contracts")
    situation_packs = importlib.import_module("roleplay.situation_packs")

    from common.roleplay_contracts import (
        check_roleplay_output as compatibility_check,
    )
    from curriculum_practice.services.roleplay.situation_pack_dto import (
        SituationPackDTO,
    )

    assert compatibility_check is contracts.check_roleplay_output
    assert SituationPackDTO is situation_packs.SituationPackSnapshot
    assert _roleplay_payload() == _load_json(
        GOLDEN_ROOT / "roleplay" / "gate4-roleplay-contracts.json"
    )


def test_roleplay_neutral_primitives_do_not_import_protected_domains() -> None:
    protected = {
        "admin",
        "agent",
        "curriculum_practice",
        "evaluation",
        "presentation_coach",
        "sales_bot",
    }
    roleplay_root = SRC_ROOT / "roleplay"
    imported: set[str] = set()
    for path in roleplay_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])

    assert roleplay_root.is_dir()
    assert imported.isdisjoint(protected)


def test_roleplay_compiler_rollout_selects_one_differential_authority(
    monkeypatch: Any,
) -> None:
    from common.config import Settings
    from curriculum_practice.services.roleplay_contracts import (
        LegacyRoleplayContractCompiler,
        build_roleplay_contract_compiler,
    )
    from curriculum_practice.services.roleplay_contracts import (
        RoleplayContractCompiler as CompatibilityCompiler,
    )
    from roleplay.compiler import RoleplayContractCompiler as NeutralCompiler

    persona = {
        "id": "gate4-rollout-persona",
        "persona_policy": {
            "roleplay_defaults": {
                "situation_code": "first_visit",
                "visible_information_keys": ["industry"],
                "hidden_information_keys": ["budget"],
            }
        },
    }
    compiled_at = "2026-07-11T00:00:00+00:00"
    neutral = build_roleplay_contract_compiler(neutral_enabled=True)
    legacy = build_roleplay_contract_compiler(neutral_enabled=False)

    assert CompatibilityCompiler is NeutralCompiler
    assert type(neutral) is NeutralCompiler
    assert type(legacy) is LegacyRoleplayContractCompiler
    assert neutral.compile_from_persona_sync(
        persona,
        actor_id="gate4",
        compiled_at=compiled_at,
    ) == legacy.compile_from_persona_sync(
        persona,
        actor_id="gate4",
        compiled_at=compiled_at,
    )

    monkeypatch.delenv("ROLEPLAY_NEUTRAL_OWNER_ENABLED", raising=False)
    assert Settings().ROLEPLAY_NEUTRAL_OWNER_ENABLED is True
    monkeypatch.setenv("ROLEPLAY_NEUTRAL_OWNER_ENABLED", "invalid")
    assert Settings().ROLEPLAY_NEUTRAL_OWNER_ENABLED is False


def test_configuration_governance_is_neutral_and_selects_one_authority(
    monkeypatch: Any,
) -> None:
    from common.config import Settings
    from configuration_governance.lifecycle import ConfigBundleLifecycleService
    from configuration_governance.rollout import select_configuration_authority

    class FakeLifecycleBackend:
        pass

    backend = FakeLifecycleBackend()
    neutral = select_configuration_authority(
        enabled=True,
        neutral_factory=lambda: ConfigBundleLifecycleService(backend),
        legacy_factory=lambda: backend,
    )
    legacy = select_configuration_authority(
        enabled=False,
        neutral_factory=lambda: ConfigBundleLifecycleService(backend),
        legacy_factory=lambda: backend,
    )

    assert isinstance(neutral, ConfigBundleLifecycleService)
    assert legacy is backend

    protected = {
        "admin",
        "agent",
        "curriculum_practice",
        "evaluation",
        "presentation_coach",
        "sales_bot",
    }
    governance_root = SRC_ROOT / "configuration_governance"
    imported: set[str] = set()
    for path in governance_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])

    assert governance_root.is_dir()
    assert imported.isdisjoint(protected)

    monkeypatch.delenv("CONFIGURATION_GOVERNANCE_ENABLED", raising=False)
    assert Settings().CONFIGURATION_GOVERNANCE_ENABLED is True
    monkeypatch.setenv("CONFIGURATION_GOVERNANCE_ENABLED", "invalid")
    assert Settings().CONFIGURATION_GOVERNANCE_ENABLED is False


@pytest.mark.asyncio
async def test_evaluation_scenario_registry_is_frozen_extensible_and_fail_closed() -> None:
    from common.error_handling.result import Result
    from evaluation.ports.evidence import SessionEvidence
    from evaluation.ports.scenario import (
        EvaluationScenarioInput,
        EvaluationScenarioRegistry,
        EvaluationScenarioResult,
    )

    class FakeScenario:
        async def evaluate(
            self,
            scenario_input: EvaluationScenarioInput,
        ) -> Result[EvaluationScenarioResult]:
            return Result.ok(
                EvaluationScenarioResult(
                    session_id=scenario_input.evidence.session_id,
                    generated_at=datetime(2026, 7, 11, tzinfo=UTC),
                    overall_score=91.0,
                    detailed_feedback="fake scenario",
                )
            )

    registry = EvaluationScenarioRegistry()
    registry.register("future-scenario", lambda _db: FakeScenario())
    with pytest.raises(ValueError, match="already registered"):
        registry.register("future-scenario", lambda _db: FakeScenario())
    registry.freeze()
    with pytest.raises(RuntimeError, match="frozen"):
        registry.register("late-scenario", lambda _db: FakeScenario())

    evidence = SessionEvidence(
        session_id="future-session",
        scenario_type="future-scenario",
        transcript="用户: hello\nAI: world",
    )
    result = await registry.evaluate(
        "future-scenario",
        db=object(),
        scenario_input=EvaluationScenarioInput(evidence=evidence),
    )
    assert result.is_success
    assert result.value is not None
    assert result.value.overall_score == 91.0

    missing = await registry.evaluate(
        "future-scenario",
        db=object(),
        scenario_input=EvaluationScenarioInput(
            evidence=SessionEvidence(
                session_id="missing-evidence",
                scenario_type="future-scenario",
                transcript="",
            )
        ),
    )
    assert missing.is_success is False
    assert missing.fallback == "[EVALUATION_EVIDENCE_INSUFFICIENT]"

    unknown = await registry.evaluate(
        "unknown",
        db=object(),
        scenario_input=EvaluationScenarioInput(evidence=evidence),
    )
    assert unknown.is_success is False
    assert unknown.fallback == "[EVALUATION_SCENARIO_NOT_CONFIGURED]"


def test_presentation_realtime_retains_only_named_sales_handler_seam() -> None:
    from sales_bot.websocket.components.stepfun_event_payloads import (
        build_heartbeat_event as compatibility_heartbeat,
    )
    from sales_bot.websocket.components.stepfun_helpers import (
        extract_response_text as compatibility_extract_response_text,
    )
    from sales_bot.websocket.components.stepfun_message_helpers import (
        save_stepfun_message as compatibility_save_message,
    )
    from training_runtime.realtime.events import build_heartbeat_event
    from training_runtime.realtime.message_persistence import save_stepfun_message
    from training_runtime.realtime.text_payloads import extract_response_text

    path = (
        SRC_ROOT
        / "presentation_coach"
        / "websocket"
        / "presentation_stepfun_realtime_handler.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sales_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("sales_bot")
    }

    assert sales_imports == {"sales_bot.websocket.stepfun_realtime_handler"}
    assert compatibility_heartbeat is build_heartbeat_event
    assert compatibility_extract_response_text is extract_response_text
    assert compatibility_save_message is save_stepfun_message


@pytest.mark.asyncio
async def test_configuration_governance_core_owns_publish_orchestration() -> None:
    from configuration_governance.contracts import (
        ConfigAuditRecord,
        ConfigVersionRecord,
    )
    from configuration_governance.lifecycle import ConfigBundleLifecycleService

    before = ConfigVersionRecord(
        version_id="version-before",
        source_config_id="source-before",
        version_number=1,
        version_label="v1",
        status="published",
        snapshot={"version": "v1"},
        updated_at=datetime(2026, 7, 11, tzinfo=UTC),
    )
    after = ConfigVersionRecord(
        version_id="version-after",
        source_config_id="source-after",
        version_number=2,
        version_label="v2",
        status="published",
        snapshot={"version": "v2"},
        updated_at=datetime(2026, 7, 11, tzinfo=UTC),
    )

    class FakePersistence:
        def __init__(self) -> None:
            self.events: list[str] = []
            self.audit_decision: Any | None = None

        async def ensure_bundle(self, bundle_key: str) -> None:
            self.events.append(f"ensure:{bundle_key}")

        async def load_active_version(
            self, bundle_key: str
        ) -> ConfigVersionRecord | None:
            self.events.append(f"active:{bundle_key}")
            return before

        async def publish_version(
            self,
            *,
            bundle_key: str,
            actor_id: str,
            config_id: str | None,
            reason: str | None,
        ) -> ConfigVersionRecord:
            assert reason == "publish v2"
            self.events.append(f"publish:{bundle_key}:{actor_id}:{config_id}")
            return after

        async def sync_projection(
            self,
            *,
            bundle_key: str,
            actor_id: str,
            version: ConfigVersionRecord,
            lifecycle_action: str,
        ) -> dict[str, Any] | None:
            self.events.append(f"projection:{lifecycle_action}:{version.version_id}")
            return {"status": "ok", "lifecycle_action": lifecycle_action}

        async def append_audit(self, decision: Any) -> ConfigAuditRecord:
            self.events.append(f"audit:{decision.action}")
            self.audit_decision = decision
            return ConfigAuditRecord(
                audit_id="audit-1",
                bundle_key=decision.bundle_key,
                version_id=decision.version_id,
                action=decision.action,
                actor_id=decision.actor_id,
                before_version=decision.before_version,
                after_version=decision.after_version,
                reason=decision.reason,
                trace_id="trace-1",
                created_at=datetime(2026, 7, 11, tzinfo=UTC),
            )

    persistence = FakePersistence()
    result = await ConfigBundleLifecycleService(persistence).publish(
        bundle_key="roleplay.situation_packs.ruleset",
        actor_id="actor-1",
        config_id="source-after",
        reason="publish v2",
    )

    assert persistence.events == [
        "ensure:roleplay.situation_packs.ruleset",
        "active:roleplay.situation_packs.ruleset",
        "publish:roleplay.situation_packs.ruleset:actor-1:source-after",
        "projection:publish:version-after",
        "audit:publish",
    ]
    assert result.version == after
    assert result.audit is not None
    assert persistence.audit_decision.before_version == 1
    assert persistence.audit_decision.after_version == 2
    assert persistence.audit_decision.after_snapshot["projection_sync"] == {
        "status": "ok",
        "lifecycle_action": "publish",
    }


def test_evaluation_scenario_value_objects_are_deeply_immutable() -> None:
    from evaluation.ports.evidence import SessionEvidence
    from evaluation.ports.scenario import (
        EvaluationScenarioInput,
        EvaluationScenarioResult,
    )

    result = EvaluationScenarioResult(
        session_id="immutable-session",
        generated_at=datetime(2026, 7, 11, tzinfo=UTC),
        overall_score=80.0,
        dimension_scores=[],
        stage_summaries=[{"stage": 1, "points": ["a"]}],
        key_strengths=["clear"],
        scoring_metadata={"source": {"kind": "published"}},
    )
    scenario_input = EvaluationScenarioInput(
        evidence=SessionEvidence(
            session_id="immutable-session",
            scenario_type="presentation",
            transcript="user: hello",
        ),
        options={"rules": ["strict"]},
    )

    with pytest.raises(AttributeError):
        result.dimension_scores.append(  # type: ignore[attr-defined]
            object()
        )
    with pytest.raises(TypeError):
        result.stage_summaries[0]["stage"] = 2  # type: ignore[index]
    with pytest.raises(TypeError):
        result.scoring_metadata["source"]["kind"] = "default"  # type: ignore[index,union-attr]
    with pytest.raises(TypeError):
        scenario_input.options["rules"] = ()  # type: ignore[index]
