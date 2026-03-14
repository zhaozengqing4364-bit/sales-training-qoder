"""Unit tests for voice instruction compiler."""

from __future__ import annotations

from types import SimpleNamespace

from sales_bot.services.voice_instruction_compiler import VoiceInstructionCompiler


def test_compile_base_contract_contains_role_and_network_constraints():
    persona = SimpleNamespace(
        system_prompt="兜底旧字段",
        traits={"决策风格": "谨慎", "关注点": "ROI"},
    )
    policy = {
        "persona_policy": {
            "system_prompt": "你是企业采购决策者，关注预算和风险。",
        },
        "tool_policy": {
            "network_access_mode": "off",
            "enable_internal_retrieval": True,
            "retrieval_priority": "kb_only",
            "strict_instruction_following": True,
            "require_grounding": True,
        },
    }

    compiled = VoiceInstructionCompiler.compile_base_contract(
        policy=policy,
        persona=persona,
    )

    assert "企业采购决策者" in compiled.base_instructions
    assert "关注预算和风险" in compiled.base_instructions
    assert "禁止联网检索" in compiled.base_instructions
    assert isinstance(compiled.contract_hash, str)
    assert len(compiled.contract_hash) == 16


def test_compose_turn_instructions_keeps_base_contract():
    merged = VoiceInstructionCompiler.compose_turn_instructions(
        base_instructions="【系统总指令】坚持角色扮演",
        grounding_context="用户问题：交付周期",
    )

    assert "坚持角色扮演" in merged
    assert "用户问题：交付周期" in merged


def test_compile_base_contract_adds_kb_lock_directive():
    policy = {
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": True,
        },
    }

    compiled = VoiceInstructionCompiler.compile_base_contract(
        policy=policy,
    )

    assert "知识库强制模式" in compiled.base_instructions
    assert "以命中片段为准" in compiled.base_instructions
