"""
Manager intervention result resolution helpers for supervisor workflow reads.

Keeps the latest-evaluable-after-creation rule explicit so HistoryService and other
admin readers can reuse one truth for intervention outcome semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from common.db.models import ManagerIntervention, SessionStatus

if TYPE_CHECKING:
    from common.analytics.history_service import HistorySessionSummary

INTERVENTION_ISSUE_FAMILY_ALIASES = {
    "evidence_gap": "evidence_gap",
    "objection_response": "objection_response",
    "objection_handling_gap": "objection_response",
    "value_expression": "value_expression",
    "value_translation_gap": "value_expression",
    "structure_gap": "structure_gap",
}


@dataclass(slots=True)
class ManagerInterventionResultSummary:
    """Latest meaningful completed-session outcome for one manager intervention."""

    intervention_id: str
    issue_family: str
    note: str | None
    created_at: datetime
    session_id: str | None
    session_start_time: datetime | None
    status: str
    reason: str
    summary: str
    overall_result: str | None
    evaluable: bool | None
    not_evaluable_reason: str | None
    main_issue: dict[str, Any] | None
    next_goal: dict[str, Any] | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "issue_family": self.issue_family,
            "note": self.note,
            "created_at": self.created_at.isoformat(),
            "session_id": self.session_id,
            "session_start_time": (
                self.session_start_time.isoformat()
                if self.session_start_time is not None
                else None
            ),
            "status": self.status,
            "reason": self.reason,
            "summary": self.summary,
            "overall_result": self.overall_result,
            "evaluable": self.evaluable,
            "not_evaluable_reason": self.not_evaluable_reason,
            "main_issue": self.main_issue,
            "next_goal": self.next_goal,
        }


class ManagerInterventionResultResolver:
    """Resolve supervisor intervention outcomes from completed-session summaries."""

    @staticmethod
    def normalize_issue_family(issue_family: str | None) -> str | None:
        if not isinstance(issue_family, str):
            return None
        cleaned = issue_family.strip()
        if not cleaned:
            return None
        return INTERVENTION_ISSUE_FAMILY_ALIASES.get(cleaned, cleaned)

    @classmethod
    def resolve_summary_issue_family(
        cls,
        summary: HistorySessionSummary,
    ) -> str | None:
        main_issue = (
            summary.main_issue if isinstance(summary.main_issue, dict) else None
        )
        issue_type = (
            main_issue.get("issue_type") if isinstance(main_issue, dict) else None
        )
        if not isinstance(issue_type, str) or not issue_type.strip():
            return None
        return cls.normalize_issue_family(issue_type)

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @classmethod
    def _build_pending_result(
        cls,
        intervention: ManagerIntervention,
    ) -> ManagerInterventionResultSummary:
        return ManagerInterventionResultSummary(
            intervention_id=str(intervention.intervention_id),
            issue_family=str(intervention.issue_family),
            note=getattr(intervention, "note", None),
            created_at=cast(datetime, intervention.created_at),
            session_id=None,
            session_start_time=None,
            status="pending",
            reason="no_completed_session_after_intervention",
            summary="主管重点建立后，还没有新的已完成训练可用于判断结果。",
            overall_result=None,
            evaluable=None,
            not_evaluable_reason=None,
            main_issue=None,
            next_goal=None,
        )

    @classmethod
    def _build_completed_result(
        cls,
        intervention: ManagerIntervention,
        summary: HistorySessionSummary,
    ) -> ManagerInterventionResultSummary:
        normalized_target_family = cls.normalize_issue_family(
            getattr(intervention, "issue_family", None)
        )
        observed_issue_family = cls.resolve_summary_issue_family(summary)

        if summary.evaluable is False:
            status = "not_evaluable"
            reason = "session_not_evaluable"
            summary_text = (
                "最近一次已完成训练证据不足，暂时还不能判断这个主管重点是否改善。"
            )
        elif summary.overall_result in {"pass", "strong_pass"}:
            status = "improved"
            reason = "session_passed"
            summary_text = "最近一次可评估训练已通过，这个主管重点不再阻塞结果。"
        elif (
            normalized_target_family is not None
            and observed_issue_family is not None
            and observed_issue_family != normalized_target_family
        ):
            status = "improved"
            reason = "issue_family_shifted"
            summary_text = (
                "最近一次可评估训练的主问题已转向其他家族，说明这个主管重点已有改善。"
            )
        else:
            status = "still_blocked"
            reason = "same_issue_family_still_primary"
            summary_text = "最近一次可评估训练里，这个主管重点仍是当前主问题。"

        return ManagerInterventionResultSummary(
            intervention_id=str(intervention.intervention_id),
            issue_family=str(intervention.issue_family),
            note=getattr(intervention, "note", None),
            created_at=cast(datetime, intervention.created_at),
            session_id=summary.session_id,
            session_start_time=summary.start_time,
            status=status,
            reason=reason,
            summary=summary_text,
            overall_result=summary.overall_result,
            evaluable=summary.evaluable,
            not_evaluable_reason=summary.not_evaluable_reason,
            main_issue=(
                dict(summary.main_issue)
                if isinstance(summary.main_issue, dict)
                else None
            ),
            next_goal=(
                dict(summary.next_goal) if isinstance(summary.next_goal, dict) else None
            ),
        )

    @classmethod
    def build_results(
        cls,
        summaries: list[HistorySessionSummary],
        interventions: list[ManagerIntervention],
    ) -> list[ManagerInterventionResultSummary]:
        completed_summaries = sorted(
            (
                summary
                for summary in summaries
                if summary.status == SessionStatus.COMPLETED.value
            ),
            key=lambda summary: cls._normalize_timestamp(summary.start_time),
        )

        results: list[ManagerInterventionResultSummary] = []
        for intervention in sorted(
            interventions,
            key=lambda item: (item.created_at, item.intervention_id),
            reverse=True,
        ):
            intervention_created_at = cls._normalize_timestamp(
                cast(datetime, intervention.created_at)
            )
            later_completed = [
                summary
                for summary in completed_summaries
                if cls._normalize_timestamp(summary.start_time)
                >= intervention_created_at
            ]
            latest_evaluable = next(
                (
                    summary
                    for summary in reversed(later_completed)
                    if summary.evaluable is True
                ),
                None,
            )
            if latest_evaluable is not None:
                results.append(
                    cls._build_completed_result(intervention, latest_evaluable)
                )
                continue
            if later_completed:
                results.append(
                    cls._build_completed_result(intervention, later_completed[-1])
                )
                continue
            results.append(cls._build_pending_result(intervention))

        return results

    @classmethod
    def build_payloads(
        cls,
        summaries: list[HistorySessionSummary],
        interventions: list[ManagerIntervention],
    ) -> list[dict[str, Any]]:
        return [
            item.to_payload() for item in cls.build_results(summaries, interventions)
        ]


manager_intervention_result_resolver = ManagerInterventionResultResolver()
