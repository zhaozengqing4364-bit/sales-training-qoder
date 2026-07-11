"""Named rollback path for the pre-Gate-3 realtime grounding authorities."""

from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable
from typing import Any

from sales_bot.websocket.grounding_decision_pipeline import (
    GroundingDecisionPipeline,
    GroundingWarmupCallable,
    KnowledgeRetriever,
)


class LegacyToolResultCache:
    """Preserve the former tool-owned result cache only on the rollback path."""

    def __init__(
        self,
        *,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._max_entries = max(1, int(max_entries or 1))
        self._entries: dict[str, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def build_key(arguments_obj: dict[str, Any]) -> str:
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

    def get(self, cache_key: str) -> dict[str, Any] | None:
        if not cache_key:
            return None
        cached = self._entries.get(cache_key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= self._clock():
            self._entries.pop(cache_key, None)
            return None
        return copy.deepcopy(payload)

    def put(
        self,
        cache_key: str,
        result: dict[str, Any],
        *,
        ttl_seconds: float,
    ) -> None:
        if not cache_key or ttl_seconds <= 0:
            return
        if len(self._entries) >= self._max_entries:
            self._entries.clear()
        self._entries[cache_key] = (
            self._clock() + ttl_seconds,
            copy.deepcopy(result),
        )

    def clear(self) -> None:
        self._entries.clear()


class LegacyRealtimeGroundingAdapter:
    """Own both superseded grounding caches behind the explicit rollback flag."""

    def __init__(
        self,
        *,
        retriever: KnowledgeRetriever,
        warmup_callable: GroundingWarmupCallable,
        cache_ttl_seconds: float,
        cache_max_entries: int,
    ) -> None:
        self.pipeline = GroundingDecisionPipeline(
            retriever=retriever,
            warmup_callable=warmup_callable,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        self.tool_cache = LegacyToolResultCache(max_entries=cache_max_entries)

    async def close(self) -> None:
        self.tool_cache.clear()
