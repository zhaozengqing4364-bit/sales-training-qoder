from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.readiness_state import (
    CAPABILITY_DEFINITIONS,
    CAPABILITY_KEYS,
    READINESS_CONTRACT_VERSION,
    READINESS_DOSSIER_TARGET_TYPE,
    REVIEW_ACTION_CREATED,
    decision_label,
    module_capability_keys,
    unique_non_empty,
)
from sales_trainer.services.training_journey_service import (
    TrainingJourneyError,
    TrainingJourneyService,
)
from sales_trainer.services.training_record_service import TrainingRecordService

ReadinessDecision = Literal["approve", "require_retraining", "mark_manual_follow_up"]
ReadinessStatus = Literal[
    "not_started",
    "in_training",
    "ai_evaluating",
    "needs_remediation",
    "pending_review",
    "approved",
    "rejected",
    "manual_follow_up",
    "blocked_by_config",
]
WorkbenchGroupKey = Literal[
    "pending_review",
    "not_passed",
    "needs_retraining",
    "approved",
    "config_exception",
    "in_training",
]

AI_EVALUATING_STATUSES = frozenset({"waiting_upload", "processing"})
RISK_STATUSES = frozenset(
    {
        "failed",
        "needs_remediation",
        "manual_review",
        "error_terminal",
        "error_transient",
    }
)
CONFIG_BLOCKER_CODES = frozenset(
    {
        "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
        "[NEWCOMER_PATH_CONFIG_MISSING]",
        "[NEWCOMER_MODULE_BINDING_MISSING]",
        "[AI_COACH_PROMPT_CONFIG_INVALID]",
        "[AI_COACH_PROMPT_TEMPLATE_MISSING]",
        "[NEWCOMER_LEARNER_LEVEL_NOT_ALLOWED]",
    }
)


class ReadinessDossierError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ReadinessDossierService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._journeys = TrainingJourneyService(db)
        self._records = TrainingRecordService(db)
        self._logs = OperationLogService(db)

    async def get_dossier(
        self,
        learner_id: str,
        *,
        viewer: User,
        team_department: str | None,
    ) -> dict[str, Any]:
        learner = await self._learner_for_viewer(
            learner_id,
            team_department=team_department,
        )
        try:
            journey = await self._journeys.get_admin_journey(
                learner_id,
                viewer=viewer,
                team_department=team_department,
            )
        except TrainingJourneyError as exc:
            if exc.code != "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]":
                raise ReadinessDossierError(
                    exc.code, exc.message, exc.status_code
                ) from exc
            journey = self._blocked_journey(
                learner,
                code=exc.code,
                message=exc.message,
            )

        records, _ = await self._records.list_records(
            user_id=learner_id,
            team_department=team_department,
            viewer=viewer,
            limit=200,
            offset=0,
        )
        review_actions = await self._review_actions(learner_id)
        return self._dossier_payload(
            journey,
            records=records,
            review_actions=review_actions,
        )

    async def list_workbench(
        self,
        *,
        viewer: User,
        team_department: str | None,
        department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        try:
            payload = await self._journeys.list_admin_journeys(
                viewer=viewer,
                team_department=team_department,
                department=department,
                limit=limit,
                offset=offset,
            )
            journeys = [
                self._dossier_payload(
                    journey,
                    records=[],
                    review_actions=await self._review_actions(
                        str(journey["learner_id"])
                    ),
                    evidence_limit=0,
                )
                for journey in payload.get("items", [])
            ]
            total = int(payload.get("total") or len(journeys))
        except TrainingJourneyError as exc:
            if exc.code != "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]":
                raise ReadinessDossierError(
                    exc.code, exc.message, exc.status_code
                ) from exc
            learners, total = await self._learners_for_workbench(
                team_department=team_department,
                department=department,
                limit=limit,
                offset=offset,
            )
            journeys = [
                self._dossier_payload(
                    self._blocked_journey(learner, code=exc.code, message=exc.message),
                    records=[],
                    review_actions=await self._review_actions(str(learner.user_id)),
                    evidence_limit=0,
                )
                for learner in learners
            ]

        groups = self._workbench_groups(journeys)
        return {
            "contract_version": READINESS_CONTRACT_VERSION,
            "generated_at": datetime.now(UTC),
            "groups": groups,
            "summary": {
                "learner_count": total,
                "loaded_learner_count": len(journeys),
                "pending_review_count": len(groups["pending_review"]["items"]),
                "not_passed_count": len(groups["not_passed"]["items"]),
                "needs_retraining_count": len(groups["needs_retraining"]["items"]),
                "approved_count": len(groups["approved"]["items"]),
                "config_exception_count": len(groups["config_exception"]["items"]),
                "in_training_count": len(groups["in_training"]["items"]),
            },
            "filters": {
                "department": team_department or department,
                "limit": limit,
                "offset": offset,
            },
        }

    async def create_review_action(
        self,
        learner_id: str,
        *,
        actor: User,
        team_department: str | None,
        decision: ReadinessDecision,
        reason: str,
        capability_keys: list[str] | None = None,
        source_evidence_ids: list[str] | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        dossier = await self.get_dossier(
            learner_id,
            viewer=actor,
            team_department=team_department,
        )
        normalized_capabilities = unique_non_empty(capability_keys or [])
        unknown_capabilities = sorted(set(normalized_capabilities) - CAPABILITY_KEYS)
        if unknown_capabilities:
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_CAPABILITY_INVALID]",
                "复核动作包含系统未识别的能力项。",
                400,
                details={"unknown_capability_keys": unknown_capabilities},
            )
        evidence_ids = unique_non_empty(source_evidence_ids or [])
        known_evidence_ids = {
            str(item.get("evidence_id"))
            for item in dossier.get("evidence", [])
            if item.get("evidence_id")
        }
        unknown_evidence_ids = sorted(set(evidence_ids) - known_evidence_ids)
        if unknown_evidence_ids:
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_EVIDENCE_INVALID]",
                "复核动作引用了不存在或无权访问的训练证据。",
                400,
                details={"unknown_evidence_ids": unknown_evidence_ids},
            )
        if decision == "approve":
            self._ensure_dossier_can_be_approved(dossier)
        if not evidence_ids:
            evidence_ids = self._default_review_evidence_ids(dossier)
        if not normalized_capabilities:
            normalized_capabilities = self._default_review_capability_keys(dossier)

        retraining_task = None
        if decision == "require_retraining":
            retraining_task = {
                "task_id": f"retraining:{learner_id}:{datetime.now(UTC).timestamp()}",
                "status": "pending",
                "source": "operation_log",
                "capability_keys": normalized_capabilities,
                "source_evidence_ids": evidence_ids,
                "target_learner_id": learner_id,
            }

        log = await self._logs.record(
            actor=actor,
            action=REVIEW_ACTION_CREATED,
            target_type=READINESS_DOSSIER_TARGET_TYPE,
            target_id=learner_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "contract_version": READINESS_CONTRACT_VERSION,
                "decision": decision,
                "decision_label": decision_label(decision),
                "reason": reason.strip(),
                "capability_keys": normalized_capabilities,
                "source_evidence_ids": evidence_ids,
                "retraining_task": retraining_task,
                "state_storage": "operation_log",
            },
        )
        await self._db.commit()
        return self._review_action_payload(log)

    @staticmethod
    def _ensure_dossier_can_be_approved(dossier: dict[str, Any]) -> None:
        status = str(dossier.get("status") or "")
        if status == "blocked_by_config":
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_CONFIG_BLOCKED]",
                "当前档案存在配置异常，不能确认达标。",
                409,
            )
        summary = dossier.get("summary")
        evidence_count = 0
        if isinstance(summary, dict):
            try:
                evidence_count = int(summary.get("evidence_count") or 0)
            except (TypeError, ValueError):
                evidence_count = 0
        if status != "pending_review" or evidence_count <= 0:
            raise ReadinessDossierError(
                "[READINESS_DOSSIER_NOT_READY]",
                "关键训练证据尚未齐全，不能确认达标。",
                409,
                details={
                    "status": status,
                    "required_status": "pending_review",
                    "evidence_count": evidence_count,
                },
            )

    async def _learner_for_viewer(
        self,
        learner_id: str,
        *,
        team_department: str | None,
    ) -> User:
        learner = await self._db.get(User, learner_id)
        if learner is None:
            raise ReadinessDossierError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "学员训练记录不存在。",
                404,
            )
        if (
            team_department is not None
            and str(learner.department or "") != team_department
        ):
            raise ReadinessDossierError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "学员训练记录不存在。",
                404,
            )
        return learner

    async def _learners_for_workbench(
        self,
        *,
        team_department: str | None,
        department: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[User], int]:
        if team_department is not None and department and department != team_department:
            return [], 0
        filters = [User.role == "user", User.is_active.is_(True)]
        effective_department = team_department or department
        if effective_department:
            filters.append(User.department == effective_department)
        total = int(
            await self._db.scalar(
                select(func.count()).select_from(User).where(*filters)
            )
            or 0
        )
        result = await self._db.execute(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.user_id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def _review_actions(self, learner_id: str) -> list[dict[str, Any]]:
        logs, _ = await self._logs.list_logs(
            target_type=READINESS_DOSSIER_TARGET_TYPE,
            target_id=learner_id,
            limit=50,
        )
        return [
            self._review_action_payload(log)
            for log in logs
            if log.action == REVIEW_ACTION_CREATED
        ]

    def _dossier_payload(
        self,
        journey: dict[str, Any],
        *,
        records: list[dict[str, Any]],
        review_actions: list[dict[str, Any]],
        evidence_limit: int | None = None,
    ) -> dict[str, Any]:
        full_evidence = self._evidence_items(journey, records)
        review_actions = self._review_actions_with_retraining_state(
            review_actions,
            full_evidence,
        )
        evidence = (
            full_evidence
            if evidence_limit is None
            else full_evidence[:evidence_limit]
        )
        latest_review_action = review_actions[0] if review_actions else None
        retraining_tasks = [
            action["retraining_task"]
            for action in review_actions
            if action.get("retraining_task")
        ]
        modules = self._module_summaries(journey, evidence)
        competencies = self._competencies(
            journey,
            evidence,
            latest_review_action=latest_review_action,
        )
        status, status_reason = self._status_and_reason(
            journey,
            latest_review_action=latest_review_action,
        )
        realtime_gate = self._realtime_gate(journey, status)
        next_actions = self._next_actions(
            status=status,
            learner_id=str(journey["learner_id"]),
            weak_capability_keys=[
                item["capability_key"]
                for item in competencies
                if item["status"] in {"ai_failed", "needs_retraining", "pending_review"}
            ],
            realtime_gate=realtime_gate,
        )
        return {
            "contract_version": READINESS_CONTRACT_VERSION,
            "learner": {
                "learner_id": str(journey["learner_id"]),
                "name": journey.get("learner_name"),
                "department": journey.get("department"),
            },
            "path": {
                "path_key": journey.get("path_key"),
                "path_revision_id": journey.get("path_revision_id"),
                "path_revision_no": journey.get("path_revision_no"),
                "source": journey.get("source"),
            },
            "status": status,
            "status_label": _status_label(status),
            "status_reason": status_reason,
            "summary": {
                **(journey.get("overall_progress") or {}),
                "evidence_count": len(full_evidence),
                "review_action_count": len(review_actions),
                "weak_capability_count": sum(
                    1
                    for item in competencies
                    if item["status"] in {"ai_failed", "needs_retraining"}
                ),
                "retraining_task_count": len(retraining_tasks),
                "completed_retraining_task_count": sum(
                    1
                    for item in retraining_tasks
                    if item.get("status") == "completed"
                ),
                "review_state_source": "operation_log",
            },
            "modules": modules,
            "competencies": competencies,
            "evidence": evidence,
            "review_actions": review_actions,
            "latest_review_action": latest_review_action,
            "retraining_tasks": retraining_tasks,
            "realtime_gate": realtime_gate,
            "diagnostics": self._diagnostics(journey),
            "next_actions": next_actions,
            "generated_at": datetime.now(UTC),
        }

    def _evidence_items(
        self,
        journey: dict[str, Any],
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        records_by_key = {
            (
                str(record.get("record_type") or ""),
                str(record.get("record_id") or ""),
            ): record
            for record in records
        }
        evidence: list[dict[str, Any]] = []
        for module in journey.get("modules") or []:
            for outcome in module.get("outcome_history") or []:
                record_type = str(outcome.get("record_type") or "")
                record_id = str(outcome.get("source_record_id") or "")
                record = records_by_key.get((record_type, record_id), {})
                capability_keys = module_capability_keys(module)
                evidence_id = f"{record_type}:{record_id}"
                evidence.append(
                    {
                        "evidence_id": evidence_id,
                        "evidence_type": record_type,
                        "source_record_id": record_id,
                        "record_type": record_type,
                        "module_key": module.get("module_key"),
                        "module_title": module.get("title")
                        or module.get("display_name"),
                        "module_type": module.get("module_type"),
                        "capability_keys": capability_keys,
                        "status": outcome.get("status") or record.get("status"),
                        "score": outcome.get("score")
                        if outcome.get("score") is not None
                        else record.get("score"),
                        "max_score": outcome.get("max_score")
                        if outcome.get("max_score") is not None
                        else record.get("max_score"),
                        "passed": outcome.get("passed")
                        if isinstance(outcome.get("passed"), bool)
                        else record.get("passed"),
                        "submitted_at": outcome.get("submitted_at")
                        or record.get("submitted_at"),
                        "completed_at": outcome.get("completed_at"),
                        "target_path": _record_detail_path(record_type, record_id),
                        "material_snapshot": _compact_snapshot(
                            record.get("material_snapshot"),
                            keys=(
                                "material_id",
                                "version_id",
                                "title",
                                "name",
                                "filename",
                            ),
                        ),
                        "scoring_snapshot": _scoring_snapshot(record),
                        "task_brief_snapshot": _compact_snapshot(
                            record.get("task_brief_snapshot"),
                            keys=("title", "purpose", "scenario", "success_criteria"),
                        ),
                        "snapshot_ref": outcome.get("snapshot_ref"),
                        "result_summary": _record_result_summary(record, outcome),
                    }
                )
        for topic in journey.get("learning_topics") or []:
            if not isinstance(topic, dict):
                continue
            topic_capabilities = module_capability_keys(
                {
                    "module_key": topic.get("source_module_key")
                    or topic.get("topic_key"),
                    "title": topic.get("title"),
                    "kind": "learning_topic",
                    "module_type": "learning_topic",
                }
            )
            for unit in topic.get("units") or []:
                if not isinstance(unit, dict) or not unit.get("latest_attempt_id"):
                    continue
                record_id = str(unit["latest_attempt_id"])
                record_type = "business_etiquette_quiz_attempt"
                unit_capabilities = unique_non_empty(
                    [
                        str(value)
                        for value in unit.get("capability_keys") or []
                        if value
                    ]
                    + topic_capabilities
                )
                evidence.append(
                    {
                        "evidence_id": f"{record_type}:{record_id}",
                        "evidence_type": record_type,
                        "source_record_id": record_id,
                        "record_type": record_type,
                        "module_key": topic.get("source_module_key")
                        or topic.get("topic_key"),
                        "module_title": topic.get("title"),
                        "module_type": "learning_topic",
                        "capability_keys": unit_capabilities or topic_capabilities,
                        "status": unit.get("status"),
                        "score": unit.get("score"),
                        "max_score": unit.get("max_score"),
                        "passed": unit.get("passed"),
                        "submitted_at": unit.get("latest_attempt_submitted_at"),
                        "completed_at": unit.get("latest_attempt_submitted_at"),
                        "target_path": _learning_topic_detail_path(
                            str(topic.get("topic_key") or "")
                        ),
                        "material_snapshot": None,
                        "scoring_snapshot": None,
                        "task_brief_snapshot": {
                            "title": unit.get("title"),
                            "purpose": topic.get("title"),
                        },
                        "snapshot_ref": topic.get("source"),
                        "result_summary": _learning_topic_result_summary(unit),
                    }
                )
        evidence.sort(
            key=lambda item: str(item.get("submitted_at") or ""), reverse=True
        )
        return evidence

    def _module_summaries(
        self,
        journey: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        evidence_by_module: dict[str, list[str]] = {}
        for item in evidence:
            module_key = str(item.get("module_key") or "")
            if not module_key:
                continue
            evidence_by_module.setdefault(module_key, []).append(
                str(item["evidence_id"])
            )
        modules = []
        for module in journey.get("modules") or []:
            next_action = module.get("next_action") or {}
            modules.append(
                {
                    "module_key": module.get("module_key"),
                    "title": module.get("title") or module.get("display_name"),
                    "kind": module.get("kind"),
                    "module_type": module.get("module_type"),
                    "order_index": module.get("order_index"),
                    "status": module.get("status"),
                    "passed": module.get("passed"),
                    "score": module.get("score"),
                    "max_score": module.get("max_score"),
                    "required": module.get("required"),
                    "completion_satisfied": module.get("completion_satisfied"),
                    "locked": module.get("locked"),
                    "block_reason": module.get("block_reason"),
                    "capability_keys": module_capability_keys(module),
                    "evidence_ids": evidence_by_module.get(
                        str(module.get("module_key") or ""),
                        [],
                    ),
                    "next_action": {
                        "label": next_action.get("label"),
                        "target_path": next_action.get("target_path"),
                        "disabled": bool(next_action.get("disabled"))
                        if next_action
                        else False,
                        "disabled_reason": next_action.get("disabled_reason"),
                    }
                    if next_action
                    else None,
                }
            )
        return modules

    def _review_actions_with_retraining_state(
        self,
        review_actions: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for action in review_actions:
            cloned = dict(action)
            task = self._enriched_retraining_task(cloned, evidence)
            if task is not None:
                cloned["retraining_task"] = task
            enriched.append(cloned)
        return enriched

    @staticmethod
    def _enriched_retraining_task(
        action: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        task_value = action.get("retraining_task")
        if not isinstance(task_value, dict):
            return None
        task = dict(task_value)
        action_created_at = _datetime_or_none(action.get("created_at"))
        source_evidence_ids = unique_non_empty(
            action.get("source_evidence_ids")
            or task.get("source_evidence_ids")
            or []
        )
        capability_keys = unique_non_empty(
            action.get("capability_keys") or task.get("capability_keys") or []
        )
        newer_evidence = _evidence_after_review(
            evidence,
            reviewed_at=action_created_at,
            source_evidence_ids=source_evidence_ids,
            capability_keys=capability_keys,
        )
        if newer_evidence:
            latest = newer_evidence[0]
            latest_status = str(latest.get("status") or "")
            if latest_status in AI_EVALUATING_STATUSES:
                task["status"] = "in_progress"
                task["completed_at"] = None
            else:
                task["status"] = "completed"
                task["completed_at"] = latest.get("completed_at") or latest.get(
                    "submitted_at"
                )
            task["completed_evidence_ids"] = [
                str(item["evidence_id"])
                for item in newer_evidence
                if item.get("evidence_id")
            ]
            task["comparison"] = {
                "before_evidence_ids": source_evidence_ids,
                "after_evidence_ids": task["completed_evidence_ids"],
                "after_status": latest_status or None,
                "after_passed": latest.get("passed"),
                "after_score": latest.get("score"),
                "after_max_score": latest.get("max_score"),
            }
        else:
            task["status"] = str(task.get("status") or "pending")
            task.setdefault("completed_evidence_ids", [])
            task.setdefault(
                "comparison",
                {
                    "before_evidence_ids": source_evidence_ids,
                    "after_evidence_ids": [],
                },
            )
        task["source_evidence_ids"] = source_evidence_ids
        task["capability_keys"] = capability_keys
        return task

    def _competencies(
        self,
        journey: dict[str, Any],
        evidence: list[dict[str, Any]],
        *,
        latest_review_action: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        blocked = self._config_blockers(journey)
        items: dict[str, dict[str, Any]] = {
            definition.capability_key: {
                "capability_key": definition.capability_key,
                "display_name": definition.display_name,
                "description": definition.description,
                "status": "blocked_by_config" if blocked else "not_trained",
                "score": None,
                "max_score": None,
                "weak": False,
                "evidence_ids": [],
                "latest_evidence_id": None,
                "review_decision": None,
                "reason": "当前训练路径配置异常，能力项不可判定。"
                if blocked
                else "暂无相关训练证据。",
            }
            for definition in CAPABILITY_DEFINITIONS
        }
        if blocked:
            return [
                items[definition.capability_key]
                for definition in CAPABILITY_DEFINITIONS
            ]
        for item in reversed(evidence):
            for capability_key in item.get("capability_keys") or []:
                if capability_key not in items:
                    continue
                target = items[capability_key]
                target["evidence_ids"].append(item["evidence_id"])
                target["latest_evidence_id"] = item["evidence_id"]
                target["score"] = item.get("score")
                target["max_score"] = item.get("max_score")
                passed = item.get("passed")
                status = str(item.get("status") or "")
                if passed is True:
                    target["status"] = "ai_passed"
                    target["weak"] = False
                    target["reason"] = "AI/规则初评已达标，等待人工复核。"
                elif passed is False or status in RISK_STATUSES:
                    target["status"] = "ai_failed"
                    target["weak"] = True
                    target["reason"] = "AI/规则初评未达标或需要补练。"
                elif status in AI_EVALUATING_STATUSES:
                    target["status"] = "pending_review"
                    target["reason"] = "证据已提交，仍需评分或人工判断。"
        if latest_review_action is not None:
            decision = str(latest_review_action.get("decision") or "")
            selected_keys = latest_review_action.get("capability_keys") or []
            if not selected_keys:
                selected_keys = list(items)
            for capability_key in selected_keys:
                if capability_key not in items:
                    continue
                items[capability_key]["review_decision"] = decision
                if decision == "approve":
                    items[capability_key]["status"] = "approved"
                    items[capability_key]["weak"] = False
                    items[capability_key]["reason"] = "培训负责人已确认达标。"
                elif decision == "require_retraining":
                    if _retraining_task_status(latest_review_action) == "completed":
                        items[capability_key]["review_decision"] = None
                        continue
                    items[capability_key]["status"] = "needs_retraining"
                    items[capability_key]["weak"] = True
                    items[capability_key]["reason"] = "培训负责人已要求重练。"
                elif decision == "mark_manual_follow_up":
                    items[capability_key]["status"] = "pending_review"
                    items[capability_key]["reason"] = "已标记需人工跟进。"
        return [
            items[definition.capability_key] for definition in CAPABILITY_DEFINITIONS
        ]

    def _status_and_reason(
        self,
        journey: dict[str, Any],
        *,
        latest_review_action: dict[str, Any] | None,
    ) -> tuple[ReadinessStatus, str]:
        blockers = self._config_blockers(journey)
        if blockers:
            return "blocked_by_config", blockers[0].get(
                "message"
            ) or "训练路径配置异常。"

        if latest_review_action is not None:
            decision = str(latest_review_action.get("decision") or "")
            if decision == "approve":
                return "approved", "培训负责人已确认达标。"
            if decision == "require_retraining":
                task_status = _retraining_task_status(latest_review_action)
                if task_status != "completed":
                    return "needs_remediation", "培训负责人已要求重练。"
            if decision == "mark_manual_follow_up":
                return "manual_follow_up", "已标记需人工跟进，下一阶段暂不开放。"

        modules = self._pre_realtime_modules(journey)
        if any(
            str(module.get("status") or "") in AI_EVALUATING_STATUSES
            for module in modules
        ):
            return "ai_evaluating", "有提交物正在评分或等待人工判断。"
        if any(
            module.get("passed") is False
            or str(module.get("status") or "") in {"failed", "needs_remediation"}
            for module in modules
        ):
            return "needs_remediation", "存在 AI/规则初评未达标的关键训练项。"
        required = [module for module in modules if module.get("required") is True]
        if required and all(
            module.get("completion_satisfied") is True for module in required
        ):
            return "pending_review", "关键训练证据已齐，等待培训负责人复核。"
        if str(journey.get("training_stage") or "") == "not_started":
            return "not_started", "新人尚未开始关键训练。"
        return "in_training", "新人仍在训练过程中。"

    def _realtime_gate(
        self,
        journey: dict[str, Any],
        readiness_status: ReadinessStatus,
    ) -> dict[str, Any]:
        module = next(
            (
                item
                for item in journey.get("modules") or []
                if item.get("kind") == "realtime_roleplay"
            ),
            None,
        )
        if module is None:
            return {
                "module_key": None,
                "status": "not_configured",
                "locked": True,
                "reason": "训练路径未配置真实语音对练入口。",
                "training_gate_status": readiness_status,
                "provider_readiness": None,
            }
        provider_readiness = _provider_readiness(module)
        training_allowed = readiness_status == "approved"
        locked = bool(module.get("locked")) or not training_allowed
        reason = None
        if not training_allowed:
            reason = "前置训练尚未由培训负责人确认达标。"
        elif module.get("locked"):
            reason = module.get("block_reason") or "真实语音对练暂未开放。"
        return {
            "module_key": module.get("module_key"),
            "status": module.get("status"),
            "locked": locked,
            "reason": reason,
            "training_gate_status": readiness_status,
            "provider_readiness": provider_readiness,
        }

    def _next_actions(
        self,
        *,
        status: ReadinessStatus,
        learner_id: str,
        weak_capability_keys: list[str],
        realtime_gate: dict[str, Any],
    ) -> list[dict[str, Any]]:
        detail_path = f"/admin/sales-trainer/readiness/{learner_id}"
        if status == "pending_review":
            return [
                {
                    "action_key": "review_dossier",
                    "label": "复核训练档案",
                    "target_path": detail_path,
                    "primary": True,
                }
            ]
        if status == "needs_remediation":
            return [
                {
                    "action_key": "require_retraining",
                    "label": "要求重练",
                    "target_path": detail_path,
                    "primary": True,
                    "capability_keys": weak_capability_keys,
                }
            ]
        if status == "blocked_by_config":
            return [
                {
                    "action_key": "fix_configuration",
                    "label": "修复训练配置",
                    "target_path": "/admin/sales-trainer/paths",
                    "primary": True,
                }
            ]
        if status == "approved" and not realtime_gate.get("locked"):
            return [
                {
                    "action_key": "enter_next_stage",
                    "label": "下一阶段已开放",
                    "target_path": detail_path,
                    "primary": False,
                }
            ]
        return [
            {
                "action_key": "view_dossier",
                "label": "查看训练档案",
                "target_path": detail_path,
                "primary": False,
            }
        ]

    def _workbench_groups(
        self,
        dossiers: list[dict[str, Any]],
    ) -> dict[WorkbenchGroupKey, dict[str, Any]]:
        groups: dict[WorkbenchGroupKey, dict[str, Any]] = {
            "pending_review": self._empty_group("pending_review", "待复核"),
            "not_passed": self._empty_group("not_passed", "未达标"),
            "needs_retraining": self._empty_group("needs_retraining", "需重练"),
            "approved": self._empty_group("approved", "已达标"),
            "config_exception": self._empty_group("config_exception", "配置异常"),
            "in_training": self._empty_group("in_training", "训练中"),
        }
        for dossier in dossiers:
            key = self._group_for_dossier(dossier)
            groups[key]["items"].append(self._workbench_item(dossier))
        for group in groups.values():
            group["count"] = len(group["items"])
        return groups

    @staticmethod
    def _empty_group(key: WorkbenchGroupKey, label: str) -> dict[str, Any]:
        return {"group_key": key, "label": label, "count": 0, "items": []}

    @staticmethod
    def _group_for_dossier(dossier: dict[str, Any]) -> WorkbenchGroupKey:
        latest = dossier.get("latest_review_action") or {}
        if (
            str(latest.get("decision") or "") == "require_retraining"
            and _retraining_task_status(latest) != "completed"
        ):
            return "needs_retraining"
        status = str(dossier.get("status") or "")
        if status == "blocked_by_config":
            return "config_exception"
        if status == "approved":
            return "approved"
        if status == "pending_review":
            return "pending_review"
        if status in {"needs_remediation", "rejected", "manual_follow_up"}:
            return "not_passed"
        return "in_training"

    @staticmethod
    def _workbench_item(dossier: dict[str, Any]) -> dict[str, Any]:
        weak_capabilities = [
            item
            for item in dossier.get("competencies", [])
            if item.get("status") in {"ai_failed", "needs_retraining", "pending_review"}
        ]
        next_action = (dossier.get("next_actions") or [{}])[0]
        return {
            "learner": dossier.get("learner"),
            "status": dossier.get("status"),
            "status_label": dossier.get("status_label"),
            "status_reason": dossier.get("status_reason"),
            "path": dossier.get("path"),
            "weak_capability_keys": [
                item.get("capability_key") for item in weak_capabilities
            ],
            "weak_capability_labels": [
                item.get("display_name") for item in weak_capabilities
            ],
            "evidence_count": dossier.get("summary", {}).get("evidence_count", 0),
            "latest_review_action": dossier.get("latest_review_action"),
            "next_action": next_action,
            "target_path": next_action.get("target_path"),
        }

    def _config_blockers(self, journey: dict[str, Any]) -> list[dict[str, Any]]:
        blockers = []
        for diagnostic in self._diagnostics(journey, include_realtime=False):
            if (
                diagnostic.get("terminal") is True
                and str(diagnostic.get("code") or "") in CONFIG_BLOCKER_CODES
            ):
                blockers.append(diagnostic)
        return blockers

    @staticmethod
    def _diagnostics(
        journey: dict[str, Any],
        *,
        include_realtime: bool = True,
    ) -> list[dict[str, Any]]:
        diagnostics = list(journey.get("diagnostics") or [])
        for module in journey.get("modules") or []:
            if not include_realtime and module.get("kind") == "realtime_roleplay":
                continue
            diagnostics.extend(module.get("diagnostics") or [])
            diagnostics.extend(module.get("unmet_reasons") or [])
        return [item for item in diagnostics if isinstance(item, dict)]

    @staticmethod
    def _pre_realtime_modules(journey: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            module
            for module in journey.get("modules") or []
            if module.get("kind") != "realtime_roleplay"
        ]

    @staticmethod
    def _default_review_evidence_ids(dossier: dict[str, Any]) -> list[str]:
        risk = [
            str(item["evidence_id"])
            for item in dossier.get("evidence", [])
            if item.get("passed") is False
            or str(item.get("status") or "") in RISK_STATUSES
        ]
        if risk:
            return risk[:10]
        return [
            str(item["evidence_id"])
            for item in dossier.get("evidence", [])[:10]
            if item.get("evidence_id")
        ]

    @staticmethod
    def _default_review_capability_keys(dossier: dict[str, Any]) -> list[str]:
        keys = [
            str(item["capability_key"])
            for item in dossier.get("competencies", [])
            if item.get("status") in {"ai_failed", "pending_review", "needs_retraining"}
        ]
        if keys:
            return keys
        return [
            str(item["capability_key"])
            for item in dossier.get("competencies", [])
            if item.get("status") in {"ai_passed", "approved"}
        ]

    @staticmethod
    def _review_action_payload(log: Any) -> dict[str, Any]:
        metadata = log.metadata_json if isinstance(log.metadata_json, dict) else {}
        decision = str(metadata.get("decision") or "mark_manual_follow_up")
        return {
            "action_id": str(log.log_id),
            "audit_log_id": str(log.log_id),
            "decision": decision,
            "decision_label": metadata.get("decision_label")
            or decision_label(decision),
            "reason": metadata.get("reason"),
            "capability_keys": unique_non_empty(metadata.get("capability_keys") or []),
            "source_evidence_ids": unique_non_empty(
                metadata.get("source_evidence_ids") or []
            ),
            "reviewer_id": str(log.actor_id) if log.actor_id else None,
            "reviewer_role": log.actor_role,
            "created_at": log.created_at,
            "retraining_task": metadata.get("retraining_task"),
            "state_storage": metadata.get("state_storage") or "operation_log",
        }

    @staticmethod
    def _blocked_journey(
        learner: User,
        *,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "journey_id": f"{learner.user_id}:blocked",
            "learner_id": str(learner.user_id),
            "learner_name": learner.name,
            "department": learner.department,
            "path_key": "newcomer_training_path_v1",
            "path_revision_id": None,
            "path_revision_no": None,
            "source": "active_revision",
            "training_stage": "error_terminal",
            "modules": [],
            "overall_progress": {
                "total_modules": 0,
                "completed_modules": 0,
                "passed_modules": 0,
                "failed_modules": 0,
                "needs_remediation_modules": 0,
            },
            "diagnostics": [
                {
                    "code": code,
                    "message": message,
                    "severity": "error",
                    "terminal": True,
                }
            ],
            "generated_at": datetime.now(UTC),
        }


def _provider_readiness(module: dict[str, Any]) -> dict[str, Any] | None:
    source = module.get("source")
    if isinstance(source, dict):
        runtime = source.get("runtime_binding") or source.get("runtime_registry")
        if isinstance(runtime, dict):
            return cast(dict[str, Any], runtime.get("provider_readiness_snapshot"))
    return None


def _record_detail_path(record_type: str, record_id: str) -> str | None:
    if record_type == "regrade" or not record_id:
        return None
    return f"/admin/sales-trainer/training-records/{record_type}/{record_id}"


def _learning_topic_detail_path(topic_key: str) -> str | None:
    if topic_key == "business_etiquette":
        return "/sales-trainer/learning-topics/business-etiquette"
    return None


def _compact_snapshot(
    value: Any,
    *,
    keys: tuple[str, ...],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {key: value.get(key) for key in keys if value.get(key) is not None}


def _scoring_snapshot(record: dict[str, Any]) -> dict[str, Any] | None:
    snapshot = _compact_snapshot(
        record.get("score_scheme_snapshot"),
        keys=(
            "score_scheme_id",
            "score_scheme_revision_id",
            "scoring_prompt_id",
            "scoring_prompt_revision_id",
            "pass_threshold",
            "max_score",
            "title",
        ),
    )
    if snapshot:
        return snapshot
    explanation = record.get("score_explanation")
    if not isinstance(explanation, dict):
        return None
    return {
        "basis": explanation.get("basis"),
        "summary": explanation.get("summary"),
        "dimension_count": len(explanation.get("dimensions") or []),
    }


def _record_result_summary(
    record: dict[str, Any],
    outcome: dict[str, Any],
) -> str | None:
    explanation = record.get("score_explanation")
    if isinstance(explanation, dict) and explanation.get("summary"):
        return str(explanation["summary"])
    status = outcome.get("status") or record.get("status")
    score = (
        outcome.get("score")
        if outcome.get("score") is not None
        else record.get("score")
    )
    max_score = (
        outcome.get("max_score")
        if outcome.get("max_score") is not None
        else record.get("max_score")
    )
    if score is not None and max_score is not None:
        return f"状态 {status}，得分 {score}/{max_score}。"
    if status:
        return f"状态 {status}。"
    return None


def _learning_topic_result_summary(unit: dict[str, Any]) -> str | None:
    title = str(unit.get("title") or "学习单元")
    status = str(unit.get("status") or "")
    score = unit.get("score")
    max_score = unit.get("max_score")
    if score is not None and max_score is not None:
        return f"{title}：状态 {status}，得分 {score}/{max_score}。"
    if status:
        return f"{title}：状态 {status}。"
    return title


def _retraining_task_status(action: dict[str, Any] | None) -> str | None:
    if not action:
        return None
    task = action.get("retraining_task")
    if not isinstance(task, dict):
        return None
    return str(task.get("status") or "pending")


def _evidence_after_review(
    evidence: list[dict[str, Any]],
    *,
    reviewed_at: datetime | None,
    source_evidence_ids: list[str],
    capability_keys: list[str],
) -> list[dict[str, Any]]:
    source_ids = set(source_evidence_ids)
    capability_set = set(capability_keys)
    matched: list[dict[str, Any]] = []
    for item in evidence:
        evidence_id = str(item.get("evidence_id") or "")
        if evidence_id and evidence_id in source_ids:
            continue
        item_capabilities = {str(key) for key in item.get("capability_keys") or []}
        if capability_set and not capability_set.intersection(item_capabilities):
            continue
        submitted_at = _datetime_or_none(item.get("submitted_at")) or _datetime_or_none(
            item.get("completed_at")
        )
        if submitted_at is None:
            continue
        if reviewed_at is not None and submitted_at <= reviewed_at:
            continue
        matched.append(item)
    matched.sort(
        key=lambda item: _datetime_or_none(item.get("submitted_at"))
        or _datetime_or_none(item.get("completed_at"))
        or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return matched


def _datetime_or_none(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def _status_label(status: str) -> str:
    return {
        "not_started": "未开始",
        "in_training": "训练中",
        "ai_evaluating": "评分中",
        "needs_remediation": "需补练",
        "pending_review": "待复核",
        "approved": "已达标",
        "rejected": "未达标",
        "manual_follow_up": "需人工跟进",
        "blocked_by_config": "配置异常",
    }.get(status, status)
