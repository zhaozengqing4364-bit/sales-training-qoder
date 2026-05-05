"""
NFR CI/CD Integration Tests

Tests the CI/CD workflow integration for NFR performance validation.
Ensures that the automated test runner and report generation work correctly.

Constitution Principle II: Real-Time Priority - <300ms end-to-end latency
Constitution Principle VII: Observability - Structured logging with trace_id
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
NFR_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "nfr-performance-check.yml"


class TestNFRCIWorkflow:
    """Test NFR CI/CD workflow integration."""

    def test_ci_workflow_file_exists(self) -> None:
        """
        NFR-CI.1: CI workflow file exists

        Verify that the GitHub Actions workflow file for NFR
        validation exists and contains required jobs.
        """
        workflow_path = NFR_WORKFLOW_PATH

        assert workflow_path.exists(), f"CI workflow file not found: {workflow_path}"

        workflow_content = workflow_path.read_text()

        # Check for required sections
        assert "nfr-performance-validation" in workflow_content
        assert "load-testing" in workflow_content
        assert "Run NFR performance tests" in workflow_content

        # Threshold values are centralized in NFRReporter instead of duplicated
        # as workflow literals.
        assert "NFRReporter" in workflow_content
        assert "failed_metrics" in workflow_content

    def test_ci_workflow_uses_real_nfr_results_instead_of_report_existence(self) -> None:
        """NFR gate must fail on failed metrics, not on synthetic report presence."""
        workflow_path = (
            NFR_WORKFLOW_PATH
        )
        workflow_content = workflow_path.read_text()

        assert "failed_metrics = int(summary.get('failed_metrics') or 0)" in workflow_content
        assert "if failed_metrics:" in workflow_content
        assert "sys.exit(1)" in workflow_content
        assert "All performance thresholds validated" not in workflow_content
        assert "'targets': {" not in workflow_content
        assert "skip_classification" in workflow_content
        assert "provider_unavailable" in workflow_content
        assert "infra_missing" in workflow_content

    def test_nfr_reporter_module_exists(self) -> None:
        """
        NFR-CI.2: NFR reporter module exists

        Verify that the NFR report generator module is available
        and can be imported.
        """
        # Should be able to import
        from common.monitoring.nfr_reporter import NFRReporter, create_nfr_report

        # Check module has required classes/functions
        assert NFRReporter is not None
        assert create_nfr_report is not None

        reporter = NFRReporter()

        # Check module has required methods
        assert hasattr(reporter, "add_result")
        assert hasattr(reporter, "generate_json")
        assert hasattr(reporter, "generate_markdown")
        assert hasattr(reporter, "generate_html")
        assert hasattr(reporter, "generate_all_reports")

    def test_nfr_runner_script_exists(self) -> None:
        """
        NFR-CI.3: NFR test runner script exists

        Verify that the bash script for running NFR tests
        exists and is executable.
        """
        runner_path = BACKEND_ROOT / "tests" / "scripts" / "run_nfr_tests.sh"

        assert runner_path.exists(), f"NFR runner script not found: {runner_path}"

        # Check script is executable
        # Note: This check may fail on Windows
        import os
        if os.name != "nt":
            assert os.access(runner_path, os.X_OK), "NFR runner script is not executable"

    def test_nfr_runner_does_not_swallow_pytest_failures(self) -> None:
        """Runner modes must propagate pytest nonzero exits."""
        runner_path = BACKEND_ROOT / "tests" / "scripts" / "run_nfr_tests.sh"
        content = runner_path.read_text()

        assert "|| true" not in content
        assert "--no-cov -q" in content

    def test_nfr_threshold_definitions(self) -> None:
        """
        NFR-CI.4: NFR thresholds are correctly defined

        Verify that all NFR thresholds from Constitution Principle II
        are defined in the reporter module.
        """
        from common.monitoring.nfr_reporter import NFRReporter

        # Expected thresholds from NFR requirements
        expected_metrics = [
            "end_to_end_latency",
            "websocket_connection",
            "asr_streaming_latency",
            "asr_first_result",
            "tts_first_byte_latency",
            "tts_total_synthesis",
            "interrupt_detection",
            "session_creation",
        ]

        # Check all expected metrics are defined
        defined_metrics = [t.metric_name for t in NFRReporter.THRESHOLDS]

        for expected in expected_metrics:
            assert (
                expected in defined_metrics
            ), f"Expected metric {expected} not found in NFR thresholds"

        # Check thresholds have target values
        for threshold in NFRReporter.THRESHOLDS:
            assert threshold.p95_target_ms > 0, f"Invalid P95 target for {threshold.metric_name}"
            assert threshold.description, f"No description for {threshold.metric_name}"

    def test_nfr_report_json_format(self) -> None:
        """
        NFR-CI.5: NFR JSON report format is correct

        Verify that the generated JSON report follows the expected
        structure for CI/CD integration.
        """
        from common.monitoring.nfr_reporter import NFRReporter

        reporter = NFRReporter(output_dir="test-results")
        reporter.add_result("end_to_end_latency", [250, 280, 290, 310, 320])
        reporter.add_result("websocket_connection", [50, 70, 80, 60, 90])

        json_path = reporter.generate_json()

        assert json_path.exists(), f"JSON report not generated: {json_path}"

        with open(json_path) as f:
            report = json.load(f)

        # Check required top-level fields
        assert "metadata" in report
        assert "summary" in report
        assert "thresholds" in report
        assert "results" in report

        # Check summary fields
        summary = report["summary"]
        assert "total_metrics" in summary
        assert "passed_metrics" in summary
        assert "failed_metrics" in summary
        assert "pass_rate" in summary
        assert "overall_status" in summary

        # Check results have required fields
        for result in report["results"]:
            assert "metric_name" in result
            assert "p95_actual_ms" in result
            assert "passed" in result
            assert "samples" in result
            assert "min_ms" in result
            assert "max_ms" in result
            assert "avg_ms" in result

    def test_nfr_report_markdown_format(self) -> None:
        """
        NFR-CI.6: NFR Markdown report format is correct

        Verify that the generated Markdown report contains all
        required sections for human review.
        """
        from common.monitoring.nfr_reporter import NFRReporter

        reporter = NFRReporter(output_dir="test-results")
        reporter.add_result("end_to_end_latency", [250, 280, 290, 310, 320])

        md_path = reporter.generate_markdown()

        assert md_path.exists(), f"Markdown report not generated: {md_path}"

        content = md_path.read_text()

        # Check required sections
        assert "# NFR Performance Report" in content
        assert "## Summary" in content
        assert "## Performance Targets" in content
        assert "Constitution Principle II" in content
        assert "## Detailed Results" in content
        assert "## Constitution Compliance" in content

    def test_nfr_report_html_format(self) -> None:
        """
        NFR-CI.7: NFR HTML report format is correct

        Verify that the generated HTML report contains the
        expected structure and styling.
        """
        from common.monitoring.nfr_reporter import NFRReporter

        reporter = NFRReporter(output_dir="test-results")
        reporter.add_result("end_to_end_latency", [250, 280, 290, 310, 320])

        html_path = reporter.generate_html()

        assert html_path.exists(), f"HTML report not generated: {html_path}"

        content = html_path.read_text()

        # Check HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "<head>" in content
        assert "<body>" in content

        # Check for required content
        assert "NFR Performance Report" in content
        assert "Performance Targets" in content
        assert "Constitution Principle II" in content

        # Check for styling
        assert "<style>" in content
        assert "border-radius:" in content
        assert "font-family:" in content

    def test_nfr_convenience_function(self) -> None:
        """
        NFR-CI.8: Convenience function works correctly

        Verify that the create_nfr_report convenience function
        correctly generates all report formats.
        """
        from common.monitoring.nfr_reporter import create_nfr_report

        test_results = {
            "end_to_end_latency": [250, 280, 290, 310, 320],
            "websocket_connection": [50, 70, 80, 60, 90],
        }

        reports = create_nfr_report(results=test_results, output_dir="test-results")

        # Check all reports generated
        assert "json" in reports
        assert "markdown" in reports
        assert "html" in reports

        # Check all files exist
        for report_type, path in reports.items():
            assert path.exists(), f"{report_type} report not found: {path}"

    def test_nfr_pass_fail_determination(self) -> None:
        """
        NFR-CI.9: Pass/fail determination is correct

        Verify that the reporter correctly determines whether
        each metric passed or failed based on thresholds.
        """
        from common.monitoring.nfr_reporter import NFRReporter

        reporter = NFRReporter(output_dir="test-results")

        # Add passing metric (all samples below threshold)
        reporter.add_result("websocket_connection", [40, 50, 60, 70, 80])

        # Add failing metric (some samples above threshold)
        reporter.add_result("end_to_end_latency", [250, 280, 350, 320, 400])

        json_path = reporter.generate_json()

        with open(json_path) as f:
            report = json.load(f)

        # Check pass/fail determination
        results_by_metric = {r["metric_name"]: r for r in report["results"]}

        # WebSocket should pass (P95 target: 100ms)
        ws_result = results_by_metric.get("websocket_connection")
        assert ws_result is not None
        assert ws_result["passed"] is True, "WebSocket metric should pass"

        # E2E should fail (P95 target: 300ms, samples include >300ms)
        e2e_result = results_by_metric.get("end_to_end_latency")
        assert e2e_result is not None
        assert e2e_result["passed"] is False, "E2E metric should fail"

    def test_nfr_metadata_handling(self) -> None:
        """
        NFR-CI.10: Test metadata is properly captured

        Verify that commit SHA, branch, and other metadata
        are correctly captured and included in reports.
        """
        from common.monitoring.nfr_reporter import NFRReporter

        reporter = NFRReporter(output_dir="test-results")
        reporter.set_metadata(
            commit_sha="test-sha-12345",
            branch="feature/test-branch",
            environment="ci",
            test_duration_seconds=123.45,
        )

        reporter.add_result("websocket_connection", [50, 70, 80])

        json_path = reporter.generate_json()

        with open(json_path) as f:
            report = json.load(f)

        # Check metadata fields
        metadata = report["metadata"]
        assert metadata["commit_sha"] == "test-sha-12345"
        assert metadata["branch"] == "feature/test-branch"
        assert metadata["environment"] == "ci"
        assert metadata["test_duration_seconds"] == 123.45

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Bash script execution test skipped on Windows"
    )
    def test_nfr_runner_script_execution(self, tmp_path: Path) -> None:
        """
        NFR-CI.11: NFR runner script executes correctly

        Verify that the bash script for running NFR tests
        executes and produces expected output.
        """
        runner_path = (
            Path(__file__).parent.parent / "scripts" / "run_nfr_tests.sh"
        )

        if not runner_path.exists():
            pytest.skip("NFR runner script not found")

        # Execute the script with --help flag to verify it works
        result = subprocess.run(
            ["bash", str(runner_path)],
            capture_output=True,
            text=True,
            cwd=str(runner_path.parent.parent),
            timeout=10,
        )

        # Script should produce some output (even if tests fail)
        # The output should contain NFR-related text
        output = result.stdout + result.stderr
        assert "NFR" in output or "nfr" in output


class TestNFRThresholdValues:
    """Test that NFR threshold values match Constitution Principle II."""

    def test_e2e_latency_threshold(self) -> None:
        """End-to-end latency P95 target is 300ms."""
        from common.monitoring.nfr_reporter import NFRReporter

        threshold = next(
            (t for t in NFRReporter.THRESHOLDS if t.metric_name == "end_to_end_latency"),
            None,
        )

        assert threshold is not None
        assert threshold.p95_target_ms == 300.0

    def test_websocket_threshold(self) -> None:
        """WebSocket connection P95 target is 100ms."""
        from common.monitoring.nfr_reporter import NFRReporter

        threshold = next(
            (t for t in NFRReporter.THRESHOLDS if t.metric_name == "websocket_connection"),
            None,
        )

        assert threshold is not None
        assert threshold.p95_target_ms == 100.0

    def test_asr_threshold(self) -> None:
        """ASR streaming P95 target is 200ms."""
        from common.monitoring.nfr_reporter import NFRReporter

        threshold = next(
            (t for t in NFRReporter.THRESHOLDS if t.metric_name == "asr_streaming_latency"),
            None,
        )

        assert threshold is not None
        assert threshold.p95_target_ms == 200.0

    def test_tts_threshold(self) -> None:
        """TTS first-byte P95 target is 300ms."""
        from common.monitoring.nfr_reporter import NFRReporter

        threshold = next(
            (t for t in NFRReporter.THRESHOLDS if t.metric_name == "tts_first_byte_latency"),
            None,
        )

        assert threshold is not None
        assert threshold.p95_target_ms == 300.0

    def test_interrupt_detection_threshold(self) -> None:
        """Interrupt detection P95 target is 100ms."""
        from common.monitoring.nfr_reporter import NFRReporter

        threshold = next(
            (t for t in NFRReporter.THRESHOLDS if t.metric_name == "interrupt_detection"),
            None,
        )

        assert threshold is not None
        assert threshold.p95_target_ms == 100.0

    def test_session_creation_threshold(self) -> None:
        """Session creation P95 target is 100ms, P99 target is 200ms."""
        from common.monitoring.nfr_reporter import NFRReporter

        threshold = next(
            (t for t in NFRReporter.THRESHOLDS if t.metric_name == "session_creation"),
            None,
        )

        assert threshold is not None
        assert threshold.p95_target_ms == 100.0
        assert threshold.p99_target_ms == 200.0
