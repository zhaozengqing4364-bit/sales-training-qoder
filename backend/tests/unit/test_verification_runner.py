"""
Unit tests for VerificationRunner

Tests the automated verification check execution logic.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from common.analytics.verification_runner import (
    VerificationRunner,
    TestExecutionResult,
    CoverageReport,
    HealthCheckResult,
    SecurityCheckResult,
    DocumentationCheckResult,
    QUALITY_GATE_THRESHOLDS,
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock()


@pytest.fixture
def runner():
    """VerificationRunner instance"""
    return VerificationRunner()


class TestParsePytestOutput:
    """Test pytest output parsing"""

    def test_parse_pytest_output_all_passed(self, runner):
        """Test parsing output when all tests passed"""
        output = "10 passed in 0.50s"

        stats = runner._parse_pytest_output(output)

        assert stats["total"] == 10
        assert stats["passed"] == 10
        assert stats["failed"] == 0
        assert stats["skipped"] == 0

    def test_parse_pytest_output_with_failures(self, runner):
        """Test parsing output with failed tests"""
        output = "8 passed, 2 failed, 1 skipped in 1.20s"

        stats = runner._parse_pytest_output(output)

        assert stats["total"] == 11  # 8 + 2 + 1
        assert stats["passed"] == 8
        assert stats["failed"] == 2
        assert stats["skipped"] == 1

    def test_parse_pytest_output_alternative_format(self, runner):
        """Test parsing alternative pytest format"""
        output = "=== 15 passed, 3 failed ==="

        stats = runner._parse_pytest_output(output)

        assert stats["total"] == 18
        assert stats["passed"] == 15
        assert stats["failed"] == 3

    def test_parse_pytest_output_empty(self, runner):
        """Test parsing empty output"""
        stats = runner._parse_pytest_output("")

        assert stats["total"] == 0
        assert stats["passed"] == 0
        assert stats["failed"] == 0
        assert stats["skipped"] == 0


class TestParsePerformanceMetrics:
    """Test performance metrics parsing"""

    def test_parse_end_to_end_p95(self, runner):
        """Test parsing end-to-end P95 latency"""
        output = "End-to-End P95: 250ms"

        metrics = runner._parse_performance_metrics(output)

        assert metrics["end_to_end_p95_ms"] == 250.0

    def test_parse_asr_p95(self, runner):
        """Test parsing ASR P95 latency"""
        output = "ASR P95: 180ms"

        metrics = runner._parse_performance_metrics(output)

        assert metrics["asr_p95_ms"] == 180.0

    def test_parse_multiple_metrics(self, runner):
        """Test parsing multiple performance metrics"""
        output = """
        End-to-End P95: 280ms
        ASR P95: 175ms
        Interruption P95: 85ms
        API P95: 95ms
        API P99: 180ms
        """

        metrics = runner._parse_performance_metrics(output)

        assert metrics["end_to_end_p95_ms"] == 280.0
        assert metrics["asr_p95_ms"] == 175.0
        assert metrics["interruption_p95_ms"] == 85.0
        assert metrics["api_p95_ms"] == 95.0
        assert metrics["api_p99_ms"] == 180.0

    def test_parse_empty_output(self, runner):
        """Test parsing empty output returns infinity values"""
        metrics = runner._parse_performance_metrics("")

        assert metrics["end_to_end_p95_ms"] == float('inf')
        assert metrics["asr_p95_ms"] == float('inf')
        assert metrics["interruption_p95_ms"] == float('inf')
        assert metrics["api_p95_ms"] == float('inf')
        assert metrics["api_p99_ms"] == float('inf')


class TestQualityGateThresholds:
    """Test quality gate threshold definitions"""

    def test_unit_test_coverage_threshold(self):
        """Test unit test coverage threshold"""
        assert "unit_test_coverage" in QUALITY_GATE_THRESHOLDS
        assert QUALITY_GATE_THRESHOLDS["unit_test_coverage"] == 70.0

    def test_contract_test_pass_rate_threshold(self):
        """Test contract test pass rate threshold (NFR19)"""
        assert "contract_test_pass_rate" in QUALITY_GATE_THRESHOLDS
        assert QUALITY_GATE_THRESHOLDS["contract_test_pass_rate"] == 100.0

    def test_performance_p95_threshold(self):
        """Test performance P95 threshold (NFR1)"""
        assert "performance_p95_latency_ms" in QUALITY_GATE_THRESHOLDS
        assert QUALITY_GATE_THRESHOLDS["performance_p95_latency_ms"] == 300.0

    def test_asr_p95_threshold(self):
        """Test ASR P95 threshold (NFR2)"""
        assert "asr_p95_latency_ms" in QUALITY_GATE_THRESHOLDS
        assert QUALITY_GATE_THRESHOLDS["asr_p95_latency_ms"] == 200.0

    def test_integration_test_pass_rate_threshold(self):
        """Test integration test pass rate threshold"""
        assert "integration_test_pass_rate" in QUALITY_GATE_THRESHOLDS
        assert QUALITY_GATE_THRESHOLDS["integration_test_pass_rate"] == 100.0


class TestGenerateSummary:
    """Test summary generation logic"""

    def test_all_passed_can_release(self, runner):
        """Test summary when all checks pass"""
        check_results = [
            {"check_name": "Unit Tests", "result": TestExecutionResult(
                test_type="unit_tests",
                passed=True,
                total_tests=10,
                passed_tests=10,
                failed_tests=0,
                skipped_tests=0,
                duration_ms=5000,
            )},
            {"check_name": "Contract Tests (NFR19)", "result": TestExecutionResult(
                test_type="contract",
                passed=True,
                total_tests=5,
                passed_tests=5,
                failed_tests=0,
                skipped_tests=0,
                duration_ms=3000,
            )},
        ]

        summary = runner._generate_summary(check_results)

        assert summary["total_checks"] == 2
        assert summary["passed_checks"] == 2
        assert summary["failed_checks"] == 0
        assert summary["can_release"] is True

    def test_blocking_failure_blocks_release(self, runner):
        """Test summary when blocking check fails"""
        check_results = [
            {"check_name": "Unit Tests", "result": TestExecutionResult(
                test_type="unit_tests",
                passed=False,
                total_tests=10,
                passed_tests=8,
                failed_tests=2,
                skipped_tests=0,
                duration_ms=5000,
            )},
        ]

        summary = runner._generate_summary(check_results)

        assert summary["failed_checks"] == 1
        assert summary["blocking_failures"] == ["Unit Tests"]
        assert summary["can_release"] is False

    def test_warning_allows_release(self, runner):
        """Test summary when non-blocking check fails"""
        check_results = [
            {"check_name": "Documentation Update", "result": DocumentationCheckResult(
                check_type="documentation",
                passed=True,  # Non-blocking
                up_to_date=False,
                missing_sections=["README.md"],
                duration_ms=1000,
            )},
        ]

        summary = runner._generate_summary(check_results)

        assert summary["failed_checks"] == 1
        assert summary["blocking_failures"] == []
        assert summary["warnings"] == ["Documentation Update"]
        assert summary["can_release"] is True  # Warnings don't block

    def test_is_blocking_check_identifies_blocking(self, runner):
        """Test blocking check identification"""
        assert runner._is_blocking_check("Unit Tests") is True
        assert runner._is_blocking_check("Code Coverage") is True
        assert runner._is_blocking_check("API Contract Tests (NFR19)") is True
        assert runner._is_blocking_check("Documentation Update") is False

    def test_core_and_additional_categorized(self, runner):
        """Test core vs additional check categorization"""
        check_results = [
            {"check_name": "Unit Tests", "check_category": "core", "result": TestExecutionResult(
                test_type="unit_tests", passed=True, total_tests=10, passed_tests=10,
                failed_tests=0, skipped_tests=0, duration_ms=5000,
            )},
            {"check_name": "Health Checks", "check_category": "additional", "result": HealthCheckResult(
                check_type="health", passed=True, duration_ms=1000,
            )},
        ]

        summary = runner._generate_summary(check_results)

        assert summary["core_checks_total"] == 1
        assert summary["core_checks_passed"] == 1
