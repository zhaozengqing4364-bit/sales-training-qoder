from __future__ import annotations

from dataclasses import FrozenInstanceError

from sales_bot.websocket.voice_runtime_profile import VoiceRuntimeProfile


def _valid_profile(**overrides: object) -> VoiceRuntimeProfile:
    values = {
        "voice_mode": "stepfun_realtime",
        "model_name": "step-audio-2",
        "voice_name": "qingchunshaonv",
        "temperature": 0.7,
        "instructions": "保持销售训练角色。",
        "instruction_contract_hash": "hash-123",
        "knowledge_base_ids": ("kb-1",),
        "tool_policy": {"network_access_mode": "off"},
    }
    values.update(overrides)
    return VoiceRuntimeProfile(**values)


def test_validate_rejects_empty_instructions() -> None:
    profile = _valid_profile(instructions="  ")

    assert profile.validate() is False


def test_validate_accepts_valid_profile() -> None:
    profile = _valid_profile()

    assert profile.validate() is True


def test_from_policy_snapshot_parses_all_fields() -> None:
    snapshot = {
        "voice_mode": "stepfun_realtime",
        "model_name": "step-audio-2",
        "voice_name": "qingchunshaonv",
        "temperature": "0.42",
        "instructions": "保持销售训练角色。",
        "instruction_contract_hash": "hash-abc",
        "knowledge_base_ids": ["kb-1", "kb-2"],
        "tool_policy": {"network_access_mode": "off", "retrieval_top_k": 3},
        "connection_health": "degraded",
    }

    profile = VoiceRuntimeProfile.from_policy_snapshot(snapshot)

    assert profile.voice_mode == "stepfun_realtime"
    assert profile.model_name == "step-audio-2"
    assert profile.voice_name == "qingchunshaonv"
    assert profile.temperature == 0.42
    assert profile.instructions == "保持销售训练角色。"
    assert profile.instruction_contract_hash == "hash-abc"
    assert profile.knowledge_base_ids == ("kb-1", "kb-2")
    assert profile.tool_policy["network_access_mode"] == "off"
    assert profile.tool_policy["retrieval_top_k"] == 3
    assert profile.connection_health == "degraded"


def test_instruction_contract_hash_is_immutable() -> None:
    profile = _valid_profile()

    try:
        profile.instruction_contract_hash = "changed"  # type: ignore[misc]
    except FrozenInstanceError:
        return

    raise AssertionError("instruction_contract_hash should be immutable")


def test_equality_by_value_not_identity() -> None:
    first = _valid_profile()
    second = _valid_profile()

    assert first is not second
    assert first == second


def test_from_policy_snapshot_does_not_share_mutable_policy_references() -> None:
    snapshot = {
        "voice_mode": "stepfun_realtime",
        "model_name": "step-audio-2",
        "voice_name": "qingchunshaonv",
        "temperature": 0.7,
        "instructions": "保持销售训练角色。",
        "instruction_contract_hash": "hash-abc",
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"network_access_mode": "off", "nested": {"enabled": True}},
    }

    profile = VoiceRuntimeProfile.from_policy_snapshot(snapshot)
    snapshot["knowledge_base_ids"].append("kb-2")
    snapshot["tool_policy"]["network_access_mode"] = "controlled"
    snapshot["tool_policy"]["nested"]["enabled"] = False

    assert profile.knowledge_base_ids == ("kb-1",)
    assert profile.tool_policy["network_access_mode"] == "off"
    assert profile.tool_policy["nested"]["enabled"] is True


def test_connection_health_defaults_to_healthy() -> None:
    profile = VoiceRuntimeProfile.from_policy_snapshot(
        {
            "voice_mode": "stepfun_realtime",
            "model_name": "step-audio-2",
            "voice_name": "qingchunshaonv",
            "temperature": 0.7,
            "instructions": "保持销售训练角色。",
            "instruction_contract_hash": "hash-abc",
        }
    )

    assert profile.connection_health == "healthy"
