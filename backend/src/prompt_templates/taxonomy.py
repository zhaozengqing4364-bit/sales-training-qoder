"""Prompt-source taxonomy for the current AI control plane.

This module turns the M021 prompt inventory into a code-owned artifact so follow-up slices
can reason about live runtime authority, compatibility helpers, and known fake integration
points without reopening a full repository scan.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.ai.llm_service import LEGACY_PROMPT_ENTRYPOINTS


PROMPT_SOURCE_TAXONOMY_VERSION = "m021_s02_t01"


@dataclass(frozen=True)
class PromptSourceTaxonomyEntry:
    """One prompt-related source surface in the repository."""

    source_key: str
    authority_level: str
    integration_status: str
    compiled_artifact: str
    primary_module: str
    runtime_consumers: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class TemplateBypassEntrypoint:
    """A code path that looks up a template but does not pass it into the model call."""

    consumer: str
    template_lookup: str
    runtime_call: str
    consumes_template_text: bool
    bypass_reason: str


@dataclass(frozen=True)
class PromptSourceTaxonomySnapshot:
    """Prompt taxonomy plus known template-bypass entrypoints."""

    version: str
    sources: tuple[PromptSourceTaxonomyEntry, ...]
    template_bypass_entrypoints: tuple[TemplateBypassEntrypoint, ...]


PROMPT_SOURCE_TAXONOMY: tuple[PromptSourceTaxonomyEntry, ...] = (
    PromptSourceTaxonomyEntry(
        source_key="prompt_template_service",
        authority_level="compat_governance",
        integration_status="governance_and_runtime_adjacent",
        compiled_artifact="resolved PromptTemplate rows + rendered Jinja output",
        primary_module="prompt_templates.service.PromptTemplateService",
        runtime_consumers=(
            "evaluation.services.staged_evaluation.StagedEvaluationService",
            "evaluation.services.comprehensive_report.ComprehensiveReportService",
            "presentation_coach.services.prompt_role_resolver.PresentationPromptRoleResolver",
        ),
        notes="Owns admin/governance lookup and some runtime-adjacent helpers, but it is not the live StepFun instruction authority.",
    ),
    PromptSourceTaxonomyEntry(
        source_key="voice_instruction_compiler",
        authority_level="live",
        integration_status="drives_runtime",
        compiled_artifact="policy['instructions'] + instruction_contract_hash",
        primary_module="sales_bot.services.voice_instruction_compiler.VoiceInstructionCompiler",
        runtime_consumers=(
            "sales_bot.services.voice_runtime_policy.VoiceRuntimePolicyService.resolve_effective_policy",
            "sales_bot.websocket.stepfun_realtime_handler.StepFunRealtimeHandler",
            "presentation_coach.websocket.presentation_stepfun_realtime_handler.PresentationStepFunRealtimeHandler",
        ),
        notes="Compiles the shipped realtime instruction contract that StepFun-mode sessions actually execute.",
    ),
    PromptSourceTaxonomyEntry(
        source_key="persona_policy",
        authority_level="live",
        integration_status="feeds_compiled_contract",
        compiled_artifact="persona_policy.system_prompt + customer_pressure + tool policy inputs",
        primary_module="sales_bot.services.voice_runtime_policy.VoiceRuntimePolicyService",
        runtime_consumers=(
            "sales_bot.services.voice_instruction_compiler.VoiceInstructionCompiler.compile_base_contract",
        ),
        notes="Persona-centered policy fields are upstream inputs to the compiled voice contract, not a separate model-call surface.",
    ),
    PromptSourceTaxonomyEntry(
        source_key="presentation_prompt_resolver",
        authority_level="compat_runtime_helper",
        integration_status="runtime_helper",
        compiled_artifact="rendered interruption copy or fallback message",
        primary_module="presentation_coach.services.prompt_role_resolver.PresentationPromptRoleResolver",
        runtime_consumers=(
            "presentation_coach.websocket.presentation_handler.PresentationWebSocketHandler",
        ),
        notes="This path really renders template text into user-visible interruption copy, but only for presentation-side helper messages.",
    ),
    PromptSourceTaxonomyEntry(
        source_key="runtime_guardrails",
        authority_level="live",
        integration_status="drives_runtime",
        compiled_artifact="tool_policy / network_access_mode / require_kb_grounding / kb_lock_mode",
        primary_module="sales_bot.services.voice_runtime_policy.VoiceRuntimePolicyService",
        runtime_consumers=(
            "sales_bot.services.voice_instruction_compiler.VoiceInstructionCompiler",
            "sales_bot.services.voice_runtime_policy.VoiceRuntimePolicyService.build_stepfun_tools",
            "sales_bot.websocket.stepfun_realtime_handler.StepFunRealtimeHandler",
        ),
        notes="Provider/network/retrieval constraints already shape the realtime runtime and tools list, so these are prompt-control inputs, not passive metadata.",
    ),
    PromptSourceTaxonomyEntry(
        source_key="legacy_llm_hardcoded_prompts",
        authority_level="compat_backend_adapter",
        integration_status="drives_runtime",
        compiled_artifact="hardcoded evaluate()/generate_report() prompt strings inside LLMService",
        primary_module="common.ai.llm_service.LLMService",
        runtime_consumers=(
            "evaluation.services.staged_evaluation.StagedEvaluationService",
            "evaluation.services.comprehensive_report.ComprehensiveReportService",
            "evaluation.services.report_generation_trigger.ReportGenerationTrigger",
            "evaluation.services.ai_scoring.AIScoringService",
        ),
        notes="Legacy evaluation/report/scoring still reaches the model through built-in prompt strings instead of PromptTemplateService-rendered contracts.",
    ),
)


TEMPLATE_BYPASS_ENTRYPOINTS: tuple[TemplateBypassEntrypoint, ...] = (
    TemplateBypassEntrypoint(
        consumer="evaluation.services.staged_evaluation.StagedEvaluationService.evaluate_stage",
        template_lookup="prompt_service.get_template_for_scenario",
        runtime_call="LLMService.evaluate",
        consumes_template_text=bool(LEGACY_PROMPT_ENTRYPOINTS["evaluate"]["consumes_template_text"]),
        bypass_reason="PromptTemplateService resolves a template ID, but LLMService.evaluate rebuilds a hardcoded evaluation prompt from selected variables instead of consuming template text.",
    ),
    TemplateBypassEntrypoint(
        consumer="evaluation.services.comprehensive_report.ComprehensiveReportService._generate_detailed_feedback",
        template_lookup="prompt_service.get_template_for_scenario",
        runtime_call="LLMService.generate_report",
        consumes_template_text=bool(LEGACY_PROMPT_ENTRYPOINTS["generate_report"]["consumes_template_text"]),
        bypass_reason="A report template lookup happens first, but the template lookup result is not forwarded into the model call because LLMService.generate_report renders its own hardcoded report prompt from context.",
    ),
)


def build_prompt_source_taxonomy() -> PromptSourceTaxonomySnapshot:
    """Return the current prompt-source taxonomy snapshot."""

    return PromptSourceTaxonomySnapshot(
        version=PROMPT_SOURCE_TAXONOMY_VERSION,
        sources=PROMPT_SOURCE_TAXONOMY,
        template_bypass_entrypoints=TEMPLATE_BYPASS_ENTRYPOINTS,
    )
