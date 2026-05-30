#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

TRUTHY_VALUES = {"1", "true", "yes"}
REQUIRED_ENV_VARS = (
    "SALES_TRAINER_RUN_REAL_PROVIDER_TESTS",
    "DEUCATE_BASE_URL",
    "DEUCATE_API_KEY",
    "DASHSCOPE_API_KEY",
    "SALES_TRAINER_ASR_MODE",
    "SALES_TRAINER_REAL_ASR_AUDIO_URL",
)
SMOKE_TEST_PATH = "tests/integration/test_sales_trainer_real_providers.py"
DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True)
class PreflightResult:
    ready: bool
    messages: list[str]
    checked_keys: list[str]

    def to_safe_dict(
        self,
        *,
        generated_at: datetime | None = None,
        env_file: Path | None = None,
        smoke_requested: bool = False,
        smoke_exit_code: int | None = None,
        smoke_command: Sequence[str] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "ready": self.ready,
            "messages": self.messages,
            "checked_keys": self.checked_keys,
            "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
            "env_file": str(env_file) if env_file is not None else None,
            "smoke_requested": smoke_requested,
            "smoke_ran": smoke_exit_code is not None,
        }
        if smoke_command is not None:
            payload["smoke_command"] = list(smoke_command)
        if smoke_exit_code is not None:
            payload["smoke_exit_code"] = smoke_exit_code
        return payload


def check_real_provider_config(
    env: dict[str, str] | None = None,
    *,
    env_file: Path | None = DEFAULT_ENV_FILE,
) -> PreflightResult:
    values = resolve_config_values(env=env, env_file=env_file)
    messages: list[str] = []

    enabled = values.get("SALES_TRAINER_RUN_REAL_PROVIDER_TESTS", "").lower()
    if enabled not in TRUTHY_VALUES:
        messages.append(
            "SALES_TRAINER_RUN_REAL_PROVIDER_TESTS must be set to 1/true/yes."
        )

    for key in ("DEUCATE_BASE_URL", "DEUCATE_API_KEY", "DASHSCOPE_API_KEY"):
        if _is_missing_or_placeholder(values.get(key, "")):
            messages.append(f"{key} is required.")

    if values.get("SALES_TRAINER_ASR_MODE", "").lower() != "file":
        messages.append("SALES_TRAINER_ASR_MODE must be set to file.")

    audio_url = values.get("SALES_TRAINER_REAL_ASR_AUDIO_URL", "")
    if not audio_url:
        messages.append("SALES_TRAINER_REAL_ASR_AUDIO_URL is required.")
    elif not _is_http_url(audio_url):
        messages.append("SALES_TRAINER_REAL_ASR_AUDIO_URL must be an HTTP/HTTPS URL.")

    return PreflightResult(
        ready=not messages,
        messages=messages,
        checked_keys=list(REQUIRED_ENV_VARS),
    )


def resolve_config_values(
    *,
    env: dict[str, str] | None = None,
    env_file: Path | None = DEFAULT_ENV_FILE,
) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file is not None and env_file.is_file():
        values.update(
            {
                key: value
                for key, value in dotenv_values(env_file).items()
                if value is not None
            }
        )
    values.update(dict(os.environ if env is None else env))
    return values


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_missing_or_placeholder(value: str) -> bool:
    stripped = value.strip()
    return not stripped or stripped.startswith("replace-with-")


def smoke_test_command(python_executable: str = sys.executable) -> list[str]:
    return [
        python_executable,
        "-m",
        "pytest",
        SMOKE_TEST_PATH,
        "--no-cov",
    ]


def run_smoke_tests(
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[object]],
) -> int:
    completed = runner(smoke_test_command())
    return completed.returncode


def write_json_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify sales trainer real Deucate/ASR smoke test config."
    )
    parser.add_argument(
        "--run-smoke",
        action="store_true",
        help="Run the real provider smoke tests after config preflight passes.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Path to the deployment .env file used for preflight values.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a safe machine-readable preflight result without secret values.",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        help="Write a safe machine-readable preflight/smoke result to this path.",
    )
    args = parser.parse_args(argv)

    result = check_real_provider_config(env_file=args.env_file)
    smoke_command = smoke_test_command()
    smoke_exit_code: int | None = None
    if result.ready:
        if not args.json:
            print("Sales trainer real provider config is ready.")
            command = " ".join(smoke_command)
            print(f"Run: {command}")
        if args.run_smoke:
            smoke_exit_code = run_smoke_tests(subprocess.run)
        exit_code = smoke_exit_code if smoke_exit_code is not None else 0
    else:
        exit_code = 2

    safe_payload = result.to_safe_dict(
        env_file=args.env_file,
        smoke_requested=args.run_smoke,
        smoke_command=smoke_command,
        smoke_exit_code=smoke_exit_code,
    )
    if args.json:
        print(json.dumps(safe_payload, ensure_ascii=False, sort_keys=True))
    if args.json_report is not None:
        write_json_report(args.json_report, safe_payload)

    if not result.ready and not args.json:
        print("Sales trainer real provider config is incomplete.")
        for message in result.messages:
            print(f"- {message}")
        print("No secret values were printed.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
