"""Regression tests for backend app factory wiring."""

from __future__ import annotations

import sys
import types
from collections import Counter
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.routing import APIWebSocketRoute
from httpx import ASGITransport, AsyncClient

if "chromadb" not in sys.modules:
    chromadb_stub = types.ModuleType("chromadb")
    chromadb_api_stub = types.ModuleType("chromadb.api")
    chromadb_models_stub = types.ModuleType("chromadb.api.models")
    chromadb_collection_stub = types.ModuleType("chromadb.api.models.Collection")
    chromadb_config_stub = types.ModuleType("chromadb.config")

    class ClientAPI:
        pass

    class Collection:
        pass

    class Settings:
        def __init__(self, **_kwargs: object) -> None:
            pass

    setattr(chromadb_stub, "PersistentClient", lambda *_args, **_kwargs: None)
    setattr(chromadb_api_stub, "ClientAPI", ClientAPI)
    setattr(chromadb_collection_stub, "Collection", Collection)
    setattr(chromadb_config_stub, "Settings", Settings)
    sys.modules["chromadb"] = chromadb_stub
    sys.modules["chromadb.api"] = chromadb_api_stub
    sys.modules["chromadb.api.models"] = chromadb_models_stub
    sys.modules["chromadb.api.models.Collection"] = chromadb_collection_stub
    sys.modules["chromadb.config"] = chromadb_config_stub

if "websockets" not in sys.modules:
    websockets_stub = types.ModuleType("websockets")
    exceptions_stub = types.ModuleType("websockets.exceptions")

    class ConnectionClosed(Exception):
        pass

    class InvalidStatus(Exception):
        pass

    setattr(exceptions_stub, "ConnectionClosed", ConnectionClosed)
    setattr(exceptions_stub, "InvalidStatus", InvalidStatus)
    sys.modules["websockets"] = websockets_stub
    sys.modules["websockets.exceptions"] = exceptions_stub

if "prometheus_client" not in sys.modules:
    prometheus_stub = types.ModuleType("prometheus_client")
    exposition_stub = types.ModuleType("prometheus_client.exposition")

    class _Metric:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def labels(self, *_args: object, **_kwargs: object) -> _Metric:
            return self

        def inc(self, *_args: object, **_kwargs: object) -> None:
            pass

        def observe(self, *_args: object, **_kwargs: object) -> None:
            pass

        def set(self, *_args: object, **_kwargs: object) -> None:
            pass

        def info(self, *_args: object, **_kwargs: object) -> None:
            pass

    setattr(prometheus_stub, "Counter", _Metric)
    setattr(prometheus_stub, "Gauge", _Metric)
    setattr(prometheus_stub, "Histogram", _Metric)
    setattr(prometheus_stub, "Info", _Metric)
    setattr(exposition_stub, "generate_latest", lambda: b"")
    sys.modules["prometheus_client"] = prometheus_stub
    sys.modules["prometheus_client.exposition"] = exposition_stub

if "oss2" not in sys.modules:
    oss2_stub = types.ModuleType("oss2")

    class Auth:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

    class Bucket:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def sign_url(self, *_args: object, **_kwargs: object) -> str:
            return "https://oss.test/signed"

    setattr(oss2_stub, "Auth", Auth)
    setattr(oss2_stub, "Bucket", Bucket)
    sys.modules["oss2"] = oss2_stub

import main
from app_factory import APP_TITLE, APP_VERSION, create_app
from app_lifespan import lifespan

IGNORED_METHODS = {"HEAD", "OPTIONS"}


def _effective_routes(app) -> Iterator[object]:
    """Yield direct routes and FastAPI included-router effective contexts."""
    for route in app.router.routes:
        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        if callable(effective_route_contexts):
            yield from effective_route_contexts()
        else:
            yield route


def _method_path_pairs(app) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for route in _effective_routes(app):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        for method in methods:
            if method not in IGNORED_METHODS:
                pairs.append((method, path))
    return pairs


def test_main_preserves_app_factory_public_contract() -> None:
    assert main.app.title == APP_TITLE
    assert main.app.version == APP_VERSION
    assert main.create_app is create_app
    assert main.lifespan is lifespan
    assert main.app.state.lifespan_authority is lifespan


def test_create_app_registers_startup_http_and_websocket_surfaces() -> None:
    app = create_app()
    http_routes = set(_method_path_pairs(app))
    websocket_routes = {
        str(getattr(getattr(route, "original_route", route), "path", ""))
        for route in _effective_routes(app)
        if isinstance(getattr(route, "original_route", route), APIWebSocketRoute)
    }

    assert ("GET", "/health") in http_routes
    assert ("GET", "/metrics") in http_routes
    assert ("POST", "/api/v1/auth/dev-login") in http_routes
    assert "/ws/presentation" in websocket_routes
    assert "/ws/presentation/{session_id}" in websocket_routes
    assert "/ws/sales" in websocket_routes
    assert "/ws/sales/{session_id}" in websocket_routes


def test_create_app_does_not_duplicate_method_path_routes() -> None:
    pairs = _method_path_pairs(create_app())
    duplicates = [item for item, count in Counter(pairs).items() if count > 1]

    assert duplicates == []


def test_create_app_cors_defaults_fail_closed_in_production(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-with-32-characters")
    monkeypatch.setenv("JWT_SECRET", "production-jwt-secret-with-32-characters")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOW_ORIGIN_REGEX", raising=False)

    app = create_app()
    cors_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )
    assert cors_middleware.kwargs["allow_origins"] == []
    assert cors_middleware.kwargs["allow_origin_regex"] is None


def test_create_app_rejects_unsafe_production_config(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEV_LOGIN_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "change-me")
    monkeypatch.setenv("JWT_SECRET", "change-me")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", "*")

    try:
        create_app()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("unsafe production config should be rejected")

    assert "PROD_DEV_LOGIN_ENABLED" in message
    assert "PROD_SECRET_KEY_UNSAFE" in message
    assert "PROD_JWT_SECRET_UNSAFE" in message
    assert "PROD_DEBUG_TRUE" in message
    assert "PROD_CORS_WIDE_OPEN" in message


@pytest.mark.asyncio
async def test_lifespan_rejects_unsafe_production_jwt_secret(monkeypatch) -> None:
    import app_lifespan as app_lifespan_module
    import common.auth.service as auth_service
    from common.config import settings

    init_db_called = False

    async def fail_if_called() -> None:
        nonlocal init_db_called
        init_db_called = True

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        settings,
        "SECRET_KEY",
        "production-secret-key-with-32-characters",
    )
    monkeypatch.setattr(auth_service, "JWT_SECRET", "change-me")
    monkeypatch.setattr(app_lifespan_module, "initialize_otel", lambda _app: None)
    monkeypatch.setattr(app_lifespan_module, "init_db", fail_if_called)

    with pytest.raises(RuntimeError, match="JWT_SECRET must be explicit"):
        async with app_lifespan_module.lifespan(FastAPI()):
            pass

    assert init_db_called is False


def test_create_app_cors_appends_dev_origins_only_in_dev(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOW_ORIGIN_REGEX", raising=False)

    app = create_app()
    cors_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )
    assert "http://localhost:3445" in cors_middleware.kwargs["allow_origins"]
    assert "http://127.0.0.1:5173" in cors_middleware.kwargs["allow_origins"]
    assert cors_middleware.kwargs["allow_origin_regex"]


@pytest.mark.asyncio
async def test_create_app_cors_wraps_error_handler_responses(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    app = create_app()

    @app.get("/__test__/cors-error")
    async def cors_error() -> None:
        raise ValueError("boom")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/__test__/cors-error",
            headers={"Origin": "http://localhost:3445"},
        )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3445"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_create_app_cors_allows_public_ipv4_dev_frontend_origin(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOW_ORIGIN_REGEX", raising=False)
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.options(
            "/api/v1/auth/providers",
            headers={
                "Origin": "http://203.0.113.42:3445",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://203.0.113.42:3445"
    )
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.asyncio
async def test_create_app_cors_wraps_csrf_rejection_responses(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/newcomer-training/ai-coach/chat/sessions",
            headers={
                "Origin": "http://localhost:3445",
                "Content-Type": "application/json",
                "Cookie": "app_session=fake-session",
            },
            json={"module_key": "business_skills"},
        )

    assert response.status_code == 403
    assert response.headers["access-control-allow-origin"] == "http://localhost:3445"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.json()["error"] == "[CSRF_VALIDATION_FAILED]"
