from __future__ import annotations

from common.ai.config_manager import ConfigManager
from common.ai.models import ModelType


def test_embedding_env_prefers_embedding_specific_dashscope_config(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-key")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-v4")
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

    config = ConfigManager().get_env_fallback(ModelType.EMBEDDING)

    assert config is not None
    assert config["api_key"] == "embedding-key"
    assert config["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config["model_name"] == "text-embedding-v4"


def test_embedding_env_uses_dashscope_key_defaults(monkeypatch):
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    config = ConfigManager().get_env_fallback(ModelType.EMBEDDING)

    assert config is not None
    assert config["api_key"] == "dashscope-key"
    assert config["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config["model_name"] == "text-embedding-v4"
