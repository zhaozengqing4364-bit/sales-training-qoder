"""Unit tests for sales websocket router compatibility and session_id validation."""

from uuid import uuid4

from sales_bot.websocket.router import _parse_session_id, router


def test_parse_session_id_accepts_uuid() -> None:
    session_id = str(uuid4())
    assert _parse_session_id(session_id) == session_id


def test_parse_session_id_rejects_invalid_value() -> None:
    assert _parse_session_id(None) is None
    assert _parse_session_id("") is None
    assert _parse_session_id("not-a-uuid") is None


def test_sales_websocket_routes_support_path_and_query_modes() -> None:
    paths = {getattr(route, "path", "") for route in router.routes}
    assert "/ws/sales" in paths
    assert "/ws/sales/{session_id}" in paths
