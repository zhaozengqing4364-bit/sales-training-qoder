from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from common.conversation.highlight_review_service import HighlightReviewService
from common.db.models import (
    ConversationMessage,
    HighlightReviewShareAccessLog,
    PracticeSession,
    Scenario,
    SessionStatus,
    User,
)


async def _seed_user_session_and_highlight(test_db):
    user = User(
        wechat_user_id="highlight-review-user",
        name="Highlight Review User",
        role="user",
    )
    scenario = Scenario(scenario_type="sales", name="销售价值验证")
    test_db.add_all([user, scenario])
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
    return user, session, message


@pytest.mark.asyncio
async def test_highlight_review_persists_across_reads(test_db):
    user, session, message = await _seed_user_session_and_highlight(test_db)
    service = HighlightReviewService()

    save_result = await service.save_review(
        db=test_db,
        session_id=str(session.session_id),
        current_user=user,
        title=None,
        items=[
            {
                "id": message.id,
                "reason": "复盘原因",
                "issue_label": "证据支撑",
                "suggested_response": "先补一条客户 ROI 案例。",
            }
        ],
    )

    assert save_result.is_success
    saved = save_result.value
    assert saved["schema_version"] == "highlight_review_v1"
    assert saved["items"][0]["message_id"] == message.id
    assert saved["items"][0]["content"].startswith("客户电话")
    assert saved["items"][0]["issue_label"] == "证据支撑"

    read_result = await service.get_review(
        db=test_db,
        session_id=str(session.session_id),
        current_user=user,
    )

    assert read_result.is_success
    read_payload = read_result.value
    assert read_payload["review_id"] == saved["review_id"]
    assert read_payload["items"][0]["suggested_response"] == "先补一条客户 ROI 案例。"


@pytest.mark.asyncio
async def test_wecom_share_requires_consent_ttl_revoke_audit_and_desensitizes_public_payload(
    test_db,
    monkeypatch,
):
    user, session, message = await _seed_user_session_and_highlight(test_db)
    service = HighlightReviewService()
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

    saved = await service.save_review(
        db=test_db,
        session_id=str(session.session_id),
        current_user=user,
        title=None,
        items=[{"id": message.id}],
    )
    assert saved.is_success

    no_consent = await service.create_share(
        db=test_db,
        session_id=str(session.session_id),
        current_user=user,
        channel="wecom",
        consent_granted=False,
        consent_text=None,
        ttl_days=None,
    )
    assert not no_consent.is_success
    assert no_consent.fallback == "[SHARE_CONSENT_REQUIRED]"

    share_result = await service.create_share(
        db=test_db,
        session_id=str(session.session_id),
        current_user=user,
        channel="wecom",
        consent_granted=True,
        consent_text="同意脱敏分享",
        ttl_days=2,
    )
    assert share_result.is_success
    share = share_result.value
    assert share["status"] == "active"
    assert share["ttl_days"] == 2
    assert share["share_token"]

    public_result = await service.get_shared_review(
        db=test_db,
        token=share["share_token"],
        viewer_label="coach",
        client_hint="127.0.0.1|pytest",
    )
    assert public_result.is_success
    public_payload = public_result.value
    public_item = public_payload["items"][0]
    assert (
        public_payload["desensitization_version"] == "highlight_share_desensitized_v1"
    )
    assert "13812345678" not in public_item["content_excerpt"]
    assert "buyer@example.com" not in public_item["content_excerpt"]
    assert "[phone]" in public_item["content_excerpt"]
    assert "[email]" in public_item["content_excerpt"]
    assert "audit" in public_payload["audit_notice"].lower()

    revoke_result = await service.revoke_share(
        db=test_db,
        session_id=str(session.session_id),
        share_id=share["share_id"],
        current_user=user,
        reason="测试撤销",
    )
    assert revoke_result.is_success
    assert revoke_result.value["status"] == "revoked"

    denied_response = await service.get_shared_review(
        db=test_db,
        token=share["share_token"],
        viewer_label="coach",
        client_hint="127.0.0.1|pytest",
    )
    assert not denied_response.is_success
    assert denied_response.fallback == "[HIGHLIGHT_SHARE_INACTIVE]"

    logs = (
        (
            await test_db.execute(
                select(HighlightReviewShareAccessLog).where(
                    HighlightReviewShareAccessLog.share_id == share["share_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert {log.event_type for log in logs} >= {
        "created",
        "accessed",
        "revoked",
        "denied",
    }
