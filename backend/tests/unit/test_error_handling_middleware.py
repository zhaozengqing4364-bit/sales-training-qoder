import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from common.error_handling.middleware import ErrorHandlerMiddleware
from common.monitoring.logger import get_trace_id, set_trace_id


@pytest.mark.asyncio
async def test_error_handler_middleware_extracts_traceparent_and_echoes_headers():
    app = FastAPI()
    app.add_middleware(ErrorHandlerMiddleware)

    @app.get("/trace")
    async def trace() -> dict[str, str]:
        return {"trace_id": get_trace_id()}

    set_trace_id("")
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    tracestate = "vendor=value"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/trace",
            headers={
                "traceparent": traceparent,
                "tracestate": tracestate,
            },
        )

    assert response.status_code == 200
    assert response.json()["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert response.headers["x-trace-id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert response.headers["traceparent"] == traceparent
    assert response.headers["tracestate"] == tracestate
