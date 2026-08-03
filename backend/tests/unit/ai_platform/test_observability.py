"""Currency-safe governed AI metrics aggregation contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy.dialects import postgresql

from ai_platform import (
    AIInvocationMetricsFilter,
    SQLAlchemyAIInvocationMetricsReader,
)


class _Result:
    def all(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                organization_id="org-1",
                business_purpose="test.generate",
                provider="provider-a",
                model="model-a",
                result_classification="succeeded",
                currency="USD",
                invocation_count=2,
                failed_count=0,
                degraded_count=0,
                average_latency_ms=12.5,
                input_tokens=7,
                output_tokens=5,
                cost_minor_units=9,
            )
        ]


class _Session:
    def __init__(self, captured: list[Any]) -> None:
        self._captured = captured

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def execute(self, statement: Any) -> _Result:
        self._captured.append(statement)
        return _Result()


class _SessionFactory:
    def __init__(self) -> None:
        self.captured: list[Any] = []

    def __call__(self) -> _Session:
        return _Session(self.captured)


async def test_metrics_keep_currency_as_a_filter_and_aggregation_dimension() -> None:
    factory = _SessionFactory()
    reader = SQLAlchemyAIInvocationMetricsReader(factory)  # type: ignore[arg-type]

    rows = await reader.query(
        AIInvocationMetricsFilter(organization_id="org-1", currency="USD")
    )

    assert len(rows) == 1
    assert rows[0].currency == "USD"
    assert rows[0].cost_minor_units == 9
    statement = factory.captured[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "ai_invocations.currency = 'USD'" in sql
    group_by = sql.split(" GROUP BY ", 1)[1].split(" ORDER BY ", 1)[0]
    order_by = sql.split(" ORDER BY ", 1)[1]
    assert "ai_invocations.currency" in group_by
    assert "ai_invocations.currency" in order_by
