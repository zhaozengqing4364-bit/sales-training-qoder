from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.db.models import PracticeSession, SessionStatus, TrainingReportSnapshot
from common.recommendations.next_practice import NextPracticeRecommendationService
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import CurriculumPlanSchema


@dataclass(frozen=True)
class LearningPathRecommendationReason:
    source_report_id: str
    dimension_name: str
    score: float
    recommended_template_id: str
    reason: str


DIMENSION_TEMPLATE_HINTS: dict[str, tuple[str, ...]] = {
    "product_knowledge": ("product", "knowledge", "产品", "证据"),
    "objection_handling": ("objection", "异议", "顾虑"),
    "value_logic": ("value", "logic", "价值", "逻辑"),
}


class LearningPathService:
    def __init__(
        self,
        db: AsyncSession | None = None,
        *,
        recommendation_service: Any | None = None,
    ) -> None:
        self.db = db
        self.recommendation_service = recommendation_service or NextPracticeRecommendationService()

    async def build_for_user(self, user_id: str, *, lookback: int = 3) -> dict[str, Any]:
        if self.db is None:
            raise RuntimeError("LearningPathService.build_for_user requires db")
        sessions = await self._recent_sessions(user_id=user_id, lookback=lookback)
        templates = await self._published_templates()
        return await self.build_from_evidence(
            user_id=user_id,
            sessions=sessions,
            templates=templates,
            lookback=lookback,
        )

    async def next_task_for_user(self, user_id: str, *, lookback: int = 3) -> dict[str, Any]:
        path = await self.build_for_user(user_id, lookback=lookback)
        return path["next_task"]

    async def build_from_evidence(
        self,
        *,
        user_id: str,
        sessions: list[PracticeSession],
        templates: list[PracticeTemplate],
        lookback: int = 3,
    ) -> dict[str, Any]:
        recent_sessions = sorted(
            sessions,
            key=lambda item: getattr(item, "start_time", None) or "",
            reverse=True,
        )[:lookback]
        if not recent_sessions:
            return self._role_default_path(user_id=user_id, templates=templates)

        reasons_by_template: dict[str, LearningPathRecommendationReason] = {}
        recommendation_payloads: list[dict[str, Any]] = []
        for session in recent_sessions:
            report_weak_dimensions = self._weak_dimensions_from_session_reports(session)
            if not report_weak_dimensions:
                continue
            result = await self._build_recommendation_for_session(session)
            if not getattr(result, "is_success", False):
                continue
            payload = result.value
            if not isinstance(payload, dict):
                continue
            recommendation_payloads.append(payload)
            for weak_dimension in report_weak_dimensions:
                template = self._template_for_dimension(weak_dimension["dimension_name"], templates)
                if template is None:
                    continue
                template_id = str(template.template_id)
                candidate = LearningPathRecommendationReason(
                    source_report_id=weak_dimension["source_report_id"],
                    dimension_name=weak_dimension["dimension_name"],
                    score=weak_dimension["score"],
                    recommended_template_id=template_id,
                    reason=self._recommendation_reason(
                        payload=payload,
                        dimension_name=weak_dimension["dimension_name"],
                        score=weak_dimension["score"],
                    ),
                )
                existing = reasons_by_template.get(template_id)
                if existing is None or candidate.score < existing.score:
                    reasons_by_template[template_id] = candidate

        if not reasons_by_template:
            return self._role_default_path(user_id=user_id, templates=templates)

        reasons = sorted(reasons_by_template.values(), key=lambda item: item.score)
        recommended_template_ids = [reason.recommended_template_id for reason in reasons]
        stages = self._build_stages(templates=templates, completed_sessions=recent_sessions)
        next_template = self._template_by_id(templates, recommended_template_ids[0])
        next_payload = recommendation_payloads[0] if recommendation_payloads else {}
        next_task = self._next_task_payload(
            template=next_template,
            fallback_title=str(next_payload.get("title") or "继续训练"),
            primary_cta=str(next_payload.get("action_label") or "开始专项练习"),
            state=self._stage_state_for_template(stages, recommended_template_ids[0]),
            failure_reason=self._failure_reason_for_template(stages, recommended_template_ids[0]),
            reason=reasons[0].reason,
        )
        return {
            "user_id": user_id,
            "path_type": "weakness_driven",
            "recommended_template_ids": recommended_template_ids,
            "recommendation_reasons": [reason.__dict__ for reason in reasons],
            "next_task": next_task,
            "stages": stages,
            "generated_at": self._generated_at(),
        }

    async def _build_recommendation_for_session(self, session: PracticeSession):
        if self.db is None:
            return self.recommendation_service.build_for_session(session)
        return await self.recommendation_service.build_for_session_with_db(
            db=self.db,
            session=session,
        )

    async def _recent_sessions(self, *, user_id: str, lookback: int) -> list[PracticeSession]:
        assert self.db is not None
        result = await self.db.execute(
            select(PracticeSession)
            .options(selectinload(PracticeSession.report_snapshots))
            .where(PracticeSession.user_id == user_id)
            .where(PracticeSession.status == SessionStatus.COMPLETED.value)
            .order_by(PracticeSession.start_time.desc())
            .limit(lookback)
        )
        return list(result.scalars().all())

    async def _published_templates(self) -> list[PracticeTemplate]:
        assert self.db is not None
        result = await self.db.execute(
            select(PracticeTemplate)
            .where(PracticeTemplate.status == "published")
            .order_by(PracticeTemplate.updated_at.desc())
        )
        return list(result.scalars().all())

    def _role_default_path(self, *, user_id: str, templates: list[PracticeTemplate]) -> dict[str, Any]:
        stages = self._build_stages(templates=templates, completed_sessions=[])
        template = templates[0] if templates else None
        template_id = str(template.template_id) if template is not None else "role-default-sales"
        return {
            "user_id": user_id,
            "path_type": "role_default",
            "recommended_template_ids": [template_id] if template is not None else [],
            "recommendation_reasons": [],
            "next_task": self._next_task_payload(
                template=template,
                fallback_title="销售基础训练",
                primary_cta="开始默认路径",
                state="available",
                failure_reason=None,
                reason="暂无足够报告证据，先从默认路径开始。",
            ),
            "stages": stages,
            "generated_at": self._generated_at(),
        }

    @staticmethod
    def _template_by_id(templates: list[PracticeTemplate], template_id: str) -> PracticeTemplate | None:
        for template in templates:
            if str(template.template_id) == template_id:
                return template
        return None

    def _template_for_dimension(
        self, dimension_name: str, templates: list[PracticeTemplate]
    ) -> PracticeTemplate | None:
        hints = DIMENSION_TEMPLATE_HINTS.get(dimension_name, (dimension_name,))
        for template in templates:
            haystack = " ".join(
                str(value or "").lower()
                for value in (
                    template.template_id,
                    template.name,
                    template.description,
                    template.curriculum_plan,
                )
            )
            if any(hint.lower() in haystack for hint in hints):
                return template
        return templates[0] if templates else None

    def _weak_dimensions_from_session_reports(
        self, session: PracticeSession, *, threshold: float = 5.0
    ) -> list[dict[str, Any]]:
        snapshots = getattr(session, "report_snapshots", None) or []
        weak_dimensions: list[dict[str, Any]] = []
        if snapshots:
            for snapshot in snapshots:
                if not isinstance(snapshot, TrainingReportSnapshot):
                    continue
                weak_dimensions.extend(
                    self._weak_dimensions_from_report_payload(
                        report_payload=snapshot.report_payload,
                        source_report_id=str(snapshot.snapshot_id),
                    )
                )
        if weak_dimensions:
            return sorted(weak_dimensions, key=lambda item: item["score"])

        fallback_dimension = self._session_weak_dimension(session)
        if fallback_dimension is None:
            return []
        dimension_name, score = fallback_dimension
        if score >= threshold:
            return []
        return [
            {
                "source_report_id": str(session.session_id),
                "dimension_name": dimension_name,
                "score": score,
            }
        ]

    @staticmethod
    def _weak_dimensions_from_report_payload(
        *, report_payload: dict[str, Any], source_report_id: str, threshold: float = 5.0
    ) -> list[dict[str, Any]]:
        raw_dimensions = report_payload.get("dimensions")
        if isinstance(raw_dimensions, dict):
            items = raw_dimensions.items()
        elif isinstance(raw_dimensions, list):
            items = (
                (item.get("name") or item.get("dimension_name") or item.get("dimension_id"), item)
                for item in raw_dimensions
                if isinstance(item, dict)
            )
        else:
            items = []

        weak_dimensions: list[dict[str, Any]] = []
        for name, value in items:
            score: float | None = None
            if isinstance(value, dict):
                raw_score = value.get("score")
            else:
                raw_score = value
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = None
            if not name or score is None or score >= threshold:
                continue
            weak_dimensions.append(
                {
                    "source_report_id": source_report_id,
                    "dimension_name": str(name),
                    "score": score,
                }
            )
        return sorted(weak_dimensions, key=lambda item: item["score"])

    @staticmethod
    def _session_weak_dimension(session: PracticeSession) -> tuple[str, float] | None:
        scores = {
            "product_knowledge": getattr(session, "accuracy_score", None),
            "objection_handling": getattr(session, "completeness_score", None),
            "value_logic": getattr(session, "logic_score", None),
        }
        parsed: dict[str, float] = {}
        for name, value in scores.items():
            if value is None:
                continue
            parsed[name] = float(value) / 10 if float(value) > 10 else float(value)
        if not parsed:
            return None
        return min(parsed.items(), key=lambda item: item[1])

    @staticmethod
    def _recommendation_reason(
        *, payload: dict[str, Any], dimension_name: str, score: float
    ) -> str:
        reason = payload.get("reason") or payload.get("explanation")
        if reason:
            return str(reason)
        return f"{dimension_name} 得分 {score:g}，建议专项练习。"

    def _build_stages(
        self,
        *,
        templates: list[PracticeTemplate],
        completed_sessions: list[PracticeSession],
    ) -> list[dict[str, Any]]:
        completed_template_ids = {
            str(session.practice_template_id)
            for session in completed_sessions
            if session.practice_template_id
            and str(session.status) == SessionStatus.COMPLETED.value
            and isinstance(session.effectiveness_snapshot, dict)
            and session.effectiveness_snapshot.get("evaluable") is True
        }
        stages: list[dict[str, Any]] = []
        for template in templates:
            plan = self._plan_for_template(template)
            if plan is None:
                stages.append(self._fallback_stage(template, completed_template_ids))
                continue
            for stage in sorted(plan.stages, key=lambda item: item.order):
                template_id = str(stage.template_ref.asset_id)
                prerequisite_keys = [item.template_stage_key for item in stage.prerequisites]
                prereqs_met = all(
                    self._stage_completed(prerequisite_key=key, stages=stages)
                    for key in prerequisite_keys
                )
                state = "completed" if template_id in completed_template_ids else "available" if prereqs_met else "locked"
                if state != "completed" and "review" in stage.template_stage_key.lower():
                    state = "pending_review"
                stages.append(
                    {
                        "template_stage_key": stage.template_stage_key,
                        "name": stage.name,
                        "state": state,
                        "prerequisites": [item.model_dump(mode="json") for item in stage.prerequisites],
                        "completion_policy": stage.completion_policy.model_dump(mode="json"),
                        "report_url": self._report_url_for_template(template_id, completed_sessions),
                        "failure_reason": self._failure_reason_for_stage(template_id, completed_sessions),
                        "result": self._stage_result_for_stage(
                            stage_key=stage.template_stage_key,
                            template_id=template_id,
                            sessions=completed_sessions,
                        ),
                        "template_id": template_id,
                    }
                )
        return stages

    @staticmethod
    def _plan_for_template(template: PracticeTemplate) -> CurriculumPlanSchema | None:
        if not isinstance(template.curriculum_plan, dict):
            return None
        return CurriculumPlanSchema.model_validate(template.curriculum_plan)

    @staticmethod
    def _fallback_stage(
        template: PracticeTemplate, completed_template_ids: set[str]
    ) -> dict[str, Any]:
        template_id = str(template.template_id)
        return {
            "template_stage_key": f"template_stage_{template_id}",
            "name": str(template.name),
            "state": "completed" if template_id in completed_template_ids else "available",
            "prerequisites": [],
            "completion_policy": {
                "min_score": 7,
                "min_rounds": 1,
                "max_duration_seconds": int(template.max_stage_duration_seconds or 600),
            },
            "report_url": None,
            "failure_reason": None,
            "result": None,
            "template_id": template_id,
        }

    @staticmethod
    def _stage_completed(*, prerequisite_key: str, stages: list[dict[str, Any]]) -> bool:
        return any(
            stage["template_stage_key"] == prerequisite_key and stage["state"] == "completed"
            for stage in stages
        )

    @staticmethod
    def _report_url_for_template(
        template_id: str, sessions: list[PracticeSession]
    ) -> str | None:
        for session in sessions:
            if str(session.practice_template_id) == template_id:
                return f"/practice/{session.session_id}/report"
        return None

    @staticmethod
    def _failure_reason_for_stage(
        template_id: str, sessions: list[PracticeSession]
    ) -> str | None:
        for session in sessions:
            if str(session.practice_template_id) != template_id:
                continue
            snapshot = session.effectiveness_snapshot if isinstance(session.effectiveness_snapshot, dict) else {}
            reason = snapshot.get("failure_reason") or snapshot.get("non_evaluable_reason")
            if reason:
                return str(reason)
        return None

    @staticmethod
    def _stage_result_for_stage(
        *, stage_key: str, template_id: str, sessions: list[PracticeSession]
    ) -> dict[str, Any] | None:
        for session in sessions:
            if str(session.practice_template_id) != template_id:
                continue
            runtime_state = session.runtime_state if isinstance(session.runtime_state, dict) else {}
            progress = runtime_state.get("template_stage_context")
            if isinstance(progress, dict):
                stage_progress = progress.get("template_stage_progress")
                if isinstance(stage_progress, dict):
                    keyed_progress = stage_progress.get(stage_key) or stage_progress.get(template_id)
                    if isinstance(keyed_progress, dict):
                        return dict(keyed_progress)
                    return dict(stage_progress)
            snapshots = getattr(session, "report_snapshots", None) or []
            for snapshot in snapshots:
                if not isinstance(snapshot, TrainingReportSnapshot):
                    continue
                payload = snapshot.report_payload if isinstance(snapshot.report_payload, dict) else {}
                lineage = payload.get("lineage")
                if not isinstance(lineage, dict):
                    continue
                stage_snapshots = lineage.get("stage_snapshots")
                if isinstance(stage_snapshots, dict):
                    result = stage_snapshots.get(stage_key) or stage_snapshots.get(template_id)
                    if isinstance(result, dict):
                        return dict(result)
        return None

    @staticmethod
    def _stage_state_for_template(stages: list[dict[str, Any]], template_id: str) -> str:
        for stage in stages:
            if str(stage.get("template_id")) == template_id:
                return str(stage["state"])
        return "available"

    @staticmethod
    def _failure_reason_for_template(stages: list[dict[str, Any]], template_id: str) -> str | None:
        for stage in stages:
            if str(stage.get("template_id")) == template_id:
                return stage.get("failure_reason")
        return None

    @staticmethod
    def _generated_at() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _next_task_payload(
        *,
        template: PracticeTemplate | None,
        fallback_title: str,
        primary_cta: str,
        state: str,
        failure_reason: str | None,
        reason: str,
    ) -> dict[str, Any]:
        title = str(template.name) if template is not None else fallback_title
        duration = None
        if template is not None and template.max_stage_duration_seconds:
            duration = max(1, int(template.max_stage_duration_seconds) // 60)
        return {
            "title": title,
            "state": state,
            "primary_cta": primary_cta,
            "reason": reason,
            "estimated_duration_minutes": duration,
            "failure_reason": failure_reason,
            "retry_action": "retry_current" if failure_reason else None,
        }
