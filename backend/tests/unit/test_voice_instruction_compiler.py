"""Unit tests for voice instruction compiler."""

from __future__ import annotations

from types import SimpleNamespace

from sales_bot.services.voice_instruction_compiler import (
    VoiceInstructionCompiler,
    enforce_question_limit,
)


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


def test_compile_base_contract_adds_coach_mode_and_single_question_directives():
    policy = {
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": True,
            "kb_lock_mode": "coach_mode",
            "max_questions_per_turn": 1,
        },
    }

    compiled = VoiceInstructionCompiler.compile_base_contract(
        policy=policy,
    )

    assert "训练辅导模式" in compiled.base_instructions
    assert "不得直接抛出内部错误" in compiled.base_instructions
    assert "每轮最多提出1个问题句" in compiled.base_instructions


def test_compile_base_contract_includes_sales_focus_axes_and_expected_questions():
    policy = {
        "persona_policy": {
            "system_prompt": "你是谨慎采购负责人。",
            "sales_focus": "value_translation",
            "value_axes": ["客户收益", "ROI", "预算优先级"],
            "objection_axes": ["价格", "竞品替代", "实施风险", "案例证据"],
            "expected_customer_questions": [
                "如果没有量化收益，我为什么要为这个方案买单？",
                "你们和竞品相比，ROI 证据在哪里？",
            ],
        },
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": True,
            "kb_lock_mode": "coach_mode",
            "max_questions_per_turn": 1,
        },
    }

    compiled = VoiceInstructionCompiler.compile_base_contract(
        policy=policy,
    )

    assert "价值翻译" in compiled.base_instructions
    assert "客户收益" in compiled.base_instructions
    assert "ROI" in compiled.base_instructions
    assert "预算优先级" in compiled.base_instructions
    assert "价格" in compiled.base_instructions
    assert "竞品替代" in compiled.base_instructions
    assert "实施风险" in compiled.base_instructions
    assert "案例证据" in compiled.base_instructions
    assert "如果没有量化收益" in compiled.base_instructions
    assert "ROI 证据在哪里" in compiled.base_instructions
    assert "训练辅导模式" in compiled.base_instructions
    assert "每轮最多提出1个问题句" in compiled.base_instructions


def test_compile_base_contract_uses_structured_customer_pressure_contract():
    policy = {
        "persona_policy": {
            "system_prompt": "你是强势采购负责人。",
        },
        "customer_pressure": {
            "source": "explicit",
            "pressure_direction": {
                "sales_focus": "proof",
                "value_axes": ["ROI", "客户收益"],
                "objection_axes": ["价格", "实施风险"],
            },
            "follow_up_behavior": {
                "question_strategy": "single_issue",
                "revisit_on_evasion": True,
                "require_evidence": True,
                "expected_customer_questions": [
                    "你拿什么证明这个 ROI 不是口号？",
                ],
            },
        },
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": True,
            "kb_lock_mode": "coach_mode",
            "max_questions_per_turn": 1,
        },
    }

    compiled = VoiceInstructionCompiler.compile_base_contract(policy=policy)

    assert "案例证据" in compiled.base_instructions
    assert "ROI" in compiled.base_instructions
    assert "客户收益" in compiled.base_instructions
    assert "价格" in compiled.base_instructions
    assert "实施风险" in compiled.base_instructions
    assert "回到同一阻塞点继续追问" in compiled.base_instructions
    assert "可验证证据" in compiled.base_instructions
    assert "你拿什么证明这个 ROI 不是口号" in compiled.base_instructions


def test_enforce_question_limit_trims_extra_questions_without_appending_template_copy():
    text = "你知道实习是什么吗？它有哪些功能？适合谁用？"

    trimmed = enforce_question_limit(text, max_questions_per_turn=1)

    assert trimmed == "你知道实习是什么吗？"
    assert "先回答这一点即可" not in trimmed
