"""
AI-based Real-time Scoring Service
使用 LLM 异步评估对话质量
"""

from __future__ import annotations

import json

from common.ai.llm_service import LLMService
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class AIScoringService:
    """AI-based scoring service for real-time evaluation."""

    DEFAULT_DIMENSIONS = [
        {
            "name": "专业度",
            "weight": 0.25,
            "description": "产品知识、行业理解、专业术语使用",
        },
        {
            "name": "沟通技巧",
            "weight": 0.25,
            "description": "倾听能力、表达清晰、情绪管理",
        },
        {
            "name": "销售流程",
            "weight": 0.20,
            "description": "需求挖掘、方案呈现、推进节奏",
        },
        {
            "name": "异议处理",
            "weight": 0.15,
            "description": "应对质疑、化解顾虑、引导思路",
        },
        {
            "name": "成交能力",
            "weight": 0.15,
            "description": "促成决策、把握时机、推动行动",
        },
    ]

    SCORING_PROMPT_TEMPLATE = """你是一位资深的销售培训专家，正在评估销售人员的对话表现。

请根据以下对话内容，对销售人员的表现在各个维度进行评分（0-100分）。

## 评估维度
{dimensions}

## 对话历史
{conversation}

## 当前阶段
{stage_name}

## 评估要求
1. 每个维度给出 0-100 的分数
2. 分数应该基于实际表现，不要给出默认分
3. 考虑对话的上下文和连贯性
4. 给出具体的评分理由
5. 指出主要优势和改进点

## 输出格式（JSON）
{{
    "scores": {{
        "专业度": <分数>,
        "沟通技巧": <分数>,
        "销售流程": <分数>,
        "异议处理": <分数>,
        "成交能力": <分数>
    }},
    "overall_score": <加权总分>,
    "feedback": "总体评价和建议（50字以内）",
    "strengths": ["优势1", "优势2"],
    "improvements": ["改进点1", "改进点2"]
}}

请直接输出 JSON，不要包含其他内容。"""

    def __init__(self, llm_service: LLMService | None = None):
        self.llm = llm_service or LLMService()

    async def evaluate_conversation(
        self,
        conversation_history: list[dict],
        stage_name: str = "开场破冰",
        dimensions: list[dict] | None = None,
    ) -> Result[dict]:
        """
        使用 AI 异步评估对话质量。

        Args:
            conversation_history: 对话历史
            stage_name: 当前阶段名称
            dimensions: 评分维度配置

        Returns:
            评分结果
        """
        try:
            dims = dimensions or self.DEFAULT_DIMENSIONS

            # 格式化维度描述
            dim_text = "\n".join(
                [
                    f"- {d['name']} (权重{d['weight'] * 100:.0f}%): {d.get('description', '')}"
                    for d in dims
                ]
            )

            # 格式化对话
            conv_text = self._format_conversation(conversation_history)

            # 构建提示词
            prompt = self.SCORING_PROMPT_TEMPLATE.format(
                dimensions=dim_text, conversation=conv_text, stage_name=stage_name
            )

            # 调用 LLM
            result = await self.llm.generate(
                prompt=prompt,
                session_id="ai_scoring",
                system_message="你是一位资深的销售培训专家，擅长评估销售对话质量。请严格按照JSON格式输出评分结果。",
            )

            if not result.is_success:
                logger.warning(f"AI scoring failed: {result.fallback}")
                return Result.fail("[AI_SCORING_FAILED]")

            # 解析 JSON 响应
            try:
                response_text = result.value.strip()
                # 提取 JSON 部分（如果 LLM 返回了 markdown 代码块）
                if "```json" in response_text:
                    response_text = (
                        response_text.split("```json")[1].split("```")[0].strip()
                    )
                elif "```" in response_text:
                    response_text = (
                        response_text.split("```")[1].split("```")[0].strip()
                    )

                scoring_result = json.loads(response_text)

                # 验证必要的字段
                if "scores" not in scoring_result:
                    logger.error("AI scoring response missing 'scores' field")
                    return Result.fail("[INVALID_SCORING_RESPONSE]")

                # 转换为前端需要的格式
                formatted_result = self._format_result(scoring_result, dims)
                return Result.ok(formatted_result)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI scoring response: {e}")
                return Result.fail("[SCORING_PARSE_ERROR]")

        except (ConnectionError, TimeoutError, RuntimeError, ValueError, OSError) as e:
            logger.error(f"AI scoring error: {e}", exc_info=True)
            return Result.fail(f"[AI_SCORING_ERROR:{str(e)}]")

    def _format_conversation(self, conversation: list[dict]) -> str:
        """格式化对话历史。"""
        lines = []
        for msg in conversation[-10:]:  # 只取最近10轮，控制token长度
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                lines.append(f"销售人员: {content}")
            elif role in ["assistant", "bot", "ai"]:
                lines.append(f"客户: {content}")
        return "\n".join(lines)

    def _format_result(self, raw_result: dict, dimensions: list[dict]) -> dict:
        """将 AI 评分结果转换为前端格式。"""
        scores = raw_result.get("scores", {})

        # 构建维度分数列表
        dimension_scores = []
        for dim in dimensions:
            dim_name = dim["name"]
            score = scores.get(dim_name, 70)
            dimension_scores.append(
                {"name": dim_name, "score": round(score), "weight": dim["weight"]}
            )

        # 计算加权总分
        overall = sum(d["score"] * d["weight"] for d in dimension_scores)

        return {
            "overall": round(overall),
            "dimensions": dimension_scores,
            "feedback": raw_result.get("feedback", ""),
            "strengths": raw_result.get("strengths", []),
            "improvements": raw_result.get("improvements", []),
        }

    async def evaluate_with_fallback(
        self,
        conversation_history: list[dict],
        stage_name: str = "开场破冰",
        dimensions: list[dict] | None = None,
    ) -> dict:
        """
        评估对话，失败时返回默认评分。

        Returns:
            评分结果字典（不会失败）
        """
        result = await self.evaluate_conversation(
            conversation_history, stage_name, dimensions
        )

        if result.is_success:
            return result.value

        # 返回默认评分
        dims = dimensions or self.DEFAULT_DIMENSIONS
        logger.warning(f"AI scoring failed, using default scores: {result.fallback}")
        return {
            "overall": 70,
            "dimensions": [
                {"name": d["name"], "score": 70, "weight": d["weight"]} for d in dims
            ],
            "feedback": "评分服务暂时不可用",
            "strengths": [],
            "improvements": [],
        }
