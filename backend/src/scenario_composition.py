"""Application-root registration of concrete Evaluation scenario adapters."""

from __future__ import annotations

from evaluation.adapters.sql_session_evidence import SqlSessionEvidencePort
from evaluation.composition import (
    configure_evaluation_scenario_registry,
    configure_session_evidence_port_factory,
)
from evaluation.ports.scenario import EvaluationScenarioRegistry
from presentation_coach.services.presentation_evaluation_adapter import (
    PresentationEvaluationAdapter,
)
from sales_bot.services.evaluation_evidence_adapter import (
    load_legacy_sales_session_evidence,
)


def build_evaluation_scenario_registry() -> EvaluationScenarioRegistry:
    registry = EvaluationScenarioRegistry()
    registry.register("presentation", PresentationEvaluationAdapter)
    registry.freeze()
    return registry


def configure_evaluation_scenarios() -> None:
    configure_evaluation_scenario_registry(build_evaluation_scenario_registry())
    configure_session_evidence_port_factory(
        lambda db: SqlSessionEvidencePort(
            db,
            legacy_loader=load_legacy_sales_session_evidence,
        )
    )
