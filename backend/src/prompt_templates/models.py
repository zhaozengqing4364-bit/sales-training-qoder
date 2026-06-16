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
    INTERRUPTION = "interruption"
    TRACKING = "tracking"
    WELCOME = "welcome"
    EVALUATION = "evaluation"
    REPORT = "report"


ALLOWED_PROMPT_TYPE_VALUES = tuple(item.value for item in PromptType)

PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION = "ai_coach_conversation_generation"
PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION = (
    "business_etiquette_question_generation"
)


class PromptBusinessPurpose(str, Enum):
    """Business-level prompt purpose used by operator/runtime selection."""

    AI_COACH_CONVERSATION_GENERATION = PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION
    BUSINESS_ETIQUETTE_QUESTION_GENERATION = (
        PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION
    )


ALLOWED_PROMPT_BUSINESS_PURPOSE_VALUES = tuple(
    item.value for item in PromptBusinessPurpose
)

PROMPT_TYPE_DISPLAY_LABELS: dict[str, str] = {
    "summary": "销售对话总结",
    "system": "系统指令",
    "system_prompt": "系统提示词",
    "extraction": "信息提取",
    "scoring": "评分规则",
    "realtime_scoring": "实时评分",
    "stage": "阶段判断",
    "fuzzy_detection": "模糊检测",
    "interruption": "打断判断",
    "tracking": "要点跟踪",
    "welcome": "欢迎话术",
    "evaluation": "实时评价",
    "report": "综合报告",
}

PROMPT_BUSINESS_PURPOSE_DISPLAY_LABELS: dict[str, str] = {
    PROMPT_BUSINESS_PURPOSE_AI_COACH_CONVERSATION: "AI 教练对话生成",
    PROMPT_BUSINESS_PURPOSE_BUSINESS_ETIQUETTE_QUESTION: "商务礼仪题目生成",
}

PROMPT_CATEGORY_DISPLAY_LABELS: dict[str, str] = {
    "common": "通用",
    "presentation": "PPT 演练",
    "sales": "销售训练",
    "sales_bot": "销售实时对练",
    "business_etiquette": "商务礼仪",
    "sales_trainer_ai_coach": "新人训练 AI 教练",
    "system": "系统报告",
}

PROMPT_TEMPLATE_DISPLAY_NAMES: dict[str, str] = {
    "Sales Conversation Summary": "销售对话总结",
    "Default Sales Persona": "默认销售客户人格",
    "PPT Point Extraction": "PPT 要点提取",
    "Interruption Feedback - Vague": "PPT 模糊表达打断反馈",
    "Interruption Detection Rules": "PPT 打断判断规则",
    "Point Tracking Configuration": "PPT 要点跟踪配置",
    "Fuzzy Detection - Uncertain": "销售不确定表达检测",
    "Fuzzy Detection - Filler": "销售填充词检测",
    "Fuzzy Detection - Vague Number": "销售模糊数字检测",
    "Realtime Scoring Rules": "销售实时评分规则",
    "Sales Stage Definition": "销售阶段定义",
    "Welcome Message 1": "销售欢迎话术 1",
    "Welcome Message 2": "销售欢迎话术 2",
    "Welcome Message 3": "销售欢迎话术 3",
    "新人训练路径商务技巧 AI 教练题目生成 v1": "商务礼仪题目草稿生成 v1",
}


def prompt_type_display_label(value: str | PromptType) -> str:
    raw = value.value if isinstance(value, PromptType) else str(value)
    return PROMPT_TYPE_DISPLAY_LABELS.get(raw, raw)


def prompt_category_display_label(value: str) -> str:
    raw = str(value or "").strip()
    return PROMPT_CATEGORY_DISPLAY_LABELS.get(raw, raw or "未分类")


def prompt_business_purpose_display_label(
    value: str | PromptBusinessPurpose | None,
) -> str:
    if value is None:
        return "未指定业务用途"
    raw = value.value if isinstance(value, PromptBusinessPurpose) else str(value)
    raw = raw.strip()
    return PROMPT_BUSINESS_PURPOSE_DISPLAY_LABELS.get(raw, raw or "未指定业务用途")


def prompt_template_display_name(value: str) -> str:
    raw = str(value or "").strip()
    return PROMPT_TEMPLATE_DISPLAY_NAMES.get(raw, raw)


def _normalize_variable_list(value: Any, *, allow_json_string: bool) -> list[str]:
    """Normalize prompt variable metadata to a de-duplicated list[str].

    Control-plane writes reject dict/object variables so invalid historical rows
    stay visible to governance instead of being silently coerced to keys. Existing
    DB reads may accept JSON-encoded list strings when explicitly allowed.
    """
    if value is None:
        return []
    if isinstance(value, str):
        if not allow_json_string:
            raise ValueError("variables must be a list of strings")
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("variables must be a JSON list of strings") from exc
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
            raise ValueError("variables must contain non-empty strings only")
        if variable not in normalized:
            normalized.append(variable)
    return normalized


def _validate_jinja_template(value: str) -> str:
    """Validate author-supplied Jinja2 before saving a template."""
    if not value:
        return value
    try:
        from jinja2.exceptions import TemplateSyntaxError
        from jinja2.sandbox import SandboxedEnvironment

        SandboxedEnvironment(autoescape=False).parse(value)
    except TemplateSyntaxError as exc:
        raise ValueError("template must be valid Jinja2") from exc
    return value


class PromptTemplateGovernanceIssue(BaseModel):
    """Visible governance issue for a historical prompt-template row."""

    code: str
    severity: str = "blocking"
    message: str


class PromptTemplateGovernanceInvalidTemplate(BaseModel):
    """Invalid historical prompt-template row shown to administrators."""

    id: str
    name: str | None = None
    prompt_type: str | None = None
    category: str | None = None
    variables: Any = None
    is_active: bool
    is_default: bool
    updated_at: str | None = None
    issues: list[PromptTemplateGovernanceIssue]
    runtime_status: str
    remediation: str


class PromptTemplateGovernanceStatus(BaseModel):
    """Prompt-template governance status for admin review/remediation."""

    allowed_prompt_types: list[str]
    policy: dict[str, str]
    invalid_count: int
    invalid_templates: list[PromptTemplateGovernanceInvalidTemplate]
    limit: int
    checked_count: int = 0
    active_invalid_count: int = 0
    invalid_active_count: int = 0
    default_conflict_count: int = 0
    issues: list[dict[str, Any]] = Field(default_factory=list)
    rollback_policy: str = "restore from SystemLog before snapshot"
    audit_log_action: str = "prompt_template.governance.remediate_invalid"


class PromptTemplateQuarantineResult(BaseModel):
    """Result of disabling invalid historical prompt templates."""

    checked_count: int
    quarantined_count: int
    issues: list[PromptTemplateGovernanceIssue]
    audit_log_action: str


class PromptTemplateGovernanceRollbackResponse(BaseModel):
    """Safe rollback result for a prompt-template governance migration."""

    template_id: str
    rolled_back: bool
    runtime_status: str
    before: dict[str, Any]
    after: dict[str, Any]
    issues: list[PromptTemplateGovernanceIssue] = Field(default_factory=list)
    safety_overrides: list[str] = Field(default_factory=list)
    audit_log_action: str = "prompt_template.governance_rollback"


class PromptTemplateBase(BaseModel):
    """Base model for prompt templates."""

    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    prompt_type: PromptType = Field(..., description="Type of prompt")
    business_purpose: PromptBusinessPurpose | None = Field(
        default=None,
        description=(
            "Business-level purpose for runtime/operator selection; category remains "
            "the grouping taxonomy."
        ),
    )
    category: str = Field(
        default="common",
        min_length=1,
        max_length=100,
        description="Category for grouping",
    )
    template: str = Field(..., min_length=1, description="Jinja2 template string")
    variables: list[str] = Field(
        default_factory=list, description="Variable names used in template"
    )
    is_active: bool = Field(default=True, description="Whether template is active")
    is_default: bool = Field(
        default=False, description="Whether this is the default for its type"
    )

    @field_validator("template")
    @classmethod
    def validate_template_syntax(cls, value: str) -> str:
        return _validate_jinja_template(value)

    @field_validator("variables", mode="before")
    @classmethod
    def validate_variables_metadata(cls, value: Any) -> list[str]:
        return _normalize_variable_list(value, allow_json_string=False)

    @field_validator("business_purpose", mode="before")
    @classmethod
    def normalize_business_purpose(
        cls,
        value: Any,
    ) -> PromptBusinessPurpose | None:
        if value is None:
            return None
        if isinstance(value, PromptBusinessPurpose):
            return value
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return PromptBusinessPurpose(raw)
        except ValueError as exc:
            raise ValueError("business_purpose must be an allowed value") from exc


class PromptTemplateCreate(PromptTemplateBase):
    """Model for creating a new prompt template."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def extract_variables(self) -> PromptTemplateCreate:
        """Extract variables from template if not explicitly provided."""
        if not self.variables and self.template:
            self.variables = self._extract_variables_from_template(self.template)
        return self

    @staticmethod
    def _extract_variables_from_template(template: str) -> list[str]:
        """Extract unique Jinja2 variable names in deterministic order."""

        def dedupe(values: list[str]) -> list[str]:
            return list(dict.fromkeys(values))

        def extract_output_vars(raw_template: str) -> list[str]:
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

    name: str | None = Field(default=None, min_length=1, max_length=255)
    prompt_type: PromptType | None = None
    business_purpose: PromptBusinessPurpose | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    template: str | None = None
    variables: list[str] | None = None
    is_active: bool | None = None
    is_default: bool | None = None

    @field_validator("template")
    @classmethod
    def validate_template_syntax(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_jinja_template(value)

    @field_validator("variables", mode="before")
    @classmethod
    def validate_variables_metadata(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        return _normalize_variable_list(value, allow_json_string=False)

    @field_validator("business_purpose", mode="before")
    @classmethod
    def normalize_business_purpose(
        cls,
        value: Any,
    ) -> PromptBusinessPurpose | None:
        if value is None:
            return None
        if isinstance(value, PromptBusinessPurpose):
            return value
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return PromptBusinessPurpose(raw)
        except ValueError as exc:
            raise ValueError("business_purpose must be an allowed value") from exc

    @model_validator(mode="after")
    def extract_variables_on_template_change(self) -> PromptTemplateUpdate:
        """Re-extract variables if template is updated without explicit variables."""
        if self.template is not None and self.variables is None:
            self.variables = PromptTemplateCreate._extract_variables_from_template(
                self.template
            )
        return self


class PromptTemplate(PromptTemplateBase):
    """Full prompt template model (database representation)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique identifier")
    is_system: bool = Field(
        default=False, description="Whether this is a system template"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    governance_status: str = Field(
        default="valid",
        description="valid or needs_review for historical rows requiring governance action",
    )
    governance_issues: list[str] = Field(default_factory=list)
    display_name: str = ""
    display_type: str = ""
    display_category: str = ""
    display_business_purpose: str = ""
    binding_count: int = 0
    is_runtime_effective: bool = False
    can_edit_directly: bool = True
    edit_block_reason: str | None = None

    @field_validator("variables", mode="before")
    @classmethod
    def validate_variables(cls, value: Any) -> list[str]:
        return _normalize_variable_list(value, allow_json_string=True)

    @field_validator(
        "display_name",
        "display_type",
        "display_category",
        "display_business_purpose",
        mode="before",
    )
    @classmethod
    def validate_optional_display_text(cls, value: Any) -> str:
        return value if isinstance(value, str) else ""

    @field_validator("edit_block_reason", mode="before")
    @classmethod
    def validate_optional_edit_block_reason(cls, value: Any) -> str | None:
        return value if isinstance(value, str) else None

    @field_validator("binding_count", mode="before")
    @classmethod
    def validate_binding_count(cls, value: Any) -> int:
        return value if isinstance(value, int) else 0

    @field_validator("is_runtime_effective", "can_edit_directly", mode="before")
    @classmethod
    def validate_optional_runtime_flags(cls, value: Any) -> bool:
        return value if isinstance(value, bool) else False

    @field_validator("governance_status", mode="before")
    @classmethod
    def validate_governance_status(cls, value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value
        return "valid"

    @field_validator("governance_issues", mode="before")
    @classmethod
    def validate_governance_issues(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return []

    @model_validator(mode="after")
    def derive_operator_display_fields(self) -> PromptTemplate:
        if not self.display_name:
            self.display_name = prompt_template_display_name(self.name)
        if not self.display_type:
            self.display_type = prompt_type_display_label(self.prompt_type)
        if not self.display_category:
            self.display_category = prompt_category_display_label(self.category)
        if not self.display_business_purpose:
            self.display_business_purpose = prompt_business_purpose_display_label(
                self.business_purpose
            )
        self.can_edit_directly = not self.is_system
        if self.is_system and not self.edit_block_reason:
            self.edit_block_reason = "系统模板不可直接编辑，请先复制为自定义模板。"
        if not self.is_runtime_effective:
            self.is_runtime_effective = bool(
                self.is_active and (self.is_default or self.binding_count > 0)
            )
        return self


class PromptTemplateGovernanceReport(BaseModel):
    """Invalid prompt-template governance report."""

    generated_at: datetime
    mode: str
    issues: list[PromptTemplateGovernanceInvalidTemplate] = Field(default_factory=list)
    migrated_count: int = 0
    audit_action: str = "prompt_template.governance_migrate"


class ScenarioPromptBase(BaseModel):
    """Base model for scenario prompt assignments."""

    scenario_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Type of scenario (sales, presentation)",
    )
    scenario_id: str | None = Field(
        default=None, max_length=255, description="Optional specific scenario ID"
    )
    prompt_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Type of prompt for this assignment",
    )
    template_id: UUID = Field(..., description="Reference to prompt template")
    is_active: bool = Field(
        default=True, description="Whether this assignment is active"
    )


class ScenarioPromptCreate(ScenarioPromptBase):
    """Model for creating a scenario prompt assignment."""

    model_config = ConfigDict(extra="forbid")


class ScenarioPrompt(ScenarioPromptBase):
    """Full scenario prompt model (database representation)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    template_display_name: str | None = None
    display_prompt_type: str | None = None
    display_scenario_type: str | None = None

    @model_validator(mode="after")
    def derive_operator_display_fields(self) -> ScenarioPrompt:
        if not self.display_prompt_type:
            self.display_prompt_type = prompt_type_display_label(self.prompt_type)
        if not self.display_scenario_type:
            self.display_scenario_type = (
                "销售训练" if self.scenario_type == "sales" else
                "PPT 演练" if self.scenario_type == "presentation" else
                self.scenario_type
            )
        return self


class PromptTemplateImpactBinding(BaseModel):
    """Runtime binding impact for one prompt template."""

    id: str
    scenario_type: str
    scenario_id: str | None = None
    prompt_type: str
    is_active: bool
    display_scenario_type: str
    display_prompt_type: str


class PromptTemplateImpactResponse(BaseModel):
    """Read-only impact report for template operations."""

    template_id: str
    display_name: str
    prompt_type: str
    display_type: str
    business_purpose: str | None = None
    display_business_purpose: str
    category: str
    display_category: str
    is_active: bool
    is_default: bool
    is_system: bool
    is_runtime_effective: bool
    can_deactivate: bool
    deactivate_block_reason: str | None = None
    can_set_default: bool
    set_default_block_reason: str | None = None
    can_edit_directly: bool
    edit_block_reason: str | None = None
    binding_count: int
    bindings: list[PromptTemplateImpactBinding] = Field(default_factory=list)
    runtime_consumers: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)


class PromptTemplateRepairDefaultsResponse(BaseModel):
    """Governance repair result for default conflicts and historical variables."""

    dry_run: bool
    checked: int
    repaired: int
    items: list[dict[str, Any]] = Field(default_factory=list)
    audit_action: str | None = None


class PromptTemplateCloneRequest(BaseModel):
    """Request to clone a system or custom prompt template."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=500)


class PromptTemplateResponse(BaseModel):
    """Response model for API (includes template with resolved variables)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    prompt_type: PromptType
    business_purpose: PromptBusinessPurpose | None = None
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
