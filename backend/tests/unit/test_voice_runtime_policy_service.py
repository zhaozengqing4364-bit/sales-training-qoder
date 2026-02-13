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
        default_knowledge_base_ids=["kb_agent_1"],
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
    assert set(effective["knowledge_base_ids"]) == {"kb_agent_1", "kb_persona_1"}
    assert effective["tool_policy"]["enable_web_search"] is True
    assert "角色设定" in effective["instructions"]


@pytest.mark.asyncio
async def test_resolve_effective_policy_disables_retrieval_without_kb(test_db: AsyncSession):
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


@pytest.mark.asyncio
async def test_resolve_effective_policy_kb_only_disables_web_search(test_db: AsyncSession):
    """KB-only retrieval priority should enforce internal retrieval and disable web search."""
    agent = Agent(
        id=str(uuid.uuid4()),
        name="知识库优先测试智能体",
        description="测试 kb_only 策略",
        category="sales",
        status="published",
        default_knowledge_base_ids=["kb_agent_only_1"],
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
    test_db.add_all([agent, profile])
    await test_db.commit()

    service = VoiceRuntimePolicyService(test_db)
    effective = await service.resolve_effective_policy(agent_id=agent.id)

    assert effective["tool_policy"]["retrieval_priority"] == "kb_only"
    assert effective["tool_policy"]["enable_internal_retrieval"] is True
    assert effective["tool_policy"]["enable_web_search"] is False
    assert "仅使用内部知识库检索" in effective["instructions"]


@pytest.mark.asyncio
async def test_resolve_effective_policy_contains_snapshot_metadata(test_db: AsyncSession):
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
    assert isinstance(effective["knowledge_base_ids"], list)
    assert isinstance(effective["source"], dict)
    assert effective["source"].get("runtime_profile") == "system_default"
    assert "resolved_at" in effective
    resolved_at = datetime.fromisoformat(str(effective["resolved_at"]))
    assert resolved_at.year >= 2025


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

    result = await test_db.execute(select(VoiceRuntimeProfile).where(VoiceRuntimeProfile.name == "旧默认"))
    old_profile = result.scalar_one()
    assert old_profile.is_default is False
