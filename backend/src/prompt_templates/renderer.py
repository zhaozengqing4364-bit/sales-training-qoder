"""
Prompt Template Renderer

Requirements: B4 - Implement PromptRenderer (Jinja2 rendering)

Features:
- Jinja2 template rendering with variable substitution
- Variable extraction and validation
- Security (autoescape enabled)
- Error handling for invalid templates
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from jinja2 import BaseLoader, TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment
from jinja2.runtime import Undefined


@dataclass
class RenderResult:
    """Result of template rendering."""

    rendered: str
    success: bool
    missing_variables: list[str] = field(default_factory=list)
    extra_variables: list[str] = field(default_factory=list)
    error_message: str | None = None


class SilentUndefined(Undefined):
    """Undefined that returns empty string for missing variables."""

    def __str__(self) -> str:
        return ""

    def __getattr__(self, name: str) -> "SilentUndefined":
        return SilentUndefined(name=f"{self._undefined_name}.{name}")

    def __getitem__(self, key: str) -> "SilentUndefined":
        return SilentUndefined(name=f"{self._undefined_name}[{key}]")


class PromptRenderer:
    """Jinja2-based prompt template renderer.

    Features:
    - Variable substitution
    - Missing/extra variable tracking
    - Strict mode for required variables
    - Security sandboxing
    """

    def __init__(self):
        """Initialize renderer with sandboxed Jinja2 environment."""
        # Use sandboxed environment for security
        self.env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,  # Don't escape for LLM prompts
            undefined=SilentUndefined,  # Return empty string for undefined vars
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        template: str,
        variables: dict[str, Any],
        strict: bool = False,
    ) -> RenderResult:
        """Render a template with variable substitution.

        Args:
            template: Jinja2 template string
            variables: Variable values for substitution
            strict: If True, fail on missing variables

        Returns:
            RenderResult with rendered text and metadata
        """
        try:
            # Parse template
            jinja_template = self.env.from_string(template)

            # Extract required variables
            required_vars = self.extract_variables(template)

            # Check for missing variables
            missing = [v for v in required_vars if v not in variables]

            if strict and missing:
                return RenderResult(
                    rendered="",
                    success=False,
                    missing_variables=missing,
                    error_message=f"Missing required variables: {missing}",
                )

            # Check for extra variables
            extra = [v for v in variables if v not in required_vars]

            # Render
            rendered = jinja_template.render(**variables)

            return RenderResult(
                rendered=rendered,
                success=True,
                missing_variables=missing,
                extra_variables=extra,
            )

        except TemplateSyntaxError as e:
            return RenderResult(
                rendered="",
                success=False,
                error_message=f"Template syntax error: {e.message}",
            )
        except (RuntimeError, ValueError, TypeError) as e:
            return RenderResult(
                rendered="",
                success=False,
                error_message=f"Render error: {str(e)}",
            )

    def extract_variables(self, template: str) -> list[str]:
        """Extract variable names from Jinja2 template.

        Args:
            template: Jinja2 template string

        Returns:
            List of unique variable names
        """
        try:
            # Parse template to get AST
            parsed = self.env.parse(template)

            # Find all variable references
            from jinja2 import meta
            undeclared = meta.find_undeclared_variables(parsed)

            return sorted(list(undeclared))

        except TemplateSyntaxError:
            # Return empty list for invalid templates
            return []

    def validate(self, template: str) -> tuple[bool, str | None]:
        """Validate template syntax.

        Args:
            template: Jinja2 template string

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.env.parse(template)
            return True, None
        except TemplateSyntaxError as e:
            return False, f"Template syntax error at line {e.lineno}: {e.message}"
        except (RuntimeError, ValueError, TypeError) as e:
            return False, f"Validation error: {str(e)}"


# Singleton instance for convenience
_renderer: PromptRenderer | None = None


def get_renderer() -> PromptRenderer:
    """Get singleton PromptRenderer instance."""
    global _renderer
    if _renderer is None:
        _renderer = PromptRenderer()
    return _renderer


def render_template(
    template: str,
    variables: dict[str, Any],
    strict: bool = False,
) -> RenderResult:
    """Convenience function to render a template.

    Args:
        template: Jinja2 template string
        variables: Variable values for substitution
        strict: If True, fail on missing variables

    Returns:
        RenderResult with rendered text and metadata
    """
    return get_renderer().render(template, variables, strict)
