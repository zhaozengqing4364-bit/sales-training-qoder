from __future__ import annotations

from copy import deepcopy

import pytest

from common.business_rules.defaults import (
    DEFAULT_SALES_COMBINATION_RULESET,
    SALES_COMBINATION_RULES_KEY,
    get_business_rule_definition,
)
from common.business_rules.validators import (
    BusinessRuleValidationError,
    validate_business_rule_value,
)


def test_sales_combination_definition_is_governed_business_rule() -> None:
    definition = get_business_rule_definition(SALES_COMBINATION_RULES_KEY)

    assert definition.admin_entry == "/admin/business-rules/sales-combinations"
    assert definition.default_value["rule_set_id"] == "sales-training-combinations-default-v1"
    assert definition.permission == "admin_publish_only"


def test_sales_combination_ruleset_validates_and_sorts_by_priority() -> None:
    ruleset = deepcopy(DEFAULT_SALES_COMBINATION_RULESET)
    ruleset["combinations"] = list(reversed(ruleset["combinations"]))

    normalized = validate_business_rule_value(SALES_COMBINATION_RULES_KEY, ruleset)

    assert normalized["fallback_policy"] == "client_default_v1"
    assert [item["priority"] for item in normalized["combinations"]] == list(range(1, 11))


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"rule_set_id": ""}, "rule_set_id is required"),
        ({"version": ""}, "version is required"),
        ({"fallback_policy": "unsafe_default"}, "fallback_policy must be"),
        ({"combinations": []}, "combinations must be non-empty"),
    ],
)
def test_sales_combination_ruleset_rejects_invalid_contract(
    patch: dict,
    message: str,
) -> None:
    ruleset = deepcopy(DEFAULT_SALES_COMBINATION_RULESET)
    ruleset.update(patch)

    with pytest.raises(BusinessRuleValidationError, match=message):
        validate_business_rule_value(SALES_COMBINATION_RULES_KEY, ruleset)


def test_sales_combination_ruleset_rejects_duplicate_pairs_and_ids() -> None:
    ruleset = deepcopy(DEFAULT_SALES_COMBINATION_RULESET)
    ruleset["combinations"][1]["id"] = ruleset["combinations"][0]["id"]

    with pytest.raises(BusinessRuleValidationError, match="duplicate combination id"):
        validate_business_rule_value(SALES_COMBINATION_RULES_KEY, ruleset)

    ruleset = deepcopy(DEFAULT_SALES_COMBINATION_RULESET)
    ruleset["combinations"][1]["capability"] = ruleset["combinations"][0]["capability"]
    ruleset["combinations"][1]["role"] = ruleset["combinations"][0]["role"]

    with pytest.raises(BusinessRuleValidationError, match="duplicate capability/role pair"):
        validate_business_rule_value(SALES_COMBINATION_RULES_KEY, ruleset)


def test_sales_combination_ruleset_all_disabled_requires_hide_all_policy() -> None:
    ruleset = deepcopy(DEFAULT_SALES_COMBINATION_RULESET)
    for combination in ruleset["combinations"]:
        combination["enabled"] = False

    with pytest.raises(BusinessRuleValidationError, match="fallback_policy must be hide_all"):
        validate_business_rule_value(SALES_COMBINATION_RULES_KEY, ruleset)

    ruleset["fallback_policy"] = "hide_all"
    normalized = validate_business_rule_value(SALES_COMBINATION_RULES_KEY, ruleset)
    assert all(item["enabled"] is False for item in normalized["combinations"])
