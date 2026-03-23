"""
Unit tests for RealtimeScoringCapability.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from agent.capabilities.realtime_scoring import RealtimeScoringCapability
from agent.context import AgentContext

SALES_DIMENSIONS = [
    "价值表达",
    "客户收益连接",
    "证据使用",
    "异议处理",
    "推进下一步",
]


@pytest.fixture
def context() -> AgentContext:
    return AgentContext(
        session_id="test-session-123",
        agent_id="test-agent-123",
        persona_id="test-persona-123",
        user_id="test-user-123",
        state={},
        conversation_history=[],
        agent_config={},
        persona_config={},
        turn_count=1,
        start_time=datetime.now(),
        trace_id="test-trace-123",
    )


@pytest.fixture
def capability() -> RealtimeScoringCapability:
    return RealtimeScoringCapability({"enabled": True})


class TestRealtimeScoringCapability:
    @pytest.mark.asyncio
    async def test_execute_returns_canonical_sales_dimensions(self, capability, context):
        await capability.on_session_start(context)

        result = await capability.execute(
            context,
            "我们能帮助你们把线索响应时间从24小时缩短到2小时。",
        )

        assert result.success is True
        assert result.data["overall_score"] == pytest.approx(result.data["overall"], abs=0.5)
        assert list(result.data["dimension_scores"].keys()) == SALES_DIMENSIONS
        assert [dim["name"] for dim in result.data["dimensions"]] == SALES_DIMENSIONS
        for dimension in result.data["dimensions"]:
            assert 0 <= dimension["score"] <= 100
            assert dimension["trend"] in {"up", "down", "stable"}

    @pytest.mark.asyncio
    async def test_execute_rewards_value_benefit_evidence_and_next_step_language(
        self,
        capability,
        context,
    ):
        await capability.on_session_start(context)
        context.state["current_stage"] = "presentation"

        result = await capability.execute(
            context,
            (
                "结合你们华东团队线索转化慢的问题，我们把跟进SOP压缩到2天，"
                "预计三个月把赢单率提升18%，ROI在一个季度内回正。"
                "像零售客户A一样，他们上线后复购率提升了12个百分点。"
                "如果你认可这个方向，我们本周可以安排试点评估和负责人对齐。"
            ),
        )

        scores = result.data["dimension_scores"]
        assert scores["价值表达"] >= 80
        assert scores["客户收益连接"] >= 80
        assert scores["证据使用"] >= 80
        assert scores["推进下一步"] >= 75

    @pytest.mark.asyncio
    async def test_execute_objection_stage_rewards_acknowledge_and_reframe(self, capability, context):
        await capability.on_session_start(context)
        context.state["current_stage"] = "objection"

        result = await capability.execute(
            context,
            (
                "我理解你现在最担心的是价格和竞品替代风险。"
                "但关键不是便宜，而是三个月内减少40%的人工复盘成本。"
                "我们有同类客户的上线案例和数据证明，你们也可以先从低风险试点开始。"
            ),
        )

        scores = result.data["dimension_scores"]
        assert scores["异议处理"] >= 80
        assert scores["证据使用"] >= 70
        assert scores["客户收益连接"] >= 70
        assert isinstance(result.data["feedback"], str) and result.data["feedback"]

    @pytest.mark.asyncio
    async def test_execute_respects_persona_scoring_weights_for_overall_score(self, context):
        weights = {
            "价值表达": 0.10,
            "客户收益连接": 0.10,
            "证据使用": 0.10,
            "异议处理": 0.10,
            "推进下一步": 0.60,
        }
        context.persona_config = {
            "scoring_weights": [
                {"name": name, "weight": weight} for name, weight in weights.items()
            ]
        }
        capability = RealtimeScoringCapability({"enabled": True})
        await capability.on_session_start(context)

        result = await capability.execute(
            context,
            "建议今天确认试点负责人、目标客户名单和下周复盘时间。",
        )

        scores = result.data["dimension_scores"]
        expected_overall = sum(scores[name] * weight for name, weight in weights.items())
        assert result.success is True
        assert result.data["overall_score"] == pytest.approx(expected_overall, abs=0.5)

    @pytest.mark.asyncio
    async def test_execute_tracks_score_history_with_canonical_snapshot(self, capability, context):
        await capability.on_session_start(context)

        await capability.execute(context, "第一轮先讲产品价值。")
        await capability.execute(context, "第二轮补上客户收益和证据。")

        history = context.state.get("score_history", [])
        assert len(history) == 2
        assert list(history[-1]["dimension_scores"].keys()) == SALES_DIMENSIONS
        assert "overall_score" in history[-1]

    @pytest.mark.asyncio
    async def test_on_session_end_returns_stats(self, capability, context):
        await capability.on_session_start(context)
        await capability.execute(context, "我们能帮助你们降低成本并安排下周试点。")

        stats = await capability.on_session_end(context)

        assert "average_score" in stats
        assert "final_score" in stats

    def test_capability_metadata_returns_correct_values(self, capability):
        assert capability.capability_id == "realtime_scoring"
        assert capability.name == "实时评分"
