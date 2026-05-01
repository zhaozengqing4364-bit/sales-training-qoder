"""
Unit tests for VerificationRunner

Tests the automated verification check execution logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from common.analytics.verification_runner import (
    QUALITY_GATE_THRESHOLDS,
    DocumentationCheckResult,
    HealthCheckResult,
    SecurityCheckResult,
    TestExecutionResult,
    VerificationRunner,
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


class TestRuntimeChecks:
    """Regression tests for release verification runtime paths."""

    @pytest.mark.asyncio
    async def test_database_health_uses_configured_async_engine(self, runner, monkeypatch):
        """Database health should use the session module engine, not a missing helper."""
        from common.db import session as db_session

        class FakeConnection:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def execute(self, statement):
                self.statement = statement

        class FakeEngine:
            def __init__(self):
                self.connection = FakeConnection()

            def connect(self):
                return self.connection

        fake_engine = FakeEngine()
        monkeypatch.setattr(db_session, "engine", fake_engine)

        check_type, result = await runner._check_database_health()

        assert check_type == "database"
        assert result.passed is True
        assert result.details == {"query": "SELECT 1 successful"}

    @pytest.mark.asyncio
    async def test_health_checks_aggregate_inner_results(self, runner, mock_db):
        """Health aggregation should consume the tuples returned by each subcheck."""
        runner._check_database_health = AsyncMock(
            return_value=(
                "database",
                HealthCheckResult("database", True, duration_ms=1),
            )
        )
        runner._check_api_health = AsyncMock(
            return_value=("api", HealthCheckResult("api", True, duration_ms=2))
        )
        runner._check_websocket_health = AsyncMock(
            return_value=(
                "websocket",
                HealthCheckResult("websocket", True, duration_ms=3),
            )
        )
        runner._check_external_dependencies = AsyncMock(
            return_value=(
                "external_deps",
                HealthCheckResult(
                    "external_deps",
                    False,
                    duration_ms=4,
                    error_message="Missing required env vars: DATABASE_URL",
                ),
            )
        )
        runner._update_verification_record = AsyncMock()

        result = await runner._run_health_checks(mock_db, "rc-1")

        assert result.passed is False
        assert result.error_message == "One or more health checks failed"
        assert result.details["checks"][-1]["check_type"] == "external_deps"
        runner._update_verification_record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_security_checks_aggregate_inner_results(self, runner, mock_db):
        """Security aggregation should consume the tuples returned by scan helpers."""
        runner._run_bandit_scan = AsyncMock(
            return_value=(
                "bandit",
                SecurityCheckResult(
                    "bandit",
                    True,
                    issues_found=0,
                    high_severity=0,
                    medium_severity=0,
                    low_severity=0,
                    duration_ms=1,
                ),
            )
        )
        runner._run_safety_scan = AsyncMock(
            return_value=(
                "safety",
                SecurityCheckResult(
                    "safety",
                    True,
                    issues_found=0,
                    high_severity=0,
                    medium_severity=0,
                    low_severity=0,
                    duration_ms=2,
                ),
            )
        )
        runner._run_secrets_scan = AsyncMock(
            return_value=(
                "secrets",
                SecurityCheckResult(
                    "secrets",
                    False,
                    issues_found=1,
                    high_severity=1,
                    medium_severity=0,
                    low_severity=0,
                    duration_ms=3,
                ),
            )
        )
        runner._update_verification_record = AsyncMock()

        result = await runner._run_security_checks(mock_db, "rc-1")

        assert result.passed is False
        assert result.issues_found == 1
        assert result.high_severity == 1
        assert result.details["severity_breakdown"]["high"] == 1
        runner._update_verification_record.assert_awaited_once()


class TestDocumentationChecks:
    """Regression tests for documentation-check result construction."""

    def test_documentation_subchecks_include_required_duration(self, runner):
        """Every DocumentationCheckResult constructor should match dataclass fields."""
        results = [
            runner._check_api_contracts(),
            runner._check_readme(),
            runner._check_deployment_docs(),
        ]

        assert all(isinstance(result, DocumentationCheckResult) for result in results)
        assert all(isinstance(result.duration_ms, int) for result in results)

    @pytest.mark.asyncio
    async def test_documentation_check_exception_returns_structured_result(
        self, runner, mock_db
    ):
        """Documentation runner exceptions should not pass unknown dataclass fields."""
        runner._check_api_contracts = lambda: (_ for _ in ()).throw(
            RuntimeError("docs boom")
        )

        result = await runner._run_documentation_checks(mock_db, "rc-1")

        assert result.passed is False
        assert result.up_to_date is False
        assert result.missing_sections == ["documentation_check_error"]
        assert "docs boom" in result.details["error"]
