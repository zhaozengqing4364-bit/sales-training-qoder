"""Integration regressions for fire-and-forget report finalization using the trigger's own DB session."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import agent.models  # noqa: F401  # ensure Agent/Persona tables are registered on Base metadata for sqlite tests
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import evaluation.services.report_generation_trigger as trigger_module
from common.conversation.models import ConversationMessage
from common.db.models import PracticeSession, Scenario, SessionStatus, User
from common.error_handling.result import Result
from evaluation.services.report_generation_trigger import trigger_report_generation


async def _seed_sales_session(
    db_session: AsyncSession,
    *,
    user_id: str,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"fire_and_forget_sales_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        scenario_id=scenario.scenario_id,
        status=SessionStatus.SCORING.value,
        report_status="processing",
        logic_score=84.0,
        accuracy_score=82.0,
        completeness_score=80.0,
        total_duration_seconds=180,
        effectiveness_snapshot={
            "pass_flags": {
                "pass_3min_flow": True,
                "pass_5turn_defense": True,
                "pass_4step_structure": False,
            },
            "main_capability_passed": False,
            "overall_result": "fail",
            "main_issue": {
                "issue_type": "evidence_gap",
                "issue_text": "客户要案例，但这一轮还没给出证据。",
                "recovery_rule": "下一轮先补案例和 ROI 数字。",
            },
            "next_goal": {
                "goal_type": "evidence_backing",
                "goal_text": "下一轮优先补一条 ROI 证据。",
                "rule": "至少补一个案例或量化收益。",
            },
            "evaluable": True,
            "not_evaluable_reason": None,
        },
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="assistant",
                content="您现在最想先看哪类 ROI 证明？",
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                sales_stage="discovery",
                score_snapshot={"overall_score": 82},
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="user",
                content="我们还是想先看同行案例和回收周期。",
                timestamp=datetime.now(UTC),
                duration_ms=2100,
                sales_stage="objection",
                score_snapshot={"overall_score": 81},
                is_highlight=True,
                highlight_type="bad",
                highlight_reason="客户已经追问 ROI 证据。",
            ),
        ]
    )
    await db_session.commit()
    await db_session.refresh(session)
    return session


def _patch_trigger_to_use_test_engine(
    monkeypatch: pytest.MonkeyPatch,
    session_factory,
    report_result: Result,
) -> AsyncMock:
    mock_report_service = AsyncMock()
    mock_report_service.generate_report = AsyncMock(return_value=report_result)

    def _init_report_service(self) -> None:
        self.report_service = mock_report_service

    monkeypatch.setattr(trigger_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(
        trigger_module.ReportGenerationTrigger,
        "_init_report_service",
        _init_report_service,
    )
    return mock_report_service


@pytest.mark.asyncio
async def test_fire_and_forget_trigger_persists_completed_sales_session_on_own_session(
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    session = await _seed_sales_session(test_db, user_id=str(test_user.user_id))
    session_factory = async_sessionmaker(
        test_db.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    mock_report_service = _patch_trigger_to_use_test_engine(
        monkeypatch,
        session_factory,
        Result.ok(SimpleNamespace(overall_score=85.0)),
    )

    await trigger_report_generation(str(session.session_id), "sales", db=None)

    async with session_factory() as verify_db:
        persisted = (
            await verify_db.execute(
                select(PracticeSession).where(
                    PracticeSession.session_id == str(session.session_id)
                )
            )
        ).scalar_one()

    mock_report_service.generate_report.assert_awaited_once_with(
        session_id=str(session.session_id),
        scenario_type="sales",
    )
    assert persisted.report_status == "completed"
    assert persisted.report_error is None
    assert persisted.status == SessionStatus.COMPLETED.value
    assert persisted.report_generated_at is not None


@pytest.mark.asyncio
async def test_fire_and_forget_trigger_persists_failed_report_and_completed_sales_session_on_own_session(
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    session = await _seed_sales_session(test_db, user_id=str(test_user.user_id))
    session_factory = async_sessionmaker(
        test_db.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    mock_report_service = _patch_trigger_to_use_test_engine(
        monkeypatch,
        session_factory,
        Result.fail("[ENHANCED_REPORT_FAILED]"),
    )

    await trigger_report_generation(str(session.session_id), "sales", db=None)

    async with session_factory() as verify_db:
        persisted = (
            await verify_db.execute(
                select(PracticeSession).where(
                    PracticeSession.session_id == str(session.session_id)
                )
            )
        ).scalar_one()

    mock_report_service.generate_report.assert_awaited_once_with(
        session_id=str(session.session_id),
        scenario_type="sales",
    )
    assert persisted.report_status == "failed"
    assert persisted.report_error == "[ENHANCED_REPORT_FAILED]"
    assert persisted.status == SessionStatus.COMPLETED.value
