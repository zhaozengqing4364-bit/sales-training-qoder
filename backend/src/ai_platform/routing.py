"""Published model routing policy contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_platform.contracts import (
    AIErrorClassification,
    BudgetScope,
    DataClassification,
)
from ai_platform.errors import ModelRouteNotPublishedError


def compute_model_routing_profile_content_hash(
    snapshot: PublishedModelRoutingProfileSnapshot | dict[str, Any],
) -> str:
    value = (
        snapshot.model_dump(mode="json")
        if isinstance(snapshot, PublishedModelRoutingProfileSnapshot)
        else snapshot
    )
    digest = hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


class ModelRoute(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    calibrated_for_formal_scoring: bool = False


class PublishedModelRoutingProfileSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    profile_id: str = Field(min_length=1)
    business_purpose: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    revision_no: int = Field(ge=1)
    status: Literal["published"]
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    timeout_policy_ref: str = Field(min_length=1)
    max_provider_retries: int = Field(ge=0, le=5)
    max_schema_retries: int = Field(ge=0, le=3)
    retry_policy_ref: str = Field(min_length=1)
    requests_per_minute: int = Field(gt=0)
    rate_limit_scopes: tuple[BudgetScope, ...]
    budget_scope: BudgetScope
    budget_limit_minor_units: int = Field(ge=0)
    budget_reservation_minor_units: int = Field(ge=0)
    budget_window_seconds: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    circuit_failure_threshold: int = Field(gt=0)
    circuit_recovery_seconds: int = Field(gt=0)
    fallback_allowed: bool = False
    fallback_error_allowlist: tuple[AIErrorClassification, ...] = ()
    fallback: ModelRoute | None = None
    calibrated_for_formal_scoring: bool = False
    allowed_data_classifications: tuple[DataClassification, ...]

    @model_validator(mode="after")
    def validate_safe_policy(self) -> PublishedModelRoutingProfileSnapshot:
        safe_fallback_classes = {
            AIErrorClassification.TIMEOUT,
            AIErrorClassification.PROVIDER_UNAVAILABLE,
            AIErrorClassification.CIRCUIT_OPEN,
            AIErrorClassification.OUTPUT_SCHEMA_INVALID,
            AIErrorClassification.EMPTY_RESPONSE,
        }
        if set(self.fallback_error_allowlist) - safe_fallback_classes:
            raise ValueError("fallback allowlist contains unsafe failure classes")
        if self.fallback_allowed and self.fallback is None:
            raise ValueError("fallback_allowed requires an explicit fallback route")
        if not self.allowed_data_classifications:
            raise ValueError("at least one data classification must be allowed")
        if not self.rate_limit_scopes or len(set(self.rate_limit_scopes)) != len(
            self.rate_limit_scopes
        ):
            raise ValueError("rate_limit_scopes must be non-empty and unique")
        if self.budget_reservation_minor_units > self.budget_limit_minor_units:
            raise ValueError("budget reservation cannot exceed the budget limit")
        if (
            self.budget_limit_minor_units == 0
            or self.budget_reservation_minor_units == 0
        ):
            raise ValueError("budget limit and reservation must be explicitly positive")
        return self


class PublishedModelRoutingProfileResolver(Protocol):
    async def resolve_published(
        self, *, profile_id: str, revision_id: str
    ) -> PublishedModelRoutingProfileSnapshot:
        """Resolve one exact published routing profile."""


class StaticPublishedModelRoutingProfileResolver:
    def __init__(self, profiles: list[PublishedModelRoutingProfileSnapshot]) -> None:
        self._profiles = {
            (profile.profile_id, profile.revision_id): profile for profile in profiles
        }

    async def resolve_published(
        self, *, profile_id: str, revision_id: str
    ) -> PublishedModelRoutingProfileSnapshot:
        try:
            return self._profiles[(profile_id, revision_id)]
        except KeyError as exc:
            raise ModelRouteNotPublishedError() from exc
