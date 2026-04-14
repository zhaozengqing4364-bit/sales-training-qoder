"""
Utilities for projecting immutable voice policy snapshot references.
"""

from __future__ import annotations

from typing import Any

from common.db.schemas import VoicePolicySnapshotReference
from agent.services.industry_pack_contract import build_runtime_binding_summary


def build_voice_policy_snapshot_ref_payload(snapshot: Any) -> dict[str, Any] | None:
    """Extract stable baseline fields from a persisted session snapshot."""
    if not isinstance(snapshot, dict):
        return None

    reference: dict[str, Any] = {
        "voice_mode": snapshot.get("voice_mode"),
        "runtime_profile_id": snapshot.get("runtime_profile_id"),
        "instruction_contract_hash": snapshot.get("instruction_contract_hash"),
        "network_access_mode": snapshot.get("network_access_mode"),
        "resolved_at": snapshot.get("resolved_at"),
        "runtime_binding": build_runtime_binding_summary(snapshot),
    }

    tool_policy = snapshot.get("tool_policy")
    reference["tool_policy"] = tool_policy if isinstance(tool_policy, dict) else {}

    knowledge_base_ids = snapshot.get("knowledge_base_ids")
    if isinstance(knowledge_base_ids, list):
        reference["knowledge_base_ids"] = [
            str(item) for item in knowledge_base_ids if item is not None
        ]
    else:
        reference["knowledge_base_ids"] = []

    source = snapshot.get("source")
    if isinstance(source, dict):
        reference["source"] = {str(key): str(value) for key, value in source.items()}
    else:
        reference["source"] = {}

    association_override = snapshot.get("agent_persona_override_config")
    if isinstance(association_override, dict):
        reference["agent_persona_override_config"] = association_override

    return reference


def build_voice_policy_snapshot_ref(
    snapshot: Any,
) -> VoicePolicySnapshotReference | None:
    """Build typed snapshot reference model used by practice session responses."""
    payload = build_voice_policy_snapshot_ref_payload(snapshot)
    if payload is None:
        return None
    return VoicePolicySnapshotReference.model_validate(payload)
