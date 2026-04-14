#!/usr/bin/env python3
"""Minimal executable recovery drill runner.

The runner reuses `scripts/recovery_drill_baseline.py` as the single authority for
commands, preconditions, evidence, and authority paths. It does not invent a
second runbook surface; it only renders, executes, and records the baseline
commands.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass(frozen=True)
class SyntheticDrill:
    id: str
    title: str
    checked_command: str
    authority_paths: tuple[str, ...]
    evidence: tuple[str, ...]
    why_it_matters: str
    preconditions: tuple[str, ...] = ()
    failure_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionStep:
    drill: Any
    command_template: str
    rendered_command: str
    required_env: tuple[str, ...]
    failure_signals: tuple[str, ...]
    log_path: str
    timeout_seconds: int = 900


@dataclass(frozen=True)
class StepExecutionResult:
    drill_id: str
    title: str
    command_template: str
    rendered_command: str
    status: str
    exit_code: int
    duration_ms: int
    log_path: str
    failure_signal: str
    required_env: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionResult:
    started_at: str
    completed_at: str
    repo_root: str
    evidence_root: str
    summary_path: str
    exit_code: int
    steps: list[StepExecutionResult]


_PLACEHOLDER_RE = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _load_baseline_module(repo_root: Path) -> ModuleType:
    path = repo_root / "scripts" / "recovery_drill_baseline.py"
    spec = importlib.util.spec_from_file_location("recovery_drill_baseline", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load recovery drill baseline from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expand_placeholders(command: str, env: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(2)
        return env.get(key, default or "")

    return _PLACEHOLDER_RE.sub(_replace, command)


def _ensure_evidence_root(evidence_root: Path) -> Path:
    evidence_root.mkdir(parents=True, exist_ok=True)
    return evidence_root


def _default_evidence_root(repo_root: Path) -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return repo_root / ".dev" / "recovery-drills" / ts


def build_execution_plan(
    *,
    repo_root: Path,
    evidence_root: Path,
    selected_drill_ids: list[str] | None,
    env: dict[str, str],
) -> list[ExecutionStep]:
    baseline = _load_baseline_module(repo_root)
    drill_ids = selected_drill_ids or [drill.id for drill in baseline.DRILLS]
    plan: list[ExecutionStep] = []

    for index, drill_id in enumerate(drill_ids, start=1):
        try:
            drill = baseline.DRILLS_BY_ID[drill_id]
        except KeyError as exc:
            available = ", ".join(sorted(baseline.DRILLS_BY_ID))
            raise ValueError(f"Unknown drill id: {drill_id}. Available: {available}") from exc

        rendered = _expand_placeholders(drill.checked_command, env)
        log_path = evidence_root / f"{index:02d}-{drill.id}.log"
        plan.append(
            ExecutionStep(
                drill=drill,
                command_template=drill.checked_command,
                rendered_command=rendered,
                required_env=tuple(drill.preconditions),
                failure_signals=tuple(drill.failure_signals),
                log_path=str(log_path),
            )
        )

    return plan


def _write_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _serialize_result(result: StepExecutionResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["required_env"] = list(result.required_env)
    return payload


def _write_summary(
    *,
    evidence_root: Path,
    started_at: str,
    completed_at: str,
    repo_root: Path,
    exit_code: int,
    steps: list[StepExecutionResult],
) -> Path:
    summary_path = evidence_root / "summary.json"
    payload = {
        "started_at": started_at,
        "completed_at": completed_at,
        "repo_root": str(repo_root),
        "evidence_root": str(evidence_root),
        "exit_code": exit_code,
        "steps": [_serialize_result(step) for step in steps],
    }
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary_path


def _precondition_failure(step: ExecutionStep, missing_env: list[str]) -> StepExecutionResult:
    message = (
        f"Precondition failed: missing required env vars: {', '.join(missing_env)}. "
        f"Failure signals to watch: {', '.join(step.failure_signals) or 'n/a'}."
    )
    _write_log(Path(step.log_path), message + "\n")
    return StepExecutionResult(
        drill_id=step.drill.id,
        title=step.drill.title,
        command_template=step.command_template,
        rendered_command=step.rendered_command,
        status="precondition_failed",
        exit_code=2,
        duration_ms=0,
        log_path=step.log_path,
        failure_signal=message,
        required_env=step.required_env,
    )


def _run_single_step(
    *,
    step: ExecutionStep,
    repo_root: Path,
    env: dict[str, str],
) -> StepExecutionResult:
    missing_env = [name for name in step.required_env if not env.get(name)]
    if missing_env:
        return _precondition_failure(step, missing_env)

    start = datetime.now(UTC)
    completed = start
    try:
        completed_process = subprocess.run(
            ["bash", "-lc", f"set -euo pipefail; {step.command_template}"],
            cwd=repo_root,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            timeout=step.timeout_seconds,
            check=False,
        )
        completed = datetime.now(UTC)
        duration_ms = int((completed - start).total_seconds() * 1000)
        log_text = (
            f"# command\n{step.command_template}\n\n"
            f"# rendered_command\n{step.rendered_command}\n\n"
            f"# exit_code\n{completed_process.returncode}\n\n"
            f"# stdout\n{completed_process.stdout}\n\n"
            f"# stderr\n{completed_process.stderr}\n"
        )
        _write_log(Path(step.log_path), log_text)

        if completed_process.returncode == 0:
            return StepExecutionResult(
                drill_id=step.drill.id,
                title=step.drill.title,
                command_template=step.command_template,
                rendered_command=step.rendered_command,
                status="passed",
                exit_code=0,
                duration_ms=duration_ms,
                log_path=step.log_path,
                failure_signal="",
                required_env=step.required_env,
            )

        stderr_tail = (completed_process.stderr or completed_process.stdout).strip().splitlines()
        failure_signal = stderr_tail[-1] if stderr_tail else "non-zero exit"
        return StepExecutionResult(
            drill_id=step.drill.id,
            title=step.drill.title,
            command_template=step.command_template,
            rendered_command=step.rendered_command,
            status="failed",
            exit_code=completed_process.returncode,
            duration_ms=duration_ms,
            log_path=step.log_path,
            failure_signal=failure_signal,
            required_env=step.required_env,
        )
    except subprocess.TimeoutExpired as exc:
        completed = datetime.now(UTC)
        duration_ms = int((completed - start).total_seconds() * 1000)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        _write_log(
            Path(step.log_path),
            (
                f"# command\n{step.command_template}\n\n"
                f"# rendered_command\n{step.rendered_command}\n\n"
                f"# timeout_seconds\n{step.timeout_seconds}\n\n"
                f"# stdout\n{stdout}\n\n"
                f"# stderr\n{stderr}\n"
            ),
        )
        return StepExecutionResult(
            drill_id=step.drill.id,
            title=step.drill.title,
            command_template=step.command_template,
            rendered_command=step.rendered_command,
            status="timeout",
            exit_code=124,
            duration_ms=duration_ms,
            log_path=step.log_path,
            failure_signal=f"Timed out after {step.timeout_seconds}s",
            required_env=step.required_env,
        )


def run_execution_plan(
    *,
    plan: list[ExecutionStep],
    repo_root: Path,
    evidence_root: Path,
    env: dict[str, str],
    continue_on_failure: bool,
) -> ExecutionResult:
    _ensure_evidence_root(evidence_root)
    started_at = datetime.now(UTC).isoformat()
    results: list[StepExecutionResult] = []

    for step in plan:
        result = _run_single_step(step=step, repo_root=repo_root, env=env)
        results.append(result)
        if result.status != "passed" and not continue_on_failure:
            break

    exit_code = 0 if all(step.status == "passed" for step in results) else 1
    completed_at = datetime.now(UTC).isoformat()
    summary_path = _write_summary(
        evidence_root=evidence_root,
        started_at=started_at,
        completed_at=completed_at,
        repo_root=repo_root,
        exit_code=exit_code,
        steps=results,
    )
    return ExecutionResult(
        started_at=started_at,
        completed_at=completed_at,
        repo_root=str(repo_root),
        evidence_root=str(evidence_root),
        summary_path=str(summary_path),
        exit_code=exit_code,
        steps=results,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("plan", "run"),
        default="plan",
        help="plan prints the rendered execution plan; run executes the selected drills.",
    )
    parser.add_argument(
        "--drill",
        dest="drills",
        action="append",
        default=[],
        help="Select one or more drill ids. Defaults to all baseline drills.",
    )
    parser.add_argument(
        "--evidence-root",
        default=None,
        help="Directory where per-drill logs and summary.json will be written.",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Keep running remaining drills after a failure or precondition miss.",
    )
    return parser


def _print_plan(plan: list[ExecutionStep], evidence_root: Path) -> None:
    lines = [f"evidence_root: {evidence_root}", ""]
    for step in plan:
        lines.extend(
            [
                f"[drill] {step.drill.id}",
                f"  title: {step.drill.title}",
                f"  command_template: {step.command_template}",
                f"  rendered_command: {step.rendered_command}",
                f"  required_env: {', '.join(step.required_env) if step.required_env else '(none)'}",
                f"  failure_signals: {', '.join(step.failure_signals) if step.failure_signals else '(none)'}",
                f"  log_path: {step.log_path}",
                "",
            ]
        )
    print("\n".join(lines).rstrip())


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    evidence_root = Path(args.evidence_root) if args.evidence_root else _default_evidence_root(repo_root)
    env = dict(os.environ)
    plan = build_execution_plan(
        repo_root=repo_root,
        evidence_root=evidence_root,
        selected_drill_ids=args.drills,
        env=env,
    )

    if args.mode == "plan":
        _print_plan(plan, evidence_root)
        return 0

    result = run_execution_plan(
        plan=plan,
        repo_root=repo_root,
        evidence_root=evidence_root,
        env=env,
        continue_on_failure=args.continue_on_failure,
    )
    _print_plan(plan, evidence_root)
    print("")
    print(json.dumps({
        "summary_path": result.summary_path,
        "exit_code": result.exit_code,
        "steps": [_serialize_result(step) for step in result.steps],
    }, ensure_ascii=False, indent=2))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
