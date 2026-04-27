"""
Unit tests for Prompt Template Models (TDD)

Requirements: B2 - Create Pydantic models for prompt templates

Tests:
- PromptTemplate model validation
- PromptTemplateCreate with variable extraction
- PromptTemplateUpdate partial updates
- ScenarioPrompt model validation
- PromptType enum validation
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from prompt_templates.models import (
    PromptRenderRequest,
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptType,
    ScenarioPrompt,
    ScenarioPromptCreate,
)


class TestPromptTypeEnum:
    """Test PromptType enum values."""

    def test_prompt_type_values(self):
        """Should have all expected prompt types."""
        expected_types = [
            "summary",
            "system",
            "system_prompt",
            "extraction",
            "scoring",
            "stage",
            "realtime_scoring",
            "fuzzy_detection",
            "realtime_scoring",
            "interruption",
            "tracking",
            "welcome",
            "evaluation",
            "report",
            "realtime_scoring",
        ]
        for type_value in expected_types:
            assert PromptType(type_value).value == type_value

    def test_prompt_type_comparison(self):
        """Should compare with string values."""
        assert PromptType.SUMMARY == "summary"
        assert PromptType.SYSTEM == "system"
        assert PromptType.REALTIME_SCORING == "realtime_scoring"


class TestPromptTemplateCreate:
    """Test PromptTemplateCreate model."""

    def test_create_with_all_fields(self):
        """Should create with all required fields."""
        template = PromptTemplateCreate(
            name="Test Template",
            prompt_type=PromptType.SUMMARY,
            category="sales",
            template="Hello {{ name }}!",
            variables=["name"],
        )
        assert template.name == "Test Template"
        assert template.prompt_type == PromptType.SUMMARY
        assert template.category == "sales"
        assert template.template == "Hello {{ name }}!"
        assert template.variables == ["name"]
        assert template.is_active is True
        assert template.is_default is False

    def test_create_with_defaults(self):
        """Should use default values for optional fields."""
        template = PromptTemplateCreate(
            name="Test Template",
            prompt_type=PromptType.SYSTEM,
            template="Static template",
        )
        assert template.category == "common"
        assert template.variables == []
        assert template.is_active is True
        assert template.is_default is False

    def test_create_auto_extracts_variables(self):
        """Should auto-extract variables from template."""
        template = PromptTemplateCreate(
            name="Test Template",
            prompt_type=PromptType.SUMMARY,
            template="Hello {{ name }}, your score is {{ score }} out of {{ total }}.",
        )
        assert "name" in template.variables
        assert "score" in template.variables
        assert "total" in template.variables
        assert len(template.variables) == 3

    def test_create_extracts_variables_with_filters(self):
        """Should extract variables with Jinja2 filters."""
        template = PromptTemplateCreate(
            name="Test Template",
            prompt_type=PromptType.SUMMARY,
            template="{{ name|upper }} scored {{ score|round }} points",
        )
        assert "name" in template.variables
        assert "score" in template.variables

    def test_create_extracts_variables_with_attributes(self):
        """Should extract variables with attribute access."""
        template = PromptTemplateCreate(
            name="Test Template",
            prompt_type=PromptType.SUMMARY,
            template="User: {{ user.name }}, Age: {{ user.age }}",
        )
        assert "user" in template.variables

    def test_create_preserves_explicit_variables(self):
        """Should use explicit variables when provided."""
        template = PromptTemplateCreate(
            name="Test Template",
            prompt_type=PromptType.SUMMARY,
            template="Hello {{ name }}!",
            variables=["custom_var"],
        )
        assert template.variables == ["custom_var"]

    def test_create_removes_duplicate_variables(self):
        """Should remove duplicate variables while preserving order."""
        template = PromptTemplateCreate(
            name="Test Template",
            prompt_type=PromptType.SUMMARY,
            template="{{ name }} {{ name }} {{ score }} {{ name }}",
        )
        assert template.variables == ["name", "score"]

    def test_create_validates_name_length(self):
        """Should validate name max length."""
        with pytest.raises(ValidationError) as exc_info:
            PromptTemplateCreate(
                name="x" * 256,
                prompt_type=PromptType.SUMMARY,
                template="Test",
            )
        assert "name" in str(exc_info.value)

    def test_create_validates_empty_name(self):
        """Should reject empty name."""
        with pytest.raises(ValidationError):
            PromptTemplateCreate(
                name="",
                prompt_type=PromptType.SUMMARY,
                template="Test",
            )

    def test_create_validates_empty_template(self):
        """Should reject empty template."""
        with pytest.raises(ValidationError):
            PromptTemplateCreate(
                name="Test",
                prompt_type=PromptType.SUMMARY,
                template="",
            )

    def test_create_rejects_extra_fields(self):
        """Should reject extra fields when extra='forbid'."""
        with pytest.raises(ValidationError):
            PromptTemplateCreate(
                name="Test",
                prompt_type=PromptType.SUMMARY,
                template="Test",
                unknown_field="value",
            )

    def test_create_rejects_legacy_dict_variables(self):
        """Should reject legacy dict/object variables instead of silently coercing keys."""
        with pytest.raises(ValidationError) as exc_info:
            PromptTemplateCreate(
                name="Legacy Variables",
                prompt_type=PromptType.REALTIME_SCORING,
                template="Score {{ score }}",
                variables={"score": "number"},
            )
        assert "variables must be a list" in str(exc_info.value)

    def test_create_rejects_invalid_jinja_template(self):
        """Should reject invalid Jinja before saving."""
        with pytest.raises(ValidationError) as exc_info:
            PromptTemplateCreate(
                name="Broken",
                prompt_type=PromptType.SUMMARY,
                template="Hello {{ name",
            )
        assert "valid Jinja2" in str(exc_info.value)


class TestPromptTemplateUpdate:
    """Test PromptTemplateUpdate model."""

    def test_update_all_fields(self):
        """Should allow updating all fields."""
        update = PromptTemplateUpdate(
            name="Updated Name",
            prompt_type=PromptType.EXTRACTION,
            category="presentation",
            template="Updated {{ content }}",
            variables=["content"],
            is_active=False,
            is_default=True,
        )
        assert update.name == "Updated Name"
        assert update.prompt_type == PromptType.EXTRACTION

    def test_update_partial(self):
        """Should allow partial updates."""
        update = PromptTemplateUpdate(name="Only Name")
        assert update.name == "Only Name"
        assert update.template is None
        assert update.is_active is None

    def test_update_empty_is_valid(self):
        """Should allow empty update (no changes)."""
        update = PromptTemplateUpdate()
        assert update.name is None
        assert update.template is None

    def test_update_re_extracts_variables_on_template_change(self):
        """Should re-extract variables when template is updated."""
        update = PromptTemplateUpdate(template="New {{ var1 }} and {{ var2 }}")
        assert "var1" in update.variables
        assert "var2" in update.variables

    def test_update_preserves_explicit_variables(self):
        """Should use explicit variables over auto-extraction."""
        update = PromptTemplateUpdate(
            template="{{ a }} {{ b }}",
            variables=["custom"],
        )
        assert update.variables == ["custom"]

    def test_update_rejects_variables_dict(self):
        """Updates must reject historical dict-shaped variables before persistence."""
        with pytest.raises(ValidationError):
            PromptTemplateUpdate(variables={"score": "number"})


class TestPromptTemplate:
    """Test PromptTemplate full model."""

    def test_template_with_all_fields(self):
        """Should create full template with all fields."""
        now = datetime.now(UTC)
        template_id = uuid4()
        template = PromptTemplate(
            id=template_id,
            name="Full Template",
            prompt_type=PromptType.SCORING,
            category="sales",
            template="Score: {{ score }}",
            variables=["score"],
            is_active=True,
            is_default=True,
            is_system=True,
            created_at=now,
            updated_at=now,
        )
        assert template.id == template_id
        assert template.is_system is True
        assert template.created_at == now

    def test_template_from_attributes(self):
        """Should support from_attributes config."""
        # Simulate ORM object
        class FakeORM:
            id = uuid4()
            name = "ORM Template"
            prompt_type = PromptType.WELCOME
            category = "sales"
            template = "Welcome!"
            variables = []
            is_active = True
            is_default = False
            is_system = False
            created_at = datetime.now(UTC)
            updated_at = datetime.now(UTC)

        orm_obj = FakeORM()
        template = PromptTemplate.model_validate(orm_obj)
        assert template.name == "ORM Template"

    def test_template_validates_json_string_variables(self):
        """Should parse JSON string variables from database."""
        now = datetime.now(UTC)
        template = PromptTemplate(
            id=uuid4(),
            name="Test",
            prompt_type=PromptType.SUMMARY,
            template="Hello",
            variables='["var1", "var2"]',
            is_active=True,
            is_default=False,
            is_system=False,
            created_at=now,
            updated_at=now,
        )
        assert template.variables == ["var1", "var2"]

    def test_template_rejects_invalid_json_variables(self):
        """Should reject invalid JSON string variables for governance visibility."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            PromptTemplate(
                id=uuid4(),
                name="Test",
                prompt_type=PromptType.SUMMARY,
                template="Hello",
                variables="invalid json",
                is_active=True,
                is_default=False,
                is_system=False,
                created_at=now,
                updated_at=now,
            )

    def test_create_rejects_object_shaped_variables(self):
        """Should reject historical object-shaped variable schemas on save."""
        with pytest.raises(ValidationError):
            PromptTemplateCreate(
                name="Bad Variables",
                prompt_type=PromptType.REALTIME_SCORING,
                template="Score {{ score }}",
                variables={"score": "number"},
            )


class TestScenarioPromptCreate:
    """Test ScenarioPromptCreate model."""

    def test_create_with_required_fields(self):
        """Should create with required fields."""
        assignment = ScenarioPromptCreate(
            scenario_type="sales",
            prompt_type="summary",
            template_id=uuid4(),
        )
        assert assignment.scenario_type == "sales"
        assert assignment.scenario_id is None
        assert assignment.is_active is True

    def test_create_with_scenario_id(self):
        """Should support optional scenario_id."""
        assignment = ScenarioPromptCreate(
            scenario_type="presentation",
            scenario_id="ppt-123",
            prompt_type="extraction",
            template_id=uuid4(),
        )
        assert assignment.scenario_id == "ppt-123"


class TestScenarioPrompt:
    """Test ScenarioPrompt full model."""

    def test_scenario_prompt_with_all_fields(self):
        """Should create full scenario prompt."""
        now = datetime.now(UTC)
        prompt_id = uuid4()
        template_id = uuid4()
        assignment = ScenarioPrompt(
            id=prompt_id,
            scenario_type="sales",
            scenario_id="scenario-1",
            prompt_type="summary",
            template_id=template_id,
            is_active=True,
            created_at=now,
        )
        assert assignment.id == prompt_id
        assert assignment.template_id == template_id


class TestPromptRenderRequest:
    """Test PromptRenderRequest model."""

    def test_render_request_with_variables(self):
        """Should accept template_id and variables."""
        request = PromptRenderRequest(
            template_id=uuid4(),
            variables={"name": "John", "score": 100},
        )
        assert isinstance(request.template_id, UUID)
        assert request.variables["name"] == "John"

    def test_render_request_empty_variables(self):
        """Should allow empty variables dict."""
        request = PromptRenderRequest(template_id=uuid4())
        assert request.variables == {}

    def test_render_request_rejects_extra_fields(self):
        """Should reject extra fields."""
        with pytest.raises(ValidationError):
            PromptRenderRequest(
                template_id=uuid4(),
                unknown="value",
            )


class TestVariableExtractionEdgeCases:
    """Test edge cases for variable extraction."""

    def test_no_variables_in_template(self):
        """Should handle template with no variables."""
        template = PromptTemplateCreate(
            name="Static",
            prompt_type=PromptType.SYSTEM,
            template="This is a static template with no variables.",
        )
        assert template.variables == []

    def test_complex_jinja2_expressions(self):
        """Should extract only variable names from complex expressions."""
        template = PromptTemplateCreate(
            name="Complex",
            prompt_type=PromptType.SUMMARY,
            template="""
            {% if condition %}
                {{ name|upper }}
            {% endif %}
            {% for item in items %}
                {{ item.value }}
            {% endfor %}
            """,
        )
        # Should extract: condition, name, items, item
        assert "name" in template.variables
        assert "condition" in template.variables
        assert "items" in template.variables

    def test_nested_braces_rejected_as_invalid_jinja(self):
        """Malformed nested braces should be rejected before saving."""
        with pytest.raises(ValidationError) as exc_info:
            PromptTemplateCreate(
                name="Nested",
                prompt_type=PromptType.SUMMARY,
                template="{{ outer {{ not_this }} }}",
            )
        assert "valid Jinja2" in str(exc_info.value)
