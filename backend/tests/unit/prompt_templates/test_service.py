"""
Tests for Prompt Template Service

TDD Tests for Task B6: Implement PromptTemplateService
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from src.prompt_templates.service import PromptTemplateService
from src.prompt_templates.models import (
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    ScenarioPromptCreate,
    PromptType,
    PromptRenderRequest,
)


class TestPromptTemplateService:
    """Test the PromptTemplateService class"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def service(self, mock_db):
        """Create service with mock db"""
        return PromptTemplateService(db_session=mock_db)

    @pytest.fixture
    def sample_template_db(self):
        """Create a sample database template mock"""
        template = MagicMock()
        template.id = uuid4()
        template.name = "Test Template"
        template.prompt_type = "summary"
        template.category = "test"
        template.template = "Hello {{ name }}"
        template.variables = ["name"]
        template.is_active = True
        template.is_default = False
        template.is_system = False
        template.created_at = datetime.utcnow()
        template.updated_at = datetime.utcnow()
        return template

    @pytest.mark.asyncio
    async def test_create_template(self, service, mock_db):
        """Test creating a new template"""
        data = PromptTemplateCreate(
            name="New Template",
            prompt_type=PromptType.SUMMARY,
            template="Hello {{ name }}",
        )

        # Mock the db operations
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch("src.prompt_templates.service.uuid4", return_value=UUID("12345678-1234-1234-1234-123456789012")):
            result = await service.create_template(data)

        assert result.name == "New Template"
        assert result.prompt_type == PromptType.SUMMARY
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_template_found(self, service, mock_db, sample_template_db):
        """Test getting an existing template"""
        # Setup mock result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template_db
        mock_db.execute.return_value = mock_result

        template_id = sample_template_db.id
        result = await service.get_template(template_id)

        assert result is not None
        assert result.name == "Test Template"
        assert result.id == template_id

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, service, mock_db):
        """Test getting a non-existent template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.get_template(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_update_template_success(self, service, mock_db, sample_template_db):
        """Test updating an existing template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template_db
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        update_data = PromptTemplateUpdate(name="Updated Name")

        result = await service.update_template(sample_template_db.id, update_data)

        assert result is not None
        assert sample_template_db.name == "Updated Name"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_template_not_found(self, service, mock_db):
        """Test updating a non-existent template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        update_data = PromptTemplateUpdate(name="Updated Name")
        result = await service.update_template(uuid4(), update_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_template_success(self, service, mock_db, sample_template_db):
        """Test deleting (soft delete) a template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template_db
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        result = await service.delete_template(sample_template_db.id)

        assert result is True
        assert sample_template_db.is_active is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_template_not_found(self, service, mock_db):
        """Test deleting a non-existent template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.delete_template(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_list_templates(self, service, mock_db, sample_template_db):
        """Test listing templates"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_template_db]
        mock_db.execute.return_value = mock_result

        results = await service.list_templates()

        assert len(results) == 1
        assert results[0].name == "Test Template"

    @pytest.mark.asyncio
    async def test_list_templates_with_filter(self, service, mock_db, sample_template_db):
        """Test listing templates with type filter"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_template_db]
        mock_db.execute.return_value = mock_result

        results = await service.list_templates(prompt_type=PromptType.SUMMARY)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_render_prompt(self, service, mock_db, sample_template_db):
        """Test rendering a prompt template"""
        # Setup for get_template
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template_db
        mock_db.execute.return_value = mock_result

        request = PromptRenderRequest(
            template_id=sample_template_db.id,
            variables={"name": "World"},
        )

        result = await service.render_prompt(request)

        assert result.rendered == "Hello World"
        assert result.template_id == sample_template_db.id

    @pytest.mark.asyncio
    async def test_render_prompt_not_found(self, service, mock_db):
        """Test rendering a non-existent template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        request = PromptRenderRequest(
            template_id=uuid4(),
            variables={"name": "World"},
        )

        result = await service.render_prompt(request)

        assert result.rendered == ""

    @pytest.mark.asyncio
    async def test_assign_template_to_scenario(self, service, mock_db):
        """Test assigning template to scenario"""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        data = ScenarioPromptCreate(
            scenario_type="sales",
            prompt_type="summary",
            template_id=uuid4(),
        )

        with patch("src.prompt_templates.service.uuid4", return_value=UUID("12345678-1234-1234-1234-123456789012")):
            result = await service.assign_template_to_scenario(data)

        assert result.scenario_type == "sales"
        assert result.prompt_type == "summary"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_default_template_success(self, service, mock_db, sample_template_db):
        """Test setting a template as default"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template_db
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        result = await service.set_default_template(
            sample_template_db.id,
            PromptType.SUMMARY
        )

        assert result is True
        assert sample_template_db.is_default is True

    @pytest.mark.asyncio
    async def test_set_default_template_not_found(self, service, mock_db):
        """Test setting default for non-existent template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.set_default_template(uuid4(), PromptType.SUMMARY)

        assert result is False


class TestGetTemplateForScenario:
    """Test scenario-specific template resolution"""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_db):
        return PromptTemplateService(db_session=mock_db)

    @pytest.fixture
    def sample_template(self):
        template = MagicMock()
        template.id = uuid4()
        template.name = "Scenario Template"
        template.prompt_type = "summary"
        return template

    @pytest.mark.asyncio
    async def test_scenario_specific_match(self, service, mock_db, sample_template):
        """Test finding scenario-specific template"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template
        mock_db.execute.return_value = mock_result

        result = await service.get_template_for_scenario(
            prompt_type="summary",
            scenario_type="sales",
            scenario_id="scenario_123",
        )

        assert result is not None
        assert result.name == "Scenario Template"

    @pytest.mark.asyncio
    async def test_fallback_to_type_default(self, service, mock_db, sample_template):
        """Test fallback to scenario-type default"""
        # First query returns None, second returns template
        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # Specific
            MagicMock(scalar_one_or_none=MagicMock(return_value=sample_template)),  # Type
        ]
        mock_db.execute.side_effect = mock_results

        result = await service.get_template_for_scenario(
            prompt_type="summary",
            scenario_type="sales",
        )

        assert result is not None
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_fallback_to_global_default(self, service, mock_db, sample_template):
        """Test fallback to global default"""
        # First two queries return None, third returns template
        mock_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=sample_template)),
        ]
        mock_db.execute.side_effect = mock_results

        result = await service.get_template_for_scenario(
            prompt_type="summary",
        )

        assert result is not None
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_no_match_found(self, service, mock_db):
        """Test when no template matches"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.get_template_for_scenario(
            prompt_type="summary",
        )

        assert result is None
