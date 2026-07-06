from __future__ import annotations

from types import SimpleNamespace

import pytest

import common.ai.llm_service as llm_service_module
from common.monitoring.metrics import (
    get_metrics,
    track_tts_request,
    track_websocket_connection_event,
    track_websocket_error,
    track_websocket_send_failure,
)


def test_websocket_prometheus_metrics_export_connection_failure_and_error() -> None:
    scenario = "unit_observability_ws"

    track_websocket_connection_event(scenario, "connect")
    track_websocket_connection_event(scenario, "disconnect")
    track_websocket_send_failure(scenario, "heartbeat", "RuntimeError")
    track_websocket_error(scenario, "RuntimeError")

    exported = get_metrics().decode("utf-8")

    assert (
        f'websocket_connection_events_total{{event="connect",scenario_type="{scenario}"'
    ) in exported
    assert (
        'websocket_connection_events_total{event="disconnect",'
        f'scenario_type="{scenario}"'
    ) in exported
    assert (
        'websocket_send_failures_total{error_type="RuntimeError",'
        'message_type="heartbeat",'
        f'scenario_type="{scenario}"'
    ) in exported
    assert (
        f'websocket_errors_total{{error_type="RuntimeError",scenario_type="{scenario}"'
    ) in exported


def test_tts_prometheus_metric_labels_include_provider_consistently() -> None:
    provider = "unit_observability_tts"

    track_tts_request("success", provider, 0.05)

    exported = get_metrics().decode("utf-8")
    assert f'tts_requests_total{{provider="{provider}",status="success"' in exported
    assert f'tts_request_duration_seconds_count{{provider="{provider}"' in exported


@pytest.mark.asyncio
async def test_llm_generate_records_prometheus_request_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, float, dict[str, float | int]]] = []

    def record_metric(
        service: str,
        status: str,
        duration: float,
        tokens: dict[str, float | int],
    ) -> None:
        calls.append((service, status, duration, tokens))

    class _FakeLlm:
        async def agenerate(self, _messages: object, callbacks: list[object]) -> object:
            token_response = SimpleNamespace(
                llm_output={
                    "token_usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 3,
                        "total_tokens": 5,
                    }
                }
            )
            for callback in callbacks:
                await callback.on_llm_end(token_response)
            return SimpleNamespace(
                generations=[
                    [
                        SimpleNamespace(
                            text="metric ok",
                            response_metadata={"finish_reason": "stop"},
                        )
                    ]
                ]
            )

    service = object.__new__(llm_service_module.LLMService)
    service._effective_config = {
        "provider": "unit_llm",
        "model_name": "unit-model",
        "base_url": "",
        "extra_config": {},
    }
    service._runtime_policy = {"base_url_required": False, "base_url_status": "ok"}
    service._llm = _FakeLlm()
    service.cost_per_1k_tokens = 0.00005
    service.session_costs = {}
    service.session_runtime_events = {}
    monkeypatch.setattr(llm_service_module, "track_llm_request", record_metric)

    result = await service.generate(
        "hello",
        "session-observability",
        allow_fallback_response=False,
    )

    assert result.is_success
    assert len(calls) == 1
    service_name, status, duration, tokens = calls[0]
    assert service_name == "unit_llm"
    assert status == "success"
    assert duration >= 0
    assert tokens == {"prompt": 2, "completion": 3, "total": 5}
