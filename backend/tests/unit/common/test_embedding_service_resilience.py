from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from common.ai.embedding_service import EmbeddingService


@pytest.mark.asyncio
async def test_embed_returns_failure_on_httpx_request_error(monkeypatch):
    service = EmbeddingService()
    service._effective_config = {
        "provider": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "test-key",
        "model_name": "text-embedding-v4",
        "extra_config": {},
    }

    class ExplodingClient:
        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(
        service,
        "_get_client",
        AsyncMock(return_value=ExplodingClient()),
    )

    result = await service.embed_batch(["测试内部检索"])

    assert result.is_success is False
    assert result.fallback is not None
    assert "[EMBEDDING_ERROR]" in result.fallback
    assert "ConnectError" in result.fallback
