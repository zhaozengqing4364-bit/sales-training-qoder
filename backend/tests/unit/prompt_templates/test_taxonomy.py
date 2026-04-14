"""Prompt source taxonomy proofs for M021/S02/T02.

These tests lock the current prompt control-plane reality so downstream runtime work can
reuse the compiled prompt contract without rediscovering which surfaces are live, compat,
or still kept only as compatibility fallbacks.
"""

from __future__ import annotations

from common.ai.llm_service import LEGACY_PROMPT_ENTRYPOINTS
from prompt_templates.taxonomy import build_prompt_source_taxonomy


def test_prompt_source_taxonomy_covers_live_and_compat_surfaces() -> None:
    taxonomy = build_prompt_source_taxonomy()
    entries = {entry.source_key: entry for entry in taxonomy.sources}

    assert set(entries) >= {
        "prompt_template_service",
        "voice_instruction_compiler",
        "persona_policy",
        "presentation_prompt_resolver",
        "runtime_guardrails",
        "legacy_llm_hardcoded_prompts",
    }

    assert entries["voice_instruction_compiler"].authority_level == "live"
    assert entries["voice_instruction_compiler"].integration_status == "drives_runtime"
    assert "instruction_contract_hash" in entries["voice_instruction_compiler"].compiled_artifact

    assert entries["prompt_template_service"].authority_level == "live_compiled_template"
    assert entries["prompt_template_service"].integration_status == "drives_runtime"
    assert "CompiledPromptContract" in entries["prompt_template_service"].compiled_artifact
    assert entries["presentation_prompt_resolver"].integration_status == "runtime_helper"
    assert entries["legacy_llm_hardcoded_prompts"].authority_level == "compat_backend_adapter"
    assert (
        entries["legacy_llm_hardcoded_prompts"].integration_status
        == "compiled_contract_consumer_with_compat_fallback"
    )


def test_prompt_source_taxonomy_clears_known_template_bypass_entrypoints() -> None:
    taxonomy = build_prompt_source_taxonomy()

    assert taxonomy.template_bypass_entrypoints == ()


def test_legacy_llm_entrypoints_are_marked_as_compiled_prompt_consumers() -> None:
    assert LEGACY_PROMPT_ENTRYPOINTS["evaluate"]["consumes_template_text"] is True
    assert LEGACY_PROMPT_ENTRYPOINTS["generate_report"]["consumes_template_text"] is True
    assert LEGACY_PROMPT_ENTRYPOINTS["evaluate"]["prompt_contract_mode"] == "compiled_prompt_contract"
    assert LEGACY_PROMPT_ENTRYPOINTS["generate_report"]["prompt_contract_mode"] == "compiled_prompt_contract"
