from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.verify_sales_trainer_real_provider_config import (
    check_real_provider_config,
    main,
    resolve_config_values,
    smoke_test_command,
    write_json_report,
)


def test_should_report_missing_real_provider_config() -> None:
    result = check_real_provider_config({}, env_file=None)

    assert not result.ready
    assert "DEUCATE_API_KEY is required." in result.messages
    assert "DASHSCOPE_API_KEY is required." in result.messages
    assert "SALES_TRAINER_REAL_ASR_AUDIO_URL is required." in result.messages
    generated_at = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
    assert result.to_safe_dict(generated_at=generated_at) == {
        "ready": False,
        "messages": result.messages,
        "checked_keys": [
            "SALES_TRAINER_RUN_REAL_PROVIDER_TESTS",
            "DEUCATE_BASE_URL",
            "DEUCATE_API_KEY",
            "DASHSCOPE_API_KEY",
            "SALES_TRAINER_ASR_MODE",
            "SALES_TRAINER_REAL_ASR_AUDIO_URL",
        ],
        "generated_at": generated_at.isoformat(),
        "env_file": None,
        "smoke_requested": False,
        "smoke_ran": False,
    }


def test_should_accept_ready_real_provider_config(tmp_path: Path) -> None:
    result = check_real_provider_config(
        {
            "SALES_TRAINER_RUN_REAL_PROVIDER_TESTS": "1",
            "DEUCATE_BASE_URL": "https://deucate.example.test/v1",
            "DEUCATE_API_KEY": "secret-value",
            "DASHSCOPE_API_KEY": "dashscope-secret-value",
            "SALES_TRAINER_ASR_MODE": "file",
            "SALES_TRAINER_REAL_ASR_AUDIO_URL": "https://audio.example.test/sample.wav",
        },
        env_file=None,
    )

    assert result.ready
    assert result.messages == []


def test_should_reject_placeholder_real_provider_config_values() -> None:
    result = check_real_provider_config(
        {
            "SALES_TRAINER_RUN_REAL_PROVIDER_TESTS": "1",
            "DEUCATE_BASE_URL": "replace-with-deucate-base-url",
            "DEUCATE_API_KEY": "replace-with-deucate-api-key",
            "DASHSCOPE_API_KEY": "replace-with-new-dashscope-api-key",
            "SALES_TRAINER_ASR_MODE": "file",
            "SALES_TRAINER_REAL_ASR_AUDIO_URL": "https://audio.example.test/sample.wav",
        },
        env_file=None,
    )

    assert not result.ready
    assert "DEUCATE_BASE_URL is required." in result.messages
    assert "DEUCATE_API_KEY is required." in result.messages
    assert "DASHSCOPE_API_KEY is required." in result.messages


def test_should_build_real_provider_smoke_test_command() -> None:
    assert smoke_test_command("/tmp/python") == [
        "/tmp/python",
        "-m",
        "pytest",
        "tests/integration/test_sales_trainer_real_providers.py",
        "--no-cov",
    ]


def test_should_include_audit_context_in_safe_payload() -> None:
    generated_at = datetime(2026, 5, 28, 12, 30, tzinfo=UTC)
    env_file = Path("/tmp/backend/.env")
    result = check_real_provider_config({}, env_file=None)

    payload = result.to_safe_dict(
        generated_at=generated_at,
        env_file=env_file,
        smoke_requested=True,
        smoke_command=["python", "-m", "pytest"],
        smoke_exit_code=7,
    )

    assert payload["generated_at"] == generated_at.isoformat()
    assert payload["env_file"] == str(env_file)
    assert payload["smoke_requested"] is True
    assert payload["smoke_ran"] is True
    assert payload["smoke_exit_code"] == 7


def test_should_load_real_provider_config_from_env_file(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1",
                "DEUCATE_BASE_URL=https://deucate.example.test/v1",
                "DEUCATE_API_KEY=secret-value",
                "DASHSCOPE_API_KEY=dashscope-secret-value",
                "SALES_TRAINER_ASR_MODE=file",
                "SALES_TRAINER_REAL_ASR_AUDIO_URL=https://audio.example.test/sample.wav",
            ]
        )
    )

    result = check_real_provider_config(env={}, env_file=env_path)

    assert result.ready


def test_should_prefer_explicit_env_over_env_file(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=0",
                "DEUCATE_BASE_URL=https://deucate.example.test/v1",
                "DEUCATE_API_KEY=env-file-secret",
                "DASHSCOPE_API_KEY=dashscope-secret-value",
                "SALES_TRAINER_ASR_MODE=file",
                "SALES_TRAINER_REAL_ASR_AUDIO_URL=https://audio.example.test/sample.wav",
            ]
        )
    )

    values = resolve_config_values(
        env={"SALES_TRAINER_RUN_REAL_PROVIDER_TESTS": "1"},
        env_file=env_path,
    )

    result = check_real_provider_config(values, env_file=None)

    assert result.ready


def test_should_print_safe_json_without_secret_values(
    tmp_path: Path,
    capsys,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "SALES_TRAINER_RUN_REAL_PROVIDER_TESTS=1",
                "DEUCATE_BASE_URL=https://deucate.example.test/v1",
                "DEUCATE_API_KEY=secret-value",
                "DASHSCOPE_API_KEY=dashscope-secret-value",
                "SALES_TRAINER_ASR_MODE=file",
                "SALES_TRAINER_REAL_ASR_AUDIO_URL=file:///missing/sample.wav",
            ]
        )
    )

    exit_code = main(["--env-file", str(env_path), "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is False
    assert "secret-value" not in json.dumps(payload)
    assert "dashscope-secret-value" not in json.dumps(payload)
    assert "DEUCATE_API_KEY" in payload["checked_keys"]
    assert "DASHSCOPE_API_KEY" in payload["checked_keys"]
    assert payload["env_file"] == str(env_path)
    assert payload["smoke_requested"] is False
    assert payload["smoke_ran"] is False
    assert "smoke_command" in payload


def test_should_write_safe_json_report_file(tmp_path: Path) -> None:
    report_path = tmp_path / "reports" / "sales-trainer-real-provider.json"
    payload = {
        "ready": False,
        "messages": ["DEUCATE_API_KEY is required."],
        "checked_keys": ["DEUCATE_API_KEY"],
    }

    write_json_report(report_path, payload)

    assert json.loads(report_path.read_text()) == payload


def test_should_write_json_report_from_cli(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    report_path = tmp_path / "preflight.json"
    env_path.write_text(
        "DEUCATE_API_KEY=secret-value\n"
        "DASHSCOPE_API_KEY=dashscope-secret-value\n"
    )

    exit_code = main(
        [
            "--env-file",
            str(env_path),
            "--json",
            "--json-report",
            str(report_path),
        ]
    )

    assert exit_code == 2
    payload = json.loads(report_path.read_text())
    assert payload["ready"] is False
    assert "secret-value" not in json.dumps(payload)
    assert "dashscope-secret-value" not in json.dumps(payload)
    assert payload["env_file"] == str(env_path)
    assert payload["smoke_requested"] is False
    assert payload["smoke_ran"] is False
    assert "smoke_command" in payload
