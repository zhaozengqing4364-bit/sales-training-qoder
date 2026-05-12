"""Regression tests for backend app factory wiring."""

from __future__ import annotations

from collections import Counter

from fastapi.routing import APIWebSocketRoute

import main
from app_factory import APP_TITLE, APP_VERSION, create_app
from app_lifespan import lifespan

IGNORED_METHODS = {"HEAD", "OPTIONS"}


def _method_path_pairs(app) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for route in app.router.routes:
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
        route.path for route in app.router.routes if isinstance(route, APIWebSocketRoute)
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
    assert "PROD_DEBUG_TRUE" in message
    assert "PROD_CORS_WIDE_OPEN" in message


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
