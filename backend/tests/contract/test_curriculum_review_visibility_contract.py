from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.integration.test_curriculum_certification_review_flow import (
    CERTIFICATION_SESSION_ID,
    _auth_headers,
    _certification_plan,
    _create_completed_template_session,
    _create_user,
)

from curriculum_practice.models import PracticeTemplate


@pytest.mark.asyncio
@pytest.mark.contract
async def test_learner_cannot_access_certification_queue_or_reviewer_thinking(
    async_client,
    test_db: AsyncSession,
) -> None:
    learner = await _create_user(
        test_db, role="user", email_prefix="cert-contract-learner"
    )
    certification_template = PracticeTemplate(
        template_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        name="契约认证复核模板",
        description="certification contract template",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash="hash-certification-queue",
        curriculum_plan=_certification_plan("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    )
    test_db.add(certification_template)
    await test_db.commit()
    await _create_completed_template_session(
        test_db,
        user=learner,
        template=certification_template,
        session_id=CERTIFICATION_SESSION_ID,
        score=70.0,
    )

    queue_response = await async_client.get(
        "/api/v1/supervisor/certification-review-queue",
        headers=_auth_headers(learner),
    )

    assert queue_response.status_code == 403
    assert queue_response.json()["error"] == "[ADMIN_REQUIRED]"

    report_response = await async_client.get(
        f"/api/v1/supervisor/report-view/{CERTIFICATION_SESSION_ID}",
        headers=_auth_headers(learner),
    )
    assert report_response.status_code == 200
    assert "thinking_evidence" not in report_response.json()["data"]

    reviewer = await _create_user(
        test_db, role="admin", email_prefix="cert-contract-reviewer-for-calibration"
    )
    review_response = await async_client.get(
        "/api/v1/supervisor/certification-review-queue",
        headers=_auth_headers(reviewer),
    )
    review_id = review_response.json()["data"][0]["review_id"]

    calibration_response = await async_client.post(
        f"/api/v1/supervisor/reviews/{review_id}/score-calibrations",
        headers=_auth_headers(learner),
        json={
            "session_id": CERTIFICATION_SESSION_ID,
            "dimension": "template_stage_onboarding_certification_review",
            "ai_score": 70.0,
            "supervisor_score": 70.0,
            "calibration_label": "accurate",
        },
    )
    assert calibration_response.status_code == 403
    assert calibration_response.json()["error"] == "[ADMIN_REQUIRED]"


@pytest.mark.asyncio
@pytest.mark.contract
async def test_authorized_reviewer_can_view_certification_queue_thinking_evidence(
    async_client,
    test_db: AsyncSession,
) -> None:
    reviewer = await _create_user(
        test_db, role="admin", email_prefix="cert-contract-reviewer"
    )
    learner = await _create_user(
        test_db, role="user", email_prefix="cert-contract-owner"
    )
    certification_template = PracticeTemplate(
        template_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        name="授权认证复核模板",
        description="authorized certification contract template",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash="hash-certification-queue",
        curriculum_plan=_certification_plan("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    )
    test_db.add(certification_template)
    await test_db.commit()
    await _create_completed_template_session(
        test_db,
        user=learner,
        template=certification_template,
        session_id="bbbbbbbb-0000-0000-0000-bbbbbbbbbbbb",
        score=70.0,
    )

    response = await async_client.get(
        "/api/v1/supervisor/certification-review-queue",
        headers=_auth_headers(reviewer),
    )

    assert response.status_code == 200, response.json()
    item = response.json()["data"][0]
    assert item["evidence"]["thinking_evidence"][0]["thinking_text"] == (
        "Reviewer-only certification reasoning"
    )
