"""E2E-adjacent proofs for the StepFun-only Sales WebSocket flow."""

from __future__ import annotations

import importlib.util
import json

import pytest

from sales_bot.websocket.phase4_local_provider import Phase4LocalStepFunProvider
from sales_bot.websocket.stepfun_realtime_handler import create_stepfun_realtime_handler


@pytest.mark.asyncio
async def test_should_drive_phase4_local_provider_and_record_transcript(tmp_path):
    """Local provider should produce scripted ASR/assistant events and transcript evidence."""
    transcript_path = tmp_path / "provider-transcript.jsonl"
    provider = Phase4LocalStepFunProvider(
        {
            "fixture_version": "sales-provider-script.test",
            "provider": "phase4_local_stepfun",
            "script": {
                "user_transcript": "客户担心预算紧张，我用 ROI 案例回应。",
                "assistant_response": "继续确认试点范围和下一步评审。",
            },
        },
        transcript_path,
    )

    await provider.send(json.dumps({"type": "input_audio_buffer.commit"}))
    transcript_event = json.loads(await provider.recv())
    await provider.send(json.dumps({"type": "response.create"}))
    response_created = json.loads(await provider.recv())
    response_delta = json.loads(await provider.recv())
    response_done = json.loads(await provider.recv())
    await provider.close()

    assert transcript_event == {
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "客户担心预算紧张，我用 ROI 案例回应。",
    }
    assert response_created["type"] == "response.created"
    assert response_delta == {
        "type": "response.text.delta",
        "delta": "继续确认试点范围和下一步评审。",
    }
    assert response_done["type"] == "response.done"

    transcript_lines = transcript_path.read_text(encoding="utf-8").splitlines()
    assert any("client_send" in line for line in transcript_lines)
    assert any("provider_event" in line for line in transcript_lines)
    assert any("provider_close" in line for line in transcript_lines)


def test_should_keep_sales_websocket_stepfun_only_runtime():
    """The Sales WebSocket E2E path must not depend on deleted legacy handlers."""
    assert create_stepfun_realtime_handler is not None

    for module_name in (
        "sales_bot.websocket.base_sales_handler",
        "sales_bot.websocket.enhanced_handler",
        "sales_bot.websocket.simple_handler",
    ):
        assert importlib.util.find_spec(module_name) is None
