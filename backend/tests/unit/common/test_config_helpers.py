from __future__ import annotations

import inspect

from common import config


def test_env_int_should_return_parsed_value_when_valid(monkeypatch) -> None:
    monkeypatch.setenv("CONFIG_HELPER_TEST_INT", "42")

    assert config._env_int("CONFIG_HELPER_TEST_INT", 10, 1, 100) == 42


def test_env_int_should_return_default_when_invalid(monkeypatch) -> None:
    monkeypatch.setenv("CONFIG_HELPER_TEST_INT", "not-an-int")

    assert config._env_int("CONFIG_HELPER_TEST_INT", 10, 1, 100) == 10


def test_env_int_should_keep_existing_clamp_strategy_when_out_of_range(
    monkeypatch,
) -> None:
    monkeypatch.setenv("CONFIG_HELPER_TEST_INT", "9000")

    assert config._env_int("CONFIG_HELPER_TEST_INT", 10, 1, 100) == 100


def test_env_choice_should_return_allowlisted_lowercase_value(monkeypatch) -> None:
    monkeypatch.setenv("CONFIG_HELPER_TEST_CHOICE", "DROP_OLDEST")

    assert (
        config._env_choice(
            "CONFIG_HELPER_TEST_CHOICE",
            "drop_newest",
            {"drop_newest", "drop_oldest"},
        )
        == "drop_oldest"
    )


def test_env_choice_should_return_default_when_invalid(monkeypatch) -> None:
    monkeypatch.setenv("CONFIG_HELPER_TEST_CHOICE", "delete_everything")

    assert (
        config._env_choice(
            "CONFIG_HELPER_TEST_CHOICE",
            "drop_newest",
            {"drop_newest", "drop_oldest"},
        )
        == "drop_newest"
    )


def test_config_module_should_define_only_current_env_helpers_once() -> None:
    source = inspect.getsource(config)

    assert source.count("def _env_int(") == 1
    assert source.count("def _env_choice(") == 1
    assert not hasattr(config, "_get_int_env")
    assert not hasattr(config, "_get_enum_env")
    assert "def _get_int_env(" not in source
    assert "def _get_enum_env(" not in source
