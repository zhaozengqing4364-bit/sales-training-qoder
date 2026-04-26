from __future__ import annotations

import sys
from copy import deepcopy
from importlib import util
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from common.auth.service import create_access_token
from common.business_rules.defaults import (
    DEFAULT_SALES_COMBINATION_RULESET,
    SALES_COMBINATION_RULES_KEY,
    get_business_rule_definition,
)
from common.db.models import BusinessRuleConfig, User
from common.db.session import get_db

BUSINESS_RULES_API_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "admin" / "api" / "business_rules.py"
)
USER_BUSINESS_RULES_API_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "common" / "api" / "business_rules.py"
)


def _router_from_path(module_name: str, path: Path):
    spec = util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.router


@pytest_asyncio.fixture
async def sales_rules_client(test_db):
    app = FastAPI()
    app.include_router(
        _router_from_path("sales_business_rules_admin_api_under_test", BUSINESS_RULES_API_PATH),
        prefix="/api/v1/admin",
    )
    app.include_router(
        _router_from_path(
            "sales_business_rules_user_api_under_test",
            USER_BUSINESS_RULES_API_PATH,
        ),
        prefix="/api/v1",
    )

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _headers_for(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def _sales_value(*, rule_set_id: str, version: str) -> dict:
    value = deepcopy(DEFAULT_SALES_COMBINATION_RULESET)
    value["rule_set_id"] = rule_set_id
    value["version"] = version
    return value


@pytest.mark.asyncio
async def test_sales_combination_routes_are_mounted_and_defaults_are_seeded(
    sales_rules_client: AsyncClient,
    test_db,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _headers_for(str(test_user.user_id))

    definitions = await sales_rules_client.get(
        "/api/v1/admin/business-rules/definitions",
        headers=headers,
    )
    assert definitions.status_code == 200
    definition_keys = {item["key"] for item in definitions.json()["data"]["items"]}
    assert SALES_COMBINATION_RULES_KEY in definition_keys

    seed = await sales_rules_client.post(
        "/api/v1/admin/business-rules/seed-defaults",
        headers=headers,
    )
    assert seed.status_code == 200
    created_keys = {item["key"] for item in seed.json()["data"]["created"]}
    assert SALES_COMBINATION_RULES_KEY in created_keys

    active = await sales_rules_client.get(
        "/api/v1/business-rules/sales-combinations/active",
        headers=headers,
    )
    assert active.status_code == 200
    payload = active.json()["data"]
    assert payload["rule_set_id"] == DEFAULT_SALES_COMBINATION_RULESET["rule_set_id"]
    assert payload["source"] == "database"
    assert payload["fallback_policy"] == "client_default_v1"
    assert len(payload["combinations"]) == len(
        DEFAULT_SALES_COMBINATION_RULESET["combinations"]
    )


@pytest.mark.asyncio
async def test_sales_combination_active_endpoint_falls_back_when_config_missing(
    sales_rules_client: AsyncClient,
    test_user: User,
):
    response = await sales_rules_client.get(
        "/api/v1/business-rules/sales-combinations/active",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["rule_set_id"] == DEFAULT_SALES_COMBINATION_RULESET["rule_set_id"]
    assert payload["source"] == "default"
    assert payload["fallback_reason"] == "active_missing"


@pytest.mark.asyncio
async def test_sales_combination_validation_rejects_duplicate_pairs_and_bad_policy(
    sales_rules_client: AsyncClient,
    test_db,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _headers_for(str(test_user.user_id))
    invalid = _sales_value(rule_set_id="sales-invalid", version="v-bad")
    invalid["fallback_policy"] = "unsafe_local_default"
    invalid["combinations"] = [
        {
            "id": "dup-1",
            "capability": "需求挖掘",
            "role": "价格敏感型客户",
            "priority": 1,
            "enabled": True,
        },
        {
            "id": "dup-2",
            "capability": "需求挖掘",
            "role": "价格敏感型客户",
            "priority": 2,
            "enabled": True,
        },
    ]

    response = await sales_rules_client.post(
        "/api/v1/admin/business-rules/sales-combinations/validate",
        headers=headers,
        json=invalid,
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["valid"] is False
    assert payload["errors"]
    assert "fallback_policy" in payload["errors"][0]["message"]


@pytest.mark.asyncio
async def test_sales_combination_publish_rollback_and_audit(
    sales_rules_client: AsyncClient,
    test_db,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _headers_for(str(test_user.user_id))

    first_draft = await sales_rules_client.post(
        f"/api/v1/admin/business-rules/{SALES_COMBINATION_RULES_KEY}/drafts",
        headers=headers,
        json={"value": _sales_value(rule_set_id="sales-v1", version="v1")},
    )
    assert first_draft.status_code == 200
    first_publish = await sales_rules_client.post(
        "/api/v1/admin/business-rules/sales-combinations/sales-v1/publish",
        headers=headers,
        json={"reason": "publish baseline sales combinations"},
    )
    assert first_publish.status_code == 200
    assert first_publish.json()["data"]["ruleset"]["version"] == "v1"

    second_draft = await sales_rules_client.post(
        f"/api/v1/admin/business-rules/{SALES_COMBINATION_RULES_KEY}/drafts",
        headers=headers,
        json={"value": _sales_value(rule_set_id="sales-v2", version="v2")},
    )
    assert second_draft.status_code == 200
    second_publish = await sales_rules_client.post(
        "/api/v1/admin/business-rules/sales-combinations/sales-v2/publish",
        headers=headers,
        json={"reason": "publish next sales combinations"},
    )
    assert second_publish.status_code == 200

    rollback = await sales_rules_client.post(
        "/api/v1/admin/business-rules/sales-combinations/sales-v1/rollback",
        headers=headers,
        json={"reason": "rollback to stable sales combinations"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["ruleset"]["version"] == "v1"

    list_response = await sales_rules_client.get(
        "/api/v1/admin/business-rules/sales-combinations",
        headers=headers,
    )
    assert list_response.status_code == 200
    payload = list_response.json()["data"]
    assert payload["active"]["rule_set_id"] == "sales-v1"
    actions = [item["action"] for item in payload["audit_log"]]
    assert "publish" in actions
    assert "rollback" in actions


@pytest.mark.asyncio
async def test_sales_combination_active_endpoint_falls_back_from_invalid_database_row(
    sales_rules_client: AsyncClient,
    test_db,
    test_user: User,
):
    definition = get_business_rule_definition(SALES_COMBINATION_RULES_KEY)
    broken = BusinessRuleConfig(
        domain=definition.domain,
        key=definition.key,
        schema_version=definition.schema_version,
        status="published",
        version=1,
        value_json={"rule_set_id": "", "version": "", "combinations": []},
        default_value_json=deepcopy(definition.default_value),
        type=definition.type,
        range_or_allowlist_json=deepcopy(definition.range_or_allowlist),
        read_path=definition.read_path,
        admin_entry=definition.admin_entry,
        permission=definition.permission,
        audit_policy=definition.audit_policy,
        fallback_policy=definition.fallback_policy,
        rollback_policy=definition.rollback_policy,
        enabled=True,
        validation_errors_json=[],
        created_by=str(test_user.user_id),
        updated_by=str(test_user.user_id),
    )
    test_db.add(broken)
    await test_db.commit()

    response = await sales_rules_client.get(
        "/api/v1/business-rules/sales-combinations/active",
        headers=_headers_for(str(test_user.user_id)),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["rule_set_id"] == DEFAULT_SALES_COMBINATION_RULESET["rule_set_id"]
    assert payload["source"] == "default"
    assert payload["fallback_reason"].startswith("active_invalid:")
