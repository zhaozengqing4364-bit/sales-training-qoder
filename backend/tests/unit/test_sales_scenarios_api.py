"""Regression tests for sales scenario API error envelopes."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.exc import SQLAlchemyError

from sales_bot.api.scenarios import list_sales_personas, list_scenarios


class FailingDatabase:
    """Minimal async DB double that raises from execute()."""

    async def execute(self, *_args, **_kwargs):
        raise SQLAlchemyError("database unavailable")


def _json_response_body(response) -> dict:
    return json.loads(response.body.decode())


@pytest.mark.asyncio
async def test_should_return_server_error_envelope_when_scenario_list_fails():
    response = await list_scenarios(
        scenario_type="sales",
        current_user=object(),
        db=FailingDatabase(),
    )

    assert response.status_code == 500
    body = _json_response_body(response)
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] == "[SCENARIOS_LIST_FAILED]"
    assert body["message"] == "Failed to list scenarios"
    assert body.get("trace_id")


@pytest.mark.asyncio
async def test_should_return_server_error_envelope_when_sales_personas_list_fails():
    response = await list_sales_personas(
        agent_id="agent-1",
        current_user=object(),
        db=FailingDatabase(),
    )

    assert response.status_code == 500
    body = _json_response_body(response)
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] == "[SALES_PERSONAS_LIST_FAILED]"
    assert body["message"] == "Failed to list sales personas"
    assert body.get("trace_id")
