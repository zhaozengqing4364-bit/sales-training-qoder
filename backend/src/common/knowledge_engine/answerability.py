from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from common.knowledge_engine.config_repo import KnowledgeAnswerabilityProfileConfig
from common.knowledge_engine.haystack_adapter import KnowledgeHaystackExecutionResult


@dataclass(frozen=True)
class KnowledgeAnswerabilityResult:
    answerability: str
    source_status: str
    covered_required_slots: list[str] = field(default_factory=list)
    missing_required_slots: list[str] = field(default_factory=list)
    covered_optional_slots: list[str] = field(default_factory=list)
    missing_optional_slots: list[str] = field(default_factory=list)
    coverage: dict[str, float] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)


class KnowledgeAnswerabilityEvaluator:
    """Evaluate grounded-answer coverage against profile-defined slots."""

    def __init__(
        self,
        *,
        answerability_profiles: dict[str, KnowledgeAnswerabilityProfileConfig]
        | None = None,
    ) -> None:
        self._answerability_profiles = dict(answerability_profiles or {})

    def evaluate(
        self,
        *,
        profile_key: str,
        rows: list[dict[str, Any]],
        execution_result: KnowledgeHaystackExecutionResult,
    ) -> KnowledgeAnswerabilityResult:
        hit_count = sum(1 for row in rows if isinstance(row, dict))
        executed_query_count = len(execution_result.executed_steps)
        blocked = bool(execution_result.search_failures) and hit_count == 0
        source_status = (
            "blocked"
            if blocked
            else ("ready" if executed_query_count > 0 else "not_run")
        )

        profile = self._answerability_profiles.get(profile_key)
        if profile is None:
            return self._evaluate_count_fallback(
                hit_count=hit_count,
                source_status=source_status,
                execution_result=execution_result,
            )

        covered_slots = _collect_slot_hits(rows)
        covered_required_slots = [
            slot for slot in profile.required_slots if slot in covered_slots
        ]
        covered_optional_slots = [
            slot for slot in profile.optional_slots if slot in covered_slots
        ]
        missing_required_slots = [
            slot for slot in profile.required_slots if slot not in covered_slots
        ]
        missing_optional_slots = [
            slot for slot in profile.optional_slots if slot not in covered_slots
        ]

        required_ratio = _coverage_ratio(covered_required_slots, profile.required_slots)
        optional_ratio = _coverage_ratio(covered_optional_slots, profile.optional_slots)
        all_slots = [*profile.required_slots, *profile.optional_slots]
        overall_ratio = _coverage_ratio(
            [slot for slot in all_slots if slot in covered_slots], all_slots
        )

        if blocked:
            answerability = "blocked"
            blocked_reason = "retrieval_failed"
        elif overall_ratio >= float(profile.sufficient_threshold):
            answerability = "sufficient"
            blocked_reason = None
        elif (
            required_ratio >= float(profile.partial_threshold)
            and len(covered_required_slots) > 0
        ):
            answerability = "partial"
            blocked_reason = None
        else:
            answerability = "insufficient"
            blocked_reason = None

        return KnowledgeAnswerabilityResult(
            answerability=answerability,
            source_status=source_status,
            covered_required_slots=covered_required_slots,
            missing_required_slots=missing_required_slots,
            covered_optional_slots=covered_optional_slots,
            missing_optional_slots=missing_optional_slots,
            coverage={
                "required_ratio": required_ratio,
                "optional_ratio": optional_ratio,
                "overall_ratio": overall_ratio,
            },
            audit={
                "mode": "slot_coverage",
                "profile_key": profile_key,
                "profile_source": profile.profile_source,
                "required_slots": list(profile.required_slots),
                "optional_slots": list(profile.optional_slots),
                "matched_slot_count": len(covered_slots),
                "hit_count": hit_count,
                "executed_query_count": executed_query_count,
                "search_failures": list(execution_result.search_failures),
                "blocked_reason": blocked_reason,
            },
        )

    def _evaluate_count_fallback(
        self,
        *,
        hit_count: int,
        source_status: str,
        execution_result: KnowledgeHaystackExecutionResult,
    ) -> KnowledgeAnswerabilityResult:
        if source_status == "blocked":
            answerability = "blocked"
        elif hit_count >= 3:
            answerability = "sufficient"
        elif hit_count > 0:
            answerability = "partial"
        else:
            answerability = "insufficient"

        return KnowledgeAnswerabilityResult(
            answerability=answerability,
            source_status=source_status,
            coverage={
                "required_ratio": 0.0,
                "optional_ratio": 0.0,
                "overall_ratio": 0.0,
            },
            audit={
                "mode": "count_fallback",
                "hit_count": hit_count,
                "executed_query_count": len(execution_result.executed_steps),
                "search_failures": list(execution_result.search_failures),
                "blocked_reason": "retrieval_failed"
                if source_status == "blocked"
                else None,
            },
        )


def _collect_slot_hits(rows: list[dict[str, Any]]) -> set[str]:
    covered: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_metadata = row.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        slot_values = (
            row.get("slot_hits"),
            row.get("coverage_slots"),
            metadata.get("slot_hits"),
            metadata.get("coverage_slots"),
        )
        for candidate in slot_values:
            if not isinstance(candidate, list):
                continue
            for slot in candidate:
                normalized = str(slot or "").strip()
                if normalized:
                    covered.add(normalized)
    return covered


def _coverage_ratio(covered_slots: list[str], configured_slots: list[str]) -> float:
    total = len(configured_slots)
    if total == 0:
        return 1.0
    return len(covered_slots) / total
