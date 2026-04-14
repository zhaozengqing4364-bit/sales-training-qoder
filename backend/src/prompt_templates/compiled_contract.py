"""Compiled prompt contracts for runtime LLM consumers.

This module gives PromptTemplateService and runtime callers one concrete compiled artifact
that can be hashed, audited, and passed into the model layer without rebuilding prompts
from ad-hoc dicts at the last moment.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


PROMPT_CONTRACT_VERSION = "m021_s02_t02"


def build_prompt_contract_hash(*parts: object) -> str:
    """Build a short stable hash for compiled prompt contracts."""
    normalized = "\n::\n".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class PromptContractDiagnostic:
    """One compile-time/runtime policy diagnostic attached to a prompt contract."""

    code: str
    severity: str
    detail: str


@dataclass(frozen=True)
class CompiledPromptContract:
    """Compiled prompt artifact that can be consumed directly by runtime LLM callers."""

    contract_version: str
    prompt_source: str
    template_id: str
    template_name: str
    prompt_type: str
    rendered_prompt: str
    system_message: str
    runtime_consumer: str
    contract_hash: str
    model_provider: str = ""
    model_name: str = ""
    base_url_policy: str = "unknown"
    missing_variables: tuple[str, ...] = field(default_factory=tuple)
    extra_variables: tuple[str, ...] = field(default_factory=tuple)
    diagnostics: tuple[PromptContractDiagnostic, ...] = field(default_factory=tuple)
