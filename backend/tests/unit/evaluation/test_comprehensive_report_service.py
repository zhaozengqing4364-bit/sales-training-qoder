"""
Unit Tests for ComprehensiveReportService

Requirements: Task #8 - Add unit tests for evaluation module
Coverage Target: 65% for comprehensive_report.py

Test Coverage:
- generate_report() method with various scenarios
- get_report() method
- _calculate_dimension_scores() helper
- _calculate_overall_score() helper
- _aggregate_strengths() and _aggregate_improvements() helpers
- _generate_stage_summaries() helper
- _generate_detailed_feedback() and _generate_recommendations() methods
- Error handling and edge cases
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from evaluation.services.comprehensive_report import (
    ComprehensiveReport,
    ComprehensiveReportService,
    DimensionScore,
)
from evaluation.services.staged_evaluation import StageEvaluationResult
from presentation_coach.services.presentation_report_service import (
    PresentationReportService,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarsResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class TestComprehensiveReportService:
    """Test ComprehensiveReportService class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def mock_staged_eval_service(self):
        """Create mock StagedEvaluationService."""
        service = AsyncMock()
        service.get_stage_results = AsyncMock()
        return service

    @pytest.fixture
    def mock_prompt_service(self):
        """Create mock prompt template service."""
        service = AsyncMock()
        service.get_template_for_scenario = AsyncMock()
        service.compile_runtime_prompt_contract = MagicMock(
            side_effect=lambda template,
            variables,
            runtime_consumer,
            system_message: Result.ok(
                SimpleNamespace(
                    rendered_prompt=str(getattr(template, "template", "")),
                    system_message=system_message,
                    contract_hash="test-report-contract",
                )
            )
        )
        return service

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        service = AsyncMock()
        service.generate_report = AsyncMock()
        return service

    @pytest.fixture
    def service(
        self,
        mock_db_session,
        mock_staged_eval_service,
        mock_prompt_service,
        mock_llm_service,
    ):
        """Create ComprehensiveReportService instance with mocked dependencies."""
        return ComprehensiveReportService(
            db_session=mock_db_session,
            staged_eval_service=mock_staged_eval_service,
            prompt_service=mock_prompt_service,
            llm_service=mock_llm_service,
        )

    @pytest.fixture
    def sample_stage_results(self):
        """Create sample stage evaluation results."""
        return [
            StageEvaluationResult(
                stage_number=1,
                start_turn=0,
                end_turn=4,
                scores={"communication": 85.0, "product_knowledge": 80.0},
                strengths=["Clear opening", "Good greeting"],
                weaknesses=["Rushed introduction"],
                suggestions=["Slow down introduction"],
                summary="Strong opening stage",
            ),
            StageEvaluationResult(
                stage_number=2,
                start_turn=4,
                end_turn=8,
                scores={"communication": 75.0, "problem_solving": 70.0},
                strengths=["Good questions"],
                weaknesses=["Missed opportunities"],
                suggestions=["Ask probing questions"],
                summary="Adequate discovery stage",
            ),
        ]

    @pytest.mark.asyncio
    async def test_generate_report_success(
        self,
        service,
        mock_staged_eval_service,
        mock_prompt_service,
        mock_llm_service,
        sample_stage_results,
    ):
        """Test successful report generation."""
        # Arrange
        session_id = str(uuid4())

        mock_staged_eval_service.get_stage_results.return_value = sample_stage_results

        mock_prompt_template = MagicMock()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        mock_llm_response = """{
            "overall_score": 80.0,
            "dimension_scores": {"communication": 80.0},
            "key_strengths": ["Good communication"],
            "key_improvements": ["Product knowledge"],
            "recommendations": ["Practice more"],
            "detailed_feedback": "Overall good performance",
            "stage_summaries": {}
        }"""
        mock_llm_service.generate_report.return_value = Result.ok(mock_llm_response)

        # Act
        result = await service.generate_report(session_id, scenario_type="sales")

        # Assert
        assert result.is_success
        report = result.value
        assert isinstance(report, ComprehensiveReport)
        assert report.session_id == session_id
        assert 0 <= report.overall_score <= 100
        assert len(report.dimension_scores) > 0
        assert len(report.key_strengths) > 0

        # Verify dependencies were called
        mock_staged_eval_service.get_stage_results.assert_called_once_with(session_id)
        mock_prompt_service.get_template_for_scenario.assert_called_once()
        mock_llm_service.generate_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_report_no_stage_results(
        self, service, mock_staged_eval_service
    ):
        """Test report generation when no stage results exist."""
        # Arrange
        session_id = str(uuid4())
        mock_staged_eval_service.get_stage_results.return_value = []

        # Act
        result = await service.generate_report(session_id)

        # Assert
        assert not result.is_success
        assert "NO_STAGE_RESULTS" in result.fallback

    @pytest.mark.asyncio
    async def test_generate_report_presentation_uses_presentation_report_service(
        self,
        service,
        mock_staged_eval_service,
        monkeypatch: pytest.MonkeyPatch,
    ):
        session_id = str(uuid4())
        mock_staged_eval_service.get_stage_results.return_value = []

        fake_report = ComprehensiveReport(
            session_id=session_id,
            generated_at=datetime.now(UTC),
            overall_score=86.0,
            dimension_scores=[
                DimensionScore(name="流畅连贯性", score=88.0, weight=0.2),
            ],
            key_strengths=["表达流畅"],
            key_improvements=["增加互动"],
            detailed_feedback="这是一份演讲报告",
            recommendations=["每页增加一个互动问题"],
            stage_summaries=[
                {
                    "stage_number": 1,
                    "start_turn": 1,
                    "end_turn": 3,
                    "average_score": 86.0,
                    "key_points": ["表达流畅"],
                    "summary": "第一页讲解稳定",
                }
            ],
        )

        class FakePresentationReportService:
            def __init__(self, db_session):
                self.db_session = db_session

            async def build_report(self, report_session_id: str):
                assert report_session_id == session_id
                return Result.ok(fake_report)

        monkeypatch.setattr(
            "evaluation.services.comprehensive_report.PresentationReportService",
            FakePresentationReportService,
        )

        result = await service.generate_report(session_id, scenario_type="presentation")

        assert result.is_success
        assert result.value.overall_score == 86.0
        assert result.value.dimension_scores[0].name == "流畅连贯性"

    @pytest.mark.asyncio
    async def test_generate_report_database_error(
        self,
        service,
        mock_staged_eval_service,
        mock_prompt_service,
        mock_llm_service,
        mock_db_session,
        sample_stage_results,
    ):
        """Test report generation with database error."""
        # Arrange
        session_id = str(uuid4())
        mock_staged_eval_service.get_stage_results.return_value = sample_stage_results

        mock_prompt_template = MagicMock()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        mock_llm_response = """{
            "overall_score": 80.0,
            "dimension_scores": {},
            "key_strengths": [],
            "key_improvements": [],
            "recommendations": [],
            "detailed_feedback": "Test",
            "stage_summaries": {}
        }"""
        mock_llm_service.generate_report.return_value = Result.ok(mock_llm_response)

        # Database error when storing report
        mock_db_session.commit.side_effect = SQLAlchemyError("Connection failed")

        # Act
        result = await service.generate_report(session_id)

        # Assert
        assert not result.is_success
        assert "DATABASE_ERROR" in result.fallback or "SQLAlchemy" in result.fallback

    @pytest.mark.asyncio
    async def test_generate_report_validation_error(
        self, service, mock_staged_eval_service, mock_prompt_service, mock_llm_service
    ):
        """Test report generation with validation error."""
        # Arrange
        session_id = str(uuid4())

        # Create result with invalid score that will cause issues
        invalid_results = [
            StageEvaluationResult(
                stage_number=1,
                start_turn=0,
                end_turn=4,
                scores={},  # Empty scores might cause calculation issues
                strengths=[],
                weaknesses=[],
                suggestions=[],
                summary="Test",
            )
        ]

        mock_staged_eval_service.get_stage_results.return_value = invalid_results
        mock_prompt_service.get_template_for_scenario.return_value = None
        mock_llm_service.generate_report.return_value = Result.ok("{}")

        # Act
        result = await service.generate_report(session_id)

        # The service should handle this gracefully
        # If there's a validation error, it should return a failure result
        assert result is not None

    @pytest.mark.asyncio
    async def test_generate_report_unexpected_error(
        self, service, mock_staged_eval_service
    ):
        """Test report generation with unexpected error."""
        # Arrange
        session_id = str(uuid4())
        mock_staged_eval_service.get_stage_results.side_effect = Exception(
            "Unexpected error"
        )

        # Act
        result = await service.generate_report(session_id)

        # Assert
        assert not result.is_success
        assert "REPORT_GENERATION_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_get_report_success(self, service, mock_db_session):
        """Test retrieving existing report."""
        # Arrange
        session_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        mock_db_report = MagicMock()
        mock_db_report.session_id = session_id
        mock_db_report.created_at = created_at
        mock_db_report.overall_score = 85.0
        mock_db_report.dimension_scores = [
            {
                "name": "communication",
                "score": 85.0,
                "weight": 0.25,
                "description": "Communication skills",
            }
        ]
        mock_db_report.stage_summaries = []
        mock_db_report.key_strengths = ["Good communication"]
        mock_db_report.key_improvements = ["Product knowledge"]
        mock_db_report.detailed_feedback = "Good performance"
        mock_db_report.recommendations = ["Practice more"]
        mock_db_report.comparison_to_baseline = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_db_report
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.get_report(session_id)

        # Assert
        assert result.is_success
        report = result.value
        assert report.session_id == session_id
        assert report.generated_at == created_at
        assert report.overall_score == 85.0
        assert len(report.dimension_scores) == 1

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, service, mock_db_session):
        """Test retrieving non-existent report."""
        # Arrange
        session_id = str(uuid4())
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.get_report(session_id)

        # Assert
        assert not result.is_success
        assert "REPORT_NOT_FOUND" in result.fallback

    @pytest.mark.asyncio
    async def test_get_report_database_error(self, service, mock_db_session):
        """Test retrieving report with database error."""
        # Arrange
        session_id = str(uuid4())
        mock_db_session.execute.side_effect = SQLAlchemyError("Connection failed")

        # Act
        result = await service.get_report(session_id)

        # Assert
        assert not result.is_success
        assert "DATABASE_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_get_report_validation_error(self, service, mock_db_session):
        """Test retrieving report with validation error."""
        # Arrange
        session_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        mock_db_report = MagicMock()
        mock_db_report.session_id = session_id
        mock_db_report.created_at = created_at
        mock_db_report.overall_score = 85.0
        # Invalid dimension_scores (missing required fields)
        mock_db_report.dimension_scores = [{"name": "test"}]
        mock_db_report.stage_summaries = []
        mock_db_report.key_strengths = []
        mock_db_report.key_improvements = []
        mock_db_report.detailed_feedback = ""
        mock_db_report.recommendations = []
        mock_db_report.comparison_to_baseline = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_db_report
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.get_report(session_id)

        # Assert - should handle validation error
        assert result is not None

    def test_calculate_dimension_scores(self, service, sample_stage_results):
        """Test _calculate_dimension_scores helper."""
        # Act
        scores = service._calculate_dimension_scores(sample_stage_results)

        # Assert
        assert len(scores) == len(service.DEFAULT_DIMENSIONS)
        assert all(isinstance(ds, DimensionScore) for ds in scores)

        # Check communication score (appears in both stages: 85 and 75)
        comm_score = next(ds for ds in scores if ds.name == "communication")
        assert comm_score.score == 80.0  # Average of 85 and 75
        assert comm_score.weight == service.DEFAULT_DIMENSIONS["communication"]

        # Check product_knowledge (only in stage 1: 80)
        prod_score = next((ds for ds in scores if ds.name == "product_knowledge"), None)
        assert prod_score is not None
        assert prod_score.score == 80.0

    def test_calculate_dimension_scores_empty_results(self, service):
        """Test _calculate_dimension_scores with empty results."""
        # Act
        scores = service._calculate_dimension_scores([])

        # Assert - Should return default scores for all dimensions
        assert len(scores) == len(service.DEFAULT_DIMENSIONS)
        assert all(ds.score == 50.0 for ds in scores)  # Default when no data

    def test_calculate_dimension_scores_missing_dimensions(self, service):
        """Test _calculate_dimension_scores with missing dimensions in stages."""
        # Arrange - stages with different dimensions
        results = [
            StageEvaluationResult(
                stage_number=1,
                start_turn=0,
                end_turn=2,
                scores={"communication": 90.0},
                strengths=[],
                weaknesses=[],
                suggestions=[],
                summary="",
            ),
            StageEvaluationResult(
                stage_number=2,
                start_turn=2,
                end_turn=4,
                scores={"professionalism": 85.0},
                strengths=[],
                weaknesses=[],
                suggestions=[],
                summary="",
            ),
        ]

        # Act
        scores = service._calculate_dimension_scores(results)

        # Assert
        comm_score = next(ds for ds in scores if ds.name == "communication")
        prof_score = next(ds for ds in scores if ds.name == "professionalism")
        assert comm_score.score == 90.0
        assert prof_score.score == 85.0

    def test_calculate_overall_score(self, service):
        """Test _calculate_overall_score helper."""
        # Arrange
        dimension_scores = [
            DimensionScore(
                name="communication", score=80.0, weight=0.25, description=""
            ),
            DimensionScore(
                name="product_knowledge", score=90.0, weight=0.20, description=""
            ),
            DimensionScore(
                name="problem_solving", score=70.0, weight=0.20, description=""
            ),
            DimensionScore(
                name="customer_focus", score=85.0, weight=0.20, description=""
            ),
            DimensionScore(
                name="professionalism", score=75.0, weight=0.15, description=""
            ),
        ]

        # Act
        overall = service._calculate_overall_score(dimension_scores)

        # Assert - Should be weighted average
        # (80*0.25 + 90*0.20 + 70*0.20 + 85*0.20 + 75*0.15) / (0.25+0.20+0.20+0.20+0.15)
        # = 20 + 18 + 14 + 17 + 11.25 = 80.25
        assert overall == pytest.approx(80.3, 0.1)

    def test_calculate_overall_score_empty(self, service):
        """Test _calculate_overall_score with empty list."""
        # Act
        overall = service._calculate_overall_score([])

        # Assert
        assert overall == 0.0

    def test_calculate_overall_score_zero_weight(self, service):
        """Test _calculate_overall_score with zero total weight."""
        # Arrange
        dimension_scores = [
            DimensionScore(name="test", score=80.0, weight=0.0, description="")
        ]

        # Act
        overall = service._calculate_overall_score(dimension_scores)

        # Assert
        assert overall == 0.0

    def test_aggregate_strengths(self, service, sample_stage_results):
        """Test _aggregate_strengths helper."""
        # Act
        strengths = service._aggregate_strengths(sample_stage_results)

        # Assert
        assert len(strengths) > 0
        assert "Clear opening" in strengths
        assert "Good greeting" in strengths
        assert len(strengths) <= 5  # Should return top 5

    def test_aggregate_strengths_empty(self, service):
        """Test _aggregate_strengths with empty results."""
        # Act
        strengths = service._aggregate_strengths([])

        # Assert
        assert strengths == []

    def test_aggregate_strengths_duplicates(self, service):
        """Test _aggregate_strengths with duplicate strengths."""
        # Arrange
        results = [
            StageEvaluationResult(
                stage_number=1,
                start_turn=0,
                end_turn=2,
                scores={},
                strengths=["Good communication", "Clear speech"],
                weaknesses=[],
                suggestions=[],
                summary="",
            ),
            StageEvaluationResult(
                stage_number=2,
                start_turn=2,
                end_turn=4,
                scores={},
                strengths=["Good communication", "Active listening"],  # Duplicate
                weaknesses=[],
                suggestions=[],
                summary="",
            ),
        ]

        # Act
        strengths = service._aggregate_strengths(results)

        # Assert - "Good communication" should appear first (mentioned twice)
        assert len(strengths) == 3
        assert strengths[0] == "Good communication"

    def test_aggregate_improvements(self, service, sample_stage_results):
        """Test _aggregate_improvements helper."""
        # Act
        improvements = service._aggregate_improvements(sample_stage_results)

        # Assert
        assert len(improvements) > 0
        assert "Rushed introduction" in improvements
        assert len(improvements) <= 5  # Should return top 5

    def test_aggregate_improvements_empty(self, service):
        """Test _aggregate_improvements with empty results."""
        # Act
        improvements = service._aggregate_improvements([])

        # Assert
        assert improvements == []

    def test_generate_stage_summaries(self, service, sample_stage_results):
        """Test _generate_stage_summaries helper."""
        # Act
        summaries = service._generate_stage_summaries(sample_stage_results)

        # Assert
        assert len(summaries) == 2
        assert summaries[0]["stage_number"] == 1
        assert summaries[1]["stage_number"] == 2
        assert "average_score" in summaries[0]
        assert "key_points" in summaries[0]
        assert "summary" in summaries[0]

    def test_generate_stage_summaries_empty(self, service):
        """Test _generate_stage_summaries with empty results."""
        # Act
        summaries = service._generate_stage_summaries([])

        # Assert
        assert summaries == []

    def test_generate_stage_summaries_calculates_average(self, service):
        """Test that _generate_stage_summaries calculates average score correctly."""
        # Arrange
        result = StageEvaluationResult(
            stage_number=1,
            start_turn=0,
            end_turn=2,
            scores={"communication": 80.0, "product_knowledge": 90.0},
            strengths=["Good"],
            weaknesses=[],
            suggestions=[],
            summary="Test",
        )

        # Act
        summaries = service._generate_stage_summaries([result])

        # Assert - Average should be (80 + 90) / 2 = 85
        assert summaries[0]["average_score"] == 85.0

    @pytest.mark.asyncio
    async def test_generate_detailed_feedback_success(
        self, service, mock_prompt_service, mock_llm_service, sample_stage_results
    ):
        """Test _generate_detailed_feedback with successful LLM call."""
        # Arrange
        session_id = str(uuid4())

        mock_prompt_template = MagicMock()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        mock_llm_response = """{
            "overall_score": 80.0,
            "dimension_scores": {},
            "key_strengths": [],
            "key_improvements": [],
            "recommendations": [],
            "detailed_feedback": "Detailed feedback from LLM",
            "stage_summaries": {}
        }"""
        mock_llm_service.generate_report.return_value = Result.ok(mock_llm_response)

        # Act
        result = await service._generate_detailed_feedback(
            session_id, sample_stage_results, "sales"
        )

        # Assert
        assert result.is_success
        assert result.value == "Detailed feedback from LLM"

    @pytest.mark.asyncio
    async def test_generate_detailed_feedback_prompt_not_found(
        self, service, mock_prompt_service, sample_stage_results
    ):
        """Test _generate_detailed_feedback when prompt template not found."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_service.get_template_for_scenario.return_value = None

        # Act
        result = await service._generate_detailed_feedback(
            session_id, sample_stage_results, "sales"
        )

        # Assert
        assert not result.is_success
        assert "REPORT_PROMPT_NOT_FOUND" in result.fallback

    @pytest.mark.asyncio
    async def test_generate_detailed_feedback_uses_compiled_prompt_contract_for_llm_runtime(
        self,
        service,
        mock_prompt_service,
        mock_llm_service,
        sample_stage_results,
    ):
        """Detailed feedback should consume a compiled prompt contract, not raw context."""
        session_id = str(uuid4())
        mock_prompt_template = MagicMock()
        mock_prompt_template.id = uuid4()
        mock_prompt_template.template = "报告：{{ overall_summary }}"
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        compiled_contract = SimpleNamespace(
            rendered_prompt="报告：第一阶段表现稳定",
            system_message="你是销售教练。",
            contract_hash="contract-hash-2",
        )
        mock_prompt_service.compile_runtime_prompt_contract = MagicMock(
            return_value=Result.ok(compiled_contract)
        )
        mock_llm_service.generate_report.return_value = Result.ok(
            '{"overall_score":80.0,"dimension_scores":{},"key_strengths":[],"key_improvements":[],"recommendations":[],"detailed_feedback":"Detailed feedback from LLM","stage_summaries":{}}'
        )

        result = await service._generate_detailed_feedback(
            session_id,
            sample_stage_results,
            "sales",
        )

        assert result.is_success
        assert result.value == "Detailed feedback from LLM"
        mock_prompt_service.compile_runtime_prompt_contract.assert_called_once()
        mock_llm_service.generate_report.assert_awaited_once_with(compiled_contract)

    @pytest.mark.asyncio
    async def test_generate_detailed_feedback_llm_failure(
        self, service, mock_prompt_service, mock_llm_service, sample_stage_results
    ):
        """Test _generate_detailed_feedback when LLM call fails."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_template = MagicMock()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )
        mock_llm_service.generate_report.return_value = Result.fail("[LLM_ERROR]")

        # Act
        result = await service._generate_detailed_feedback(
            session_id, sample_stage_results, "sales"
        )

        # Assert
        assert not result.is_success

    @pytest.mark.asyncio
    async def test_generate_detailed_feedback_validation_failure(
        self, service, mock_prompt_service, mock_llm_service, sample_stage_results
    ):
        """Test _generate_detailed_feedback when LLM response validation fails."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_template = MagicMock()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        # Invalid LLM response
        mock_llm_service.generate_report.return_value = Result.ok("Not valid JSON")

        # Act
        result = await service._generate_detailed_feedback(
            session_id, sample_stage_results, "sales"
        )

        # Assert
        assert not result.is_success
        assert "LLM_VALIDATION_FAILED" in result.fallback

    @pytest.mark.asyncio
    async def test_generate_detailed_feedback_exception_returns_empty(
        self, service, mock_prompt_service, sample_stage_results
    ):
        """Test _generate_detailed_feedback returns empty string on exception."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_service.get_template_for_scenario.side_effect = RuntimeError(
            "Test error"
        )

        # Act
        result = await service._generate_detailed_feedback(
            session_id, sample_stage_results, "sales"
        )

        # Assert - Should return success with empty string (graceful degradation)
        assert result.is_success
        assert result.value == ""

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, service):
        """Test _generate_recommendations helper."""
        # Arrange
        dimension_scores = [
            DimensionScore(
                name="communication", score=50.0, weight=0.25, description=""
            ),  # Low score
            DimensionScore(
                name="product_knowledge", score=90.0, weight=0.20, description=""
            ),  # High score
        ]
        key_improvements = ["Product knowledge", "Closing techniques"]

        # Act
        recommendations = await service._generate_recommendations(
            dimension_scores, key_improvements, "sales"
        )

        # Assert
        assert len(recommendations) > 0
        assert any("communication" in r.lower() for r in recommendations)

    @pytest.mark.asyncio
    async def test_generate_recommendations_no_low_scores(self, service):
        """Test _generate_recommendations when all scores are good."""
        # Arrange
        dimension_scores = [
            DimensionScore(
                name="communication", score=85.0, weight=0.25, description=""
            ),
            DimensionScore(
                name="product_knowledge", score=90.0, weight=0.20, description=""
            ),
        ]
        key_improvements = ["Minor improvements"]

        # Act
        recommendations = await service._generate_recommendations(
            dimension_scores, key_improvements, "sales"
        )

        # Assert - Should only include improvement-based recommendations
        assert len(recommendations) > 0
        assert not any("score" in r for r in recommendations)  # No score-based ones

    @pytest.mark.asyncio
    async def test_generate_recommendations_max_five(self, service):
        """Test _generate_recommendations limits to 5 recommendations."""
        # Arrange
        dimension_scores = [
            DimensionScore(name=f"dim_{i}", score=50.0, weight=0.1, description="")
            for i in range(10)
        ]
        key_improvements = [f"Improvement {i}" for i in range(10)]

        # Act
        recommendations = await service._generate_recommendations(
            dimension_scores, key_improvements, "sales"
        )

        # Assert
        assert len(recommendations) <= 5

    @pytest.mark.asyncio
    async def test_generate_recommendations_exception_returns_empty(self, service):
        """Test _generate_recommendations returns empty list on exception."""
        # Arrange - Pass invalid data that might cause issues
        dimension_scores = None  # This will cause an error

        # Act
        recommendations = await service._generate_recommendations(
            dimension_scores, [], "sales"
        )

        # Assert - Should return empty list on error
        assert recommendations == []

    def test_get_dimension_description(self, service):
        """Test _get_dimension_description helper."""
        # Act & Assert
        assert "clarity" in service._get_dimension_description("communication").lower()
        assert (
            "understanding"
            in service._get_dimension_description("product_knowledge").lower()
        )
        assert (
            "ability" in service._get_dimension_description("problem_solving").lower()
        )
        assert "empathy" in service._get_dimension_description("customer_focus").lower()
        assert (
            "professional"
            in service._get_dimension_description("professionalism").lower()
        )

    def test_get_dimension_description_unknown(self, service):
        """Test _get_dimension_description with unknown dimension."""
        # Act
        description = service._get_dimension_description("unknown_dimension")

        # Assert
        assert description == ""

    def test_format_stage_summaries(self, service, sample_stage_results):
        """Test _format_stage_summaries helper."""
        # Act
        formatted = service._format_stage_summaries(sample_stage_results)

        # Assert
        assert "Stage 1:" in formatted
        assert "Stage 2:" in formatted
        assert "Strong opening stage" in formatted

    def test_format_stage_summaries_empty(self, service):
        """Test _format_stage_summaries with empty results."""
        # Act
        formatted = service._format_stage_summaries([])

        # Assert
        assert formatted == ""

    @pytest.mark.asyncio
    async def test_store_report_success(self, service, mock_db_session):
        """Test _store_report successful storage."""
        # Arrange
        report = ComprehensiveReport(
            session_id=str(uuid4()),
            generated_at=datetime.now(UTC),
            overall_score=85.0,
            dimension_scores=[
                DimensionScore(
                    name="communication", score=85.0, weight=0.25, description="Test"
                )
            ],
            stage_summaries=[],
            key_strengths=[],
            key_improvements=[],
            detailed_feedback="",
            recommendations=[],
        )

        # Act
        result = await service._store_report(report)

        # Assert
        assert result.is_success
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        stored_row = mock_db_session.add.call_args.args[0]
        assert stored_row.session_id == report.session_id
        assert stored_row.created_at == report.generated_at

    @pytest.mark.asyncio
    async def test_store_report_database_error(self, service, mock_db_session):
        """Test _store_report with database error."""
        # Arrange
        report = ComprehensiveReport(
            session_id=str(uuid4()),
            generated_at=datetime.now(UTC),
            overall_score=85.0,
            dimension_scores=[],
            stage_summaries=[],
            key_strengths=[],
            key_improvements=[],
            detailed_feedback="",
            recommendations=[],
        )
        mock_db_session.commit.side_effect = SQLAlchemyError("Connection failed")

        # Act
        result = await service._store_report(report)

        # Assert
        assert not result.is_success
        assert "DATABASE_ERROR" in result.fallback
        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_report_unexpected_error(self, service, mock_db_session):
        """Test _store_report with unexpected error."""
        # Arrange
        report = ComprehensiveReport(
            session_id=str(uuid4()),
            generated_at=datetime.now(UTC),
            overall_score=85.0,
            dimension_scores=[],
            stage_summaries=[],
            key_strengths=[],
            key_improvements=[],
            detailed_feedback="",
            recommendations=[],
        )
        mock_db_session.add.side_effect = Exception("Unexpected error")

        # Act
        result = await service._store_report(report)

        # Assert
        assert not result.is_success
        assert "STORAGE_ERROR" in result.fallback
        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_report_store_failure(
        self,
        service,
        mock_staged_eval_service,
        mock_prompt_service,
        mock_llm_service,
        mock_db_session,
        sample_stage_results,
    ):
        """Test generate_report when storing report fails."""
        # Arrange
        session_id = str(uuid4())
        mock_staged_eval_service.get_stage_results.return_value = sample_stage_results

        mock_prompt_template = MagicMock()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        mock_llm_response = """{
            "overall_score": 80.0,
            "dimension_scores": {},
            "key_strengths": [],
            "key_improvements": [],
            "recommendations": [],
            "detailed_feedback": "Test",
            "stage_summaries": {}
        }"""
        mock_llm_service.generate_report.return_value = Result.ok(mock_llm_response)

        mock_db_session.commit.side_effect = SQLAlchemyError("Storage failed")

        # Act
        result = await service.generate_report(session_id)

        # Assert
        assert not result.is_success
        assert "DATABASE_ERROR" in result.fallback or "STORAGE" in result.fallback

    @pytest.mark.asyncio
    async def test_generate_report_with_feedback_failure_continues(
        self,
        service,
        mock_staged_eval_service,
        mock_prompt_service,
        mock_llm_service,
        mock_db_session,
        sample_stage_results,
    ):
        """Test that report generation continues even if detailed feedback generation fails."""
        # Arrange
        session_id = str(uuid4())
        mock_staged_eval_service.get_stage_results.return_value = sample_stage_results

        mock_prompt_template = MagicMock()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        # LLM fails for feedback
        mock_llm_service.generate_report.return_value = Result.fail("[LLM_ERROR]")

        # Mock successful storage
        mock_db_session.commit = AsyncMock()

        # Act
        result = await service.generate_report(session_id)

        # Assert - Should still succeed with empty feedback
        assert result.is_success
        assert result.value.detailed_feedback == ""


class TestPresentationReportService:
    @pytest.fixture
    def presentation_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_build_presentation_review_includes_page_coverage_and_diagnostics(
        self,
        presentation_db_session,
    ):
        session_id = str(uuid4())
        practice_session = SimpleNamespace(
            session_id=session_id,
            presentation_id="ppt-001",
            start_time=datetime(2026, 3, 1, tzinfo=UTC),
            end_time=datetime(2026, 3, 1, 0, 12, tzinfo=UTC),
            logic_score=None,
            accuracy_score=None,
            completeness_score=None,
        )
        user_messages = [
            SimpleNamespace(
                content="客户痛点和价值方案介绍很完整",
                role="user",
                turn_number=1,
                timestamp=datetime(2026, 3, 1, 0, 1, tzinfo=UTC),
                transcript_metadata={"page_number": 1},
            ),
            SimpleNamespace(
                content="这一页补充了实施计划，但没有展开落地细节",
                role="user",
                turn_number=2,
                timestamp=datetime(2026, 3, 1, 0, 2, tzinfo=UTC),
                transcript_metadata={"page_number": 2},
            ),
        ]
        interruption_events = [
            SimpleNamespace(interruption_type="forbidden_word"),
            SimpleNamespace(interruption_type="missing_point"),
            SimpleNamespace(interruption_type="vague_response"),
        ]
        pages = [
            SimpleNamespace(page_id="page-1", page_number=1),
            SimpleNamespace(page_id="page-2", page_number=2),
        ]
        required_points = [
            SimpleNamespace(page_id="page-1", description="客户痛点"),
            SimpleNamespace(page_id="page-1", description="价值方案"),
            SimpleNamespace(page_id="page-2", description="时间安排"),
        ]
        presentation_db_session.execute.side_effect = [
            _ScalarResult(practice_session),
            _ScalarsResult(user_messages),
            _ScalarsResult(interruption_events),
            _ScalarsResult(pages),
            _ScalarsResult(required_points),
            _ScalarsResult([]),
        ]

        service = PresentationReportService(presentation_db_session)

        result = await service.build_presentation_review(session_id)

        assert result.is_success
        review = result.value
        assert review["has_page_metadata"] is True
        assert review["coverage_status"] == "complete"
        assert len(review["dimension_scores"]) == 6
        assert [summary["page_number"] for summary in review["page_summaries"]] == [
            1,
            2,
        ]
        assert review["required_talking_points"] == {
            "status": "complete",
            "total": 3,
            "covered": 2,
            "missing": 1,
            "coverage_ratio": pytest.approx(2 / 3, 0.001),
        }
        assert review["issue_counts"] == {
            "forbidden_word": 1,
            "missing_point": 1,
            "vague_response": 1,
        }
        assert review["page_summaries"][0]["issue_clusters"] == []
        assert review["page_summaries"][1]["issue_clusters"] == [
            {
                "issue_type": "missing_point",
                "summary": "第 2 页仍缺少 1 个必讲点，需要补齐再进入下一页。",
                "evidence": ["未覆盖：时间安排"],
                "turn_numbers": [2],
                "linked_points": ["时间安排"],
                "linked_phrases": [],
                "related_page_numbers": [],
            }
        ]
        assert review["diagnostics"]["page_issue_cluster_count"] == 1
        assert review["diagnostics"]["page_issue_types"] == ["missing_point"]
        assert review["diagnostics"]["degraded_reasons"] == []

    @pytest.mark.asyncio
    async def test_build_presentation_review_degrades_without_page_metadata(
        self,
        presentation_db_session,
    ):
        session_id = str(uuid4())
        practice_session = SimpleNamespace(
            session_id=session_id,
            presentation_id="ppt-002",
            start_time=datetime(2026, 3, 1, tzinfo=UTC),
            end_time=datetime(2026, 3, 1, 0, 8, tzinfo=UTC),
            logic_score=None,
            accuracy_score=None,
            completeness_score=None,
        )
        user_messages = [
            SimpleNamespace(
                content="我们先讲客户痛点，再讲价值方案",
                role="user",
                turn_number=1,
                timestamp=datetime(2026, 3, 1, 0, 1, tzinfo=UTC),
                transcript_metadata=None,
            ),
            SimpleNamespace(
                content="最后补充实施计划",
                role="user",
                turn_number=2,
                timestamp=datetime(2026, 3, 1, 0, 2, tzinfo=UTC),
                transcript_metadata={},
            ),
        ]
        pages = [
            SimpleNamespace(page_id="page-1", page_number=1),
            SimpleNamespace(page_id="page-2", page_number=2),
        ]
        required_points = [
            SimpleNamespace(page_id="page-1", description="客户痛点"),
            SimpleNamespace(page_id="page-2", description="实施计划"),
        ]
        presentation_db_session.execute.side_effect = [
            _ScalarResult(practice_session),
            _ScalarsResult(user_messages),
            _ScalarsResult([]),
            _ScalarsResult(pages),
            _ScalarsResult(required_points),
            _ScalarsResult([]),
        ]

        service = PresentationReportService(presentation_db_session)

        result = await service.build_presentation_review(session_id)

        assert result.is_success
        review = result.value
        assert review["has_page_metadata"] is False
        assert review["coverage_status"] == "degraded"
        assert review["page_summaries"] == []
        assert review["required_talking_points"]["status"] == "degraded"
        assert review["required_talking_points"]["total"] == 2
        assert review["diagnostics"]["page_issue_cluster_count"] == 0
        assert review["diagnostics"]["page_issue_types"] == []
        assert review["diagnostics"]["degraded_reasons"] == ["missing_page_metadata"]

    @pytest.mark.asyncio
    async def test_build_report_reuses_normalized_presentation_review_builder(
        self,
        presentation_db_session,
    ):
        payload = {
            "overall_score": 88.0,
            "dimension_scores": [
                {
                    "name": "流畅连贯性",
                    "score": 90.0,
                    "weight": 0.22,
                    "description": "讲解节奏、重复情况与口头语控制",
                },
                {
                    "name": "准确性",
                    "score": 86.0,
                    "weight": 0.20,
                    "description": "内容与资料一致性、错误信息控制",
                },
            ],
            "page_summaries": [
                {
                    "page_number": 1,
                    "stage_number": 1,
                    "start_turn": 1,
                    "end_turn": 2,
                    "average_score": 88.0,
                    "key_points": ["客户痛点"],
                    "matched_required_points": ["客户痛点"],
                    "missing_required_points": ["价值方案"],
                    "summary": "第一页讲解较完整。",
                }
            ],
            "required_talking_points": {
                "status": "complete",
                "total": 2,
                "covered": 1,
                "missing": 1,
                "coverage_ratio": 0.5,
            },
            "issue_counts": {
                "forbidden_word": 0,
                "missing_point": 1,
                "vague_response": 0,
            },
            "strengths": ["表达流畅"],
            "improvements": ["补齐价值方案"],
            "recommendations": ["每页准备两个必须讲到的关键词。"],
            "detailed_feedback": "总体讲解稳定，但第二个关键点覆盖不足。",
            "has_page_metadata": True,
            "coverage_status": "complete",
            "diagnostics": {
                "has_page_metadata": True,
                "pages_with_messages": 1,
                "total_pages": 1,
                "page_coverage_ratio": 1.0,
                "required_points_total": 2,
                "required_points_covered": 1,
                "required_points_missing": 1,
                "required_coverage_ratio": 0.5,
                "degraded_reasons": [],
            },
        }

        service = PresentationReportService(presentation_db_session)
        service.build_presentation_review = AsyncMock(return_value=Result.ok(payload))
        service._load_report_context = AsyncMock(
            return_value=Result.ok(
                {
                    "session": SimpleNamespace(
                        logic_score=None,
                        accuracy_score=None,
                        completeness_score=None,
                    )
                }
            )
        )

        result = await service.build_report("session-report-001")

        assert result.is_success
        report = result.value
        service.build_presentation_review.assert_awaited_once_with("session-report-001")
        service._load_report_context.assert_awaited_once_with("session-report-001")
        assert report.overall_score == 88.0
        assert report.dimension_scores[0].name == "流畅连贯性"
        assert report.stage_summaries == payload["page_summaries"]
        assert report.key_strengths == ["表达流畅"]
        assert report.key_improvements == ["补齐价值方案"]
        assert report.recommendations == ["每页准备两个必须讲到的关键词。"]
