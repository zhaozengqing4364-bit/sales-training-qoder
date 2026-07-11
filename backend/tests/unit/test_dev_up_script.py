import os
import shlex
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
DEV_UP_SCRIPT = ROOT_DIR / "scripts" / "dev-up.sh"
DEV_SMOKE_UP_SCRIPT = ROOT_DIR / "scripts" / "dev-smoke-up.sh"


def run_bash(script: str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT_DIR,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dev_up_can_be_sourced_without_running_main() -> None:
    result = run_bash(
        "\n".join(
            [
                "set -euo pipefail",
                "export AUTO_START_INFRA=0",
                "export PORTS_TO_CLEAN=",
                "export BACKEND_PYTHON=/bin/false",
                f"source {shlex.quote(str(DEV_UP_SCRIPT))}",
                "declare -F start_infra_services >/dev/null",
            ]
        )
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "启动 Backend" not in result.stdout


def test_dev_up_starts_linux_services_when_brew_is_unavailable(tmp_path: Path) -> None:
    calls_file = tmp_path / "calls"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    (fake_bin / "pg_lsclusters").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' 'Ver Cluster Port Status Owner Data directory Log file'",
                "printf '%s\\n' '16 main 5432 down postgres /tmp/postgres /tmp/postgres.log'",
            ]
        )
    )
    (fake_bin / "pg_ctlcluster").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf 'pg_ctlcluster %s\\n' \"$*\" >> {shlex.quote(str(calls_file))}",
            ]
        )
    )
    (fake_bin / "service").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf 'service %s\\n' \"$*\" >> {shlex.quote(str(calls_file))}",
            ]
        )
    )
    for command in ("pg_lsclusters", "pg_ctlcluster", "service"):
        (fake_bin / command).chmod(0o755)

    result = run_bash(
        "\n".join(
            [
                "set -euo pipefail",
                f"source {shlex.quote(str(DEV_UP_SCRIPT))}",
                "MANAGE_POSTGRES=1",
                "MANAGE_REDIS=1",
                "AUTO_START_INFRA=1",
                "POSTGRES_PORT=5432",
                "REDIS_PORT=6379",
                "is_port_busy() { return 1; }",
                "wait_for_port() { return 0; }",
                "start_infra_services",
                f"cat {shlex.quote(str(calls_file))}",
            ]
        ),
        env={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "pg_ctlcluster 16 main start" in result.stdout
    assert "service redis-server start" in result.stdout


def test_dev_up_detects_listening_port_without_visible_pid(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "ss").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' 'LISTEN 0 200 127.0.0.1:5432 0.0.0.0:*'",
            ]
        )
    )
    (fake_bin / "ss").chmod(0o755)

    result = run_bash(
        "\n".join(
            [
                "set -euo pipefail",
                f"source {shlex.quote(str(DEV_UP_SCRIPT))}",
                "lsof() { return 1; }",
                "fuser() { return 1; }",
                "is_port_busy 5432",
            ]
        ),
        env={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
    )

    assert result.returncode == 0, result.stderr + result.stdout


def test_dev_up_binds_backend_to_all_interfaces_by_default(tmp_path: Path) -> None:
    calls_file = tmp_path / "backend-args"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" > {shlex.quote(str(calls_file))}",
            ]
        )
    )
    fake_python.chmod(0o755)

    result = run_bash(
        "\n".join(
            [
                "set -euo pipefail",
                "unset BACKEND_HOST",
                f"source {shlex.quote(str(DEV_UP_SCRIPT))}",
                f"resolve_python_bin() {{ printf '%s\\n' {shlex.quote(str(fake_python))}; }}",
                "wait_for_port() { return 0; }",
                "wait_for_http_ok() { return 0; }",
                "mkdir -p \"${LOG_DIR}\" \"${PID_DIR}\"",
                "EFFECTIVE_DATABASE_URL=postgresql+asyncpg://dev:dev@127.0.0.1:5432/sales_training",
                "EFFECTIVE_REDIS_URL=redis://127.0.0.1:6379/0",
                "LOG_LEVEL=ERROR",
                "start_backend",
                "for _ in $(seq 1 20); do [[ -f " + shlex.quote(str(calls_file)) + " ]] && break; sleep 0.1; done",
                "cat " + shlex.quote(str(calls_file)),
            ]
        )
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "--host 0.0.0.0" in result.stdout


def test_dev_smoke_up_resets_generated_frontend_dev_state_before_start(
    tmp_path: Path,
) -> None:
    sourceable_script = tmp_path / "dev-smoke-up-sourceable.sh"
    sourceable_script.write_text(
        DEV_SMOKE_UP_SCRIPT.read_text().replace('\nmain "$@"\n', "\n")
    )

    result = run_bash(
        "\n".join(
            [
                "set -euo pipefail",
                f"source {shlex.quote(str(sourceable_script))}",
                f"ROOT_DIR={shlex.quote(str(ROOT_DIR))}",
                "rm() { printf 'rm %s\\n' \"$*\"; }",
                "bash() { printf 'bash %s api=%s ws=%s\\n' \"$*\" \"${NEXT_PUBLIC_API_URL:-}\" \"${NEXT_PUBLIC_WS_URL:-}\"; }",
                "start_local_stack",
            ]
        )
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.splitlines() == [
        f"rm -rf {ROOT_DIR / 'web' / '.next' / 'dev'}",
        (
            f"bash {ROOT_DIR / 'scripts' / 'dev-up.sh'} "
            "api=http://localhost:3444/api/v1 ws=ws://localhost:3444"
        ),
    ]
