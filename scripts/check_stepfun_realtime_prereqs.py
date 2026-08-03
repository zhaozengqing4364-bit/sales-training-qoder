#!/usr/bin/env python3
"""Preflight StepFun realtime env without printing secrets or opening a socket."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_REALTIME_URL = "wss://api.stepfun.com/v1/realtime"
DEFAULT_REALTIME_MODEL = "stepaudio-2.5-realtime"
PLACEHOLDER_KEYS = {
    "",
    "phase4-local-e2e",
    "replace-with-stepfun-api-key",
}
PUBLIC_REALTIME_MODELS = {
    "stepaudio-2.5-realtime",
    "step-1o-audio",
    "step-audio-2",
    "step-audio-2-mini",
    "step-audio-r1.1",
}
LOCAL_ALLOWED_REALTIME_MODELS = PUBLIC_REALTIME_MODELS
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "client_secret",
    "key",
    "secret",
    "sig",
    "signature",
    "token",
}


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = normalize_env_value(value)
    return values


def normalize_env_value(value: str) -> str:
    """Strip shell-style inline comments while preserving quoted values."""

    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    for marker in (" #", "\t#"):
        index = text.find(marker)
        if index >= 0:
            text = text[:index].rstrip()
            break
    return text.strip().strip('"').strip("'")


def effective_env(env_file: Path | None) -> dict[str, str]:
    merged = dict(os.environ)
    if env_file is not None:
        merged.update(load_env_file(env_file))
    return merged


def sanitized_netloc(parsed: SplitResult) -> str:
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port is not None:
        return f"{host}:{parsed.port}"
    return host


def safe_query_pairs(query: str) -> tuple[list[tuple[str, str]], bool]:
    sensitive_found = False
    pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        normalized = key.lower()
        if normalized == "model":
            continue
        if normalized in SENSITIVE_QUERY_KEYS:
            sensitive_found = True
            continue
        pairs.append((key, value))
    return pairs, sensitive_found


def build_endpoint(url: str, *, model: str) -> str:
    parsed = urlsplit(url)
    query_pairs, _ = safe_query_pairs(parsed.query)
    query_pairs.append(("model", model))
    return urlunsplit(
        (
            parsed.scheme,
            sanitized_netloc(parsed),
            parsed.path,
            urlencode(query_pairs),
            "",
        )
    )


def sanitize_url_for_report(url: str) -> str:
    parsed = urlsplit(url)
    query_pairs, _ = safe_query_pairs(parsed.query)
    return urlunsplit(
        (
            parsed.scheme,
            sanitized_netloc(parsed),
            parsed.path,
            urlencode(query_pairs),
            "",
        )
    )


def build_report(env: dict[str, str]) -> dict[str, object]:
    api_key = env.get("STEPFUN_API_KEY", "")
    model = env.get("STEPFUN_REALTIME_MODEL") or DEFAULT_REALTIME_MODEL
    url = env.get("STEPFUN_REALTIME_URL") or DEFAULT_REALTIME_URL
    endpoint = build_endpoint(url, model=model)
    parsed = urlsplit(url)
    _, sensitive_query_found = safe_query_pairs(parsed.query)

    errors: list[str] = []
    warnings: list[str] = []
    if api_key in PLACEHOLDER_KEYS:
        errors.append("stepfun_api_key_missing_or_placeholder")
    if parsed.scheme != "wss":
        errors.append("stepfun_realtime_url_must_use_wss")
    if not parsed.netloc:
        errors.append("stepfun_realtime_url_missing_host")
    if parsed.username or parsed.password:
        errors.append("stepfun_realtime_url_must_not_include_userinfo")
    if sensitive_query_found:
        errors.append("stepfun_realtime_url_must_not_include_sensitive_query")
    if model not in PUBLIC_REALTIME_MODELS:
        warnings.append(
            "model_not_in_public_realtime_docs_confirm_console_authorization"
        )
    if model not in LOCAL_ALLOWED_REALTIME_MODELS:
        warnings.append("model_not_in_local_allowlist_confirm_runtime_policy")

    return {
        "status": "blocked" if errors else "ready",
        "errors": errors,
        "warnings": warnings,
        "api_key_configured": api_key not in PLACEHOLDER_KEYS,
        "api_key_redacted": "<configured>"
        if api_key not in PLACEHOLDER_KEYS
        else "<missing>",
        "realtime_url_configured": bool(env.get("STEPFUN_REALTIME_URL")),
        "realtime_url": sanitize_url_for_report(url),
        "step_plan_url": parsed.path.startswith("/step_plan/"),
        "model": model,
        "model_in_local_allowlist": model in LOCAL_ALLOWED_REALTIME_MODELS,
        "model_in_public_realtime_docs": model in PUBLIC_REALTIME_MODELS,
        "endpoint_without_secret": endpoint,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check StepFun realtime env prerequisites without network access.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional env file, for example backend/.env. Values override process env.",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit non-zero when public-doc model warnings are present.",
    )
    args = parser.parse_args(argv)

    report = build_report(effective_env(args.env_file))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        return 2
    if args.fail_on_warnings and report["warnings"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
