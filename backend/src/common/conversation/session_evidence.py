"""Shared session evidence projection for report/replay/history consumers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.models import ConversationMessage
from common.db.models import PracticeSession, SessionStatus
from common.effectiveness import evaluate_effectiveness_snapshot
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from sales_bot.websocket.components.stepfun_message_helpers import (
    normalize_score_snapshot,
)

logger = get_logger(__name__)

STAGE_SEQUENCE = ["opening", "discovery", "presentation", "objection", "closing"]
STAGE_NAMES = {
    "opening": "开场破冰",
    "discovery": "需求挖掘",
    "presentation": "方案呈现",
    "objection": "异议处理",
    "closing": "促成成交",
}


@dataclass(slots=True)
class SessionEvidenceProjection:
    session: PracticeSession
    session_id: str
    scenario_type: str
    messages: list[dict[str, Any]]
    timeline_markers: list[dict[str, Any]]
    stage_summary: list[dict[str, Any]]
    total_duration_ms: int
    logic_score: float
    accuracy_score: float
    completeness_score: float
    overall_score: float
    effectiveness_snapshot: dict[str, Any] | None
    pass_flags: dict[str, bool] | None
    main_capability_passed: bool | None
    overall_result: str | None
    main_issue: dict[str, Any] | None
    next_goal: dict[str, Any] | None
    evaluable: bool | None
    not_evaluable_reason: str | None
    evidence_completeness: dict[str, Any]
    legacy_score_key_used: bool
    presentation_review: dict[str, Any] | None = None


class SessionEvidenceService:
    """Build a normalized evidence projection from PracticeSession + ordered messages."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_projection(
        self,
        *,
        session_id: str,
        session: PracticeSession | None = None,
        require_completed: bool = False,
        scenario_type: str | None = None,
    ) -> Result[SessionEvidenceProjection]:
        try:
            current_session = session
            if current_session is None:
                session_result = await self._get_session(session_id)
                if not session_result.is_success:
                    return session_result
                current_session = session_result.value

            resolved_scenario_type = self.resolve_scenario_type(
                current_session,
                scenario_type=scenario_type,
            )

            if require_completed and current_session.status != SessionStatus.COMPLETED.value:
                return Result.fail(
                    f"[SESSION_NOT_COMPLETED] Session must be completed for replay. "
                    f"Current status: {current_session.status}"
                )

            messages_result = await self._get_ordered_messages(session_id)
            if not messages_result.is_success:
                return messages_result

            projection = self.build_projection(
                current_session,
                messages_result.value,
                scenario_type=resolved_scenario_type,
            )
            if resolved_scenario_type == "presentation":
                presentation_result = await self._attach_presentation_review(
                    session_id=session_id,
                    projection=projection,
                )
                if not presentation_result.is_success:
                    return Result.fail(
                        presentation_result.fallback
                        or "[PRESENTATION_REVIEW_FAILED]"
                    )
                projection = presentation_result.value

            logger.info(
                "practice_session_evidence_projection_built",
                session_id=projection.session_id,
                scenario_type=projection.scenario_type,
                message_count=projection.evidence_completeness["message_count"],
                legacy_score_key_used=projection.legacy_score_key_used,
                projection_complete=projection.evidence_completeness["complete"],
                projection_missing_fields=projection.evidence_completeness["missing_fields"],
                presentation_review_available=bool(projection.presentation_review),
                presentation_page_metadata_complete=projection.evidence_completeness.get(
                    "page_metadata_complete"
                ),
                presentation_degraded_reasons=projection.evidence_completeness.get(
                    "degraded_reasons"
                ),
            )
            return Result.ok(projection)
        except (SQLAlchemyError, ValueError, OSError) as exc:
            logger.error(
                "practice_session_evidence_projection_failed",
                session_id=session_id,
                scenario_type=scenario_type,
                error=str(exc),
            )
            return Result.fail(f"[SESSION_EVIDENCE_FAILED] {str(exc)}")

    async def _get_session(self, session_id: str) -> Result[PracticeSession]:
        result = await self.db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return Result.fail(
                f"[SESSION_NOT_FOUND] Session with id '{session_id}' not found"
            )
        return Result.ok(session)

    async def _get_ordered_messages(
        self,
        session_id: str,
    ) -> Result[list[ConversationMessage]]:
        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.turn_number, ConversationMessage.timestamp)
        )
        return Result.ok(list(result.scalars().all()))

    @staticmethod
    def resolve_scenario_type(
        session: PracticeSession,
        *,
        scenario_type: str | None = None,
    ) -> str:
        scenario_from_relationship = None
        session_dict = getattr(session, "__dict__", {})
        scenario_obj = session_dict.get("scenario") if isinstance(session_dict, dict) else None
        if scenario_obj is not None:
            scenario_from_relationship = getattr(scenario_obj, "scenario_type", None)

        candidate = scenario_type or scenario_from_relationship
        normalized = str(candidate or "").lower()
        if normalized in {"sales", "presentation"}:
            return normalized
        return "presentation" if getattr(session, "presentation_id", None) else "sales"

    async def _attach_presentation_review(
        self,
        *,
        session_id: str,
        projection: SessionEvidenceProjection,
    ) -> Result[SessionEvidenceProjection]:
        from presentation_coach.services.presentation_report_service import (
            PresentationReportService,
        )

        review_result = await PresentationReportService(self.db).build_presentation_review(
            session_id
        )
        if not review_result.is_success or review_result.value is None:
            return Result.fail(review_result.fallback or "[PRESENTATION_REVIEW_FAILED]")

        review = review_result.value
        dimension_scores = review.get("dimension_scores")
        if not isinstance(dimension_scores, list):
            dimension_scores = []
        dimension_values = {
            str(item.get("name")): float(item.get("score") or 0.0)
            for item in dimension_scores
            if isinstance(item, dict)
        }

        remainder_scores = [
            dimension_values.get("专业性"),
            dimension_values.get("生动性"),
            dimension_values.get("互动问答"),
            dimension_values.get("其他表现"),
        ]
        remainder_scores = [score for score in remainder_scores if score is not None]

        projection.logic_score = float(
            dimension_values.get("流畅连贯性", projection.logic_score)
        )
        projection.accuracy_score = float(
            dimension_values.get("准确性", projection.accuracy_score)
        )
        if remainder_scores:
            projection.completeness_score = round(
                sum(remainder_scores) / len(remainder_scores),
                2,
            )
        overall_score = review.get("overall_score")
        if isinstance(overall_score, (int, float)):
            projection.overall_score = round(float(overall_score), 2)
        projection.stage_summary = []
        projection.effectiveness_snapshot = None
        projection.pass_flags = None
        projection.main_capability_passed = None
        projection.overall_result = None
        projection.main_issue = None
        projection.next_goal = None
        projection.evaluable = None
        projection.not_evaluable_reason = None
        projection.presentation_review = review
        projection.evidence_completeness = self._build_presentation_evidence_completeness(
            messages=projection.messages,
            review=review,
        )
        return Result.ok(projection)

    @staticmethod
    def _build_presentation_evidence_completeness(
        *,
        messages: list[dict[str, Any]],
        review: dict[str, Any],
    ) -> dict[str, Any]:
        diagnostics = review.get("diagnostics")
        if not isinstance(diagnostics, dict):
            diagnostics = {}
        required_points = review.get("required_talking_points")
        if not isinstance(required_points, dict):
            required_points = {}
        degraded_reasons = diagnostics.get("degraded_reasons")
        if not isinstance(degraded_reasons, list):
            degraded_reasons = []

        has_page_metadata = bool(diagnostics.get("has_page_metadata", False))
        page_summaries = review.get("page_summaries")
        if not isinstance(page_summaries, list):
            page_summaries = []

        missing_fields: list[str] = []
        if not has_page_metadata:
            missing_fields.append("page_metadata")
        if not page_summaries:
            missing_fields.append("page_summaries")
        if str(required_points.get("status") or "") != "complete":
            missing_fields.append("required_talking_points")

        return {
            "scenario_type": "presentation",
            "complete": not missing_fields,
            "message_count": len(messages),
            "message_analysis": sum(
                1
                for message in messages
                if any(
                    message.get(field) is not None
                    for field in (
                        "transcript_metadata",
                        "score_snapshot",
                        "ai_feedback",
                    )
                )
            ),
            "presentation_review_available": True,
            "page_metadata_complete": has_page_metadata,
            "page_summary_count": len(page_summaries),
            "required_talking_points_status": str(
                required_points.get("status") or "unknown"
            ),
            "required_points_total": int(required_points.get("total") or 0),
            "required_points_covered": int(required_points.get("covered") or 0),
            "required_points_missing": int(required_points.get("missing") or 0),
            "required_coverage_ratio": round(
                float(required_points.get("coverage_ratio") or 0.0),
                4,
            ),
            "degraded_reasons": degraded_reasons,
            "missing_fields": missing_fields,
        }

    @classmethod
    def build_projection(
        cls,
        session: PracticeSession,
        messages: list[ConversationMessage],
        *,
        scenario_type: str | None = None,
    ) -> SessionEvidenceProjection:
        normalized_messages: list[dict[str, Any]] = []
        legacy_score_key_used = False
        resolved_scenario_type = cls.resolve_scenario_type(
            session,
            scenario_type=scenario_type,
        )

        for index, message in enumerate(messages):
            normalized = cls.serialize_message(message, fallback_turn_number=index + 1)
            raw_snapshot = getattr(message, "score_snapshot", None)
            if isinstance(raw_snapshot, dict) and raw_snapshot.get("overall") is not None:
                legacy_score_key_used = True
            normalized_messages.append(normalized)

        logic_score, accuracy_score, completeness_score = cls._resolve_score_triplet(
            session,
            normalized_messages,
        )
        overall_score = round((logic_score + accuracy_score + completeness_score) / 3.0, 2)
        snapshot = ensure_effectiveness_snapshot(
            session,
            resolved_scores=(logic_score, accuracy_score, completeness_score),
        )
        evidence_completeness = cls._build_evidence_completeness(
            session=session,
            messages=normalized_messages,
            snapshot=snapshot,
            legacy_score_key_used=legacy_score_key_used,
        )

        return SessionEvidenceProjection(
            session=session,
            session_id=str(session.session_id),
            scenario_type=resolved_scenario_type,
            messages=normalized_messages,
            timeline_markers=cls.build_timeline_markers(normalized_messages),
            stage_summary=cls.build_stage_summary(normalized_messages),
            total_duration_ms=cls.calculate_total_duration(normalized_messages),
            logic_score=logic_score,
            accuracy_score=accuracy_score,
            completeness_score=completeness_score,
            overall_score=overall_score,
            effectiveness_snapshot=snapshot,
            pass_flags=snapshot.get("pass_flags")
            if isinstance(snapshot.get("pass_flags"), dict)
            else None,
            main_capability_passed=(
                snapshot.get("main_capability_passed")
                if isinstance(snapshot.get("main_capability_passed"), bool)
                else None
            ),
            overall_result=(
                str(snapshot.get("overall_result"))
                if snapshot.get("overall_result") is not None
                else None
            ),
            main_issue=snapshot.get("main_issue")
            if isinstance(snapshot.get("main_issue"), dict)
            else None,
            next_goal=snapshot.get("next_goal")
            if isinstance(snapshot.get("next_goal"), dict)
            else None,
            evaluable=bool(snapshot.get("evaluable", False)),
            not_evaluable_reason=(
                str(snapshot.get("not_evaluable_reason"))
                if snapshot.get("not_evaluable_reason") is not None
                else None
            ),
            evidence_completeness=evidence_completeness,
            legacy_score_key_used=legacy_score_key_used,
        )

    @staticmethod
    def normalize_turn_number(
        raw_turn_number: int | None,
        fallback_turn_number: int = 1,
    ) -> int:
        if isinstance(raw_turn_number, int) and raw_turn_number >= 1:
            return raw_turn_number
        return max(1, fallback_turn_number)

    @classmethod
    def serialize_message(
        cls,
        message: ConversationMessage,
        fallback_turn_number: int = 1,
    ) -> dict[str, Any]:
        timestamp = getattr(message, "timestamp", None)
        return {
            "id": getattr(message, "id", None),
            "session_id": getattr(message, "session_id", None),
            "turn_number": cls.normalize_turn_number(
                getattr(message, "turn_number", None),
                fallback_turn_number,
            ),
            "role": getattr(message, "role", None),
            "content": getattr(message, "content", None),
            "audio_url": getattr(message, "audio_url", None),
            "timestamp": timestamp.isoformat() if timestamp else None,
            "duration_ms": getattr(message, "duration_ms", None),
            "fuzzy_words": getattr(message, "fuzzy_words", None),
            "transcript_metadata": getattr(message, "transcript_metadata", None),
            "sales_stage": getattr(message, "sales_stage", None),
            "score_snapshot": normalize_score_snapshot(
                getattr(message, "score_snapshot", None)
            ),
            "ai_feedback": getattr(message, "ai_feedback", None),
            "is_highlight": bool(getattr(message, "is_highlight", False)),
            "highlight_type": getattr(message, "highlight_type", None),
            "highlight_reason": getattr(message, "highlight_reason", None),
        }

    @classmethod
    def build_timeline_markers(
        cls,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        markers: list[dict[str, Any]] = []
        current_stage = None
        cumulative_ms = 0

        for message in messages:
            sales_stage = message.get("sales_stage")
            if sales_stage and sales_stage != current_stage:
                markers.append(
                    {
                        "timestamp_ms": cumulative_ms,
                        "type": "stage_change",
                        "label": STAGE_NAMES.get(str(sales_stage), str(sales_stage)),
                        "message_id": message.get("id"),
                        "highlight_type": None,
                    }
                )
                current_stage = sales_stage

            fuzzy_words = message.get("fuzzy_words")
            if isinstance(fuzzy_words, list):
                for fuzzy_word in fuzzy_words:
                    if not isinstance(fuzzy_word, dict):
                        continue
                    if fuzzy_word.get("severity") == "high":
                        matched_words = fuzzy_word.get("matched", [])
                        if not isinstance(matched_words, list):
                            matched_words = []
                        markers.append(
                            {
                                "timestamp_ms": cumulative_ms,
                                "type": "fuzzy_word",
                                "label": f"模糊词: {', '.join(str(word) for word in matched_words)}",
                                "message_id": message.get("id"),
                                "highlight_type": "bad",
                            }
                        )

            if message.get("is_highlight"):
                markers.append(
                    {
                        "timestamp_ms": cumulative_ms,
                        "type": "highlight",
                        "label": message.get("highlight_reason") or "关键时刻",
                        "message_id": message.get("id"),
                        "highlight_type": message.get("highlight_type"),
                    }
                )

            cumulative_ms += int(message.get("duration_ms") or 0)

        return markers

    @classmethod
    def build_stage_summary(
        cls,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        stage_data: dict[str, dict[str, Any]] = {}
        current_stage = None
        stage_start_ms = 0
        cumulative_ms = 0

        for message in messages:
            sales_stage = message.get("sales_stage")
            if sales_stage and sales_stage != current_stage:
                if current_stage:
                    stage_data.setdefault(current_stage, {"duration_ms": 0, "scores": []})
                    stage_data[current_stage]["duration_ms"] += cumulative_ms - stage_start_ms

                current_stage = str(sales_stage)
                stage_start_ms = cumulative_ms

            score_snapshot = message.get("score_snapshot")
            if current_stage and isinstance(score_snapshot, dict):
                overall_score = score_snapshot.get("overall_score")
                if isinstance(overall_score, (int, float)):
                    stage_data.setdefault(current_stage, {"duration_ms": 0, "scores": []})
                    stage_data[current_stage]["scores"].append(float(overall_score))

            cumulative_ms += int(message.get("duration_ms") or 0)

        if current_stage:
            stage_data.setdefault(current_stage, {"duration_ms": 0, "scores": []})
            stage_data[current_stage]["duration_ms"] += cumulative_ms - stage_start_ms

        summary: list[dict[str, Any]] = []
        for stage in STAGE_SEQUENCE:
            if stage not in stage_data:
                continue
            scores = stage_data[stage]["scores"]
            average_score = int(round(sum(scores) / len(scores))) if scores else 0
            summary.append(
                {
                    "stage": stage,
                    "duration_ms": int(stage_data[stage]["duration_ms"]),
                    "score": average_score,
                }
            )
        return summary

    @staticmethod
    def calculate_total_duration(messages: list[dict[str, Any]]) -> int:
        return sum(int(message.get("duration_ms") or 0) for message in messages)

    @classmethod
    def _resolve_score_triplet(
        cls,
        session: PracticeSession,
        messages: list[dict[str, Any]],
    ) -> tuple[float, float, float]:
        latest_snapshot = cls._get_latest_score_snapshot(messages)

        def _fallback_from_snapshot(*keys: str) -> float:
            if not isinstance(latest_snapshot, dict):
                return 0.0
            overall_score = latest_snapshot.get("overall_score")
            try:
                overall_score_value = float(overall_score or 0.0)
            except (TypeError, ValueError):
                overall_score_value = 0.0
            dimension_scores = latest_snapshot.get("dimension_scores")
            if not isinstance(dimension_scores, dict):
                dimension_scores = {}
            for key in keys:
                value = dimension_scores.get(key)
                if isinstance(value, (int, float)):
                    return max(0.0, min(100.0, float(value)))
            return max(0.0, min(100.0, overall_score_value))

        logic_score = cls._coerce_score(getattr(session, "logic_score", None))
        accuracy_score = cls._coerce_score(getattr(session, "accuracy_score", None))
        completeness_score = cls._coerce_score(getattr(session, "completeness_score", None))

        if logic_score is None:
            logic_score = _fallback_from_snapshot("专业度", "professional")
        if accuracy_score is None:
            accuracy_score = _fallback_from_snapshot("沟通技巧", "communication")
        if completeness_score is None:
            completeness_score = _fallback_from_snapshot("销售流程", "discovery", "closing")

        return logic_score, accuracy_score, completeness_score

    @staticmethod
    def _coerce_score(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _get_latest_score_snapshot(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
        for message in reversed(messages):
            snapshot = message.get("score_snapshot")
            if isinstance(snapshot, dict):
                return snapshot
        return None

    @classmethod
    def _build_evidence_completeness(
        cls,
        *,
        session: PracticeSession,
        messages: list[dict[str, Any]],
        snapshot: dict[str, Any],
        legacy_score_key_used: bool,
    ) -> dict[str, Any]:
        message_count = len(messages)
        message_analysis = sum(
            1
            for message in messages
            if any(
                message.get(field) is not None
                for field in (
                    "fuzzy_words",
                    "transcript_metadata",
                    "sales_stage",
                    "score_snapshot",
                    "ai_feedback",
                )
            )
        )
        message_scores = sum(
            1
            for message in messages
            if isinstance(message.get("score_snapshot"), dict)
            and message["score_snapshot"].get("overall_score") is not None
        )
        stage_evidence = sum(1 for message in messages if message.get("sales_stage"))
        session_scores = all(
            getattr(session, attr, None) is not None
            for attr in ("logic_score", "accuracy_score", "completeness_score")
        )
        snapshot_complete = all(
            key in snapshot
            for key in (
                "pass_flags",
                "overall_result",
                "main_issue",
                "next_goal",
                "evaluable",
                "not_evaluable_reason",
            )
        )

        missing_fields: list[str] = []
        if not session_scores:
            missing_fields.append("session_scores")
        if not snapshot_complete:
            missing_fields.append("effectiveness_snapshot")
        if message_count > 0 and message_scores == 0:
            missing_fields.append("message_scores")
        if message_count > 0 and stage_evidence == 0:
            missing_fields.append("stage_evidence")

        return {
            "complete": not missing_fields,
            "session_scores": session_scores,
            "effectiveness_snapshot": snapshot_complete,
            "message_count": message_count,
            "message_analysis": message_analysis,
            "message_scores": message_scores,
            "stage_evidence": stage_evidence,
            "legacy_score_key_used": legacy_score_key_used,
            "missing_fields": missing_fields,
        }


def _coerce_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _duration_seconds_between(
    start_time: datetime | None,
    end_time: datetime | None,
) -> int | None:
    if start_time is None or end_time is None:
        return None
    start_time_utc = _coerce_utc_timestamp(start_time)
    end_time_utc = _coerce_utc_timestamp(end_time)
    return max(0, int((end_time_utc - start_time_utc).total_seconds()))


def derive_effectiveness_metrics(
    session: PracticeSession,
    *,
    resolved_scores: tuple[float, float, float] | None = None,
) -> tuple[dict[str, Any], bool, bool, str | None]:
    if resolved_scores is None:
        logic = float(getattr(session, "logic_score", None) or 0.0)
        accuracy = float(getattr(session, "accuracy_score", None) or 0.0)
        completeness = float(getattr(session, "completeness_score", None) or 0.0)
    else:
        logic, accuracy, completeness = resolved_scores

    duration_seconds = int(getattr(session, "total_duration_seconds", None) or 0)
    if (
        duration_seconds <= 0
        and getattr(session, "start_time", None) is not None
        and getattr(session, "end_time", None) is not None
    ):
        derived_duration_seconds = _duration_seconds_between(
            getattr(session, "start_time", None),
            getattr(session, "end_time", None),
        )
        if derived_duration_seconds is not None:
            duration_seconds = derived_duration_seconds

    has_scores = any(score > 0 for score in (logic, accuracy, completeness))
    evaluable = has_scores and duration_seconds > 0
    not_evaluable_reason = None if evaluable else "INSUFFICIENT_SESSION_METRICS"
    metrics = {
        "continuous_speech_seconds": float(
            max(duration_seconds, int((logic + completeness) * 0.9))
        ),
        "filler_rate_per_100_words": round(
            max(0.0, min(30.0, (100.0 - logic) / 4.0)),
            2,
        ),
        "offtopic_turn_count": float(max(0, round((100.0 - accuracy) / 25.0))),
        "offtopic_max_streak": float(2 if accuracy < 55 else (1 if accuracy < 80 else 0)),
        "structure_coverage": round(max(0.0, min(1.0, completeness / 100.0)), 4),
    }
    overall_score = (logic + accuracy + completeness) / 3.0
    main_capability_passed = overall_score >= 70.0
    return metrics, main_capability_passed, evaluable, not_evaluable_reason


def ensure_effectiveness_snapshot(
    session: PracticeSession,
    *,
    resolved_scores: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    existing_snapshot = getattr(session, "effectiveness_snapshot", None)
    if isinstance(existing_snapshot, dict) and existing_snapshot:
        has_required_keys = all(
            key in existing_snapshot
            for key in (
                "pass_flags",
                "overall_result",
                "main_issue",
                "next_goal",
                "evaluable",
                "not_evaluable_reason",
            )
        )
        if has_required_keys:
            return existing_snapshot

        fallback_metrics, fallback_main_passed, fallback_evaluable, fallback_reason = (
            derive_effectiveness_metrics(session, resolved_scores=resolved_scores)
        )
        metrics = existing_snapshot.get("metrics")
        if not isinstance(metrics, dict):
            metrics = fallback_metrics
        else:
            filler_rate_raw = metrics.get(
                "filler_rate_per_100_words",
                fallback_metrics.get("filler_rate_per_100_words", 0.0),
            )
            try:
                filler_rate = float(filler_rate_raw)
            except (TypeError, ValueError):
                filler_rate = float(
                    fallback_metrics.get("filler_rate_per_100_words", 0.0)
                )
            metrics = {
                **metrics,
                "filler_rate_per_100_words": filler_rate,
            }
        main_capability_passed = existing_snapshot.get("main_capability_passed")
        if not isinstance(main_capability_passed, bool):
            main_capability_passed = fallback_main_passed
        evaluable = existing_snapshot.get("evaluable")
        if not isinstance(evaluable, bool):
            evaluable = fallback_evaluable
        not_evaluable_reason = existing_snapshot.get("not_evaluable_reason")
        if not isinstance(not_evaluable_reason, str):
            not_evaluable_reason = fallback_reason

        merged_snapshot = {
            **existing_snapshot,
            **evaluate_effectiveness_snapshot(
                metrics=metrics,
                main_capability_passed=main_capability_passed,
                evaluable=evaluable,
                not_evaluable_reason=not_evaluable_reason,
            ),
        }
        session.effectiveness_snapshot = merged_snapshot
        return merged_snapshot

    metrics, main_capability_passed, evaluable, not_evaluable_reason = (
        derive_effectiveness_metrics(session, resolved_scores=resolved_scores)
    )
    snapshot = evaluate_effectiveness_snapshot(
        metrics=metrics,
        main_capability_passed=main_capability_passed,
        evaluable=evaluable,
        not_evaluable_reason=not_evaluable_reason,
    )
    session.effectiveness_snapshot = snapshot
    return snapshot


def session_has_persisted_scores(session: PracticeSession) -> bool:
    return all(
        getattr(session, attr, None) is not None
        for attr in ("logic_score", "accuracy_score", "completeness_score")
    )
