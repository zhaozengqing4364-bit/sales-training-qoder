from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.services.roleplay_contract_eval import (
    RoleplayContractDeterministicEvalHarness,
    RoleplayEvalReleaseGateConfig,
    build_roleplay_eval_run_artifact,
    roleplay_eval_should_fail_release,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "roleplay_contract_eval_cases.json"
)


def _raw_eval_cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_roleplay_contract_eval_cases_cover_initial_situations() -> None:
    cases = _raw_eval_cases()
    situation_codes = {str(case["situation_code"]) for case in cases}

    assert {
        "first_visit",
        "follow_up",
        "proposal_review",
        "price_negotiation",
        "renewal",
        "complaint_recovery",
    }.issubset(situation_codes)


def test_roleplay_contract_deterministic_eval_harness_reports_baseline() -> None:
    run = RoleplayContractDeterministicEvalHarness().evaluate_cases(_raw_eval_cases())

    assert run.total == 8
    assert run.failed == 0
    assert run.passed == run.total
    by_id = {result.case_id: result for result in run.results}
    assert (
        by_id["first_visit_history_contradiction"].actual_violation_code
        == "ROLEPLAY_HISTORY_CONTRADICTION"
    )
    assert (
        by_id["first_visit_hidden_key_leak"].actual_violation_code
        == "ROLEPLAY_HIDDEN_INFORMATION_LEAK"
    )
    assert by_id["price_negotiation_allows_price_topic"].actual_violation_code is None


def test_roleplay_eval_release_gate_blocks_deterministic_regression() -> None:
    cases = _raw_eval_cases()
    broken_case = dict(cases[0])
    broken_case["expected_violation_code"] = None
    run = RoleplayContractDeterministicEvalHarness().evaluate_cases([broken_case])

    artifact = build_roleplay_eval_run_artifact(
        run=run,
        gate_config=RoleplayEvalReleaseGateConfig.from_mapping(
            {"deterministic_gate_mode": "blocking"}
        ),
        llm_grader_enabled=True,
    )

    assert artifact["deterministic"]["failed"] == 1
    assert artifact["release_gate"]["blocking"] is True
    assert artifact["llm_grader"]["status"] == "not_configured"
    assert roleplay_eval_should_fail_release(artifact) is True


def test_roleplay_eval_release_gate_warn_only_does_not_block() -> None:
    cases = _raw_eval_cases()
    broken_case = dict(cases[0])
    broken_case["expected_violation_code"] = None
    run = RoleplayContractDeterministicEvalHarness().evaluate_cases([broken_case])

    artifact = build_roleplay_eval_run_artifact(
        run=run,
        gate_config=RoleplayEvalReleaseGateConfig.from_mapping(
            {"deterministic_gate_mode": "warn_only"}
        ),
    )

    assert artifact["deterministic"]["failed"] == 1
    assert artifact["release_gate"]["blocking"] is False
    assert roleplay_eval_should_fail_release(artifact) is False
