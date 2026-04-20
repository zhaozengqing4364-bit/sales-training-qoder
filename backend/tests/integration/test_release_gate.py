"""
Integration tests for Release Verification Gate

Tests the complete release verification flow including:
- Automated test execution
- Quality gate validation
- Report generation
- Release blocking on failures
"""

from __future__ import annotations

import pytest
import json
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from common.analytics.verification_runner import (
    VerificationRunner,
    verification_runner,
    TestExecutionResult,
    HealthCheckResult,
    SecurityCheckResult,
    DocumentationCheckResult,
)
from common.analytics.release_verification_service import release_verification_service


@pytest.fixture
async def mock_db_session(test_db):
    """Use real test DB session for release gate integration tests."""
    yield test_db


@pytest.fixture
def runner():
    """VerificationRunner instance with lightweight check stubs for deterministic tests."""
    runner = VerificationRunner()

    runner._run_unit_tests = AsyncMock(return_value=TestExecutionResult(
        test_type="unit_tests",
        passed=True,
        total_tests=10,
        passed_tests=10,
        failed_tests=0,
        skipped_tests=0,
        duration_ms=10,
    ))
    runner._load_coverage_report = lambda: runner.CoverageReport(
        coverage_percentage=85.0,
        covered_lines=850,
        total_lines=1000,
        missing_lines=150,
        by_module={},
    )
    runner._run_integration_tests = AsyncMock(return_value=TestExecutionResult(
        test_type="integration_tests",
        passed=True,
        total_tests=8,
        passed_tests=8,
        failed_tests=0,
        skipped_tests=0,
        duration_ms=10,
    ))
    runner._run_contract_tests = AsyncMock(return_value=TestExecutionResult(
        test_type="contract",
        passed=True,
        total_tests=6,
        passed_tests=6,
        failed_tests=0,
        skipped_tests=0,
        duration_ms=10,
    ))
    runner._run_performance_tests = AsyncMock(return_value=TestExecutionResult(
        test_type="performance",
        passed=True,
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        skipped_tests=0,
        duration_ms=10,
        performance_metrics={
            "end_to_end_p95_ms": 180.0,
            "asr_p95_ms": 120.0,
            "interruption_p95_ms": 80.0,
            "api_p95_ms": 60.0,
            "api_p99_ms": 140.0,
        },
    ))
    runner._run_health_checks = AsyncMock(return_value=HealthCheckResult(
        check_type="health",
        passed=True,
        duration_ms=10,
        details={},
    ))
    runner._run_security_checks = AsyncMock(return_value=SecurityCheckResult(
        check_type="security",
        passed=True,
        issues_found=0,
        high_severity=0,
        medium_severity=0,
        low_severity=0,
        duration_ms=10,
    ))
    runner._run_documentation_checks = AsyncMock(return_value=DocumentationCheckResult(
        check_type="documentation",
        passed=True,
        up_to_date=True,
        missing_sections=[],
        duration_ms=10,
    ))

    return runner


class TestReleaseVerificationFlow:
    """Test the complete release verification flow"""

    @pytest.mark.asyncio
    async def test_create_release_candidate(self, mock_db_session):
        """Test creating a new release candidate"""
        result = await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-1.2.0-001",
            created_by="test-user",
        )

        assert result.is_success
        summary = result.value
        assert summary.release_version == "v1.2.0"
        assert summary.release_candidate_id == "rc-1.2.0-001"
        assert summary.overall_status == "pending"
        assert summary.total_checks == 5  # Default checks count

    @pytest.mark.asyncio
    async def test_run_all_verification_checks(self, mock_db_session, runner):
        """Test running all verification checks"""
        # First create release candidate
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-test-001",
        )

        # Run all checks
        result = await runner.run_all_checks(
            db=mock_db_session,
            release_candidate_id="rc-test-001",
        )

        assert result.is_success
        summary = result.value

        # Check that all check types were executed
        check_names = [c["check_name"] for c in summary["checks"]]
        assert "unit_tests" in check_names
        assert "coverage" in check_names
        assert "integration_tests" in check_names
        assert "contract_tests" in check_names
        assert "performance" in check_names
        assert "health" in check_names
        assert "security" in check_names
        assert "documentation" in check_names

    @pytest.mark.asyncio
    async def test_quality_gate_blocks_on_critical_failure(self, mock_db_session, runner):
        """Test that quality gate blocks on critical failures"""
        # Create release candidate
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-gate-test",
        )

        # Mock unit tests to fail (blocking)
        with patch.object(runner, '_run_unit_tests', return_value=runner.TestExecutionResult(
            test_type="unit_tests",
            passed=False,
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            skipped_tests=0,
            duration_ms=5000,
        )):
            result = await runner.run_all_checks(
                db=mock_db_session,
                release_candidate_id="rc-gate-test",
            )

        # Check summary shows blocking failure
        summary = result.value["summary"]
        assert summary["can_release"] is False
        assert "unit_tests" in summary["blocking_failures"]

    @pytest.mark.asyncio
    async def test_quality_gate_allows_with_warnings(self, mock_db_session, runner):
        """Test that quality gate allows release with non-blocking warnings"""
        # Create release candidate
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-warning-test",
        )

        # Mock documentation check to fail (non-blocking)
        with patch.object(runner, '_run_documentation_checks', return_value=runner.DocumentationCheckResult(
            check_type="documentation",
            passed=True,
            up_to_date=False,
            missing_sections=["README.md"],
            duration_ms=1000,
        )):
            result = await runner.run_all_checks(
                db=mock_db_session,
                release_candidate_id="rc-warning-test",
            )

        # Check summary allows release (warnings don't block)
        summary = result.value["summary"]
        assert summary["can_release"] is True
        assert "documentation" in summary["warnings"]

    @pytest.mark.asyncio
    async def test_get_verification_report(self, mock_db_session):
        """Test getting complete verification report"""
        # Create release candidate
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-report-test",
        )

        # Get report
        result = await release_verification_service.get_verification_report(
            db=mock_db_session,
            release_candidate_id="rc-report-test",
        )

        assert result.is_success
        report = result.value

        # Verify report structure
        assert report.summary is not None
        assert len(report.checks) == 5  # Default checks
        assert report.gate_status is not None
        assert isinstance(report.recommendations, list)

    @pytest.mark.asyncio
    async def test_check_quality_gate_status(self, mock_db_session):
        """Test quality gate status checking"""
        # Create release candidate with some checks run
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-gate-status-test",
        )

        # Check quality gate
        result = await release_verification_service.check_quality_gate(
            db=mock_db_session,
            release_candidate_id="rc-gate-status-test",
        )

        assert result.is_success
        gate_status = result.value

        # Verify gate status structure
        assert "overall_status" in gate_status
        assert "gates" in gate_status
        assert "blocking_failures" in gate_status
        assert "warnings" in gate_status
        assert "can_release" in gate_status
        assert "recommendations" in gate_status

    @pytest.mark.asyncio
    async def test_make_automated_decision(self, mock_db_session, runner):
        """Test automated go/no-go decision making"""
        # Create release candidate
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-auto-decision-test",
        )

        # Complete checks so automated decision can be made
        await runner.run_all_checks(
            db=mock_db_session,
            release_candidate_id="rc-auto-decision-test",
        )

        # Make automated decision
        result = await release_verification_service.make_automated_decision(
            db=mock_db_session,
            release_candidate_id="rc-auto-decision-test",
            finalized_by="test-user",
        )

        assert result.is_success
        decision = result.value

        # Verify decision was made
        assert decision.go_no_go_decision in ["go", "no_go", "conditional"]
        assert decision.finalized_by == "test-user"
        assert decision.finalized_at is not None


class TestQualityGateThresholds:
    """Test quality gate threshold enforcement"""

    @pytest.mark.asyncio
    async def test_coverage_threshold_blocks_release(self, mock_db_session, runner):
        """Test that coverage below 70% blocks release"""
        # Create release candidate
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-coverage-test",
        )

        # Mock coverage below threshold
        with patch.object(runner, '_load_coverage_report', return_value=runner.CoverageReport(
            coverage_percentage=65.0,  # Below 70% threshold
            covered_lines=650,
            total_lines=1000,
            missing_lines=350,
            by_module={},
        )):
            result = await runner.run_all_checks(
                db=mock_db_session,
                release_candidate_id="rc-coverage-test",
            )

        # Check quality gate status
        gate_result = await release_verification_service.check_quality_gate(
            db=mock_db_session,
            release_candidate_id="rc-coverage-test",
        )

        assert gate_result.is_success
        gate_status = gate_result.value

        # Verify coverage gate failed
        assert gate_status["gates"]["coverage"]["status"] == "fail"
        assert gate_status["can_release"] is False
        assert any("coverage below" in r.lower() for r in gate_status["recommendations"])

    @pytest.mark.asyncio
    async def test_contract_test_100_required(self, mock_db_session, runner):
        """Test that contract tests must be 100% passing (NFR19)"""
        # Create release candidate
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-contract-test",
        )

        # Mock contract tests not 100% passing
        with patch.object(runner, '_run_contract_tests', return_value=runner.TestExecutionResult(
            test_type="contract",
            passed=False,  # Contract tests must pass
            total_tests=5,
            passed_tests=4,  # 80% pass rate - should fail
            failed_tests=1,
            skipped_tests=0,
            duration_ms=3000,
        )):
            result = await runner.run_all_checks(
                db=mock_db_session,
                release_candidate_id="rc-contract-test",
            )

        # Check quality gate status
        gate_result = await release_verification_service.check_quality_gate(
            db=mock_db_session,
            release_candidate_id="rc-contract-test",
        )

        assert gate_result.is_success
        gate_status = gate_result.value

        # Verify contract gate is marked as blocking
        assert gate_status["gates"]["contract"]["critical"] is True
        assert gate_status["can_release"] is False
        assert any("contract" in r.lower() for r in gate_status["blocking_failures"])

    @pytest.mark.asyncio
    async def test_performance_p95_threshold_blocks(self, mock_db_session, runner):
        """Test that performance P95 > 300ms blocks release (NFR1)"""
        # Create release candidate
        await release_verification_service.create_release_candidate(
            db=mock_db_session,
            release_version="v1.2.0",
            release_candidate_id="rc-perf-test",
        )

        # Mock performance metrics above threshold
        with patch.object(runner, '_run_performance_tests', return_value=runner.TestExecutionResult(
            test_type="performance",
            passed=False,  # Failed due to threshold
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            skipped_tests=0,
            duration_ms=5000,
            performance_metrics={
                "end_to_end_p95_ms": 350.0,  # Above 300ms threshold (NFR1)
                "asr_p95_ms": 180.0,
                "interruption_p95_ms": 85.0,
                "api_p95_ms": 95.0,
                "api_p99_ms": 180.0,
            },
            test_output="End-to-End P95: 350ms",
        )):
            result = await runner.run_all_checks(
                db=mock_db_session,
                release_candidate_id="rc-perf-test",
            )

        # Check quality gate status
        gate_result = await release_verification_service.check_quality_gate(
            db=mock_db_session,
            release_candidate_id="rc-perf-test",
        )

        assert gate_result.is_success
        gate_status = gate_result.value

        # Verify performance gate failed
        assert gate_status["gates"]["performance"]["status"] == "fail"
        assert gate_status["can_release"] is False
        assert any(
            "performance" in r.lower() or "threshold" in r.lower()
            for r in gate_status["warnings"]
        )
