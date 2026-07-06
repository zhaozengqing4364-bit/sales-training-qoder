"""Immutable voice runtime policy snapshot for StepFun sessions."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, cast

from prompt_templates.compiled_contract import compose_turn_instruction_text
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
class ContractValidationResult:
    """Instruction contract validation diagnostic."""

    valid: bool
    expected_hash: str
    actual_hash: str
    reason: str = "ok"


@dataclass(frozen=True)
class ProfileDiff:
    """Field-level diagnostic diff between two runtime profiles."""

    changed_fields: tuple[str, ...]
    before: Mapping[str, Any]
    after: Mapping[str, Any]

    @property
    def has_changes(self) -> bool:
        return bool(self.changed_fields)


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
    role_anchor_text: str = ""
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
        object.__setattr__(self, "role_anchor_text", self.role_anchor_text.strip())
        object.__setattr__(
            self,
            "knowledge_base_ids",
            tuple(
                str(item).strip()
                for item in self.knowledge_base_ids
                if str(item).strip()
            ),
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
            model_name=_as_text(snapshot.get("model_name"), "stepaudio-2.5-realtime"),
            voice_name=_as_text(snapshot.get("voice_name"), "qingchunshaonv"),
            temperature=_as_float(snapshot.get("temperature"), 0.7),
            instructions=instructions,
            instruction_contract_hash=contract_hash,
            knowledge_base_ids=_as_kb_ids(snapshot.get("knowledge_base_ids")),
            tool_policy=tool_policy if isinstance(tool_policy, Mapping) else {},
            role_anchor_text=_as_text(snapshot.get("role_anchor_text")),
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

    def compile_instructions(
        self,
        *,
        base_instructions: str | None = None,
        grounding_context: str = "",
        roleplay_turn_instruction: str = "",
        role_anchor_text: str | None = None,
    ) -> str:
        anchor = (
            self.role_anchor_text
            if role_anchor_text is None
            else str(role_anchor_text or "").strip()
        )
        return cast(
            str,
            compose_turn_instruction_text(
                base_instructions=(
                    self.instructions
                    if base_instructions is None
                    else base_instructions
                ),
                grounding_context=grounding_context,
                roleplay_turn_instruction=roleplay_turn_instruction,
                role_anchor_text=anchor,
            ),
        )

    def validate_instruction_contract(self) -> ContractValidationResult:
        return self.verify_contract_hash(
            instructions=self.instructions,
            contract_hash=self.instruction_contract_hash,
        )

    @staticmethod
    def verify_contract_hash(
        *,
        instructions: str,
        contract_hash: str,
    ) -> ContractValidationResult:
        normalized_instructions = instructions.strip()
        expected_hash = build_instruction_contract_hash(normalized_instructions)
        actual_hash = contract_hash.strip()
        if not normalized_instructions:
            return ContractValidationResult(
                valid=False,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
                reason="empty_instructions",
            )
        if not actual_hash:
            return ContractValidationResult(
                valid=False,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
                reason="missing_instruction_contract_hash",
            )
        if expected_hash != actual_hash:
            return ContractValidationResult(
                valid=False,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
                reason="instruction_contract_hash_mismatch",
            )
        return ContractValidationResult(
            valid=True,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
        )

    def diff(self, other: VoiceRuntimeProfile) -> ProfileDiff:
        return self.diff_with(other)

    def diff_with(self, other: VoiceRuntimeProfile) -> ProfileDiff:
        before = self.to_diagnostic_dict()
        after = other.to_diagnostic_dict()
        field_order = (
            "voice_mode",
            "model_name",
            "voice_name",
            "temperature",
            "instructions",
            "instruction_contract_hash",
            "role_anchor_text",
            "knowledge_base_ids",
            "tool_policy",
            "connection_health",
        )
        changed = tuple(key for key in field_order if before[key] != after[key])
        return ProfileDiff(changed_fields=changed, before=before, after=after)

    def to_diagnostic_dict(self) -> Mapping[str, Any]:
        return FrozenDict(
            {
                "voice_mode": self.voice_mode,
                "model_name": self.model_name,
                "voice_name": self.voice_name,
                "temperature": self.temperature,
                "instructions": self.instructions,
                "instruction_contract_hash": self.instruction_contract_hash,
                "role_anchor_text": self.role_anchor_text,
                "knowledge_base_ids": self.knowledge_base_ids,
                "tool_policy": self.tool_policy,
                "connection_health": self.connection_health,
            }
        )

    @staticmethod
    def _normalize_connection_health(value: str) -> str:
        normalized = str(value or "healthy").strip().lower()
        if normalized in {"healthy", "degraded", "recovering"}:
            return normalized
        return "healthy"
