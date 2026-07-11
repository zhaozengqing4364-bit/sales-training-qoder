"""Configured Evaluation ports without concrete scenario imports."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evaluation.ports.evidence import SessionEvidencePort
from evaluation.ports.scenario import EvaluationScenarioRegistry

_scenario_registry: EvaluationScenarioRegistry | None = None
_evidence_port_factory: Callable[[Any], SessionEvidencePort] | None = None


def configure_evaluation_scenario_registry(
    registry: EvaluationScenarioRegistry,
) -> None:
    if not registry.is_frozen:
        raise ValueError("Evaluation scenario registry must be frozen before configuration")
    global _scenario_registry
    _scenario_registry = registry


def get_evaluation_scenario_registry() -> EvaluationScenarioRegistry | None:
    return _scenario_registry


def configure_session_evidence_port_factory(
    factory: Callable[[Any], SessionEvidencePort],
) -> None:
    global _evidence_port_factory
    _evidence_port_factory = factory


def get_configured_session_evidence_port(db: Any) -> SessionEvidencePort | None:
    return _evidence_port_factory(db) if _evidence_port_factory is not None else None
