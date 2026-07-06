from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.config import settings
from common.db.models import (
    PracticeSession,
    RetrainingTask,
    SessionStatus,
    SupervisorReview,
    TrainingReportSnapshot,
)
from common.error_handling.result import Result
from common.recommendations.next_practice import NextPracticeRecommendationService
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import CurriculumPlanSchema, CurriculumPlanStage
from curriculum_practice.services.examiner_report_service import (
    examiner_report_frontend_path,
)
from curriculum_practice.services.learning_progress_service import (
    LearningProgressService,
)
from curriculum_practice.services.orm_payload_typing import orm_dict


@dataclass(frozen=True)
class LearningPathRecommendationReason:
    source_report_id: str
    dimension_name: str
    score: float
    recommended_template_id: str
    reason: str


class _ExamAttemptStats(TypedDict):
    best_score: float | None
    lowest_score: float | None
    latest_score: float | None
    attempt_count: int


class _ExamReportMetrics(TypedDict):
    score: float
    passed: bool | None
    answered_count: int


class _StageCompletionEvidence(TypedDict):
    practice_template_ids: set[str]
    learning_content_ids: set[str]
    learning_content_participated_ids: set[str]
    examiner_agent_ids: set[str]
    exam_sessions_by_agent_id: dict[str, PracticeSession]
    exam_latest_session_by_agent_id: dict[str, PracticeSession]
    exam_stats_by_agent_id: dict[str, _ExamAttemptStats]


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
        path = await self.build_from_evidence(
            user_id=user_id,
            sessions=sessions,
            templates=templates,
            lookback=lookback,
        )
        study_task = await self._study_next_task(user_id=user_id)
        if study_task is not None:
            path["next_task"] = study_task
        return path

    async def next_task_for_user(self, user_id: str, *, lookback: int = 3) -> dict[str, Any]:
        path = await self.build_for_user(user_id, lookback=lookback)
        next_task = path.get("next_task")
        return dict(next_task) if isinstance(next_task, dict) else {}

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
            return await self._role_default_path(user_id=user_id, templates=templates)

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
            return await self._role_default_path(user_id=user_id, templates=templates)

        reasons = sorted(reasons_by_template.values(), key=lambda item: item.score)
        recommended_template_ids = [reason.recommended_template_id for reason in reasons]
        review_outcomes = await self._review_outcomes_for_sessions(recent_sessions)
        stages = await self._build_stages(
            user_id=user_id,
            templates=templates,
            completed_sessions=recent_sessions,
            review_outcomes=review_outcomes,
        )
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

    async def _build_recommendation_for_session(
        self, session: PracticeSession
    ) -> Result[dict[str, Any]]:
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
            .options(
                selectinload(PracticeSession.report_snapshots),
                selectinload(PracticeSession.scenario),
            )
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

    async def _study_next_task(self, *, user_id: str) -> dict[str, Any] | None:
        assert self.db is not None
        result = await LearningProgressService(self.db).first_published_content_progress(
            user_id=user_id
        )
        if not result.is_success or result.value is None:
            return None
        content, progress = result.value
        return {
            "title": content.title,
            "state": progress.state,
            "primary_cta": progress.primary_cta,
            "reason": (
                "讲义已全部完成，可开始 AI 考核。"
                if progress.is_completed
                else "继续完成讲义学习，完成后可进入考试。"
            ),
            "estimated_duration_minutes": None,
            "failure_reason": None,
            "retry_action": None,
            "learning_content_id": str(content.learning_content_id),
        }

    async def _review_outcomes_for_sessions(
        self,
        sessions: list[PracticeSession],
    ) -> dict[str, str]:
        if self.db is None:
            return {}
        session_ids = [str(session.session_id) for session in sessions if session.session_id]
        if not session_ids:
            return {}
        reviews_result = await self.db.execute(
            select(SupervisorReview).where(SupervisorReview.session_id.in_(session_ids))
        )
        reviews = list(reviews_result.scalars().all())
        if not reviews:
            return {}
        retraining_result = await self.db.execute(
            select(RetrainingTask.source_review_id).where(
                RetrainingTask.source_review_id.in_(
                    [str(review.review_id) for review in reviews]
                ),
                RetrainingTask.status.in_(("todo", "in_progress")),
            )
        )
        open_retraining_review_ids = {
            str(review_id) for review_id in retraining_result.scalars().all()
        }
        outcomes: dict[str, str] = {}
        for review in reviews:
            session_id = str(review.session_id)
            if (
                str(review.review_id) in open_retraining_review_ids
                or str(review.decision) == "needs_retraining"
                or bool(review.required_retraining)
            ):
                outcomes[session_id] = "retraining_required"
            elif str(review.decision) == "rejected":
                outcomes[session_id] = "failed"
            elif str(review.decision) == "approved":
                outcomes[session_id] = "completed"
            else:
                outcomes[session_id] = "pending_review"
        return outcomes

    async def _role_default_path(self, *, user_id: str, templates: list[PracticeTemplate]) -> dict[str, Any]:
        stages = await self._build_stages(
            user_id=user_id,
            templates=templates,
            completed_sessions=[],
            review_outcomes={},
        )
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
                        report_payload=orm_dict(snapshot.report_payload),
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
        items: Iterable[tuple[object, object]]
        if isinstance(raw_dimensions, dict):
            items = raw_dimensions.items()
        elif isinstance(raw_dimensions, list):
            items = (
                (item.get("name") or item.get("dimension_name") or item.get("dimension_id"), item)
                for item in raw_dimensions
                if isinstance(item, dict)
            )
        else:
            items = ()

        weak_dimensions: list[dict[str, Any]] = []
        for name, value in items:
            score: float | None = None
            if isinstance(value, dict):
                raw_score = value.get("score")
            else:
                raw_score = value
            if raw_score is None:
                continue
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
            numeric_score = float(value)
            parsed[name] = numeric_score / 10 if numeric_score > 10 else numeric_score
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

    async def _build_stages(
        self,
        *,
        user_id: str,
        templates: list[PracticeTemplate],
        completed_sessions: list[PracticeSession],
        review_outcomes: dict[str, str],
    ) -> list[dict[str, Any]]:
        evidence = await self._load_stage_completion_evidence(
            user_id=user_id,
            templates=templates,
            completed_sessions=completed_sessions,
        )
        stages: list[dict[str, Any]] = []
        for template in templates:
            plan = self._plan_for_template(template)
            if plan is None:
                stages.append(
                    self._fallback_stage(template, evidence["practice_template_ids"])
                )
                continue
            for stage in sorted(plan.stages, key=lambda item: item.order):
                asset_id = str(stage.template_ref.asset_id)
                prerequisite_keys = [item.template_stage_key for item in stage.prerequisites]
                prereqs_met = all(
                    self._stage_prerequisite_satisfied(
                        prerequisite_key=key,
                        stages=stages,
                        evidence=evidence,
                    )
                    for key in prerequisite_keys
                )
                state = self._base_stage_state(
                    stage=stage,
                    evidence=evidence,
                    prereqs_met=prereqs_met,
                )
                if "review" in stage.template_stage_key.lower():
                    state = self._review_stage_state(
                        default_state=state,
                        template_id=asset_id,
                        sessions=completed_sessions,
                        review_outcomes=review_outcomes,
                    )
                stages.append(
                    {
                        "template_stage_key": stage.template_stage_key,
                        "name": stage.name,
                        "state": state,
                        "stage_type": stage.stage_type,
                        "asset_type": stage.template_ref.asset_type,
                        "asset_id": stage.template_ref.asset_id,
                        "learning_content_id": (
                            str(stage.template_ref.asset_id)
                            if stage.stage_type == "study"
                            and stage.template_ref.asset_type == "learning_content"
                            else str(template.learning_content_id)
                            if stage.stage_type == "exam" and template.learning_content_id
                            else None
                        ),
                        "agent_id": (
                            str(template.agent_id)
                            if stage.stage_type == "practice" and template.agent_id
                            else None
                        ),
                        "prerequisites": [item.model_dump(mode="json") for item in stage.prerequisites],
                        "completion_policy": stage.completion_policy.model_dump(mode="json"),
                        "report_url": self._report_url_for_stage(
                            stage=stage,
                            evidence=evidence,
                            completed_sessions=completed_sessions,
                        ),
                        "failure_reason": self._failure_reason_for_stage(
                            asset_id, completed_sessions
                        ),
                        "result": self._stage_result_payload(
                            stage=stage,
                            evidence=evidence,
                            completed_sessions=completed_sessions,
                        ),
                        "template_id": asset_id,
                    }
                )
        return stages

    async def _load_stage_completion_evidence(
        self,
        *,
        user_id: str,
        templates: list[PracticeTemplate],
        completed_sessions: list[PracticeSession],
    ) -> _StageCompletionEvidence:
        if self.db is None:
            return self._completion_evidence_from_sessions(
                completed_sessions=completed_sessions,
            )

        practice_template_ids: set[str] = set()
        session_result = await self.db.execute(
            select(PracticeSession)
            .where(PracticeSession.user_id == user_id)
            .where(PracticeSession.status == SessionStatus.COMPLETED.value)
            .order_by(PracticeSession.start_time.desc())
        )
        all_completed_sessions = list(session_result.scalars().all())
        for session in all_completed_sessions:
            template_id = session.practice_template_id
            if not template_id:
                continue
            if self._is_curriculum_examiner_session(session):
                continue
            if not isinstance(session.effectiveness_snapshot, dict):
                continue
            if session.effectiveness_snapshot.get("evaluable") is not True:
                continue
            practice_template_ids.add(str(template_id))

        exam_aggregate = self._aggregate_exam_sessions(all_completed_sessions)
        examiner_agent_ids = set(exam_aggregate["exam_sessions_by_agent_id"].keys())
        exam_sessions_by_agent_id = exam_aggregate["exam_sessions_by_agent_id"]
        exam_latest_session_by_agent_id = exam_aggregate["exam_latest_session_by_agent_id"]
        exam_stats_by_agent_id = exam_aggregate["exam_stats_by_agent_id"]

        learning_content_ids: set[str] = set()
        learning_content_participated_ids: set[str] = set()
        content_ids: set[str] = set()
        for template in templates:
            if template.learning_content_id:
                content_ids.add(str(template.learning_content_id))
            plan = self._plan_for_template(template)
            if plan is None:
                continue
            for stage in plan.stages:
                if (
                    stage.stage_type == "study"
                    and stage.template_ref.asset_type == "learning_content"
                ):
                    content_ids.add(str(stage.template_ref.asset_id))

        progress_service = LearningProgressService(self.db)
        for content_id in content_ids:
            content_result = await progress_service.get_study_content(
                user_id=user_id,
                content_id=content_id,
            )
            if not content_result.is_success or content_result.value is None:
                continue
            progress = content_result.value.progress
            if progress.completed_chapter_ids:
                learning_content_participated_ids.add(content_id)
            if progress.is_completed:
                learning_content_ids.add(content_id)

        return {
            "practice_template_ids": practice_template_ids,
            "learning_content_ids": learning_content_ids,
            "learning_content_participated_ids": learning_content_participated_ids,
            "examiner_agent_ids": examiner_agent_ids,
            "exam_sessions_by_agent_id": exam_sessions_by_agent_id,
            "exam_latest_session_by_agent_id": exam_latest_session_by_agent_id,
            "exam_stats_by_agent_id": exam_stats_by_agent_id,
        }

    @staticmethod
    def _completion_evidence_from_sessions(
        *,
        completed_sessions: list[PracticeSession],
    ) -> _StageCompletionEvidence:
        practice_template_ids: set[str] = set()
        examiner_agent_ids: set[str] = set()
        exam_sessions_by_agent_id: dict[str, PracticeSession] = {}
        for session in completed_sessions:
            if str(session.status) != SessionStatus.COMPLETED.value:
                continue
            if LearningPathService._is_curriculum_examiner_session(session):
                agent_id = LearningPathService._examiner_agent_id_from_session(session)
                if agent_id and agent_id not in exam_sessions_by_agent_id:
                    exam_sessions_by_agent_id[agent_id] = session
                    examiner_agent_ids.add(agent_id)
                continue
            template_id = session.practice_template_id
            if not template_id:
                continue
            if not isinstance(session.effectiveness_snapshot, dict):
                continue
            if session.effectiveness_snapshot.get("evaluable") is not True:
                continue
            practice_template_ids.add(str(template_id))
        exam_aggregate = LearningPathService._aggregate_exam_sessions(completed_sessions)
        return {
            "practice_template_ids": practice_template_ids,
            "learning_content_ids": set(),
            "learning_content_participated_ids": set(),
            "examiner_agent_ids": set(exam_aggregate["exam_sessions_by_agent_id"].keys()),
            "exam_sessions_by_agent_id": exam_aggregate["exam_sessions_by_agent_id"],
            "exam_latest_session_by_agent_id": exam_aggregate[
                "exam_latest_session_by_agent_id"
            ],
            "exam_stats_by_agent_id": exam_aggregate["exam_stats_by_agent_id"],
        }

    @staticmethod
    def _aggregate_exam_sessions(
        sessions: list[PracticeSession],
    ) -> dict[str, Any]:
        by_agent: dict[str, list[PracticeSession]] = {}
        for session in sessions:
            if str(session.status) != SessionStatus.COMPLETED.value:
                continue
            if not LearningPathService._is_curriculum_examiner_session(session):
                continue
            agent_id = LearningPathService._examiner_agent_id_from_session(session)
            if not agent_id:
                continue
            by_agent.setdefault(agent_id, []).append(session)

        exam_sessions_by_agent_id: dict[str, PracticeSession] = {}
        exam_latest_session_by_agent_id: dict[str, PracticeSession] = {}
        exam_stats_by_agent_id: dict[str, _ExamAttemptStats] = {}
        for agent_id, agent_sessions in by_agent.items():
            ordered = sorted(
                agent_sessions,
                key=lambda item: getattr(item, "start_time", None) or "",
                reverse=True,
            )
            latest = ordered[0]
            exam_latest_session_by_agent_id[agent_id] = latest
            scores: list[float] = []
            for item in agent_sessions:
                metrics = LearningPathService._exam_report_metrics(item)
                if metrics is not None:
                    scores.append(metrics["score"])
            best_session = latest
            if scores:
                best_session = max(
                    agent_sessions,
                    key=lambda item: (
                        LearningPathService._exam_report_metrics(item) or {"score": -1.0}
                    )["score"],
                )
            exam_sessions_by_agent_id[agent_id] = best_session
            latest_metrics = LearningPathService._exam_report_metrics(latest)
            exam_stats_by_agent_id[agent_id] = {
                "best_score": max(scores) if scores else None,
                "lowest_score": min(scores) if scores else None,
                "latest_score": (
                    latest_metrics["score"] if latest_metrics is not None else None
                ),
                "attempt_count": len(agent_sessions),
            }
        return {
            "exam_sessions_by_agent_id": exam_sessions_by_agent_id,
            "exam_latest_session_by_agent_id": exam_latest_session_by_agent_id,
            "exam_stats_by_agent_id": exam_stats_by_agent_id,
        }

    @staticmethod
    def _exam_report_metrics(session: PracticeSession) -> _ExamReportMetrics | None:
        runtime_state: dict[str, Any] = orm_dict(session.runtime_state)
        report = runtime_state.get("examiner_report")
        if not isinstance(report, dict):
            return None
        try:
            score = float(report.get("overall_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        passed = report.get("passed")
        return {
            "score": score,
            "passed": passed if isinstance(passed, bool) else None,
            "answered_count": int(report.get("answered_count") or 0),
        }

    @staticmethod
    def _is_curriculum_examiner_session(session: PracticeSession) -> bool:
        snapshot = session.curriculum_snapshot
        return isinstance(snapshot, dict) and snapshot.get("kind") == "curriculum_examiner_session"

    @staticmethod
    def _examiner_agent_id_from_session(session: PracticeSession) -> str | None:
        snapshot = session.curriculum_snapshot
        if not isinstance(snapshot, dict):
            return None
        assets = snapshot.get("content_assets")
        if not isinstance(assets, list):
            return None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if asset.get("asset_type") != "examiner_agent":
                continue
            agent_id = str(asset.get("asset_id") or "").strip()
            if agent_id:
                return agent_id
        return None

    @staticmethod
    def _completion_policy_participation_unlock(completion_policy: dict[str, Any]) -> bool:
        if settings.LEARNING_PATH_PARTICIPATION_UNLOCK:
            return True
        try:
            min_score = float(completion_policy.get("min_score") or 0)
            min_rounds = int(completion_policy.get("min_rounds") or 0)
        except (TypeError, ValueError):
            return False
        return min_score <= 0 and min_rounds <= 0

    @staticmethod
    def _exam_report_passed(
        session: PracticeSession, *, completion_policy: dict[str, Any]
    ) -> bool:
        metrics = LearningPathService._exam_report_metrics(session)
        if metrics is None:
            return LearningPathService._completion_policy_participation_unlock(
                completion_policy
            )
        if LearningPathService._completion_policy_participation_unlock(completion_policy):
            return metrics["answered_count"] > 0 or metrics["score"] >= 0
        if metrics["passed"] is False:
            return False
        try:
            min_score = float(completion_policy.get("min_score") or 0)
        except (TypeError, ValueError):
            return True
        overall_score = float(metrics["score"])
        if min_score <= 10:
            return overall_score >= min_score * 10
        return overall_score >= min_score

    def _base_stage_state(
        self,
        *,
        stage: CurriculumPlanStage,
        evidence: _StageCompletionEvidence,
        prereqs_met: bool,
    ) -> str:
        asset_id = str(stage.template_ref.asset_id)
        asset_type = str(stage.template_ref.asset_type)
        completion_policy = stage.completion_policy.model_dump(mode="json")

        if stage.stage_type == "study" and asset_type == "learning_content":
            if asset_id in evidence["learning_content_ids"]:
                return "completed"
        elif stage.stage_type == "exam" and asset_type == "examiner_agent":
            exam_session = evidence["exam_sessions_by_agent_id"].get(asset_id)
            if asset_id in evidence["examiner_agent_ids"] and exam_session is not None:
                if self._exam_report_passed(exam_session, completion_policy=completion_policy):
                    return "completed"
                return "failed"
        elif asset_type in {"practice_template"} or stage.stage_type == "practice":
            if asset_id in evidence["practice_template_ids"]:
                return "completed"

        return "available" if prereqs_met else "locked"

    @staticmethod
    def _report_url_for_stage(
        *,
        stage: CurriculumPlanStage,
        evidence: _StageCompletionEvidence,
        completed_sessions: list[PracticeSession],
    ) -> str | None:
        asset_id = str(stage.template_ref.asset_id)
        if stage.stage_type == "exam" and stage.template_ref.asset_type == "examiner_agent":
            exam_session = evidence["exam_latest_session_by_agent_id"].get(asset_id)
            if exam_session is None:
                exam_session = evidence["exam_sessions_by_agent_id"].get(asset_id)
            if exam_session is not None:
                return str(examiner_report_frontend_path(str(exam_session.session_id)))
        return LearningPathService._report_url_for_template(asset_id, completed_sessions)

    @staticmethod
    def _stage_result_payload(
        *,
        stage: CurriculumPlanStage,
        evidence: _StageCompletionEvidence,
        completed_sessions: list[PracticeSession],
    ) -> dict[str, Any] | None:
        asset_id = str(stage.template_ref.asset_id)
        if stage.stage_type == "study" and stage.template_ref.asset_type == "learning_content":
            if asset_id not in evidence["learning_content_ids"]:
                return None
            return {"result": "completed"}

        if stage.stage_type == "exam" and stage.template_ref.asset_type == "examiner_agent":
            exam_session = evidence["exam_sessions_by_agent_id"].get(asset_id)
            if exam_session is None:
                return None
            completion_policy = stage.completion_policy.model_dump(mode="json")
            passed = LearningPathService._exam_report_passed(
                exam_session,
                completion_policy=completion_policy,
            )
            stats = evidence["exam_stats_by_agent_id"].get(asset_id)
            metrics = LearningPathService._exam_report_metrics(exam_session)
            payload: dict[str, Any] = {
                "result": "completed" if passed else "failed",
                "passed": passed,
            }
            if stats is not None:
                payload["score"] = stats.get("best_score")
                payload["best_score"] = stats.get("best_score")
                payload["lowest_score"] = stats.get("lowest_score")
                payload["latest_score"] = stats.get("latest_score")
                payload["attempt_count"] = stats.get("attempt_count")
            elif metrics is not None:
                payload["score"] = metrics.get("score")
            return payload

        return LearningPathService._stage_result_for_stage(
            stage_key=stage.template_stage_key,
            template_id=asset_id,
            sessions=completed_sessions,
        )

    @staticmethod
    def _plan_for_template(template: PracticeTemplate) -> CurriculumPlanSchema | None:
        if not isinstance(template.curriculum_plan, dict):
            return None
        try:
            return CurriculumPlanSchema.model_validate(template.curriculum_plan)
        except (TypeError, ValueError, ValidationError):
            return None

    @staticmethod
    def _fallback_stage(
        template: PracticeTemplate, completed_template_ids: set[str]
    ) -> dict[str, Any]:
        template_id = str(template.template_id)
        return {
            "template_stage_key": f"template_stage_{template_id}",
            "name": str(template.name),
            "state": "completed" if template_id in completed_template_ids else "available",
            "stage_type": "practice",
            "asset_type": "practice_template",
            "asset_id": template_id,
            "learning_content_id": (
                str(template.learning_content_id) if template.learning_content_id else None
            ),
            "agent_id": str(template.agent_id) if template.agent_id else None,
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
    def _review_stage_state(
        *,
        default_state: str,
        template_id: str,
        sessions: list[PracticeSession],
        review_outcomes: dict[str, str],
    ) -> str:
        for session in sessions:
            if str(session.practice_template_id) != template_id:
                continue
            outcome = review_outcomes.get(str(session.session_id))
            if outcome:
                return outcome
            if default_state == "completed":
                return "pending_review"
        if default_state == "locked":
            return "locked"
        return "pending_review"

    @staticmethod
    def _stage_prerequisite_satisfied(
        *,
        prerequisite_key: str,
        stages: list[dict[str, Any]],
        evidence: _StageCompletionEvidence,
    ) -> bool:
        for stage in stages:
            if stage["template_stage_key"] != prerequisite_key:
                continue
            state = str(stage.get("state") or "")
            if state == "completed":
                return True
            if state in {"failed", "in_progress", "pending_review", "retraining_required"}:
                return True
            asset_id = str(stage.get("asset_id") or "")
            if (
                stage.get("stage_type") == "study"
                and asset_id in evidence["learning_content_participated_ids"]
            ):
                return True
            return False
        return False

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
            snapshot: dict[str, Any] = orm_dict(session.effectiveness_snapshot)
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
            runtime_state: dict[str, Any] = orm_dict(session.runtime_state)
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
                payload: dict[str, Any] = orm_dict(snapshot.report_payload)
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
                reason = stage.get("failure_reason")
                return str(reason) if reason else None
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
