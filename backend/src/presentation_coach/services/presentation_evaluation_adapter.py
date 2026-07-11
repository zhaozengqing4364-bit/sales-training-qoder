"""Presentation implementation of the Evaluation scenario port."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from evaluation.ports.scenario import (
    EvaluationScenarioInput,
    EvaluationScenarioResult,
)
from presentation_coach.services.presentation_report_service import (
    PresentationReportService,
)


class PresentationEvaluationAdapter:
    def __init__(self, db: AsyncSession) -> None:
        self._service = PresentationReportService(db)

    async def evaluate(
        self,
        scenario_input: EvaluationScenarioInput,
    ) -> Result[EvaluationScenarioResult]:
        return await self._service.build_report(scenario_input.evidence.session_id)
