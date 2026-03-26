"""
Unit Tests for ReplayService

Tests for get_messages(), get_replay_data(), get_highlights(), and timeline generation.

References:
- Requirements: R10 (Conversation replay API)
- Design: Section 12 (Replay Service)
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.conversation.replay import ReplayService, STAGE_NAMES
from common.db.models import SessionStatus
from common.error_handling.result import Result


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


def _make_projection(
    session,
    *,
    messages: list[dict[str, object]],
    main_issue: dict[str, object] | None = None,
    next_goal: dict[str, object] | None = None,
    overall_score: float = 78.0,
):
    projection = MagicMock()
    projection.session = session
    projection.session_id = session.session_id
    projection.scenario_type = "sales"
    projection.messages = messages
    projection.timeline_markers = []
    projection.stage_summary = []
    projection.total_duration_ms = sum(int(message.get("duration_ms") or 0) for message in messages)
    projection.logic_score = 78.0
    projection.accuracy_score = 77.0
    projection.completeness_score = 79.0
    projection.overall_score = overall_score
    projection.effectiveness_snapshot = {
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": False,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "main_issue": main_issue,
        "next_goal": next_goal,
        "version": "rule_v1",
        "evaluable": True,
        "not_evaluable_reason": None,
    }
    projection.pass_flags = projection.effectiveness_snapshot["pass_flags"]
    projection.main_capability_passed = False
    projection.overall_result = "fail"
    projection.main_issue = main_issue
    projection.next_goal = next_goal
    projection.evaluable = True
    projection.not_evaluable_reason = None
    projection.evidence_completeness = {
        "complete": True,
        "message_count": len(messages),
        "missing_fields": [],
    }
    projection.legacy_score_key_used = False
    projection.sales_alignment_used = True
    projection.sales_alignment_stage_key = (
        str(messages[-1].get("sales_stage")) if messages and messages[-1].get("sales_stage") else None
    )
    projection.sales_alignment_focus_type = (
        str(main_issue.get("issue_type")) if isinstance(main_issue, dict) else None
    )
    projection.sales_alignment_fallback_reason = None
    projection.presentation_review = None
    return projection


class TestReplayService:
    """Tests for ReplayService"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock AsyncSession"""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create ReplayService with mock db"""
        return ReplayService(mock_db)

    @pytest.fixture
    def sample_session_id(self):
        """Sample session ID"""
        return str(uuid.uuid4())

    @pytest.fixture
    def mock_completed_session(self, sample_session_id):
        """Create a mock completed session"""
        session = MagicMock()
        session.session_id = sample_session_id
        session.status = SessionStatus.COMPLETED.value
        session.agent_id = None
        session.persona_id = None
        session.presentation_id = None
        session.voice_policy_snapshot = None
        return session

    @pytest.fixture
    def mock_in_progress_session(self, sample_session_id):
        """Create a mock in-progress session"""
        session = MagicMock()
        session.session_id = sample_session_id
        session.status = SessionStatus.IN_PROGRESS.value
        return session

    @pytest.fixture
    def mock_messages(self, sample_session_id):
        """Create mock conversation messages"""
        messages = []
        for i in range(3):
            msg = MagicMock()
            msg.id = str(uuid.uuid4())
            msg.session_id = sample_session_id
            msg.turn_number = i + 1
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i + 1}"
            msg.audio_url = f"https://storage.example.com/audio/msg-{i + 1}.mp3"
            msg.timestamp = datetime.now(timezone.utc)
            msg.duration_ms = 3000 + i * 500
            msg.fuzzy_words = None
            msg.sales_stage = "opening" if i == 0 else "discovery"
            msg.score_snapshot = {"overall": 70 + i * 5, "dimensions": []}
            msg.ai_feedback = None
            msg.is_highlight = False
            msg.highlight_type = None
            msg.highlight_reason = None
            messages.append(msg)
        return messages

    # ========== _check_session_completed tests ==========

    @pytest.mark.asyncio
    async def test_check_session_completed_success(self, service, mock_db, mock_completed_session):
        """Test checking a completed session succeeds"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_completed_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await service._check_session_completed(mock_completed_session.session_id)

        # Assert
        assert result.is_success
        assert result.value.status == SessionStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_check_session_completed_not_completed(self, service, mock_db, mock_in_progress_session):
        """Test checking an in-progress session fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_in_progress_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await service._check_session_completed(mock_in_progress_session.session_id)

        # Assert
        assert not result.is_success
        assert "[SESSION_NOT_COMPLETED]" in result.fallback

    @pytest.mark.asyncio
    async def test_check_session_completed_not_found(self, service, mock_db, sample_session_id):
        """Test checking a non-existent session fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await service._check_session_completed(sample_session_id)

        # Assert
        assert not result.is_success
        assert "[SESSION_NOT_FOUND]" in result.fallback

    # ========== get_messages tests ==========

    @pytest.mark.asyncio
    async def test_get_messages_success(self, service, mock_db, mock_completed_session, mock_messages):
        """Test getting messages for a completed session"""
        # Arrange
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = mock_messages

        mock_db.execute.side_effect = [mock_session_result, mock_count_result, mock_messages_result]

        # Act
        result = await service.get_messages(mock_completed_session.session_id)

        # Assert
        assert result.is_success
        messages, total = result.value
        assert len(messages) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_messages_session_not_completed(self, service, mock_db, mock_in_progress_session):
        """Test getting messages for an incomplete session fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_in_progress_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_messages(mock_in_progress_session.session_id)

        # Assert
        assert not result.is_success
        assert "[SESSION_NOT_COMPLETED]" in result.fallback

    @pytest.mark.asyncio
    async def test_get_messages_pagination(self, service, mock_db, mock_completed_session, mock_messages):
        """Test pagination for messages"""
        # Arrange
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = mock_messages[:1]

        mock_db.execute.side_effect = [mock_session_result, mock_count_result, mock_messages_result]

        # Act
        result = await service.get_messages(
            mock_completed_session.session_id,
            page=2,
            page_size=10
        )

        # Assert
        assert result.is_success
        messages, total = result.value
        assert total == 100

    # ========== get_replay_data tests ==========

    @pytest.mark.asyncio
    async def test_get_replay_data_success(self, service, mock_db, mock_completed_session, mock_messages):
        """Test getting replay data for a completed session"""
        # Arrange
        mock_completed_session.logic_score = 84.0
        mock_completed_session.accuracy_score = 82.0
        mock_completed_session.completeness_score = 79.0
        mock_completed_session.effectiveness_snapshot = {
            "pass_flags": {
                "pass_3min_flow": True,
                "pass_5turn_defense": True,
                "pass_4step_structure": False,
            },
            "main_capability_passed": True,
            "overall_result": "pass",
            "main_issue": {
                "issue_type": "structure_gap",
                "issue_text": "还需要更早确认预算。",
                "recovery_rule": "在 discovery 阶段补预算问题。",
            },
            "next_goal": {
                "goal_type": "budget_probe",
                "goal_text": "下一轮先确认预算和决策链。",
                "rule": "在第 2 轮前问出预算区间。",
            },
            "metrics": {
                "continuous_speech_seconds": 120.0,
                "filler_rate_per_100_words": 3.0,
                "offtopic_turn_count": 0.0,
                "offtopic_max_streak": 0.0,
                "structure_coverage": 0.8,
            },
            "version": "rule_v1",
            "evaluable": True,
            "not_evaluable_reason": None,
        }

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session

        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = mock_messages

        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        # Act
        result = await service.get_replay_data(mock_completed_session.session_id)

        # Assert
        assert result.is_success
        data = result.value
        assert data["session_id"] == mock_completed_session.session_id
        assert len(data["messages"]) == 3
        assert data["overall_score"] == pytest.approx(81.67, abs=0.01)
        assert data["main_issue"]["issue_type"] == mock_completed_session.effectiveness_snapshot["main_issue"]["issue_type"]
        assert data["main_issue"]["issue_text"] == mock_completed_session.effectiveness_snapshot["main_issue"]["issue_text"]
        assert data["main_issue"]["recovery_rule"] == mock_completed_session.effectiveness_snapshot["main_issue"]["recovery_rule"]
        assert data["main_issue"]["replay_anchor"]["status"] == "degraded"
        assert data["next_goal"]["goal_type"] == mock_completed_session.effectiveness_snapshot["next_goal"]["goal_type"]
        assert data["next_goal"]["goal_text"] == mock_completed_session.effectiveness_snapshot["next_goal"]["goal_text"]
        assert data["next_goal"]["rule"] == mock_completed_session.effectiveness_snapshot["next_goal"]["rule"]
        assert data["next_goal"]["replay_anchor"]["status"] == "degraded"
        assert data["evaluable"] is True
        assert data["not_evaluable_reason"] is None
        assert "timeline_markers" in data
        assert "stage_summary" in data
        assert "total_duration_ms" in data

    @pytest.mark.asyncio
    async def test_get_replay_data_sales_alignment_overrides_stale_snapshot(self, service, mock_db, mock_completed_session):
        """Replay should expose aligned sales conclusions when the persisted snapshot is stale."""
        mock_completed_session.logic_score = 80.0
        mock_completed_session.accuracy_score = 69.5
        mock_completed_session.completeness_score = 71.5
        mock_completed_session.effectiveness_snapshot = _make_stale_sales_snapshot()

        aligned_message = MagicMock()
        aligned_message.id = str(uuid.uuid4())
        aligned_message.session_id = mock_completed_session.session_id
        aligned_message.turn_number = 1
        aligned_message.role = "user"
        aligned_message.content = "ROI 这一块你们有真实案例吗？"
        aligned_message.audio_url = None
        aligned_message.timestamp = datetime.now(timezone.utc)
        aligned_message.duration_ms = 2500
        aligned_message.fuzzy_words = None
        aligned_message.transcript_metadata = None
        aligned_message.sales_stage = "discovery"
        aligned_message.score_snapshot = {
            "overall_score": 82.0,
            "dimension_scores": {
                "价值表达": 84.0,
                "客户收益连接": 80.0,
                "证据使用": 58.0,
                "异议处理": 76.0,
                "推进下一步": 72.0,
            },
        }
        aligned_message.ai_feedback = "补充案例和 ROI 数据"
        aligned_message.is_highlight = False
        aligned_message.highlight_type = None
        aligned_message.highlight_reason = None

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = [aligned_message]
        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        result = await service.get_replay_data(mock_completed_session.session_id)

        assert result.is_success
        data = result.value
        assert data["main_issue"]["issue_type"] == "evidence_gap"
        assert data["next_goal"]["goal_type"] == "evidence_backing"
        assert data["effectiveness_snapshot"]["main_issue"]["issue_type"] == "evidence_gap"
        assert data["effectiveness_snapshot"]["next_goal"]["goal_type"] == "evidence_backing"
        assert mock_completed_session.effectiveness_snapshot["main_issue"]["issue_type"] == "value_translation_gap"
        assert mock_completed_session.effectiveness_snapshot["next_goal"]["goal_type"] == "value_to_benefit_translation"

    @pytest.mark.asyncio
    async def test_get_replay_data_attaches_learning_evidence_to_highlight_messages(
        self,
        service,
        mock_completed_session,
    ):
        """Replay messages should expose structured learning evidence from the shared session projection."""
        main_issue = {
            "issue_type": "evidence_gap",
            "issue_text": "ROI 证据没有落到真实案例。",
            "recovery_rule": "下一轮先补真实 ROI / 案例证据，再推进下一步。",
        }
        next_goal = {
            "goal_type": "evidence_backing",
            "goal_text": "下一轮优先补 ROI 证据。",
            "rule": "至少给出一个真实案例或量化回报。",
        }
        replay_messages = [
            {
                "id": "msg-prev",
                "session_id": mock_completed_session.session_id,
                "turn_number": 1,
                "role": "assistant",
                "content": "您现在最担心的是 ROI 还是实施复杂度？",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:00+00:00",
                "duration_ms": 1800,
                "fuzzy_words": None,
                "transcript_metadata": None,
                "sales_stage": "discovery",
                "score_snapshot": {"overall_score": 78.0},
                "ai_feedback": None,
                "is_highlight": False,
                "highlight_type": None,
                "highlight_reason": None,
            },
            {
                "id": "msg-highlight",
                "session_id": mock_completed_session.session_id,
                "turn_number": 2,
                "role": "user",
                "content": "我们内部最关心的是 ROI，最好有同行案例。",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:05+00:00",
                "duration_ms": 2200,
                "fuzzy_words": [
                    {
                        "category": "uncertain",
                        "matched": ["应该"],
                        "suggestion": "直接给出已验证的 ROI 区间和客户案例",
                        "severity": "high",
                    }
                ],
                "transcript_metadata": {
                    "objection_ledger": {
                        "objection_family": "roi_proof",
                        "closure_state": "open",
                        "promised_proof": "补 ROI 案例",
                        "next_expected_evidence": "给出量化回报区间",
                    }
                },
                "sales_stage": "objection",
                "score_snapshot": {"overall_score": 66.0},
                "ai_feedback": "先承认对方需要证据，再补案例与 ROI 区间。",
                "is_highlight": True,
                "highlight_type": "bad",
                "highlight_reason": "客户已经明确要 ROI 证据，但这一轮还没有回应到位。",
            },
            {
                "id": "msg-next",
                "session_id": mock_completed_session.session_id,
                "turn_number": 3,
                "role": "assistant",
                "content": "明白，我下一轮先补一个 3 个月回本的客户案例。",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:08+00:00",
                "duration_ms": 2400,
                "fuzzy_words": None,
                "transcript_metadata": None,
                "sales_stage": "objection",
                "score_snapshot": {"overall_score": 72.0},
                "ai_feedback": None,
                "is_highlight": False,
                "highlight_type": None,
                "highlight_reason": None,
            },
        ]
        projection = _make_projection(
            mock_completed_session,
            messages=replay_messages,
            main_issue=main_issue,
            next_goal=next_goal,
            overall_score=72.0,
        )

        with patch(
            "common.conversation.replay.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(projection)),
        ):
            result = await service.get_replay_data(mock_completed_session.session_id)

        assert result.is_success
        data = result.value
        highlighted_message = next(
            message for message in data["messages"] if message["id"] == "msg-highlight"
        )
        learning_evidence = highlighted_message["learning_evidence"]
        assert learning_evidence["reason"] == "客户已经明确要 ROI 证据，但这一轮还没有回应到位。"
        assert learning_evidence["issue_family"] == "evidence_gap"
        assert learning_evidence["objection_family"] == "roi_proof"
        assert learning_evidence["stage"] == {"key": "objection", "name": STAGE_NAMES["objection"]}
        assert learning_evidence["linked_issue"]["issue_type"] == "evidence_gap"
        assert learning_evidence["linked_goal"]["goal_type"] == "evidence_backing"
        assert learning_evidence["nearby_context"]["prev_message"]["id"] == "msg-prev"
        assert learning_evidence["nearby_context"]["next_message"]["id"] == "msg-next"
        assert (
            learning_evidence["suggested_response"]
            == "建议改进: 直接给出已验证的 ROI 区间和客户案例"
        )

    @pytest.mark.asyncio
    async def test_get_replay_data_attaches_resolved_replay_anchor_to_issue_and_goal(
        self,
        service,
        mock_completed_session,
    ):
        """Replay should surface stable issue/goal anchors that point at the matched highlight marker."""
        main_issue = {
            "issue_type": "evidence_gap",
            "issue_text": "ROI 证据没有落到真实案例。",
            "recovery_rule": "下一轮先补真实 ROI / 案例证据，再推进下一步。",
        }
        next_goal = {
            "goal_type": "evidence_backing",
            "goal_text": "下一轮优先补 ROI 证据。",
            "rule": "至少给出一个真实案例或量化回报。",
        }
        replay_messages = [
            {
                "id": "msg-prev",
                "session_id": mock_completed_session.session_id,
                "turn_number": 1,
                "role": "assistant",
                "content": "您最需要什么类型的 ROI 证明？",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:00+00:00",
                "duration_ms": 1800,
                "fuzzy_words": None,
                "transcript_metadata": None,
                "sales_stage": "discovery",
                "score_snapshot": {"overall_score": 78.0},
                "ai_feedback": None,
                "is_highlight": False,
                "highlight_type": None,
                "highlight_reason": None,
            },
            {
                "id": "msg-highlight",
                "session_id": mock_completed_session.session_id,
                "turn_number": 2,
                "role": "user",
                "content": "我们内部还是想先看同行案例和回收周期。",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:04+00:00",
                "duration_ms": 2200,
                "fuzzy_words": None,
                "transcript_metadata": None,
                "sales_stage": "objection",
                "score_snapshot": {"overall_score": 64.0},
                "ai_feedback": "先确认对方需要案例，再补 ROI 和回收周期。",
                "is_highlight": True,
                "highlight_type": "bad",
                "highlight_reason": "客户已经明确要证据，但这轮还没给出任何案例或数字。",
            },
            {
                "id": "msg-next",
                "session_id": mock_completed_session.session_id,
                "turn_number": 3,
                "role": "assistant",
                "content": "我下一轮先给您一个 3 个月回本的同行案例。",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:08+00:00",
                "duration_ms": 2400,
                "fuzzy_words": None,
                "transcript_metadata": None,
                "sales_stage": "objection",
                "score_snapshot": {"overall_score": 72.0},
                "ai_feedback": None,
                "is_highlight": False,
                "highlight_type": None,
                "highlight_reason": None,
            },
        ]
        projection = _make_projection(
            mock_completed_session,
            messages=replay_messages,
            main_issue=main_issue,
            next_goal=next_goal,
            overall_score=72.0,
        )
        projection.timeline_markers = [
            {
                "timestamp_ms": 0,
                "type": "stage_change",
                "label": STAGE_NAMES["discovery"],
                "message_id": "msg-prev",
                "highlight_type": None,
            },
            {
                "timestamp_ms": 1800,
                "type": "stage_change",
                "label": STAGE_NAMES["objection"],
                "message_id": "msg-highlight",
                "highlight_type": None,
            },
            {
                "timestamp_ms": 1800,
                "type": "highlight",
                "label": "客户已经明确要证据，但这轮还没给出任何案例或数字。",
                "message_id": "msg-highlight",
                "highlight_type": "bad",
            },
        ]
        projection.sales_alignment_stage_key = "objection"

        with patch(
            "common.conversation.replay.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(projection)),
        ):
            result = await service.get_replay_data(mock_completed_session.session_id)

        assert result.is_success
        data = result.value
        issue_anchor = data["main_issue"]["replay_anchor"]
        goal_anchor = data["next_goal"]["replay_anchor"]

        assert issue_anchor["status"] == "resolved"
        assert issue_anchor["message_id"] == "msg-highlight"
        assert issue_anchor["turn_number"] == 2
        assert issue_anchor["marker"] == {
            "type": "highlight",
            "timestamp_ms": 1800,
            "label": "客户已经明确要证据，但这轮还没给出任何案例或数字。",
        }
        assert issue_anchor["degraded_reason"] is None

        assert goal_anchor["status"] == "resolved"
        assert goal_anchor["message_id"] == "msg-highlight"
        assert goal_anchor["turn_number"] == 2
        assert goal_anchor["marker"]["type"] == "highlight"
        assert goal_anchor["degraded_reason"] is None

    @pytest.mark.asyncio
    async def test_get_replay_data_marks_replay_anchor_degraded_when_highlight_marker_is_missing(
        self,
        service,
        mock_completed_session,
    ):
        """Replay should surface missing-marker degradation instead of silently dropping the anchor."""
        main_issue = {
            "issue_type": "evidence_gap",
            "issue_text": "ROI 证据没有落到真实案例。",
            "recovery_rule": "下一轮先补真实 ROI / 案例证据，再推进下一步。",
        }
        next_goal = {
            "goal_type": "evidence_backing",
            "goal_text": "下一轮优先补 ROI 证据。",
            "rule": "至少给出一个真实案例或量化回报。",
        }
        replay_messages = [
            {
                "id": "msg-highlight",
                "session_id": mock_completed_session.session_id,
                "turn_number": 2,
                "role": "user",
                "content": "我们内部还是想先看同行案例和回收周期。",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:04+00:00",
                "duration_ms": 2200,
                "fuzzy_words": None,
                "transcript_metadata": None,
                "sales_stage": "objection",
                "score_snapshot": {"overall_score": 64.0},
                "ai_feedback": "先确认对方需要案例，再补 ROI 和回收周期。",
                "is_highlight": True,
                "highlight_type": "bad",
                "highlight_reason": "客户已经明确要证据，但这轮还没给出任何案例或数字。",
            },
        ]
        projection = _make_projection(
            mock_completed_session,
            messages=replay_messages,
            main_issue=main_issue,
            next_goal=next_goal,
            overall_score=64.0,
        )
        projection.timeline_markers = []
        projection.sales_alignment_stage_key = "objection"

        with patch(
            "common.conversation.replay.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(projection)),
        ):
            result = await service.get_replay_data(mock_completed_session.session_id)

        assert result.is_success
        data = result.value
        issue_anchor = data["main_issue"]["replay_anchor"]
        goal_anchor = data["next_goal"]["replay_anchor"]

        assert issue_anchor["status"] == "degraded"
        assert issue_anchor["message_id"] == "msg-highlight"
        assert issue_anchor["turn_number"] == 2
        assert issue_anchor["marker"] is None
        assert issue_anchor["degraded_reason"] == "missing_marker"

        assert goal_anchor["status"] == "degraded"
        assert goal_anchor["message_id"] == "msg-highlight"
        assert goal_anchor["turn_number"] == 2
        assert goal_anchor["marker"] is None
        assert goal_anchor["degraded_reason"] == "missing_marker"

    @pytest.mark.asyncio
    async def test_get_replay_data_marks_replay_anchor_degraded_when_falling_back_to_stage(
        self,
        service,
        mock_completed_session,
    ):
        """Replay should keep degraded anchor state visible when no highlight matches the aligned stage."""
        main_issue = {
            "issue_type": "objection_handling_gap",
            "issue_text": "价格顾虑已经出现，但还没给出报价逻辑。",
            "recovery_rule": "下一轮先承接价格顾虑，再解释报价依据。",
        }
        next_goal = {
            "goal_type": "objection_reframe",
            "goal_text": "下一轮先解释报价逻辑，再推进低风险下一步。",
            "rule": "至少先承接价格顾虑，再说明报价或 ROI 逻辑。",
        }
        replay_messages = [
            {
                "id": "msg-discovery",
                "session_id": mock_completed_session.session_id,
                "turn_number": 1,
                "role": "assistant",
                "content": "您目前更担心预算还是上线周期？",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:00+00:00",
                "duration_ms": 1800,
                "fuzzy_words": None,
                "transcript_metadata": None,
                "sales_stage": "discovery",
                "score_snapshot": {"overall_score": 78.0},
                "ai_feedback": None,
                "is_highlight": False,
                "highlight_type": None,
                "highlight_reason": None,
            },
            {
                "id": "msg-objection",
                "session_id": mock_completed_session.session_id,
                "turn_number": 2,
                "role": "user",
                "content": "最大的顾虑还是价格，你们为什么比别人贵？",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:04+00:00",
                "duration_ms": 2200,
                "fuzzy_words": None,
                "transcript_metadata": None,
                "sales_stage": "objection",
                "score_snapshot": {"overall_score": 60.0},
                "ai_feedback": None,
                "is_highlight": False,
                "highlight_type": None,
                "highlight_reason": None,
            },
        ]
        projection = _make_projection(
            mock_completed_session,
            messages=replay_messages,
            main_issue=main_issue,
            next_goal=next_goal,
            overall_score=69.0,
        )
        projection.timeline_markers = [
            {
                "timestamp_ms": 0,
                "type": "stage_change",
                "label": STAGE_NAMES["discovery"],
                "message_id": "msg-discovery",
                "highlight_type": None,
            },
            {
                "timestamp_ms": 1800,
                "type": "stage_change",
                "label": STAGE_NAMES["objection"],
                "message_id": "msg-objection",
                "highlight_type": None,
            },
        ]
        projection.sales_alignment_stage_key = "objection"

        with patch(
            "common.conversation.replay.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(projection)),
        ):
            result = await service.get_replay_data(mock_completed_session.session_id)

        assert result.is_success
        data = result.value
        issue_anchor = data["main_issue"]["replay_anchor"]
        goal_anchor = data["next_goal"]["replay_anchor"]

        assert issue_anchor["status"] == "degraded"
        assert issue_anchor["message_id"] == "msg-objection"
        assert issue_anchor["turn_number"] == 2
        assert issue_anchor["marker"] == {
            "type": "stage_change",
            "timestamp_ms": 1800,
            "label": STAGE_NAMES["objection"],
        }
        assert issue_anchor["degraded_reason"] == "no_matching_highlight"

        assert goal_anchor["status"] == "degraded"
        assert goal_anchor["message_id"] == "msg-objection"
        assert goal_anchor["turn_number"] == 2
        assert goal_anchor["marker"]["type"] == "stage_change"
        assert goal_anchor["degraded_reason"] == "no_matching_highlight"

    @pytest.mark.asyncio
    async def test_get_replay_data_normalizes_legacy_message_scores(self, service, mock_db, mock_completed_session):
        """Replay should expose the shared normalized score_snapshot contract."""
        mock_completed_session.logic_score = 70.0
        mock_completed_session.accuracy_score = 70.0
        mock_completed_session.completeness_score = 70.0
        mock_completed_session.effectiveness_snapshot = {
            "pass_flags": {},
            "main_capability_passed": False,
            "overall_result": "fail",
            "main_issue": {"issue_type": "budget", "issue_text": "预算没问到", "recovery_rule": "第二轮补问"},
            "next_goal": {"goal_type": "budget_probe", "goal_text": "先问预算", "rule": "第二轮前完成"},
            "metrics": {},
            "version": "rule_v1",
            "evaluable": False,
            "not_evaluable_reason": "INSUFFICIENT_TURN_DATA",
        }

        legacy_message = MagicMock()
        legacy_message.id = str(uuid.uuid4())
        legacy_message.session_id = mock_completed_session.session_id
        legacy_message.turn_number = 1
        legacy_message.role = "user"
        legacy_message.content = "我们先聊聊现状。"
        legacy_message.audio_url = None
        legacy_message.timestamp = datetime.now(timezone.utc)
        legacy_message.duration_ms = 2500
        legacy_message.fuzzy_words = None
        legacy_message.transcript_metadata = None
        legacy_message.sales_stage = "opening"
        legacy_message.score_snapshot = {"overall": 74}
        legacy_message.ai_feedback = None
        legacy_message.is_highlight = False
        legacy_message.highlight_type = None
        legacy_message.highlight_reason = None

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = [legacy_message]
        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        result = await service.get_replay_data(mock_completed_session.session_id)

        assert result.is_success
        data = result.value
        assert data["messages"][0]["score_snapshot"] == {"overall_score": 74.0}
        assert data["stage_summary"] == [{"stage": "opening", "duration_ms": 2500, "score": 74}]
        assert data["not_evaluable_reason"] == "INSUFFICIENT_TURN_DATA"
        assert data["evidence_completeness"]["legacy_score_key_used"] is True

    @pytest.mark.asyncio
    async def test_get_replay_data_includes_presentation_review_for_presentation_sessions(
        self,
        service,
        mock_completed_session,
    ):
        """Presentation replay should expose page-level review data on the existing replay authority line."""
        mock_completed_session.presentation_id = "presentation-1"
        replay_messages = [
            {
                "id": "ppt-turn-1",
                "session_id": mock_completed_session.session_id,
                "turn_number": 1,
                "role": "user",
                "content": "第一页先讲业务目标。",
                "audio_url": None,
                "timestamp": "2026-03-25T00:00:00+00:00",
                "duration_ms": 1800,
                "fuzzy_words": None,
                "transcript_metadata": {"page_number": 1},
                "sales_stage": None,
                "score_snapshot": {"overall_score": 88.0},
                "ai_feedback": None,
                "is_highlight": False,
                "highlight_type": None,
                "highlight_reason": None,
            },
        ]
        projection = _make_projection(
            mock_completed_session,
            messages=replay_messages,
            main_issue=None,
            next_goal=None,
            overall_score=88.0,
        )
        projection.scenario_type = "presentation"
        projection.effectiveness_snapshot = None
        projection.pass_flags = None
        projection.main_capability_passed = None
        projection.overall_result = None
        projection.evaluable = None
        projection.not_evaluable_reason = None
        projection.stage_summary = []
        projection.presentation_review = {
            "overall_score": 88,
            "dimension_scores": [],
            "page_summaries": [
                {
                    "page_number": 1,
                    "stage_number": 1,
                    "start_turn": 1,
                    "end_turn": 1,
                    "average_score": 88,
                    "key_points": ["业务目标"],
                    "matched_required_points": ["业务目标"],
                    "missing_required_points": [],
                    "issue_clusters": [
                        {
                            "issue_type": "off_page",
                            "summary": "第 1 页讲解带到了其他页内容，优先回到当前页要点。",
                            "evidence": ["第 2 页要点：实施计划"],
                            "turn_numbers": [1],
                            "linked_points": ["实施计划"],
                            "linked_phrases": [],
                            "related_page_numbers": [2],
                        }
                    ],
                    "summary": "第一页完整讲清业务目标。",
                }
            ],
            "required_talking_points": {
                "status": "complete",
                "total": 1,
                "covered": 1,
                "missing": 0,
                "coverage_ratio": 1,
            },
            "issue_counts": {"off_page": 1},
            "strengths": ["表达流畅"],
            "improvements": ["减少串页"],
            "recommendations": ["按页讲述。"],
            "detailed_feedback": "整体稳定，但第一页发生串页。",
            "has_page_metadata": True,
            "coverage_status": "complete",
            "diagnostics": {
                "has_page_metadata": True,
                "pages_with_messages": 1,
                "total_pages": 2,
                "page_coverage_ratio": 0.5,
                "required_points_total": 1,
                "required_points_covered": 1,
                "required_points_missing": 0,
                "required_coverage_ratio": 1,
                "degraded_reasons": [],
                "page_issue_cluster_count": 1,
                "page_issue_types": ["off_page"],
            },
        }
        projection.evidence_completeness = {
            "complete": True,
            "scenario_type": "presentation",
            "presentation_review_available": True,
            "page_metadata_complete": True,
            "page_summary_count": 1,
            "required_talking_points_status": "complete",
            "required_points_total": 1,
            "required_points_covered": 1,
            "required_points_missing": 0,
            "required_coverage_ratio": 1,
            "degraded_reasons": [],
        }

        with patch(
            "common.conversation.replay.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(projection)),
        ):
            result = await service.get_replay_data(mock_completed_session.session_id)

        assert result.is_success
        data = result.value
        assert data["scenario_type"] == "presentation"
        assert data["presentation_id"] == "presentation-1"
        assert data["presentation_review"] == projection.presentation_review
        assert data["main_issue"] is None
        assert data["next_goal"] is None
        assert data["messages"][0]["learning_evidence"] is None

    @pytest.mark.asyncio
    async def test_get_replay_data_session_not_completed(self, service, mock_db, mock_in_progress_session):
        """Test getting replay data for an incomplete session fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_in_progress_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_replay_data(mock_in_progress_session.session_id)

        # Assert
        assert not result.is_success
        assert "[SESSION_NOT_COMPLETED]" in result.fallback

    # ========== get_highlights tests ==========

    @pytest.mark.asyncio
    async def test_get_highlights_success(self, service, mock_completed_session):
        """Test getting highlights for a completed session"""
        main_issue = {
            "issue_type": "evidence_gap",
            "issue_text": "ROI 证据没有落到真实案例。",
            "recovery_rule": "下一轮先补真实 ROI / 案例证据，再推进下一步。",
        }
        next_goal = {
            "goal_type": "evidence_backing",
            "goal_text": "下一轮优先补 ROI 证据。",
            "rule": "至少给出一个真实案例或量化回报。",
        }
        projection = _make_projection(
            mock_completed_session,
            messages=[
                {
                    "id": "msg-prev",
                    "session_id": mock_completed_session.session_id,
                    "turn_number": 1,
                    "role": "assistant",
                    "content": "您最需要什么类型的 ROI 证明？",
                    "audio_url": None,
                    "timestamp": "2026-03-25T00:00:00+00:00",
                    "duration_ms": 1800,
                    "fuzzy_words": None,
                    "transcript_metadata": None,
                    "sales_stage": "discovery",
                    "score_snapshot": {"overall_score": 78.0},
                    "ai_feedback": None,
                    "is_highlight": False,
                    "highlight_type": None,
                    "highlight_reason": None,
                },
                {
                    "id": "msg-highlight",
                    "session_id": mock_completed_session.session_id,
                    "turn_number": 2,
                    "role": "user",
                    "content": "我们内部更想看同行案例和回收周期。",
                    "audio_url": None,
                    "timestamp": "2026-03-25T00:00:04+00:00",
                    "duration_ms": 2200,
                    "fuzzy_words": [
                        {
                            "category": "uncertain",
                            "matched": ["差不多"],
                            "suggestion": "直接补同行案例和 ROI 数字",
                            "severity": "high",
                        }
                    ],
                    "transcript_metadata": {
                        "objection_ledger": {
                            "objection_family": "roi_proof",
                            "closure_state": "open",
                            "promised_proof": "补同行 ROI 案例",
                            "next_expected_evidence": "给出回收周期区间",
                        }
                    },
                    "sales_stage": "objection",
                    "score_snapshot": {"overall_score": 64.0},
                    "ai_feedback": "先确认对方要看案例，再补 ROI 和回收周期。",
                    "is_highlight": True,
                    "highlight_type": "bad",
                    "highlight_reason": "客户已经明确要证据，但这轮还没给出任何案例或数字。",
                },
                {
                    "id": "msg-next",
                    "session_id": mock_completed_session.session_id,
                    "turn_number": 3,
                    "role": "assistant",
                    "content": "我下一轮先给您一个 3 个月回本的同行案例。",
                    "audio_url": None,
                    "timestamp": "2026-03-25T00:00:08+00:00",
                    "duration_ms": 2400,
                    "fuzzy_words": None,
                    "transcript_metadata": None,
                    "sales_stage": "objection",
                    "score_snapshot": {"overall_score": 72.0},
                    "ai_feedback": None,
                    "is_highlight": False,
                    "highlight_type": None,
                    "highlight_reason": None,
                },
            ],
            main_issue=main_issue,
            next_goal=next_goal,
        )

        with patch(
            "common.conversation.replay.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(projection)),
        ):
            result = await service.get_highlights(mock_completed_session.session_id)

        assert result.is_success
        highlights = result.value["highlights"]
        assert len(highlights) == 1
        assert highlights[0]["highlight_type"] == "bad"
        assert highlights[0]["highlight_reason"] == "客户已经明确要证据，但这轮还没给出任何案例或数字。"
        assert highlights[0]["sales_stage"] == "objection"
        assert highlights[0]["stage_name"] == STAGE_NAMES["objection"]
        assert highlights[0]["context"]["prev_message"]["id"] == "msg-prev"
        assert highlights[0]["context"]["next_message"]["id"] == "msg-next"
        learning_evidence = highlights[0]["learning_evidence"]
        assert learning_evidence["issue_family"] == "evidence_gap"
        assert learning_evidence["objection_family"] == "roi_proof"
        assert learning_evidence["linked_goal"]["goal_type"] == "evidence_backing"
        assert learning_evidence["nearby_context"] == highlights[0]["context"]
        assert learning_evidence["suggested_response"] == "建议改进: 直接补同行案例和 ROI 数字"

    @pytest.mark.asyncio
    async def test_get_highlights_empty(self, service, mock_completed_session):
        """Test getting highlights when none exist"""
        projection = _make_projection(
            mock_completed_session,
            messages=[],
            main_issue=None,
            next_goal=None,
        )

        with patch(
            "common.conversation.replay.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(projection)),
        ):
            result = await service.get_highlights(mock_completed_session.session_id)

        assert result.is_success
        assert len(result.value["highlights"]) == 0
        assert result.value["total_good"] == 0
        assert result.value["total_bad"] == 0

    # ========== _generate_timeline_markers tests ==========

    def test_generate_timeline_markers_stage_changes(self, service, mock_messages):
        """Test timeline markers include stage changes"""
        # Act
        markers = service._generate_timeline_markers(mock_messages)

        # Assert
        stage_markers = [m for m in markers if m["type"] == "stage_change"]
        assert len(stage_markers) >= 1  # At least opening stage

    def test_generate_timeline_markers_fuzzy_words(self, service, sample_session_id):
        """Test timeline markers include high severity fuzzy words"""
        # Arrange
        msg = MagicMock()
        msg.id = str(uuid.uuid4())
        msg.sales_stage = "presentation"
        msg.duration_ms = 3000
        msg.is_highlight = False
        msg.fuzzy_words = [
            {"category": "uncertain", "matched": ["大概"], "suggestion": "请给出具体数据", "severity": "high"}
        ]

        # Act
        markers = service._generate_timeline_markers([msg])

        # Assert
        fuzzy_markers = [m for m in markers if m["type"] == "fuzzy_word"]
        assert len(fuzzy_markers) == 1
        assert "大概" in fuzzy_markers[0]["label"]
        assert fuzzy_markers[0]["highlight_type"] == "bad"

    def test_generate_timeline_markers_highlights(self, service, sample_session_id):
        """Test timeline markers include highlights"""
        # Arrange
        msg = MagicMock()
        msg.id = str(uuid.uuid4())
        msg.sales_stage = "presentation"
        msg.duration_ms = 3000
        msg.is_highlight = True
        msg.highlight_type = "good"
        msg.highlight_reason = "优秀案例引用"
        msg.fuzzy_words = None

        # Act
        markers = service._generate_timeline_markers([msg])

        # Assert
        highlight_markers = [m for m in markers if m["type"] == "highlight"]
        assert len(highlight_markers) == 1
        assert highlight_markers[0]["label"] == "优秀案例引用"
        assert highlight_markers[0]["highlight_type"] == "good"

    def test_generate_timeline_markers_cumulative_time(self, service, mock_messages):
        """Test timeline markers have cumulative timestamps"""
        # Act
        markers = service._generate_timeline_markers(mock_messages)

        # Assert
        # Timestamps should be cumulative
        if len(markers) > 1:
            for i in range(1, len(markers)):
                assert markers[i]["timestamp_ms"] >= markers[i - 1]["timestamp_ms"]

    # ========== _generate_stage_summary tests ==========

    def test_generate_stage_summary(self, service, mock_messages):
        """Test stage summary generation"""
        # Act
        summary = service._generate_stage_summary(mock_messages)

        # Assert
        assert isinstance(summary, list)
        for item in summary:
            assert "stage" in item
            assert "duration_ms" in item
            assert "score" in item

    def test_generate_stage_summary_with_scores(self, service, sample_session_id):
        """Test stage summary includes average scores"""
        # Arrange
        messages = []
        for i in range(3):
            msg = MagicMock()
            msg.sales_stage = "presentation"
            msg.duration_ms = 1000
            msg.score_snapshot = {"overall": 70 + i * 10}  # 70, 80, 90
            messages.append(msg)

        # Act
        summary = service._generate_stage_summary(messages)

        # Assert
        presentation_summary = next((s for s in summary if s["stage"] == "presentation"), None)
        assert presentation_summary is not None
        assert presentation_summary["score"] == 80  # Average of 70, 80, 90

    # ========== _calculate_total_duration tests ==========

    def test_calculate_total_duration(self, service, mock_messages):
        """Test total duration calculation"""
        # Act
        total = service._calculate_total_duration(mock_messages)

        # Assert
        expected = sum(msg.duration_ms for msg in mock_messages)
        assert total == expected

    def test_calculate_total_duration_with_none(self, service):
        """Test total duration handles None values"""
        # Arrange
        msg1 = MagicMock()
        msg1.duration_ms = 1000
        msg2 = MagicMock()
        msg2.duration_ms = None
        msg3 = MagicMock()
        msg3.duration_ms = 2000

        # Act
        total = service._calculate_total_duration([msg1, msg2, msg3])

        # Assert
        assert total == 3000

    # ========== _message_to_dict tests ==========

    def test_message_to_dict(self, service, mock_messages):
        """Test message to dict conversion"""
        # Act
        result = service._message_to_dict(mock_messages[0])

        # Assert
        assert "id" in result
        assert "session_id" in result
        assert "turn_number" in result
        assert "role" in result
        assert "content" in result
        assert "audio_url" in result
        assert "timestamp" in result
        assert "duration_ms" in result
        assert "fuzzy_words" in result
        assert "sales_stage" in result
        assert "score_snapshot" in result
        assert "is_highlight" in result

    # ========== _generate_suggested_response tests ==========

    def test_generate_suggested_response_bad_highlight(self, service):
        """Test suggested response for bad highlight"""
        # Arrange
        msg = MagicMock()
        msg.highlight_type = "bad"
        msg.fuzzy_words = [
            {"category": "uncertain", "matched": ["大概"], "suggestion": "请给出具体数据", "severity": "high"}
        ]

        # Act
        result = service._generate_suggested_response(msg)

        # Assert
        assert result is not None
        assert "请给出具体数据" in result

    def test_generate_suggested_response_good_highlight(self, service):
        """Test suggested response for good highlight returns None"""
        # Arrange
        msg = MagicMock()
        msg.highlight_type = "good"
        msg.fuzzy_words = None

        # Act
        result = service._generate_suggested_response(msg)

        # Assert
        assert result is None

    def test_generate_suggested_response_neutral_highlight(self, service):
        """Test suggested response for neutral highlight returns None"""
        # Arrange
        msg = MagicMock()
        msg.highlight_type = "neutral"
        msg.fuzzy_words = None

        # Act
        result = service._generate_suggested_response(msg)

        # Assert
        assert result is None
