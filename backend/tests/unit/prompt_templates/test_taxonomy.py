"""Prompt source taxonomy proofs for M021/S02/T01.

These tests lock the current prompt control-plane reality so downstream runtime work can
promote one compiled contract without rediscovering which surfaces are live, compat, or
only governance-time helpers.
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

    assert entries["prompt_template_service"].authority_level == "compat_governance"
    assert entries["presentation_prompt_resolver"].integration_status == "runtime_helper"
    assert entries["legacy_llm_hardcoded_prompts"].authority_level == "compat_backend_adapter"


def test_prompt_source_taxonomy_flags_template_bypass_entrypoints() -> None:
    taxonomy = build_prompt_source_taxonomy()
    bypass_map = {entry.consumer: entry for entry in taxonomy.template_bypass_entrypoints}

    staged_eval = bypass_map["evaluation.services.staged_evaluation.StagedEvaluationService.evaluate_stage"]
    assert staged_eval.template_lookup == "prompt_service.get_template_for_scenario"
    assert staged_eval.runtime_call == "LLMService.evaluate"
    assert staged_eval.consumes_template_text is False
    assert "hardcoded" in staged_eval.bypass_reason

    report_feedback = bypass_map[
        "evaluation.services.comprehensive_report.ComprehensiveReportService._generate_detailed_feedback"
    ]
    assert report_feedback.runtime_call == "LLMService.generate_report"
    assert report_feedback.consumes_template_text is False
    assert "template lookup" in report_feedback.bypass_reason


def test_legacy_llm_entrypoints_are_marked_as_non_template_consumers() -> None:
    assert LEGACY_PROMPT_ENTRYPOINTS["evaluate"]["consumes_template_text"] is False
    assert LEGACY_PROMPT_ENTRYPOINTS["generate_report"]["consumes_template_text"] is False
    assert LEGACY_PROMPT_ENTRYPOINTS["evaluate"]["prompt_contract_mode"] == "hardcoded_builtin_prompt"
    assert LEGACY_PROMPT_ENTRYPOINTS["generate_report"]["prompt_contract_mode"] == "hardcoded_builtin_prompt"
