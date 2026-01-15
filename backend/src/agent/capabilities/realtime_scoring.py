"""
RealtimeScoringCapability - 实时评分能力

基于对话内容实时计算多维度评分，支持趋势分析和反馈生成。

References:
- Requirements: R8 (实时评分)
- Design: Section 10 (Realtime Scoring Capability)
"""
from __future__ import annotations

from typing import Any, ClassVar

from agent.capabilities.base import BaseCapability, CapabilityConfig, CapabilityResult
from agent.capabilities.registry import CapabilityRegistry
from agent.context import AgentContext
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# Constants for state management
MAX_SCORE_HISTORY_SIZE = 100  # Maximum number of history entries to keep
WEIGHT_TOLERANCE = 0.001  # Tolerance for weight sum validation


@CapabilityRegistry.register
class RealtimeScoringCapability(BaseCapability):
    """
    实时评分能力
    
    默认5维度评分：
    - 专业度 (25%)
    - 沟通技巧 (25%)
    - 销售流程 (20%)
    - 异议处理 (15%)
    - 成交能力 (15%)
    """

    capability_id: ClassVar[str] = "realtime_scoring"
    name: ClassVar[str] = "实时评分"
    description: ClassVar[str] = "基于对话内容实时计算多维度评分"

    DEFAULT_DIMENSIONS: ClassVar[list[dict[str, Any]]] = [
        {"name": "专业度", "weight": 0.25},
        {"name": "沟通技巧", "weight": 0.25},
        {"name": "销售流程", "weight": 0.20},
        {"name": "异议处理", "weight": 0.15},
        {"name": "成交能力", "weight": 0.15}
    ]

    # 评分规则
    SCORING_RULES: ClassVar[dict[str, dict[str, Any]]] = {
        "专业度": {
            "positive": ["数据", "案例", "证据", "研究", "统计", "报告"],
            "negative": ["大概", "可能", "也许", "不太清楚"],
            "base_score": 70
        },
        "沟通技巧": {
            "positive": ["您", "请问", "理解", "明白", "感谢"],
            "negative": ["不是", "错了", "你不懂"],
            "base_score": 70,
            "length_bonus": {"min": 50, "max": 200, "bonus": 5}
        },
        "销售流程": {
            "positive": ["需求", "方案", "价值", "优势", "下一步"],
            "negative": ["随便", "都行", "无所谓"],
            "base_score": 70
        },
        "异议处理": {
            "positive": ["理解您的顾虑", "确实", "同时", "不过"],
            "negative": ["不可能", "绝对不", "你错了"],
            "base_score": 70
        },
        "成交能力": {
            "positive": ["合作", "开始", "签约", "确认", "行动"],
            "negative": ["再说", "以后", "不急"],
            "base_score": 70
        }
    }

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean", "default": True},
            "dimensions": {"type": "array"},
            "trend_threshold": {"type": "number", "default": 2}
        }
    }

    def __init__(self, config: CapabilityConfig) -> None:
        super().__init__(config)
        self._dimensions = self._validate_dimensions(
            self.config.get("dimensions", self.DEFAULT_DIMENSIONS)
        )
        self._trend_threshold = self.config.get("trend_threshold", 2)

    def _validate_dimensions(
        self, dimensions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Validate and normalize scoring dimensions.

        Ensures:
        - Each dimension has name and weight
        - Weights sum to 1.0 (normalizes if not)
        - Returns default dimensions if invalid

        Args:
            dimensions: List of dimension configurations

        Returns:
            Validated and normalized dimensions
        """
        if not isinstance(dimensions, list) or not dimensions:
            logger.warning("Invalid dimensions config, using defaults")
            return self.DEFAULT_DIMENSIONS

        # Validate each dimension has required fields
        valid_dimensions = []
        for dim in dimensions:
            if not isinstance(dim, dict):
                continue
            if "name" not in dim or "weight" not in dim:
                logger.warning(f"Dimension missing required fields: {dim}")
                continue
            if not isinstance(dim.get("weight"), (int, float)):
                logger.warning(f"Invalid weight type for dimension: {dim}")
                continue
            if dim["weight"] <= 0:
                logger.warning(f"Non-positive weight for dimension: {dim}")
                continue
            valid_dimensions.append(dim)

        if not valid_dimensions:
            logger.warning("No valid dimensions found, using defaults")
            return self.DEFAULT_DIMENSIONS

        # Check and normalize weights
        total_weight = sum(d["weight"] for d in valid_dimensions)
        if abs(total_weight - 1.0) > WEIGHT_TOLERANCE:
            logger.warning(
                f"Dimension weights sum to {total_weight:.4f}, normalizing to 1.0"
            )
            for dim in valid_dimensions:
                dim["weight"] = dim["weight"] / total_weight

        return valid_dimensions

    async def execute(
        self,
        context: AgentContext,
        input_data: Any,
    ) -> CapabilityResult:
        """计算本轮评分"""
        try:
            # 优先使用 Persona 的评分权重
            dimensions = context.get_scoring_weights() or self._dimensions

            text = ""
            if isinstance(input_data, str):
                text = input_data
            elif isinstance(input_data, dict):
                text = input_data.get("content", "")

            dimension_scores = []
            for dim in dimensions:
                dim_name = dim["name"]
                score = self._evaluate_dimension(dim_name, text, context)

                # 计算趋势
                prev_key = f"score_{dim_name}"
                prev_score = context.state.get(prev_key, score)
                delta = score - prev_score

                if delta > self._trend_threshold:
                    trend = "up"
                elif delta < -self._trend_threshold:
                    trend = "down"
                else:
                    trend = "stable"

                dimension_scores.append({
                    "name": dim_name,
                    "score": score,
                    "trend": trend,
                    "delta": round(delta)
                })

                # 更新状态
                context.state[prev_key] = score

            # 计算总分
            overall = sum(
                d["score"] * dim["weight"]
                for d, dim in zip(dimension_scores, dimensions)
            )

            # 更新历史 (with size limit)
            history_key = "score_history"
            history = context.state.get(history_key, [])
            history.append({
                "turn": context.turn_count,
                "overall": round(overall),
                "dimensions": dimension_scores
            })

            # Limit history size to prevent memory growth
            if len(history) > MAX_SCORE_HISTORY_SIZE:
                history = history[-MAX_SCORE_HISTORY_SIZE:]

            context.state[history_key] = history

            self._update_usage_count(context)

            feedback = self._generate_feedback(dimension_scores)

            logger.info(
                f"Realtime scoring completed: overall={round(overall)}",
                session_id=context.session_id
            )

            return CapabilityResult(
                success=True,
                data={
                    "overall": round(overall),
                    "dimensions": dimension_scores,
                    "feedback": feedback
                },
                feedback=feedback
            )

        except Exception as e:
            logger.error(f"Realtime scoring failed: {e}", session_id=context.session_id)
            return CapabilityResult(success=False, fallback="[SCORING_FAILED]")

    def _evaluate_dimension(
        self,
        dim_name: str,
        text: str,
        context: AgentContext
    ) -> int:
        """评估单个维度"""
        rules = self.SCORING_RULES.get(dim_name, {})
        base_score = rules.get("base_score", 70)

        score = base_score

        # 正向关键词加分
        for kw in rules.get("positive", []):
            if kw in text:
                score += 5

        # 负向关键词减分
        for kw in rules.get("negative", []):
            if kw in text:
                score -= 5

        # 长度奖励
        length_bonus = rules.get("length_bonus")
        if length_bonus:
            text_len = len(text)
            if length_bonus["min"] <= text_len <= length_bonus["max"]:
                score += length_bonus["bonus"]

        return max(0, min(100, score))

    def _generate_feedback(self, scores: list[dict[str, Any]]) -> str:
        """生成反馈建议"""
        if not scores:
            return ""

        lowest = min(scores, key=lambda x: x["score"])

        if lowest["score"] < 60:
            return f"建议加强{lowest['name']}方面的表现"
        elif lowest["score"] < 75:
            return f"注意提升{lowest['name']}"
        return "表现良好，继续保持"

    async def on_session_start(self, context: AgentContext) -> None:
        """会话开始时初始化"""
        await super().on_session_start(context)
        context.state["score_history"] = []
        logger.info("Realtime scoring initialized", session_id=context.session_id)

    async def on_session_end(self, context: AgentContext) -> dict[str, Any]:
        """会话结束时返回统计"""
        stats = await super().on_session_end(context)

        history = context.state.get("score_history", [])
        if history:
            # 计算平均分
            avg_overall = sum(h["overall"] for h in history) / len(history)
            stats["average_score"] = round(avg_overall)

            # 最高/最低分
            stats["highest_score"] = max(h["overall"] for h in history)
            stats["lowest_score"] = min(h["overall"] for h in history)

            # 最终分数
            stats["final_score"] = history[-1]["overall"]

        logger.info(
            "Realtime scoring session ended",
            session_id=context.session_id,
            stats=stats
        )
        return stats
