"""Route integrity checks for mounted FastAPI routes."""

from collections import Counter

from main import app

IGNORED_METHODS = {"HEAD", "OPTIONS"}


def _collect_method_path_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []

    for route in app.router.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue

        for method in methods:
            if method in IGNORED_METHODS:
                continue
            pairs.append((method, path))

    return pairs


def test_no_duplicate_http_method_path_routes() -> None:
    """Ensure each HTTP method+path pair is unique."""
    pairs = _collect_method_path_pairs()
    counter = Counter(pairs)

    duplicates = [item for item, count in counter.items() if count > 1]
    assert duplicates == []


def test_key_business_routers_are_mounted() -> None:
    """Protect critical mounted routers from accidental removal."""
    actual = set(_collect_method_path_pairs())

    expected_routes = {
        ("GET", "/api/v1/scenarios"),
        ("GET", "/api/v1/scenarios/sales/personas"),
        ("GET", "/api/v1/scenarios/{scenario_id}"),
        ("POST", "/api/v1/admin/knowledge/{kb_id}/search"),
        ("POST", "/api/v1/internal/knowledge/{kb_id}/search"),
        ("GET", "/api/v1/admin/presentations"),
        ("GET", "/api/v1/admin/business-rules/definitions"),
        ("GET", "/api/v1/business-rules/sales-combinations/active"),
        ("GET", "/api/v1/evaluation/admin/scoring-rulesets"),
    }

    missing = expected_routes - actual
    assert missing == set()


def test_lane_11_canonical_route_inventory_is_present() -> None:
    actual = set(_collect_method_path_pairs())
    expected_routes = {
        ("GET", "/api/v1/support/runtime/overview"),
        ("GET", "/api/v1/support/runtime/faults"),
        ("GET", "/api/v1/evaluation/admin/scoring-rulesets"),
        ("GET", "/api/v1/admin/business-rules/definitions"),
        ("GET", "/api/v1/business-rules/sales-combinations/active"),
        ("GET", "/api/v1/admin/presentations"),
        ("GET", "/api/v1/admin/knowledge"),
    }

    missing = expected_routes - actual
    assert missing == set(), missing


def test_websocket_routes_support_legacy_and_path_modes() -> None:
    websocket_paths = {
        getattr(route, "path", "")
        for route in app.router.routes
        if route.__class__.__name__ == "APIWebSocketRoute"
    }

    assert "/ws/sales" in websocket_paths
    assert "/ws/sales/{session_id}" in websocket_paths
    assert "/ws/presentation" in websocket_paths
    assert "/ws/presentation/{session_id}" in websocket_paths


def test_prompt_templates_static_route_precedes_dynamic_route() -> None:
    prompt_routes = [
        getattr(route, "path", "")
        for route in app.router.routes
        if isinstance(getattr(route, "path", None), str)
        and str(getattr(route, "path", "")).startswith("/api/v1/prompt-templates")
    ]

    by_scenario_index = prompt_routes.index(
        "/api/v1/prompt-templates/by-scenario/{scenario_type}"
    )
    template_id_index = prompt_routes.index("/api/v1/prompt-templates/{template_id}")
    assert by_scenario_index < template_id_index
