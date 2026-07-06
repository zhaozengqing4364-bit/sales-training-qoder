from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check_stepfun_realtime_prereqs.py"


def run_preflight(env_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--env-file", str(env_file)],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_stepfun_realtime_preflight_redacts_configured_key(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "STEPFUN_API_KEY=secret-stepfun-key",
                "STEPFUN_REALTIME_URL=wss://api.stepfun.com/v1/realtime",
                "STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime",
            ]
        ),
        encoding="utf-8",
    )

    result = run_preflight(env_file)
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["status"] == "ready"
    assert payload["api_key_configured"] is True
    assert payload["api_key_redacted"] == "<configured>"
    assert "secret-stepfun-key" not in result.stdout
    assert payload["endpoint_without_secret"] == (
        "wss://api.stepfun.com/v1/realtime?model=stepaudio-2.5-realtime"
    )
    assert payload["model_in_local_allowlist"] is True
    assert payload["model_in_public_realtime_docs"] is True
    assert payload["warnings"] == []


def test_stepfun_realtime_preflight_can_fail_on_public_model_warning(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "STEPFUN_API_KEY=secret-stepfun-key",
                "STEPFUN_REALTIME_URL=wss://api.stepfun.com/v1/realtime",
                "STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime-beta",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--env-file",
            str(env_file),
            "--fail-on-warnings",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 3
    assert payload["status"] == "ready"
    assert payload["model_in_local_allowlist"] is False
    assert payload["model_in_public_realtime_docs"] is False
    assert "secret-stepfun-key" not in result.stdout
    assert (
        "model_not_in_public_realtime_docs_confirm_console_authorization"
        in payload["warnings"]
    )
    assert "model_not_in_local_allowlist_confirm_runtime_policy" in payload["warnings"]


def test_stepfun_realtime_preflight_blocks_placeholder_key(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "STEPFUN_API_KEY=phase4-local-e2e",
                "STEPFUN_REALTIME_URL=wss://api.stepfun.com/step_plan/v1/realtime",
                "STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime",
            ]
        ),
        encoding="utf-8",
    )

    result = run_preflight(env_file)
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["status"] == "blocked"
    assert payload["api_key_configured"] is False
    assert payload["step_plan_url"] is True
    assert "stepfun_api_key_missing_or_placeholder" in payload["errors"]
    assert "phase4-local-e2e" not in result.stdout


def test_stepfun_realtime_preflight_blocks_url_userinfo_without_leaking_secret(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "STEPFUN_API_KEY=secret-stepfun-key",
                "STEPFUN_REALTIME_URL=wss://user:secret-pass@api.stepfun.com/v1/realtime",
                "STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime",
            ]
        ),
        encoding="utf-8",
    )

    result = run_preflight(env_file)
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["status"] == "blocked"
    assert "stepfun_realtime_url_must_not_include_userinfo" in payload["errors"]
    assert payload["realtime_url"] == "wss://api.stepfun.com/v1/realtime"
    assert payload["endpoint_without_secret"] == (
        "wss://api.stepfun.com/v1/realtime?model=stepaudio-2.5-realtime"
    )
    assert "secret-stepfun-key" not in result.stdout
    assert "secret-pass" not in result.stdout


def test_stepfun_realtime_preflight_blocks_sensitive_url_query_without_leaking_secret(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "STEPFUN_API_KEY=secret-stepfun-key",
                "STEPFUN_REALTIME_URL=wss://api.stepfun.com/v1/realtime?api_key=query-secret&region=cn&model=old",
                "STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime",
            ]
        ),
        encoding="utf-8",
    )

    result = run_preflight(env_file)
    payload = json.loads(result.stdout)

    assert result.returncode == 2
    assert payload["status"] == "blocked"
    assert "stepfun_realtime_url_must_not_include_sensitive_query" in payload["errors"]
    assert payload["realtime_url"] == "wss://api.stepfun.com/v1/realtime?region=cn"
    assert payload["endpoint_without_secret"] == (
        "wss://api.stepfun.com/v1/realtime?region=cn&model=stepaudio-2.5-realtime"
    )
    assert "secret-stepfun-key" not in result.stdout
    assert "query-secret" not in result.stdout


def test_stepfun_realtime_preflight_accepts_env_example_inline_comments(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "STEPFUN_API_KEY=secret-stepfun-key",
                "STEPFUN_REALTIME_URL=wss://api.stepfun.com/v1/realtime # default endpoint",
                "STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime  # default model",
            ]
        ),
        encoding="utf-8",
    )

    result = run_preflight(env_file)
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["status"] == "ready"
    assert payload["model"] == "stepaudio-2.5-realtime"
    assert payload["realtime_url"] == "wss://api.stepfun.com/v1/realtime"
    assert "secret-stepfun-key" not in result.stdout
