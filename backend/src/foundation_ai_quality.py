"""Deterministic quality gate for newcomer Foundation AI contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_coach.contracts import (
    CoachAnswerEvaluationOutput,
    CoachCardGenerationOutput,
)
from ai_platform.errors import AIPlatformError
from ai_platform.schemas import OutputSchemaRegistry
from audio_assessment.contracts import AudioScoringAIOutput
from learning.contracts import QuestionGenerationOutput
from learning.quiz_runtime import ShortAnswerScoringOutput
from readiness.contracts import AISummaryDraft

FOUNDATION_READINESS_SUMMARY_OUTPUT_SCHEMA = "readiness-summary-output-v1"
DEFAULT_FOUNDATION_AI_GOLD_SET = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "golden"
    / "foundation"
    / "foundation-ai-quality-v1.json"
)

FoundationAICapability = Literal[
    "question_generation",
    "short_answer_scoring",
    "audio_scoring",
    "coach_card_generation",
    "coach_answer_evaluation",
    "readiness_dossier_summary",
]

FOUNDATION_AI_OUTPUT_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "question-generation-output-v1": QuestionGenerationOutput,
    "short-answer-output-v1": ShortAnswerScoringOutput,
    "audio-scoring-output-v1": AudioScoringAIOutput,
    "coach-card-generation-output-v1": CoachCardGenerationOutput,
    "coach-answer-evaluation-output-v1": CoachAnswerEvaluationOutput,
    FOUNDATION_READINESS_SUMMARY_OUTPUT_SCHEMA: AISummaryDraft,
}


class FoundationAIQualityUsage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_minor_units: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)


class FoundationAIQualityCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1, max_length=160)
    capability: FoundationAICapability
    business_purpose: str = Field(min_length=1, max_length=160)
    prompt_template_id: str = Field(min_length=1, max_length=160)
    prompt_revision_id: str = Field(min_length=1, max_length=160)
    output_schema_version: str = Field(min_length=1, max_length=160)
    expected_behavior: Literal["accept", "reject", "degrade"]
    instruction: str = Field(min_length=1, max_length=20_000)
    output: dict[str, Any] | None = None
    repeat_outputs: tuple[dict[str, Any], ...] = Field(
        default_factory=tuple,
        max_length=5,
    )
    allowed_evidence_refs: tuple[str, ...] = Field(
        default_factory=tuple,
        max_length=500,
    )
    transcript: str | None = Field(default=None, max_length=1_000_000)
    required_phrases: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    forbidden_phrases: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    failure_code: str | None = Field(default=None, max_length=160)
    formal_result: bool = False
    formal_scoring: bool = False
    usage: FoundationAIQualityUsage = Field(
        default_factory=lambda: FoundationAIQualityUsage(
            input_tokens=0,
            output_tokens=0,
            cost_minor_units=0,
            currency="CNY",
        )
    )
    max_cost_minor_units: int = Field(default=10, ge=0)


class FoundationAIQualityThresholds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_schema_validity_rate: float = Field(ge=0, le=1)
    minimum_invalid_rejection_rate: float = Field(ge=0, le=1)
    minimum_evidence_coverage_rate: float = Field(ge=0, le=1)
    maximum_factual_error_rate: float = Field(ge=0, le=1)
    maximum_hallucination_reference_rate: float = Field(ge=0, le=1)
    minimum_degradation_contract_rate: float = Field(ge=0, le=1)
    minimum_stability_rate: float = Field(ge=0, le=1)
    maximum_total_cost_minor_units: int = Field(ge=0)


class FoundationAIQualityManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["foundation_ai_quality_v1"]
    thresholds: FoundationAIQualityThresholds
    cases: tuple[FoundationAIQualityCase, ...] = Field(min_length=8, max_length=500)


def build_foundation_ai_quality_schema_registry() -> OutputSchemaRegistry:
    registry = OutputSchemaRegistry()
    for version, schema in FOUNDATION_AI_OUTPUT_SCHEMA_MODELS.items():
        registry.register_output(version, schema)
    return registry


def load_foundation_ai_quality_manifest(
    path: Path = DEFAULT_FOUNDATION_AI_GOLD_SET,
) -> FoundationAIQualityManifest:
    return FoundationAIQualityManifest.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def evaluate_foundation_ai_quality(
    manifest: FoundationAIQualityManifest,
    *,
    registry: OutputSchemaRegistry | None = None,
) -> dict[str, Any]:
    schemas = registry or build_foundation_ai_quality_schema_registry()
    results: list[dict[str, Any]] = []
    accepted = rejected = degraded = 0
    schema_valid = invalid_rejected = degradation_valid = stable = 0
    evidence_covered = evidence_total = 0
    factual_errors = factual_checks = 0
    unknown_refs = total_refs = 0
    total_cost = 0

    for case in manifest.cases:
        result: dict[str, Any] = {
            "case_id": case.case_id,
            "capability": case.capability,
            "expected_behavior": case.expected_behavior,
            "passed": False,
            "failures": [],
        }
        failures: list[str] = result["failures"]
        total_cost += case.usage.cost_minor_units
        if case.usage.cost_minor_units > case.max_cost_minor_units:
            failures.append("case_cost_exceeded")

        if case.expected_behavior == "accept":
            accepted += 1
            normalized = _validate_output(schemas, case, case.output)
            if normalized is None:
                failures.append("schema_invalid")
            else:
                schema_valid += 1
                covered, coverage_total, refs, unknown = _evidence_result(
                    case,
                    normalized,
                )
                evidence_covered += covered
                evidence_total += coverage_total
                total_refs += refs
                unknown_refs += unknown
                errors, checks = _factual_result(case, normalized)
                factual_errors += errors
                factual_checks += checks
                if covered != coverage_total:
                    failures.append("evidence_coverage_incomplete")
                if unknown:
                    failures.append("unknown_evidence_reference")
                if errors:
                    failures.append("factual_contract_failed")
                if _is_stable(schemas, case, normalized):
                    stable += 1
                else:
                    failures.append("unstable_output")
        elif case.expected_behavior == "reject":
            rejected += 1
            if _validate_output(schemas, case, case.output) is None:
                invalid_rejected += 1
            else:
                failures.append("invalid_output_was_accepted")
        else:
            degraded += 1
            valid_degradation = (
                case.output is None
                and bool(case.failure_code)
                and not case.formal_result
            )
            if valid_degradation:
                degradation_valid += 1
                stable += 1
            else:
                failures.append("degradation_contract_failed")

        result["passed"] = not failures
        result["cost_minor_units"] = case.usage.cost_minor_units
        results.append(result)

    schema_validity_rate = _rate(schema_valid, accepted)
    invalid_rejection_rate = _rate(invalid_rejected, rejected)
    evidence_coverage_rate = _rate(evidence_covered, evidence_total)
    factual_error_rate = _rate(factual_errors, factual_checks)
    hallucination_reference_rate = _rate(unknown_refs, total_refs)
    degradation_contract_rate = _rate(degradation_valid, degraded)
    stability_rate = _rate(stable, accepted + degraded)
    metrics = {
        "schema_validity_rate": schema_validity_rate,
        "invalid_rejection_rate": invalid_rejection_rate,
        "evidence_coverage_rate": evidence_coverage_rate,
        "factual_error_rate": factual_error_rate,
        "hallucination_reference_rate": hallucination_reference_rate,
        "degradation_contract_rate": degradation_contract_rate,
        "stability_rate": stability_rate,
        "total_cost_minor_units": total_cost,
        "currency": _single_currency(manifest),
    }
    thresholds = manifest.thresholds
    gate_failures = [
        name
        for name, passed in (
            (
                "schema_validity_rate",
                schema_validity_rate >= thresholds.minimum_schema_validity_rate,
            ),
            (
                "invalid_rejection_rate",
                invalid_rejection_rate >= thresholds.minimum_invalid_rejection_rate,
            ),
            (
                "evidence_coverage_rate",
                evidence_coverage_rate >= thresholds.minimum_evidence_coverage_rate,
            ),
            (
                "factual_error_rate",
                factual_error_rate <= thresholds.maximum_factual_error_rate,
            ),
            (
                "hallucination_reference_rate",
                hallucination_reference_rate
                <= thresholds.maximum_hallucination_reference_rate,
            ),
            (
                "degradation_contract_rate",
                degradation_contract_rate
                >= thresholds.minimum_degradation_contract_rate,
            ),
            (
                "stability_rate",
                stability_rate >= thresholds.minimum_stability_rate,
            ),
            (
                "total_cost_minor_units",
                total_cost <= thresholds.maximum_total_cost_minor_units,
            ),
        )
        if not passed
    ]
    if any(not item["passed"] for item in results):
        gate_failures.append("case_failures")
    return {
        "contract_version": manifest.contract_version,
        "status": "passed" if not gate_failures else "failed",
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_sha256": _canonical_hash(manifest.model_dump(mode="json")),
        "case_count": len(manifest.cases),
        "capabilities": sorted({case.capability for case in manifest.cases}),
        "metrics": metrics,
        "thresholds": thresholds.model_dump(mode="json"),
        "gate_failures": gate_failures,
        "results": results,
    }


def _validate_output(
    registry: OutputSchemaRegistry,
    case: FoundationAIQualityCase,
    output: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if output is None:
        return None
    try:
        return registry.validate_output(case.output_schema_version, output)
    except AIPlatformError:
        return None


def _evidence_result(
    case: FoundationAIQualityCase,
    output: dict[str, Any],
) -> tuple[int, int, int, int]:
    allowed = set(case.allowed_evidence_refs)
    refs = _collect_refs(output)
    unknown = len([item for item in refs if item not in allowed])
    if case.capability == "question_generation":
        items = output.get("questions", [])
        covered = sum(bool(item.get("source_anchor_ids")) for item in items)
        return covered, len(items), len(refs), unknown
    if case.capability == "short_answer_scoring":
        items = output.get("answers", [])
        covered = sum(bool(item.get("rubric_evidence")) for item in items)
        return covered, len(items), len(refs), unknown
    if case.capability == "audio_scoring":
        dimensions = output.get("dimension_scores", [])
        spans = output.get("evidence_spans", [])
        covered = sum(
            any(
                span.get("dimension_key") == dimension.get("dimension_key")
                and bool(span.get("quote"))
                and bool(case.transcript)
                and str(span["quote"]) in str(case.transcript)
                for span in spans
            )
            for dimension in dimensions
        )
        return covered, len(dimensions), len(refs), unknown
    if case.capability == "coach_card_generation":
        items = output.get("cards", [])
        covered = sum(bool(item.get("source_ref_ids")) for item in items)
        return covered, len(items), len(refs), unknown
    if case.capability == "coach_answer_evaluation":
        covered = int(
            bool(output.get("source_ref_ids"))
            and bool(output.get("evidence_from_answer"))
        )
        return covered, 1, len(refs), unknown
    facts = output.get("facts", [])
    covered = sum(bool(item.get("evidence_ids")) for item in facts)
    return covered, len(facts), len(refs), unknown


def _collect_refs(value: Any, *, key: str | None = None) -> list[str]:
    if isinstance(value, dict):
        refs: list[str] = []
        for nested_key, nested_value in value.items():
            refs.extend(_collect_refs(nested_value, key=str(nested_key)))
        return refs
    if isinstance(value, list):
        if key in {"source_anchor_ids", "source_ref_ids", "evidence_ids"}:
            return [str(item) for item in value]
        refs = []
        for item in value:
            refs.extend(_collect_refs(item, key=key))
        return refs
    return []


def _factual_result(
    case: FoundationAIQualityCase,
    output: dict[str, Any],
) -> tuple[int, int]:
    serialized = json.dumps(output, ensure_ascii=False, sort_keys=True)
    errors = sum(phrase not in serialized for phrase in case.required_phrases)
    errors += sum(phrase in serialized for phrase in case.forbidden_phrases)
    return errors, len(case.required_phrases) + len(case.forbidden_phrases)


def _is_stable(
    registry: OutputSchemaRegistry,
    case: FoundationAIQualityCase,
    normalized: dict[str, Any],
) -> bool:
    for output in case.repeat_outputs:
        repeated = _validate_output(registry, case, output)
        if repeated is None:
            return False
        covered, coverage_total, _, unknown = _evidence_result(case, repeated)
        factual_errors, _ = _factual_result(case, repeated)
        if covered != coverage_total or unknown or factual_errors:
            return False
        if not _same_stability_contract(case.capability, normalized, repeated):
            return False
    return True


def _same_stability_contract(
    capability: FoundationAICapability,
    baseline: dict[str, Any],
    repeated: dict[str, Any],
) -> bool:
    """Compare business decisions while allowing harmless language variation."""

    if capability == "question_generation":
        return _question_generation_signature(baseline) == _question_generation_signature(
            repeated
        )
    if capability == "short_answer_scoring":
        return _short_answer_decisions_match(baseline, repeated)
    if capability == "audio_scoring":
        return _audio_decisions_match(baseline, repeated)
    if capability == "coach_card_generation":
        return _coach_card_signature(baseline) == _coach_card_signature(repeated)
    if capability == "coach_answer_evaluation":
        return _coach_evaluation_decisions_match(baseline, repeated)
    return _readiness_summary_signature(baseline) == _readiness_summary_signature(
        repeated
    )


def _question_generation_signature(output: dict[str, Any]) -> tuple[object, ...]:
    return tuple(
        (
            str(item.get("question_type")),
            tuple(sorted(str(ref) for ref in item.get("source_anchor_ids", []))),
            sum(bool(option.get("is_correct")) for option in item.get("options", [])),
        )
        for item in output.get("questions", [])
    )


def _short_answer_decisions_match(
    baseline: dict[str, Any],
    repeated: dict[str, Any],
) -> bool:
    baseline_answers = {
        str(item.get("question_revision_id")): item
        for item in baseline.get("answers", [])
    }
    repeated_answers = {
        str(item.get("question_revision_id")): item
        for item in repeated.get("answers", [])
    }
    if baseline_answers.keys() != repeated_answers.keys():
        return False
    for question_id, expected in baseline_answers.items():
        actual = repeated_answers[question_id]
        if not _close(float(expected["max_points"]), float(actual["max_points"]), 0.01):
            return False
        expected_ratio = float(expected["awarded_points"]) / float(
            expected["max_points"]
        )
        actual_ratio = float(actual["awarded_points"]) / float(actual["max_points"])
        if not _close(expected_ratio, actual_ratio, 0.1):
            return False
        if sorted(bool(item.get("met")) for item in expected.get("rubric_evidence", [])) != sorted(
            bool(item.get("met")) for item in actual.get("rubric_evidence", [])
        ):
            return False
    return True


def _audio_decisions_match(
    baseline: dict[str, Any],
    repeated: dict[str, Any],
) -> bool:
    baseline_dimensions = {
        str(item.get("dimension_key")): item
        for item in baseline.get("dimension_scores", [])
    }
    repeated_dimensions = {
        str(item.get("dimension_key")): item
        for item in repeated.get("dimension_scores", [])
    }
    if baseline_dimensions.keys() != repeated_dimensions.keys():
        return False
    for dimension_key, expected in baseline_dimensions.items():
        actual = repeated_dimensions[dimension_key]
        if not _close(float(expected["score"]), float(actual["score"]), 10.0):
            return False
        if not _close(
            float(expected.get("uncertainty", 0)),
            float(actual.get("uncertainty", 0)),
            0.25,
        ):
            return False
    return bool(baseline.get("critical_flags")) == bool(
        repeated.get("critical_flags")
    )


def _coach_card_signature(output: dict[str, Any]) -> tuple[object, ...]:
    cards = output.get("cards", [])
    return (
        len(cards),
        len({str(item.get("card_type")) for item in cards}),
        tuple(
            sorted(
                tuple(sorted(str(ref) for ref in item.get("source_ref_ids", [])))
                for item in cards
            )
        ),
    )


def _coach_evaluation_decisions_match(
    baseline: dict[str, Any],
    repeated: dict[str, Any],
) -> bool:
    # ``mastered`` is retained as a model draft for audit only. The Coach domain
    # computes the authoritative decision from score, uncertainty, and the frozen
    # profile rule, so draft label drift must not masquerade as business drift.
    return (
        _close(
            float(baseline.get("score_percent", 0)),
            float(repeated.get("score_percent", 0)),
            10.0,
        )
        and _close(
            float(baseline.get("uncertainty", 0)),
            float(repeated.get("uncertainty", 0)),
            0.25,
        )
        and sorted(str(item) for item in baseline.get("source_ref_ids", []))
        == sorted(str(item) for item in repeated.get("source_ref_ids", []))
    )


def _readiness_summary_signature(output: dict[str, Any]) -> tuple[object, ...]:
    facts = output.get("facts", [])
    return (
        len(facts),
        tuple(
            sorted(
                tuple(sorted(str(ref) for ref in item.get("evidence_ids", [])))
                for item in facts
            )
        ),
        tuple(
            bool(output.get(key))
            for key in (
                "calculations",
                "inferences",
                "recommendations",
                "limitations",
            )
        ),
    )


def _close(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def _rate(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 6)


def _single_currency(manifest: FoundationAIQualityManifest) -> str:
    currencies = {case.usage.currency for case in manifest.cases}
    return next(iter(currencies)) if len(currencies) == 1 else "MIXED"


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "DEFAULT_FOUNDATION_AI_GOLD_SET",
    "FOUNDATION_AI_OUTPUT_SCHEMA_MODELS",
    "FOUNDATION_READINESS_SUMMARY_OUTPUT_SCHEMA",
    "FoundationAIQualityCase",
    "FoundationAIQualityManifest",
    "build_foundation_ai_quality_schema_registry",
    "evaluate_foundation_ai_quality",
    "load_foundation_ai_quality_manifest",
]
