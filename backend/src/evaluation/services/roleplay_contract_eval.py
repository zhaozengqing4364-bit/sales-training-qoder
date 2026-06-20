from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.business_rules.defaults import DEFAULT_ROLEPLAY_EVAL_RELEASE_GATE
from common.roleplay_contracts import check_roleplay_output
from curriculum_practice.services.roleplay_contracts import (
    RoleplayContractCompiler,
)


@dataclass(frozen=True, slots=True)
class RoleplayContractEvalResult:
    case_id: str
    situation_code: str
    passed: bool
    expected_violation_code: str | None
    actual_violation_code: str | None
    decision: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "situation_code": self.situation_code,
            "passed": self.passed,
            "expected_violation_code": self.expected_violation_code,
            "actual_violation_code": self.actual_violation_code,
            "decision": dict(self.decision),
        }


@dataclass(frozen=True, slots=True)
class RoleplayContractEvalRun:
    total: int
    passed: int
    failed: int
    results: list[RoleplayContractEvalResult]

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "results": [result.as_dict() for result in self.results],
        }


@dataclass(frozen=True, slots=True)
class RoleplayEvalReleaseGateConfig:
    version: str
    enabled: bool
    deterministic_gate_mode: str
    llm_grader_mode: str
    blocking_violation_codes: tuple[str, ...]
    artifact_retention_days: int

    @classmethod
    def from_mapping(
        cls,
        value: dict[str, Any] | None = None,
    ) -> RoleplayEvalReleaseGateConfig:
        payload = {
            **DEFAULT_ROLEPLAY_EVAL_RELEASE_GATE,
            **(value if isinstance(value, dict) else {}),
        }
        return cls(
            version=str(payload.get("version") or "roleplay_eval_release_gate_v1"),
            enabled=bool(payload.get("enabled", True)),
            deterministic_gate_mode=str(
                payload.get("deterministic_gate_mode") or "blocking"
            ),
            llm_grader_mode=str(payload.get("llm_grader_mode") or "warn_only"),
            blocking_violation_codes=tuple(
                str(item)
                for item in payload.get("blocking_violation_codes", [])
                if str(item).strip()
            ),
            artifact_retention_days=int(payload.get("artifact_retention_days") or 30),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "enabled": self.enabled,
            "deterministic_gate_mode": self.deterministic_gate_mode,
            "llm_grader_mode": self.llm_grader_mode,
            "blocking_violation_codes": list(self.blocking_violation_codes),
            "artifact_retention_days": self.artifact_retention_days,
        }


def build_roleplay_eval_run_artifact(
    *,
    run: RoleplayContractEvalRun,
    gate_config: RoleplayEvalReleaseGateConfig | None = None,
    llm_grader_enabled: bool = False,
) -> dict[str, Any]:
    config = gate_config or RoleplayEvalReleaseGateConfig.from_mapping()
    deterministic_status = "passed" if run.failed == 0 else "failed"
    should_block = (
        config.enabled
        and config.deterministic_gate_mode == "blocking"
        and run.failed > 0
    )
    return {
        "schema_version": "roleplay_contract_eval_run_v1",
        "release_gate": {
            **config.as_dict(),
            "deterministic_status": deterministic_status,
            "blocking": should_block,
        },
        "deterministic": run.as_dict(),
        "llm_grader": {
            "enabled": llm_grader_enabled,
            "mode": config.llm_grader_mode,
            "status": "not_configured" if llm_grader_enabled else "skipped",
            "blocking": False,
            "summary": (
                "LLM grader is intentionally excluded from realtime path; configure a provider before enabling blocking mode."
                if llm_grader_enabled
                else "LLM grader skipped."
            ),
        },
    }


def roleplay_eval_should_fail_release(artifact: dict[str, Any]) -> bool:
    release_gate = artifact.get("release_gate")
    if not isinstance(release_gate, dict):
        return False
    return bool(release_gate.get("blocking"))


class RoleplayContractDeterministicEvalHarness:
    """Deterministic Roleplay Contract regression harness.

    This is the release-gate friendly layer. It intentionally does not call an
    LLM judge; style and human-review graders can be layered on top of this data
    set without entering the realtime path.
    """

    def evaluate_cases(self, raw_cases: list[dict[str, Any]]) -> RoleplayContractEvalRun:
        results = [self.evaluate_case(raw_case) for raw_case in raw_cases]
        passed = sum(1 for result in results if result.passed)
        return RoleplayContractEvalRun(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    def evaluate_case(self, raw_case: dict[str, Any]) -> RoleplayContractEvalResult:
        case_id = str(raw_case.get("id") or "")
        situation_code = str(raw_case.get("situation_code") or "")
        expected = raw_case.get("expected_violation_code")
        expected_violation = str(expected) if expected else None
        text = str(raw_case.get("assistant_text") or "")
        runtime_state = raw_case.get("runtime_state")
        if not isinstance(runtime_state, dict):
            runtime_state = {}
        current_visible_keys = raw_case.get("current_visible_keys")
        if not isinstance(current_visible_keys, list):
            current_visible_keys = None
        contract = self._contract_for_case(raw_case)
        decision = check_roleplay_output(
            contract=contract,
            text=text,
            runtime_state=runtime_state,
            current_visible_keys=[
                str(item) for item in current_visible_keys
            ]
            if current_visible_keys is not None
            else None,
            current_sales_stage=raw_case.get("current_sales_stage"),
        )
        actual = decision.get("violation_code")
        return RoleplayContractEvalResult(
            case_id=case_id,
            situation_code=situation_code,
            passed=actual == expected_violation,
            expected_violation_code=expected_violation,
            actual_violation_code=str(actual) if actual else None,
            decision=decision,
        )

    def _contract_for_case(self, raw_case: dict[str, Any]) -> dict[str, Any]:
        situation_code = str(raw_case.get("situation_code") or "general_practice")
        persona = {
            "id": f"eval-persona-{situation_code}",
            "persona_policy": {
                "roleplay_defaults": {
                    "situation_code": situation_code,
                    "relationship_context": raw_case.get("relationship_context") or {},
                    "visible_information_keys": raw_case.get("initial_visible_keys")
                    or [],
                    "hidden_information_keys": raw_case.get("hidden_information_keys")
                    or [],
                    "forbidden_claim_patterns": raw_case.get(
                        "forbidden_claim_patterns"
                    )
                    or [],
                }
            },
        }
        return RoleplayContractCompiler().compile_from_persona_sync(
            persona,
            actor_id="roleplay_eval",
            compiled_at="2026-05-26T00:00:00+00:00",
        )
