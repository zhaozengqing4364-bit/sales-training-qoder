"""Industry pack / customer-pressure contract helpers.

These helpers document the current composed-asset authority model:
- We do not have a standalone industry-pack table yet.
- Industry behavior is composed from existing agent/persona/knowledge/scenario surfaces.
- Runtime truth is frozen into practice_sessions.voice_policy_snapshot and compiled instructions.
"""

from __future__ import annotations

from typing import Any

from .persona_policy import resolve_persona_policy

INDUSTRY_PACK_CONTRACT_VERSION = 1


RUNTIME_AUTHORITIES = [
    "sales_bot.services.voice_runtime_policy.resolve_effective_policy",
    "sales_bot.services.voice_instruction_compiler.compile_base_contract",
    "practice_sessions.voice_policy_snapshot",
]

ENTRYPOINTS = {
    "agent": "/api/v1/admin/agents/{agent_id}",
    "persona": "/api/v1/admin/personas/{persona_id}",
    "knowledge": "/api/v1/admin/knowledge/{knowledge_base_id}",
    "scenario": "/api/v1/scenarios/{scenario_id}",
}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def build_agent_industry_pack_contract() -> dict[str, Any]:
    return {
        "contract_version": INDUSTRY_PACK_CONTRACT_VERSION,
        "industry_pack": {
            "authority_model": "composed_from_existing_admin_surfaces",
            "summary": (
                "Industry pack is not a standalone admin resource yet; it is composed "
                "from existing agent/persona/knowledge/scenario surfaces."
            ),
            "composition_units": [
                "agent runtime shell",
                "persona behavior contract",
                "knowledge bundle",
                "scenario metadata",
            ],
        },
        "entrypoints": dict(ENTRYPOINTS),
        "runtime_authorities": list(RUNTIME_AUTHORITIES),
        "composition_rules": [
            "Agent owns runtime shell and capability defaults, not customer-pressure semantics.",
            "Persona policy owns role prompt, customer-pressure, and knowledge-bundle selection.",
            "Scenario keeps session entry metadata and legacy persona_prompt compatibility only.",
            "Knowledge bases stay in the existing admin knowledge surface and bind via persona_policy.knowledge_base_ids.",
        ],
        "observability_surfaces": [
            "/api/v1/admin/personas/policy-health",
            "practice_sessions.voice_policy_snapshot",
            "common.conversation.runtime_diagnostics.build_retrieval_facts",
        ],
    }


def build_persona_industry_pack_contract() -> dict[str, Any]:
    return {
        "contract_version": INDUSTRY_PACK_CONTRACT_VERSION,
        "owned_fields": {
            "persona": [
                "persona_policy.system_prompt",
                "traits",
                "behavior_config",
                "tts_config",
                "difficulty",
            ],
            "customer_pressure": [
                "persona_policy.customer_pressure.pressure_direction.sales_focus",
                "persona_policy.customer_pressure.pressure_direction.value_axes",
                "persona_policy.customer_pressure.pressure_direction.objection_axes",
                "persona_policy.customer_pressure.follow_up_behavior.question_strategy",
                "persona_policy.customer_pressure.follow_up_behavior.revisit_on_evasion",
                "persona_policy.customer_pressure.follow_up_behavior.require_evidence",
                "persona_policy.customer_pressure.follow_up_behavior.expected_customer_questions",
            ],
            "knowledge_bundle": [
                "persona_policy.knowledge_base_ids",
                "persona_policy.tool_policy.enable_internal_retrieval",
                "persona_policy.tool_policy.require_kb_grounding",
                "persona_policy.tool_policy.retrieval_priority",
                "persona_policy.tool_policy.allow_web_search_without_kb",
            ],
            "scenario": [
                "scenarios.scenario_id",
                "scenarios.scenario_type",
                "scenarios.name",
                "scenarios.description",
                "scenarios.persona_prompt (legacy compatibility only)",
            ],
        },
        "runtime_targets": {
            "persona": {
                "persisted_in": "practice_sessions.voice_policy_snapshot.persona_policy",
                "compiled_instruction_sections": ["角色核心设定", "角色特征", "角色行为准则"],
            },
            "customer_pressure": {
                "persisted_in": "practice_sessions.voice_policy_snapshot.customer_pressure",
                "compiled_instruction_section": "销售追问焦点",
                "runtime_service": "sales_bot.services.voice_runtime_policy.resolve_effective_policy",
            },
            "knowledge_bundle": {
                "persisted_in": "practice_sessions.voice_policy_snapshot.knowledge_base_ids",
                "tool_builder": "sales_bot.services.voice_runtime_policy.build_stepfun_tools",
                "read_side": "common.conversation.runtime_diagnostics.build_retrieval_facts",
            },
            "scenario": {
                "session_entry": "common.api.practice",
                "websocket_router": "sales_bot.websocket.router",
                "note": "sales scenario metadata participates in session entry, but persona-centered runtime truth comes from the frozen voice policy snapshot.",
            },
        },
        "governance_rules": [
            "Customer-pressure and knowledge-bundle rules must be updated through persona_policy, not ad-hoc prompt text.",
            "Scenario metadata can label the training context, but it does not replace persona_policy as runtime truth.",
            "Industry pack rollout should reuse existing admin/persona/knowledge entrypoints instead of adding a second content platform.",
        ],
    }


def build_sales_scenario_runtime_contract() -> dict[str, Any]:
    return {
        "contract_version": INDUSTRY_PACK_CONTRACT_VERSION,
        "industry_pack": {
            "authority_model": "composed_from_existing_surfaces",
            "scenario_owner": "sales scenarios api",
            "summary": (
                "Sales scenarios provide session-facing labels and discovery surfaces; "
                "persona_policy and knowledge bindings still define runtime truth."
            ),
        },
        "entrypoints": dict(ENTRYPOINTS),
        "runtime_targets": {
            "scenario": {
                "used_by": [
                    "scenario listing",
                    "session creation",
                    "websocket scenario routing",
                ],
                "authority": "common.db.models.Scenario",
            },
            "customer_pressure": {
                "reads_from": "persona_policy.customer_pressure",
                "compiled_in": "sales_bot.services.voice_instruction_compiler.compile_base_contract",
                "persisted_in": "practice_sessions.voice_policy_snapshot",
            },
            "knowledge_base_ids": {
                "reads_from": "persona_policy.knowledge_base_ids",
                "tool_policy_source": "persona_policy.tool_policy",
                "persisted_in": "practice_sessions.voice_policy_snapshot",
            },
        },
        "notes": [
            "persona_prompt on Scenario remains a legacy compatibility field for sales scenario metadata.",
            "Runtime snapshots are the inspection surface for proving which customer-pressure and knowledge bundle actually applied.",
        ],
    }


def build_persona_runtime_binding_summary(persona: Any) -> dict[str, Any]:
    persona_policy = resolve_persona_policy(persona)
    customer_pressure = _as_dict(persona_policy.get("customer_pressure"))
    pressure_direction = _as_dict(customer_pressure.get("pressure_direction"))
    follow_up_behavior = _as_dict(customer_pressure.get("follow_up_behavior"))

    return {
        "industry_pack_strategy": "persona_policy_plus_scenario_plus_knowledge",
        "customer_pressure_source": str(customer_pressure.get("source") or "none"),
        "sales_focus": str(pressure_direction.get("sales_focus") or ""),
        "value_axes": _as_str_list(pressure_direction.get("value_axes")),
        "objection_axes": _as_str_list(pressure_direction.get("objection_axes")),
        "expected_customer_questions": _as_str_list(
            follow_up_behavior.get("expected_customer_questions")
        ),
        "knowledge_base_ids": _as_str_list(persona_policy.get("knowledge_base_ids")),
        "runtime_impacts": [
            "compiled_instructions",
            "voice_policy_snapshot.customer_pressure",
            "voice_policy_snapshot.knowledge_base_ids",
        ],
    }
