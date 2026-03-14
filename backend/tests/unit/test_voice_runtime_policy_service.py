"""
Unit tests for VoiceRuntimePolicyService.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentVoicePolicy, Persona, VoiceRuntimeProfile
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService


@pytest.mark.asyncio
async def test_resolve_effective_policy_precedence(test_db: AsyncSession):
    """Session override should take precedence over agent policy and profile defaults."""
    agent = Agent(
        id=str(uuid.uuid4()),
        name="销售教练",
        description="测试智能体",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="强势采购总监",
        description="测试角色",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是强势采购总监。",
        knowledge_base_ids=["kb_persona_1"],
    )
    default_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="默认配置",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2-mini",
        voice_name="qingchunshaonv",
        temperature=0.5,
        tool_policy={"enable_web_search": False, "enable_internal_retrieval": True},
    )
    agent_profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="Agent配置",
        is_default=False,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="wenrounansheng",
        temperature=0.8,
        tool_policy={"enable_web_search": True, "retrieval_priority": "balanced"},
    )
    agent_policy = AgentVoicePolicy(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        runtime_profile_id=agent_profile.id,
        enabled=True,
        voice_mode_override="stepfun_realtime",
        instructions_override="请严格执行角色约束。",
        tool_policy_override={"enable_web_search": True},
    )

    test_db.add_all([agent, persona, default_profile, agent_profile, agent_policy])
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy(
        agent_id=agent.id,
        persona_id=persona.id,
        voice_mode_override="legacy",
    )

    assert effective["runtime_profile_id"] == agent_profile.id
    assert effective["voice_mode"] == "legacy"
    assert effective["model_name"] == "step-audio-2"
    assert set(effective["knowledge_base_ids"]) == {"kb_persona_1"}
    assert effective["tool_policy"]["enable_web_search"] is False
    assert effective["tool_policy"]["retrieval_priority"] == "kb_only"
    assert effective["source"]["tool_policy_enforcement"] == "kb_lock_enforced"
    assert effective["source"]["kb_lock_default"] == "auto_enabled_when_kb_bound"
    assert effective["tool_policy"]["require_kb_grounding"] is True
    assert effective["tool_policy"]["network_access_mode"] == "off"
    assert isinstance(effective["instruction_contract_hash"], str)
    assert effective["instruction_contract_hash"]
    assert "角色核心设定" in effective["instructions"]


@pytest.mark.asyncio
async def test_resolve_effective_policy_disables_retrieval_without_kb(
    test_db: AsyncSession,
):
    """Internal retrieval should auto-disable when no knowledge base is bound."""
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="无知识库测试",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
        tool_policy={"enable_internal_retrieval": True},
    )
    test_db.add(profile)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy()

    assert effective["knowledge_base_ids"] == []
    assert effective["tool_policy"]["enable_internal_retrieval"] is False
    assert effective["tool_policy"]["enable_web_search"] is False
    assert effective["source"]["tool_policy_enforcement"] == "no_kb_no_web"


@pytest.mark.asyncio
async def test_resolve_effective_policy_kb_only_disables_web_search(
    test_db: AsyncSession,
):
    """KB-only retrieval priority should enforce internal retrieval and disable web search."""
    agent = Agent(
        id=str(uuid.uuid4()),
        name="知识库优先测试智能体",
        description="测试 kb_only 策略",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="知识库角色",
        description="绑定知识库",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是采购负责人。",
        knowledge_base_ids=["kb_persona_only_1"],
    )
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="仅知识库档位",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
        tool_policy={
            "enable_internal_retrieval": True,
            "enable_web_search": True,
            "retrieval_priority": "kb_only",
        },
    )
    test_db.add_all([agent, persona, profile])
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy(
        agent_id=agent.id,
        persona_id=persona.id,
    )

    assert effective["tool_policy"]["retrieval_priority"] == "kb_only"
    assert effective["tool_policy"]["enable_internal_retrieval"] is True
    assert effective["tool_policy"]["enable_web_search"] is False
    assert "知识库强制模式" in effective["instructions"]


@pytest.mark.asyncio
async def test_resolve_effective_policy_disables_web_search_when_kb_bound_even_if_internal_retrieval_disabled(
    test_db: AsyncSession,
):
    """When KB is bound, policy should always force KB-only internal retrieval."""
    agent = Agent(
        id=str(uuid.uuid4()),
        name="联网禁用测试智能体",
        description="测试 KB 绑定时禁用联网",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="企业知识角色",
        description="绑定企业知识",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是采购总监。",
        knowledge_base_ids=["kb_enterprise_1"],
    )
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="冲突策略档位",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
        tool_policy={
            "enable_internal_retrieval": False,
            "enable_web_search": True,
            "retrieval_priority": "web_first",
        },
    )
    test_db.add_all([agent, persona, profile])
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy(
        agent_id=agent.id,
        persona_id=persona.id,
    )

    assert effective["tool_policy"]["enable_internal_retrieval"] is True
    assert effective["tool_policy"]["enable_web_search"] is False
    assert effective["tool_policy"]["retrieval_priority"] == "kb_only"
    assert effective["source"]["tool_policy_enforcement"] == "kb_lock_enforced"
    assert effective["source"]["kb_lock_default"] == "auto_enabled_when_kb_bound"
    assert effective["tool_policy"]["require_kb_grounding"] is True


@pytest.mark.asyncio
async def test_resolve_effective_policy_respects_explicit_disable_kb_lock(
    test_db: AsyncSession,
):
    """When persona explicitly disables KB lock, auto-default lock must not override it."""
    agent = Agent(
        id=str(uuid.uuid4()),
        name="显式关闭锁测试",
        description="验证显式策略优先",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="显式关闭锁角色",
        description="绑定知识库但显式允许非严格模式",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是采购总监。",
        knowledge_base_ids=["kb_enterprise_2"],
        persona_policy={
            "version": 1,
            "system_prompt": "你是采购总监。",
            "knowledge_base_ids": ["kb_enterprise_2"],
            "tool_policy": {
                "require_kb_grounding": False,
                "network_access_mode": "off",
                "enable_web_search": False,
            },
        },
    )
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="显式关闭锁档位",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
    )
    test_db.add_all([agent, persona, profile])
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy(
        agent_id=agent.id,
        persona_id=persona.id,
    )

    assert effective["tool_policy"]["require_kb_grounding"] is False
    assert effective["source"]["tool_policy_enforcement"] == "kb_internal_only"
    assert "kb_lock_default" not in effective["source"]


@pytest.mark.asyncio
async def test_resolve_effective_policy_legacy_agent_kb_fallback_keeps_kb_lock(
    test_db: AsyncSession,
):
    """Compatibility: agent-level KB binding should still be readable during migration."""
    agent = Agent(
        id=str(uuid.uuid4()),
        name="旧版智能体KB",
        description="agent-level KB fallback",
        category="sales",
        status="published",
        default_knowledge_base_ids=["kb_agent_legacy_1"],
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="无KB角色",
        description="persona policy 未配置KB",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是采购总监。",
        knowledge_base_ids=[],
        persona_policy={
            "version": 1,
            "system_prompt": "你是采购总监。",
            "knowledge_base_ids": [],
            "tool_policy": {},
        },
    )
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="兼容回退档位",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
    )
    test_db.add_all([agent, persona, profile])
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy(
        agent_id=agent.id,
        persona_id=persona.id,
    )

    assert set(effective["knowledge_base_ids"]) == {"kb_agent_legacy_1"}
    assert (
        effective["source"]["knowledge_base_source"]
        == "agent_default_knowledge_base_ids_legacy_fallback"
    )
    assert effective["tool_policy"]["require_kb_grounding"] is True
    assert effective["source"]["tool_policy_enforcement"] == "kb_lock_enforced"


@pytest.mark.asyncio
async def test_resolve_effective_policy_uses_lower_default_similarity_threshold(
    test_db: AsyncSession,
):
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="默认检索阈值档位",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
    )
    test_db.add(profile)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy()

    assert effective["tool_policy"]["retrieval_similarity_threshold"] == 0.58


@pytest.mark.asyncio
async def test_resolve_effective_policy_contains_snapshot_metadata(
    test_db: AsyncSession,
):
    """Resolved policy should always include snapshot baseline metadata fields."""
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="默认快照配置",
        is_default=True,
        is_active=True,
        voice_mode="legacy",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
    )
    test_db.add(profile)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy()

    assert effective["voice_mode"] == "legacy"
    assert effective["runtime_profile_id"] == profile.id
    assert isinstance(effective["tool_policy"], dict)
    assert effective["tool_policy"]["network_access_mode"] == "off"
    assert isinstance(effective["knowledge_base_ids"], list)
    assert isinstance(effective["source"], dict)
    assert effective["source"].get("runtime_profile") == "system_default"
    assert "resolved_at" in effective
    assert isinstance(effective.get("instruction_contract_hash"), str)
    resolved_at = datetime.fromisoformat(str(effective["resolved_at"]))
    assert resolved_at.year >= 2025


@pytest.mark.asyncio
async def test_resolve_effective_policy_allows_controlled_web_search_without_kb_when_enabled(
    test_db: AsyncSession,
):
    """Controlled mode can allow web search without KB when explicitly enabled."""
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="联网受控档位",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
        tool_policy={
            "enable_web_search": True,
            "enable_internal_retrieval": False,
            "network_access_mode": "controlled",
            "allow_web_search_without_kb": True,
            "retrieval_priority": "web_first",
        },
    )
    test_db.add(profile)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy()

    assert effective["knowledge_base_ids"] == []
    assert effective["tool_policy"]["network_access_mode"] == "controlled"
    assert effective["tool_policy"]["allow_web_search_without_kb"] is True
    assert effective["tool_policy"]["enable_web_search"] is True
    assert effective["tool_policy"]["enable_internal_retrieval"] is False


@pytest.mark.asyncio
async def test_resolve_effective_policy_enforces_kb_lock_when_enabled(
    test_db: AsyncSession,
):
    """KB lock should force internal-only retrieval even without bound KB IDs."""
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="知识库硬锁档位",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
        tool_policy={
            "enable_web_search": True,
            "enable_internal_retrieval": False,
            "network_access_mode": "controlled",
            "allow_web_search_without_kb": True,
            "retrieval_priority": "web_first",
            "require_kb_grounding": True,
        },
    )
    test_db.add(profile)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy()

    assert effective["knowledge_base_ids"] == []
    assert effective["tool_policy"]["require_kb_grounding"] is True
    assert effective["tool_policy"]["enable_internal_retrieval"] is True
    assert effective["tool_policy"]["enable_web_search"] is False
    assert effective["tool_policy"]["retrieval_priority"] == "kb_only"
    assert effective["source"]["tool_policy_enforcement"] == "kb_lock_unbound"


@pytest.mark.asyncio
async def test_create_profile_should_switch_default_flag(test_db: AsyncSession):
    """Creating a new default profile should clear previous default profile."""
    existing_default = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="旧默认",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
    )
    test_db.add(existing_default)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    created = await service.create_profile(
        {
            "name": "新默认",
            "is_default": True,
            "is_active": True,
            "voice_mode": "stepfun_realtime",
            "model_name": "step-audio-2-mini",
            "voice_name": "wenrounansheng",
            "temperature": 0.6,
            "tool_policy": {"enable_web_search": True},
        }
    )
    await test_db.commit()

    assert created["is_default"] is True

    result = await test_db.execute(
        select(VoiceRuntimeProfile).where(VoiceRuntimeProfile.name == "旧默认")
    )
    old_profile = result.scalar_one()
    assert old_profile.is_default is False


@pytest.mark.asyncio
async def test_create_profile_rejects_deprecated_instruction_template(
    test_db: AsyncSession,
):
    service = VoiceRuntimePolicyService(test_db)
    with pytest.raises(ValueError) as exc_info:
        await service.create_profile(
            {
                "name": "非法配置",
                "voice_mode": "stepfun_realtime",
                "system_instruction_template": "legacy",
            }
        )
    assert "[FIELD_DEPRECATED_PERSONA_CENTERED]" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upsert_agent_policy_rejects_deprecated_instruction_override(
    test_db: AsyncSession,
):
    agent = Agent(
        id=str(uuid.uuid4()),
        name="策略测试智能体",
        description="test",
        category="sales",
        status="draft",
    )
    test_db.add(agent)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    with pytest.raises(ValueError) as exc_info:
        await service.upsert_agent_policy(
            agent.id,
            {"instructions_override": "legacy override"},
        )
    assert "[FIELD_DEPRECATED_PERSONA_CENTERED]" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upsert_agent_policy_rejects_persona_owned_tool_keys(
    test_db: AsyncSession,
):
    agent = Agent(
        id=str(uuid.uuid4()),
        name="策略测试智能体2",
        description="test",
        category="sales",
        status="draft",
    )
    test_db.add(agent)
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    with pytest.raises(ValueError) as exc_info:
        await service.upsert_agent_policy(
            agent.id,
            {"tool_policy_override": {"enable_web_search": True}},
        )
    assert "[FIELD_DEPRECATED_PERSONA_CENTERED]" in str(exc_info.value)
