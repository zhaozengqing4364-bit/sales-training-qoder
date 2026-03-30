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


def _make_conclusion_evidence(
    *,
    retrieval_available: bool = True,
    retrieval_reason: str | None = None,
    transcript_available: bool = True,
    audio_available: bool = True,
    audio_reason: str | None = None,
) -> dict[str, object]:
    return {
        "main_issue": {
            "retrieval_source": {
                "available": retrieval_available,
                "reason": None if retrieval_available else retrieval_reason,
            },
            "transcript_source": {
                "available": transcript_available,
                "turn_count": 1 if transcript_available else 0,
            },
            "audio_source": {
                "available": audio_available,
                "reason": None if audio_available else audio_reason,
            },
        },
        "next_goal": {
            "retrieval_source": {
                "available": retrieval_available,
                "reason": None if retrieval_available else retrieval_reason,
            },
            "transcript_source": {
                "available": transcript_available,
                "turn_count": 1 if transcript_available else 0,
            },
            "audio_source": {
                "available": audio_available,
                "reason": None if audio_available else audio_reason,
            },
        },
        "claim_truth": {
            "retrieval_source": {
                "available": retrieval_available,
                "reason": None if retrieval_available else retrieval_reason,
            },
            "transcript_source": {
                "available": transcript_available,
                "turn_count": 1 if transcript_available else 0,
            },
            "audio_source": {
                "available": audio_available,
                "reason": None if audio_available else audio_reason,
            },
        },
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

        assert logger.info.call_count == 3
        first_call = logger.info.call_args_list[0]
        second_call = logger.info.call_args_list[1]
        third_call = logger.info.call_args_list[2]

        assert first_call.args[0] == "projection_conclusion_evidence_built"
        assert first_call.kwargs["retrieval_available"] is False
        assert first_call.kwargs["transcript_available"] is True
        assert first_call.kwargs["audio_available"] is True

        assert second_call.args[0] == "projection_evidence_degradation_built"
        assert second_call.kwargs["retrieval_status"] == "degraded"
        assert second_call.kwargs["transcript_status"] == "ok"
        assert second_call.kwargs["audio_status"] == "ok"
        assert second_call.kwargs["enhanced_report_status"] == "ok"

        assert third_call.args[0] == "practice_session_evidence_projection_built"
        assert third_call.kwargs["session_id"] == sample_session_id
        assert third_call.kwargs["message_count"] == 2
        assert third_call.kwargs["legacy_score_key_used"] is True
        assert third_call.kwargs["projection_complete"] is True

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
        assert projection.effectiveness_snapshot["claim_truth"]["status"] == "weak_evidence"
        assert projection.effectiveness_snapshot["claim_truth"]["source"] == "score_snapshot"
        assert session.effectiveness_snapshot["main_issue"]["issue_type"] == "value_translation_gap"
        assert session.effectiveness_snapshot["next_goal"]["goal_type"] == "value_to_benefit_translation"

        assert logger.info.call_count == 3
        first_call = logger.info.call_args_list[0]
        second_call = logger.info.call_args_list[1]
        third_call = logger.info.call_args_list[2]

        assert first_call.args[0] == "projection_conclusion_evidence_built"
        assert first_call.kwargs["retrieval_available"] is False
        assert first_call.kwargs["transcript_available"] is True
        assert first_call.kwargs["audio_available"] is True

        assert second_call.args[0] == "projection_evidence_degradation_built"
        assert second_call.kwargs["retrieval_status"] == "degraded"
        assert second_call.kwargs["transcript_status"] == "ok"
        assert second_call.kwargs["audio_status"] == "ok"
        assert second_call.kwargs["enhanced_report_status"] == "ok"

        assert third_call.args[0] == "practice_session_evidence_projection_built"
        assert third_call.kwargs["sales_alignment_used"] is True
        assert third_call.kwargs["sales_alignment_stage_key"] == "discovery"
        assert third_call.kwargs["sales_alignment_focus_type"] == "evidence_gap"
        assert third_call.kwargs["sales_alignment_fallback_reason"] is None

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
        assert projection.effectiveness_snapshot["claim_truth"]["status"] == "evidence_pending"
        assert projection.effectiveness_snapshot["claim_truth"]["source"] == "fallback_snapshot"
        assert projection.evaluable is False
        assert projection.not_evaluable_reason == "INSUFFICIENT_TURN_DATA"
        assert projection.evidence_completeness["message_scores"] == 1
        assert projection.evidence_completeness["stage_evidence"] == 1

        assert logger.info.call_count == 3
        first_call = logger.info.call_args_list[0]
        second_call = logger.info.call_args_list[1]
        third_call = logger.info.call_args_list[2]

        assert first_call.args[0] == "projection_conclusion_evidence_built"
        assert first_call.kwargs["retrieval_available"] is False
        assert first_call.kwargs["transcript_available"] is True
        assert first_call.kwargs["audio_available"] is True

        assert second_call.args[0] == "projection_evidence_degradation_built"
        assert second_call.kwargs["retrieval_status"] == "degraded"
        assert second_call.kwargs["transcript_status"] == "ok"
        assert second_call.kwargs["audio_status"] == "ok"
        assert second_call.kwargs["enhanced_report_status"] == "ok"

        assert third_call.args[0] == "practice_session_evidence_projection_built"
        assert third_call.kwargs["sales_alignment_used"] is False
        assert third_call.kwargs["sales_alignment_stage_key"] == "discovery"
        assert third_call.kwargs["sales_alignment_focus_type"] is None
        assert third_call.kwargs["sales_alignment_fallback_reason"] == "missing_dimension_scores"

    @pytest.mark.asyncio
    async def test_get_projection_prefers_latest_open_objection_ledger_for_sales_issue_and_next_goal(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=80.0,
            accuracy_score=78.0,
            completeness_score=74.0,
            total_duration_seconds=180,
            start_time=datetime.now(UTC) - timedelta(seconds=180),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=_make_stale_sales_snapshot(),
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="我们后面再看具体案例。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1600,
                fuzzy_words=None,
                transcript_metadata={
                    "objection_ledger": {
                        "objection_family": "roi_proof",
                        "promised_proof": "补充同类客户 ROI 案例",
                        "next_expected_evidence": "给出 6 个月回本测算",
                        "closure_state": "open",
                    }
                },
                sales_stage="closing",
                score_snapshot={
                    "overall_score": 79.0,
                    "dimension_scores": {
                        "价值表达": 83.0,
                        "客户收益连接": 80.0,
                        "证据使用": 84.0,
                        "异议处理": 76.0,
                        "推进下一步": 58.0,
                    },
                    "suggestions": ["先锁定试点时间"],
                },
                ai_feedback="先锁定试点时间。",
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
        assert projection.main_issue == {
            "issue_type": "evidence_gap",
            "issue_text": "客户持续追问 ROI / 案例证明，但这条证据直到结束都没有补上。",
            "recovery_rule": "下一轮先补充同类客户 ROI 案例，再给出 6 个月回本测算。",
        }
        assert projection.next_goal == {
            "goal_type": "evidence_backing",
            "goal_text": "下一轮优先给出 6 个月回本测算，别让 ROI 证明再次悬空。",
            "rule": "至少先补一条 ROI / 案例证据；如果暂时给不出，就明确承认缺口。",
        }
        assert projection.effectiveness_snapshot["main_issue"] == projection.main_issue
        assert projection.effectiveness_snapshot["next_goal"] == projection.next_goal
        assert projection.effectiveness_snapshot["claim_truth"]["status"] == "evidence_pending"
        assert projection.effectiveness_snapshot["claim_truth"]["source"] == "objection_ledger"
        assert projection.sales_alignment_used is True
        assert projection.sales_alignment_focus_type == "evidence_gap"

    @pytest.mark.asyncio
    async def test_get_projection_marks_gap_acknowledged_claims_as_unsupported(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=79.0,
            accuracy_score=68.0,
            completeness_score=72.0,
            total_duration_seconds=180,
            start_time=datetime.now(UTC) - timedelta(seconds=180),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=_make_stale_sales_snapshot(),
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="这个证明我们暂时给不出来。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                fuzzy_words=None,
                transcript_metadata={
                    "objection_ledger": {
                        "objection_family": "roi_proof",
                        "promised_proof": "补充同类客户 ROI 案例",
                        "next_expected_evidence": "给出 6 个月回本测算",
                        "closure_state": "gap_acknowledged",
                    }
                },
                sales_stage="objection",
                score_snapshot={
                    "overall_score": 73.0,
                    "dimension_scores": {
                        "价值表达": 80.0,
                        "客户收益连接": 76.0,
                        "证据使用": 46.0,
                        "异议处理": 64.0,
                        "推进下一步": 70.0,
                    },
                },
                ai_feedback="先明确当前缺口，再约定补齐时点。",
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
        assert projection.effectiveness_snapshot["claim_truth"]["status"] == "unsupported_claim"
        assert projection.effectiveness_snapshot["claim_truth"]["source"] == "objection_ledger"

    @pytest.mark.asyncio
    async def test_get_projection_marks_evidence_provided_claims_as_verified_when_support_is_strong(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=84.0,
            accuracy_score=82.0,
            completeness_score=78.0,
            total_duration_seconds=180,
            start_time=datetime.now(UTC) - timedelta(seconds=180),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=_make_stale_sales_snapshot(),
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="我们给了案例和回本周期。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                fuzzy_words=None,
                transcript_metadata={
                    "objection_ledger": {
                        "objection_family": "roi_proof",
                        "promised_proof": "补充同类客户 ROI 案例",
                        "next_expected_evidence": "给出 6 个月回本测算",
                        "closure_state": "evidence_provided",
                    }
                },
                sales_stage="closing",
                score_snapshot={
                    "overall_score": 84.0,
                    "dimension_scores": {
                        "价值表达": 82.0,
                        "客户收益连接": 81.0,
                        "证据使用": 88.0,
                        "异议处理": 79.0,
                        "推进下一步": 58.0,
                    },
                },
                ai_feedback="证据已经到位，继续锁定下一步。",
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
        assert projection.effectiveness_snapshot["claim_truth"]["status"] == "evidence_verified"
        assert projection.effectiveness_snapshot["claim_truth"]["source"] == "objection_ledger"

    async def test_get_projection_attaches_retrieval_facts_for_completed_sales_session(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        """Completed sales session with retrieval ledger data gets retrieval_facts in projection."""
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=84.0,
            accuracy_score=82.0,
            completeness_score=78.0,
            total_duration_seconds=180,
            start_time=datetime.now(UTC) - timedelta(seconds=180),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=_make_effectiveness_snapshot(
                evaluable=True,
                reason=None,
            ),
            voice_policy_snapshot={
                "knowledge_base_ids": ["kb-001", "kb-002"],
                "tool_policy": {"enable_internal_retrieval": True},
                "runtime_metrics": {
                    "knowledge_retrieval": {
                        "attempt_count": 3,
                        "hit_query_count": 2,
                        "hit_rate": 0.67,
                        "last_status": "hit",
                        "recent_attempts": [
                            {
                                "query": "客户回访方案",
                                "status": "hit",
                                "result_count": 5,
                                "result_summaries": ["文档A", "文档B"],
                                "knowledge_base_ids": ["kb-001"],
                            },
                        ],
                    }
                },
            },
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="你好",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="opening",
                score_snapshot={"overall_score": 84.0, "dimension_scores": {"专业度": 84.0}},
                ai_feedback=None,
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

        result = await service.get_projection(session_id=sample_session_id)

        assert result.is_success
        projection = result.value
        retrieval_facts = projection.effectiveness_snapshot.get("retrieval_facts")
        assert isinstance(retrieval_facts, dict)
        assert retrieval_facts["kb_bound"] is True
        assert retrieval_facts["knowledge_base_ids"] == ["kb-001", "kb-002"]
        assert retrieval_facts["knowledge_base_count"] == 2
        assert retrieval_facts["retrieval_enabled"] is True
        assert retrieval_facts["status"] == "hit"
        assert retrieval_facts["attempt_count"] == 3
        assert retrieval_facts["hit_count"] == 2
        assert isinstance(retrieval_facts["recent_attempts"], list)
        assert len(retrieval_facts["recent_attempts"]) >= 1

    async def test_get_projection_does_not_mutate_persisted_effectiveness_snapshot(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        """The projection overlay is copy-on-write; the persisted snapshot dict is not mutated."""
        original_snapshot = _make_effectiveness_snapshot(evaluable=True, reason=None)
        # Deep-copy to get a stable reference for comparison
        original_snapshot_copy = dict(original_snapshot)

        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=84.0,
            accuracy_score=82.0,
            completeness_score=78.0,
            total_duration_seconds=180,
            start_time=datetime.now(UTC) - timedelta(seconds=180),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=original_snapshot,
            voice_policy_snapshot={
                "knowledge_base_ids": ["kb-001"],
                "tool_policy": {"enable_internal_retrieval": True},
                "runtime_metrics": {
                    "knowledge_retrieval": {
                        "attempt_count": 1,
                        "hit_query_count": 1,
                        "hit_rate": 1.0,
                        "last_status": "hit",
                        "recent_attempts": [
                            {"query": "测试", "status": "hit", "result_count": 2},
                        ],
                    }
                },
            },
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="hello",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="opening",
                score_snapshot={"overall_score": 84.0},
                ai_feedback=None,
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

        result = await service.get_projection(session_id=sample_session_id)

        assert result.is_success
        # The projection should have retrieval_facts
        assert "retrieval_facts" in result.value.effectiveness_snapshot
        # But the original persisted snapshot must NOT be mutated
        assert "retrieval_facts" not in original_snapshot
        assert original_snapshot == original_snapshot_copy

    async def test_get_projection_skips_retrieval_facts_when_voice_policy_snapshot_missing(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        """Sessions without voice_policy_snapshot do not get retrieval_facts."""
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=84.0,
            accuracy_score=82.0,
            completeness_score=78.0,
            total_duration_seconds=180,
            start_time=datetime.now(UTC) - timedelta(seconds=180),
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
                content="hello",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="opening",
                score_snapshot={"overall_score": 84.0},
                ai_feedback=None,
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

        result = await service.get_projection(session_id=sample_session_id)

        assert result.is_success
        projection = result.value
        assert "retrieval_facts" not in projection.effectiveness_snapshot

    async def test_get_projection_builds_conclusion_evidence_bundle_for_sales_projection(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=84.0,
            accuracy_score=82.0,
            completeness_score=78.0,
            total_duration_seconds=180,
            start_time=datetime.now(UTC) - timedelta(seconds=180),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=_make_stale_sales_snapshot(),
            voice_policy_snapshot={
                "knowledge_base_ids": ["kb-1"],
                "tool_policy": {
                    "enable_internal_retrieval": True,
                    "require_kb_grounding": False,
                },
                "runtime_metrics": {
                    "knowledge_retrieval": {
                        "attempt_count": 1,
                        "hit_query_count": 1,
                        "last_status": "hit",
                        "recent_attempts": [
                            {
                                "attempted_at": datetime.now(UTC).isoformat(),
                                "query": "ROI 案例",
                                "status": "hit",
                                "result_count": 1,
                                "retrieval_mode": "hybrid",
                                "knowledge_base_ids": ["kb-1"],
                                "result_summaries": [
                                    {
                                        "knowledge_base_id": "kb-1",
                                        "knowledge_base_name": "产品知识库",
                                        "snippet": "客户A在6个月内实现ROI回本",
                                        "score": 0.92,
                                        "retrieval_mode": "vector",
                                    }
                                ],
                            }
                        ],
                    }
                },
            },
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="我们有 3 个同类客户在 6 个月内回本。",
                audio_url="https://example.com/audio-1.webm",
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="objection",
                score_snapshot={
                    "overall_score": 88.0,
                    "dimension_scores": {
                        "价值表达": 86.0,
                        "客户收益连接": 84.0,
                        "证据使用": 89.0,
                        "异议处理": 81.0,
                        "推进下一步": 79.0,
                    },
                },
                ai_feedback="补上了 ROI 证据。",
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

        result = await service.get_projection(session_id=sample_session_id)

        assert result.is_success
        projection = result.value
        assert projection.conclusion_evidence == {
            "main_issue": {
                "retrieval_source": {"available": True, "reason": None},
                "transcript_source": {"available": True, "turn_count": 1},
                "audio_source": {"available": True, "reason": None},
            },
            "next_goal": {
                "retrieval_source": {"available": True, "reason": None},
                "transcript_source": {"available": True, "turn_count": 1},
                "audio_source": {"available": True, "reason": None},
            },
            "claim_truth": {
                "retrieval_source": {"available": True, "reason": None},
                "transcript_source": {"available": True, "turn_count": 1},
                "audio_source": {"available": True, "reason": None},
            },
        }

    def test_build_evidence_degradation_returns_none_for_presentation_sessions(self) -> None:
        session = SimpleNamespace(report_status=None, report_error=None)
        conclusion_evidence = {
            "main_issue": {
                "retrieval_source": {"available": True, "reason": None},
                "transcript_source": {"available": True, "turn_count": 1},
                "audio_source": {"available": True, "reason": None},
            }
        }

        assert (
            SessionEvidenceService._build_evidence_degradation(
                session=session,
                conclusion_evidence=conclusion_evidence,
                scenario_type="presentation",
            )
            is None
        )

    def test_build_evidence_degradation_marks_all_layers_ok_for_happy_path(self) -> None:
        session = SimpleNamespace(report_status="completed", report_error=None)
        conclusion_evidence = {
            "main_issue": {
                "retrieval_source": {"available": True, "reason": None},
                "transcript_source": {"available": True, "turn_count": 1},
                "audio_source": {"available": True, "reason": None},
            },
            "next_goal": {
                "retrieval_source": {"available": True, "reason": None},
                "transcript_source": {"available": True, "turn_count": 1},
                "audio_source": {"available": True, "reason": None},
            },
            "claim_truth": {
                "retrieval_source": {"available": True, "reason": None},
                "transcript_source": {"available": True, "turn_count": 1},
                "audio_source": {"available": True, "reason": None},
            },
        }

        assert SessionEvidenceService._build_evidence_degradation(
            session=session,
            conclusion_evidence=conclusion_evidence,
            scenario_type="sales",
        ) == {
            "retrieval": {"status": "ok", "token": "retrieval_ok", "explanation": None},
            "transcript": {"status": "ok", "token": "transcript_ok", "explanation": None},
            "audio": {"status": "ok", "token": "audio_ok", "explanation": None},
            "enhanced_report": {
                "status": "ok",
                "token": "enhanced_report_ok",
                "explanation": None,
            },
        }

    def test_build_evidence_degradation_derives_reason_specific_degraded_layers(self) -> None:
        session = SimpleNamespace(
            report_status="failed",
            report_error="REPORT_GENERATION_FAILED",
        )
        conclusion_evidence = {
            "main_issue": {
                "retrieval_source": {
                    "available": False,
                    "reason": "no_voice_policy_snapshot",
                },
                "transcript_source": {"available": False, "turn_count": 0},
                "audio_source": {"available": False, "reason": "no_audio_segments"},
            },
            "next_goal": {
                "retrieval_source": {
                    "available": False,
                    "reason": "no_voice_policy_snapshot",
                },
                "transcript_source": {"available": False, "turn_count": 0},
                "audio_source": {"available": False, "reason": "no_audio_segments"},
            },
            "claim_truth": {
                "retrieval_source": {
                    "available": False,
                    "reason": "no_voice_policy_snapshot",
                },
                "transcript_source": {"available": False, "turn_count": 0},
                "audio_source": {"available": False, "reason": "no_audio_segments"},
            },
        }

        assert SessionEvidenceService._build_evidence_degradation(
            session=session,
            conclusion_evidence=conclusion_evidence,
            scenario_type="sales",
        ) == {
            "retrieval": {
                "status": "degraded",
                "token": "no_retrieval_facts",
                "explanation": "no_voice_policy_snapshot",
            },
            "transcript": {
                "status": "degraded",
                "token": "no_scored_turns",
                "explanation": "no_scored_turns",
            },
            "audio": {
                "status": "degraded",
                "token": "no_audio_segments",
                "explanation": "no_audio_segments",
            },
            "enhanced_report": {
                "status": "degraded",
                "token": "report_generation_failed",
                "explanation": "REPORT_GENERATION_FAILED",
            },
        }
