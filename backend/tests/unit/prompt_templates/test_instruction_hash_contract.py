"""Unit tests for three-level instruction/contract hash helpers."""

from __future__ import annotations

from prompt_templates.compiled_contract import (
    build_base_instruction_hash,
    build_roleplay_contract_hash,
    build_turn_instruction_hash,
    compose_turn_instruction_text,
)
from sales_bot.services.voice_instruction_compiler import (
    VoiceInstructionCompiler,
    build_instruction_contract_hash,
)


def _sample_roleplay_contract(*, label: str = "首次拜访") -> dict:
    return {
        "schema_version": "roleplay_contract_v1",
        "contract_id": "sha256:pending",
        "situation": {"code": "first_visit", "version": "v1", "label": label},
        "relationship_context": {
            "prior_interactions": "none",
            "has_prior_meeting": False,
        },
        "visible_information_scope": {
            "initial_visible_keys": ["industry", "company_profile"],
            "hidden_by_default_keys": ["hidden_information"],
        },
        "forbidden_claim_patterns": ["上次拜访"],
        "audit": {
            "compiled_at": "2026-05-27T00:00:00+00:00",
            "compiled_by": "seed",
            "compiler_version": "roleplay_contract_compiler_v1",
            "contract_hash": "sha256:pending",
        },
    }


def test_roleplay_contract_hash_is_stable_and_ignores_audit_metadata():
    first = build_roleplay_contract_hash(_sample_roleplay_contract())
    changed_audit = _sample_roleplay_contract()
    changed_audit["audit"]["compiled_at"] = "2026-05-28T00:00:00+00:00"
    changed_audit["contract_id"] = "sha256:changed"

    assert first == build_roleplay_contract_hash(changed_audit)
    assert first is not None
    assert first.startswith("sha256:")


def test_roleplay_contract_hash_changes_when_domain_fields_change():
    baseline = build_roleplay_contract_hash(_sample_roleplay_contract())
    changed = build_roleplay_contract_hash(
        _sample_roleplay_contract(label="复访推进")
    )

    assert baseline != changed


def test_roleplay_contract_hash_returns_none_for_missing_or_legacy_contract():
    assert build_roleplay_contract_hash(None) is None
    assert build_roleplay_contract_hash({}) is None
    assert (
        build_roleplay_contract_hash(
            {"legacy_status": "legacy_unstructured_roleplay"}
        )
        is None
    )


def test_base_instruction_hash_is_stable_and_distinct_from_turn_hash():
    base = "【角色核心设定】\n你是制造业 CIO。"

    assert build_base_instruction_hash(base) == build_base_instruction_hash(base)
    assert build_base_instruction_hash(base) != build_turn_instruction_hash(base)


def test_anchor_changes_do_not_affect_base_instruction_hash():
    policy = {
        "persona_policy": {
            "system_prompt": "你是制造业 CIO，关注集成与 ROI。",
        }
    }
    compiled = VoiceInstructionCompiler.compile_base_contract(policy=policy)

    anchor_a = "【角色锚】\n你是 CIO，首次见面，保持审慎。"
    anchor_b = "【角色锚】\n你是 CIO，首次见面，必须追问 ROI。"

    turn_a = compose_turn_instruction_text(
        base_instructions=compiled.base_instructions,
        role_anchor_text=anchor_a,
    )
    turn_b = compose_turn_instruction_text(
        base_instructions=compiled.base_instructions,
        role_anchor_text=anchor_b,
    )

    assert build_base_instruction_hash(compiled.base_instructions) == (
        build_base_instruction_hash(compiled.base_instructions)
    )
    assert build_turn_instruction_hash(turn_a) != build_turn_instruction_hash(turn_b)
    assert build_base_instruction_hash(compiled.base_instructions) != (
        build_turn_instruction_hash(turn_a)
    )


def test_turn_instruction_hash_includes_grounding_and_roleplay_turn():
    base = "base contract"
    turn = compose_turn_instruction_text(
        base_instructions=base,
        grounding_context="用户问题：集成风险",
        roleplay_turn_instruction="当前可见字段：industry",
        role_anchor_text="【角色锚】底线约束",
    )

    assert build_turn_instruction_hash(turn) != build_base_instruction_hash(base)
    assert "集成风险" in turn
    assert "底线约束" in turn


def test_build_instruction_contract_hash_keeps_legacy_voice_instruction_domain():
    instructions = "保持客户角色。"

    assert build_instruction_contract_hash(instructions) != build_base_instruction_hash(
        instructions
    )
