"""Frozen registry and DTOs for scenario-specific Evaluation capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from common.error_handling.result import Result
from evaluation.ports.evidence import SessionEvidence


@dataclass(frozen=True, slots=True)
class EvaluationDimensionResult:
    name: str
    score: float
    weight: float
    description: str = ""
    dimension_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationScenarioResult:
    session_id: str
    generated_at: datetime
    overall_score: float
    dimension_scores: list[EvaluationDimensionResult] = field(default_factory=list)
    stage_summaries: list[dict[str, Any]] = field(default_factory=list)
    key_strengths: list[str] = field(default_factory=list)
    key_improvements: list[str] = field(default_factory=list)
    detailed_feedback: str = ""
    recommendations: list[str] = field(default_factory=list)
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    score_basis: str | None = None
    ruleset_source: str | None = None
    scoring_metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class EvaluationScenarioInput:
    evidence: SessionEvidence
    options: dict[str, Any] = field(default_factory=dict)


class EvaluationScenarioPort(Protocol):
    async def evaluate(
        self,
        scenario_input: EvaluationScenarioInput,
    ) -> Result[EvaluationScenarioResult]: ...


EvaluationScenarioFactory = Callable[[Any], EvaluationScenarioPort]


class EvaluationScenarioRegistry:
    """Register once during app composition, then dispatch without concrete imports."""

    def __init__(self) -> None:
        self._factories: dict[str, EvaluationScenarioFactory] = {}
        self._frozen = False

    def register(
        self,
        scenario_type: str,
        factory: EvaluationScenarioFactory,
    ) -> None:
        if self._frozen:
            raise RuntimeError("Evaluation scenario registry is frozen")
        key = self._normalize(scenario_type)
        if key in self._factories:
            raise ValueError(f"Evaluation scenario already registered: {key}")
        self._factories[key] = factory

    def freeze(self) -> None:
        self._frozen = True

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def scenario_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    async def evaluate(
        self,
        scenario_type: str,
        *,
        db: Any,
        scenario_input: EvaluationScenarioInput,
    ) -> Result[EvaluationScenarioResult]:
        if not self._frozen:
            return Result.fail("[EVALUATION_SCENARIO_REGISTRY_NOT_FROZEN]")
        if not scenario_input.evidence.is_evaluable:
            return Result.fail("[EVALUATION_EVIDENCE_INSUFFICIENT]")
        factory = self._factories.get(self._normalize(scenario_type))
        if factory is None:
            return Result.fail("[EVALUATION_SCENARIO_NOT_CONFIGURED]")
        return await factory(db).evaluate(scenario_input)

    @staticmethod
    def _normalize(scenario_type: str) -> str:
        return str(scenario_type or "").strip().lower()
