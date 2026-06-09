from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sales_trainer.models import SalesTrainerUnit


@dataclass(frozen=True, slots=True)
class PathAudioBindingRefs:
    scoring_prompt_id: str | None
    material_id: str | None
    material_version_id: str | None


def audio_refs_from_unit(unit: SalesTrainerUnit) -> PathAudioBindingRefs:
    config = unit.config or {}
    if not isinstance(config, dict):
        return _empty_audio_refs()
    audio = config.get("audio")
    materials = config.get("materials")
    binding = _first_material_binding(materials)
    return PathAudioBindingRefs(
        scoring_prompt_id=_string_or_none(
            audio.get("scoring_prompt_id") if isinstance(audio, dict) else None
        ),
        material_id=_string_or_none(binding.get("material_id") if binding else None),
        material_version_id=_string_or_none(
            binding.get("locked_version_id") if binding else None
        ),
    )


def _first_material_binding(raw_materials: Any) -> dict[str, Any] | None:
    if not isinstance(raw_materials, dict):
        return None
    bindings = raw_materials.get("bindings")
    if not isinstance(bindings, list):
        return None
    first = bindings[0] if bindings else None
    return first if isinstance(first, dict) else None


def _string_or_none(value: Any) -> str | None:
    return str(value) if value else None


def _empty_audio_refs() -> PathAudioBindingRefs:
    return PathAudioBindingRefs(
        scoring_prompt_id=None,
        material_id=None,
        material_version_id=None,
    )
