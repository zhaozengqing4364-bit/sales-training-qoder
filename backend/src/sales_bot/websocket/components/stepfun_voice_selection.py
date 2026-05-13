from __future__ import annotations

from collections.abc import Iterable, Mapping


def resolve_session_voice(
    *,
    default_voice: str,
    runtime_snapshot: Mapping[str, object] | None,
    current_stage_key: str | None = None,
    unavailable_voice_ids: Iterable[str] | None = None,
    allow_hot_switch: bool = False,
) -> str:
    unavailable = set(unavailable_voice_ids or [])
    voice_id = _snapshot_voice_id(runtime_snapshot)
    if allow_hot_switch and current_stage_key:
        voice_id = _stage_voice_id(runtime_snapshot, current_stage_key) or voice_id
    if not voice_id or voice_id in unavailable:
        return default_voice
    return voice_id


def _snapshot_voice_id(runtime_snapshot: Mapping[str, object] | None) -> str | None:
    if not isinstance(runtime_snapshot, Mapping):
        return None
    value = runtime_snapshot.get("role_profile_voice_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _stage_voice_id(
    runtime_snapshot: Mapping[str, object] | None, current_stage_key: str
) -> str | None:
    if not isinstance(runtime_snapshot, Mapping):
        return None
    stage_snapshots = runtime_snapshot.get("stage_snapshots")
    if not isinstance(stage_snapshots, Mapping):
        return None
    stage_snapshot = stage_snapshots.get(current_stage_key)
    if not isinstance(stage_snapshot, Mapping):
        return None
    runtime_payload = stage_snapshot.get("runtime_payload")
    if not isinstance(runtime_payload, Mapping):
        return None
    value = runtime_payload.get("role_profile_voice_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
