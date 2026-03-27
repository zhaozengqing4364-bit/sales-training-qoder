"""Shared backend asset metadata registry for governance and fault linking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


AssetIdExtractor = Callable[[Any], Iterable[str]]
AssetAdminPathBuilder = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class AssetRegistration:
    asset_type: str
    label: str
    build_admin_path: AssetAdminPathBuilder
    extract_ids: AssetIdExtractor


def _extract_session_attr(record: Any, attr_name: str) -> tuple[str, ...]:
    session = getattr(record, "session", None)
    value = str(getattr(session, attr_name, "") or "").strip()
    return (value,) if value else ()


def _extract_runtime_profile_ids(record: Any) -> tuple[str, ...]:
    session = getattr(record, "session", None)
    snapshot = getattr(record, "voice_policy_snapshot", {}) or {}
    value = str(
        getattr(session, "voice_runtime_profile_id", None)
        or snapshot.get("runtime_profile_id")
        or ""
    ).strip()
    return (value,) if value else ()


def _extract_knowledge_base_ids(record: Any) -> tuple[str, ...]:
    snapshot = getattr(record, "voice_policy_snapshot", {}) or {}
    raw_kb_ids = snapshot.get("knowledge_base_ids")
    if not isinstance(raw_kb_ids, list):
        return ()

    refs: list[str] = []
    seen: set[str] = set()
    for kb_id in raw_kb_ids:
        normalized = str(kb_id or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        refs.append(normalized)
    return tuple(refs)


_ASSET_REGISTRATIONS: tuple[AssetRegistration, ...] = (
    AssetRegistration(
        asset_type="persona",
        label="角色",
        build_admin_path=lambda _asset_id: "/admin/personas",
        extract_ids=lambda record: _extract_session_attr(record, "persona_id"),
    ),
    AssetRegistration(
        asset_type="presentation",
        label="PPT",
        build_admin_path=lambda _asset_id: "/admin/presentations",
        extract_ids=lambda record: _extract_session_attr(record, "presentation_id"),
    ),
    AssetRegistration(
        asset_type="runtime_profile",
        label="运行时配置",
        build_admin_path=lambda _asset_id: "/admin/voice-runtime",
        extract_ids=_extract_runtime_profile_ids,
    ),
    AssetRegistration(
        asset_type="knowledge_base",
        label="知识库",
        build_admin_path=lambda _asset_id: "/admin/knowledge",
        extract_ids=_extract_knowledge_base_ids,
    ),
)

_ASSET_REGISTRATION_MAP = {
    registration.asset_type: registration for registration in _ASSET_REGISTRATIONS
}


def supported_asset_types() -> tuple[str, ...]:
    return tuple(registration.asset_type for registration in _ASSET_REGISTRATIONS)


def build_empty_asset_governance_indexes() -> dict[str, dict[str, dict[str, Any]]]:
    return {asset_type: {} for asset_type in supported_asset_types()}


def get_asset_registration(asset_type: str) -> AssetRegistration:
    try:
        return _ASSET_REGISTRATION_MAP[asset_type]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise KeyError(f"Unsupported asset type: {asset_type}") from exc


def iter_asset_refs(record: Any) -> tuple[tuple[str, str], ...]:
    refs: list[tuple[str, str]] = []
    for registration in _ASSET_REGISTRATIONS:
        for asset_id in registration.extract_ids(record):
            refs.append((registration.asset_type, asset_id))
    return tuple(refs)
