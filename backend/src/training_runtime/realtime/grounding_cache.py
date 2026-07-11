"""Bounded per-session retrieval cache with cancellation-safe single-flight."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import replace
from math import isfinite

from training_runtime.realtime.grounding import (
    GroundingCacheDisposition,
    GroundingCacheStats,
    GroundingRequest,
    GroundingRetrievalResult,
    GroundingRetrieverPort,
)


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_json(item) for item in value]
    return value


class GroundingRetrievalCache:
    """Own the only realtime retrieval-result cache for one selected session path."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int,
        timeout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            type(ttl_seconds) not in {int, float}
            or not isfinite(float(ttl_seconds))
            or float(ttl_seconds) < 0
        ):
            raise ValueError("grounding_cache_ttl_seconds_invalid")
        if type(max_entries) is not int or max_entries <= 0:
            raise ValueError("grounding_cache_max_entries_invalid")
        if (
            type(timeout_seconds) not in {int, float}
            or not isfinite(float(timeout_seconds))
            or float(timeout_seconds) <= 0
        ):
            raise ValueError("grounding_cache_timeout_seconds_invalid")
        self._ttl_seconds = float(ttl_seconds)
        self._max_entries = max_entries
        self._timeout_seconds = float(timeout_seconds)
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, GroundingRetrievalResult]] = (
            OrderedDict()
        )
        self._inflight: dict[str, asyncio.Task[GroundingRetrievalResult]] = {}
        self._hit_count = 0
        self._miss_count = 0
        self._shared_count = 0
        self._bypass_count = 0
        self._eviction_count = 0
        self._closed = False
        self._close_task: asyncio.Task[None] | None = None

    async def get_or_retrieve(
        self,
        request: GroundingRequest,
        retriever: GroundingRetrieverPort,
    ) -> GroundingRetrievalResult:
        if self._closed:
            raise RuntimeError("grounding_cache_closed")
        if not isinstance(request, GroundingRequest):
            raise ValueError("grounding_cache_request_invalid")
        cache_key = self._cache_key(request)
        self._drop_expired()
        entry = self._entries.get(cache_key)
        if entry is not None:
            self._hit_count += 1
            self._entries.move_to_end(cache_key)
            return self._with_disposition(
                copy.deepcopy(entry[1]),
                GroundingCacheDisposition.HIT,
            )

        owner = self._inflight.get(cache_key)
        if owner is not None:
            self._shared_count += 1
            result = await asyncio.shield(owner)
            return self._with_disposition(
                copy.deepcopy(result),
                GroundingCacheDisposition.SHARED,
            )

        self._miss_count += 1
        owner = asyncio.create_task(self._retrieve_owner(cache_key, request, retriever))
        self._inflight[cache_key] = owner
        try:
            result = await asyncio.shield(owner)
            return self._with_disposition(
                copy.deepcopy(result),
                GroundingCacheDisposition.MISS,
            )
        finally:
            if owner.done() and self._inflight.get(cache_key) is owner:
                self._inflight.pop(cache_key, None)

    def stats(self) -> GroundingCacheStats:
        self._drop_expired()
        return GroundingCacheStats(
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            shared_count=self._shared_count,
            bypass_count=self._bypass_count,
            eviction_count=self._eviction_count,
            cache_size=len(self._entries),
            inflight_count=len(self._inflight),
        )

    async def close(self) -> None:
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(self._close_owned_tasks())
        cancellation: asyncio.CancelledError | None = None
        while True:
            try:
                await asyncio.shield(self._close_task)
                break
            except asyncio.CancelledError as error:
                if cancellation is None:
                    cancellation = error
                if self._close_task.done():
                    break
        if cancellation is not None:
            raise cancellation

    async def _retrieve_owner(
        self,
        cache_key: str,
        request: GroundingRequest,
        retriever: GroundingRetrieverPort,
    ) -> GroundingRetrievalResult:
        current = asyncio.current_task()
        try:
            result = await asyncio.wait_for(
                retriever(request),
                timeout=self._timeout_seconds,
            )
            if not isinstance(result, GroundingRetrievalResult):
                raise ValueError("grounding_retriever_result_invalid")
            if self._cacheable(result) and not self._closed and self._ttl_seconds > 0:
                self._entries[cache_key] = (
                    self._clock() + self._ttl_seconds,
                    copy.deepcopy(result),
                )
                self._entries.move_to_end(cache_key)
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
                    self._eviction_count += 1
            else:
                self._bypass_count += 1
            return result
        except asyncio.CancelledError:
            raise
        except Exception:
            self._bypass_count += 1
            raise
        finally:
            if current is not None and self._inflight.get(cache_key) is current:
                self._inflight.pop(cache_key, None)

    async def _close_owned_tasks(self) -> None:
        owners = tuple(dict.fromkeys(self._inflight.values()))
        for owner in owners:
            owner.cancel()
        if owners:
            await asyncio.gather(*owners, return_exceptions=True)
        self._inflight.clear()
        self._entries.clear()

    def _drop_expired(self) -> None:
        now = self._clock()
        expired = [
            key
            for key, (expires_at, _result) in self._entries.items()
            if expires_at <= now
        ]
        for key in expired:
            self._entries.pop(key, None)

    @staticmethod
    def _cacheable(result: GroundingRetrievalResult) -> bool:
        return bool(
            result.error_reason is None
            and result.result_count > 0
            and result.status in {"success", "ready", "grounded"}
        )

    @staticmethod
    def _cache_key(request: GroundingRequest) -> str:
        canonical = json.dumps(
            {
                "query": request.query,
                "top_k": request.top_k,
                "metadata_filter": _plain_json(request.metadata_filter),
                "frozen_policy_hash": request.frozen_policy_hash,
                "knowledge_base_ids": sorted(request.knowledge_base_ids),
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _with_disposition(
        result: GroundingRetrievalResult,
        disposition: GroundingCacheDisposition,
    ) -> GroundingRetrievalResult:
        return replace(
            result,
            diagnostics=replace(
                result.diagnostics,
                cache_disposition=disposition,
            ),
        )
