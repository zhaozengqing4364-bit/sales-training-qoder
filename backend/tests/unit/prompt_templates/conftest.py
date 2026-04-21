"""
Test fixtures for prompt_templates module.

Requirements: B3 - Create test skeleton for prompt templates
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from prompt_templates.models import (
    PromptTemplate,
    PromptTemplateCreate,
    PromptType,
    ScenarioPrompt,
    ScenarioPromptCreate,
)


@pytest.fixture
def sample_template_id() -> UUID:
    """Sample template UUID."""
    return uuid4()


@pytest.fixture
def sample_prompt_template_create() -> PromptTemplateCreate:
    """Sample prompt template create model."""
    return PromptTemplateCreate(
        name="Test Template",
        prompt_type=PromptType.SUMMARY,
        category="sales",
        template="Hello {{ name }}, your score is {{ score }}!",
        variables=["name", "score"],
        is_active=True,
        is_default=False,
    )


@pytest.fixture
def sample_prompt_template() -> PromptTemplate:
    """Sample full prompt template model."""
    now = datetime.now(UTC)
    return PromptTemplate(
        id=uuid4(),
        name="Sample Template",
        prompt_type=PromptType.SYSTEM,
        category="common",
        template="Welcome to the system!",
        variables=[],
        is_active=True,
        is_default=True,
        is_system=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_scenario_prompt_create(sample_template_id: UUID) -> ScenarioPromptCreate:
    """Sample scenario prompt create model."""
    return ScenarioPromptCreate(
        scenario_type="sales",
        scenario_id="scenario-123",
        prompt_type="summary",
        template_id=sample_template_id,
        is_active=True,
    )


@pytest.fixture
def sample_scenario_prompt(sample_template_id: UUID) -> ScenarioPrompt:
    """Sample full scenario prompt model."""
    return ScenarioPrompt(
        id=uuid4(),
        scenario_type="presentation",
        scenario_id="ppt-456",
        prompt_type="extraction",
        template_id=sample_template_id,
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_llm_service(mocker):
    """Mock LLM service for testing."""
    mock = mocker.patch("common.ai.llm_service.get_llm_service")
    mock.return_value.is_configured = True
    mock.return_value.generate.return_value = "Mocked LLM response"
    return mock


@pytest.fixture
def mock_db_session(mocker):
    """Mock database session for testing."""
    return mocker.AsyncMock()
