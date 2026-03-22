from fastapi import FastAPI
from fastapi.testclient import TestClient

from common.error_handling.middleware import ErrorHandlerMiddleware
from common.monitoring.logger import get_trace_id


def test_error_handler_uses_traceparent_trace_id_for_request_context():
    app = FastAPI()
    app.add_middleware(ErrorHandlerMiddleware)

    @app.get("/trace-id")
    async def trace_id_endpoint():
        return {"trace_id": get_trace_id()}

    client = TestClient(app)

    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    response = client.get("/trace-id", headers={"traceparent": traceparent})

    assert response.status_code == 200
    assert response.json()["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert response.headers["X-Trace-ID"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert response.headers["traceparent"].startswith(
        "00-4bf92f3577b34da6a3ce929d0e0e4736-"
    )


def test_error_handler_preserves_tracestate_header():
    app = FastAPI()
    app.add_middleware(ErrorHandlerMiddleware)

    @app.get("/ok")
    async def ok_endpoint():
        return {"ok": True}

    client = TestClient(app)

    response = client.get(
        "/ok",
        headers={
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            "tracestate": "vendor=value",
        },
    )

    assert response.status_code == 200
    assert response.headers["tracestate"] == "vendor=value"
