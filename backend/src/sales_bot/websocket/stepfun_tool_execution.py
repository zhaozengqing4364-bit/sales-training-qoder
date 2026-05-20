"""StepFun tool execution boundary for realtime handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sales_bot.websocket.components.stepfun_function_call_helpers import (
    build_function_call_output_event,
    build_unsupported_function_output,
)
from sales_bot.websocket.components.stepfun_internal_knowledge_searcher import (
    search_internal_knowledge,
)
from sales_bot.websocket.components.stepfun_tool_helpers import (
    build_stepfun_tools_from_policy,
)

InternalKnowledgeSearcher = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolExecutionContext:
    """Runtime seams required for executing StepFun tools."""

    session_id: str
    effective_policy: dict[str, Any]
    session_factory: Callable[[], Any]
    knowledge_service_factory: Callable[[Any], Any]
    record_metric: Callable[..., Awaitable[None]]


class StepFunToolExecutionModule:
    """Small interface around StepFun tool definitions and execution seams."""

    def __init__(
        self,
        *,
        internal_knowledge_searcher: InternalKnowledgeSearcher = search_internal_knowledge,
    ) -> None:
        self._internal_knowledge_searcher = internal_knowledge_searcher

    def build_tools_from_policy(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        """Build StepFun tool definitions from resolved effective policy."""
        return build_stepfun_tools_from_policy(policy)

    def enforce_guardrails(
        self,
        tools: list[dict[str, Any]],
        policy: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Filter tool list using final effective policy guarantees."""
        filtered_tools = list(tools)
        tool_policy = policy.get("tool_policy")
        if not isinstance(tool_policy, dict):
            tool_policy = {}

        knowledge_base_ids = policy.get("knowledge_base_ids")
        has_bound_knowledge_base = isinstance(knowledge_base_ids, list) and bool(
            [item for item in knowledge_base_ids if str(item).strip()]
        )
        network_access_mode = str(
            tool_policy.get("network_access_mode") or "off"
        ).lower()
        allow_web_search_without_kb = bool(
            tool_policy.get("allow_web_search_without_kb", False)
        )

        should_remove_web_search = (
            network_access_mode == "off"
            or has_bound_knowledge_base
            or not allow_web_search_without_kb
        )
        if should_remove_web_search:
            filtered_tools = [
                tool
                for tool in filtered_tools
                if str(tool.get("type") or "").lower() != "web_search"
            ]
        return filtered_tools

    def build_tool_response(
        self,
        *,
        tool_call_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a StepFun function_call_output event for a successful tool result."""
        return build_function_call_output_event(
            call_id=tool_call_id,
            output_payload=result,
        )

    def build_tool_error_response(
        self,
        *,
        tool_call_id: str,
        error: str,
    ) -> dict[str, Any]:
        """Build a StepFun function_call_output event for a tool error."""
        return self.build_tool_response(
            tool_call_id=tool_call_id,
            result={"error": str(error)},
        )

    async def execute_tool(
        self,
        tool_call: dict[str, Any],
        *,
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        """Execute one supported StepFun tool through injected runtime seams."""
        tool_name = str(tool_call.get("name") or "")
        arguments_obj = tool_call.get("arguments")
        if not isinstance(arguments_obj, dict):
            arguments_obj = {}

        if tool_name != "search_internal_knowledge":
            return build_unsupported_function_output(tool_name or "unknown")

        return await self._internal_knowledge_searcher(
            arguments_obj={
                **arguments_obj,
                "session_id": context.session_id,
            },
            effective_policy=context.effective_policy,
            session_factory=context.session_factory,
            knowledge_service_cls=context.knowledge_service_factory,
            record_metric=context.record_metric,
        )
