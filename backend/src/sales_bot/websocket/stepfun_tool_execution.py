"""StepFun tool execution boundary for realtime handlers."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
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


class ToolRoutingStatus(StrEnum):
    EXECUTE = "execute"
    SKIP_DUPLICATE = "skip_duplicate"


@dataclass(frozen=True)
class ToolRoutingDecision:
    status: ToolRoutingStatus
    stable_key: str
    should_execute: bool
    should_trigger_grounding: bool = False


@dataclass(frozen=True)
class ToolExecutionDiagnostics:
    total_calls: int = 0
    duplicate_skips: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    grounding_triggers: int = 0
    errors: int = 0


class StepFunToolExecutionModule:
    """Small interface around StepFun tool definitions and execution seams."""

    def __init__(
        self,
        *,
        internal_knowledge_searcher: InternalKnowledgeSearcher = search_internal_knowledge,
        clock: Callable[[], float] = time.monotonic,
        cache_max_entries: int = 128,
    ) -> None:
        self._internal_knowledge_searcher = internal_knowledge_searcher
        self._clock = clock
        self._cache_max_entries = max(1, int(cache_max_entries or 1))
        self._call_registry: dict[str, set[str]] = {}
        self._completed_call_ids: set[str] = set()
        self._result_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._diagnostics = ToolExecutionDiagnostics()

    def decide_tool_routing(
        self,
        tool_call: dict[str, Any],
        *,
        turn_context: dict[str, Any] | None = None,
    ) -> ToolRoutingDecision:
        """Decide whether a tool call should execute in the current turn."""
        tool_name = str(tool_call.get("name") or "unknown")
        arguments_obj = tool_call.get("arguments")
        if not isinstance(arguments_obj, dict):
            arguments_obj = {}

        context = turn_context if isinstance(turn_context, dict) else {}
        call_id = str(tool_call.get("id") or context.get("call_id") or "").strip()
        if call_id and call_id in self._completed_call_ids:
            stable_key = f"completed_call_id:{call_id}"
            self._record_total_call()
            self._record_duplicate_skip()
            return ToolRoutingDecision(
                status=ToolRoutingStatus.SKIP_DUPLICATE,
                stable_key=stable_key,
                should_execute=False,
                should_trigger_grounding=False,
            )
        turn_key = str(context.get("turn_id") or context.get("session_id") or "default")
        stable_key = self._build_tool_call_stable_key(tool_name, arguments_obj, turn_key)
        self._record_total_call()
        seen = self._call_registry.setdefault(turn_key, set())
        if stable_key in seen:
            self._record_duplicate_skip()
            return ToolRoutingDecision(
                status=ToolRoutingStatus.SKIP_DUPLICATE,
                stable_key=stable_key,
                should_execute=False,
                should_trigger_grounding=False,
            )
        seen.add(stable_key)
        should_trigger_grounding = tool_name == "search_internal_knowledge"
        if should_trigger_grounding:
            self._diagnostics = ToolExecutionDiagnostics(
                total_calls=self._diagnostics.total_calls,
                duplicate_skips=self._diagnostics.duplicate_skips,
                cache_hits=self._diagnostics.cache_hits,
                cache_misses=self._diagnostics.cache_misses,
                grounding_triggers=self._diagnostics.grounding_triggers + 1,
                errors=self._diagnostics.errors,
            )
        return ToolRoutingDecision(
            status=ToolRoutingStatus.EXECUTE,
            stable_key=stable_key,
            should_execute=True,
            should_trigger_grounding=should_trigger_grounding,
        )

    def build_internal_retrieval_cache_key(self, arguments_obj: dict[str, Any]) -> str:
        """Build the stable cache key for internal knowledge retrieval arguments."""
        query = str(arguments_obj.get("query") or "").strip().lower()
        if not query:
            return ""

        top_k = arguments_obj.get("top_k")
        metadata_filter = arguments_obj.get("metadata_filter")
        if not isinstance(metadata_filter, dict):
            metadata_filter = {}
        metadata_filter_signature = json.dumps(
            metadata_filter,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"{query}|top_k={top_k}|filter={metadata_filter_signature}"

    def get_cached_result(self, cache_key: str) -> dict[str, Any] | None:
        """Return a cached tool result when present and not expired."""
        if not cache_key:
            return None
        cached = self._result_cache.get(cache_key)
        if not cached:
            self._record_cache_miss()
            return None
        expires_at, payload = cached
        if expires_at <= self._clock():
            self._result_cache.pop(cache_key, None)
            self._record_cache_miss()
            return None
        self._diagnostics = ToolExecutionDiagnostics(
            total_calls=self._diagnostics.total_calls,
            duplicate_skips=self._diagnostics.duplicate_skips,
            cache_hits=self._diagnostics.cache_hits + 1,
            cache_misses=self._diagnostics.cache_misses,
            grounding_triggers=self._diagnostics.grounding_triggers,
            errors=self._diagnostics.errors,
        )
        return dict(payload)

    def cache_result(
        self,
        cache_key: str,
        result: dict[str, Any],
        *,
        ttl_seconds: float,
    ) -> None:
        """Cache a successful tool result for a bounded TTL."""
        if not cache_key or ttl_seconds <= 0:
            return
        if len(self._result_cache) >= self._cache_max_entries:
            self._result_cache.clear()
        self._result_cache[cache_key] = (self._clock() + ttl_seconds, dict(result))

    def configure_cache(self, *, max_entries: int | None = None) -> None:
        """Apply cache bounds from the owning runtime policy."""
        if max_entries is not None:
            self._cache_max_entries = max(1, int(max_entries or 1))
            if len(self._result_cache) > self._cache_max_entries:
                self._result_cache.clear()

    def collect_diagnostics(self) -> ToolExecutionDiagnostics:
        """Return aggregate tool execution diagnostics."""
        return self._diagnostics

    def record_execution_error(self) -> None:
        """Record a tool execution error for diagnostics."""
        self._diagnostics = ToolExecutionDiagnostics(
            total_calls=self._diagnostics.total_calls,
            duplicate_skips=self._diagnostics.duplicate_skips,
            cache_hits=self._diagnostics.cache_hits,
            cache_misses=self._diagnostics.cache_misses,
            grounding_triggers=self._diagnostics.grounding_triggers,
            errors=self._diagnostics.errors + 1,
        )

    def clear_turn_registry(self, turn_key: str | None = None) -> None:
        """Clear routing registry for one turn or all turns."""
        if turn_key is None:
            self._call_registry.clear()
            self._completed_call_ids.clear()
            return
        self._call_registry.pop(str(turn_key), None)

    def mark_tool_call_completed(self, call_id: str) -> None:
        """Remember an executed StepFun call_id for compatibility de-duplication."""
        normalized = str(call_id or "").strip()
        if normalized:
            self._completed_call_ids.add(normalized)

    def _record_total_call(self) -> None:
        self._diagnostics = ToolExecutionDiagnostics(
            total_calls=self._diagnostics.total_calls + 1,
            duplicate_skips=self._diagnostics.duplicate_skips,
            cache_hits=self._diagnostics.cache_hits,
            cache_misses=self._diagnostics.cache_misses,
            grounding_triggers=self._diagnostics.grounding_triggers,
            errors=self._diagnostics.errors,
        )

    def _record_duplicate_skip(self) -> None:
        self._diagnostics = ToolExecutionDiagnostics(
            total_calls=self._diagnostics.total_calls,
            duplicate_skips=self._diagnostics.duplicate_skips + 1,
            cache_hits=self._diagnostics.cache_hits,
            cache_misses=self._diagnostics.cache_misses,
            grounding_triggers=self._diagnostics.grounding_triggers,
            errors=self._diagnostics.errors,
        )

    def _record_cache_miss(self) -> None:
        self._diagnostics = ToolExecutionDiagnostics(
            total_calls=self._diagnostics.total_calls,
            duplicate_skips=self._diagnostics.duplicate_skips,
            cache_hits=self._diagnostics.cache_hits,
            cache_misses=self._diagnostics.cache_misses + 1,
            grounding_triggers=self._diagnostics.grounding_triggers,
            errors=self._diagnostics.errors,
        )

    @staticmethod
    def _build_tool_call_stable_key(
        tool_name: str,
        arguments_obj: dict[str, Any],
        turn_key: str,
    ) -> str:
        normalized_arguments = json.dumps(
            arguments_obj,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(normalized_arguments.encode("utf-8")).hexdigest()
        return f"{turn_key}:{tool_name}:{digest}"

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
