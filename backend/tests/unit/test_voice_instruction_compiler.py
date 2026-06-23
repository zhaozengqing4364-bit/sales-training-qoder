"""Unit tests for voice instruction compiler."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from sales_bot.services.it_leader_roleplay_v1 import get_roleplay_contract
from sales_bot.services.voice_instruction_compiler import (
    VoiceInstructionCompiler,
    enforce_question_limit,
)


def _first_visit_situation_pack() -> SituationPackDTO:
    return SituationPackDTO(
        code="first_visit",
        label="首次拜访",
        version="v1",
        status="published",
        relationship_context={
            "prior_interactions": "none",
            "has_prior_meeting": False,
            "has_seen_proposal": False,
            "has_discussed_budget": False,
            "has_existing_partnership": False,
            "meeting_history_summary": None,
        },
        visible_information_scope={
            "initial_visible_keys": ["industry"],
            "hidden_by_default_keys": ["hidden_information"],
        },
        forbidden_claim_patterns=["上次拜访"],
        forbidden_topic_codes=[],
        forbidden_stage_codes=[],
        conflict_response_strategy="customer_confused_correction",
        behavior_rules_for_prompt_only=[],
        disclosure_policy={},
        runtime_violation_policy={},
        compatible_practice_modes=["customer_roleplay"],
        compatible_scenario_types=["sales"],
    )


def _sample_role_anchor() -> dict[str, str]:
    return {
        "identity_template": "你是{role_name}，{relationship_stage}。{bottom_line}。",
        "bottom_line": "你不认识对方，保持审慎距离；需求未被充分理解前不让步。",
        "must_do": "追问量化影响、集成风险与可验证证据。",
        "must_not": "主动报价、承诺未验证 ROI、一次性透露全部隐藏信息。",
    }


def test_build_role_anchor_humanizes_first_visit_relationship():
    persona_policy = {"role_anchor": _sample_role_anchor()}

    anchor = VoiceInstructionCompiler.build_role_anchor(
        persona_policy,
        _first_visit_situation_pack(),
        "制造业 CIO",
    )

    assert anchor.startswith("【角色锚】")
    assert "制造业 CIO" in anchor
    assert "这是你们首次正式见面" in anchor
    assert "你不认识对方，保持审慎距离" in anchor
    assert "必须：追问量化影响、集成风险与可验证证据。" in anchor
    assert "禁止：主动报价、承诺未验证 ROI、一次性透露全部隐藏信息。" in anchor


def test_build_role_anchor_returns_empty_when_role_anchor_missing():
    anchor = VoiceInstructionCompiler.build_role_anchor(
        {"system_prompt": "prompt"},
        _first_visit_situation_pack(),
        "制造业 CIO",
    )

    assert anchor == ""


def test_build_role_anchor_returns_empty_for_empty_role_anchor_with_warning():
    with patch(
        "sales_bot.services.voice_instruction_compiler.logger.warning"
    ) as warning_mock:
        anchor = VoiceInstructionCompiler.build_role_anchor(
            {"role_anchor": {}},
            _first_visit_situation_pack(),
            "制造业 CIO",
        )

    assert anchor == ""
    warning_mock.assert_called_once()
    assert warning_mock.call_args.kwargs["reason"] == "empty_role_anchor"


def test_build_role_anchor_returns_empty_when_relationship_stage_unresolved():
    pack = SituationPackDTO(
        code="custom",
        label="自定义",
        version="v1",
        status="published",
        relationship_context={},
        visible_information_scope={},
        forbidden_claim_patterns=[],
        forbidden_topic_codes=[],
        forbidden_stage_codes=[],
        conflict_response_strategy="neutral_clarification",
        behavior_rules_for_prompt_only=[],
        disclosure_policy={},
        runtime_violation_policy={},
        compatible_practice_modes=[],
        compatible_scenario_types=[],
    )

    with patch(
        "sales_bot.services.voice_instruction_compiler.logger.warning"
    ) as warning_mock:
        anchor = VoiceInstructionCompiler.build_role_anchor(
            {"role_anchor": _sample_role_anchor()},
            pack,
            "制造业 CIO",
        )

    assert anchor == ""
    warning_mock.assert_called_once()
    assert warning_mock.call_args.kwargs["reason"] == "missing_relationship_stage"


def test_build_role_anchor_uses_meeting_history_summary_for_follow_up():
    pack = SituationPackDTO(
        code="follow_up",
        label="复访跟进",
        version="v1",
        status="published",
        relationship_context={
            "prior_interactions": "one_meeting",
            "has_prior_meeting": True,
            "meeting_history_summary": "上次已讨论现状与初步痛点。",
        },
        visible_information_scope={},
        forbidden_claim_patterns=[],
        forbidden_topic_codes=[],
        forbidden_stage_codes=[],
        conflict_response_strategy="neutral_clarification",
        behavior_rules_for_prompt_only=[],
        disclosure_policy={},
        runtime_violation_policy={},
        compatible_practice_modes=[],
        compatible_scenario_types=[],
    )

    anchor = VoiceInstructionCompiler.build_role_anchor(
        {"role_anchor": _sample_role_anchor()},
        pack,
        "制造业 CIO",
    )

    assert "上次已讨论现状与初步痛点。" in anchor


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


def test_profile_compose_turn_includes_role_anchor_for_hash_audit():
    from prompt_templates.compiled_contract import (
        build_base_instruction_hash,
        build_turn_instruction_hash,
        compose_turn_instruction_text,
    )
    from sales_bot.websocket.voice_runtime_profile import VoiceRuntimeProfile

    profile = VoiceRuntimeProfile(
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
        instructions="【系统总指令】坚持角色扮演",
        instruction_contract_hash="hash-base",
        role_anchor_text="【角色锚】\n底线约束。",
        knowledge_base_ids=(),
        tool_policy={},
    )
    turn = profile.compile_instructions(
        grounding_context="用户问题：交付周期",
    )

    assert turn == compose_turn_instruction_text(
        base_instructions=profile.instructions,
        grounding_context="用户问题：交付周期",
        role_anchor_text=profile.role_anchor_text,
    )
    assert build_base_instruction_hash(profile.instructions) != build_turn_instruction_hash(
        turn
    )


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


def test_compile_base_contract_adds_question_triggered_disclosure_rules():
    policy = {
        "persona_policy": {
            "system_prompt": "你是制造业 CIO，掌握复杂公司背景。",
        },
        "customer_pressure": {
            "hidden_information_disclosure": "question_triggered",
            "challenge_premature_pitch": True,
            "question_strategy": "single_issue",
            "objection_axes": ["integration_risk"],
        },
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": False,
            "max_questions_per_turn": 1,
        },
    }

    compiled = VoiceInstructionCompiler.compile_base_contract(policy=policy)

    assert "隐藏信息只能在销售问到对应主题后分阶段披露" in compiled.base_instructions
    assert "不要主动完整列出公司现状" in compiled.base_instructions
    assert "最多披露一个表层顾虑" in compiled.base_instructions
    assert "你还没了解我们现状，为什么认为适合" in compiled.base_instructions
    assert "每次只选择一个最关键的主问题" in compiled.base_instructions


def test_compile_base_contract_adds_v1_phase_and_state_card_anchors_only():
    contract = get_roleplay_contract()
    contract_hash = contract["audit"]["contract_hash"]
    policy = {
        "roleplay_contract": contract,
        "roleplay_contract_hash": contract_hash,
        "roleplay_phase_anchor": (
            "当前阶段 opening_intent（开场与来意）；目标：确认拜访目的。"
        ),
        "session_state_card_summary": (
            "state_card_version=1；当前阶段=opening_intent；"
            "客户态度=谨慎但愿意继续听；下一轮压力=追问拜访目的。"
        ),
    }

    compiled = VoiceInstructionCompiler.compile_base_contract(policy=policy)

    assert "【v1阶段锚点】" in compiled.base_instructions
    assert "opening_intent" in compiled.base_instructions
    assert "roleplay_contract_hash=" + contract_hash in compiled.base_instructions
    assert "【状态卡摘要】" in compiled.base_instructions
    assert "谨慎但愿意继续听" in compiled.base_instructions
    assert "标准答案" not in compiled.base_instructions
    assert "内部销售话术" not in compiled.base_instructions


def test_enforce_question_limit_trims_extra_questions_without_appending_template_copy():
    text = "你知道实习是什么吗？它有哪些功能？适合谁用？"

    trimmed = enforce_question_limit(text, max_questions_per_turn=1)

    assert trimmed == "你知道实习是什么吗？"
    assert "先回答这一点即可" not in trimmed
