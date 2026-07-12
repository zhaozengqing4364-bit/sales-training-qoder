"""Deterministic Training Journey policy and analytics projection."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from sales_trainer.services.journey_read_repository import JourneyLearnerProjection

if TYPE_CHECKING:
    from sales_trainer.services.training_journey_service import JourneyModule

TrainingStage = Literal[
    "not_started",
    "in_progress",
    "waiting_upload",
    "processing",
    "scored",
    "passed",
    "failed",
    "needs_remediation",
    "manual_review",
    "disabled",
    "archived",
    "error_terminal",
    "error_transient",
]

RISK_MODULE_STATUSES: frozenset[str] = frozenset(
    {
        "failed",
        "needs_remediation",
        "manual_review",
        "error_terminal",
        "error_transient",
    }
)
TRAINING_STAGE_VALUES: frozenset[str] = frozenset(
    {
        "not_started",
        "in_progress",
        "waiting_upload",
        "processing",
        "scored",
        "passed",
        "failed",
        "needs_remediation",
        "manual_review",
        "disabled",
        "archived",
        "error_terminal",
        "error_transient",
    }
)


class TrainingJourneyProjection:
    @staticmethod
    def _module_stage(
        module: JourneyModule,
        latest: dict[str, Any] | None,
    ) -> TrainingStage:
        if module.locked:
            return module.lock_status
        if latest is None:
            return "not_started"
        status = latest.get("status")
        if isinstance(status, str) and status in TRAINING_STAGE_VALUES:
            return cast(TrainingStage, status)
        return "not_started"

    @staticmethod
    def _completion_satisfied(
        module: JourneyModule,
        latest: dict[str, Any] | None,
    ) -> bool:
        if module.locked or latest is None:
            return False
        status = latest.get("status")
        if status in {
            "error_terminal",
            "error_transient",
            "not_started",
            "in_progress",
        }:
            return False
        if latest.get("passed") is False:
            return False
        if module.completion_rule == "passed":
            return latest.get("passed") is True
        if module.completion_rule == "submitted":
            return bool(latest.get("submitted_at") or latest.get("completed_at"))
        if module.completion_rule == "scored":
            return status in {"scored", "passed", "failed"}
        return False

    @staticmethod
    def _next_action(
        module: JourneyModule,
        status: TrainingStage,
    ) -> dict[str, Any] | None:
        if module.kind == "audio_submission":
            target_path = _module_practice_path(module)
            action_key = (
                "retry_audio_submission"
                if status in {"scored", "passed", "failed", "needs_remediation"}
                else "start_audio_submission"
            )
            if module.locked or target_path is None:
                return {
                    "action_key": action_key,
                    "label": "上传录音",
                    "target_path": target_path,
                    "disabled": True,
                    "disabled_reason": module.block_reason or "该录音训练暂不可用。",
                }
            return {
                "action_key": action_key,
                "label": "重新上传录音"
                if action_key == "retry_audio_submission"
                else "上传录音",
                "target_path": target_path,
                "disabled": False,
                "disabled_reason": None,
            }
        if module.kind == "quiz_attempt":
            target_path = _module_practice_path(module)
            action_key = (
                "retry_quiz_attempt"
                if status in {"scored", "passed", "failed", "needs_remediation"}
                else "start_quiz_attempt"
            )
            default_label = (
                "重新学习并答题"
                if module.base_module_key == "business_skills"
                else "重新答题"
            )
            start_label = (
                "学习并答题"
                if module.base_module_key == "business_skills"
                else "开始答题"
            )
            if module.locked or target_path is None:
                return {
                    "action_key": action_key,
                    "label": start_label,
                    "target_path": target_path,
                    "disabled": True,
                    "disabled_reason": module.block_reason or "该答题训练暂不可用。",
                }
            return {
                "action_key": action_key,
                "label": default_label
                if action_key == "retry_quiz_attempt"
                else start_label,
                "target_path": target_path,
                "disabled": False,
                "disabled_reason": None,
            }
        if module.kind == "ai_coach":
            target_path = (
                "/sales-trainer/business-skills/coach"
                if module.base_module_key == "business_skills"
                else None
            )
            action_key = (
                "start_ai_coach" if status == "not_started" else "continue_ai_coach"
            )
            if module.locked or target_path is None:
                return {
                    "action_key": action_key,
                    "label": "进入 AI 教练",
                    "target_path": target_path,
                    "disabled": True,
                    "disabled_reason": module.block_reason or "AI Coach 暂不可用。",
                }
            return {
                "action_key": action_key,
                "label": "继续 AI 教练"
                if status in {"in_progress", "failed", "needs_remediation"}
                else "进入 AI 教练",
                "target_path": target_path,
                "disabled": False,
                "disabled_reason": None,
            }
        if module.kind == "realtime_roleplay" and module.locked:
            return {
                "action_key": "start_realtime_roleplay",
                "label": "开始实时对练",
                "target_path": None,
                "disabled": True,
                "disabled_reason": module.block_reason or "实时对练暂不可用。",
            }
        if module.kind == "realtime_roleplay":
            return {
                "action_key": "start_realtime_roleplay",
                "label": "再次对练"
                if status in {"scored", "passed", "failed"}
                else "开始实时对练",
                "target_path": None,
                "disabled": False,
                "disabled_reason": None,
            }
        return None

    @staticmethod
    def _overall_progress(modules: list[dict[str, Any]]) -> dict[str, int]:
        completed = [
            module
            for module in modules
            if module["status"] in {"passed", "failed", "scored"}
        ]
        return {
            "total_modules": len(modules),
            "completed_modules": len(completed),
            "passed_modules": sum(1 for module in modules if module["passed"] is True),
            "failed_modules": sum(1 for module in modules if module["passed"] is False),
            "needs_remediation_modules": sum(
                1
                for module in modules
                if module["status"] in {"failed", "needs_remediation"}
            ),
        }

    @staticmethod
    def _journey_stage(
        modules: list[dict[str, Any]],
        path_enabled: bool,
    ) -> TrainingStage:
        if not path_enabled:
            return "disabled"
        required = [module for module in modules if module["required"]]
        stage_modules = required or modules
        if any(module["status"] == "error_terminal" for module in stage_modules):
            return "error_terminal"
        if any(module["passed"] is False for module in stage_modules):
            return "needs_remediation"
        if required and all(
            module["completion_satisfied"] is True for module in required
        ):
            return "passed"
        if any(module["latest_outcome"] is not None for module in stage_modules):
            return "in_progress"
        return "not_started"

    @staticmethod
    def _journey_diagnostics(
        path_enabled: bool,
        modules: list[JourneyModule],
    ) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        if not path_enabled:
            diagnostics.append(
                TrainingJourneyProjection._diagnostic(
                    "[NEWCOMER_PATH_CONFIG_MISSING]",
                    "active path revision 当前未启用。",
                    terminal=True,
                )
            )
        if not modules:
            diagnostics.append(
                TrainingJourneyProjection._diagnostic(
                    "[NEWCOMER_PATH_CONFIG_MISSING]",
                    "active path revision 没有可投影模块。",
                    terminal=True,
                )
            )
        return diagnostics

    @staticmethod
    def _journeys_with_module_scope(
        journeys: list[dict[str, Any]],
        module_key: str | None,
    ) -> list[dict[str, Any]]:
        if not module_key:
            return journeys
        scoped_journeys: list[dict[str, Any]] = []
        for journey in journeys:
            scoped = dict(journey)
            scoped["modules"] = [
                module
                for module in journey.get("modules") or []
                if module.get("module_key") == module_key
            ]
            scoped_journeys.append(scoped)
        return scoped_journeys

    @staticmethod
    def _analytics_summary(
        journeys: list[dict[str, Any]],
        total: int,
    ) -> dict[str, Any]:
        passed = [
            journey for journey in journeys if journey["training_stage"] == "passed"
        ]
        risk = [
            journey
            for journey in journeys
            if journey["training_stage"] in {"needs_remediation", "error_terminal"}
        ]
        return {
            "learner_count": total,
            "loaded_learner_count": len(journeys),
            "passed_learner_count": len(passed),
            "risk_learner_count": len(risk),
            "pass_rate": _rate(len(passed), len(journeys)),
        }

    @staticmethod
    def _analytics_funnel(journeys: list[dict[str, Any]]) -> list[dict[str, Any]]:
        order = [
            "not_started",
            "in_progress",
            "processing",
            "needs_remediation",
            "passed",
            "error_terminal",
        ]
        counts = {stage: 0 for stage in order}
        for journey in journeys:
            stage = str(journey.get("training_stage") or "not_started")
            counts[stage] = counts.get(stage, 0) + 1
        return [
            {
                "stage": stage,
                "learner_count": counts.get(stage, 0),
                "rate": _rate(counts.get(stage, 0), len(journeys)),
            }
            for stage in order
            if counts.get(stage, 0) or stage in {"not_started", "passed"}
        ]

    @staticmethod
    def _analytics_modules(journeys: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for journey in journeys:
            for module in journey.get("modules") or []:
                module_key = str(module.get("module_key") or "unknown")
                kind = str(module.get("kind") or module.get("module_type") or "unknown")
                key = f"{module_key}:{kind}"
                bucket = buckets.setdefault(
                    key,
                    {
                        "module_key": module_key,
                        "title": module.get("title") or key,
                        "kind": module.get("kind"),
                        "learner_count": 0,
                        "passed_count": 0,
                        "failed_count": 0,
                        "status_counts": {},
                        "score_sum": 0.0,
                        "score_count": 0,
                    },
                )
                bucket["learner_count"] += 1
                status = str(module.get("status") or "not_started")
                bucket["status_counts"][status] = (
                    bucket["status_counts"].get(status, 0) + 1
                )
                if module.get("passed") is True:
                    bucket["passed_count"] += 1
                if module.get("passed") is False:
                    bucket["failed_count"] += 1
                score = TrainingJourneyProjection._float_or_none(module.get("score"))
                if score is not None:
                    bucket["score_sum"] += score
                    bucket["score_count"] += 1
        return [
            {
                "module_key": bucket["module_key"],
                "title": bucket["title"],
                "kind": bucket["kind"],
                "learner_count": bucket["learner_count"],
                "passed_count": bucket["passed_count"],
                "failed_count": bucket["failed_count"],
                "status_counts": bucket["status_counts"],
                "pass_rate": _rate(bucket["passed_count"], bucket["learner_count"]),
                "average_score": (
                    round(bucket["score_sum"] / bucket["score_count"], 2)
                    if bucket["score_count"]
                    else None
                ),
            }
            for bucket in sorted(
                buckets.values(),
                key=lambda item: (
                    -int(item["learner_count"]),
                    str(item["module_key"]),
                    str(item["kind"]),
                ),
            )
        ]

    @staticmethod
    def _analytics_learning_topics(
        journeys: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for journey in journeys:
            for topic in journey.get("learning_topics") or []:
                key = str(topic.get("topic_key") or "unknown")
                bucket = buckets.setdefault(
                    key,
                    {
                        "topic_key": key,
                        "source_module_key": topic.get("source_module_key"),
                        "title": topic.get("title") or key,
                        "learner_count": 0,
                        "completed_count": 0,
                        "needs_remediation_count": 0,
                        "status_counts": {},
                        "unit_score_sum": 0.0,
                        "unit_score_count": 0,
                    },
                )
                bucket["learner_count"] += 1
                status = str(topic.get("status") or "not_started")
                bucket["status_counts"][status] = (
                    bucket["status_counts"].get(status, 0) + 1
                )
                if status == "passed":
                    bucket["completed_count"] += 1
                if status == "needs_remediation":
                    bucket["needs_remediation_count"] += 1
                for unit in topic.get("units") or []:
                    if not isinstance(unit, dict):
                        continue
                    score = TrainingJourneyProjection._float_or_none(unit.get("score"))
                    if score is not None:
                        bucket["unit_score_sum"] += score
                        bucket["unit_score_count"] += 1
        return [
            {
                "topic_key": bucket["topic_key"],
                "source_module_key": bucket["source_module_key"],
                "title": bucket["title"],
                "learner_count": bucket["learner_count"],
                "completed_count": bucket["completed_count"],
                "needs_remediation_count": bucket["needs_remediation_count"],
                "status_counts": bucket["status_counts"],
                "completion_rate": _rate(
                    bucket["completed_count"],
                    bucket["learner_count"],
                ),
                "average_unit_score": (
                    round(bucket["unit_score_sum"] / bucket["unit_score_count"], 2)
                    if bucket["unit_score_count"]
                    else None
                ),
                "blocking_required_path": False,
            }
            for bucket in sorted(
                buckets.values(),
                key=lambda item: (-int(item["learner_count"]), str(item["topic_key"])),
            )
        ]

    @staticmethod
    def _analytics_weakness_heatmap(
        journeys: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for journey in journeys:
            for module in journey.get("modules") or []:
                module_key = str(module.get("module_key") or "unknown")
                kind = str(module.get("kind") or module.get("module_type") or "unknown")
                heatmap_key = f"{module_key}:{kind}"
                bucket = buckets.setdefault(
                    heatmap_key,
                    {
                        "heatmap_key": heatmap_key,
                        "module_key": module_key,
                        "title": module.get("title") or module_key,
                        "kind": kind,
                        "module_type": module.get("module_type"),
                        "learner_count": 0,
                        "risk_count": 0,
                        "passed_count": 0,
                        "status_counts": {},
                        "score_sum": 0.0,
                        "score_count": 0,
                    },
                )
                bucket["learner_count"] += 1
                status = str(module.get("status") or "not_started")
                bucket["status_counts"][status] = (
                    bucket["status_counts"].get(status, 0) + 1
                )
                if module.get("passed") is True:
                    bucket["passed_count"] += 1
                if module.get("passed") is False or status in RISK_MODULE_STATUSES:
                    bucket["risk_count"] += 1
                score = TrainingJourneyProjection._float_or_none(module.get("score"))
                if score is not None:
                    bucket["score_sum"] += score
                    bucket["score_count"] += 1
        return [
            {
                "heatmap_key": bucket["heatmap_key"],
                "module_key": bucket["module_key"],
                "title": bucket["title"],
                "kind": bucket["kind"],
                "module_type": bucket["module_type"],
                "learner_count": bucket["learner_count"],
                "risk_count": bucket["risk_count"],
                "passed_count": bucket["passed_count"],
                "status_counts": bucket["status_counts"],
                "risk_rate": _rate(bucket["risk_count"], bucket["learner_count"]),
                "pass_rate": _rate(bucket["passed_count"], bucket["learner_count"]),
                "average_score": (
                    round(bucket["score_sum"] / bucket["score_count"], 2)
                    if bucket["score_count"]
                    else None
                ),
            }
            for bucket in sorted(
                buckets.values(),
                key=lambda item: (
                    -int(item["risk_count"]),
                    -float(_rate(item["risk_count"], item["learner_count"]) or 0.0),
                    str(item["kind"]),
                    str(item["module_key"]),
                ),
            )
        ]

    @staticmethod
    def _analytics_trend(journeys: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for journey in journeys:
            learner_id = str(journey.get("learner_id") or "")
            for module in journey.get("modules") or []:
                for outcome in module.get("outcome_history") or []:
                    date_key = TrainingJourneyProjection._trend_date_key(
                        outcome.get("completed_at") or outcome.get("submitted_at")
                    )
                    if date_key is None:
                        continue
                    bucket = buckets.setdefault(
                        date_key,
                        {
                            "date": date_key,
                            "outcome_count": 0,
                            "passed_outcome_count": 0,
                            "risk_outcome_count": 0,
                            "learner_ids": set(),
                            "score_sum": 0.0,
                            "score_count": 0,
                        },
                    )
                    bucket["outcome_count"] += 1
                    if learner_id:
                        bucket["learner_ids"].add(learner_id)
                    passed = outcome.get("passed")
                    status = str(outcome.get("status") or "")
                    if passed is True:
                        bucket["passed_outcome_count"] += 1
                    if passed is False or status in RISK_MODULE_STATUSES:
                        bucket["risk_outcome_count"] += 1
                    score = TrainingJourneyProjection._float_or_none(
                        outcome.get("score")
                    )
                    if score is not None:
                        bucket["score_sum"] += score
                        bucket["score_count"] += 1
        return [
            {
                "date": bucket["date"],
                "outcome_count": bucket["outcome_count"],
                "passed_outcome_count": bucket["passed_outcome_count"],
                "risk_outcome_count": bucket["risk_outcome_count"],
                "active_learner_count": len(bucket["learner_ids"]),
                "pass_rate": _rate(
                    bucket["passed_outcome_count"],
                    bucket["outcome_count"],
                ),
                "average_score": (
                    round(bucket["score_sum"] / bucket["score_count"], 2)
                    if bucket["score_count"]
                    else None
                ),
            }
            for bucket in sorted(buckets.values(), key=lambda item: str(item["date"]))
        ]

    @staticmethod
    def _trend_date_key(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            try:
                return (
                    datetime.fromisoformat(normalized.replace("Z", "+00:00"))
                    .date()
                    .isoformat()
                )
            except ValueError:
                return normalized[:10] if len(normalized) >= 10 else normalized
        isoformat = getattr(value, "isoformat", None)
        if callable(isoformat):
            return str(isoformat())[:10]
        return None

    @staticmethod
    def _analytics_group_counts(
        journeys: list[dict[str, Any]],
        *,
        key_fn: Any,
        label_fn: Any,
        source_fn: Any | None = None,
    ) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for journey in journeys:
            key = key_fn(journey)
            bucket = buckets.setdefault(
                key,
                {
                    "key": key,
                    "label": label_fn(journey),
                    "learner_count": 0,
                    "passed_count": 0,
                    "source": source_fn(journey) if source_fn is not None else None,
                },
            )
            bucket["learner_count"] += 1
            if journey.get("training_stage") == "passed":
                bucket["passed_count"] += 1
        for bucket in buckets.values():
            bucket["pass_rate"] = _rate(bucket["passed_count"], bucket["learner_count"])
        return sorted(buckets.values(), key=lambda item: str(item["key"]))

    @staticmethod
    def _analytics_risk_learners(
        journeys: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        risks = []
        for journey in journeys:
            risk_modules = [
                module
                for module in journey.get("modules") or []
                if module.get("passed") is False
                or module.get("status") in RISK_MODULE_STATUSES
            ]
            if not risk_modules:
                continue
            risk_reasons = [
                TrainingJourneyProjection._analytics_risk_reason(module)
                for module in risk_modules
            ]
            risks.append(
                {
                    "learner_id": journey["learner_id"],
                    "learner_name": journey.get("learner_name"),
                    "department": journey.get("department"),
                    "training_stage": journey.get("training_stage"),
                    "risk_reasons": risk_reasons,
                    "risk_module_count": len(risk_modules),
                    "risk_module_keys": [
                        str(module.get("module_key")) for module in risk_modules
                    ],
                }
            )
        return risks[:50]

    @staticmethod
    def _analytics_risk_reason(module: dict[str, Any]) -> str:
        module_key = str(module.get("module_key") or "unknown")
        if module.get("passed") is False:
            return f"{module_key}:not_passed"
        status = str(module.get("status") or "unknown")
        return f"{module_key}:status:{status}"

    @staticmethod
    def _default_learner_level_policy() -> dict[str, Any]:
        return {
            "version": "sales_trainer_learner_level_policy_v1",
            "default_level": {
                "key": "unassigned",
                "label": "未分层",
                "rank": 0,
                "description": "未发布学员等级规则时的安全默认分层。",
            },
            "levels": [
                {
                    "key": "unassigned",
                    "label": "未分层",
                    "rank": 0,
                    "description": "未发布学员等级规则时的安全默认分层。",
                }
            ],
            "rules": [],
        }

    @staticmethod
    def _default_role_level_policy() -> dict[str, Any]:
        return {
            "version": "sales_trainer_role_level_policy_v1",
            "default_level": {
                "key": "learner",
                "label": "普通学员",
                "rank": 0,
                "description": "未发布组织角色等级规则时的安全默认角色等级。",
            },
            "levels": [
                {
                    "key": "learner",
                    "label": "普通学员",
                    "rank": 0,
                    "description": "未发布组织角色等级规则时的安全默认角色等级。",
                }
            ],
            "rules": [
                {
                    "key": "default_user_role",
                    "level_key": "learner",
                    "priority": 1,
                    "enabled": True,
                    "conditions": {"role_in": ["user"]},
                }
            ],
        }

    @staticmethod
    def _learner_level_payload(
        *,
        policy: dict[str, Any],
        level: dict[str, Any],
        source: str,
        config_revision_id: str | None,
        fallback_applied: bool,
        fallback_reason: str | None,
        policy_key: str,
        management_entry: str,
    ) -> dict[str, Any]:
        return {
            "level_key": str(level.get("key") or "unassigned"),
            "label": str(level.get("label") or "未分层"),
            "source": source,
            "rank": int(level.get("rank") or 0),
            "effective_from": None,
            "effective_to": None,
            "config_revision_id": config_revision_id,
            "description": level.get("description"),
            "fallback_applied": fallback_applied,
            "fallback_reason": fallback_reason,
            "policy_key": policy_key,
            "policy_version": policy.get("version"),
            "management_entry": management_entry,
        }

    @staticmethod
    def _match_learner_level(
        *,
        policy: dict[str, Any],
        learner: JourneyLearnerProjection,
        training_stage: str,
        overall: dict[str, Any],
    ) -> dict[str, Any]:
        levels = {
            str(level.get("key")): level
            for level in policy.get("levels", [])
            if isinstance(level, dict) and level.get("key")
        }
        default_level = policy.get("default_level")
        if not isinstance(default_level, dict):
            default_level = {"key": "unassigned", "label": "未分层", "rank": 0}

        for rule in policy.get("rules", []):
            if not isinstance(rule, dict) or rule.get("enabled") is False:
                continue
            conditions = rule.get("conditions")
            if not isinstance(conditions, dict):
                continue
            if TrainingJourneyProjection._learner_level_conditions_match(
                conditions=conditions,
                learner=learner,
                training_stage=training_stage,
                overall=overall,
            ):
                level_key = str(rule.get("level_key") or "")
                return levels.get(level_key, default_level)
        return default_level

    @staticmethod
    def _learner_level_conditions_match(
        *,
        conditions: dict[str, Any],
        learner: JourneyLearnerProjection,
        training_stage: str,
        overall: dict[str, Any],
    ) -> bool:
        stage_values = conditions.get("training_stage_in")
        if isinstance(stage_values, list) and training_stage not in {
            str(item) for item in stage_values
        }:
            return False

        department_values = conditions.get("department_in")
        if isinstance(department_values, list) and str(
            learner.department or ""
        ) not in {str(item) for item in department_values}:
            return False

        role_values = conditions.get("role_in")
        if isinstance(role_values, list) and str(learner.role or "") not in {
            str(item) for item in role_values
        }:
            return False

        total_modules = int(overall.get("total_modules") or 0)
        completed_modules = int(overall.get("completed_modules") or 0)
        passed_modules = int(overall.get("passed_modules") or 0)
        failed_modules = int(overall.get("failed_modules") or 0)
        pass_rate = (passed_modules / total_modules * 100) if total_modules else 0.0

        min_pass_rate = conditions.get("min_pass_rate")
        if isinstance(min_pass_rate, (int, float)) and pass_rate < float(min_pass_rate):
            return False

        max_pass_rate = conditions.get("max_pass_rate")
        if isinstance(max_pass_rate, (int, float)) and pass_rate > float(max_pass_rate):
            return False

        min_completed_modules = conditions.get("min_completed_modules")
        if (
            isinstance(min_completed_modules, int)
            and completed_modules < min_completed_modules
        ):
            return False

        min_passed_modules = conditions.get("min_passed_modules")
        if isinstance(min_passed_modules, int) and passed_modules < min_passed_modules:
            return False

        max_failed_modules = conditions.get("max_failed_modules")
        if isinstance(max_failed_modules, int) and failed_modules > max_failed_modules:
            return False

        return True

    @staticmethod
    def _diagnostic(
        code: str,
        message: str,
        *,
        severity: str = "error",
        terminal: bool,
    ) -> dict[str, Any]:
        return {
            "code": code,
            "message": message,
            "severity": severity,
            "terminal": terminal,
        }

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        return float(value) if value is not None else None

    # Explicit application-facing projection interface. The underscored methods
    # remain implementation details so their internal composition can evolve.
    module_stage = _module_stage
    completion_satisfied = _completion_satisfied
    next_action = _next_action
    overall_progress = _overall_progress
    journey_stage = _journey_stage
    journey_diagnostics = _journey_diagnostics
    journeys_with_module_scope = _journeys_with_module_scope
    analytics_summary = _analytics_summary
    analytics_funnel = _analytics_funnel
    analytics_modules = _analytics_modules
    analytics_learning_topics = _analytics_learning_topics
    analytics_weakness_heatmap = _analytics_weakness_heatmap
    analytics_trend = _analytics_trend
    analytics_group_counts = _analytics_group_counts
    analytics_risk_learners = _analytics_risk_learners
    default_learner_level_policy = _default_learner_level_policy
    default_role_level_policy = _default_role_level_policy
    learner_level_payload = _learner_level_payload
    match_learner_level = _match_learner_level
    diagnostic = _diagnostic
    float_or_none = _float_or_none


def _module_practice_path(module: JourneyModule) -> str | None:
    target_unit_id = module.target_unit_id or next(iter(module.target_unit_ids), None)
    if module.kind == "audio_submission" and target_unit_id:
        return f"/sales-trainer/audio/{target_unit_id}"
    if module.kind == "quiz_attempt":
        if module.base_module_key == "business_skills":
            if target_unit_id:
                return f"/sales-trainer/business-skills?unitId={target_unit_id}"
            return "/sales-trainer/business-skills"
        if target_unit_id:
            return f"/sales-trainer/quiz/{target_unit_id}"
    return None


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)


__all__ = ["TrainingJourneyProjection", "TrainingStage"]
