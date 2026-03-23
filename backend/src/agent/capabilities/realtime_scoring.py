"""
RealtimeScoringCapability - 实时评分能力

基于对话内容实时计算销售训练所需的价值表达与异议处理评分。
"""
from __future__ import annotations

from typing import Any, ClassVar

from agent.capabilities.base import BaseCapability, CapabilityConfig, CapabilityResult
from agent.capabilities.registry import CapabilityRegistry
from agent.context import AgentContext
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

MAX_SCORE_HISTORY_SIZE = 100
WEIGHT_TOLERANCE = 0.001


@CapabilityRegistry.register
class RealtimeScoringCapability(BaseCapability):
    """实时销售评分能力。"""

    capability_id: ClassVar[str] = "realtime_scoring"
    name: ClassVar[str] = "实时评分"
    description: ClassVar[str] = "基于对话内容实时计算销售价值评分"

    DEFAULT_DIMENSIONS: ClassVar[list[dict[str, Any]]] = [
        {"name": "价值表达", "weight": 0.24},
        {"name": "客户收益连接", "weight": 0.22},
        {"name": "证据使用", "weight": 0.18},
        {"name": "异议处理", "weight": 0.20},
        {"name": "推进下一步", "weight": 0.16},
    ]

    SCORING_RULES: ClassVar[dict[str, dict[str, Any]]] = {
        "价值表达": {
            "positive": [
                "价值",
                "收益",
                "回报",
                "roi",
                "提升",
                "降低",
                "缩短",
                "减少",
                "增长",
                "赢单",
                "转化",
                "效率",
                "结果",
            ],
            "negative": ["功能很多", "模块", "界面", "配置", "参数"],
            "base_score": 60,
            "stage_bonus": {"opening": 2, "presentation": 5, "discovery": 3},
        },
        "客户收益连接": {
            "positive": [
                "你们",
                "贵司",
                "客户",
                "团队",
                "成本",
                "营收",
                "利润",
                "效率",
                "留存",
                "复购",
                "预算",
                "风险",
                "场景",
            ],
            "negative": ["我们产品", "我们公司", "行业领先", "技术架构"],
            "base_score": 60,
            "stage_bonus": {"discovery": 5, "presentation": 4, "objection": 3},
        },
        "证据使用": {
            "positive": [
                "案例",
                "数据",
                "证据",
                "benchmark",
                "对标",
                "报告",
                "研究",
                "统计",
                "上线",
                "复盘",
                "客户a",
                "客户b",
            ],
            "negative": ["大概", "可能", "应该", "也许", "我觉得", "差不多"],
            "base_score": 58,
            "stage_bonus": {"presentation": 5, "objection": 5, "closing": 2},
        },
        "异议处理": {
            "positive": [
                "理解",
                "顾虑",
                "担心",
                "价格",
                "预算",
                "竞品",
                "风险",
                "但是",
                "不过",
                "同时",
                "先从",
                "试点",
                "低风险",
            ],
            "negative": ["不可能", "绝对不", "你错了", "没必要", "不需要考虑"],
            "base_score": 60,
            "stage_bonus": {"objection": 6, "closing": 2},
        },
        "推进下一步": {
            "positive": [
                "下一步",
                "安排",
                "试点",
                "demo",
                "演示",
                "报价",
                "确认",
                "负责人",
                "时间",
                "本周",
                "下周",
                "会议",
                "复盘",
                "poc",
                "试用",
            ],
            "negative": ["再说", "以后", "不急", "考虑一下", "回头再看"],
            "base_score": 58,
            "stage_bonus": {"closing": 7, "objection": 3, "presentation": 2},
        },
    }

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean", "default": True},
            "dimensions": {"type": "array"},
            "trend_threshold": {"type": "number", "default": 2},
        },
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
        if not isinstance(dimensions, list) or not dimensions:
            logger.warning("Invalid dimensions config, using defaults")
            return [dict(item) for item in self.DEFAULT_DIMENSIONS]

        valid_dimensions: list[dict[str, Any]] = []
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
            valid_dimensions.append({"name": str(dim["name"]), "weight": float(dim["weight"])})

        if not valid_dimensions:
            logger.warning("No valid dimensions found, using defaults")
            return [dict(item) for item in self.DEFAULT_DIMENSIONS]

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
        """计算本轮销售评分。"""
        try:
            raw_dimensions = context.get_scoring_weights() or self._dimensions
            dimensions = self._validate_dimensions(raw_dimensions)

            text = ""
            if isinstance(input_data, str):
                text = input_data
            elif isinstance(input_data, dict):
                text = str(input_data.get("content", "") or "")

            stage_name = self._resolve_stage(context, input_data)
            dimension_scores: list[dict[str, Any]] = []
            canonical_scores: dict[str, float] = {}

            for dim in dimensions:
                dim_name = dim["name"]
                score = self._evaluate_dimension(dim_name, text, context, stage_name)

                prev_key = f"score_{dim_name}"
                prev_score = context.state.get(prev_key, score)
                delta = score - int(prev_score)

                if delta > self._trend_threshold:
                    trend = "up"
                elif delta < -self._trend_threshold:
                    trend = "down"
                else:
                    trend = "stable"

                dimension_scores.append(
                    {
                        "name": dim_name,
                        "score": score,
                        "trend": trend,
                        "delta": round(delta),
                    }
                )
                canonical_scores[dim_name] = float(score)
                context.state[prev_key] = score

            overall_score = round(
                sum(canonical_scores[dim["name"]] * float(dim["weight"]) for dim in dimensions),
                2,
            )

            history_key = "score_history"
            history = context.state.get(history_key, [])
            history.append(
                {
                    "turn": context.turn_count,
                    "overall": round(overall_score, 1),
                    "overall_score": overall_score,
                    "dimensions": dimension_scores,
                    "dimension_scores": canonical_scores,
                }
            )
            if len(history) > MAX_SCORE_HISTORY_SIZE:
                history = history[-MAX_SCORE_HISTORY_SIZE:]
            context.state[history_key] = history

            self._update_usage_count(context)
            feedback = self._generate_feedback(canonical_scores)

            logger.info(
                f"Realtime scoring completed: overall={round(overall_score)}",
                session_id=context.session_id,
                stage_name=stage_name,
            )

            return CapabilityResult(
                success=True,
                data={
                    "overall": round(overall_score, 1),
                    "overall_score": overall_score,
                    "dimensions": dimension_scores,
                    "dimension_scores": canonical_scores,
                    "feedback": feedback,
                },
                feedback=feedback,
            )

        except (RuntimeError, ValueError, KeyError) as e:
            logger.error(f"Realtime scoring failed: {e}", session_id=context.session_id)
            return CapabilityResult(success=False, fallback="[SCORING_FAILED]")

    def _resolve_stage(self, context: AgentContext, input_data: Any) -> str:
        if isinstance(input_data, dict):
            for key in ("sales_stage", "stage_name", "stage"):
                value = input_data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().lower()

        state_value = context.state.get("current_stage")
        if isinstance(state_value, str) and state_value.strip():
            return state_value.strip().lower()
        return ""

    def _collect_context_text(self, context: AgentContext) -> str:
        recent_messages = context.get_recent_messages(4)
        return " ".join(
            str(message.get("content") or "")
            for message in recent_messages
            if isinstance(message, dict)
        )

    def _count_matches(self, haystack: str, keywords: list[str]) -> int:
        lowered = haystack.lower()
        return sum(1 for keyword in keywords if keyword.lower() in lowered)

    def _evaluate_dimension(
        self,
        dim_name: str,
        text: str,
        context: AgentContext,
        stage_name: str,
    ) -> int:
        rules = self.SCORING_RULES.get(dim_name, {})
        base_score = int(rules.get("base_score", 60))
        text_lower = text.lower()
        context_text = self._collect_context_text(context).lower()
        feature_only_terms = ["功能", "模块", "配置", "界面", "参数"]
        benefit_terms = ["收益", "roi", "成本", "效率", "营收", "转化", "留存", "复购"]

        score = base_score
        positive_matches = self._count_matches(text_lower, list(rules.get("positive", [])))
        negative_matches = self._count_matches(text_lower, list(rules.get("negative", [])))

        score += min(positive_matches * 5, 25)
        score -= min(negative_matches * 6, 18)

        stage_bonus = rules.get("stage_bonus", {})
        if isinstance(stage_bonus, dict):
            score += int(stage_bonus.get(stage_name, 0) or 0)

        if dim_name in {"价值表达", "客户收益连接"}:
            feature_signal = self._count_matches(text_lower, feature_only_terms)
            benefit_signal = self._count_matches(text_lower, benefit_terms)
            if feature_signal > 0 and benefit_signal == 0:
                score -= 8
            if any(token in text_lower for token in ("帮助你们", "对你们", "对贵司", "帮助贵司")):
                score += 6

        if dim_name == "证据使用":
            if any(token in text_lower for token in ("案例", "数据", "roi", "benchmark")):
                score += 4
            if any(token in text_lower for token in ("大概", "应该", "也许", "可能")):
                score -= 8

        if dim_name == "异议处理":
            objection_terms = ["价格", "预算", "竞品", "风险", "顾虑", "担心"]
            if self._count_matches(context_text, objection_terms) > 0 and self._count_matches(text_lower, objection_terms) > 0:
                score += 5
            if any(token in text_lower for token in ("理解", "顾虑", "担心")):
                score += 4

        if dim_name == "推进下一步":
            if any(token in text_lower for token in ("本周", "下周", "今天", "明天")):
                score += 4
            if any(token in text_lower for token in ("负责人", "时间", "试点", "会议", "demo")):
                score += 4

        if len(text) >= 60:
            score += 3
        if len(text) >= 140:
            score += 2

        return max(0, min(100, int(round(score))))

    def _generate_feedback(self, scores: dict[str, float]) -> str:
        if not scores:
            return ""

        lowest_name = min(scores, key=scores.get)
        feedback_map = {
            "价值表达": "少讲功能，多讲业务结果和价值变化。",
            "客户收益连接": "把产品能力明确翻译成客户的成本、效率或营收收益。",
            "证据使用": "补上案例、数据或ROI证据，让价值主张更可信。",
            "异议处理": "先承接价格、竞品或风险顾虑，再给回应。",
            "推进下一步": "明确试点、会议、报价或责任人，推动下一步落地。",
        }
        return feedback_map.get(lowest_name, "继续围绕客户价值推进对话。")

    async def on_session_start(self, context: AgentContext) -> None:
        await super().on_session_start(context)
        context.state["score_history"] = []
        logger.info("Realtime scoring initialized", session_id=context.session_id)

    async def on_session_end(self, context: AgentContext) -> dict[str, Any]:
        stats = await super().on_session_end(context)

        history = context.state.get("score_history", [])
        if history:
            avg_overall = sum(h["overall"] for h in history) / len(history)
            stats["average_score"] = round(avg_overall)
            stats["highest_score"] = max(h["overall"] for h in history)
            stats["lowest_score"] = min(h["overall"] for h in history)
            stats["final_score"] = history[-1]["overall"]

        logger.info(
            "Realtime scoring session ended",
            session_id=context.session_id,
            stats=stats,
        )
        return stats
