from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_SCRIPT = REPO_ROOT / "scripts" / "frontend-runtime.sh"
APP_UP_SCRIPT = REPO_ROOT / "scripts" / "app-up.sh"
DEV_UP_SCRIPT = REPO_ROOT / "scripts" / "dev-up.sh"


def _fake_npm_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    call_log = tmp_path / "npm-calls.log"
    fake_npm = tmp_path / "npm"
    fake_npm.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%s\\n\' "$*" >> "$NPM_CALL_LOG"\n',
        encoding="utf-8",
    )
    fake_npm.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{tmp_path}:{environment['PATH']}",
            "NPM_CALL_LOG": str(call_log),
        }
    )
    return environment, call_log


def _run_runtime(tmp_path: Path, mode: str) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    environment, call_log = _fake_npm_environment(tmp_path)
    environment.update({"FRONTEND_MODE": mode, "FRONTEND_PORT": "4555"})
    result = subprocess.run(
        ["/bin/bash", str(RUNTIME_SCRIPT)],
        cwd=REPO_ROOT / "web",
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    calls = call_log.read_text(encoding="utf-8").splitlines() if call_log.exists() else []
    return result, calls


def test_should_build_then_start_next_in_production_mode(tmp_path: Path) -> None:
    result, calls = _run_runtime(tmp_path, "production")

    assert result.returncode == 0, result.stderr
    assert calls == ["run build", "exec -- next start -p 4555"]


def test_should_keep_hot_reload_in_development_mode(tmp_path: Path) -> None:
    result, calls = _run_runtime(tmp_path, "development")

    assert result.returncode == 0, result.stderr
    assert calls == ["exec -- next dev -p 4555"]


def test_should_clear_next_dev_cache_before_development_server(tmp_path: Path) -> None:
    web_dir = tmp_path / "web"
    stale_marker = web_dir / ".next" / "dev" / "stale"
    stale_marker.parent.mkdir(parents=True)
    stale_marker.write_text("stale", encoding="utf-8")
    production_artifact = web_dir / ".next" / "BUILD_ID"
    production_artifact.write_text("keep-me", encoding="utf-8")

    environment, call_log = _fake_npm_environment(tmp_path)
    environment.update({"FRONTEND_MODE": "development", "FRONTEND_PORT": "4555"})
    result = subprocess.run(
        ["/bin/bash", str(RUNTIME_SCRIPT)],
        cwd=web_dir,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    calls = call_log.read_text(encoding="utf-8").splitlines() if call_log.exists() else []

    assert result.returncode == 0, result.stderr
    assert calls == ["exec -- next dev -p 4555"]
    assert not (web_dir / ".next" / "dev").exists()
    assert production_artifact.read_text(encoding="utf-8") == "keep-me"


def test_should_clear_full_next_cache_when_next_clean_cache_enabled(
    tmp_path: Path,
) -> None:
    web_dir = tmp_path / "web"
    stale_marker = web_dir / ".next" / "dev" / "stale"
    stale_marker.parent.mkdir(parents=True)
    stale_marker.write_text("stale", encoding="utf-8")

    environment, call_log = _fake_npm_environment(tmp_path)
    environment.update(
        {
            "FRONTEND_MODE": "development",
            "FRONTEND_PORT": "4555",
            "NEXT_CLEAN_CACHE": "1",
        }
    )
    result = subprocess.run(
        ["/bin/bash", str(RUNTIME_SCRIPT)],
        cwd=web_dir,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    calls = call_log.read_text(encoding="utf-8").splitlines() if call_log.exists() else []

    assert result.returncode == 0, result.stderr
    assert calls == ["exec -- next dev -p 4555"]
    assert not (web_dir / ".next").exists()


def test_should_reject_unknown_frontend_mode(tmp_path: Path) -> None:
    result, calls = _run_runtime(tmp_path, "turbo-magic")

    assert result.returncode != 0
    assert calls == []
    assert "FRONTEND_MODE" in result.stderr


def test_should_delegate_app_start_to_production_frontend_mode(tmp_path: Path) -> None:
    call_log = tmp_path / "bash-calls.log"
    fake_bash = tmp_path / "bash"
    fake_bash.write_text(
        "#!/bin/sh\n"
        'printf \'%s|%s\\n\' "$FRONTEND_MODE" "$*" > "$BASH_CALL_LOG"\n',
        encoding="utf-8",
    )
    fake_bash.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{tmp_path}:{environment['PATH']}",
            "BASH_CALL_LOG": str(call_log),
        }
    )

    result = subprocess.run(
        ["/bin/bash", str(APP_UP_SCRIPT)],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert call_log.read_text(encoding="utf-8").strip() == (
        f"production|{REPO_ROOT / 'scripts' / 'dev-up.sh'}"
    )


def test_should_delegate_dev_up_frontend_process_to_runtime_script() -> None:
    script = DEV_UP_SCRIPT.read_text(encoding="utf-8")

    assert 'FRONTEND_MODE="${FRONTEND_MODE:-development}"' in script
    assert '"${ROOT_DIR}/scripts/frontend-runtime.sh"' in script
    assert "npm exec -- next dev" not in script
    assert 'rm -rf "${ROOT_DIR}/web/.next/dev"' in script
    assert "疑似陈旧 web/.next/dev 缓存" in script
