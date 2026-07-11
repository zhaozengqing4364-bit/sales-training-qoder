from __future__ import annotations

import ast
import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

    assert remaining <= GATE4_REVERSE_EDGES
    assert remaining


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
