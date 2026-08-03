"""Task-oriented, organization-scoped read models for the admin workspace."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Never

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.models import CoachSession
from common.db.models import User
from foundation_admin_permissions import FoundationAdminActors
from learning.models import (
    LearningQuestion,
    LearningQuestionCandidate,
    LearningQuestionRevision,
    LearningQuiz,
    LearningQuizRevision,
    LearningSourceAnchor,
    LearningSourceDocument,
    LearningSourceDocumentRevision,
    LearningUnit,
    LearningUnitRevision,
)
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerCohort,
    NewcomerCommandAudit,
    NewcomerEnrollment,
    NewcomerEnrollmentImport,
    NewcomerEnrollmentMigration,
    NewcomerPath,
    NewcomerPathRevision,
    NewcomerReleasePlan,
)
from readiness.models import ReadinessDossier
from task_runtime.models import DurableTask
from task_runtime.operator_service import (
    OperatorActor,
    SQLAlchemyTaskAccessPolicy,
    TaskAccessAction,
)

_TASK_STATE_LABELS = {
    "queued": "等待处理",
    "running": "处理中",
    "retry_wait": "等待重试",
    "cancel_requested": "正在取消",
    "cancelled": "已取消",
    "succeeded": "已完成",
    "dead_letter": "需要人工处理",
}


class FoundationAdminWorkspaceQueryService:
    def __init__(
        self, session: AsyncSession, *, actors: FoundationAdminActors
    ) -> None:
        self._session = session
        self._actors = actors
        self._organization_id = actors.newcomer.organization_id
        self._task_access = SQLAlchemyTaskAccessPolicy(session)
        self._task_actor = OperatorActor(
            actor_id=actors.newcomer.actor_id,
            capabilities=frozenset(
                {
                    "task_runtime.read",
                    *(
                        ("task_runtime.operate",)
                        if "retry_assessments" in actors.capabilities
                        else ()
                    ),
                }
            ),
        )

    async def overview(self) -> dict[str, Any]:
        self._require("view_overview")
        action_items: list[dict[str, Any]] = []
        if "publish_releases" in self._actors.capabilities:
            releases = list(
                (
                    await self._session.execute(
                        select(NewcomerReleasePlan)
                        .where(
                            NewcomerReleasePlan.organization_id
                            == self._organization_id
                        )
                        .where(NewcomerReleasePlan.status.in_(("blocked", "failed")))
                        .order_by(NewcomerReleasePlan.created_at.asc())
                        .limit(20)
                    )
                ).scalars()
            )
            action_items.extend(
                {
                    "id": row.release_plan_id,
                    "category": "发布阻塞",
                    "priority": "high",
                    "title": "训练路径发布尚未完成",
                    "reason": self._release_reason(row),
                    "affected_object": row.path_id,
                    "status": row.status,
                    "waiting_since": row.created_at,
                    "href": f"/admin/newcomer-training/releases?plan={row.release_plan_id}",
                }
                for row in releases
            )
        if "review_questions" in self._actors.capabilities:
            candidates = list(
                (
                    await self._session.execute(
                        select(LearningQuestionCandidate)
                        .where(
                            LearningQuestionCandidate.organization_id
                            == self._organization_id
                        )
                        .where(
                            LearningQuestionCandidate.status.in_(
                                ("generated", "in_review")
                            )
                        )
                        .order_by(LearningQuestionCandidate.created_at.asc())
                        .limit(20)
                    )
                ).scalars()
            )
            action_items.extend(
                {
                    "id": row.candidate_id,
                    "category": "题目审核",
                    "priority": "normal",
                    "title": "生成题目等待人工审核",
                    "reason": "人工确认答案、来源和能力映射后才能进入正式题库。",
                    "affected_object": row.batch_id,
                    "status": row.status,
                    "waiting_since": row.created_at,
                    "href": f"/admin/newcomer-training/questions?candidate={row.candidate_id}",
                }
                for row in candidates
            )
        if "retry_assessments" in self._actors.capabilities:
            tasks = list(
                (
                    await self._session.execute(
                        select(DurableTask)
                        .where(DurableTask.organization_id == self._organization_id)
                        .where(
                            DurableTask.state.in_(
                                ("retry_wait", "dead_letter", "cancel_requested")
                            )
                        )
                        .order_by(DurableTask.updated_at.asc())
                        .limit(20)
                    )
                ).scalars()
            )
            readable_tasks = await self._scoped_tasks(
                tasks, action=TaskAccessAction.READ
            )
            action_items.extend(self._task_action(row) for row in readable_tasks)
            aged = list(
                (
                    await self._session.execute(
                        select(DurableTask)
                        .where(DurableTask.organization_id == self._organization_id)
                        .where(DurableTask.state.in_(("queued", "running")))
                        .where(
                            DurableTask.created_at
                            < datetime.now(UTC) - timedelta(hours=2)
                        )
                        .order_by(DurableTask.created_at.asc())
                        .limit(10)
                    )
                ).scalars()
            )
            readable_aged = await self._scoped_tasks(
                aged, action=TaskAccessAction.READ
            )
            action_items.extend(
                self._task_action(row, long_wait=True) for row in readable_aged
            )
        if "review_readiness" in self._actors.capabilities:
            dossiers = list(
                (
                    await self._session.execute(
                        select(ReadinessDossier)
                        .where(
                            ReadinessDossier.organization_id
                            == self._organization_id
                        )
                        .where(
                            ReadinessDossier.state.in_(
                                ("ready_for_review", "stale", "projection_failed")
                            )
                        )
                        .order_by(ReadinessDossier.updated_at.asc())
                        .limit(20)
                    )
                ).scalars()
            )
            action_items.extend(
                {
                    "id": row.dossier_id,
                    "category": "达标复核",
                    "priority": (
                        "high" if row.state == "projection_failed" else "normal"
                    ),
                    "title": (
                        "达标档案需要恢复"
                        if row.state == "projection_failed"
                        else "学员达标档案等待复核"
                    ),
                    "reason": row.stale_reason or "证据已经汇总，等待有权限的复核人决定。",
                    "affected_object": row.learner_id,
                    "status": row.state,
                    "waiting_since": row.updated_at,
                    "href": f"/admin/newcomer-training/reviews?dossier={row.dossier_id}",
                }
                for row in dossiers
            )
        if "retry_assessments" in self._actors.capabilities:
            sessions = list(
                (
                    await self._session.execute(
                        select(CoachSession)
                        .where(CoachSession.organization_id == self._organization_id)
                        .where(CoachSession.status == "needs_human_help")
                        .order_by(CoachSession.updated_at.asc())
                        .limit(20)
                    )
                ).scalars()
            )
            action_items.extend(
                {
                    "id": row.session_id,
                    "category": "教练人工帮助",
                    "priority": "high",
                    "title": "学员训练需要人工接手",
                    "reason": row.safe_error_message or "自动辅导无法可靠继续。",
                    "affected_object": row.learner_id,
                    "status": row.status,
                    "waiting_since": row.updated_at,
                    "href": f"/admin/newcomer-training/assessments?coach={row.session_id}",
                }
                for row in sessions
            )
        if "manage_cohorts" in self._actors.capabilities:
            imports = list(
                (
                    await self._session.execute(
                        select(NewcomerEnrollmentImport)
                        .where(
                            NewcomerEnrollmentImport.organization_id
                            == self._organization_id
                        )
                        .where(NewcomerEnrollmentImport.status.in_(("partial", "failed")))
                        .order_by(NewcomerEnrollmentImport.created_at.asc())
                        .limit(10)
                    )
                ).scalars()
            )
            migrations = list(
                (
                    await self._session.execute(
                        select(NewcomerEnrollmentMigration)
                        .where(
                            NewcomerEnrollmentMigration.organization_id
                            == self._organization_id
                        )
                        .where(
                            NewcomerEnrollmentMigration.status.in_(("partial", "failed"))
                        )
                        .order_by(NewcomerEnrollmentMigration.created_at.asc())
                        .limit(10)
                    )
                ).scalars()
            )
            action_items.extend(
                {
                    "id": row.import_id,
                    "category": "学员分配",
                    "priority": "normal",
                    "title": "批量分配存在未成功项",
                    "reason": "查看逐项结果，修正后仅重试失败学员。",
                    "affected_object": row.cohort_id,
                    "status": row.status,
                    "waiting_since": row.created_at,
                    "href": f"/admin/newcomer-training/cohorts/{row.cohort_id}?import={row.import_id}",
                }
                for row in imports
            )
            action_items.extend(
                {
                    "id": row.migration_id,
                    "category": "版本迁移",
                    "priority": "normal",
                    "title": "路径版本迁移存在未成功项",
                    "reason": "活跃学员保持原修订，请查看逐项冲突后重新预览。",
                    "affected_object": row.target_revision_id,
                    "status": row.status,
                    "waiting_since": row.created_at,
                    "href": f"/admin/newcomer-training/cohorts?migration={row.migration_id}",
                }
                for row in migrations
            )
        priority = {"high": 0, "normal": 1, "low": 2}
        action_items.sort(
            key=lambda item: (
                priority.get(str(item["priority"]), 9),
                item["waiting_since"],
            )
        )
        grouped_counts: dict[str, int] = {}
        for item in action_items:
            category = str(item["category"])
            grouped_counts[category] = grouped_counts.get(category, 0) + 1
        return {
            "capabilities": sorted(self._actors.capabilities),
            "action_items": action_items[:100],
            "counts": grouped_counts,
            "generated_at": datetime.now(UTC),
            "is_partial": False,
        }

    async def list_paths(
        self, *, query: str | None, status: str | None, limit: int
    ) -> dict[str, Any]:
        self._require("edit_paths", "publish_releases")
        statement = (
            select(NewcomerPath)
            .where(NewcomerPath.organization_id == self._organization_id)
            .order_by(NewcomerPath.updated_at.desc(), NewcomerPath.path_id.desc())
            .limit(max(1, min(limit, 100)))
        )
        if status:
            statement = statement.where(NewcomerPath.status == status)
        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(
                or_(NewcomerPath.title.ilike(like), NewcomerPath.stable_key.ilike(like))
            )
        rows = list((await self._session.execute(statement)).scalars())
        return {
            "items": [
                {
                    "path_id": row.path_id,
                    "stable_key": row.stable_key,
                    "title": row.title,
                    "status": row.status,
                    "working_revision_id": row.working_revision_id,
                    "published_revision_id": row.published_revision_id,
                    "active_release_plan_id": row.active_release_plan_id,
                    "version": row.version,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ],
            "limit": max(1, min(limit, 100)),
        }

    async def resource_references(
        self, *, resource_type: str, resource_id: str
    ) -> dict[str, Any]:
        """Project human-safe references without exposing revision payloads.

        Revision references currently live inside versioned snapshots.  This
        read model therefore scans only the organization-scoped, bounded
        revision columns and reports when the bound was reached.  It never
        treats a partial scan as a complete impact result.
        """

        self._require("edit_content")
        references: list[dict[str, Any]] = []
        revision_ids, anchor_ids = await self._resource_revision_scope(
            resource_type=resource_type,
            resource_id=resource_id,
        )
        scan_limit = 2_001
        is_partial = False

        if resource_type in {"learning_unit", "quiz"}:
            rows = list(
                (
                    await self._session.execute(
                        select(NewcomerPathRevision, NewcomerPath)
                        .join(
                            NewcomerPath,
                            NewcomerPath.path_id == NewcomerPathRevision.path_id,
                        )
                        .where(
                            NewcomerPathRevision.organization_id
                            == self._organization_id
                        )
                        .order_by(NewcomerPathRevision.created_at.desc())
                        .limit(scan_limit)
                    )
                ).all()
            )
            is_partial = is_partial or len(rows) == scan_limit
            field = (
                "learning_unit_revision_id"
                if resource_type == "learning_unit"
                else "quiz_revision_id"
            )
            for revision, path in rows[: scan_limit - 1]:
                if self._snapshot_references(
                    revision.snapshot_json,
                    field=field,
                    revision_ids=revision_ids,
                ):
                    references.append(
                        {
                            "reference_type": "path",
                            "title": path.title,
                            "revision_label": revision.revision_label,
                            "status": revision.status,
                            "href": (
                                f"/admin/newcomer-training/paths/"
                                f"{path.path_id}/edit"
                            ),
                        }
                    )

        if resource_type == "source_document" and anchor_ids:
            unit_rows = list(
                (
                    await self._session.execute(
                        select(LearningUnitRevision, LearningUnit)
                        .join(
                            LearningUnit,
                            LearningUnit.unit_id == LearningUnitRevision.unit_id,
                        )
                        .where(
                            LearningUnitRevision.organization_id
                            == self._organization_id
                        )
                        .order_by(LearningUnitRevision.created_at.desc())
                        .limit(scan_limit)
                    )
                ).all()
            )
            question_rows = list(
                (
                    await self._session.execute(
                        select(LearningQuestionRevision, LearningQuestion)
                        .join(
                            LearningQuestion,
                            LearningQuestion.question_id
                            == LearningQuestionRevision.question_id,
                        )
                        .where(
                            LearningQuestionRevision.organization_id
                            == self._organization_id
                        )
                        .order_by(LearningQuestionRevision.created_at.desc())
                        .limit(scan_limit)
                    )
                ).all()
            )
            is_partial = is_partial or len(unit_rows) == scan_limit
            is_partial = is_partial or len(question_rows) == scan_limit
            for revision, unit in unit_rows[: scan_limit - 1]:
                if anchor_ids.intersection(revision.source_anchor_ids_json):
                    references.append(
                        {
                            "reference_type": "learning_unit",
                            "title": unit.title,
                            "revision_label": revision.revision_label,
                            "status": revision.status,
                            "href": "/admin/newcomer-training/content",
                        }
                    )
            for revision, question in question_rows[: scan_limit - 1]:
                if anchor_ids.intersection(revision.source_anchor_ids_json):
                    title = str(
                        revision.content_json.get("stem")
                        or revision.content_json.get("question")
                        or question.stable_key
                    )
                    references.append(
                        {
                            "reference_type": "question",
                            "title": title[:240],
                            "revision_label": f"第 {revision.revision_no} 版",
                            "status": revision.status,
                            "href": "/admin/newcomer-training/questions",
                        }
                    )

        if resource_type == "question":
            quiz_rows = list(
                (
                    await self._session.execute(
                        select(LearningQuizRevision, LearningQuiz)
                        .join(
                            LearningQuiz,
                            LearningQuiz.quiz_id == LearningQuizRevision.quiz_id,
                        )
                        .where(
                            LearningQuizRevision.organization_id
                            == self._organization_id
                        )
                        .order_by(LearningQuizRevision.created_at.desc())
                        .limit(scan_limit)
                    )
                ).all()
            )
            is_partial = is_partial or len(quiz_rows) == scan_limit
            for revision, quiz in quiz_rows[: scan_limit - 1]:
                if revision_ids.intersection(revision.question_revision_ids_json):
                    references.append(
                        {
                            "reference_type": "quiz",
                            "title": quiz.title,
                            "revision_label": revision.revision_label,
                            "status": revision.status,
                            "href": "/admin/newcomer-training/content",
                        }
                    )

        deduplicated = list(
            {
                (
                    item["reference_type"],
                    item["title"],
                    item["revision_label"],
                    item["href"],
                ): item
                for item in references
            }.values()
        )
        return {
            "items": deduplicated,
            "total": len(deduplicated),
            "is_partial": is_partial,
            "archive_behavior": "preserve_revisions",
        }

    async def _resource_revision_scope(
        self, *, resource_type: str, resource_id: str
    ) -> tuple[set[str], set[str]]:
        model_by_type: dict[str, tuple[type[Any], type[Any], str, str]] = {
            "source_document": (
                LearningSourceDocument,
                LearningSourceDocumentRevision,
                "document_id",
                "document_id",
            ),
            "learning_unit": (
                LearningUnit,
                LearningUnitRevision,
                "unit_id",
                "unit_id",
            ),
            "question": (
                LearningQuestion,
                LearningQuestionRevision,
                "question_id",
                "question_id",
            ),
            "quiz": (
                LearningQuiz,
                LearningQuizRevision,
                "quiz_id",
                "quiz_id",
            ),
        }
        models = model_by_type.get(resource_type)
        if models is None:
            self._not_found("学习资源")
        resource_model, revision_model, resource_key, revision_key = models
        resource = await self._session.get(resource_model, resource_id)
        if (
            resource is None
            or resource.organization_id != self._organization_id
        ):
            self._not_found("学习资源")
        revisions = list(
            (
                await self._session.execute(
                    select(revision_model).where(
                        getattr(revision_model, revision_key)
                        == getattr(resource, resource_key)
                    )
                )
            ).scalars()
        )
        revision_ids = {str(row.revision_id) for row in revisions}
        anchor_ids: set[str] = set()
        if resource_type == "source_document" and revision_ids:
            anchor_ids = {
                str(value)
                for value in (
                    await self._session.execute(
                        select(LearningSourceAnchor.anchor_id).where(
                            LearningSourceAnchor.source_revision_id.in_(revision_ids)
                        )
                    )
                ).scalars()
            }
        return revision_ids, anchor_ids

    @staticmethod
    def _snapshot_references(
        snapshot: dict[str, Any], *, field: str, revision_ids: set[str]
    ) -> bool:
        for stage in snapshot.get("stages", []):
            if not isinstance(stage, dict):
                continue
            for activity in stage.get("activities", []):
                if not isinstance(activity, dict):
                    continue
                config = activity.get("config")
                if isinstance(config, dict) and str(config.get(field)) in revision_ids:
                    return True
        return False

    async def path_workspace(self, *, path_id: str) -> dict[str, Any]:
        self._require("edit_paths", "publish_releases")
        path = await self._session.get(NewcomerPath, path_id)
        if path is None or path.organization_id != self._organization_id:
            self._not_found("训练路径")
        revisions = list(
            (
                await self._session.execute(
                    select(NewcomerPathRevision)
                    .where(NewcomerPathRevision.path_id == path_id)
                    .where(
                        NewcomerPathRevision.organization_id
                        == self._organization_id
                    )
                    .order_by(NewcomerPathRevision.revision_no.desc())
                    .limit(50)
                )
            ).scalars()
        )
        return {
            "path": {
                "path_id": path.path_id,
                "stable_key": path.stable_key,
                "title": path.title,
                "status": path.status,
                "working_revision_id": path.working_revision_id,
                "published_revision_id": path.published_revision_id,
                "active_release_plan_id": path.active_release_plan_id,
                "version": path.version,
            },
            "working_revision": self._revision_payload(
                next(
                    (row for row in revisions if row.revision_id == path.working_revision_id),
                    None,
                )
            ),
            "published_revision": self._revision_payload(
                next(
                    (
                        row
                        for row in revisions
                        if row.revision_id == path.published_revision_id
                    ),
                    None,
                )
            ),
            "revision_history": [
                {
                    "revision_id": row.revision_id,
                    "revision_no": row.revision_no,
                    "revision_label": row.revision_label,
                    "status": row.status,
                    "content_hash": row.content_hash,
                    "version": row.version,
                    "created_at": row.created_at,
                    "published_at": row.published_at,
                }
                for row in revisions
            ],
        }

    async def list_cohorts(
        self, *, query: str | None, status: str | None, limit: int
    ) -> dict[str, Any]:
        self._require("manage_cohorts")
        enrollment_counts = (
            select(
                NewcomerEnrollment.cohort_id,
                func.count(NewcomerEnrollment.enrollment_id).label("count"),
            )
            .where(NewcomerEnrollment.organization_id == self._organization_id)
            .group_by(NewcomerEnrollment.cohort_id)
            .subquery()
        )
        statement = (
            select(NewcomerCohort, func.coalesce(enrollment_counts.c.count, 0))
            .outerjoin(
                enrollment_counts,
                enrollment_counts.c.cohort_id == NewcomerCohort.cohort_id,
            )
            .where(NewcomerCohort.organization_id == self._organization_id)
            .order_by(NewcomerCohort.updated_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        if status:
            statement = statement.where(NewcomerCohort.status == status)
        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(
                or_(NewcomerCohort.name.ilike(like), NewcomerCohort.stable_key.ilike(like))
            )
        rows = (await self._session.execute(statement)).all()
        return {
            "items": [
                {
                    "cohort_id": cohort.cohort_id,
                    "stable_key": cohort.stable_key,
                    "name": cohort.name,
                    "path_revision_id": cohort.path_revision_id,
                    "status": cohort.status,
                    "version": cohort.version,
                    "enrollment_count": int(count),
                    "updated_at": cohort.updated_at,
                }
                for cohort, count in rows
            ],
            "limit": max(1, min(limit, 100)),
        }

    async def cohort_workspace(self, *, cohort_id: str) -> dict[str, Any]:
        self._require("manage_cohorts")
        cohort = await self._session.get(NewcomerCohort, cohort_id)
        if cohort is None or cohort.organization_id != self._organization_id:
            self._not_found("训练班级")
        rows = (
            await self._session.execute(
                select(NewcomerEnrollment, User)
                .join(User, User.user_id == NewcomerEnrollment.learner_id)
                .where(NewcomerEnrollment.organization_id == self._organization_id)
                .where(NewcomerEnrollment.cohort_id == cohort_id)
                .order_by(NewcomerEnrollment.assigned_at.desc())
                .limit(500)
            )
        ).all()
        return {
            "cohort": {
                "cohort_id": cohort.cohort_id,
                "stable_key": cohort.stable_key,
                "name": cohort.name,
                "path_revision_id": cohort.path_revision_id,
                "status": cohort.status,
                "version": cohort.version,
            },
            "enrollments": [
                {
                    "enrollment_id": enrollment.enrollment_id,
                    "learner_id": enrollment.learner_id,
                    "learner_name": user.name,
                    "learner_email": user.email,
                    "path_revision_id": enrollment.path_revision_id,
                    "status": enrollment.status,
                    "version": enrollment.version,
                    "assigned_at": enrollment.assigned_at,
                }
                for enrollment, user in rows
            ],
        }

    async def assessment_tasks(
        self, *, state: str | None, limit: int
    ) -> dict[str, Any]:
        self._require("retry_assessments", "regrade_results")
        statement = (
            select(DurableTask)
            .where(DurableTask.organization_id == self._organization_id)
            .order_by(DurableTask.updated_at.desc(), DurableTask.task_id.desc())
            .limit(max(1, min(limit, 100)))
        )
        if state:
            statement = statement.where(DurableTask.state == state)
        rows = list((await self._session.execute(statement)).scalars())
        rows = await self._scoped_tasks(rows, action=TaskAccessAction.READ)
        operable = {
            (row.resource_type, row.resource_id)
            for row in await self._scoped_tasks(
                rows, action=TaskAccessAction.OPERATE
            )
        }
        return {
            "items": [
                {
                    "task_id": row.task_id,
                    "category": self._task_category(row.task_type),
                    "business_object": self._resource_label(row.resource_type),
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id,
                    "state": row.state,
                    "state_label": _TASK_STATE_LABELS.get(row.state, "状态待确认"),
                    "attempt_count": row.attempt_count,
                    "waiting_since": row.created_at,
                    "updated_at": row.updated_at,
                    "failure": (
                        row.last_error_message
                        if row.state in {"retry_wait", "dead_letter"}
                        else None
                    ),
                    "available_actions": self._task_actions(
                        row,
                        may_operate=(row.resource_type, row.resource_id) in operable,
                    ),
                }
                for row in rows
            ],
            "limit": max(1, min(limit, 100)),
        }

    async def audits(
        self, *, object_id: str | None, limit: int
    ) -> dict[str, Any]:
        self._require("view_sensitive_audit")
        statement = (
            select(NewcomerCommandAudit)
            .where(NewcomerCommandAudit.organization_id == self._organization_id)
            .order_by(NewcomerCommandAudit.occurred_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        if object_id:
            statement = statement.where(NewcomerCommandAudit.object_id == object_id)
        rows = list((await self._session.execute(statement)).scalars())
        return {
            "items": [
                {
                    "audit_id": row.audit_id,
                    "actor_id": row.actor_id,
                    "object_type": row.object_type,
                    "object_id": row.object_id,
                    "action": row.command,
                    "result": row.result,
                    "reason": row.reason,
                    "before_version": row.before_version,
                    "after_version": row.after_version,
                    "occurred_at": row.occurred_at,
                }
                for row in rows
            ]
        }

    def _require(self, *capabilities: str) -> None:
        if not any(item in self._actors.capabilities for item in capabilities):
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]",
                "没有查看此工作区的权限，请联系组织管理员。",
                403,
            )

    @staticmethod
    def _not_found(label: str) -> Never:
        raise NewcomerTrainingError(
            "[NEWCOMER_ADMIN_OBJECT_NOT_FOUND]", f"{label}不存在或不可访问。", 404
        )

    @staticmethod
    def _revision_payload(row: NewcomerPathRevision | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "revision_id": row.revision_id,
            "revision_no": row.revision_no,
            "revision_label": row.revision_label,
            "status": row.status,
            "snapshot": row.snapshot_json,
            "content_hash": row.content_hash,
            "version": row.version,
            "created_at": row.created_at,
            "published_at": row.published_at,
        }

    @staticmethod
    def _release_reason(row: NewcomerReleasePlan) -> str:
        failure = row.validation_report_json.get("publish_failure")
        if isinstance(failure, dict) and failure.get("message"):
            return str(failure["message"])
        issues = row.validation_report_json.get("issues", [])
        if issues and isinstance(issues[0], dict):
            return str(issues[0].get("message") or "发布检查仍有阻塞项。")
        return "发布检查仍有阻塞项。"

    @classmethod
    def _task_action(
        cls, row: DurableTask, *, long_wait: bool = False
    ) -> dict[str, Any]:
        return {
            "id": row.task_id,
            "category": "评测任务",
            "priority": "high" if row.state == "dead_letter" else "normal",
            "title": (
                "任务等待时间较长"
                if long_wait
                else f"{cls._task_category(row.task_type)}需要处理"
            ),
            "reason": row.last_error_message or "查看业务对象和可执行的恢复动作。",
            "affected_object": row.resource_id,
            "status": row.state,
            "waiting_since": row.created_at,
            "href": f"/admin/newcomer-training/assessments?task={row.task_id}",
        }

    @staticmethod
    def _task_category(task_type: str) -> str:
        value = task_type.lower()
        if "source_document" in value or "content_parse" in value:
            return "内容解析"
        if "audio" in value or "transcript" in value or "score" in value:
            return "录音评测"
        if "coach" in value:
            return "训练教练"
        if "question" in value:
            return "题目生成"
        if "readiness" in value or "evidence" in value:
            return "达标证据"
        return "后台处理"

    @staticmethod
    def _resource_label(resource_type: str) -> str:
        value = resource_type.lower()
        if "source_document" in value:
            return "原始材料修订"
        if "submission" in value or "audio" in value:
            return "学员录音"
        if "coach" in value or "session" in value:
            return "教练训练记录"
        if "question" in value or "batch" in value:
            return "题目生成批次"
        if "dossier" in value or "readiness" in value:
            return "达标档案"
        return "训练业务对象"

    def _task_actions(self, row: DurableTask, *, may_operate: bool) -> list[str]:
        actions = ["查看详情"]
        if may_operate and "retry_assessments" in self._actors.capabilities and row.state in {
            "retry_wait",
            "dead_letter",
        }:
            actions.append("预览重试")
        if may_operate and "retry_assessments" in self._actors.capabilities and row.state in {
            "queued",
            "running",
            "retry_wait",
        }:
            actions.append("申请取消")
        if (
            may_operate
            and "regrade_results" in self._actors.capabilities
            and row.resource_type == "audio_submission"
            and row.state == "succeeded"
        ):
            actions.extend(("预览重评", "预览失效"))
        return actions

    async def _scoped_tasks(
        self,
        rows: list[DurableTask],
        *,
        action: TaskAccessAction,
    ) -> list[DurableTask]:
        resources = frozenset((row.resource_type, row.resource_id) for row in rows)
        allowed = await self._task_access.allowed_resource_keys(
            self._task_actor,
            organization_id=self._organization_id,
            resources=resources,
            action=action,
        )
        return [
            row
            for row in rows
            if (row.resource_type, row.resource_id) in allowed
        ]


__all__ = ["FoundationAdminWorkspaceQueryService"]
