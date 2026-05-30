#!/usr/bin/env python3
"""Run Roleplay Contract deterministic evals and emit release-gate artifacts."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evaluation.services.roleplay_contract_eval import (  # noqa: E402
    RoleplayContractDeterministicEvalHarness,
    RoleplayEvalReleaseGateConfig,
    build_roleplay_eval_run_artifact,
    roleplay_eval_should_fail_release,
)

DEFAULT_FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "roleplay_contract_eval_cases.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_junit(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    deterministic = artifact.get("deterministic")
    results = deterministic.get("results", []) if isinstance(deterministic, dict) else []
    failures = [
        result
        for result in results
        if isinstance(result, dict) and not bool(result.get("passed"))
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<testsuite name="roleplay_contract_eval" tests="{len(results)}" '
            f'failures="{len(failures)}">'
        ),
    ]
    for result in results:
        if not isinstance(result, dict):
            continue
        case_id = html.escape(str(result.get("case_id") or "unknown"))
        situation_code = html.escape(str(result.get("situation_code") or "unknown"))
        lines.append(f'  <testcase classname="{situation_code}" name="{case_id}">')
        if not bool(result.get("passed")):
            expected = html.escape(str(result.get("expected_violation_code")))
            actual = html.escape(str(result.get("actual_violation_code")))
            lines.append(
                f'    <failure message="expected {expected}, got {actual}" />'
            )
        lines.append("  </testcase>")
    lines.append("</testsuite>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gate_config_from_args(args: argparse.Namespace) -> RoleplayEvalReleaseGateConfig:
    config_path = Path(args.gate_config).resolve() if args.gate_config else None
    payload = _read_json(config_path) if config_path else {}
    env_overrides = {
        "deterministic_gate_mode": os.getenv("ROLEPLAY_EVAL_DETERMINISTIC_GATE_MODE"),
        "llm_grader_mode": os.getenv("ROLEPLAY_EVAL_LLM_GRADER_MODE"),
    }
    payload.update({key: value for key, value in env_overrides.items() if value})
    if args.deterministic_gate_mode:
        payload["deterministic_gate_mode"] = args.deterministic_gate_mode
    if args.llm_grader_mode:
        payload["llm_grader_mode"] = args.llm_grader_mode
    return RoleplayEvalReleaseGateConfig.from_mapping(payload)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(DEFAULT_FIXTURE), help="Eval fixture JSON")
    parser.add_argument("--output-json", help="Path for JSON artifact")
    parser.add_argument("--output-junit", help="Path for JUnit XML artifact")
    parser.add_argument("--gate-config", help="Optional roleplay_eval_release_gate JSON")
    parser.add_argument(
        "--deterministic-gate-mode",
        choices=("blocking", "warn_only", "disabled"),
        help="Override deterministic release gate mode",
    )
    parser.add_argument(
        "--llm-grader-mode",
        choices=("blocking", "warn_only", "disabled"),
        help="Override LLM grader gate mode",
    )
    parser.add_argument(
        "--enable-llm-grader",
        action="store_true",
        help="Emit LLM grader section as not_configured/warn-only placeholder",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    cases = _read_json(Path(args.cases).resolve())
    if not isinstance(cases, list):
        raise SystemExit("--cases must contain a JSON array")
    run = RoleplayContractDeterministicEvalHarness().evaluate_cases(cases)
    artifact = build_roleplay_eval_run_artifact(
        run=run,
        gate_config=_gate_config_from_args(args),
        llm_grader_enabled=bool(args.enable_llm_grader),
    )
    if args.output_json:
        _write_json(Path(args.output_json).resolve(), artifact)
    else:
        sys.stdout.write(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    if args.output_junit:
        _write_junit(Path(args.output_junit).resolve(), artifact)
    return 1 if roleplay_eval_should_fail_release(artifact) else 0


if __name__ == "__main__":
    raise SystemExit(main())
