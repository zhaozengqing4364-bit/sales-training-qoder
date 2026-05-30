"""Compiled prompt contracts for runtime LLM consumers.

This module gives PromptTemplateService and runtime callers one concrete compiled artifact
that can be hashed, audited, and passed into the model layer without rebuilding prompts
from ad-hoc dicts at the last moment.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from json import dumps
from typing import Any

PROMPT_CONTRACT_VERSION = "m021_s02_t02"

_ROLEPLAY_CONTRACT_VOLATILE_FIELDS = frozenset(
    {
        "audit",
        "contract_id",
        "compiled_at",
        "compiled_by",
        "compiler_version",
        "contract_hash",
    }
)


def build_prompt_contract_hash(*parts: object) -> str:
    """Build a short stable hash for compiled prompt contracts."""
    normalized = "\n::\n".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def build_roleplay_contract_hash(contract: dict[str, Any] | None) -> str | None:
    """Hash structured Roleplay Contract domain fields for audit/version compare.

    Covers situation, relationship, visible scope, forbidden patterns, and disclosure
    policy. Excludes volatile audit metadata (compiled_at, contract_id, etc.).
    """
    if not isinstance(contract, dict) or not contract:
        return None
    if contract.get("legacy_status"):
        return None

    payload = _without_volatile_contract_fields(contract)
    if not payload:
        return None

    digest = hashlib.sha256(
        dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def build_base_instruction_hash(base_instructions: str) -> str:
    """Hash session-level base instructions without per-turn role_anchor."""
    normalized = str(base_instructions or "").strip()
    return build_prompt_contract_hash("base_instruction", normalized)


def build_turn_instruction_hash(turn_instructions: str) -> str:
    """Hash per-turn full instructions including grounding and role_anchor."""
    normalized = str(turn_instructions or "").strip()
    return build_prompt_contract_hash("turn_instruction", normalized)


def compose_turn_instruction_text(
    *,
    base_instructions: str,
    grounding_context: str = "",
    roleplay_turn_instruction: str = "",
    role_anchor_text: str = "",
) -> str:
    """Compose one turn instruction payload for turn_instruction_hash auditing."""
    sections: list[str] = []
    base = str(base_instructions or "").strip()
    grounding = str(grounding_context or "").strip()
    if base and grounding:
        sections.append(f"{base}\n\n【当前轮内部知识依据】\n{grounding}")
    elif base:
        sections.append(base)
    elif grounding:
        sections.append(f"【当前轮内部知识依据】\n{grounding}")

    roleplay_turn = str(roleplay_turn_instruction or "").strip()
    if roleplay_turn:
        sections.append(roleplay_turn)

    role_anchor = str(role_anchor_text or "").strip()
    if role_anchor:
        sections.append(role_anchor)

    return "\n\n".join(section for section in sections if section).strip()


def _without_volatile_contract_fields(payload: object) -> object:
    if isinstance(payload, dict):
        return {
            key: _without_volatile_contract_fields(value)
            for key, value in payload.items()
            if key not in _ROLEPLAY_CONTRACT_VOLATILE_FIELDS
        }
    if isinstance(payload, list):
        return [_without_volatile_contract_fields(item) for item in payload]
    return payload


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
