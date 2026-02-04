"""
Prompt Templates Module

Provides configurable prompt management for AI evaluation system.
"""

# Import models first (no dependencies)
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

# Import renderer (only depends on models)
from src.prompt_templates.renderer import (
    PromptRenderer,
    RenderResult,
    render_template,
)

# Import loader (only depends on models)
from src.prompt_templates.loader import (
    PromptTemplateLoader,
    CachedTemplate,
    get_loader,
)

# Import service (depends on renderer, loader, models)
from src.prompt_templates.service import PromptTemplateService

__all__ = [
    # Models
    "PromptTemplate",
    "PromptTemplateCreate",
    "PromptTemplateUpdate",
    "ScenarioPrompt",
    "ScenarioPromptCreate",
    "PromptType",
    "PromptRenderRequest",
    "PromptRenderResponse",
    # Renderer
    "PromptRenderer",
    "RenderResult",
    "render_template",
    # Loader
    "PromptTemplateLoader",
    "CachedTemplate",
    "get_loader",
    # Service
    "PromptTemplateService",
]
