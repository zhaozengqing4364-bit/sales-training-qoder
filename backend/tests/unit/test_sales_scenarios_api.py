"""Unit tests for dynamic sales personas API."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sales_bot.api.scenarios import get_sales_runtime_contract, list_sales_personas


class _DummyResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_list_sales_personas_reads_from_database_and_deduplicates():
    persona_a = SimpleNamespace(
        id="persona-a",
        name="技术型 CTO",
        description="关注技术实现",
        traits={"关注点": "技术细节", "风格": "严谨"},
        difficulty="hard",
    )
    persona_b = SimpleNamespace(
        id="persona-b",
        name="价格敏感型买家",
        description="优先看价格",
        traits={"关注点": "价格与折扣"},
        difficulty="medium",
    )

    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=_DummyResult(
                [
                    (persona_a, 1),
                    (persona_b, 2),
                    (persona_a, 3),
                ]
            )
        )
    )

    payload = await list_sales_personas(
        agent_id=None,
        current_user=SimpleNamespace(user_id="user-1"),
        db=db,
    )

    assert len(payload) == 2
    assert payload[0]["id"] == "persona-a"
    assert payload[0]["characteristics"] == ["关注点: 技术细节", "风格: 严谨"]
    assert payload[0]["runtime_binding"]["industry_pack_strategy"] == "persona_policy_plus_scenario_plus_knowledge"
    assert payload[0]["runtime_binding"]["runtime_impacts"] == [
        "compiled_instructions",
        "voice_policy_snapshot.customer_pressure",
        "voice_policy_snapshot.knowledge_base_ids",
    ]
    assert payload[1]["id"] == "persona-b"


@pytest.mark.asyncio
async def test_list_sales_personas_returns_empty_list_on_query_error():
    db = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("db unavailable")))

    payload = await list_sales_personas(
        agent_id="agent-1",
        current_user=SimpleNamespace(user_id="user-1"),
        db=db,
    )

    assert payload == []


@pytest.mark.asyncio
async def test_get_sales_runtime_contract_exposes_industry_pack_mapping():
    payload = await get_sales_runtime_contract(
        current_user=SimpleNamespace(user_id="user-1"),
        db=SimpleNamespace(),
    )

    assert payload["contract_version"] == 1
    assert payload["industry_pack"]["authority_model"] == "composed_from_existing_surfaces"
    assert payload["industry_pack"]["scenario_owner"] == "sales scenarios api"
    assert "customer_pressure" in payload["runtime_targets"]
    assert "knowledge_base_ids" in payload["runtime_targets"]
    assert payload["runtime_targets"]["customer_pressure"]["persisted_in"] == "practice_sessions.voice_policy_snapshot"
