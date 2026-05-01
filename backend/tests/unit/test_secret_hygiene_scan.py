import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_secret_hygiene.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("check_secret_hygiene", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_secret_scan_detects_realistic_secret_and_ignores_placeholder():
    module = _load_script_module()

    findings = module.scan_text(
        Path("fixture.env"),
        "OPENAI_API_KEY=sk-1234567890abcdef1234567890\n"
        "STEPFUN_API_KEY=<STEPFUN_API_KEY>\n",
    )

    assert [finding.pattern_name for finding in findings] == ["openai-style-key"]


def test_secret_scan_passes_current_release_facing_files():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Secret hygiene scan passed" in result.stdout
