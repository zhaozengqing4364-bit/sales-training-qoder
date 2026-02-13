"""Unit tests for analytics API parameter normalization."""

from common.api.analytics import _normalize_scenario_type, _normalize_time_period


def test_normalize_scenario_type_alias_sales_bot() -> None:
    """`sales_bot` alias should normalize to canonical `sales`."""
    assert _normalize_scenario_type("sales_bot") == "sales"


def test_normalize_scenario_type_passthrough_and_none() -> None:
    """Other scenario values should pass through; None stays None."""
    assert _normalize_scenario_type("presentation") == "presentation"
    assert _normalize_scenario_type(None) is None


def test_normalize_time_period_aliases() -> None:
    """Time-period aliases should normalize to canonical values."""
    assert _normalize_time_period("day") == "daily"
    assert _normalize_time_period("daily") == "daily"
    assert _normalize_time_period("week") == "weekly"
    assert _normalize_time_period("weekly") == "weekly"
    assert _normalize_time_period("month") == "monthly"
    assert _normalize_time_period("monthly") == "monthly"
    assert _normalize_time_period("all") == "all_time"
    assert _normalize_time_period("all_time") == "all_time"


def test_normalize_time_period_unknown_defaults_all_time() -> None:
    """Unknown values should safely fallback to `all_time`."""
    assert _normalize_time_period("quarterly") == "all_time"
