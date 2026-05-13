"""Curriculum template-stage runtime state machine for StepFun sessions."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TEMPLATE_STAGE_WARNING_LEAD_SECONDS = 30.0
DEFAULT_TEMPLATE_STAGE_GRACE_SECONDS = 5.0


@dataclass(frozen=True)
class CurriculumStageRuntimeResult:
    runtime_state_patch: dict[str, Any] = field(default_factory=dict)
    websocket_events: list[dict[str, Any]] = field(default_factory=list)


class CurriculumStageRuntime:
    """Tracks curriculum template-stage progress for one live session."""

    def __init__(
        self,
        *,
        curriculum_plan: dict[str, Any] | None,
        stage_snapshots: dict[str, Any] | None,
        runtime_state: dict[str, Any] | None = None,
        warning_lead_seconds: float = DEFAULT_TEMPLATE_STAGE_WARNING_LEAD_SECONDS,
        grace_seconds: float = DEFAULT_TEMPLATE_STAGE_GRACE_SECONDS,
    ) -> None:
        self._stage_snapshots = (
            copy.deepcopy(stage_snapshots) if isinstance(stage_snapshots, dict) else {}
        )
        self._template_stage_entries = self._normalize_stage_entries(curriculum_plan)
        self._warning_lead_seconds = max(0.0, float(warning_lead_seconds))
        self._grace_seconds = max(0.0, float(grace_seconds))
        self._template_stage_context = self._restore_context(runtime_state)

    def initialize(self, *, now_seconds: float) -> CurriculumStageRuntimeResult:
        if self._template_stage_context is not None:
            return CurriculumStageRuntimeResult(
                runtime_state_patch=self._build_patch(),
                websocket_events=[],
            )
        if not self._template_stage_entries:
            return CurriculumStageRuntimeResult()
        self._activate_stage(index=0, now_seconds=now_seconds, previous_key=None)
        return CurriculumStageRuntimeResult(
            runtime_state_patch=self._build_patch(),
            websocket_events=[self._transition_event(previous_key=None)],
        )

    def runtime_state_patch(self) -> dict[str, Any]:
        return self._build_patch()

    def restore_runtime_state(self, runtime_state: dict[str, Any] | None) -> None:
        restored = self._restore_context(runtime_state)
        if restored is not None:
            self._template_stage_context = restored

    def handle_turn(
        self,
        *,
        turn_number: int,
        template_stage_score: float | None,
        now_seconds: float,
        template_stage_failed: bool = False,
        template_stage_failure_policy: str | None = None,
    ) -> CurriculumStageRuntimeResult:
        if self._template_stage_context is None:
            self.initialize(now_seconds=now_seconds)
        if self._template_stage_context is None:
            return CurriculumStageRuntimeResult()

        self._template_stage_context["template_stage_rounds"] = int(
            self._template_stage_context.get("template_stage_rounds") or 0
        ) + 1
        self._increment_version()

        if template_stage_failed:
            return self._apply_failure_policy(
                now_seconds=now_seconds,
                template_stage_failure_policy=template_stage_failure_policy,
            )

        stage = self._current_stage_entry()
        completion_policy = _as_dict(stage.get("completion_policy"))
        min_rounds = int(completion_policy.get("min_rounds") or 0)
        min_score = float(completion_policy.get("min_score") or 0.0)
        score = float(template_stage_score or 0.0)
        if score > 10.0:
            score = score / 10.0
        if (
            int(self._template_stage_context.get("template_stage_rounds") or 0)
            >= min_rounds
            and score >= min_score
        ):
            return self._advance_or_complete(now_seconds=now_seconds)
        return CurriculumStageRuntimeResult(runtime_state_patch=self._build_patch())

    def handle_timing(self, *, now_seconds: float) -> CurriculumStageRuntimeResult:
        if self._template_stage_context is None:
            self.initialize(now_seconds=now_seconds)
        if self._template_stage_context is None:
            return CurriculumStageRuntimeResult()

        stage = self._current_stage_entry()
        completion_policy = _as_dict(stage.get("completion_policy"))
        max_duration_seconds = float(completion_policy.get("max_duration_seconds") or 0.0)
        if max_duration_seconds <= 0:
            return CurriculumStageRuntimeResult(runtime_state_patch=self._build_patch())

        started_at = float(self._template_stage_context.get("template_stage_started_at") or now_seconds)
        elapsed_seconds = max(0.0, float(now_seconds) - started_at)
        if elapsed_seconds < max_duration_seconds:
            seconds_remaining = max_duration_seconds - elapsed_seconds
            warning_sent = bool(
                self._template_stage_context.get("template_stage_warning_sent")
            )
            if not warning_sent and seconds_remaining <= self._warning_lead_seconds:
                self._template_stage_context["template_stage_warning_sent"] = True
                self._increment_version()
                return CurriculumStageRuntimeResult(
                    runtime_state_patch=self._build_patch(),
                    websocket_events=[
                        {
                            "type": "template_stage_warning",
                            "data": {
                                "template_stage_key": self._template_stage_context.get(
                                    "template_stage_key"
                                ),
                                "template_stage_status": self._template_stage_context.get(
                                    "template_stage_status"
                                ),
                                "template_stage_seconds_remaining": round(seconds_remaining, 3),
                                "template_stage_version": self._template_stage_context.get(
                                    "template_stage_version"
                                ),
                            },
                        }
                    ],
                )
            return CurriculumStageRuntimeResult(runtime_state_patch=self._build_patch())

        grace_started_at = self._template_stage_context.get(
            "template_stage_grace_started_at"
        )
        if grace_started_at is None:
            self._template_stage_context["template_stage_grace_started_at"] = float(
                now_seconds
            )
            self._increment_version()
            return CurriculumStageRuntimeResult(runtime_state_patch=self._build_patch())
        if float(now_seconds) - float(grace_started_at) < self._grace_seconds:
            return CurriculumStageRuntimeResult(runtime_state_patch=self._build_patch())

        self._increment_version()
        return self._apply_failure_policy(now_seconds=now_seconds)

    def _normalize_stage_entries(
        self, curriculum_plan: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        raw_stages = curriculum_plan.get("stages") if isinstance(curriculum_plan, dict) else None
        stages = [stage for stage in raw_stages or [] if isinstance(stage, dict)]
        stages.sort(key=lambda stage: int(stage.get("order") or 0))
        entries: list[dict[str, Any]] = []
        for stage in stages:
            stage_key = str(stage.get("template_stage_key") or "").strip()
            if not stage_key or stage_key not in self._stage_snapshots:
                continue
            entries.append(copy.deepcopy(stage))
        if entries:
            return entries
        return [
            {"template_stage_key": stage_key, "order": index + 1}
            for index, stage_key in enumerate(self._stage_snapshots.keys())
        ]

    def _restore_context(
        self, runtime_state: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        context = (
            runtime_state.get("template_stage_context")
            if isinstance(runtime_state, dict)
            else None
        )
        if not isinstance(context, dict):
            return None
        stage_key = str(context.get("template_stage_key") or "").strip()
        if not stage_key or stage_key not in self._stage_snapshots:
            return None
        return copy.deepcopy(context)

    def _activate_stage(
        self,
        *,
        index: int,
        now_seconds: float,
        previous_key: str | None,
        template_stage_version: int | None = None,
    ) -> None:
        stage = self._template_stage_entries[index]
        previous_version = 0
        if isinstance(self._template_stage_context, dict):
            previous_version = int(
                self._template_stage_context.get("template_stage_version") or 0
            )
        self._template_stage_context = {
            "template_stage_key": stage["template_stage_key"],
            "template_stage_index": index,
            "template_stage_status": "active",
            "template_stage_started_at": float(now_seconds),
            "template_stage_rounds": 0,
            "template_stage_version": template_stage_version or previous_version + 1,
            "template_stage_warning_sent": False,
            "template_stage_grace_started_at": None,
        }
        logger.info(
            "template_stage_activated",
            template_stage_key=stage["template_stage_key"],
            template_stage_previous_key=previous_key,
        )

    def _increment_version(self) -> None:
        if self._template_stage_context is None:
            return
        self._template_stage_context["template_stage_version"] = int(
            self._template_stage_context.get("template_stage_version") or 0
        ) + 1

    def _current_stage_entry(self) -> dict[str, Any]:
        if self._template_stage_context is None:
            return {}
        index = int(self._template_stage_context.get("template_stage_index") or 0)
        if index < 0 or index >= len(self._template_stage_entries):
            return {}
        return self._template_stage_entries[index]

    def _advance_or_complete(self, *, now_seconds: float) -> CurriculumStageRuntimeResult:
        if self._template_stage_context is None:
            return CurriculumStageRuntimeResult()
        previous_key = str(self._template_stage_context.get("template_stage_key") or "")
        next_index = int(self._template_stage_context.get("template_stage_index") or 0) + 1
        if next_index >= len(self._template_stage_entries):
            self._template_stage_context["template_stage_status"] = "completed"
            self._increment_version()
            return CurriculumStageRuntimeResult(
                runtime_state_patch=self._build_patch(),
                websocket_events=[self._transition_event(previous_key=previous_key)],
            )
        self._activate_stage(
            index=next_index,
            now_seconds=now_seconds,
            previous_key=previous_key,
        )
        return CurriculumStageRuntimeResult(
            runtime_state_patch=self._build_patch(),
            websocket_events=[self._transition_event(previous_key=previous_key)],
        )

    def _apply_failure_policy(
        self,
        *,
        now_seconds: float,
        template_stage_failure_policy: str | None = None,
    ) -> CurriculumStageRuntimeResult:
        if self._template_stage_context is None:
            return CurriculumStageRuntimeResult()
        stage = self._current_stage_entry()
        failure_policy = str(
            template_stage_failure_policy or stage.get("failure_policy") or "retry_current"
        )
        if failure_policy == "retry_current":
            return CurriculumStageRuntimeResult(runtime_state_patch=self._build_patch())

        current_index = int(self._template_stage_context.get("template_stage_index") or 0)
        target_index = current_index
        if failure_policy == "allow_skip":
            target_index = min(current_index + 1, len(self._template_stage_entries) - 1)
        elif failure_policy == "fallback_to_previous":
            target_index = max(current_index - 1, 0)
        if target_index == current_index:
            return CurriculumStageRuntimeResult(runtime_state_patch=self._build_patch())

        previous_key = str(self._template_stage_context.get("template_stage_key") or "")
        self._activate_stage(
            index=target_index,
            now_seconds=now_seconds,
            previous_key=previous_key,
        )
        return CurriculumStageRuntimeResult(
            runtime_state_patch=self._build_patch(),
            websocket_events=[self._transition_event(previous_key=previous_key)],
        )

    def _build_patch(self) -> dict[str, Any]:
        if self._template_stage_context is None:
            return {}
        return {"template_stage_context": copy.deepcopy(self._template_stage_context)}

    def _transition_event(self, *, previous_key: str | None) -> dict[str, Any]:
        context = self._template_stage_context or {}
        return {
            "type": "template_stage_transition",
            "data": {
                "template_stage_key": context.get("template_stage_key"),
                "template_stage_status": context.get("template_stage_status"),
                "template_stage_previous_key": previous_key,
                "template_stage_version": context.get("template_stage_version"),
            },
        }


def _as_dict(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}
