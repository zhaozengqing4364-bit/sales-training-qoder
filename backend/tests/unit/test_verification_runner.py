"""
Unit tests for VerificationRunner

Tests the automated verification check execution logic.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch

import pytest

from common.analytics.verification_runner import (
    QUALITY_GATE_THRESHOLDS,
    DocumentationCheckResult,
    HealthCheckResult,
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


class TestHealthAndSecurityChecks:
    """Test release verification runner aggregate checks."""

    @pytest.mark.asyncio
    async def test_run_health_checks_aggregates_child_results(self, runner, mock_db):
        """Health check aggregation consumes direct child result tuples."""
        runner._check_database_health = AsyncMock(
            return_value=(
                "database",
                HealthCheckResult(
                    check_type="database",
                    passed=True,
                    duration_ms=1,
                ),
            )
        )
        runner._check_api_health = AsyncMock(
            return_value=(
                "api",
                HealthCheckResult(
                    check_type="api",
                    passed=True,
                    duration_ms=1,
                ),
            )
        )
        runner._check_websocket_health = AsyncMock(
            return_value=(
                "websocket",
                HealthCheckResult(
                    check_type="websocket",
                    passed=True,
                    duration_ms=1,
                ),
            )
        )
        runner._check_external_dependencies = AsyncMock(
            return_value=(
                "external_deps",
                HealthCheckResult(
                    check_type="external_deps",
                    passed=True,
                    duration_ms=1,
                ),
            )
        )
        runner._update_verification_record = AsyncMock()

        result = await runner._run_health_checks(mock_db, "rc-health")

        assert result.passed is True
        assert [item["check_type"] for item in result.details["checks"]] == [
            "database",
            "api",
            "websocket",
            "external_deps",
        ]
        runner._update_verification_record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_security_checks_aggregates_child_results(self, runner, mock_db):
        """Security check aggregation consumes direct child result tuples."""
        def passed_scan(name):
            return (
                name,
                runner.SecurityCheckResult(
                    check_type=name,
                    passed=True,
                    issues_found=0,
                    high_severity=0,
                    medium_severity=0,
                    low_severity=0,
                    duration_ms=1,
                ),
            )

        runner._run_bandit_scan = AsyncMock(return_value=passed_scan("bandit"))
        runner._run_safety_scan = AsyncMock(return_value=passed_scan("safety"))
        runner._run_secrets_scan = AsyncMock(return_value=passed_scan("secrets"))
        runner._run_release_readiness_check = AsyncMock(
            return_value=passed_scan("release_readiness")
        )
        runner._update_verification_record = AsyncMock()

        result = await runner._run_security_checks(mock_db, "rc-security")

        assert result.passed is True
        assert result.issues_found == 0
        assert [item["check_type"] for item in result.details["checks"]] == [
            "bandit",
            "safety",
            "secrets",
            "release_readiness",
        ]
        runner._update_verification_record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_release_readiness_child_failure_blocks_security_gate(self, runner, mock_db):
        """Phase 5 release readiness failures are blocking security failures."""
        passed = (
            "bandit",
            runner.SecurityCheckResult(
                check_type="bandit",
                passed=True,
                issues_found=0,
                high_severity=0,
                medium_severity=0,
                low_severity=0,
                duration_ms=1,
            ),
        )
        failed_readiness = (
            "release_readiness",
            runner.SecurityCheckResult(
                check_type="release_readiness",
                passed=False,
                issues_found=1,
                high_severity=1,
                medium_severity=0,
                low_severity=0,
                duration_ms=1,
                error_message="PHASE4_ISSUE44_MANIFEST_MISSING",
            ),
        )
        runner._run_bandit_scan = AsyncMock(return_value=passed)
        runner._run_safety_scan = AsyncMock(return_value=passed)
        runner._run_secrets_scan = AsyncMock(return_value=passed)
        runner._run_release_readiness_check = AsyncMock(return_value=failed_readiness)
        runner._update_verification_record = AsyncMock()

        result = await runner._run_security_checks(mock_db, "rc-security")

        assert result.passed is False
        assert result.high_severity == 1
        assert result.details["checks"][-1]["check_type"] == "release_readiness"

    @pytest.mark.asyncio
    async def test_database_health_uses_session_engine_export(
        self, runner, monkeypatch
    ):
        """Database health uses common.db.session.engine, not a missing get_engine."""

        class FakeConnection:
            def __init__(self):
                self.executed = False
                self.committed = False

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def execute(self, statement):
                self.executed = str(statement) == "SELECT 1"

            async def commit(self):
                self.committed = True

        class FakeEngine:
            def __init__(self):
                self.connection = FakeConnection()

            def connect(self):
                return self.connection

        fake_engine = FakeEngine()
        fake_session_module = ModuleType("common.db.session")
        setattr(fake_session_module, "engine", fake_engine)
        monkeypatch.setitem(sys.modules, "common.db.session", fake_session_module)

        check_name, result = await runner._check_database_health()

        assert check_name == "database"
        assert result.passed is True
        assert fake_engine.connection.executed is True
        assert fake_engine.connection.committed is False


class TestDocumentationChecks:
    """Test documentation verification runtime-safe result construction."""

    def test_api_contracts_missing_docs_include_duration(self, tmp_path):
        """Missing API contract docs return a complete dataclass result."""
        runner = VerificationRunner(tmp_path / "backend")
        (tmp_path / "docs" / "api-contract").mkdir(parents=True)

        result = runner._check_api_contracts()

        assert result.check_type == "api_contract"
        assert result.up_to_date is False
        assert "websocket.md" in result.missing_sections
        assert isinstance(result.duration_ms, int)

    def test_readme_missing_includes_duration(self, tmp_path):
        """Missing README returns a complete non-blocking result."""
        runner = VerificationRunner(tmp_path / "backend")

        result = runner._check_readme()

        assert result.check_type == "readme"
        assert result.passed is True
        assert result.up_to_date is False
        assert result.missing_sections == ["README.md"]
        assert isinstance(result.duration_ms, int)

    def test_deployment_docs_missing_include_duration(self, tmp_path):
        """Missing deployment docs return a complete non-blocking result."""
        runner = VerificationRunner(tmp_path / "backend")
        (tmp_path / "docs").mkdir()

        result = runner._check_deployment_docs()

        assert result.check_type == "deployment"
        assert result.up_to_date is False
        assert result.missing_sections == [
            "deployment.md",
            "roadmap",
            "api-contract",
        ]
        assert isinstance(result.duration_ms, int)

    def test_documentation_check_errors_are_stored_in_details(self, tmp_path):
        """Documentation sub-check exceptions avoid unsupported dataclass fields."""
        runner = VerificationRunner(tmp_path / "backend")
        (tmp_path / "docs").mkdir()

        with patch(
            "common.analytics.verification_runner.Path.glob",
            side_effect=RuntimeError("docs exploded"),
        ):
            result = runner._check_deployment_docs()

        assert result.passed is True
        assert result.up_to_date is False
        assert result.details == {"error": "docs exploded"}
        assert isinstance(result.duration_ms, int)

    @pytest.mark.asyncio
    async def test_run_documentation_checks_exception_returns_result(
        self, runner, mock_db
    ):
        """Top-level documentation exceptions return result instead of TypeError."""
        runner._check_api_contracts = Mock(side_effect=RuntimeError("api docs boom"))

        result = await runner._run_documentation_checks(mock_db, "rc-docs")

        assert result.check_type == "documentation"
        assert result.passed is False
        assert result.up_to_date is False
        assert result.details == {
            "error": "Documentation checks failed: api docs boom"
        }
        assert isinstance(result.duration_ms, int)
