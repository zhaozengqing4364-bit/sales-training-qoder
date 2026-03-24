from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.conversation.session_evidence import SessionEvidenceService


def _make_effectiveness_snapshot(*, evaluable: bool, reason: str | None) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": False,
            "pass_4step_structure": False,
        },
        "main_capability_passed": not evaluable,
        "overall_result": "fail",
        "metrics": {
            "continuous_speech_seconds": 0.0,
            "filler_rate_per_100_words": 0.0,
            "offtopic_turn_count": 0.0,
            "offtopic_max_streak": 0.0,
            "structure_coverage": 0.0,
        },
        "main_issue": {
            "issue_type": "main_capability_not_passed",
            "issue_text": "证据不足，当前无法评估。",
            "recovery_rule": "请先完成至少一轮有效互动后再结束。",
        },
        "next_goal": {
            "goal_type": "main_capability_focus",
            "goal_text": "先完成一轮有效互动再评估。",
            "rule": "补齐用户表达和AI回应后再结束。",
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": reason,
    }


def _make_stale_sales_snapshot() -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "metrics": {
            "value_expression_score": 82.0,
            "customer_benefit_score": 78.0,
            "evidence_usage_score": 61.0,
            "objection_handling_score": 74.0,
            "next_step_score": 69.0,
            "value_articulation_rollup": 80.0,
            "evidence_benefit_rollup": 69.5,
            "objection_progress_rollup": 71.5,
        },
        "main_issue": {
            "issue_type": "value_translation_gap",
            "issue_text": "产品价值说得太功能化，还没有翻译成客户收益与 ROI。",
            "recovery_rule": "下一轮先把价值翻译成客户收益，再回应价格与竞品问题。",
        },
        "next_goal": {
            "goal_type": "value_to_benefit_translation",
            "goal_text": "先把产品价值翻译成客户收益，再进入方案说明。",
            "rule": "至少说清一个客户场景、一个收益指标、一个量化变化。",
        },
        "version": "rule_v1",
        "evaluable": True,
        "not_evaluable_reason": None,
    }


class TestSessionEvidenceService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return SessionEvidenceService(mock_db)

    @pytest.fixture
    def sample_session_id(self) -> str:
        return str(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_projection_normalizes_legacy_scores_and_logs_projection_completeness(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=81.0,
            accuracy_score=84.0,
            completeness_score=78.0,
            total_duration_seconds=135,
            start_time=datetime.now(UTC) - timedelta(seconds=135),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=_make_effectiveness_snapshot(
                evaluable=True,
                reason=None,
            ),
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="您好，我想先了解下贵司目前怎么做客户回访。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                fuzzy_words=None,
                transcript_metadata={"source": "legacy"},
                sales_stage="opening",
                score_snapshot={"overall": 72, "dimension_scores": {"沟通技巧": 70}},
                ai_feedback="先确认客户背景",
                is_highlight=False,
                highlight_type=None,
                highlight_reason=None,
            ),
            SimpleNamespace(
                id="msg-2",
                session_id=sample_session_id,
                turn_number=2,
                role="assistant",
                content="目前主要靠人工跟进，信息容易丢失。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1800,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="discovery",
                score_snapshot={"overall_score": 86, "dimension_scores": {"沟通技巧": 84}},
                ai_feedback="继续追问影响范围",
                is_highlight=False,
                highlight_type=None,
                highlight_reason=None,
            ),
        ]

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = messages
        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        with patch("common.conversation.session_evidence.logger") as logger:
            result = await service.get_projection(
                session_id=sample_session_id,
                require_completed=True,
            )

        assert result.is_success
        projection = result.value
        assert projection.session_id == sample_session_id
        assert projection.overall_score == pytest.approx(81.0)
        assert projection.messages[0]["score_snapshot"]["overall_score"] == 72.0
        assert "overall" not in projection.messages[0]["score_snapshot"]
        assert projection.stage_summary == [
            {"stage": "opening", "duration_ms": 1500, "score": 72},
            {"stage": "discovery", "duration_ms": 1800, "score": 86},
        ]
        assert projection.evaluable is True
        assert projection.not_evaluable_reason is None
        assert projection.evidence_completeness["message_count"] == 2
        assert projection.evidence_completeness["legacy_score_key_used"] is True
        assert projection.evidence_completeness["complete"] is True

        logger.info.assert_called_once()
        call = logger.info.call_args
        assert call.args[0] == "practice_session_evidence_projection_built"
        assert call.kwargs["session_id"] == sample_session_id
        assert call.kwargs["message_count"] == 2
        assert call.kwargs["legacy_score_key_used"] is True
        assert call.kwargs["projection_complete"] is True

    @pytest.mark.asyncio
    async def test_get_projection_falls_back_to_latest_message_scores_when_session_scores_missing(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=None,
            accuracy_score=None,
            completeness_score=None,
            total_duration_seconds=96,
            start_time=datetime.now(UTC) - timedelta(seconds=96),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=None,
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="我们预算其实卡得比较紧。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1200,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 89,
                    "dimension_scores": {
                        "professional": 88,
                        "communication": 82,
                        "discovery": 76,
                    },
                },
                ai_feedback="继续确认预算审批链路",
                is_highlight=False,
                highlight_type=None,
                highlight_reason=None,
            ),
        ]

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = messages
        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        result = await service.get_projection(
            session_id=sample_session_id,
            require_completed=True,
        )

        assert result.is_success
        projection = result.value
        assert projection.logic_score == pytest.approx(88.0)
        assert projection.accuracy_score == pytest.approx(82.0)
        assert projection.completeness_score == pytest.approx(76.0)
        assert projection.overall_score == pytest.approx(82.0)
        assert projection.evaluable is True
        assert projection.not_evaluable_reason is None
        assert projection.evidence_completeness["session_scores"] is False
        assert projection.evidence_completeness["message_scores"] == 1

    @pytest.mark.asyncio
    async def test_get_projection_sales_alignment_overrides_stale_snapshot_from_persisted_sales_evidence(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        stale_snapshot = _make_stale_sales_snapshot()
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=80.0,
            accuracy_score=69.5,
            completeness_score=71.5,
            total_duration_seconds=180,
            start_time=datetime.now(UTC) - timedelta(seconds=180),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=stale_snapshot,
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="ROI 这一块你们有真实案例吗？",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1600,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 82.0,
                    "dimension_scores": {
                        "价值表达": 84.0,
                        "客户收益连接": 80.0,
                        "证据使用": 58.0,
                        "异议处理": 76.0,
                        "推进下一步": 72.0,
                    },
                },
                ai_feedback="补充案例和 ROI 数据",
                is_highlight=False,
                highlight_type=None,
                highlight_reason=None,
            ),
        ]

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = messages
        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        with patch("common.conversation.session_evidence.logger") as logger:
            result = await service.get_projection(
                session_id=sample_session_id,
                require_completed=True,
            )

        assert result.is_success
        projection = result.value
        assert projection.main_issue["issue_type"] == "evidence_gap"
        assert projection.next_goal["goal_type"] == "evidence_backing"
        assert projection.effectiveness_snapshot["main_issue"]["issue_type"] == "evidence_gap"
        assert projection.effectiveness_snapshot["next_goal"]["goal_type"] == "evidence_backing"
        assert session.effectiveness_snapshot["main_issue"]["issue_type"] == "value_translation_gap"
        assert session.effectiveness_snapshot["next_goal"]["goal_type"] == "value_to_benefit_translation"

        logger.info.assert_called_once()
        call = logger.info.call_args
        assert call.kwargs["sales_alignment_used"] is True
        assert call.kwargs["sales_alignment_stage_key"] == "discovery"
        assert call.kwargs["sales_alignment_focus_type"] == "evidence_gap"
        assert call.kwargs["sales_alignment_fallback_reason"] is None

    @pytest.mark.asyncio
    async def test_get_projection_sales_alignment_preserves_insufficient_sales_evidence_fallback(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        snapshot = _make_effectiveness_snapshot(
            evaluable=False,
            reason="INSUFFICIENT_TURN_DATA",
        )
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=0.0,
            accuracy_score=0.0,
            completeness_score=0.0,
            total_duration_seconds=0,
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=snapshot,
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="我们先看看这个方向。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1200,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="discovery",
                score_snapshot={"overall_score": 81.0},
                ai_feedback="继续追问客户现状",
                is_highlight=False,
                highlight_type=None,
                highlight_reason=None,
            ),
        ]

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = messages
        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        with patch("common.conversation.session_evidence.logger") as logger:
            result = await service.get_projection(
                session_id=sample_session_id,
                require_completed=True,
            )

        assert result.is_success
        projection = result.value
        assert projection.main_issue == snapshot["main_issue"]
        assert projection.next_goal == snapshot["next_goal"]
        assert projection.evaluable is False
        assert projection.not_evaluable_reason == "INSUFFICIENT_TURN_DATA"
        assert projection.evidence_completeness["message_scores"] == 1
        assert projection.evidence_completeness["stage_evidence"] == 1

        logger.info.assert_called_once()
        call = logger.info.call_args
        assert call.kwargs["sales_alignment_used"] is False
        assert call.kwargs["sales_alignment_stage_key"] == "discovery"
        assert call.kwargs["sales_alignment_focus_type"] is None
        assert call.kwargs["sales_alignment_fallback_reason"] == "missing_dimension_scores"
