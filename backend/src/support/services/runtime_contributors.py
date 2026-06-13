from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

VoicePolicyToolTypesContributor = Callable[
    [AsyncSession, dict[str, Any]],
    Awaitable[list[str]],
]
RoleplayDiagnosticsContributor = Callable[
    [Any, dict[str, Any]],
    dict[str, Any],
]
ConfigAssetCenterContributor = Callable[
    [AsyncSession, datetime],
    Awaitable[dict[str, object]],
]


@dataclass(frozen=True)
class RuntimePresentationReview:
    payload: dict[str, Any] | None
    error: str | None = None


PresentationReviewContributor = Callable[
    [AsyncSession, str],
    Awaitable[RuntimePresentationReview],
]

_voice_policy_tool_types_contributors: dict[str, VoicePolicyToolTypesContributor] = {}
_presentation_review_contributors: dict[str, PresentationReviewContributor] = {}
_roleplay_diagnostics_contributors: dict[str, RoleplayDiagnosticsContributor] = {}
_config_asset_center_contributors: dict[str, ConfigAssetCenterContributor] = {}


def register_voice_policy_tool_types_contributor(
    provider_key: str,
    contributor: VoicePolicyToolTypesContributor,
) -> None:
    _voice_policy_tool_types_contributors[provider_key] = contributor


def register_presentation_review_contributor(
    provider_key: str,
    contributor: PresentationReviewContributor,
) -> None:
    _presentation_review_contributors[provider_key] = contributor


def register_roleplay_diagnostics_contributor(
    provider_key: str,
    contributor: RoleplayDiagnosticsContributor,
) -> None:
    _roleplay_diagnostics_contributors[provider_key] = contributor


def register_config_asset_center_contributor(
    provider_key: str,
    contributor: ConfigAssetCenterContributor,
) -> None:
    _config_asset_center_contributors[provider_key] = contributor


def clear_runtime_contributors() -> None:
    _voice_policy_tool_types_contributors.clear()
    _presentation_review_contributors.clear()
    _roleplay_diagnostics_contributors.clear()
    _config_asset_center_contributors.clear()


async def build_registered_voice_policy_tool_types(
    db: AsyncSession,
    snapshot: dict[str, Any],
) -> list[str]:
    tool_types: list[str] = []
    seen: set[str] = set()
    for provider_key, contributor in _voice_policy_tool_types_contributors.items():
        try:
            contributed = await contributor(db, snapshot)
        except Exception as exc:  # noqa: BLE001
            _log_contributor_failure(provider_key, exc)
            continue
        for tool_type in contributed:
            if not tool_type or tool_type in seen:
                continue
            seen.add(tool_type)
            tool_types.append(tool_type)
    return tool_types


async def build_registered_presentation_review(
    db: AsyncSession,
    session_id: str,
) -> RuntimePresentationReview:
    for provider_key, contributor in _presentation_review_contributors.items():
        try:
            review = await contributor(db, session_id)
        except Exception as exc:  # noqa: BLE001
            _log_contributor_failure(provider_key, exc)
            continue
        if review.payload is not None or review.error is not None:
            return review
    return RuntimePresentationReview(payload=None)


def build_registered_roleplay_diagnostics(
    session: Any,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    for provider_key, contributor in _roleplay_diagnostics_contributors.items():
        try:
            diagnostics = contributor(session, snapshot)
        except Exception as exc:  # noqa: BLE001
            _log_contributor_failure(provider_key, exc)
            continue
        if diagnostics:
            return diagnostics
    return {}


async def build_registered_config_asset_center(
    db: AsyncSession,
    *,
    now: datetime,
) -> dict[str, object]:
    for provider_key, contributor in _config_asset_center_contributors.items():
        try:
            payload = await contributor(db, now)
        except Exception as exc:  # noqa: BLE001
            _log_contributor_failure(provider_key, exc)
            continue
        if payload:
            return payload
    return build_empty_config_asset_center_payload()


def build_empty_config_asset_center_payload() -> dict[str, object]:
    return {
        "status": "unknown",
        "dual_read": {
            "enabled": False,
            "promotion_ready": False,
            "blocked_reasons": [],
            "approval_id": None,
            "window_start": None,
            "window_end": None,
        },
    }


def _log_contributor_failure(provider_key: str, exc: Exception) -> None:
    logger.warning(
        "support_runtime_contributor_failed",
        provider_key=provider_key,
        error=str(exc),
        exc_info=True,
    )
