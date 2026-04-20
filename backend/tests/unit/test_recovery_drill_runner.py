"""Focused proof for the recovery drill runner script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT_DIR / "scripts" / "recovery_drill_runner.py"
BASELINE_PATH = ROOT_DIR / "scripts" / "recovery_drill_baseline.py"


def _load_module(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, f"Missing script: {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_builds_auth_and_health_steps_from_baseline_command_templates(tmp_path: Path) -> None:
    baseline = _load_module(BASELINE_PATH, "recovery_drill_baseline")
    module = _load_module(SCRIPT_PATH, "recovery_drill_runner")

    plan = module.build_execution_plan(
        repo_root=ROOT_DIR,
        evidence_root=tmp_path,
        selected_drill_ids=["auth_bootstrap", "health_check"],
        env={
            "RECOVERY_ADMIN_EMAIL": "admin@example.com",
            "RECOVERY_ADMIN_NAME": "恢复管理员",
            "RECOVERY_ADMIN_ROLE": "support",
            "RECOVERY_HEALTH_URL": "http://127.0.0.1:6553/health",
        },
    )

    auth_step = next(step for step in plan if step.drill.id == "auth_bootstrap")
    health_step = next(step for step in plan if step.drill.id == "health_check")
    baseline_auth = next(drill for drill in baseline.DRILLS if drill.id == "auth_bootstrap")

    assert auth_step.command_template == baseline_auth.checked_command
    assert auth_step.required_env == ("RECOVERY_ADMIN_EMAIL", "RECOVERY_ADMIN_NAME")
    assert "admin@example.com" in auth_step.rendered_command
    assert "恢复管理员" in auth_step.rendered_command
    assert "support" in auth_step.rendered_command
    assert health_step.required_env == ()
    assert health_step.rendered_command.endswith('/health"')


def test_runner_records_precondition_failures_without_invoking_missing_secret_drill(tmp_path: Path) -> None:
    module = _load_module(SCRIPT_PATH, "recovery_drill_runner")

    plan = module.build_execution_plan(
        repo_root=ROOT_DIR,
        evidence_root=tmp_path,
        selected_drill_ids=["auth_bootstrap"],
        env={},
    )

    result = module.run_execution_plan(
        plan=plan,
        repo_root=ROOT_DIR,
        evidence_root=tmp_path,
        env={},
        continue_on_failure=True,
    )

    auth_result = result.steps[0]
    assert result.exit_code == 1
    assert auth_result.status == "precondition_failed"
    assert auth_result.exit_code == 2
    assert "RECOVERY_ADMIN_EMAIL" in auth_result.failure_signal
    assert Path(auth_result.log_path).exists()
    assert Path(result.summary_path).exists()


def test_runner_persists_command_logs_and_summary_for_success_and_failure(tmp_path: Path) -> None:
    module = _load_module(SCRIPT_PATH, "recovery_drill_runner")

    plan = [
        module.ExecutionStep(
            drill=module.SyntheticDrill(
                id="success_probe",
                title="success",
                checked_command="python3 -c \"print('success-probe')\"",
                authority_paths=("scripts/recovery_drill_runner.py",),
                evidence=("stdout",),
                why_it_matters="proof",
            ),
            command_template="python3 -c \"print('success-probe')\"",
            rendered_command="python3 -c \"print('success-probe')\"",
            required_env=(),
            failure_signals=("non-zero exit",),
            log_path=str(tmp_path / "success.log"),
        ),
        module.ExecutionStep(
            drill=module.SyntheticDrill(
                id="failure_probe",
                title="failure",
                checked_command="python3 -c \"import sys; print('boom', file=sys.stderr); sys.exit(7)\"",
                authority_paths=("scripts/recovery_drill_runner.py",),
                evidence=("stderr",),
                why_it_matters="proof",
            ),
            command_template="python3 -c \"import sys; print('boom', file=sys.stderr); sys.exit(7)\"",
            rendered_command="python3 -c \"import sys; print('boom', file=sys.stderr); sys.exit(7)\"",
            required_env=(),
            failure_signals=("stderr tail",),
            log_path=str(tmp_path / "failure.log"),
        ),
    ]

    result = module.run_execution_plan(
        plan=plan,
        repo_root=ROOT_DIR,
        evidence_root=tmp_path,
        env={},
        continue_on_failure=True,
    )

    assert result.exit_code == 1
    assert [step.status for step in result.steps] == ["passed", "failed"]
    assert "success-probe" in Path(result.steps[0].log_path).read_text(encoding="utf-8")
    failure_log = Path(result.steps[1].log_path).read_text(encoding="utf-8")
    assert "boom" in failure_log
    summary_text = Path(result.summary_path).read_text(encoding="utf-8")
    assert '"failure_probe"' in summary_text
    assert '"status": "failed"' in summary_text
