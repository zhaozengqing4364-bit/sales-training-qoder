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
