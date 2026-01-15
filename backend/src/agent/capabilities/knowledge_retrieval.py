"""
KnowledgeRetrievalCapability - 知识库检索能力

在对话中自动检索相关知识，合并 Agent 和 Persona 的知识库。

References:
- Requirements: R5 (知识库检索)
- Design: Section 7 (Knowledge Retrieval Capability)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from agent.capabilities.base import BaseCapability, CapabilityConfig, CapabilityResult
from agent.capabilities.registry import CapabilityRegistry
from agent.context import AgentContext
from common.monitoring.logger import get_logger

if TYPE_CHECKING:
    from common.knowledge.service import KnowledgeService

logger = get_logger(__name__)


@CapabilityRegistry.register
class KnowledgeRetrievalCapability(BaseCapability):
    """
    知识库检索能力

    在对话中自动检索相关知识，支持：
    - 合并 Agent 和 Persona 的知识库
    - 相似度阈值过滤
    - 结果格式化为 LLM 上下文
    """

    capability_id: ClassVar[str] = "knowledge_retrieval"
    name: ClassVar[str] = "知识库检索"
    description: ClassVar[str] = "在对话中自动检索相关知识"

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean", "default": True},
            "top_k": {
                "type": "number",
                "minimum": 1,
                "maximum": 10,
                "default": 3,
                "description": "返回最相关的K个结果"
            },
            "similarity_threshold": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.7,
                "description": "相似度阈值"
            },
            "include_source": {
                "type": "boolean",
                "default": True,
                "description": "是否在结果中包含来源信息"
            }
        }
    }

    def __init__(
        self,
        config: CapabilityConfig,
        knowledge_service: KnowledgeService | None = None
    ) -> None:
        super().__init__(config)
        self._knowledge_service = knowledge_service
        self._top_k = self.config.get("top_k", 3)
        self._threshold = self.config.get("similarity_threshold", 0.7)
        self._include_source = self.config.get("include_source", True)

    def set_knowledge_service(self, service: KnowledgeService) -> None:
        """设置知识库服务（延迟注入）"""
        self._knowledge_service = service

    async def execute(
        self,
        context: AgentContext,
        input_data: Any,
    ) -> CapabilityResult:
        """检索相关知识"""
        try:
            # 验证输入
            if not isinstance(input_data, str) or not input_data.strip():
                return CapabilityResult(
                    success=True,
                    data={"context": "", "results": []}
                )

            query = input_data.strip()

            # 合并 Agent 和 Persona 的知识库 ID
            kb_ids = self._get_knowledge_base_ids(context)

            if not kb_ids:
                logger.debug(
                    "No knowledge bases configured",
                    session_id=context.session_id
                )
                return CapabilityResult(
                    success=True,
                    data={"context": "", "results": []}
                )

            # 使用 KnowledgeService 的 search_multiple 方法
            all_results: list[dict[str, Any]] = []

            if self._knowledge_service:
                search_result = await self._knowledge_service.search_multiple(
                    kb_ids=kb_ids,
                    query=query,
                    top_k=self._top_k,
                    similarity_threshold=self._threshold
                )
                if search_result.is_success:
                    all_results = search_result.value
                else:
                    # Log the failure reason for debugging
                    logger.warning(
                        "Knowledge search returned failure",
                        session_id=context.session_id,
                        error=getattr(search_result, 'error', 'Unknown error'),
                        kb_ids=kb_ids,
                        query_preview=query[:50] if query else ""
                    )
            else:
                logger.warning(
                    "Knowledge service not available",
                    session_id=context.session_id
                )

            # 格式化为 LLM 上下文
            formatted_context = self._format_context(all_results)

            # 更新统计
            self._update_usage_count(context)
            context.state["knowledge_retrieval_count"] = (
                context.state.get("knowledge_retrieval_count", 0) + len(all_results)
            )

            logger.debug(
                "Knowledge retrieval completed",
                session_id=context.session_id,
                result_count=len(all_results)
            )

            return CapabilityResult(
                success=True,
                data={
                    "context": formatted_context,
                    "results": all_results,
                    "query": query,
                    "kb_ids": kb_ids
                }
            )

        except Exception as e:
            logger.error(
                f"Knowledge retrieval failed: {e}",
                session_id=context.session_id
            )
            return CapabilityResult(
                success=False,
                fallback="[KNOWLEDGE_RETRIEVAL_FAILED]"
            )

    def _get_knowledge_base_ids(self, context: AgentContext) -> list[str]:
        """获取合并后的知识库 ID 列表"""
        kb_ids: list[str] = []

        # Agent 默认知识库
        agent_kbs = context.agent_config.get("default_knowledge_base_ids", [])
        if agent_kbs:
            kb_ids.extend(agent_kbs)

        # Persona 知识库
        persona_kbs = context.persona_config.get("knowledge_base_ids", [])
        if persona_kbs:
            kb_ids.extend(persona_kbs)

        # 去重
        return list(dict.fromkeys(kb_ids))

    def _format_context(self, results: list[dict[str, Any]]) -> str:
        """格式化为 LLM 上下文"""
        if not results:
            return ""

        formatted_parts = []
        for r in results:
            content = r.get("content", "")
            if not content:
                continue

            if self._include_source:
                source = r.get("source", "未知来源")
                formatted_parts.append(f"[来源: {source}]\n{content}")
            else:
                formatted_parts.append(content)

        return "\n\n---\n\n".join(formatted_parts)

    async def on_session_start(self, context: AgentContext) -> None:
        await super().on_session_start(context)
        context.state["knowledge_retrieval_count"] = 0

    async def on_session_end(self, context: AgentContext) -> dict[str, Any]:
        stats = await super().on_session_end(context)
        stats["total_retrievals"] = context.state.get(
            "knowledge_retrieval_count", 0
        )
        return stats
