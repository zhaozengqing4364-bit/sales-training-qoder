"""Unit tests for KB lock behavior in BaseSalesHandler."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import sales_bot.websocket.base_sales_handler as base_module
from sales_bot.websocket.base_sales_handler import BaseSalesHandler


class DummySalesHandler(BaseSalesHandler):
    def __init__(self):
        super().__init__("sales")
        self.generated_calls: list[str] = []
        self.last_knowledge_context = ""

    async def _generate_response(self, text: str, **kwargs) -> str | None:
        self.generated_calls.append(text)
        self.last_knowledge_context = str(kwargs.get("knowledge_context") or "")
        return "模型回答"

    async def _send_greeting(self):
        return None


@pytest.mark.asyncio
async def test_process_user_text_blocks_llm_when_kb_lock_fails(monkeypatch):
    handler = DummySalesHandler()
    handler._send_status = AsyncMock()
    handler._send_tts_response = AsyncMock()
    handler._voice_policy_snapshot = {
        "tool_policy": {"require_kb_grounding": True},
        "knowledge_base_ids": ["kb-1"],
    }

    monkeypatch.setattr(
        base_module,
        "evaluate_kb_lock_decision",
        AsyncMock(
            return_value=SimpleNamespace(
                lock_required=True,
                allow_generation=False,
                user_message="知识库未命中，拒绝回答",
                grounding_context="",
            )
        ),
    )

    await handler._process_user_text("介绍产品")

    assert handler.generated_calls == []
    handler._send_tts_response.assert_awaited_once()
    sent_text = handler._send_tts_response.await_args_list[0].args[0]
    assert sent_text == "知识库未命中，拒绝回答"


@pytest.mark.asyncio
async def test_process_user_text_passes_grounding_context_to_llm(monkeypatch):
    handler = DummySalesHandler()
    handler._send_status = AsyncMock()
    handler._send_tts_response = AsyncMock()
    handler._voice_policy_snapshot = {
        "tool_policy": {"require_kb_grounding": True},
        "knowledge_base_ids": ["kb-1"],
    }

    decision = SimpleNamespace(
        lock_required=True,
        allow_generation=True,
        user_message="",
        grounding_context="内部知识依据",
    )
    monkeypatch.setattr(
        base_module,
        "evaluate_kb_lock_decision",
        AsyncMock(return_value=decision),
    )

    await handler._process_user_text("介绍产品")

    assert handler.generated_calls == ["介绍产品"]
    assert handler.last_knowledge_context == "内部知识依据"
    handler._send_tts_response.assert_awaited_once()
