"""
FuzzyDetectionCapability - 模糊词检测能力

检测用户语音中的模糊表达（如"大概"、"可能"、"也许"等），
并提供实时反馈和改进建议。

References:
- Requirements: R6 (模糊词检测)
- Design: Section 8 (Fuzzy Detection Capability)
"""

from __future__ import annotations

import re
import time
from typing import Any, ClassVar

from agent.capabilities.base import BaseCapability, CapabilityConfig, CapabilityResult
from agent.capabilities.registry import CapabilityRegistry
from agent.context import AgentContext
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# Security constants for regex patterns
MAX_PATTERN_LENGTH = 200  # Maximum regex pattern length
MAX_PATTERNS_COUNT = 20  # Maximum number of custom patterns
DANGEROUS_REGEX_PATTERNS = [
    r"\(\?[^)]*\)",  # Lookahead/lookbehind assertions
    r"\{[0-9]{3,}\}",  # Large repetition counts
    r"(\.\*){2,}",  # Multiple greedy wildcards
    r"(\.\+){2,}",  # Multiple greedy plus
]


@CapabilityRegistry.register
class FuzzyDetectionCapability(BaseCapability):
    """
    模糊词检测能力

    检测用户语音中的模糊表达，支持三种类型：
    - uncertain: 不确定词（大概、可能、也许）
    - filler: 填充词（嗯、那个、就是说）
    - vague: 模糊数值（差不多、左右、大约）

    配置项:
    - fuzzy_patterns: 自定义模糊词模式列表
    - detection_mode: 检测模式 (realtime/batch)
    - cooldown_seconds: 同类型检测冷却时间
    """

    capability_id: ClassVar[str] = "fuzzy_detection"
    name: ClassVar[str] = "模糊词检测"
    description: ClassVar[str] = "检测用户语音中的模糊表达，提供实时反馈"

    # 默认模糊词模式
    DEFAULT_PATTERNS: ClassVar[list[dict[str, Any]]] = [
        {
            "pattern": r"大概|可能|也许|应该|估计|好像",
            "category": "uncertain",
            "suggestion": "请给出具体数据或明确表态",
            "severity": "high",
        },
        {
            "pattern": r"嗯+|那个|就是说|然后|这个",
            "category": "filler",
            "suggestion": "减少填充词，保持表达流畅",
            "severity": "low",
        },
        {
            "pattern": r"差不多|左右|大约|大致|基本上",
            "category": "vague",
            "suggestion": "请给出精确数值或具体范围",
            "severity": "medium",
        },
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "是否启用模糊词检测",
                "default": True,
            },
            "fuzzy_patterns": {
                "type": "array",
                "description": "自定义模糊词模式列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "category": {"type": "string"},
                        "suggestion": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                    "required": ["pattern", "category", "suggestion", "severity"],
                },
            },
            "detection_mode": {
                "type": "string",
                "enum": ["realtime", "batch"],
                "default": "realtime",
                "description": "检测模式：realtime=实时检测，batch=批量检测",
            },
            "cooldown_seconds": {
                "type": "number",
                "minimum": 0,
                "maximum": 60,
                "default": 10,
                "description": "同类型检测冷却时间（秒）",
            },
        },
    }

    def __init__(self, config: CapabilityConfig) -> None:
        super().__init__(config)
        self._patterns = self._validate_patterns(
            self.config.get("fuzzy_patterns", self.DEFAULT_PATTERNS)
        )
        self._cooldown = self.config.get("cooldown_seconds", 10)
        self._compiled_patterns: dict[str, re.Pattern] = {}
        self._compile_patterns()

    def _validate_patterns(
        self, patterns: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Validate and sanitize custom patterns for security.

        Args:
            patterns: List of pattern configurations

        Returns:
            Validated patterns (unsafe patterns filtered out)
        """
        if not isinstance(patterns, list):
            logger.warning("Invalid patterns config, using defaults")
            return self.DEFAULT_PATTERNS

        # Limit number of patterns
        if len(patterns) > MAX_PATTERNS_COUNT:
            logger.warning(
                f"Too many patterns ({len(patterns)}), limiting to {MAX_PATTERNS_COUNT}"
            )
            patterns = patterns[:MAX_PATTERNS_COUNT]

        validated = []
        for pattern_config in patterns:
            if not isinstance(pattern_config, dict):
                continue

            pattern_str = pattern_config.get("pattern", "")

            # Check pattern length
            if len(pattern_str) > MAX_PATTERN_LENGTH:
                logger.warning(
                    f"Pattern too long ({len(pattern_str)} chars), skipping",
                    pattern_preview=pattern_str[:50],
                )
                continue

            # Check for dangerous patterns (ReDoS prevention)
            is_dangerous = False
            for dangerous in DANGEROUS_REGEX_PATTERNS:
                if re.search(dangerous, pattern_str):
                    logger.warning(
                        "Dangerous regex pattern detected, skipping",
                        pattern_preview=pattern_str[:50],
                    )
                    is_dangerous = True
                    break

            if is_dangerous:
                continue

            # Validate required fields
            if not all(
                k in pattern_config
                for k in ["pattern", "category", "suggestion", "severity"]
            ):
                logger.warning("Pattern missing required fields, skipping")
                continue

            # Validate severity
            if pattern_config.get("severity") not in ["low", "medium", "high"]:
                pattern_config["severity"] = "medium"

            validated.append(pattern_config)

        return validated if validated else self.DEFAULT_PATTERNS

    def _compile_patterns(self) -> None:
        """预编译正则表达式以提高性能"""
        for pattern_config in self._patterns:
            pattern_str = pattern_config["pattern"]
            try:
                self._compiled_patterns[pattern_str] = re.compile(pattern_str)
            except re.error as e:
                logger.warning(f"Invalid regex pattern: {pattern_str}", error=str(e))

    async def execute(
        self,
        context: AgentContext,
        input_data: Any,
    ) -> CapabilityResult:
        """
        检测文本中的模糊词

        Args:
            context: AgentContext with session state
            input_data: 用户输入文本 (str)

        Returns:
            CapabilityResult with detections list
        """
        try:
            # 验证输入 - 明确处理 None 和非字符串
            if input_data is None:
                return CapabilityResult(success=True, data={"detections": []})

            if not isinstance(input_data, str):
                return CapabilityResult(success=True, data={"detections": []})

            text = input_data.strip()
            if not text:
                return CapabilityResult(success=True, data={"detections": []})
            detections = []
            now = time.time()

            for pattern_config in self._patterns:
                pattern_str = pattern_config["pattern"]
                compiled = self._compiled_patterns.get(pattern_str)

                if compiled is None:
                    continue

                matches = compiled.findall(text)
                if not matches:
                    continue

                # 检查冷却时间
                category = pattern_config["category"]
                cooldown_key = f"fuzzy_cooldown_{category}"
                last_detection = context.state.get(cooldown_key, 0)

                if now - last_detection < self._cooldown:
                    logger.debug(
                        f"Skipping {category} detection due to cooldown",
                        session_id=context.session_id,
                    )
                    continue

                # 记录检测结果
                detection = {
                    "category": category,
                    "matched": list(set(matches)),
                    "suggestion": pattern_config["suggestion"],
                    "severity": pattern_config["severity"],
                }
                detections.append(detection)

                # 更新冷却时间
                context.state[cooldown_key] = now

                # 更新统计
                stats_key = f"fuzzy_detection_{category}_count"
                context.state[stats_key] = context.state.get(stats_key, 0) + len(
                    matches
                )

            # 更新使用计数
            self._update_usage_count(context)

            # 判断是否需要打断
            should_interrupt = any(d["severity"] == "high" for d in detections)

            # 生成反馈
            feedback = self._generate_feedback(detections) if detections else None

            logger.debug(
                "Fuzzy detection completed",
                session_id=context.session_id,
                detection_count=len(detections),
            )

            return CapabilityResult(
                success=True,
                data={"detections": detections},
                should_interrupt=should_interrupt,
                feedback=feedback,
            )

        except (RuntimeError, ValueError, KeyError) as e:
            logger.error(f"Fuzzy detection failed: {e}", session_id=context.session_id)
            return CapabilityResult(success=False, fallback="[FUZZY_DETECTION_FAILED]")

    def _generate_feedback(self, detections: list[dict[str, Any]]) -> str:
        """生成反馈消息"""
        if not detections:
            return ""

        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        sorted_detections = sorted(
            detections, key=lambda d: severity_order.get(d["severity"], 3)
        )

        # 取最高严重程度的检测
        top_detection = sorted_detections[0]
        matched_words = "、".join(top_detection["matched"][:3])

        return f"检测到模糊表达「{matched_words}」，{top_detection['suggestion']}"

    async def on_session_start(self, context: AgentContext) -> None:
        """会话开始时初始化状态"""
        await super().on_session_start(context)

        # 初始化各类型计数
        for pattern_config in self._patterns:
            category = pattern_config["category"]
            context.state[f"fuzzy_detection_{category}_count"] = 0

    async def on_session_end(self, context: AgentContext) -> dict[str, Any]:
        """会话结束时返回统计数据"""
        stats = await super().on_session_end(context)

        # 添加各类型统计
        category_stats = {}
        for pattern_config in self._patterns:
            category = pattern_config["category"]
            count = context.state.get(f"fuzzy_detection_{category}_count", 0)
            category_stats[category] = count

        stats["by_category"] = category_stats
        stats["total_detections"] = sum(category_stats.values())

        return stats
