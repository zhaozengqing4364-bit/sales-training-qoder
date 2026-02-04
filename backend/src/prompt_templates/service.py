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

from typing import Any
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.prompt_templates.models import (
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    ScenarioPrompt,
    ScenarioPromptCreate,
    PromptType,
    PromptRenderRequest,
    PromptRenderResponse,
)
from src.prompt_templates.renderer import render_template
from src.prompt_templates.loader import get_loader


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

    async def create_template(
        self,
        data: PromptTemplateCreate,
    ) -> PromptTemplate:
        """Create a new prompt template.

        Args:
            data: Template creation data

        Returns:
            Created PromptTemplate
        """
        from src.common.db.models import PromptTemplate as PromptTemplateDB

        template_id = uuid4()
        now = datetime.utcnow()

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
        await self.db.commit()
        await self.db.refresh(db_template)

        # Convert to Pydantic model
        return PromptTemplate.model_validate(db_template)

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
        from src.common.db.models import PromptTemplate as PromptTemplateDB

        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == template_id)
        )
        db_template = result.scalar_one_or_none()

        if db_template:
            return PromptTemplate.model_validate(db_template)
        return None

    async def update_template(
        self,
        template_id: UUID,
        data: PromptTemplateUpdate,
    ) -> PromptTemplate | None:
        """Update an existing template.

        Args:
            template_id: Template UUID
            data: Update data

        Returns:
            Updated PromptTemplate or None if not found
        """
        from src.common.db.models import PromptTemplate as PromptTemplateDB

        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == template_id)
        )
        db_template = result.scalar_one_or_none()

        if not db_template:
            return None

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "prompt_type" and value:
                value = value.value if hasattr(value, "value") else value
            setattr(db_template, field, value)

        db_template.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(db_template)

        # Invalidate cache
        await self.loader.invalidate_cache(template_id)

        return PromptTemplate.model_validate(db_template)

    async def delete_template(self, template_id: UUID) -> bool:
        """Delete a template (soft delete by deactivating).

        Args:
            template_id: Template UUID

        Returns:
            True if deleted, False if not found
        """
        from src.common.db.models import PromptTemplate as PromptTemplateDB

        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == template_id)
        )
        db_template = result.scalar_one_or_none()

        if not db_template:
            return False

        # Soft delete - just deactivate
        db_template.is_active = False
        db_template.updated_at = datetime.utcnow()

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
        from src.common.db.models import PromptTemplate as PromptTemplateDB

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

        return [PromptTemplate.model_validate(t) for t in db_templates]

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
        from src.common.db.models import (
            PromptTemplate as PromptTemplateDB,
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
                        ScenarioPromptDB.is_active == True,
                        PromptTemplateDB.is_active == True,
                    )
                )
            )
            template = result.scalar_one_or_none()
            if template:
                return PromptTemplate.model_validate(template)

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
                        ScenarioPromptDB.is_active == True,
                        PromptTemplateDB.is_active == True,
                    )
                )
            )
            template = result.scalar_one_or_none()
            if template:
                return PromptTemplate.model_validate(template)

        # Fall back to global default
        result = await self.db.execute(
            select(PromptTemplateDB).where(
                and_(
                    PromptTemplateDB.prompt_type == prompt_type,
                    PromptTemplateDB.is_default == True,
                    PromptTemplateDB.is_active == True,
                )
            )
        )
        template = result.scalar_one_or_none()
        if template:
            return PromptTemplate.model_validate(template)

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

    async def assign_template_to_scenario(
        self,
        data: ScenarioPromptCreate,
    ) -> ScenarioPrompt:
        """Assign a template to a scenario.

        Args:
            data: Scenario prompt assignment data

        Returns:
            Created ScenarioPrompt
        """
        from src.common.db.models import ScenarioPrompt as ScenarioPromptDB

        assignment_id = uuid4()

        db_assignment = ScenarioPromptDB(
            id=assignment_id,
            scenario_type=data.scenario_type,
            scenario_id=data.scenario_id,
            prompt_type=data.prompt_type,
            template_id=data.template_id,
            is_active=data.is_active,
            created_at=datetime.utcnow(),
        )

        self.db.add(db_assignment)
        await self.db.commit()
        await self.db.refresh(db_assignment)

        return ScenarioPrompt.model_validate(db_assignment)

    async def set_default_template(
        self,
        template_id: UUID,
        prompt_type: PromptType,
    ) -> bool:
        """Set a template as the default for its type.

        Args:
            template_id: Template to make default
            prompt_type: Type of prompt

        Returns:
            True if successful, False if template not found
        """
        from src.common.db.models import PromptTemplate as PromptTemplateDB

        # First, unset any existing default for this type
        await self.db.execute(
            select(PromptTemplateDB)
            .where(
                and_(
                    PromptTemplateDB.prompt_type == prompt_type.value,
                    PromptTemplateDB.is_default == True,
                )
            )
        )

        # Set new default
        result = await self.db.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            return False

        template.is_default = True
        template.updated_at = datetime.utcnow()

        await self.db.commit()

        # Invalidate cache
        await self.loader.invalidate_cache()

        return True
