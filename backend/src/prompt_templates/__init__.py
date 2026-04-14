"""
Prompt Templates Module

Provides configurable prompt management for AI evaluation system.
"""

# Import models first (no dependencies)
from prompt_templates.models import (
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
from prompt_templates.renderer import (
    PromptRenderer,
    RenderResult,
    render_template,
)

# Import compiled contracts (runtime artifacts)
from prompt_templates.compiled_contract import (
    PROMPT_CONTRACT_VERSION,
    CompiledPromptContract,
    PromptContractDiagnostic,
    build_prompt_contract_hash,
)

# Import loader (only depends on models)
from prompt_templates.loader import (
    PromptTemplateLoader,
    CachedTemplate,
    get_loader,
)

# Import service (depends on renderer, loader, models)
from prompt_templates.service import PromptTemplateService

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
    # Compiled contracts
    "PROMPT_CONTRACT_VERSION",
    "CompiledPromptContract",
    "PromptContractDiagnostic",
    "build_prompt_contract_hash",
    # Loader
    "PromptTemplateLoader",
    "CachedTemplate",
    "get_loader",
    # Service
    "PromptTemplateService",
]
