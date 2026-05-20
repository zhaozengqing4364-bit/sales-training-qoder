"""Immutable voice runtime policy snapshot for StepFun sessions."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from sales_bot.services.voice_instruction_compiler import (
    build_instruction_contract_hash,
)


class FrozenDict(Mapping[str, Any]):
    """Small immutable mapping with value equality."""

    def __init__(self, values: Mapping[str, Any] | None = None) -> None:
        source = values if isinstance(values, Mapping) else {}
        self._items = tuple(
            sorted((str(key), _freeze_value(value)) for key, value in source.items())
        )
        self._data = dict(self._items)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return False

    def __hash__(self) -> int:
        return hash(self._items)

    def __repr__(self) -> str:
        return repr(self._data)


def _freeze_value(value: Any) -> Any:
    if isinstance(value, FrozenDict):
        return value
    if isinstance(value, Mapping):
        return FrozenDict(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _as_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_kb_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


@dataclass(frozen=True)
class VoiceRuntimeProfile:
    """Immutable value object for stable voice runtime policy fields."""

    voice_mode: str
    model_name: str
    voice_name: str
    temperature: float
    instructions: str
    instruction_contract_hash: str
    knowledge_base_ids: tuple[str, ...]
    tool_policy: Mapping[str, Any]
    connection_health: str = "healthy"

    def __post_init__(self) -> None:
        object.__setattr__(self, "voice_mode", self.voice_mode.strip())
        object.__setattr__(self, "model_name", self.model_name.strip())
        object.__setattr__(self, "voice_name", self.voice_name.strip())
        object.__setattr__(self, "temperature", float(self.temperature))
        object.__setattr__(self, "instructions", self.instructions.strip())
        object.__setattr__(
            self,
            "instruction_contract_hash",
            self.instruction_contract_hash.strip(),
        )
        object.__setattr__(
            self,
            "knowledge_base_ids",
            tuple(str(item).strip() for item in self.knowledge_base_ids if str(item).strip()),
        )
        object.__setattr__(self, "tool_policy", FrozenDict(self.tool_policy))
        object.__setattr__(
            self,
            "connection_health",
            self._normalize_connection_health(self.connection_health),
        )

    @classmethod
    def from_policy_snapshot(cls, snapshot: Mapping[str, Any]) -> VoiceRuntimeProfile:
        """Build an immutable profile from a persisted/resolved policy snapshot."""

        instructions = _as_text(snapshot.get("instructions"))
        contract_hash = _as_text(snapshot.get("instruction_contract_hash"))
        if not contract_hash and instructions:
            contract_hash = build_instruction_contract_hash(instructions)
        tool_policy = snapshot.get("tool_policy")
        return cls(
            voice_mode=_as_text(snapshot.get("voice_mode"), "legacy"),
            model_name=_as_text(snapshot.get("model_name"), "step-audio-2"),
            voice_name=_as_text(snapshot.get("voice_name"), "qingchunshaonv"),
            temperature=_as_float(snapshot.get("temperature"), 0.7),
            instructions=instructions,
            instruction_contract_hash=contract_hash,
            knowledge_base_ids=_as_kb_ids(snapshot.get("knowledge_base_ids")),
            tool_policy=tool_policy if isinstance(tool_policy, Mapping) else {},
            connection_health=_as_text(snapshot.get("connection_health"), "healthy"),
        )

    def validate(self) -> bool:
        return bool(
            self.voice_mode
            and self.model_name
            and self.voice_name
            and self.instructions
            and self.instruction_contract_hash
            and 0.0 <= self.temperature <= 2.0
        )

    @staticmethod
    def _normalize_connection_health(value: str) -> str:
        normalized = str(value or "healthy").strip().lower()
        if normalized in {"healthy", "degraded", "recovering"}:
            return normalized
        return "healthy"
