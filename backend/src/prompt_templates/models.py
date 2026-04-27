"""
Pydantic Models for Prompt Templates

Requirements: B2 - Create Pydantic models for prompt templates

Features:
- PromptTemplate: Full model with all fields
- PromptTemplateCreate: Input model for creation with auto variable extraction
- PromptTemplateUpdate: Input model for partial updates
- ScenarioPrompt: Link between scenarios and templates
- PromptType: Enum for prompt type classification
- Variable extraction from Jinja2 templates
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PromptType(str, Enum):
    """Prompt type classification."""

    SUMMARY = "summary"
    SYSTEM = "system"
    SYSTEM_PROMPT = "system_prompt"
    EXTRACTION = "extraction"
    SCORING = "scoring"
    REALTIME_SCORING = "realtime_scoring"
    STAGE = "stage"
    FUZZY_DETECTION = "fuzzy_detection"
    REALTIME_SCORING = "realtime_scoring"
    INTERRUPTION = "interruption"
    TRACKING = "tracking"
    WELCOME = "welcome"
    EVALUATION = "evaluation"
    REPORT = "report"
    REALTIME_SCORING = "realtime_scoring"




def _normalize_variable_names(value: Any) -> list[str]:
    """Normalize template variable metadata and reject historical dict-shaped payloads.

    Prompt variable metadata is a list of variable names. Dict-shaped rows are
    treated as governance issues because key/value schema objects hide runtime
    contract drift and previously caused invalid templates to be skipped.
    """
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("variables must be a JSON list of strings") from exc
        value = parsed
    if isinstance(value, dict):
        raise ValueError("variables must be a list of strings, not an object")
    if not isinstance(value, list):
        raise ValueError("variables must be a list of strings")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("variables must contain only strings")
        variable = item.strip()
        if not variable:
            raise ValueError("variables must not contain blank names")
        if variable not in normalized:
            normalized.append(variable)
    return normalized


def _ensure_variables_are_list(value: Any) -> list[str]:
    return _normalize_variable_names(value)


class PromptTemplateBase(BaseModel):
    """Base model for prompt templates."""

    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    prompt_type: PromptType = Field(..., description="Type of prompt")
    category: str = Field(
        default="common", min_length=1, max_length=100, description="Category for grouping"
    )
    template: str = Field(..., min_length=1, description="Jinja2 template string")
    variables: list[str] = Field(
        default_factory=list, description="Variable names used in template"
    )
    is_active: bool = Field(default=True, description="Whether template is active")
    is_default: bool = Field(default=False, description="Whether this is the default for its type")

    @field_validator("variables", mode="before")
    @classmethod
    def validate_variable_list(cls, value: Any) -> list[str]:
        """Reject legacy dict/object variables at write time; DB repair is explicit."""
        if value is None:
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("variables must be a list of strings") from exc
            value = parsed
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ValueError("variables must be a list of non-empty strings")
        return list(dict.fromkeys(value))

    @field_validator("template")
    @classmethod
    def validate_template_syntax(cls, value: str) -> str:
        """Validate Jinja syntax before a template can be saved."""
        try:
            from jinja2.sandbox import SandboxedEnvironment

            SandboxedEnvironment(autoescape=False).parse(value)
        except Exception as exc:
            raise ValueError("template must be valid Jinja2 syntax") from exc
        return value


    @field_validator("variables", mode="before")
    @classmethod
    def validate_variables_metadata(cls, value: Any) -> list[str]:
        return _ensure_variables_are_list(value)


class PromptTemplateCreate(PromptTemplateBase):
    """Model for creating a new prompt template."""

    model_config = ConfigDict(extra="forbid")

    @field_validator("variables", mode="before")
    @classmethod
    def validate_author_variables(cls, v: Any) -> list[str]:
        return _normalize_prompt_variables(v)

    @model_validator(mode="after")
    def extract_variables(self) -> PromptTemplateCreate:
        """Extract variables from template if not explicitly provided."""
        if not self.variables and self.template:
            self.variables = self._extract_variables_from_template(self.template)
        return self

    @staticmethod
    def _extract_variables_from_template(template: str) -> list[str]:
        """
        Extract Jinja2 variable names from template.

        Strategy:
        1. Extract variables from output blocks in appearance order ({{ ... }}).
        2. For valid Jinja2 templates, merge undeclared vars from AST (captures if/for conditions).
        3. Keep first-seen order for output vars and append missing AST vars deterministically.

        Returns:
            List of unique variable names.
        """

        def dedupe(values: list[str]) -> list[str]:
            return list(dict.fromkeys(values))

        def extract_output_vars(raw_template: str) -> list[str]:
            """Extract first identifier from each top-level output block, tolerating nested braces."""
            variables: list[str] = []
            depth = 0
            start = -1
            index = 0

            while index < len(raw_template) - 1:
                token = raw_template[index : index + 2]

                if token == "{{":
                    if depth == 0:
                        start = index + 2
                    depth += 1
                    index += 2
                    continue

                if token == "}}" and depth > 0:
                    depth -= 1
                    if depth == 0 and start >= 0:
                        expression = raw_template[start:index]
                        previous = None
                        cleaned = expression
                        while previous != cleaned:
                            previous = cleaned
                            cleaned = re.sub(r"\{\{[^{}]*\}\}", " ", cleaned)

                        match = re.search(r"[A-Za-z_][A-Za-z0-9_]*", cleaned)
                        if match:
                            variables.append(match.group(0))
                        start = -1
                    index += 2
                    continue

                index += 1

            return dedupe(variables)

        output_vars = extract_output_vars(template)

        try:
            from jinja2 import meta
            from jinja2.sandbox import SandboxedEnvironment

            env = SandboxedEnvironment(autoescape=False)
            parsed = env.parse(template)
            undeclared_vars = sorted(meta.find_undeclared_variables(parsed))
        except Exception:
            undeclared_vars = []

        merged = list(output_vars)
        for variable in undeclared_vars:
            if variable not in merged:
                merged.append(variable)

        return dedupe(merged)


class PromptTemplateUpdate(BaseModel):
    """Model for updating an existing prompt template (partial update)."""

    model_config = ConfigDict(extra="forbid")

    @field_validator("variables", mode="before")
    @classmethod
    def validate_author_variables(cls, v: Any) -> list[str]:
        return _normalize_prompt_variables(v)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    prompt_type: PromptType | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    template: str | None = None
    variables: list[str] | None = None
    is_active: bool | None = None
    is_default: bool | None = None

    @field_validator("variables", mode="before")
    @classmethod
    def validate_variables_metadata(cls, value: Any) -> list[str]:
        return _ensure_variables_are_list(value)

    @model_validator(mode="after")
    def extract_variables_on_template_change(self) -> PromptTemplateUpdate:
        """Re-extract variables if template is updated."""
        if self.template is not None and self.variables is None:
            self.variables = PromptTemplateCreate._extract_variables_from_template(self.template)
        return self

    @field_validator("variables", mode="before")
    @classmethod
    def validate_control_plane_variables(cls, value: Any) -> list[str] | None:
        """Control-plane writes must provide a list[str], never a dict/map."""
        if value is None:
            return None
        return _normalize_variable_list(value, allow_json_string=False)


class PromptTemplate(PromptTemplateBase):
    """Full prompt template model (database representation)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique identifier")
    is_system: bool = Field(default=False, description="Whether this is a system template")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    governance_status: str = Field(
        default="valid",
        description="valid or needs_review for historical rows requiring governance action",
    )
    governance_issues: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def validate_variables(cls, v: Any) -> list[str]:
        """Ensure variables is a visible, valid list of strings."""
        return _ensure_variables_are_list(v)


class ScenarioPromptBase(BaseModel):
    """Base model for scenario prompt assignments."""

    scenario_type: str = Field(
        ..., min_length=1, max_length=50, description="Type of scenario (sales, presentation)"
    )
    scenario_id: str | None = Field(
        default=None, max_length=255, description="Optional specific scenario ID"
    )
    prompt_type: str = Field(
        ..., min_length=1, max_length=50, description="Type of prompt for this assignment"
    )
    template_id: UUID = Field(..., description="Reference to prompt template")
    is_active: bool = Field(default=True, description="Whether this assignment is active")


class ScenarioPromptCreate(ScenarioPromptBase):
    """Model for creating a scenario prompt assignment."""

    model_config = ConfigDict(extra="forbid")


class ScenarioPrompt(ScenarioPromptBase):
    """Full scenario prompt model (database representation)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")


class PromptTemplateResponse(BaseModel):
    """Response model for API (includes template with resolved variables)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    prompt_type: PromptType
    category: str
    template: str
    variables: list[str]
    is_active: bool
    is_default: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime
    governance_status: str = "valid"
    governance_issues: list[str] = Field(default_factory=list)


class ScenarioPromptResponse(BaseModel):
    """Response model for scenario prompt assignments."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scenario_type: str
    scenario_id: str | None
    prompt_type: str
    template: PromptTemplateResponse | None = None  # Expanded template
    is_active: bool
    created_at: datetime


class PromptRenderRequest(BaseModel):
    """Request to render a prompt template with variables."""

    model_config = ConfigDict(extra="forbid")

    template_id: UUID = Field(..., description="Template to render")
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Variable values for rendering"
    )


class PromptRenderResponse(BaseModel):
    """Response with rendered prompt."""

    model_config = ConfigDict(from_attributes=True)

    template_id: UUID
    rendered: str = Field(..., description="Rendered template string")
    missing_variables: list[str] = Field(
        default_factory=list, description="Variables that were not provided"
    )
    extra_variables: list[str] = Field(
        default_factory=list, description="Variables provided but not in template"
    )
