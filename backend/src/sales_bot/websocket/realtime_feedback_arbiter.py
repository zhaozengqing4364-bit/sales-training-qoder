"""Shared pacing and priority rules for realtime coaching signals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from common.effectiveness import build_action_card
from common.effectiveness.schemas import ActionCard, PassFlags

PrimarySource = Literal["fuzzy_detection", "score"]

_SEVERITY_PRIORITY: dict[str, float] = {
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
}


@dataclass(frozen=True)
class RealtimeFeedbackPacingState:
    """Minimal reconnect-safe state for realtime coaching dedupe."""

    last_action_signature: str | None = None
    last_action_turn: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.last_action_signature:
            payload["last_action_signature"] = self.last_action_signature
        if self.last_action_turn is not None:
            payload["last_action_turn"] = self.last_action_turn
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RealtimeFeedbackPacingState":
        if not isinstance(payload, dict):
            return cls()

        signature = payload.get("last_action_signature")
        turn = payload.get("last_action_turn")
        return cls(
            last_action_signature=signature if isinstance(signature, str) and signature else None,
            last_action_turn=max(1, int(turn)) if isinstance(turn, int) else None,
        )


@dataclass(frozen=True)
class RealtimeFeedbackDecision:
    """Arbiter output for one analyzed user turn."""

    primary_source: PrimarySource | None
    action_card: ActionCard | None
    fuzzy_detections: list[dict[str, Any]] = field(default_factory=list)
    stage_context: dict[str, Any] | None = None
    score_context: dict[str, Any] | None = None
    duplicate_action_suppressed: bool = False
    action_signature: str | None = None
    state: RealtimeFeedbackPacingState = field(default_factory=RealtimeFeedbackPacingState)


class RealtimeFeedbackArbiter:
    """Select one primary coaching direction while preserving context signals."""

    def decide(
        self,
        *,
        turn_number: int | None,
        fuzzy_detections: list[dict[str, Any]] | None = None,
        score_suggestions: list[str] | None = None,
        stage_context: dict[str, Any] | None = None,
        score_context: dict[str, Any] | None = None,
        pass_flags: PassFlags | None = None,
        prior_state: RealtimeFeedbackPacingState | None = None,
    ) -> RealtimeFeedbackDecision:
        normalized_turn = self._normalize_turn_number(turn_number)
        prior = prior_state or RealtimeFeedbackPacingState()
        detections = [item for item in (fuzzy_detections or []) if isinstance(item, dict)]
        suggestions = [
            tip.strip()
            for tip in (score_suggestions or [])
            if isinstance(tip, str) and tip.strip()
        ]

        primary_source = self._pick_primary_source(detections, suggestions)
        action_card: ActionCard | None = None

        if primary_source == "fuzzy_detection":
            action_card = build_action_card(
                fuzzy_detections=[self._pick_primary_detection(detections)],
                pass_flags=pass_flags,
                stage_context=stage_context,
                score_context=score_context,
            )
        elif primary_source == "score":
            action_card = build_action_card(
                suggestions=[suggestions[0]],
                pass_flags=pass_flags,
                stage_context=stage_context,
                score_context=score_context,
            )

        action_signature = self._build_action_signature(primary_source, action_card)
        duplicate_action_suppressed = bool(
            action_card
            and action_signature
            and prior.last_action_signature == action_signature
            and prior.last_action_turn == normalized_turn
        )

        if action_signature and not duplicate_action_suppressed:
            next_state = RealtimeFeedbackPacingState(
                last_action_signature=action_signature,
                last_action_turn=normalized_turn,
            )
        else:
            next_state = prior

        return RealtimeFeedbackDecision(
            primary_source=primary_source,
            action_card=None if duplicate_action_suppressed else action_card,
            fuzzy_detections=detections,
            stage_context=stage_context if isinstance(stage_context, dict) else None,
            score_context=score_context if isinstance(score_context, dict) else None,
            duplicate_action_suppressed=duplicate_action_suppressed,
            action_signature=action_signature,
            state=next_state,
        )

    def _pick_primary_source(
        self,
        detections: list[dict[str, Any]],
        suggestions: list[str],
    ) -> PrimarySource | None:
        if detections and suggestions:
            primary_detection = self._pick_primary_detection(detections)
            fuzzy_priority = self._fuzzy_priority(primary_detection)
            score_priority = self._score_priority(suggestions)
            return "score" if score_priority > fuzzy_priority else "fuzzy_detection"
        if detections:
            return "fuzzy_detection"
        if suggestions:
            return "score"
        return None

    def _pick_primary_detection(
        self,
        detections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not detections:
            return {}
        return max(detections, key=self._fuzzy_priority)

    def _fuzzy_priority(self, detection: dict[str, Any]) -> float:
        severity = detection.get("severity")
        if not isinstance(severity, str):
            return 1.0
        return _SEVERITY_PRIORITY.get(severity.strip().lower(), 1.0)

    def _score_priority(self, suggestions: list[str]) -> float:
        if not suggestions:
            return 0.0
        return 2.5

    def _build_action_signature(
        self,
        primary_source: PrimarySource | None,
        action_card: ActionCard | None,
    ) -> str | None:
        if primary_source is None or action_card is None:
            return None
        raw = json.dumps(
            {
                "primary_source": primary_source,
                "action_card": action_card,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _normalize_turn_number(self, turn_number: int | None) -> int:
        if not isinstance(turn_number, int):
            return 1
        return max(1, turn_number)
