"""
Prompt Template Service - Core Business Logic

Requirements: B6 - Implement PromptTemplateService

Features:
- CRUD operations for prompt templates
- Scenario-specific template resolution
- Template rendering with variable substitution
- Default template management
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.config_manager import get_config_manager
from common.ai.models import ModelType
from common.error_handling.result import Result
from common.monitoring.logger import get_logger, get_trace_id
from prompt_templates.compiled_contract import (
    PROMPT_CONTRACT_VERSION,
    CompiledPromptContract,
    PromptContractDiagnostic,
    build_prompt_contract_hash,
)
from prompt_templates.loader import get_loader
from prompt_templates.models import (
    PromptRenderRequest,
    PromptRenderResponse,
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateQuarantineResult,
    PromptTemplateUpdate,
    PromptType,
    ScenarioPrompt,
    ScenarioPromptCreate,
)
from prompt_templates.renderer import render_template

logger = get_logger(__name__)
SALES_PROMPT_SCOPE_ALLOWED_TYPES = {"evaluation", "report", "stage", "scoring", "realtime_scoring"}
PROMPT_GOVERNANCE_AUDIT_ACTION = "prompt_template.governance"


class PromptTemplateService:
    """Service for managing prompt templates.

    Provides:
    - CRUD operations for templates
    - Scenario-specific template resolution
    - Template rendering with variable substitution
    """

    def __init__(self, db_session: AsyncSession | None = None):
        """Initialize service.

        Args:
            db_session: SQLAlchemy async session
        """
        self.db = db_session
        self.loader = get_loader()

    @staticmethod
    def _audit_identifier(actor: Any | None) -> tuple[str | None, str]:
        if actor is None:
            return None, "system"
        actor_id = getattr(actor, "user_id", None) or getattr(actor, "id", None)
        identifier = getattr(actor, "email", None) or getattr(actor, "name", None) or str(actor_id or "system")
        return str(actor_id) if actor_id else None, identifier

    @staticmethod
    def _snapshot_db_template(row: Any) -> dict[str, Any]:
        return {
            "id": str(getattr(row, "id", "")),
            "name": getattr(row, "name", None),
            "prompt_type": getattr(row, "prompt_type", None),
            "category": getattr(row, "category", None),
            "template": getattr(row, "template", None),
            "variables": getattr(row, "variables", None),
            "is_active": bool(getattr(row, "is_active", False)),
            "is_default": bool(getattr(row, "is_default", False)),
            "is_system": bool(getattr(row, "is_system", False)),
        }

    @staticmethod
    def _legacy_governance_issue_codes(row: Any) -> list[str]:
        issues: list[str] = []
        variables = getattr(row, "variables", None)
        if isinstance(variables, dict):
            issues.append("variables_object_migratable")
        elif isinstance(variables, str):
            try:
                parsed = json.loads(variables)
            except json.JSONDecodeError:
                issues.append("variables_string_not_json_array")
            else:
                if isinstance(parsed, dict):
                    issues.append("variables_object_migratable")
                elif not isinstance(parsed, list):
                    issues.append("variables_json_not_array")
        elif variables is not None and not isinstance(variables, list):
            issues.append("variables_not_array")

        prompt_type = str(getattr(row, "prompt_type", "") or "")
        if prompt_type:
            try:
                PromptType(prompt_type)
            except ValueError:
                issues.append("prompt_type_not_allowed")
        return issues

    @staticmethod
    def _normalize_legacy_variables(value: Any) -> list[str]:
        if isinstance(value, dict):
            return [str(key) for key in value.keys() if str(key).strip()]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            if isinstance(parsed, dict):
                return [str(key) for key in parsed.keys() if str(key).strip()]
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    async def _queue_prompt_governance_audit(
        self,
        *,
        action: str,
        actor: Any | None,
        template_id: str,
        reason: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        issues: list[Any],
        status: str = "success",
    ) -> None:
        from common.db.models import SystemLog

        actor_id, identifier = self._audit_identifier(actor)
        details = {
            "template_id": template_id,
            "reason": reason,
            "issues": issues,
            "before": before,
            "after": after,
            "rollback_supported": before is not None,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.db.add(
            SystemLog(
                action=action,
                user_id=actor_id,
                user_identifier=identifier,
                status=status,
                details=json.dumps(details, ensure_ascii=False, default=str),
                created_at=datetime.now(UTC),
            )
        )

    def _add_audit_log(
        self,
        *,
        action: str,
        status: str,
        actor_user_id: str | None,
        actor_user_identifier: str | None,
        details: dict[str, Any],
    ) -> None:
        from common.db.models import SystemLog

        self.db.add(
            SystemLog(
                action=action,
                user_id=actor_user_id,
                user_identifier=actor_user_identifier or actor_user_id or "system",
                status=status,
                details=json.dumps(details, ensure_ascii=False, default=str),
                created_at=datetime.now(UTC),
            )
        )

    def _queue_audit_log(
        self,
        *,
        action: str,
        actor: Any | None,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        reason: str,
        status: str = "success",
    ) -> None:
        if actor is None:
            return
        actor_id, identifier = self._audit_identifier(actor)
        self._add_audit_log(
            action=action,
            status=status,
            actor_user_id=actor_id,
            actor_user_identifier=identifier,
            details={
                "reason": reason,
                "before": before,
                "after": after,
                "trace_id": get_trace_id(),
                "rollback_supported": before is not None,
            },
        )

    @staticmethod
    def _safe_model_validate(db_template: Any) -> PromptTemplate | None:
        try:
            template = PromptTemplate.model_validate(db_template)
            if template.governance_issues:
                logger.warning(
                    "Prompt template row requires governance remediation",
                    template_id=str(template.id),
                    governance_issues=template.governance_issues,
                    is_active=template.is_active,
                )
            return template
        except ValidationError as exc:
            logger.warning(
                "Invalid prompt template row requires governance migration",
                template_id=getattr(db_template, "id", None),
                prompt_type=getattr(db_template, "prompt_type", None),
                is_active=getattr(db_template, "is_active", None),
                error=str(exc),
            )
            return None

    @staticmethod
    def _template_snapshot(db_template: Any) -> dict[str, Any]:
        return {
            "id": str(getattr(db_template, "id", "") or ""),
            "name": str(getattr(db_template, "name", "") or ""),
            "prompt_type": str(getattr(db_template, "prompt_type", "") or ""),
            "category": str(getattr(db_template, "category", "") or ""),
            "variables": getattr(db_template, "variables", None),
            "is_active": bool(getattr(db_template, "is_active", False)),
            "is_default": bool(getattr(db_template, "is_default", False)),
            "updated_at": (
                getattr(db_template, "updated_at", None).isoformat()
                if getattr(db_template, "updated_at", None)
                else None
            ),
        }

    @classmethod
    def _governance_issues_for_row(cls, db_template: Any) -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        prompt_type = str(getattr(db_template, "prompt_type", "") or "").strip()
        try:
            PromptType(prompt_type)
        except ValueError:
            issues.append(
                {
                    "code": "invalid_prompt_type",
                    "severity": "blocking",
                    "message": f"prompt_type '{prompt_type}' is not in the allowed runtime taxonomy",
                }
            )

        variables = getattr(db_template, "variables", None)
        parsed_variables = variables
        if isinstance(variables, str):
            try:
                parsed_variables = json.loads(variables)
            except json.JSONDecodeError:
                issues.append(
                    {
                        "code": "variables_invalid_json",
                        "severity": "blocking",
                        "message": "variables is a string but not valid JSON",
                    }
                )
                parsed_variables = None
        if isinstance(parsed_variables, dict):
            issues.append(
                {
                    "code": "variables_object_schema",
                    "severity": "blocking",
                    "message": "variables must be a list[str]; object-shaped historical rows are disabled before runtime use",
                }
            )
        elif parsed_variables is not None and not isinstance(parsed_variables, list):
            issues.append(
                {
                    "code": "variables_not_list",
                    "severity": "blocking",
                    "message": "variables must be a list[str]",
                }
            )
        elif isinstance(parsed_variables, list) and not all(
            isinstance(item, str) and item.strip() for item in parsed_variables
        ):
            issues.append(
                {
                    "code": "variables_non_string_item",
                    "severity": "blocking",
                    "message": "variables must contain only non-empty strings",
                }
            )

        if not str(getattr(db_template, "template", "") or "").strip():
            issues.append(
                {
                    "code": "empty_template",
                    "severity": "blocking",
                    "message": "template body is empty",
                }
            )
        return issues

    async def get_governance_status(self, *, limit: int = 1000) -> dict[str, Any]:
        """Return visible governance status for invalid historical prompt templates."""
        from common.db.models import PromptTemplate as PromptTemplateDB

        result = await self.db.execute(select(PromptTemplateDB).limit(limit))
        rows = result.scalars().all()
        invalid_rows: list[dict[str, Any]] = []
        flattened_issues: list[dict[str, Any]] = []
        for row in rows:
            issues = self._governance_issues_for_row(row)
            if not issues:
                continue
            snapshot = self._template_snapshot(row)
            invalid_row = {
                "id": snapshot["id"],
                "name": snapshot["name"],
                "prompt_type": snapshot["prompt_type"],
                "category": snapshot["category"],
                "variables": snapshot["variables"],
                "is_active": snapshot["is_active"],
                "is_default": snapshot["is_default"],
                "updated_at": snapshot["updated_at"],
                "issues": issues,
                "runtime_status": "disabled_required" if snapshot["is_active"] else "inactive_invalid",
                "remediation": "disable_and_clear_default",
            }
            invalid_rows.append(invalid_row)
            flattened_issues.append(
                {
                    "template_id": snapshot["id"],
                    "name": snapshot["name"],
                    "issue_codes": [issue["code"] for issue in issues],
                    "messages": [issue["message"] for issue in issues],
                    "recommended_action": "disable_and_clear_default",
                }
            )

        active_invalid_count = sum(1 for item in invalid_rows if item["is_active"] or item["is_default"])
        policy = {
            "variables_schema": "list[str]",
            "invalid_history_runtime_behavior": "visible_in_governance_and_disabled_before_runtime_lookup",
            "rollback": "restore prior is_active/is_default from prompt_template.governance.remediate_invalid SystemLog details",
            "audit_action": "prompt_template.governance.remediate_invalid",
        }
        return {
            "allowed_prompt_types": [item.value for item in PromptType],
            "policy": policy,
            "invalid_count": len(invalid_rows),
            "invalid_templates": invalid_rows,
            "limit": limit,
            "checked_count": len(rows),
            "active_invalid_count": active_invalid_count,
            "invalid_active_count": active_invalid_count,
            "issues": flattened_issues,
            "rollback_policy": policy["rollback"],
            "audit_log_action": policy["audit_action"],
        }

    async def remediate_invalid_templates(
        self,
        *,
        actor_id: str | None,
        reason: str,
        limit: int = 1000,
    ) -> dict[str, Any]:
        from common.db.models import PromptTemplate as PromptTemplateDB
        from common.db.models import SystemLog

        result = await self.db.execute(select(PromptTemplateDB).limit(limit))
        rows = result.scalars().all()
        remediated: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        trace_id = get_trace_id()
        normalized_reason = reason.strip() or "prompt governance remediation"

        for row in rows:
            issues = self._governance_issues_for_row(row)
            if not issues:
                continue
            before = self._template_snapshot(row)
            if bool(getattr(row, "is_active", False)) or bool(getattr(row, "is_default", False)):
                row.is_active = False
                row.is_default = False
                row.updated_at = now
            after = self._template_snapshot(row)
            remediated.append({"before": before, "after": after, "issues": issues})

        if remediated:
            self.db.add(
                SystemLog(
                    user_id=actor_id,
                    user_identifier=actor_id or "system",
                    action="prompt_template.governance.remediate_invalid",
                    status="success",
                    details=json.dumps(
                        {
                            "reason": normalized_reason,
                            "trace_id": trace_id,
                            "count": len(remediated),
                            "items": remediated,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                )
            )
        await self.db.commit()
        await self.loader.invalidate_cache()
        return {
            "remediated_count": len(remediated),
            "items": remediated,
            "audit": {
                "action": "prompt_template.governance.remediate_invalid",
                "actor_id": actor_id,
                "reason": normalized_reason,
                "trace_id": trace_id,
            },
        }

    async def create_template(
        self,
        data: PromptTemplateCreate,
        *,
        actor: Any | None = None,
        reason: str = "create_prompt_template",
    ) -> PromptTemplate:
        """Create a new prompt template.

        Args:
            data: Template creation data

        Returns:
            Created PromptTemplate
        """
        from common.db.models import PromptTemplate as PromptTemplateDB

        template_id = str(uuid4())
        now = datetime.now(UTC)

        db_template = PromptTemplateDB(
            id=template_id,
            name=data.name,
            prompt_type=data.prompt_type.value,
            category=data.category,
            template=data.template,
            variables=data.variables,
            is_active=data.is_active,
            is_default=data.is_default,
            is_system=False,
            created_at=now,
            updated_at=now,
        )

        self.db.add(db_template)
        self._queue_audit_log(
            action=f"{PROMPT_GOVERNANCE_AUDIT_ACTION}.create",
            actor=actor,
            before=None,
            after=self._template_snapshot(db_template),
            reason=reason,
        )
        await self.db.commit()
        await self.db.refresh(db_template)

        # Convert to Pydantic model
        normalized = self._safe_model_validate(db_template)
        if normalized is None:
            raise ValueError("invalid prompt template data")
        return normalized

    async def get_template(self, template_id: UUID) -> PromptTemplate | None:
        """Get a template by ID.

        Args:
            template_id: Template UUID

        Returns:
            PromptTemplate or None if not found
        """
        # Try cache first
        cached = await self.loader.get_template(template_id, self.db)
        if cached:
            return cached

        # Load from database
        from common.db.models import PromptTemplate as PromptTemplateDB

        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == str(template_id))
        )
        db_template = result.scalar_one_or_none()

        if db_template:
            normalized = self._safe_model_validate(db_template)
            if normalized is None:
                raise ValueError("invalid prompt template data")
            return normalized
        return None

    async def update_template(
        self,
        template_id: UUID,
        data: PromptTemplateUpdate,
        *,
        actor: Any | None = None,
        reason: str = "update_prompt_template",
    ) -> PromptTemplate | None:
        """Update an existing template.

        Args:
            template_id: Template UUID
            data: Update data

        Returns:
            Updated PromptTemplate or None if not found
        """
        from common.db.models import PromptTemplate as PromptTemplateDB

        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == str(template_id))
        )
        db_template = result.scalar_one_or_none()

        if not db_template:
            return None

        before = self._template_snapshot(db_template)
        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "prompt_type" and value:
                value = value.value if hasattr(value, "value") else value
            setattr(db_template, field, value)

        db_template.updated_at = datetime.now(UTC)
        self._queue_audit_log(
            action=f"{PROMPT_GOVERNANCE_AUDIT_ACTION}.update",
            actor=actor,
            before=before,
            after=self._template_snapshot(db_template),
            reason=reason,
        )

        await self.db.commit()
        await self.db.refresh(db_template)

        # Invalidate cache
        await self.loader.invalidate_cache(template_id)

        normalized = self._safe_model_validate(db_template)
        if normalized is None:
            raise ValueError("invalid prompt template data")
        return normalized

    async def delete_template(
        self,
        template_id: UUID,
        *,
        actor: Any | None = None,
        reason: str = "disable_prompt_template",
    ) -> bool:
        """Delete a template (soft delete by deactivating).

        Args:
            template_id: Template UUID

        Returns:
            True if deleted, False if not found
        """
        from common.db.models import PromptTemplate as PromptTemplateDB

        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == str(template_id))
        )
        db_template = result.scalar_one_or_none()

        if not db_template:
            return False

        before = self._template_snapshot(db_template)
        # Soft delete - just deactivate
        db_template.is_active = False
        db_template.updated_at = datetime.now(UTC)
        self._queue_audit_log(
            action=f"{PROMPT_GOVERNANCE_AUDIT_ACTION}.disable",
            actor=actor,
            before=before,
            after=self._template_snapshot(db_template),
            reason=reason,
        )

        await self.db.commit()

        # Invalidate cache
        await self.loader.invalidate_cache(template_id)

        return True

    async def list_templates(
        self,
        prompt_type: PromptType | None = None,
        category: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PromptTemplate]:
        """List templates with optional filtering.

        Args:
            prompt_type: Filter by type
            category: Filter by category
            is_active: Filter by active status
            skip: Number to skip (pagination)
            limit: Max to return (pagination)

        Returns:
            List of PromptTemplate
        """
        from common.db.models import PromptTemplate as PromptTemplateDB

        query = select(PromptTemplateDB)

        if prompt_type:
            query = query.where(PromptTemplateDB.prompt_type == prompt_type.value)
        if category:
            query = query.where(PromptTemplateDB.category == category)
        if is_active is not None:
            query = query.where(PromptTemplateDB.is_active == is_active)

        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        db_templates = result.scalars().all()

        normalized: list[PromptTemplate] = []
        for item in db_templates:
            converted = self._safe_model_validate(item)
            if converted is not None:
                normalized.append(converted)
        return normalized

    async def get_template_for_scenario(
        self,
        prompt_type: str,
        scenario_type: str | None = None,
        scenario_id: str | None = None,
    ) -> PromptTemplate | None:
        """Get the best matching template for a scenario.

        Resolution order:
        1. Scenario-specific assignment (scenario_type + scenario_id)
        2. Scenario-type default (scenario_type only)
        3. Global default for prompt_type

        Args:
            prompt_type: Type of prompt needed
            scenario_type: Optional scenario category
            scenario_id: Optional specific scenario ID

        Returns:
            Best matching PromptTemplate or None
        """
        self._assert_scenario_prompt_scope(
            prompt_type=prompt_type,
            scenario_type=scenario_type,
            operation="resolve",
        )
        from common.db.models import (
            PromptTemplate as PromptTemplateDB,
        )
        from common.db.models import (
            ScenarioPrompt as ScenarioPromptDB,
        )

        # Try scenario-specific first
        if scenario_type and scenario_id:
            result = await self.db.execute(
                select(PromptTemplateDB)
                .join(ScenarioPromptDB)
                .where(
                    and_(
                        ScenarioPromptDB.scenario_type == scenario_type,
                        ScenarioPromptDB.scenario_id == scenario_id,
                        ScenarioPromptDB.prompt_type == prompt_type,
                        ScenarioPromptDB.is_active.is_(True),
                        PromptTemplateDB.is_active.is_(True),
                    )
                )
            )
            template = result.scalar_one_or_none()
            if template:
                normalized = self._safe_model_validate(template)
                if normalized is None:
                    raise ValueError("invalid prompt template data")
                return normalized

        # Try scenario-type only
        if scenario_type:
            result = await self.db.execute(
                select(PromptTemplateDB)
                .join(ScenarioPromptDB)
                .where(
                    and_(
                        ScenarioPromptDB.scenario_type == scenario_type,
                        ScenarioPromptDB.scenario_id.is_(None),
                        ScenarioPromptDB.prompt_type == prompt_type,
                        ScenarioPromptDB.is_active.is_(True),
                        PromptTemplateDB.is_active.is_(True),
                    )
                )
            )
            template = result.scalar_one_or_none()
            if template:
                normalized = self._safe_model_validate(template)
                if normalized is None:
                    raise ValueError("invalid prompt template data")
                return normalized

        # Fall back to global default
        result = await self.db.execute(
            select(PromptTemplateDB).where(
                and_(
                    PromptTemplateDB.prompt_type == prompt_type,
                    PromptTemplateDB.is_default.is_(True),
                    PromptTemplateDB.is_active.is_(True),
                )
            )
        )
        template = result.scalar_one_or_none()
        if template:
            normalized = self._safe_model_validate(template)
            if normalized is None:
                raise ValueError("invalid prompt template data")
            return normalized

        return None

    async def render_prompt(
        self,
        request: PromptRenderRequest,
    ) -> PromptRenderResponse:
        """Render a prompt template with variables.

        Args:
            request: Render request with template_id and variables

        Returns:
            PromptRenderResponse with rendered text
        """
        template = await self.get_template(request.template_id)

        if not template:
            return PromptRenderResponse(
                template_id=request.template_id,
                rendered="",
                missing_variables=[],
                extra_variables=[],
            )

        result = render_template(template.template, request.variables)

        return PromptRenderResponse(
            template_id=request.template_id,
            rendered=result.rendered,
            missing_variables=result.missing_variables,
            extra_variables=result.extra_variables,
        )

    def compile_runtime_prompt_contract(
        self,
        *,
        template: PromptTemplate,
        variables: dict[str, Any],
        runtime_consumer: str,
        system_message: str,
        model_config: dict[str, Any] | None = None,
    ) -> Result[CompiledPromptContract]:
        """Compile a runtime prompt contract from a resolved template.

        This is the control-plane handoff point where PromptTemplateService stops being a
        governance-only lookup helper and starts producing the exact prompt artifact that the
        runtime LLM consumer will execute.
        """
        render_result = render_template(template.template, variables, strict=True)
        if not render_result.success:
            if render_result.missing_variables:
                missing = ",".join(render_result.missing_variables)
                logger.warning(
                    "Prompt contract compilation failed due to missing template variables",
                    template_id=str(template.id),
                    runtime_consumer=runtime_consumer,
                    prompt_type=(
                        template.prompt_type.value
                        if hasattr(template.prompt_type, "value")
                        else str(template.prompt_type)
                    ),
                    missing_variables=render_result.missing_variables,
                )
                return Result.fail(
                    f"[PROMPT_CONTRACT_MISSING_VARIABLES:{missing}]"
                )
            logger.warning(
                "Prompt contract compilation failed due to render error",
                template_id=str(template.id),
                runtime_consumer=runtime_consumer,
                error_message=render_result.error_message,
            )
            return Result.fail("[PROMPT_CONTRACT_RENDER_ERROR]")

        rendered_prompt = render_result.rendered.strip()
        if not rendered_prompt:
            logger.warning(
                "Prompt contract compilation produced empty rendered prompt",
                template_id=str(template.id),
                runtime_consumer=runtime_consumer,
            )
            return Result.fail("[PROMPT_CONTRACT_EMPTY_RENDERED_PROMPT]")

        config_manager = get_config_manager()
        effective_config = model_config or config_manager.get_effective_config(ModelType.LLM)
        runtime_policy = config_manager.describe_runtime_policy(
            ModelType.LLM,
            effective_config,
        )
        base_url_status = str(runtime_policy.get("base_url_status") or "unknown")
        base_url_required = bool(runtime_policy.get("base_url_required", False))
        base_url_policy = (
            f"required_{base_url_status}"
            if base_url_required
            else f"not_required_{base_url_status}"
        )
        if base_url_required and base_url_status != "configured":
            logger.error(
                "Prompt contract blocked by LLM base_url policy",
                template_id=str(template.id),
                runtime_consumer=runtime_consumer,
                provider=str(runtime_policy.get("provider") or ""),
                model_name=str(runtime_policy.get("model_name") or ""),
                base_url_policy=base_url_policy,
            )
            return Result.fail("[PROMPT_CONTRACT_BASE_URL_REQUIRED]")

        diagnostics: list[PromptContractDiagnostic] = [
            PromptContractDiagnostic(
                code="PROMPT_TEMPLATE_RENDERED",
                severity="info",
                detail=(
                    f"template_id={template.id} prompt_type="
                    f"{template.prompt_type.value if hasattr(template.prompt_type, 'value') else template.prompt_type}"
                ),
            ),
            PromptContractDiagnostic(
                code="LLM_BASE_URL_POLICY",
                severity="info",
                detail=(
                    f"provider={runtime_policy.get('provider') or ''} "
                    f"model={runtime_policy.get('model_name') or ''} "
                    f"policy={base_url_policy}"
                ),
            ),
        ]
        if render_result.extra_variables:
            diagnostics.append(
                PromptContractDiagnostic(
                    code="PROMPT_TEMPLATE_EXTRA_VARIABLES",
                    severity="warning",
                    detail=",".join(render_result.extra_variables),
                )
            )

        contract_hash = build_prompt_contract_hash(
            PROMPT_CONTRACT_VERSION,
            template.id,
            runtime_consumer,
            system_message,
            rendered_prompt,
        )
        prompt_type = (
            template.prompt_type.value
            if hasattr(template.prompt_type, "value")
            else str(template.prompt_type)
        )
        logger.info(
            "Compiled runtime prompt contract",
            template_id=str(template.id),
            runtime_consumer=runtime_consumer,
            contract_hash=contract_hash,
            prompt_type=prompt_type,
            base_url_policy=base_url_policy,
        )
        return Result.ok(
            CompiledPromptContract(
                contract_version=PROMPT_CONTRACT_VERSION,
                prompt_source="prompt_template_service",
                template_id=str(template.id),
                template_name=template.name,
                prompt_type=prompt_type,
                rendered_prompt=rendered_prompt,
                system_message=system_message,
                runtime_consumer=runtime_consumer,
                contract_hash=contract_hash,
                model_provider=str(runtime_policy.get("provider") or ""),
                model_name=str(runtime_policy.get("model_name") or ""),
                base_url_policy=base_url_policy,
                missing_variables=tuple(render_result.missing_variables),
                extra_variables=tuple(render_result.extra_variables),
                diagnostics=tuple(diagnostics),
            )
        )

    async def quarantine_invalid_templates(
        self,
        *,
        actor: Any | None = None,
        reason: str,
    ) -> PromptTemplateQuarantineResult:
        """Compatibility wrapper that disables invalid historical templates."""
        status_before = await self.get_governance_status()
        actor_id, _ = self._audit_identifier(actor)
        result = await self.remediate_invalid_templates(actor_id=actor_id, reason=reason)
        issues = [
            issue
            for item in result.get("items", [])
            for issue in item.get("issues", [])
            if isinstance(issue, dict)
        ]
        return PromptTemplateQuarantineResult(
            checked_count=int(status_before.get("checked_count", 0)),
            quarantined_count=int(result.get("remediated_count", 0)),
            issues=issues,
            audit_log_action=str(result.get("audit", {}).get("action", "prompt_template.governance.remediate_invalid")),
        )

    async def migrate_invalid_templates(
        self,
        *,
        actor: Any | None = None,
        reason: str = "PromptTemplate governance scan",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Scan historical PromptTemplate rows and migrate/disable invalid records.

        Variables stored as objects are migrated to a string list. Unknown prompt
        types cannot be safely executed, so those rows are disabled until an admin
        explicitly rewrites the type. Each mutation is queued in SystemLog so it can
        be audited and rolled back from the captured before snapshot.
        """
        from common.db.models import PromptTemplate as PromptTemplateDB

        result = await self.db.execute(select(PromptTemplateDB))
        rows = list(result.scalars().all())
        remediations: list[dict[str, Any]] = []

        for row in rows:
            issues = self._governance_issues_for_row(row)
            if not issues:
                continue
            issue_codes = [str(issue.get("code", "")) for issue in issues]

            before = self._snapshot_db_template(row)
            after = dict(before)
            actions: list[str] = []

            if any(issue.startswith("variables_") for issue in issue_codes):
                after["variables"] = self._normalize_legacy_variables(getattr(row, "variables", None))
                actions.append("migrate_variables_to_list")

            if "invalid_prompt_type" in issue_codes:
                after["is_active"] = False
                after["is_default"] = False
                actions.append("disable_unknown_prompt_type")

            remediation = {
                "template_id": str(getattr(row, "id", "")),
                "name": getattr(row, "name", None),
                "issues": issues,
                "actions": actions,
                "before": before,
                "after": after,
            }
            remediations.append(remediation)

            if dry_run:
                continue

            row.variables = after["variables"]
            row.is_active = after["is_active"]
            row.is_default = after["is_default"]
            row.updated_at = datetime.now(UTC)
            await self._queue_prompt_governance_audit(
                action="prompt_template.governance_migrate",
                actor=actor,
                template_id=str(getattr(row, "id", "")),
                reason=reason,
                before=before,
                after=after,
                issues=issues,
                status="warning" if "invalid_prompt_type" in issue_codes else "success",
            )

        if not dry_run and remediations:
            await self.db.commit()
            await self.loader.invalidate_cache()

        return {
            "dry_run": dry_run,
            "checked": len(rows),
            "remediated": len(remediations),
            "items": remediations,
            "audit_action": None if dry_run else "prompt_template.governance_migrate",
        }

    async def rollback_last_governance_migration(
        self,
        *,
        template_id: UUID,
        actor: Any | None = None,
        reason: str = "PromptTemplate governance rollback",
    ) -> PromptTemplate | None:
        from common.db.models import PromptTemplate as PromptTemplateDB
        from common.db.models import SystemLog

        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == str(template_id))
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        audit_result = await self.db.execute(
            select(SystemLog)
            .where(SystemLog.action == "prompt_template.governance_migrate")
            .order_by(SystemLog.created_at.desc())
        )
        before: dict[str, Any] | None = None
        issues: list[str] = []
        for audit in audit_result.scalars().all():
            try:
                details = json.loads(audit.details or "{}")
            except json.JSONDecodeError:
                continue
            if str(details.get("template_id")) == str(template_id) and isinstance(details.get("before"), dict):
                before = details["before"]
                issues = [
                    str(issue.get("code", ""))
                    if isinstance(issue, dict)
                    else str(issue)
                    for issue in details.get("issues", [])
                ]
                break

        if before is None:
            raise ValueError("[PROMPT_GOVERNANCE_ROLLBACK_NOT_AVAILABLE]")

        current = self._snapshot_db_template(row)
        row.variables = before.get("variables")
        row.is_active = bool(before.get("is_active"))
        row.is_default = bool(before.get("is_default"))
        row.prompt_type = str(before.get("prompt_type") or row.prompt_type)
        row.updated_at = datetime.now(UTC)

        await self._queue_prompt_governance_audit(
            action="prompt_template.governance_rollback",
            actor=actor,
            template_id=str(template_id),
            reason=reason,
            before=current,
            after=self._snapshot_db_template(row),
            issues=issues,
        )
        await self.db.commit()
        await self.db.refresh(row)
        await self.loader.invalidate_cache(template_id)
        return self._safe_model_validate(row)

    async def assign_template_to_scenario(
        self,
        data: ScenarioPromptCreate,
        *,
        actor: Any | None = None,
        reason: str = "assign_scenario_prompt",
    ) -> ScenarioPrompt:
        """Assign a template to a scenario.

        Args:
            data: Scenario prompt assignment data

        Returns:
            Created ScenarioPrompt
        """
        self._assert_scenario_prompt_scope(
            prompt_type=data.prompt_type,
            scenario_type=data.scenario_type,
            operation="assign",
        )
        from common.db.models import ScenarioPrompt as ScenarioPromptDB

        assignment_id = str(uuid4())

        db_assignment = ScenarioPromptDB(
            id=assignment_id,
            scenario_type=data.scenario_type,
            scenario_id=data.scenario_id,
            prompt_type=data.prompt_type,
            template_id=str(data.template_id),
            is_active=data.is_active,
            created_at=datetime.now(UTC),
        )

        self.db.add(db_assignment)
        self._queue_audit_log(
            action=f"{PROMPT_GOVERNANCE_AUDIT_ACTION}.assign_scenario",
            actor=actor,
            before=None,
            after={
                "id": assignment_id,
                "scenario_type": data.scenario_type,
                "scenario_id": data.scenario_id,
                "prompt_type": data.prompt_type,
                "template_id": str(data.template_id),
                "is_active": data.is_active,
            },
            reason=reason,
        )
        await self.db.commit()
        await self.db.refresh(db_assignment)

        return ScenarioPrompt.model_validate(db_assignment)

    async def set_default_template(
        self,
        template_id: UUID,
        prompt_type: PromptType,
        *,
        actor: Any | None = None,
        reason: str = "set_default_prompt_template",
    ) -> bool:
        """Set a template as the default for its type.

        Args:
            template_id: Template to make default
            prompt_type: Type of prompt

        Returns:
            True if successful, False if template not found
        """
        from common.db.models import PromptTemplate as PromptTemplateDB

        now = datetime.now(UTC)

        # First, unset existing defaults for this prompt type.
        before_result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.prompt_type == prompt_type.value)
        )
        before_defaults = [
            self._template_snapshot(item)
            for item in before_result.scalars().all()
            if bool(getattr(item, "is_default", False))
        ]
        await self.db.execute(
            update(PromptTemplateDB)
            .where(
                PromptTemplateDB.prompt_type == prompt_type.value,
                PromptTemplateDB.is_default.is_(True),
            )
            .values(is_default=False, updated_at=now)
        )

        # Set new default
        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == str(template_id))
        )
        template = result.scalar_one_or_none()

        if not template:
            return False

        template.is_default = True
        template.updated_at = now
        self._queue_audit_log(
            action=f"{PROMPT_GOVERNANCE_AUDIT_ACTION}.set_default",
            actor=actor,
            before={"defaults": before_defaults},
            after=self._template_snapshot(template),
            reason=reason,
        )

        await self.db.commit()

        # Invalidate cache
        await self.loader.invalidate_cache()

        return True

    async def list_scenario_prompts(
        self,
        scenario_type: str | None = None,
        prompt_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[ScenarioPrompt]:
        """List scenario prompt assignments with optional filtering.

        Args:
            scenario_type: Filter by scenario type (e.g., 'sales', 'presentation')
            prompt_type: Filter by prompt type
            is_active: Filter by active status

        Returns:
            List of ScenarioPrompt assignments
        """
        from common.db.models import (
            PromptTemplate as PromptTemplateDB,
        )
        from common.db.models import (
            ScenarioPrompt as ScenarioPromptDB,
        )

        query = select(ScenarioPromptDB).join(
            PromptTemplateDB,
            ScenarioPromptDB.template_id == PromptTemplateDB.id,
            isouter=True
        )

        if scenario_type:
            query = query.where(ScenarioPromptDB.scenario_type == scenario_type)
        if prompt_type:
            query = query.where(ScenarioPromptDB.prompt_type == prompt_type)
        if is_active is not None:
            query = query.where(ScenarioPromptDB.is_active == is_active)

        query = query.order_by(ScenarioPromptDB.created_at.desc())

        result = await self.db.execute(query)
        assignments = result.scalars().all()

        return [ScenarioPrompt.model_validate(a) for a in assignments]

    async def get_scenario_prompt(
        self,
        assignment_id: UUID,
    ) -> ScenarioPrompt | None:
        """Get a scenario prompt assignment by ID.

        Args:
            assignment_id: Assignment UUID

        Returns:
            ScenarioPrompt or None if not found
        """
        from common.db.models import ScenarioPrompt as ScenarioPromptDB

        result = await self.db.execute(
            select(ScenarioPromptDB).where(ScenarioPromptDB.id == str(assignment_id))
        )
        assignment = result.scalar_one_or_none()

        if assignment:
            return ScenarioPrompt.model_validate(assignment)
        return None

    async def delete_scenario_prompt(
        self,
        assignment_id: UUID,
        *,
        actor: Any | None = None,
        reason: str = "delete_scenario_prompt",
    ) -> bool:
        """Delete a scenario prompt assignment.

        Args:
            assignment_id: Assignment UUID

        Returns:
            True if deleted, False if not found
        """
        from common.db.models import ScenarioPrompt as ScenarioPromptDB

        result = await self.db.execute(
            select(ScenarioPromptDB).where(ScenarioPromptDB.id == str(assignment_id))
        )
        assignment = result.scalar_one_or_none()

        if not assignment:
            return False

        before = {
            "id": str(assignment.id),
            "scenario_type": assignment.scenario_type,
            "scenario_id": assignment.scenario_id,
            "prompt_type": assignment.prompt_type,
            "template_id": str(assignment.template_id),
            "is_active": bool(assignment.is_active),
        }
        await self.db.delete(assignment)
        self._queue_audit_log(
            action=f"{PROMPT_GOVERNANCE_AUDIT_ACTION}.delete_scenario",
            actor=actor,
            before=before,
            after=None,
            reason=reason,
        )
        await self.db.commit()

        return True

    async def update_scenario_prompt(
        self,
        assignment_id: UUID,
        is_active: bool | None = None,
        template_id: UUID | None = None,
        *,
        actor: Any | None = None,
        reason: str = "update_scenario_prompt",
    ) -> ScenarioPrompt | None:
        """Update a scenario prompt assignment.

        Args:
            assignment_id: Assignment UUID
            is_active: New active status
            template_id: New template ID

        Returns:
            Updated ScenarioPrompt or None if not found
        """
        from common.db.models import ScenarioPrompt as ScenarioPromptDB

        result = await self.db.execute(
            select(ScenarioPromptDB).where(ScenarioPromptDB.id == str(assignment_id))
        )
        assignment = result.scalar_one_or_none()

        if not assignment:
            return None

        before = {
            "id": str(assignment.id),
            "scenario_type": assignment.scenario_type,
            "scenario_id": assignment.scenario_id,
            "prompt_type": assignment.prompt_type,
            "template_id": str(assignment.template_id),
            "is_active": bool(assignment.is_active),
        }
        if is_active is not None:
            assignment.is_active = is_active
        if template_id is not None:
            assignment.template_id = str(template_id)
        self._queue_audit_log(
            action=f"{PROMPT_GOVERNANCE_AUDIT_ACTION}.update_scenario",
            actor=actor,
            before=before,
            after={
                "id": str(assignment.id),
                "scenario_type": assignment.scenario_type,
                "scenario_id": assignment.scenario_id,
                "prompt_type": assignment.prompt_type,
                "template_id": str(assignment.template_id),
                "is_active": bool(assignment.is_active),
            },
            reason=reason,
        )

        await self.db.commit()
        await self.db.refresh(assignment)

        return ScenarioPrompt.model_validate(assignment)

    def _assert_scenario_prompt_scope(
        self,
        *,
        prompt_type: str,
        scenario_type: str | None,
        operation: str,
    ) -> None:
        normalized_scenario_type = str(scenario_type or "").strip().lower()
        if normalized_scenario_type != "sales":
            return

        normalized_prompt_type = str(prompt_type or "").strip().lower()
        if normalized_prompt_type in SALES_PROMPT_SCOPE_ALLOWED_TYPES:
            return

        raise ValueError(
            "[PROMPT_SCOPE_VIOLATION] "
            f"sales.{operation}.{normalized_prompt_type} "
            "only_evaluation_report_templates_allowed"
        )
