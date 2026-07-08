from common.ai.config_manager import ConfigManager
from common.ai.models import ModelType
from common.config import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL


def _clear_llm_env(monkeypatch) -> None:
    for name in (
        "LLM_API_KEY",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
        "LLM_TIMEOUT",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_TOKENS",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_llm_env_fallback_uses_project_default_when_llm_env_is_configured(
    monkeypatch,
):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "test-llm-key")

    config = ConfigManager().get_env_fallback(ModelType.LLM)

    assert config is not None
    assert config["provider"] == "openai"
    assert config["base_url"] == DEFAULT_LLM_BASE_URL
    assert config["model_name"] == DEFAULT_LLM_MODEL
    assert config["api_key"] == "test-llm-key"
    assert config["extra_config"]["timeout"] == 10.0


def test_llm_env_fallback_keeps_openai_legacy_defaults_when_only_openai_key_exists(
    monkeypatch,
):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    config = ConfigManager().get_env_fallback(ModelType.LLM)

    assert config is not None
    assert config["provider"] == "openai"
    assert config["base_url"] == "https://api.openai.com/v1"
    assert config["model_name"] == "gpt-4o"
    assert config["api_key"] == "test-openai-key"
