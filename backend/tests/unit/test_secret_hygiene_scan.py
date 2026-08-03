import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_secret_hygiene.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("check_secret_hygiene", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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


def test_secret_scan_detects_stepfun_key_even_when_line_mentions_example():
    module = _load_script_module()

    findings = module.scan_text(
        Path("fixture.env"),
        "# example env copied from incident notes\n"
        "STEPFUN_API_KEY=stpf_live_1234567890abcdef1234567890 # example only\n"
        "STEPFUN_API_KEY=<STEPFUN_API_KEY>\n",
    )

    assert [finding.pattern_name for finding in findings] == [
        "stepfun-api-key-assignment"
    ]


def test_secret_scan_detects_bearer_jwt_and_url_query_token():
    module = _load_script_module()

    findings = module.scan_text(
        Path("fixture.md"),
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0.signatureValue123\n"
        "wss://api.example.com/v1/realtime?token=tok_live_1234567890abcdef\n"
        "Authorization: Bearer <token>\n"
        "wss://api.example.com/v1/realtime?token={jwt_token}\n",
    )

    pattern_names = {finding.pattern_name for finding in findings}
    assert "bearer-token" in pattern_names
    assert "jwt-token" in pattern_names
    assert "url-query-token" in pattern_names


def test_secret_scan_detects_token_inside_playwright_trace_archive(tmp_path):
    module = _load_script_module()
    archive_path = tmp_path / "trace.zip"
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSJ9.signatureValue123"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("trace.network", f"Authorization: Bearer {token}\n")

    findings = module.scan_paths(tmp_path, ("trace.zip",))

    assert {finding.pattern_name for finding in findings} >= {
        "bearer-token",
        "jwt-token",
    }
    assert "trace.zip::trace.network" in str(findings[0].path)


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


def test_secret_scan_passes_stepfun_realtime_contract_and_migrations():
    migration_paths = [
        "backend/alembic/archive/prelaunch_20260715/versions/"
        "20260702_1100_088_stepfun_default_model_stepaudio25.py",
        "backend/alembic/archive/prelaunch_20260715/versions/"
        "20260702_1530_089_sales_trainer_roleplay_observations.py",
        "backend/alembic/versions/20260715_0000_001_launch_baseline.py",
    ]
    assert all((REPO_ROOT / path).is_file() for path in migration_paths)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "docs/api-contract/sales-trainer.md",
            "docs/api-contract/voice-runtime.md",
            "docs/adr/2026-06-27-newcomer-training-closed-loop.md",
            "docs/adr/2026-07-02-roleplay-observation-sidecar.md",
            *migration_paths,
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Secret hygiene scan passed" in result.stdout


def test_secret_scan_default_paths_cover_runtime_evidence_and_skip_report(tmp_path):
    module = _load_script_module()
    evidence_dir = tmp_path / ".sisyphus" / "evidence"
    evidence_dir.mkdir(parents=True)
    runtime_evidence = evidence_dir / "newcomer-real-provider-gate.json"
    runtime_evidence.write_text('{"provider": "synthetic"}\n', encoding="utf-8")
    generated_report = evidence_dir / "secret-scan-report.json"
    generated_report.write_text('{"findings": []}\n', encoding="utf-8")

    assert ".sisyphus/evidence" in module.DEFAULT_PATHS
    files = module.iter_files(tmp_path, module.DEFAULT_PATHS)

    assert runtime_evidence in files
    assert generated_report not in files


def test_secret_scan_skips_generated_report_names_to_prevent_recursive_pollution(
    tmp_path,
):
    module = _load_script_module()
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "sales_qoder_secret_scan_after.json").write_text(
        "SECRET_KEY=synthetic-report-value-1234567890\n",
        encoding="utf-8",
    )
    (evidence_dir / "release-note.txt").write_text(
        "no secrets here\n",
        encoding="utf-8",
    )

    files = module.iter_files(tmp_path, ("evidence",))

    assert [path.name for path in files] == ["release-note.txt"]


def test_secret_scan_excludes_explicit_report_path_from_scan(tmp_path):
    report_path = tmp_path / "custom-report.json"
    report_path.write_text(
        "SECRET_KEY=synthetic-report-value-1234567890\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--report",
            str(report_path),
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stderr
    assert report["passed"] is True


def test_secret_scan_writes_report_for_failure(tmp_path):
    report_path = tmp_path / "secret-report.json"
    fixture_path = tmp_path / "fixture.env"
    fixture_path.write_text(
        "SECRET_KEY=super-realistic-secret-value-123456\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--report",
            str(report_path),
            str(fixture_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result.returncode == 1
    assert report["passed"] is False
    assert report["findings"][0]["pattern_name"] == "jwt-secret-assignment"
    assert "super-realistic-secret-value-123456" not in result.stderr
    assert "super-realistic-secret-value-123456" not in json.dumps(report)
    assert "***" in report["findings"][0]["excerpt"]
