"""
SalesStageCapability - 销售阶段识别能力

基于对话历史识别当前销售阶段，提供阶段指导和进度计算。

References:
- Requirements: R7 (销售阶段识别)
- Design: Section 9 (Sales Stage Capability)
"""
from __future__ import annotations

from typing import Any, ClassVar

from agent.capabilities.base import BaseCapability, CapabilityConfig, CapabilityResult
from agent.capabilities.registry import CapabilityRegistry
from agent.context import AgentContext
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@CapabilityRegistry.register
class SalesStageCapability(BaseCapability):
    """
    销售阶段识别能力
    
    识别5个销售阶段：
    1. opening - 开场破冰
    2. discovery - 需求挖掘
    3. presentation - 方案呈现
    4. objection - 异议处理
    5. closing - 促成成交
    """

    capability_id: ClassVar[str] = "sales_stage"
    name: ClassVar[str] = "销售阶段识别"
    description: ClassVar[str] = "基于对话历史识别当前销售阶段"

    DEFAULT_STAGES: ClassVar[list[dict[str, Any]]] = [
        {
            "id": "opening",
            "name": "开场破冰",
            "key_actions": ["建立信任", "了解背景"],
            "keywords": ["你好", "介绍", "了解", "认识"],
            "guidance": "建立良好的第一印象"
        },
        {
            "id": "discovery",
            "name": "需求挖掘",
            "key_actions": ["深入痛点", "确认需求"],
            "keywords": ["需求", "问题", "痛点", "挑战", "目标"],
            "guidance": "深入挖掘客户需求和痛点"
        },
        {
            "id": "presentation",
            "name": "方案呈现",
            "key_actions": ["匹配需求", "展示价值"],
            "keywords": ["方案", "产品", "功能", "价值", "优势"],
            "guidance": "展示产品价值，匹配客户需求"
        },
        {
            "id": "objection",
            "name": "异议处理",
            "key_actions": ["处理疑虑", "提供证据"],
            "keywords": ["但是", "担心", "价格", "竞品", "考虑"],
            "guidance": "耐心处理客户疑虑"
        },
        {
            "id": "closing",
            "name": "促成成交",
            "key_actions": ["推动决策", "行动号召"],
            "keywords": ["合作", "签约", "下一步", "决定", "购买"],
            "guidance": "推动客户做出决策"
        }
    ]

    # Valid stage transitions (state machine)
    # None means any transition is allowed from that stage
    VALID_TRANSITIONS: ClassVar[dict[str, list[str] | None]] = {
        "opening": ["discovery", "presentation"],  # Can skip to presentation
        "discovery": ["presentation", "objection"],
        "presentation": ["objection", "closing", "discovery"],  # Can go back
        "objection": ["presentation", "closing"],  # Can revisit presentation
        "closing": None,  # Can stay or end
    }

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean", "default": True},
            "stages": {"type": "array"},
            "history_window": {"type": "number", "default": 5},
            "enforce_transitions": {
                "type": "boolean",
                "default": False,
                "description": "Whether to enforce valid stage transitions"
            }
        }
    }

    def __init__(self, config: CapabilityConfig) -> None:
        super().__init__(config)
        self._stages = self.config.get("stages", self.DEFAULT_STAGES)
        self._history_window = self.config.get("history_window", 5)
        self._stage_order = [s["id"] for s in self._stages]
        self._enforce_transitions = self.config.get("enforce_transitions", False)

    async def execute(
        self,
        context: AgentContext,
        input_data: Any,
    ) -> CapabilityResult:
        """基于对话历史判断当前阶段"""
        try:
            # Handle different input types
            if isinstance(input_data, list):
                history = input_data
            else:
                history = context.conversation_history.copy()
                if isinstance(input_data, str) and input_data.strip():
                    history.append({"role": "user", "content": input_data})

            current_stage = self._analyze_stage(history)
            previous_stage = context.state.get("current_stage")

            # Validate transition if enforcement is enabled
            if self._enforce_transitions and previous_stage:
                if not self._is_valid_transition(previous_stage, current_stage):
                    logger.debug(
                        "Invalid stage transition "
                        f"{previous_stage} -> {current_stage}, keeping current",
                        session_id=context.session_id
                    )
                    current_stage = previous_stage

            stage_info = self._get_stage_info(current_stage)
            progress = self._calculate_progress(current_stage)

            # Update state
            context.state["current_stage"] = current_stage
            context.state["stage_history"] = context.state.get("stage_history", [])

            stage_changed = current_stage != previous_stage
            if stage_changed and previous_stage is not None:
                context.state["stage_history"].append({
                    "from": previous_stage,
                    "to": current_stage,
                    "turn": context.turn_count
                })

            self._update_usage_count(context)

            result_data = {
                "current_stage": current_stage,
                "stage_name": stage_info["name"],
                "key_actions": stage_info.get("key_actions", []),
                "guidance": stage_info.get("guidance", ""),
                "progress": progress,
                "stage_changed": stage_changed
            }

            if previous_stage:
                result_data["previous_stage"] = previous_stage

            logger.debug(
                "Sales stage analysis completed",
                session_id=context.session_id,
                current_stage=current_stage,
                stage_changed=stage_changed
            )

            return CapabilityResult(
                success=True,
                data=result_data,
                should_interrupt=stage_changed,
                feedback=self._generate_feedback(stage_info, stage_changed)
            )

        except Exception as e:
            logger.error(
                f"Sales stage analysis failed: {e}",
                session_id=context.session_id
            )
            return CapabilityResult(success=False, fallback="[SALES_STAGE_FAILED]")

    def _analyze_stage(self, history: list[dict[str, Any]]) -> str:
        """分析当前阶段 - 基于关键词规则"""
        if not history:
            return "opening"

        # Get recent messages
        recent = history[-self._history_window:]
        text = " ".join([m.get("content", "") for m in recent]).lower()

        # Score each stage based on keyword matches
        stage_scores: dict[str, int] = {}
        for stage in self._stages:
            score = sum(1 for kw in stage["keywords"] if kw in text)
            stage_scores[stage["id"]] = score

        # Find best matching stage
        max_score = max(stage_scores.values()) if stage_scores else 0
        if max_score == 0:
            return "opening"

        # If multiple stages have same score, prefer later stages
        best_stage = "opening"
        best_score = 0
        best_order = -1

        for stage_id, score in stage_scores.items():
            if score > best_score:
                best_score = score
                best_stage = stage_id
                best_order = self._stage_order.index(stage_id)
            elif score == best_score and score > 0:
                order = self._stage_order.index(stage_id)
                if order > best_order:
                    best_stage = stage_id
                    best_order = order

        return best_stage

    def _get_stage_info(self, stage_id: str) -> dict[str, Any]:
        """获取阶段信息"""
        for stage in self._stages:
            if stage["id"] == stage_id:
                return stage
        return self._stages[0]

    def _calculate_progress(self, stage_id: str) -> float:
        """计算进度 (0-1)"""
        try:
            idx = self._stage_order.index(stage_id)
            return (idx + 1) / len(self._stage_order)
        except ValueError:
            return 0.0

    def _is_valid_transition(self, from_stage: str, to_stage: str) -> bool:
        """
        Check if a stage transition is valid.

        Args:
            from_stage: Current stage ID
            to_stage: Target stage ID

        Returns:
            True if transition is valid, False otherwise
        """
        if from_stage == to_stage:
            return True  # Staying in same stage is always valid

        valid_targets = self.VALID_TRANSITIONS.get(from_stage)
        if valid_targets is None:
            return True  # No restrictions for this stage

        return to_stage in valid_targets

    def _generate_feedback(self, stage_info: dict, changed: bool) -> str | None:
        """生成阶段反馈"""
        if not changed:
            return None
        return f"进入{stage_info['name']}阶段：{stage_info.get('guidance', '')}"

    async def on_session_start(self, context: AgentContext) -> None:
        """会话开始时初始化状态"""
        await super().on_session_start(context)
        context.state["current_stage"] = "opening"
        context.state["stage_history"] = []
        logger.info(
            "Sales stage capability initialized",
            session_id=context.session_id
        )

    async def on_session_end(self, context: AgentContext) -> dict[str, Any]:
        """会话结束时返回统计数据"""
        stats = await super().on_session_end(context)
        stats["final_stage"] = context.state.get("current_stage", "opening")
        stats["stage_transitions"] = len(context.state.get("stage_history", []))
        stats["stage_history"] = context.state.get("stage_history", [])

        logger.info(
            "Sales stage session ended",
            session_id=context.session_id,
            final_stage=stats["final_stage"],
            transitions=stats["stage_transitions"]
        )
        return stats
