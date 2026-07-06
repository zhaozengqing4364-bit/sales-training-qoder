from __future__ import annotations

from typing import Any

from sales_trainer.models import SalesTrainerAudioScorePrompt
from sales_trainer.schemas import AudioScorePromptUpdate
from sales_trainer.services.asset_revision_service import AssetChangeClass
from sales_trainer.services.material_service import (
    normalize_audio_score_output_schema,
    normalize_learner_rubric,
)

PROMPT_RESOURCE_TYPE = "sales_trainer_audio_score_prompt"
HIGH_RISK_PROMPT_FIELDS = frozenset(
    {
        "purpose",
        "system_prompt",
        "scoring_template",
        "output_schema",
        "learner_rubric",
    }
)


def prompt_lifecycle_snapshot(
    prompt: SalesTrainerAudioScorePrompt,
) -> dict[str, Any]:
    return {
        "prompt_id": prompt.prompt_id,
        "name": prompt.name,
        "purpose": prompt.purpose,
        "system_prompt": prompt.system_prompt,
        "scoring_template": prompt.scoring_template,
        "output_schema": normalize_audio_score_output_schema(prompt.output_schema),
        "learner_rubric": normalize_learner_rubric(prompt.learner_rubric),
        "version": int(prompt.version),
        "status": prompt.status,
    }


def prompt_revision_payload_from_update(
    prompt: SalesTrainerAudioScorePrompt,
    payload: AudioScorePromptUpdate,
) -> dict[str, Any]:
    next_snapshot = prompt_lifecycle_snapshot(prompt)
    data = payload.model_dump(exclude_unset=True)
    if "output_schema" in data:
        data["output_schema"] = normalize_audio_score_output_schema(
            data["output_schema"]
        )
    if "learner_rubric" in data:
        data["learner_rubric"] = normalize_learner_rubric(data["learner_rubric"])
    next_snapshot.update(data)
    next_snapshot["status"] = "published"
    return next_snapshot


def apply_prompt_revision_payload(
    prompt: SalesTrainerAudioScorePrompt,
    payload: dict[str, Any],
    *,
    actor_id: str,
    revision_no: int,
) -> None:
    for field in (
        "name",
        "purpose",
        "system_prompt",
        "scoring_template",
    ):
        if field in payload:
            setattr(prompt, field, payload[field])
    if "output_schema" in payload:
        setattr(
            prompt,
            "output_schema",
            normalize_audio_score_output_schema(payload["output_schema"]),
        )
    if "learner_rubric" in payload:
        setattr(
            prompt,
            "learner_rubric",
            normalize_learner_rubric(payload["learner_rubric"]),
        )
    setattr(prompt, "version", revision_no)
    setattr(prompt, "status", "published")
    setattr(prompt, "updated_by", actor_id)


def prompt_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    changed_fields = set(prompt_changed_fields(previous, next_snapshot))
    if changed_fields & HIGH_RISK_PROMPT_FIELDS:
        return "scoring_high_risk"
    return "non_semantic"


def prompt_lifecycle_metadata(
    previous: dict[str, Any] | None,
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    changed_fields = (
        prompt_changed_fields(previous, next_snapshot) if previous is not None else []
    )
    return {
        "previous": previous,
        "next": next_snapshot,
        "changed_fields": changed_fields,
    }


def prompt_changed_fields(
    previous: dict[str, Any] | None,
    next_snapshot: dict[str, Any],
) -> list[str]:
    if previous is None:
        return []
    fields = (
        "name",
        "purpose",
        "system_prompt",
        "scoring_template",
        "output_schema",
        "learner_rubric",
        "version",
        "status",
    )
    return [field for field in fields if previous.get(field) != next_snapshot.get(field)]
