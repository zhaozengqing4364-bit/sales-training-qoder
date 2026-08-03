"""Deterministic task-runtime adapters; never imported by production composition."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from task_runtime.contracts import TaskCompletion


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self._value = value

    def now(self) -> datetime:
        return self._value

    def advance(self, **delta: int) -> None:
        self._value += timedelta(**delta)


class ControlledSleeper:
    def __init__(self, clock: FixedClock) -> None:
        self.clock = clock
        self.calls = 0
        self._ticks: asyncio.Queue[None] = asyncio.Queue()

    async def sleep(self, seconds: float) -> None:
        self.calls += 1
        await self._ticks.get()
        self.clock.advance(seconds=int(seconds))

    async def tick_after_call(self, call_number: int) -> None:
        while self.calls < call_number:
            await asyncio.sleep(0)
        self._ticks.put_nowait(None)


class DeterministicTaskHandler:
    def __init__(self, outcome: TaskCompletion) -> None:
        self.outcome = outcome
        self.calls: list[Any] = []

    async def execute(self, context: Any, payload: Any) -> TaskCompletion:
        self.calls.append(payload)
        await context.checkpoint()
        return self.outcome


__all__ = ["ControlledSleeper", "DeterministicTaskHandler", "FixedClock"]
