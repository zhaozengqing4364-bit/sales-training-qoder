"""Backend-side local StepFun provider seam for Phase 4 E2E."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from common.e2e.fixtures import load_versioned_fixture


def should_use_phase4_local_provider() -> bool:
    return os.getenv("PHASE4_E2E_PROVIDER", "").strip().lower() == "local"


class Phase4LocalStepFunProvider:
    """Small WebSocket-like provider backed by a milestone fixture script."""

    def __init__(self, fixture: Mapping[str, Any], transcript_path: Path | None) -> None:
        self.fixture = dict(fixture)
        self.transcript_path = transcript_path
        self.sent_payloads: list[dict[str, Any]] = []
        self._events: asyncio.Queue[str] = asyncio.Queue()
        self._closed = False
        self._turn_index = 0

    @classmethod
    def from_env(cls) -> Phase4LocalStepFunProvider:
        fixture_name = os.getenv(
            "PHASE4_E2E_PROVIDER_SCRIPT", "sales-provider-script.v1.json"
        )
        transcript = os.getenv("PHASE4_E2E_PROVIDER_TRANSCRIPT", "").strip()
        transcript_path = Path(transcript).expanduser().resolve() if transcript else None
        return cls(load_versioned_fixture(fixture_name), transcript_path)

    async def send(self, raw_payload: str) -> None:
        payload = json.loads(raw_payload)
        if not isinstance(payload, dict):
            return
        self.sent_payloads.append(payload)
        await self._record("client_send", payload)
        if payload.get("type") == "input_audio_buffer.commit":
            await self._enqueue_scripted_turn()
        elif payload.get("type") == "response.create":
            await self._enqueue_scripted_response()

    async def recv(self) -> str:
        return await self._events.get()

    async def close(self) -> None:
        self._closed = True
        await self._record("provider_close", {"closed": True})

    async def _enqueue_scripted_turn(self) -> None:
        script = self._current_script_turn()
        transcript = ""
        if isinstance(script, dict):
            transcript = str(script.get("user_transcript") or "").strip()
        if transcript:
            await self._put_event(
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "transcript": transcript,
                }
            )

    async def _enqueue_scripted_response(self) -> None:
        script = self._current_script_turn()
        response_text = ""
        if isinstance(script, dict):
            response_text = str(script.get("assistant_response") or "").strip()
        if response_text:
            await self._put_event({"type": "response.created", "response": {"id": "phase4-local-response"}})
            await self._put_event({"type": "response.text.delta", "delta": response_text})
            await self._put_event({"type": "response.done", "response": {"id": "phase4-local-response"}})
        self._turn_index += 1

    def _current_script_turn(self) -> Mapping[str, Any] | None:
        script = self.fixture.get("script") if isinstance(self.fixture, dict) else None
        if isinstance(script, dict):
            return script
        if isinstance(script, list) and script:
            turn = script[min(self._turn_index, len(script) - 1)]
            return turn if isinstance(turn, Mapping) else None
        return None

    async def _put_event(self, event: dict[str, Any]) -> None:
        await self._record("provider_event", event)
        await self._events.put(json.dumps(event, ensure_ascii=False))

    async def _record(self, direction: str, payload: dict[str, Any]) -> None:
        if self.transcript_path is None:
            return
        self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "fixture_version": self.fixture.get("fixture_version"),
            "provider": self.fixture.get("provider"),
            "direction": direction,
            "payload": payload,
        }
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
