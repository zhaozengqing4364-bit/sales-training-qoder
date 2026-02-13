"""
Tests for Prompt Renderer (Jinja2)

TDD Tests for Task B4: Implement PromptRenderer
"""

import pytest
from uuid import uuid4

from prompt_templates.renderer import PromptRenderer, RenderResult, render_template


class TestPromptRenderer:
    """Test the PromptRenderer class"""

    @pytest.fixture
    def renderer(self):
        """Create a fresh renderer instance"""
        return PromptRenderer()

    def test_simple_variable_render(self, renderer):
        """Test rendering with simple variables"""
        result = renderer.render(
            "Hello {{ name }}!",
            {"name": "World"}
        )
        assert result.success is True
        assert result.rendered == "Hello World!"
        assert result.missing_variables == []
        assert result.extra_variables == []

    def test_multiple_variables(self, renderer):
        """Test rendering with multiple variables"""
        result = renderer.render(
            "{{ greeting }}, {{ name }}! Welcome to {{ place }}.",
            {"greeting": "Hello", "name": "Alice", "place": "Wonderland"}
        )
        assert result.success is True
        assert result.rendered == "Hello, Alice! Welcome to Wonderland."

    def test_missing_variables_tracking(self, renderer):
        """Test tracking of missing variables"""
        result = renderer.render(
            "Hello {{ name }}, you are {{ age }} years old.",
            {"name": "Bob"}
        )
        assert result.success is True
        assert "age" in result.missing_variables
        assert result.rendered == "Hello Bob, you are  years old."

    def test_extra_variables_tracking(self, renderer):
        """Test tracking of extra variables"""
        result = renderer.render(
            "Hello {{ name }}!",
            {"name": "Alice", "extra": "value"}
        )
        assert result.success is True
        assert "extra" in result.extra_variables

    def test_strict_mode_failure(self, renderer):
        """Test that strict mode fails on missing variables"""
        result = renderer.render(
            "Hello {{ name }}!",
            {},
            strict=True
        )
        assert result.success is False
        assert "Missing required variables" in result.error_message
        assert "name" in result.missing_variables

    def test_strict_mode_success(self, renderer):
        """Test that strict mode succeeds when all vars provided"""
        result = renderer.render(
            "Hello {{ name }}!",
            {"name": "World"},
            strict=True
        )
        assert result.success is True
        assert result.rendered == "Hello World!"

    def test_template_syntax_error(self, renderer):
        """Test handling of template syntax errors"""
        result = renderer.render(
            "Hello {{ name",  # Missing closing braces
            {"name": "World"}
        )
        assert result.success is False
        assert "syntax error" in result.error_message.lower()

    def test_empty_template(self, renderer):
        """Test rendering empty template"""
        result = renderer.render("", {})
        assert result.success is True
        assert result.rendered == ""

    def test_no_variables_template(self, renderer):
        """Test rendering template without variables"""
        result = renderer.render(
            "Static content without variables",
            {"unused": "value"}
        )
        assert result.success is True
        assert result.rendered == "Static content without variables"
        assert "unused" in result.extra_variables

    def test_jinja2_filters(self, renderer):
        """Test using Jinja2 built-in filters"""
        result = renderer.render(
            "Hello {{ name|upper }}!",
            {"name": "world"}
        )
        assert result.success is True
        assert result.rendered == "Hello WORLD!"

    def test_jinja2_default_filter(self, renderer):
        """Test default filter for missing variables"""
        result = renderer.render(
            "Hello {{ name|default('Guest') }}!",
            {}
        )
        assert result.success is True
        assert result.rendered == "Hello Guest!"


class TestRenderResult:
    """Test the RenderResult dataclass"""

    def test_success_result(self):
        """Test creating a successful result"""
        result = RenderResult(
            rendered="Hello World",
            success=True,
            missing_variables=[],
            extra_variables=[]
        )
        assert result.success is True
        assert result.rendered == "Hello World"

    def test_failed_result(self):
        """Test creating a failed result"""
        result = RenderResult(
            rendered="",
            success=False,
            missing_variables=["name"],
            extra_variables=[],
            error_message="Missing required variable"
        )
        assert result.success is False
        assert result.error_message == "Missing required variable"


class TestExtractVariables:
    """Test variable extraction from templates"""

    @pytest.fixture
    def renderer(self):
        return PromptRenderer()

    def test_extract_simple_variables(self, renderer):
        """Test extracting simple variables"""
        vars = renderer.extract_variables("Hello {{ name }}, welcome to {{ place }}")
        assert sorted(vars) == ["name", "place"]

    def test_extract_with_filters(self, renderer):
        """Test extraction with filters applied"""
        vars = renderer.extract_variables("{{ name|upper }} - {{ age|default(0) }}")
        assert sorted(vars) == ["age", "name"]

    def test_extract_no_variables(self, renderer):
        """Test extraction from static template"""
        vars = renderer.extract_variables("Static content")
        assert vars == []

    def test_extract_duplicates_removed(self, renderer):
        """Test that duplicate variables are deduplicated"""
        vars = renderer.extract_variables("{{ name }} {{ name }} {{ other }}")
        assert sorted(vars) == ["name", "other"]

    def test_extract_invalid_template(self, renderer):
        """Test extraction from invalid template"""
        vars = renderer.extract_variables("{{ invalid")
        assert vars == []


class TestValidate:
    """Test template validation"""

    @pytest.fixture
    def renderer(self):
        return PromptRenderer()

    def test_valid_template(self, renderer):
        """Test validating a valid template"""
        is_valid, error = renderer.validate("Hello {{ name }}!")
        assert is_valid is True
        assert error is None

    def test_invalid_template_syntax(self, renderer):
        """Test validating invalid template syntax"""
        is_valid, error = renderer.validate("Hello {{ name")
        assert is_valid is False
        assert error is not None
        assert "syntax error" in error.lower()

    def test_valid_complex_template(self, renderer):
        """Test validating complex valid template"""
        template = """
        {% if user %}
            Hello {{ user.name }}!
        {% else %}
            Hello Guest!
        {% endif %}
        """
        is_valid, error = renderer.validate(template)
        assert is_valid is True


class TestConvenienceFunction:
    """Test the render_template convenience function"""

    def test_convenience_function(self):
        """Test that render_template uses default renderer"""
        result = render_template(
            "Hello {{ name }}!",
            {"name": "World"}
        )
        assert result.success is True
        assert result.rendered == "Hello World!"
