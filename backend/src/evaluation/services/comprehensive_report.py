"""
Comprehensive Report Service

Requirements: C4 - Implement ComprehensiveReportService

Features:
- Aggregate stage evaluation results
- Generate comprehensive performance report
- Calculate overall scores and trends
- Provide actionable recommendations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.evaluation.services.staged_evaluation import StagedEvaluationService, StageEvaluationResult
from src.prompt_templates.service import PromptTemplateService
from src.common.ai.llm_service import LLMService
from src.common.error_handling.result import Result


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""

    name: str
    score: float  # 0-100
    weight: float
    description: str = ""


@dataclass
class ComprehensiveReport:
    """Comprehensive evaluation report."""

    session_id: str
    generated_at: datetime
    overall_score: float  # 0-100
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    stage_summaries: list[dict] = field(default_factory=list)
    key_strengths: list[str] = field(default_factory=list)
    key_improvements: list[str] = field(default_factory=list)
    detailed_feedback: str = ""
    recommendations: list[str] = field(default_factory=list)
    comparison_to_baseline: dict | None = None


class ComprehensiveReportService:
    """Service for generating comprehensive evaluation reports.

    Aggregates stage evaluations into a comprehensive report:
    - Overall scoring across dimensions
    - Trend analysis across stages
    - Key strengths and areas for improvement
    - Actionable recommendations
    """

    # Default dimension weights (can be configured per scenario)
    DEFAULT_DIMENSIONS = {
        "communication": 0.25,
        "product_knowledge": 0.20,
        "problem_solving": 0.20,
        "customer_focus": 0.20,
        "professionalism": 0.15,
    }

    def __init__(
        self,
        db_session: AsyncSession,
        staged_eval_service: StagedEvaluationService,
        prompt_service: PromptTemplateService,
        llm_service: LLMService,
    ):
        """Initialize service.

        Args:
            db_session: Database session
            staged_eval_service: Staged evaluation service
            prompt_service: Prompt template service
            llm_service: LLM service
        """
        self.db = db_session
        self.staged_eval = staged_eval_service
        self.prompt_service = prompt_service
        self.llm = llm_service

    async def generate_report(
        self,
        session_id: str,
        scenario_type: str = "sales",
    ) -> Result[ComprehensiveReport]:
        """Generate comprehensive report for a session.

        Args:
            session_id: Practice session ID
            scenario_type: Type of scenario

        Returns:
            Result with comprehensive report
        """
        try:
            # Get all stage evaluations
            stage_results = await self.staged_eval.get_stage_results(session_id)

            if not stage_results:
                return Result.fail("[NO_STAGE_RESULTS]")

            # Calculate dimension scores
            dimension_scores = self._calculate_dimension_scores(stage_results)

            # Calculate overall score
            overall_score = self._calculate_overall_score(dimension_scores)

            # Aggregate strengths and improvements
            key_strengths = self._aggregate_strengths(stage_results)
            key_improvements = self._aggregate_improvements(stage_results)

            # Generate stage summaries
            stage_summaries = self._generate_stage_summaries(stage_results)

            # Generate detailed feedback using LLM
            feedback_result = await self._generate_detailed_feedback(
                session_id, stage_results, scenario_type
            )
            detailed_feedback = feedback_result if feedback_result.is_success else ""

            # Generate recommendations
            recommendations = await self._generate_recommendations(
                dimension_scores, key_improvements, scenario_type
            )

            report = ComprehensiveReport(
                session_id=session_id,
                generated_at=datetime.utcnow(),
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                stage_summaries=stage_summaries,
                key_strengths=key_strengths,
                key_improvements=key_improvements,
                detailed_feedback=detailed_feedback.value if isinstance(detailed_feedback, Result) else detailed_feedback,
                recommendations=recommendations,
            )

            # Store report in database
            await self._store_report(report)

            return Result.ok(report)

        except Exception as e:
            return Result.fail(f"[REPORT_GENERATION_ERROR:{str(e)}]")

    async def get_report(
        self,
        session_id: str,
    ) -> ComprehensiveReport | None:
        """Get existing comprehensive report for a session.

        Args:
            session_id: Session ID

        Returns:
            ComprehensiveReport or None if not found
        """
        from src.common.db.models import ComprehensiveReport as DBModel

        result = await self.db.execute(
            select(DBModel).where(DBModel.session_id == session_id)
        )
        db_report = result.scalar_one_or_none()

        if not db_report:
            return None

        return ComprehensiveReport(
            session_id=db_report.session_id,
            generated_at=db_report.generated_at,
            overall_score=db_report.overall_score,
            dimension_scores=[
                DimensionScore(**d) for d in db_report.dimension_scores
            ],
            stage_summaries=db_report.stage_summaries,
            key_strengths=db_report.key_strengths,
            key_improvements=db_report.key_improvements,
            detailed_feedback=db_report.detailed_feedback,
            recommendations=db_report.recommendations,
            comparison_to_baseline=db_report.comparison_to_baseline,
        )

    def _calculate_dimension_scores(
        self,
        stage_results: list[StageEvaluationResult],
    ) -> list[DimensionScore]:
        """Calculate aggregated scores for each dimension.

        Args:
            stage_results: List of stage evaluation results

        Returns:
            List of dimension scores
        """
        # Collect scores per dimension across stages
        dimension_values: dict[str, list[float]] = {}

        for stage in stage_results:
            for dim_name, score in stage.scores.items():
                if dim_name not in dimension_values:
                    dimension_values[dim_name] = []
                dimension_values[dim_name].append(score)

        # Calculate weighted averages
        dimension_scores = []
        for dim_name, weight in self.DEFAULT_DIMENSIONS.items():
            values = dimension_values.get(dim_name, [])
            avg_score = sum(values) / len(values) if values else 50.0

            dimension_scores.append(DimensionScore(
                name=dim_name,
                score=avg_score,
                weight=weight,
                description=self._get_dimension_description(dim_name),
            ))

        return dimension_scores

    def _calculate_overall_score(
        self,
        dimension_scores: list[DimensionScore],
    ) -> float:
        """Calculate overall weighted score.

        Args:
            dimension_scores: List of dimension scores

        Returns:
            Overall score (0-100)
        """
        if not dimension_scores:
            return 0.0

        total_weight = sum(ds.weight for ds in dimension_scores)
        weighted_sum = sum(ds.score * ds.weight for ds in dimension_scores)

        return round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0

    def _aggregate_strengths(
        self,
        stage_results: list[StageEvaluationResult],
    ) -> list[str]:
        """Aggregate key strengths from all stages.

        Args:
            stage_results: List of stage results

        Returns:
            List of unique strengths
        """
        strength_counts: dict[str, int] = {}

        for stage in stage_results:
            for strength in stage.strengths:
                strength_counts[strength] = strength_counts.get(strength, 0) + 1

        # Sort by frequency and take top 5
        sorted_strengths = sorted(
            strength_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [s[0] for s in sorted_strengths[:5]]

    def _aggregate_improvements(
        self,
        stage_results: list[StageEvaluationResult],
    ) -> list[str]:
        """Aggregate key improvement areas from all stages.

        Args:
            stage_results: List of stage results

        Returns:
            List of unique improvement areas
        """
        weakness_counts: dict[str, int] = {}

        for stage in stage_results:
            for weakness in stage.weaknesses:
                weakness_counts[weakness] = weakness_counts.get(weakness, 0) + 1

        # Sort by frequency and take top 5
        sorted_weaknesses = sorted(
            weakness_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [w[0] for w in sorted_weaknesses[:5]]

    def _generate_stage_summaries(
        self,
        stage_results: list[StageEvaluationResult],
    ) -> list[dict]:
        """Generate summaries for each stage.

        Args:
            stage_results: List of stage results

        Returns:
            List of stage summaries
        """
        summaries = []

        for stage in stage_results:
            avg_score = sum(stage.scores.values()) / len(stage.scores) if stage.scores else 0

            summaries.append({
                "stage_number": stage.stage_number,
                "start_turn": stage.start_turn,
                "end_turn": stage.end_turn,
                "average_score": round(avg_score, 1),
                "key_points": stage.strengths[:3],
                "summary": stage.summary,
            })

        return summaries

    async def _generate_detailed_feedback(
        self,
        session_id: str,
        stage_results: list[StageEvaluationResult],
        scenario_type: str,
    ) -> Result[str]:
        """Generate detailed feedback using LLM.

        Args:
            session_id: Session ID
            stage_results: Stage evaluation results
            scenario_type: Scenario type

        Returns:
            Result with detailed feedback text
        """
        # Get report generation prompt
        prompt_template = await self.prompt_service.get_template_for_scenario(
            prompt_type="report",
            scenario_type=scenario_type,
        )

        if not prompt_template:
            return Result.fail("[REPORT_PROMPT_NOT_FOUND]")

        # Prepare context
        context = {
            "session_id": session_id,
            "stage_count": len(stage_results),
            "overall_summary": self._format_stage_summaries(stage_results),
        }

        # Call LLM
        result = await self.llm.generate_report(context)

        return result

    async def _generate_recommendations(
        self,
        dimension_scores: list[DimensionScore],
        key_improvements: list[str],
        scenario_type: str,
    ) -> list[str]:
        """Generate actionable recommendations.

        Args:
            dimension_scores: Dimension scores
            key_improvements: Key improvement areas
            scenario_type: Scenario type

        Returns:
            List of recommendations
        """
        recommendations = []

        # Add recommendations based on low-scoring dimensions
        for dim in dimension_scores:
            if dim.score < 60:
                recommendations.append(
                    f"Focus on improving {dim.name.replace('_', ' ')} "
                    f"(current score: {dim.score:.0f}/100)"
                )

        # Add recommendations based on improvement areas
        for improvement in key_improvements[:3]:
            recommendations.append(f"Practice: {improvement}")

        return recommendations[:5]  # Max 5 recommendations

    def _get_dimension_description(self, dimension_name: str) -> str:
        """Get description for a dimension.

        Args:
            dimension_name: Name of dimension

        Returns:
            Description string
        """
        descriptions = {
            "communication": "Clarity, articulation, and listening skills",
            "product_knowledge": "Understanding of products and features",
            "problem_solving": "Ability to identify and resolve issues",
            "customer_focus": "Empathy and customer-centric approach",
            "professionalism": "Professional demeanor and ethics",
        }
        return descriptions.get(dimension_name, "")

    def _format_stage_summaries(
        self,
        stage_results: list[StageEvaluationResult],
    ) -> str:
        """Format stage summaries for LLM context.

        Args:
            stage_results: List of stage results

        Returns:
            Formatted string
        """
        parts = []
        for stage in stage_results:
            parts.append(f"Stage {stage.stage_number}: {stage.summary}")
        return "\n".join(parts)

    async def _store_report(self, report: ComprehensiveReport) -> None:
        """Store report in database.

        Args:
            report: Report to store
        """
        from src.common.db.models import ComprehensiveReport as DBModel

        db_report = DBModel(
            id=uuid4(),
            session_id=report.session_id,
            generated_at=report.generated_at,
            overall_score=report.overall_score,
            dimension_scores=[
                {
                    "name": ds.name,
                    "score": ds.score,
                    "weight": ds.weight,
                    "description": ds.description,
                }
                for ds in report.dimension_scores
            ],
            stage_summaries=report.stage_summaries,
            key_strengths=report.key_strengths,
            key_improvements=report.key_improvements,
            detailed_feedback=report.detailed_feedback,
            recommendations=report.recommendations,
            comparison_to_baseline=report.comparison_to_baseline,
        )

        self.db.add(db_report)
        await self.db.commit()
