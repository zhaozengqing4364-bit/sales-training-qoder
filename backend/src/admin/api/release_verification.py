"""
Release Verification API - Endpoints for release gate verification management

Implements FR40: Release gate check results recording and tracking

References:
- Requirements: FR40
- Constitution Principles:
  - I. NO ERROR POPUPS - Graceful degradation
  - VI. Data privacy - Admin-only access
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.release_verification_service import (
    release_verification_service,
)
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/release-verification", tags=["release-verification"])


# Request/Response schemas
class CreateReleaseCandidateRequest(BaseModel):
    """Request to create a new release candidate"""
    release_version: str = Field(..., description="Version string (e.g., v1.2.0)")
    release_candidate_id: str = Field(..., description="Unique RC identifier")


class VerificationCheckInput(BaseModel):
    """Input for a verification check"""
    check_type: Literal["migration", "contract", "performance", "manual"]
    check_name: str
    check_description: str | None = None


class CreateReleaseCandidateWithChecksRequest(BaseModel):
    """Request to create RC with custom checks"""
    release_version: str
    release_candidate_id: str
    checks: list[VerificationCheckInput] | None = None


class UpdateCheckResultRequest(BaseModel):
    """Request to update a check result"""
    status: Literal["pending", "passed", "failed", "skipped"]
    passed: bool
    details: dict[str, Any] | None = None
    error_message: str | None = None
    duration_ms: int | None = None


class GoNoGoDecisionRequest(BaseModel):
    """Request to make a go/no-go decision"""
    decision: Literal["go", "no_go", "conditional"]
    reason: str


def success_response(data: Any, trace_id: str | None = None) -> dict:
    """Create unified success response"""
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id()
    }


def error_response(error_code: str, message: str, trace_id: str | None = None) -> dict:
    """Create unified error response"""
    return {
        "success": False,
        "error": error_code,
        "message": message,
        "trace_id": trace_id or get_trace_id()
    }


@router.post("/candidates", response_model=dict)
async def create_release_candidate(
    request: CreateReleaseCandidateWithChecksRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Create a new release candidate with verification checks

    Creates a release candidate with default or custom verification checks:
    - Migration check
    - Contract tests (NFR19: 100% required)
    - Performance benchmarks
    - Manual checklist
    """
    logger.info(
        "Creating release candidate",
        extra={
            "release_version": request.release_version,
            "release_candidate_id": request.release_candidate_id,
            "user_id": str(current_user.user_id)
        }
    )

    checks = None
    if request.checks:
        from common.analytics.release_verification_service import (
            VerificationCheckInput as CheckInput,
        )
        checks = [
            CheckInput(
                check_type=c.check_type,
                check_name=c.check_name,
                check_description=c.check_description
            )
            for c in request.checks
        ]

    result = await release_verification_service.create_release_candidate(
        db=db,
        release_version=request.release_version,
        release_candidate_id=request.release_candidate_id,
        checks=checks,
        created_by=str(current_user.user_id)
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[CREATE_FAILED]",
            "Failed to create release candidate"
        )

    from dataclasses import asdict
    return success_response(asdict(result.value))


@router.get("/candidates", response_model=dict)
async def list_release_candidates(
    status: Literal["pending", "passed", "failed"] | None = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    List release candidates with optional status filter
    """
    logger.info(
        "Listing release candidates",
        extra={
            "status": status,
            "user_id": str(current_user.user_id)
        }
    )

    result = await release_verification_service.list_release_candidates(
        db=db,
        status=status,
        limit=limit,
        offset=offset
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[LIST_FAILED]",
            "Failed to list release candidates"
        )

    from dataclasses import asdict
    return success_response({
        "candidates": [asdict(c) for c in result.value],
        "total": len(result.value)
    })


@router.get("/candidates/latest", response_model=dict)
async def get_latest_release_candidate(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get the latest release candidate
    """
    result = await release_verification_service.get_latest_release_candidate(db=db)

    if not result.is_success:
        return error_response(
            result.fallback or "[GET_LATEST_FAILED]",
            "Failed to get latest release candidate"
        )

    if result.value is None:
        return success_response({"candidate": None})

    from dataclasses import asdict
    return success_response({"candidate": asdict(result.value)})


@router.get("/candidates/{release_candidate_id}/report", response_model=dict)
async def get_verification_report(
    release_candidate_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get complete verification report for a release candidate

    Returns:
    - Summary with counts and overall status
    - All verification check records
    - Gate status summary (per check type)
    - Recommendations
    """
    logger.info(
        "Getting verification report",
        extra={
            "release_candidate_id": release_candidate_id,
            "user_id": str(current_user.user_id)
        }
    )

    result = await release_verification_service.get_verification_report(
        db=db,
        release_candidate_id=release_candidate_id
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[REPORT_FAILED]",
            "Failed to get verification report"
        )

    from dataclasses import asdict
    report = result.value
    return success_response({
        "summary": asdict(report.summary),
        "checks": [asdict(c) for c in report.checks],
        "gate_status": report.gate_status,
        "recommendations": report.recommendations
    })


@router.put("/checks/{record_id}", response_model=dict)
async def update_check_result(
    record_id: str,
    request: UpdateCheckResultRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Update a verification check result

    Records the outcome of a verification check including:
    - Pass/fail status
    - Execution details
    - Error message if failed
    - Duration in milliseconds
    """
    logger.info(
        "Updating check result",
        extra={
            "record_id": record_id,
            "status": request.status,
            "passed": request.passed,
            "user_id": str(current_user.user_id)
        }
    )

    result = await release_verification_service.update_check_result(
        db=db,
        record_id=record_id,
        status=request.status,
        passed=request.passed,
        details=request.details,
        error_message=request.error_message,
        duration_ms=request.duration_ms,
        executed_by=str(current_user.user_id)
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[UPDATE_FAILED]",
            "Failed to update check result"
        )

    from dataclasses import asdict
    return success_response(asdict(result.value))


@router.post("/candidates/{release_candidate_id}/decision", response_model=dict)
async def make_go_no_go_decision(
    release_candidate_id: str,
    request: GoNoGoDecisionRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Make a go/no-go decision for a release candidate

    Records the final decision for a release candidate:
    - go: All checks passed, ready for release
    - no_go: Critical issues found, not ready
    - conditional: Approved with conditions

    Note: Cannot make decision if pending checks exist
    """
    logger.info(
        "Making go/no-go decision",
        extra={
            "release_candidate_id": release_candidate_id,
            "decision": request.decision,
            "user_id": str(current_user.user_id)
        }
    )

    result = await release_verification_service.make_go_no_go_decision(
        db=db,
        release_candidate_id=release_candidate_id,
        decision=request.decision,
        reason=request.reason,
        finalized_by=str(current_user.user_id)
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[DECISION_FAILED]",
            "Failed to make go/no-go decision"
        )

    from dataclasses import asdict
    return success_response(asdict(result.value))


@router.post("/candidates/{release_candidate_id}/run-verification", response_model=dict)
async def run_automated_verification(
    release_candidate_id: str,
    skip_checks: list[str] | None = Query(None, description="List of check types to skip"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Run automated verification checks for a release candidate

    This endpoint triggers the full automated verification pipeline:
    1. Unit tests with coverage
    2. Integration tests
    3. Contract tests (NFR19: 100% required)
    4. Performance benchmarks

    Quality Gates:
    - Code coverage >= 70%
    - Contract tests 100% pass rate
    - Performance: P95 latency < 300ms

    Returns:
        Verification results with pass/fail status per check
    """
    logger.info(
        "Starting automated verification",
        extra={
            "release_candidate_id": release_candidate_id,
            "skip_checks": skip_checks,
            "user_id": str(current_user.user_id)
        }
    )

    # Import here to avoid circular dependency
    from common.analytics.verification_runner import verification_runner

    result = await verification_runner.run_all_checks(
        db=db,
        release_candidate_id=release_candidate_id,
        skip_checks=skip_checks
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[VERIFICATION_FAILED]",
            "Automated verification failed to execute"
        )

    # Commit all database updates made by runner
    await db.commit()

    logger.info(
        "Automated verification completed",
        extra={
            "release_candidate_id": release_candidate_id,
            "summary": result.value.get("summary", {})
        }
    )

    return success_response(result.value)


@router.get("/candidates/{release_candidate_id}/quality-gate", response_model=dict)
async def check_quality_gate_status(
    release_candidate_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Check quality gate status for a release candidate

    Returns:
        - Overall gate status (pass/fail/pending)
        - Individual gate results with thresholds
        - Blocking issues preventing release
        - Recommendations for passing gates
    """
    logger.info(
        "Checking quality gate status",
        extra={
            "release_candidate_id": release_candidate_id,
            "user_id": str(current_user.user_id)
        }
    )

    result = await release_verification_service.check_quality_gate(
        db=db,
        release_candidate_id=release_candidate_id
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[GATE_CHECK_FAILED]",
            "Failed to check quality gate status"
        )

    return success_response(result.value)


@router.post("/candidates/{release_candidate_id}/auto-decision", response_model=dict)
async def make_automated_decision(
    release_candidate_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Make automated go/no-go decision based on quality gate results

    Automatically determines if a release candidate should proceed:
    - GO: All quality gates pass, no blocking failures
    - NO_GO: Critical gates fail (contract tests, coverage below threshold)
    - CONDITIONAL: Non-critical gates fail but release may proceed with warning

    Note: All verification checks must be complete before making decision
    """
    logger.info(
        "Making automated go/no-go decision",
        extra={
            "release_candidate_id": release_candidate_id,
            "user_id": str(current_user.user_id)
        }
    )

    result = await release_verification_service.make_automated_decision(
        db=db,
        release_candidate_id=release_candidate_id,
        finalized_by=str(current_user.user_id)
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[AUTO_DECISION_FAILED]",
            result.fallback or "Failed to make automated decision"
        )

    from dataclasses import asdict
    return success_response(asdict(result.value))
