"""Integration tests for release-truth observability surfaces."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_frontend_analytics_routes_accept_beacons_and_surface_them_in_metrics(
    async_client,
) -> None:
    error_response = await async_client.post(
        "/api/v1/analytics/error",
        json={
            "error": "boundary exploded",
            "stack": "Error: boundary exploded",
            "componentStack": "at ThrowOnRender",
            "url": "http://localhost:3445/practice",
            "userAgent": "vitest",
            "timestamp": "2026-04-13T05:00:00Z",
            "source": "react.error-boundary",
        },
    )

    assert error_response.status_code == 202
    assert error_response.json() == {
        "accepted": True,
        "event_type": "error",
    }

    performance_response = await async_client.post(
        "/api/v1/analytics/performance",
        json={
            "name": "LCP",
            "value": 2450,
            "rating": "good",
            "delta": 2450,
            "id": "metric-lcp-1",
            "url": "http://localhost:3445/",
            "timestamp": "2026-04-13T05:00:01Z",
        },
    )

    assert performance_response.status_code == 202
    assert performance_response.json() == {
        "accepted": True,
        "event_type": "performance",
    }

    custom_response = await async_client.post(
        "/api/v1/analytics/custom",
        json={
            "name": "websocket_connect",
            "value": 180,
            "metadata": {"transport": "ws"},
            "url": "http://localhost:3445/practice",
            "timestamp": "2026-04-13T05:00:02Z",
        },
    )

    assert custom_response.status_code == 202
    assert custom_response.json() == {
        "accepted": True,
        "event_type": "custom",
    }

    metrics_response = await async_client.get("/metrics")

    assert metrics_response.status_code == 200
    assert metrics_response.headers["content-type"].startswith(
        "text/plain; version=0.0.4"
    )
    assert (
        'frontend_analytics_events_total{event_type="error",status="accepted"} 1.0'
        in metrics_response.text
    )
    assert (
        'frontend_analytics_events_total{event_type="performance",status="accepted"} 1.0'
        in metrics_response.text
    )
    assert (
        'frontend_analytics_events_total{event_type="custom",status="accepted"} 1.0'
        in metrics_response.text
    )


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_processable_prometheus_payload(async_client) -> None:
    response = await async_client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "http_requests_total" in response.text
    assert "application_info" in response.text
