from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from common.db.models import (
    ConversationMessage,
    HighlightReviewShareAccessLog,
    PracticeSession,
    Scenario,
    SessionStatus,
)


async def _seed_completed_session_with_highlight(test_db, user):
    scenario = Scenario(scenario_type="sales", name="销售价值验证")
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=datetime.now(UTC) - timedelta(minutes=20),
        end_time=datetime.now(UTC) - timedelta(minutes=10),
        logic_score=88,
        accuracy_score=86,
        completeness_score=84,
        effectiveness_snapshot={"evaluable": True},
    )
    test_db.add(session)
    await test_db.flush()

    message = ConversationMessage(
        session_id=session.session_id,
        turn_number=4,
        role="user",
        content="客户电话 13812345678，邮箱 buyer@example.com；我们担心 ROI。",
        is_highlight=True,
        highlight_type="bad",
        highlight_reason="客户已经追问证据，这一轮需要补充 ROI。",
        ai_feedback="先给案例或数据，再确认客户是否认可。",
        sales_stage="objection",
    )
    test_db.add(message)
    await test_db.commit()
    return session, message


@pytest.mark.asyncio
async def test_highlight_review_persists_across_reads(
    async_client,
    auth_headers,
    test_db,
    test_user,
):
    session, message = await _seed_completed_session_with_highlight(test_db, test_user)

    save_response = await async_client.put(
        f"/api/v1/sessions/{session.session_id}/highlight-review",
        headers=auth_headers,
        json={
            "items": [
                {
                    "id": message.id,
                    "reason": "复盘原因",
                    "issue_label": "证据支撑",
                    "suggested_response": "先补一条客户 ROI 案例。",
                }
            ]
        },
    )

    assert save_response.status_code == 200
    saved = save_response.json()["data"]
    assert saved["schema_version"] == "highlight_review_v1"
    assert saved["items"][0]["message_id"] == message.id
    assert saved["items"][0]["content"].startswith("客户电话")
    assert saved["items"][0]["issue_label"] == "证据支撑"

    read_response = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/highlight-review",
        headers=auth_headers,
    )

    assert read_response.status_code == 200
    read_payload = read_response.json()["data"]
    assert read_payload["review_id"] == saved["review_id"]
    assert read_payload["items"][0]["suggested_response"] == "先补一条客户 ROI 案例。"


@pytest.mark.asyncio
async def test_wecom_share_requires_consent_ttl_revoke_audit_and_desensitizes_public_payload(
    async_client,
    auth_headers,
    test_db,
    test_user,
    monkeypatch,
):
    session, message = await _seed_completed_session_with_highlight(test_db, test_user)
    monkeypatch.setenv(
        "GROWTH_WECOM_SHARE_POLICY_JSON",
        json.dumps(
            {
                "version": "wecom_test_v1",
                "enabled": True,
                "adr_approved": True,
                "ttl_days": 3,
                "allowed_domains": ["internal.example.com"],
            }
        ),
    )

    await async_client.put(
        f"/api/v1/sessions/{session.session_id}/highlight-review",
        headers=auth_headers,
        json={"items": [{"id": message.id}]},
    )

    no_consent = await async_client.post(
        f"/api/v1/sessions/{session.session_id}/highlight-review/shares",
        headers=auth_headers,
        json={"channel": "wecom", "consent_granted": False},
    )
    assert no_consent.status_code == 400
    assert no_consent.json()["error"] == "[SHARE_CONSENT_REQUIRED]"

    share_response = await async_client.post(
        f"/api/v1/sessions/{session.session_id}/highlight-review/shares",
        headers=auth_headers,
        json={
            "channel": "wecom",
            "consent_granted": True,
            "consent_text": "同意脱敏分享",
            "ttl_days": 2,
        },
    )
    assert share_response.status_code == 200
    share = share_response.json()["data"]
    assert share["status"] == "active"
    assert share["ttl_days"] == 2
    assert share["share_token"]
    assert share["share_url"].endswith(share["public_api_path"])

    public_response = await async_client.get(share["public_api_path"])
    assert public_response.status_code == 200
    public_payload = public_response.json()["data"]
    public_item = public_payload["items"][0]
    assert public_payload["desensitization_version"] == "highlight_share_desensitized_v1"
    assert "13812345678" not in public_item["content_excerpt"]
    assert "buyer@example.com" not in public_item["content_excerpt"]
    assert "[phone]" in public_item["content_excerpt"]
    assert "[email]" in public_item["content_excerpt"]
    assert "audit" in public_payload["audit_notice"].lower()

    revoke_response = await async_client.post(
        f"/api/v1/sessions/{session.session_id}/highlight-review/shares/{share['share_id']}/revoke",
        headers=auth_headers,
        json={"reason": "测试撤销"},
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["data"]["status"] == "revoked"

    denied_response = await async_client.get(share["public_api_path"])
    assert denied_response.status_code == 410

    logs = (
        await test_db.execute(
            select(HighlightReviewShareAccessLog).where(
                HighlightReviewShareAccessLog.share_id == share["share_id"]
            )
        )
    ).scalars().all()
    assert {log.event_type for log in logs} >= {"created", "accessed", "revoked", "denied"}
