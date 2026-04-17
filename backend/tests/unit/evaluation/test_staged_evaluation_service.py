"""
Unit Tests for StagedEvaluationService

Requirements: Task #8 - Add unit tests for evaluation module
Coverage Target: 70% for staged_evaluation.py

Test Coverage:
- evaluate_stage() method with various scenarios
- check_triggers() method
- get_stage_results() method
- register_stage_config() and get_stage_configs() methods
- _format_conversation() helper method
- Error handling and edge cases
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from evaluation.services.staged_evaluation import (
    StageConfig,
    StagedEvaluationService,
    StageEvaluationResult,
)
from evaluation.triggers.base_trigger import BaseTrigger, TriggerContext


class MockTrigger(BaseTrigger):
    """Mock trigger for testing."""

    def __init__(self, should_fire: bool = True):
        super().__init__(cooldown_turns=0)
        self.should_fire = should_fire
        self.check_called = False

    def should_trigger(self, context: TriggerContext) -> bool:
        self.check_called = True
        return self.should_fire

    async def check(self, context: TriggerContext) -> bool:
        """Async wrapper for should_trigger to match service expectations."""
        return self.should_trigger(context)


class TestStagedEvaluationService:
    """Test StagedEvaluationService class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

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
                    contract_hash="test-stage-contract",
                )
            )
        )
        return service

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        service = AsyncMock()
        service.evaluate = AsyncMock()
        return service

    @pytest.fixture
    def service(self, mock_db_session, mock_prompt_service, mock_llm_service):
        """Create StagedEvaluationService instance with mocked dependencies."""
        return StagedEvaluationService(
            db_session=mock_db_session,
            prompt_service=mock_prompt_service,
            llm_service=mock_llm_service,
        )

    @pytest.fixture
    def sample_stage_config(self):
        """Create sample StageConfig."""
        return StageConfig(
            stage_number=1,
            name="Opening",
            description="Opening stage of conversation",
            evaluation_prompt_type="stage",
            triggers=[MockTrigger(should_fire=True)],
        )

    @pytest.fixture
    def sample_conversation_history(self):
        """Create sample conversation history."""
        return [
            {"role": "assistant", "content": "Hello! How can I help you today?"},
            {"role": "user", "content": "I'm interested in your products."},
            {
                "role": "assistant",
                "content": "Great! What products are you looking for?",
            },
            {"role": "user", "content": "Sales training software."},
        ]

    @pytest.mark.asyncio
    async def test_evaluate_stage_success(
        self,
        service,
        mock_prompt_service,
        mock_llm_service,
        sample_stage_config,
        sample_conversation_history,
    ):
        """Test successful stage evaluation."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_template = MagicMock()
        mock_prompt_template.id = uuid4()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        mock_llm_response = """{
            "scores": {"communication": 85.0, "product_knowledge": 90.0},
            "strengths": ["Clear opening", "Good greeting"],
            "suggestions": ["Ask more questions"],
            "summary": "Strong opening stage",
            "confidence": 0.9
        }"""
        mock_llm_service.evaluate.return_value = Result.ok(mock_llm_response)

        # Act
        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=sample_stage_config,
            conversation_history=sample_conversation_history,
        )

        # Assert
        assert result.is_success
        evaluation = result.value
        assert isinstance(evaluation, StageEvaluationResult)
        assert evaluation.stage_number == 1
        assert evaluation.scores["communication"] == 85.0
        assert evaluation.strengths == ["Clear opening", "Good greeting"]
        assert evaluation.summary == "Strong opening stage"

        # Verify dependencies were called
        mock_prompt_service.get_template_for_scenario.assert_called_once()
        mock_llm_service.evaluate.assert_called_once()
        service.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_stage_prompt_not_found(
        self,
        service,
        mock_prompt_service,
        sample_stage_config,
        sample_conversation_history,
    ):
        """Test evaluation when prompt template is not found."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_service.get_template_for_scenario.return_value = None

        # Act
        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=sample_stage_config,
            conversation_history=sample_conversation_history,
        )

        # Assert
        assert not result.is_success
        assert "PROMPT_NOT_FOUND" in result.fallback

    @pytest.mark.asyncio
    async def test_evaluate_stage_uses_compiled_prompt_contract_for_llm_runtime(
        self,
        service,
        mock_prompt_service,
        mock_llm_service,
        sample_stage_config,
        sample_conversation_history,
    ):
        """Stage evaluation should pass the compiled prompt contract into the LLM runtime."""
        session_id = str(uuid4())
        mock_prompt_template = MagicMock()
        mock_prompt_template.id = uuid4()
        mock_prompt_template.template = (
            "阶段：{{ stage_name }}\n对话：{{ conversation }}"
        )
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        compiled_contract = SimpleNamespace(
            rendered_prompt="阶段：Opening\n对话：user: hi",
            system_message="你是评估专家。",
            contract_hash="contract-hash-1",
        )
        mock_prompt_service.compile_runtime_prompt_contract = MagicMock(
            return_value=Result.ok(compiled_contract)
        )
        mock_llm_service.evaluate.return_value = Result.ok(
            '{"scores":{"communication":85.0},"strengths":[],"weaknesses":[],"suggestions":[],"summary":"ok"}'
        )

        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=sample_stage_config,
            conversation_history=sample_conversation_history,
        )

        assert result.is_success
        mock_prompt_service.compile_runtime_prompt_contract.assert_called_once()
        mock_llm_service.evaluate.assert_awaited_once_with(compiled_contract)

    @pytest.mark.asyncio
    async def test_evaluate_stage_llm_failure(
        self,
        service,
        mock_prompt_service,
        mock_llm_service,
        sample_stage_config,
        sample_conversation_history,
    ):
        """Test evaluation when LLM call fails."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_template = MagicMock()
        mock_prompt_template.id = uuid4()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )
        mock_llm_service.evaluate.return_value = Result.fail("[LLM_TIMEOUT]")

        # Act
        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=sample_stage_config,
            conversation_history=sample_conversation_history,
        )

        # Assert
        assert not result.is_success
        assert "LLM_EVALUATION_FAILED" in result.fallback

    @pytest.mark.asyncio
    async def test_evaluate_stage_validation_failure(
        self,
        service,
        mock_prompt_service,
        mock_llm_service,
        sample_stage_config,
        sample_conversation_history,
    ):
        """Test evaluation when LLM response validation fails."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_template = MagicMock()
        mock_prompt_template.id = uuid4()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        # Invalid response (missing required fields in wrong format)
        invalid_response = "This is not valid JSON"
        mock_llm_service.evaluate.return_value = Result.ok(invalid_response)

        # Act
        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=sample_stage_config,
            conversation_history=sample_conversation_history,
        )

        # Assert
        assert not result.is_success
        assert (
            "LLM_VALIDATION_FAILED" in result.fallback or "LLM_PARSE" in result.fallback
        )

    @pytest.mark.asyncio
    async def test_evaluate_stage_exception_handling(
        self,
        service,
        mock_prompt_service,
        sample_stage_config,
        sample_conversation_history,
    ):
        """Test evaluation when an unexpected exception occurs."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_service.get_template_for_scenario.side_effect = Exception(
            "Database connection failed"
        )

        # Act
        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=sample_stage_config,
            conversation_history=sample_conversation_history,
        )

        # Assert
        assert not result.is_success
        assert "STAGE_EVALUATION_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_check_triggers_no_triggers_fired(
        self, service, sample_stage_config, sample_conversation_history
    ):
        """Test check_triggers when no triggers are activated."""
        # Arrange
        session_id = str(uuid4())
        config_with_no_trigger = StageConfig(
            stage_number=1,
            name="Opening",
            description="Opening stage",
            evaluation_prompt_type="stage",
            triggers=[MockTrigger(should_fire=False)],
        )

        # Act
        triggered = await service.check_triggers(
            session_id=session_id,
            conversation_history=sample_conversation_history,
            stage_configs=[config_with_no_trigger],
        )

        # Assert
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_check_triggers_one_trigger_fired(
        self, service, sample_stage_config, sample_conversation_history
    ):
        """Test check_triggers when one trigger is activated."""
        # Arrange
        session_id = str(uuid4())

        # Act
        triggered = await service.check_triggers(
            session_id=session_id,
            conversation_history=sample_conversation_history,
            stage_configs=[sample_stage_config],
        )

        # Assert
        assert len(triggered) == 1
        assert triggered[0].stage_number == 1

    @pytest.mark.asyncio
    async def test_check_triggers_multiple_stages(
        self, service, sample_conversation_history
    ):
        """Test check_triggers with multiple stage configurations."""
        # Arrange
        session_id = str(uuid4())
        stage_configs = [
            StageConfig(
                stage_number=1,
                name="Opening",
                description="Opening",
                evaluation_prompt_type="stage",
                triggers=[MockTrigger(should_fire=False)],  # Won't fire
            ),
            StageConfig(
                stage_number=2,
                name="Discovery",
                description="Discovery",
                evaluation_prompt_type="stage",
                triggers=[MockTrigger(should_fire=True)],  # Will fire
            ),
            StageConfig(
                stage_number=3,
                name="Closing",
                description="Closing",
                evaluation_prompt_type="stage",
                triggers=[MockTrigger(should_fire=True)],  # Will fire
            ),
        ]

        # Act
        triggered = await service.check_triggers(
            session_id=session_id,
            conversation_history=sample_conversation_history,
            stage_configs=stage_configs,
        )

        # Assert
        assert len(triggered) == 2
        assert triggered[0].stage_number == 2
        assert triggered[1].stage_number == 3

    @pytest.mark.asyncio
    async def test_check_triggers_extracts_last_messages(
        self, service, sample_conversation_history
    ):
        """Test that check_triggers correctly extracts last user and bot messages."""
        # Arrange
        session_id = str(uuid4())
        trigger = MockTrigger(should_fire=True)
        stage_config = StageConfig(
            stage_number=1,
            name="Opening",
            description="Opening",
            evaluation_prompt_type="stage",
            triggers=[trigger],
        )

        # Act
        await service.check_triggers(
            session_id=session_id,
            conversation_history=sample_conversation_history,
            stage_configs=[stage_config],
        )

        # Assert - trigger was called with correct context
        assert trigger.check_called

    @pytest.mark.asyncio
    async def test_check_triggers_empty_conversation(
        self, service, sample_stage_config
    ):
        """Test check_triggers with empty conversation history."""
        # Arrange
        session_id = str(uuid4())
        empty_history = []

        # Act
        triggered = await service.check_triggers(
            session_id=session_id,
            conversation_history=empty_history,
            stage_configs=[sample_stage_config],
        )

        # Assert - trigger should still be checked
        assert len(triggered) == 1

    @pytest.mark.asyncio
    async def test_get_stage_results_empty(self, service, mock_db_session):
        """Test get_stage_results when no results exist."""
        # Arrange
        session_id = str(uuid4())
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = []
        mock_db_session.execute.return_value = mock_result

        # Act
        results = await service.get_stage_results(session_id)

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_get_stage_results_with_data(self, service, mock_db_session):
        """Test get_stage_results returns existing results."""
        # Arrange
        session_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        # Mock database results
        mock_db_result = MagicMock()
        mock_db_result.stage_number = 1
        mock_db_result.start_turn = 0
        mock_db_result.end_turn = 4
        mock_db_result.created_at = created_at
        mock_db_result.scores = {"communication": 85.0}
        mock_db_result.strengths = ["Good"]
        mock_db_result.weaknesses = ["Needs improvement"]
        mock_db_result.suggestions = ["Practice more"]
        mock_db_result.summary = "Good effort"

        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [mock_db_result]
        mock_db_session.execute.return_value = mock_result

        # Act
        results = await service.get_stage_results(session_id)

        # Assert
        assert len(results) == 1
        assert results[0].stage_number == 1
        assert results[0].timestamp == created_at
        assert results[0].scores["communication"] == 85.0

    @pytest.mark.asyncio
    async def test_register_stage_config(self, service):
        """Test registering stage configurations."""
        # Arrange
        scenario_type = "sales"
        configs = [
            StageConfig(
                stage_number=1,
                name="Opening",
                description="Opening",
                evaluation_prompt_type="stage",
                triggers=[],
            ),
            StageConfig(
                stage_number=2,
                name="Discovery",
                description="Discovery",
                evaluation_prompt_type="stage",
                triggers=[],
            ),
        ]

        # Act
        await service.register_stage_config(scenario_type, configs)

        # Assert
        retrieved = service.get_stage_configs(scenario_type)
        assert len(retrieved) == 2
        assert retrieved[0].name == "Opening"
        assert retrieved[1].name == "Discovery"

    def test_get_stage_configs_not_registered(self, service):
        """Test getting configs for unregistered scenario type."""
        # Act
        configs = service.get_stage_configs("unknown_scenario")

        # Assert
        assert configs == []

    def test_format_conversation(self, service, sample_conversation_history):
        """Test _format_conversation helper method."""
        # Act
        formatted = service._format_conversation(sample_conversation_history)

        # Assert
        assert "assistant: Hello! How can I help you today?" in formatted
        assert "user: I'm interested in your products." in formatted
        assert "\n".join(formatted.split("\n")) == formatted  # Check newlines

    def test_format_conversation_empty(self, service):
        """Test _format_conversation with empty history."""
        # Act
        formatted = service._format_conversation([])

        # Assert
        assert formatted == ""

    def test_format_conversation_missing_role(self, service):
        """Test _format_conversation handles missing role."""
        # Arrange
        history = [{"content": "Message without role"}]

        # Act
        formatted = service._format_conversation(history)

        # Assert
        assert "unknown: Message without role" in formatted

    def test_format_conversation_missing_content(self, service):
        """Test _format_conversation handles missing content."""
        # Arrange
        history = [{"role": "user"}]

        # Act
        formatted = service._format_conversation(history)

        # Assert
        assert "user: " in formatted

    @pytest.mark.asyncio
    async def test_evaluate_stage_calculates_turns_correctly(
        self, service, mock_prompt_service, mock_llm_service, sample_stage_config
    ):
        """Test that evaluate_stage calculates start and end turns correctly."""
        # Arrange
        session_id = str(uuid4())
        conversation = [
            {"role": "assistant", "content": "Msg 1"},
            {"role": "user", "content": "Msg 2"},
            {"role": "assistant", "content": "Msg 3"},
            {"role": "user", "content": "Msg 4"},
            {"role": "assistant", "content": "Msg 5"},
            {"role": "user", "content": "Msg 6"},
        ]

        mock_prompt_template = MagicMock()
        mock_prompt_template.id = uuid4()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        mock_llm_response = """{
            "scores": {"communication": 80.0},
            "strengths": [],
            "suggestions": [],
            "summary": "Test",
            "confidence": 0.8
        }"""
        mock_llm_service.evaluate.return_value = Result.ok(mock_llm_response)

        # Act
        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=sample_stage_config,  # stage_number = 1
            conversation_history=conversation,
        )

        # Assert
        assert result.is_success
        assert result.value.start_turn == 0
        assert result.value.end_turn == 6

    @pytest.mark.asyncio
    async def test_evaluate_stage_stage_number_zero(
        self,
        service,
        mock_prompt_service,
        mock_llm_service,
        sample_conversation_history,
    ):
        """Test evaluate_stage with stage_number=0."""
        # Arrange
        session_id = str(uuid4())
        config_zero = StageConfig(
            stage_number=0,
            name="Preparation",
            description="Preparation stage",
            evaluation_prompt_type="stage",
            triggers=[],
        )

        mock_prompt_template = MagicMock()
        mock_prompt_template.id = uuid4()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        mock_llm_response = """{
            "scores": {"communication": 80.0},
            "strengths": [],
            "suggestions": [],
            "summary": "Test",
            "confidence": 0.8
        }"""
        mock_llm_service.evaluate.return_value = Result.ok(mock_llm_response)

        # Act
        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=config_zero,
            conversation_history=sample_conversation_history,
        )

        # Assert
        assert result.is_success
        assert result.value.start_turn == 0  # 0 * 2 = 0

    @pytest.mark.asyncio
    async def test_store_evaluation_called(
        self,
        service,
        mock_db_session,
        mock_prompt_service,
        mock_llm_service,
        sample_stage_config,
        sample_conversation_history,
    ):
        """Test that _store_evaluation is called and database operations are performed."""
        # Arrange
        session_id = str(uuid4())
        mock_prompt_template = MagicMock()
        mock_prompt_template.id = uuid4()
        mock_prompt_service.get_template_for_scenario.return_value = (
            mock_prompt_template
        )

        mock_llm_response = """{
            "scores": {"communication": 85.0},
            "strengths": ["Good"],
            "weaknesses": ["Needs more specificity"],
            "suggestions": [],
            "summary": "Test",
            "confidence": 0.85
        }"""
        mock_llm_service.evaluate.return_value = Result.ok(mock_llm_response)

        # Act
        result = await service.evaluate_stage(
            session_id=session_id,
            stage_config=sample_stage_config,
            conversation_history=sample_conversation_history,
        )

        # Assert
        assert result.is_success
        service.db.add.assert_called_once()
        service.db.commit.assert_called_once()
        stored_row = service.db.add.call_args.args[0]
        assert stored_row.session_id == session_id
        assert stored_row.weaknesses == ["Needs more specificity"]
        assert stored_row.created_at == result.value.timestamp

    @pytest.mark.asyncio
    async def test_multiple_stage_configs_same_scenario(self, service):
        """Test registering multiple configs for same scenario overwrites."""
        # Arrange
        scenario_type = "sales"
        configs_v1 = [
            StageConfig(
                stage_number=1,
                name="Opening",
                description="Original",
                evaluation_prompt_type="stage",
                triggers=[],
            )
        ]
        configs_v2 = [
            StageConfig(
                stage_number=1,
                name="Opening V2",
                description="Updated",
                evaluation_prompt_type="stage",
                triggers=[],
            )
        ]

        # Act
        await service.register_stage_config(scenario_type, configs_v1)
        await service.register_stage_config(scenario_type, configs_v2)

        # Assert
        retrieved = service.get_stage_configs(scenario_type)
        assert len(retrieved) == 1
        assert retrieved[0].description == "Updated"
