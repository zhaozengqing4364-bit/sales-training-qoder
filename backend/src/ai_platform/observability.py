"""Read-only aggregate seam for governed AI usage and reliability metrics."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_platform.models import AIInvocationRecord


class AIInvocationMetricsFilter(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    organization_id: str | None = None
    business_purpose: str | None = None
    provider: str | None = None
    model: str | None = None
    result_classification: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class AIInvocationMetricRow(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    organization_id: str
    business_purpose: str
    provider: str | None
    model: str | None
    result_classification: str
    currency: str = Field(min_length=3, max_length=3)
    invocation_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    degraded_count: int = Field(ge=0)
    average_latency_ms: float | None = Field(default=None, ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_minor_units: int = Field(ge=0)


class SQLAlchemyAIInvocationMetricsReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def query(
        self,
        filters: AIInvocationMetricsFilter | None = None,
    ) -> tuple[AIInvocationMetricRow, ...]:
        filters = filters or AIInvocationMetricsFilter()
        classification = func.coalesce(
            AIInvocationRecord.error_classification,
            AIInvocationRecord.state,
        ).label("result_classification")
        statement = select(
            AIInvocationRecord.organization_id,
            AIInvocationRecord.business_purpose,
            AIInvocationRecord.provider,
            AIInvocationRecord.model,
            classification,
            AIInvocationRecord.currency,
            func.count(AIInvocationRecord.invocation_id).label("invocation_count"),
            func.sum(case((AIInvocationRecord.state == "failed", 1), else_=0)).label(
                "failed_count"
            ),
            func.sum(
                case(
                    (
                        func.jsonb_array_length(AIInvocationRecord.degradations_json)
                        > 0,
                        1,
                    ),
                    else_=0,
                )
            ).label("degraded_count"),
            func.avg(AIInvocationRecord.latency_ms).label("average_latency_ms"),
            func.sum(AIInvocationRecord.input_tokens).label("input_tokens"),
            func.sum(AIInvocationRecord.output_tokens).label("output_tokens"),
            func.sum(AIInvocationRecord.cost_minor_units).label("cost_minor_units"),
        )
        if filters.organization_id is not None:
            statement = statement.where(
                AIInvocationRecord.organization_id == filters.organization_id
            )
        if filters.business_purpose is not None:
            statement = statement.where(
                AIInvocationRecord.business_purpose == filters.business_purpose
            )
        if filters.provider is not None:
            statement = statement.where(AIInvocationRecord.provider == filters.provider)
        if filters.model is not None:
            statement = statement.where(AIInvocationRecord.model == filters.model)
        if filters.result_classification is not None:
            statement = statement.where(classification == filters.result_classification)
        if filters.currency is not None:
            statement = statement.where(AIInvocationRecord.currency == filters.currency)
        statement = statement.group_by(
            AIInvocationRecord.organization_id,
            AIInvocationRecord.business_purpose,
            AIInvocationRecord.provider,
            AIInvocationRecord.model,
            classification,
            AIInvocationRecord.currency,
        ).order_by(
            AIInvocationRecord.organization_id,
            AIInvocationRecord.business_purpose,
            AIInvocationRecord.provider,
            AIInvocationRecord.model,
            classification,
            AIInvocationRecord.currency,
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
        return tuple(
            AIInvocationMetricRow(
                organization_id=row.organization_id,
                business_purpose=row.business_purpose,
                provider=row.provider,
                model=row.model,
                result_classification=row.result_classification,
                currency=row.currency,
                invocation_count=int(row.invocation_count),
                failed_count=int(row.failed_count),
                degraded_count=int(row.degraded_count),
                average_latency_ms=(
                    float(row.average_latency_ms)
                    if row.average_latency_ms is not None
                    else None
                ),
                input_tokens=int(row.input_tokens or 0),
                output_tokens=int(row.output_tokens or 0),
                cost_minor_units=int(row.cost_minor_units or 0),
            )
            for row in rows
        )
