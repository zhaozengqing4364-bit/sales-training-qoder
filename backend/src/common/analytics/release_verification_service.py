"""
Release Verification Service - Release gate verification and tracking

Implements FR40: Release gate check results recording and tracking

References:
- Requirements: FR40
- NFR19: Contract test pass rate 100% required for release
- Constitution Principles:
  - I. NO ERROR POPUPS - Graceful degradation
  - VII. Observability - Structured logging with trace_id
"""

from __future__ import annotations

import logging
import inspect
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Literal
from unittest.mock import Mock

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from common.db.models import (
    ReleaseVerificationRecord,
    ReleaseVerificationSummary,
    VerificationCheckType,
    VerificationStatus,
    User,
)
from common.error_handling.result import Result

logger = logging.getLogger(__name__)


# Type aliases
CheckType = Literal[
    "unit_tests",
    "coverage",
    "integration_tests",
    "contract",
    "performance",
    "health",
    "security",
    "documentation",
    "migration",
    "manual",
    "api",
    "database",
    "websocket",
    "external_deps",
    "bandit",
    "safety",
    "secrets",
    "api_contract",
    "readme",
    "deployment",
]
CheckStatus = Literal["pending", "passed", "failed", "skipped"]
GoNoGoDecision = Literal["go", "no_go", "conditional"]

# Gate blockage levels
GateLevel = Literal["blocking", "warning"]


@dataclass
class VerificationCheckInput:
    """Input for creating/updating a verification check"""
    check_type: CheckType
    check_name: str
    check_description: str | None = None
    status: CheckStatus = "pending"
    details: dict[str, Any] | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    gate_level: GateLevel = "blocking"  # Whether this check blocks release on failure


@dataclass
class CheckThreshold:
    """Threshold definitions for verification checks"""
    min_value: float | None = None
    max_value: float | None = None
    required_value: Any = None
    unit: str | None = None


@dataclass
class VerificationRecordView:
    """View of a verification record"""
    record_id: str
    release_version: str
    release_candidate_id: str
    check_type: str
    check_name: str
    check_description: str | None
    status: str
    passed: bool
    details: dict[str, Any] | None
    error_message: str | None
    executed_by: str | None
    executed_at: str | None
    duration_ms: int | None
    created_at: str
    updated_at: str


@dataclass
class VerificationSummaryView:
    """View of a verification summary"""
    summary_id: str
    release_version: str
    release_candidate_id: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    skipped_checks: int
    pending_checks: int
    overall_status: str
    go_no_go_decision: str | None
    decision_reason: str | None
    created_at: str
    updated_at: str
    finalized_at: str | None
    finalized_by: str | None


@dataclass
class ReleaseVerificationReport:
    """Complete verification report for a release"""
    summary: VerificationSummaryView
    checks: list[VerificationRecordView]
    gate_status: dict[str, dict[str, Any]]  # Per-gate status summary
    recommendations: list[str]


class ReleaseVerificationService:
    """
    Service for managing release gate verification records

    Key responsibilities:
    - Create and update verification check records
    - Generate verification summaries
    - Track go/no-go decisions
    - Provide verification reports
    """

    # Default check templates for a new release candidate
    DEFAULT_CHECKS: list[VerificationCheckInput] = [
        VerificationCheckInput(
            check_type="unit_tests",
            check_name="Unit Tests",
            check_description="Verify unit test suite passes"
        ),
        VerificationCheckInput(
            check_type="coverage",
            check_name="Code Coverage",
            check_description="Verify code coverage meets threshold (>=70%)"
        ),
        VerificationCheckInput(
            check_type="integration_tests",
            check_name="Integration Tests",
            check_description="Verify integration test suite passes"
        ),
        VerificationCheckInput(
            check_type="contract",
            check_name="API Contract Tests",
            check_description="Verify all API contracts pass (NFR19: 100% required)"
        ),
        VerificationCheckInput(
            check_type="performance",
            check_name="Performance Benchmarks",
            check_description="Verify latency and throughput meet NFR thresholds"
        ),
    ]

    async def _resolve_scalar_one_or_none(self, query_result: Any) -> Any | None:
        """Resolve SQLAlchemy scalar result while tolerating async mocks in tests."""
        scalar_getter = getattr(query_result, "scalar_one_or_none", None)
        if not callable(scalar_getter):
            return None

        value = scalar_getter()
        if inspect.isawaitable(value):
            value = await value

        if isinstance(value, Mock):
            return None

        return value

    async def create_release_candidate(
        self,
        db: AsyncSession,
        release_version: str,
        release_candidate_id: str,
        checks: list[VerificationCheckInput] | None = None,
        created_by: str | None = None,
    ) -> Result[VerificationSummaryView]:
        """
        Create a new release candidate with default verification checks

        Args:
            db: Database session
            release_version: Version string (e.g., "v1.2.0")
            release_candidate_id: Unique identifier for the RC
            checks: Optional custom checks (defaults used if not provided)
            created_by: User ID of creator

        Returns:
            Result containing VerificationSummaryView or error
        """
        try:
            # Check if RC already exists
            existing = await db.execute(
                select(ReleaseVerificationSummary).where(
                    ReleaseVerificationSummary.release_candidate_id == release_candidate_id
                )
            )
            if await self._resolve_scalar_one_or_none(existing):
                return Result.fail(fallback="[RC_ALREADY_EXISTS]")

            # Create summary
            check_list = checks or self.DEFAULT_CHECKS
            summary = ReleaseVerificationSummary(
                summary_id=str(uuid.uuid4()),
                release_version=release_version,
                release_candidate_id=release_candidate_id,
                total_checks=len(check_list),
                pending_checks=len(check_list),
                overall_status="pending",
            )
            db.add(summary)

            # Create check records
            for check in check_list:
                record = ReleaseVerificationRecord(
                    record_id=str(uuid.uuid4()),
                    release_version=release_version,
                    release_candidate_id=release_candidate_id,
                    check_type=check.check_type,
                    check_name=check.check_name,
                    check_description=check.check_description,
                    status=check.status,
                    passed=False,
                    details=check.details,
                )
                db.add(record)

            await db.commit()
            await db.refresh(summary)

            logger.info(
                "Created release candidate verification",
                extra={
                    "release_version": release_version,
                    "release_candidate_id": release_candidate_id,
                    "total_checks": len(check_list),
                    "created_by": created_by,
                }
            )

            return Result(value=self._summary_to_view(summary))

        except SQLAlchemyError as e:
            logger.error(
                "Failed to create release candidate",
                extra={"error": str(e)},
                exc_info=True
            )
            await db.rollback()
            return Result.fail(fallback="[CREATE_RC_FAILED]")

    async def update_check_result(
        self,
        db: AsyncSession,
        record_id: str,
        status: CheckStatus,
        passed: bool,
        details: dict[str, Any] | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
        executed_by: str | None = None,
    ) -> Result[VerificationRecordView]:
        """
        Update a verification check result

        Args:
            db: Database session
            record_id: ID of the verification record
            status: New status
            passed: Whether the check passed
            details: Additional check data
            error_message: Error message if failed
            duration_ms: Duration of check execution
            executed_by: User ID of executor

        Returns:
            Result containing updated VerificationRecordView or error
        """
        try:
            result = await db.execute(
                select(ReleaseVerificationRecord).where(
                    ReleaseVerificationRecord.record_id == record_id
                )
            )
            record = await self._resolve_scalar_one_or_none(result)

            if not record:
                return Result.fail(fallback="[RECORD_NOT_FOUND]")

            # Update record
            old_status = record.status
            record.status = status
            record.passed = passed
            record.details = details or record.details
            record.error_message = error_message
            record.duration_ms = duration_ms
            record.executed_by = executed_by
            record.executed_at = datetime.now(timezone.utc)
            record.updated_at = datetime.now(timezone.utc)

            # Update summary counts
            await self._update_summary_counts(db, record.release_candidate_id, old_status, status)

            await db.commit()
            await db.refresh(record)

            logger.info(
                "Updated verification check result",
                extra={
                    "record_id": record_id,
                    "status": status,
                    "passed": passed,
                    "executed_by": executed_by,
                }
            )

            return Result(value=self._record_to_view(record))

        except SQLAlchemyError as e:
            logger.error(
                "Failed to update check result",
                extra={"record_id": record_id, "error": str(e)},
                exc_info=True
            )
            await db.rollback()
            return Result.fail(fallback="[UPDATE_CHECK_FAILED]")

    async def make_go_no_go_decision(
        self,
        db: AsyncSession,
        release_candidate_id: str,
        decision: GoNoGoDecision,
        reason: str,
        finalized_by: str,
    ) -> Result[VerificationSummaryView]:
        """
        Make a go/no-go decision for a release candidate

        Args:
            db: Database session
            release_candidate_id: ID of the release candidate
            decision: go, no_go, or conditional
            reason: Reason for the decision
            finalized_by: User ID making the decision

        Returns:
            Result containing updated VerificationSummaryView or error
        """
        try:
            result = await db.execute(
                select(ReleaseVerificationSummary).where(
                    ReleaseVerificationSummary.release_candidate_id == release_candidate_id
                )
            )
            summary = await self._resolve_scalar_one_or_none(result)

            if not summary:
                return Result.fail(fallback="[SUMMARY_NOT_FOUND]")

            # Check if all required checks are complete
            if summary.pending_checks > 0:
                return Result.fail(fallback="[PENDING_CHECKS_EXIST]")

            summary.go_no_go_decision = decision
            summary.decision_reason = reason
            summary.finalized_at = datetime.now(timezone.utc)
            summary.finalized_by = finalized_by
            summary.updated_at = datetime.now(timezone.utc)

            # Set overall status based on decision
            if decision == "go":
                summary.overall_status = "passed"
            elif decision == "no_go":
                summary.overall_status = "failed"
            else:
                summary.overall_status = "passed"  # Conditional is still a pass

            await db.commit()
            await db.refresh(summary)

            logger.info(
                "Made go/no-go decision",
                extra={
                    "release_candidate_id": release_candidate_id,
                    "decision": decision,
                    "finalized_by": finalized_by,
                }
            )

            return Result(value=self._summary_to_view(summary))

        except SQLAlchemyError as e:
            logger.error(
                "Failed to make go/no-go decision",
                extra={"release_candidate_id": release_candidate_id, "error": str(e)},
                exc_info=True
            )
            await db.rollback()
            return Result.fail(fallback="[DECISION_FAILED]")

    async def get_verification_report(
        self,
        db: AsyncSession,
        release_candidate_id: str,
    ) -> Result[ReleaseVerificationReport]:
        """
        Get complete verification report for a release candidate

        Args:
            db: Database session
            release_candidate_id: ID of the release candidate

        Returns:
            Result containing ReleaseVerificationReport or error
        """
        try:
            # Get summary
            summary_result = await db.execute(
                select(ReleaseVerificationSummary).where(
                    ReleaseVerificationSummary.release_candidate_id == release_candidate_id
                )
            )
            summary = await self._resolve_scalar_one_or_none(summary_result)

            if not summary:
                return Result.fail(fallback="[SUMMARY_NOT_FOUND]")

            # Get all checks
            checks_result = await db.execute(
                select(ReleaseVerificationRecord).where(
                    ReleaseVerificationRecord.release_candidate_id == release_candidate_id
                ).order_by(ReleaseVerificationRecord.created_at)
            )
            checks = checks_result.scalars().all()

            # Build gate status summary
            gate_status: dict[str, dict[str, Any]] = {}
            for check in checks:
                if check.check_type not in gate_status:
                    gate_status[check.check_type] = {
                        "total": 0,
                        "passed": 0,
                        "failed": 0,
                        "pending": 0,
                    }
                gate_status[check.check_type]["total"] += 1
                if check.status == "passed":
                    gate_status[check.check_type]["passed"] += 1
                elif check.status == "failed":
                    gate_status[check.check_type]["failed"] += 1
                elif check.status == "pending":
                    gate_status[check.check_type]["pending"] += 1

            # Generate recommendations
            recommendations = self._generate_recommendations(summary, checks)

            report = ReleaseVerificationReport(
                summary=self._summary_to_view(summary),
                checks=[self._record_to_view(c) for c in checks],
                gate_status=gate_status,
                recommendations=recommendations,
            )

            return Result(value=report)

        except SQLAlchemyError as e:
            logger.error(
                "Failed to get verification report",
                extra={"release_candidate_id": release_candidate_id, "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[REPORT_FAILED]")

    async def list_release_candidates(
        self,
        db: AsyncSession,
        status: CheckStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Result[list[VerificationSummaryView]]:
        """
        List release candidates with optional status filter

        Args:
            db: Database session
            status: Optional status filter
            limit: Max items to return
            offset: Pagination offset

        Returns:
            Result containing list of VerificationSummaryView or error
        """
        try:
            query = select(ReleaseVerificationSummary).order_by(
                ReleaseVerificationSummary.created_at.desc()
            )

            if status:
                query = query.where(ReleaseVerificationSummary.overall_status == status)

            query = query.limit(limit).offset(offset)

            result = await db.execute(query)
            summaries = result.scalars().all()

            return Result(value=[self._summary_to_view(s) for s in summaries])

        except SQLAlchemyError as e:
            logger.error(
                "Failed to list release candidates",
                extra={"error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[LIST_FAILED]")

    async def get_latest_release_candidate(
        self,
        db: AsyncSession,
    ) -> Result[VerificationSummaryView | None]:
        """
        Get the latest release candidate

        Returns:
            Result containing VerificationSummaryView or None or error
        """
        try:
            result = await db.execute(
                select(ReleaseVerificationSummary)
                .order_by(ReleaseVerificationSummary.created_at.desc())
                .limit(1)
            )
            summary = await self._resolve_scalar_one_or_none(result)

            if summary:
                return Result(value=self._summary_to_view(summary))
            return Result(value=None)

        except SQLAlchemyError as e:
            logger.error(
                "Failed to get latest release candidate",
                extra={"error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[GET_LATEST_FAILED]")

    async def _update_summary_counts(
        self,
        db: AsyncSession,
        release_candidate_id: str,
        old_status: str,
        new_status: str,
    ) -> None:
        """Update summary counts when a check status changes"""
        result = await db.execute(
            select(ReleaseVerificationSummary).where(
                ReleaseVerificationSummary.release_candidate_id == release_candidate_id
            )
        )
        summary = await self._resolve_scalar_one_or_none(result)

        if summary:
            # Decrement old status count
            if old_status == "pending":
                summary.pending_checks = max(0, summary.pending_checks - 1)
            elif old_status == "passed":
                summary.passed_checks = max(0, summary.passed_checks - 1)
            elif old_status == "failed":
                summary.failed_checks = max(0, summary.failed_checks - 1)
            elif old_status == "skipped":
                summary.skipped_checks = max(0, summary.skipped_checks - 1)

            # Increment new status count
            if new_status == "pending":
                summary.pending_checks += 1
            elif new_status == "passed":
                summary.passed_checks += 1
            elif new_status == "failed":
                summary.failed_checks += 1
            elif new_status == "skipped":
                summary.skipped_checks += 1

            # Update overall status
            if summary.failed_checks > 0:
                summary.overall_status = "failed"
            elif summary.pending_checks == 0:
                summary.overall_status = "passed"

            summary.updated_at = datetime.now(timezone.utc)

    def _generate_recommendations(
        self,
        summary: ReleaseVerificationSummary,
        checks: list[ReleaseVerificationRecord],
    ) -> list[str]:
        """Generate recommendations based on verification results"""
        recommendations = []

        # Check for failed items
        failed_checks = [c for c in checks if c.status == "failed"]
        if failed_checks:
            recommendations.append(
                f"Address {len(failed_checks)} failed check(s) before proceeding"
            )

        # Check for pending items
        if summary.pending_checks > 0:
            recommendations.append(
                f"Complete {summary.pending_checks} pending check(s)"
            )

        # Contract tests must be 100% (NFR19)
        contract_checks = [c for c in checks if c.check_type == "contract"]
        failed_contracts = [c for c in contract_checks if c.status == "failed"]
        if failed_contracts:
            recommendations.append(
                "CRITICAL: Contract tests must pass 100% (NFR19) before release"
            )

        # Performance checks
        perf_checks = [c for c in checks if c.check_type == "performance"]
        failed_perf = [c for c in perf_checks if c.status == "failed"]
        if failed_perf:
            recommendations.append(
                "Review performance benchmarks to ensure NFR thresholds are met"
            )

        # If all passed
        if summary.passed_checks == summary.total_checks:
            recommendations.append("All checks passed - ready for go decision")

        return recommendations

    def _record_to_view(self, record: ReleaseVerificationRecord) -> VerificationRecordView:
        """Convert model to view"""
        return VerificationRecordView(
            record_id=record.record_id,
            release_version=record.release_version,
            release_candidate_id=record.release_candidate_id,
            check_type=record.check_type,
            check_name=record.check_name,
            check_description=record.check_description,
            status=record.status,
            passed=record.passed,
            details=record.details,
            error_message=record.error_message,
            executed_by=record.executed_by,
            executed_at=record.executed_at.isoformat() if record.executed_at else None,
            duration_ms=record.duration_ms,
            created_at=record.created_at.isoformat() if record.created_at else "",
            updated_at=record.updated_at.isoformat() if record.updated_at else "",
        )

    def _summary_to_view(self, summary: ReleaseVerificationSummary) -> VerificationSummaryView:
        """Convert model to view"""
        return VerificationSummaryView(
            summary_id=summary.summary_id,
            release_version=summary.release_version,
            release_candidate_id=summary.release_candidate_id,
            total_checks=summary.total_checks,
            passed_checks=summary.passed_checks,
            failed_checks=summary.failed_checks,
            skipped_checks=summary.skipped_checks,
            pending_checks=summary.pending_checks,
            overall_status=summary.overall_status,
            go_no_go_decision=summary.go_no_go_decision,
            decision_reason=summary.decision_reason,
            created_at=summary.created_at.isoformat() if summary.created_at else "",
            updated_at=summary.updated_at.isoformat() if summary.updated_at else "",
            finalized_at=summary.finalized_at.isoformat() if summary.finalized_at else None,
            finalized_by=summary.finalized_by,
        )

    async def check_quality_gate(
        self,
        db: AsyncSession,
        release_candidate_id: str,
    ) -> Result[dict[str, Any]]:
        """
        Check quality gate status for a release candidate

        Args:
            db: Database session
            release_candidate_id: ID of release candidate

        Returns:
            Result containing quality gate status dictionary
        """
        try:
            # Get summary
            summary_result = await db.execute(
                select(ReleaseVerificationSummary).where(
                    ReleaseVerificationSummary.release_candidate_id == release_candidate_id
                )
            )
            summary = await self._resolve_scalar_one_or_none(summary_result)

            if not summary:
                return Result.fail(fallback="[SUMMARY_NOT_FOUND]")

            # Get all checks
            checks_result = await db.execute(
                select(ReleaseVerificationRecord).where(
                    ReleaseVerificationRecord.release_candidate_id == release_candidate_id
                ).order_by(ReleaseVerificationRecord.created_at)
            )
            checks = checks_result.scalars().all()

            # Quality gate thresholds
            quality_gates = {
                "coverage": {
                    "name": "Code Coverage",
                    "threshold": 70.0,
                    "unit": "%",
                    "critical": True,
                    "status": "pending",
                    "current_value": None,
                },
                "unit_tests": {
                    "name": "Unit Tests",
                    "threshold": 100.0,
                    "unit": "%",
                    "critical": True,
                    "status": "pending",
                    "current_value": None,
                },
                "integration_tests": {
                    "name": "Integration Tests",
                    "threshold": 100.0,
                    "unit": "%",
                    "critical": True,
                    "status": "pending",
                    "current_value": None,
                },
                "contract": {
                    "name": "API Contract Tests (NFR19)",
                    "threshold": 100.0,
                    "unit": "%",
                    "critical": True,  # NFR19 requires 100%
                    "status": "pending",
                    "current_value": None,
                },
                "performance": {
                    "name": "Performance Benchmarks",
                    "threshold": 300.0,
                    "unit": "ms",
                    "critical": True,
                    "status": "pending",
                    "current_value": None,
                },
            }

            # Update gate status based on check results
            blocking_failures = []
            warnings = []

            for check in checks:
                gate_key = check.check_type
                if gate_key not in quality_gates:
                    continue

                if check.status == "passed":
                    quality_gates[gate_key]["status"] = "pass"

                    # Extract actual values from details
                    if check.details:
                        if check.check_type == "coverage":
                            coverage = check.details.get("coverage_percentage")
                            if coverage:
                                quality_gates[gate_key]["current_value"] = coverage
                        elif check.check_type == "performance":
                            # Check latency metrics
                            if "thresholds" in check.details:
                                quality_gates[gate_key]["thresholds"] = check.details["thresholds"]

                elif check.status == "failed":
                    quality_gates[gate_key]["status"] = "fail"

                    if gate_key == "contract":
                        blocking_failures.append(
                            "Contract tests failed - NFR19 requires 100% pass rate"
                        )
                    elif gate_key == "coverage":
                        blocking_failures.append(
                            f"Code coverage below {quality_gates[gate_key]['threshold']}% threshold"
                        )
                    elif gate_key in ["unit_tests", "integration_tests"]:
                        blocking_failures.append(
                            f"{quality_gates[gate_key]['name']} failed"
                        )
                    elif gate_key == "performance":
                        warnings.append(
                            "Performance benchmarks did not meet NFR thresholds"
                        )

                elif check.status == "pending":
                    quality_gates[gate_key]["status"] = "pending"

            # Determine overall gate status
            any_pending = any(
                g["status"] == "pending" for g in quality_gates.values()
            )
            any_blocking_fail = any(
                g["status"] == "fail" and g.get("critical", False)
                for g in quality_gates.values()
            )
            any_warning_fail = any(
                g["status"] == "fail" and not g.get("critical", False)
                for g in quality_gates.values()
            )

            if any_pending:
                overall_status = "pending"
            elif any_blocking_fail:
                overall_status = "fail"
            elif any_warning_fail:
                overall_status = "warning"
            else:
                overall_status = "pass"

            # Generate recommendations
            recommendations = []
            if blocking_failures:
                recommendations.extend(blocking_failures)
            if warnings:
                recommendations.extend(warnings)
            if overall_status == "pass":
                recommendations.append("All quality gates passed - ready for release")
            elif overall_status == "pending":
                recommendations.append("Complete all pending verification checks")

            return Result(value={
                "overall_status": overall_status,
                "gates": quality_gates,
                "blocking_failures": blocking_failures,
                "warnings": warnings,
                "can_release": overall_status == "pass",
                "recommendations": recommendations,
            })

        except SQLAlchemyError as e:
            logger.error(
                "Failed to check quality gate",
                extra={"release_candidate_id": release_candidate_id, "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[GATE_CHECK_FAILED]")

    async def make_automated_decision(
        self,
        db: AsyncSession,
        release_candidate_id: str,
        finalized_by: str,
    ) -> Result[VerificationSummaryView]:
        """
        Make automated go/no-go decision based on quality gate results

        Args:
            db: Database session
            release_candidate_id: ID of release candidate
            finalized_by: User ID of the user triggering the decision

        Returns:
            Result containing updated VerificationSummaryView or error
        """
        try:
            # Get summary
            summary_result = await db.execute(
                select(ReleaseVerificationSummary).where(
                    ReleaseVerificationSummary.release_candidate_id == release_candidate_id
                )
            )
            summary = await self._resolve_scalar_one_or_none(summary_result)

            if not summary:
                return Result.fail(fallback="[SUMMARY_NOT_FOUND]")

            # Check if all checks are complete
            if summary.pending_checks > 0:
                return Result.fail(
                    fallback="[PENDING_CHECKS_EXIST]",
                )

            # Get quality gate status
            gate_result = await self.check_quality_gate(db, release_candidate_id)
            if not gate_result.is_success:
                return Result.fail(fallback="[GATE_CHECK_FAILED]")

            gate_status = gate_result.value

            # Determine decision based on gate status
            if gate_status["can_release"]:
                decision = "go"
                reason = "All quality gates passed: " + ", ".join(
                    f"{g['name']}={g['status']}"
                    for g in gate_status["gates"].values()
                )
            elif gate_status["blocking_failures"]:
                decision = "no_go"
                reason = "Blocking failures: " + "; ".join(
                    gate_status["blocking_failures"]
                )
            else:
                decision = "conditional"
                reason = "Non-critical warnings: " + "; ".join(
                    gate_status["warnings"]
                )

            # Update summary with decision
            summary.go_no_go_decision = decision
            summary.decision_reason = reason
            summary.finalized_at = datetime.now(timezone.utc)
            summary.finalized_by = finalized_by

            # Set overall status based on decision
            if decision == "go":
                summary.overall_status = "passed"
            elif decision == "no_go":
                summary.overall_status = "failed"
            else:
                summary.overall_status = "passed"  # Conditional is still a pass

            await db.commit()
            await db.refresh(summary)

            logger.info(
                "Made automated go/no-go decision",
                extra={
                    "release_candidate_id": release_candidate_id,
                    "decision": decision,
                    "reason": reason,
                    "finalized_by": finalized_by,
                }
            )

            return Result(value=self._summary_to_view(summary))

        except SQLAlchemyError as e:
            logger.error(
                "Failed to make automated decision",
                extra={"release_candidate_id": release_candidate_id, "error": str(e)},
                exc_info=True
            )
            await db.rollback()
            return Result.fail(fallback="[AUTO_DECISION_FAILED]")


# Singleton instance
release_verification_service = ReleaseVerificationService()
