from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import ValidationError
from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    SALES_TRAINER_LEARNER_LEVEL_POLICY_KEY,
    SALES_TRAINER_ROLE_LEVEL_POLICY_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.typing import json_dict_or_empty
from common.services.runtime_outcome_projection import (
    RuntimeOutcomeProjection,
    RuntimeOutcomeProjectionService,
)
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAudioSubmission,
    SalesTrainerBusinessEtiquetteQuizAttempt,
    SalesTrainerQuizAttempt,
    SalesTrainerRoleplayObservation,
)
from sales_trainer.permissions import (
    can_view_sales_trainer_global_records,
    can_view_sales_trainer_records,
)
from sales_trainer.regrade_models import SalesTrainerRegradeRun
from sales_trainer.schemas import AiCoachConfig, NewcomerPathModuleConfig
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.audio_submission_service import AudioSubmissionService
from sales_trainer.services.journey_read_repository import (
    JourneyLearnerProjection,
    JourneyReadRepository,
    JourneyRoleplaySessionProjection,
    JourneyViewer,
)
from sales_trainer.services.journey_sqlalchemy_adapter import (
    SqlAlchemyJourneyReadRepository,
)
from sales_trainer.services.learning_topic_projection_service import (
    LearningTopicProjectionService,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    payload_from_revision,
)
from sales_trainer.services.quiz_service import QuizService
from sales_trainer.services.readiness_state import (
    READINESS_DOSSIER_TARGET_TYPE,
    REVIEW_ACTION_CREATED,
    capability_label,
    module_capability_keys,
    unique_non_empty,
)
from sales_trainer.services.training_journey_projection import (
    TrainingJourneyProjection,
    TrainingStage,
)
from sales_trainer.services.training_record_lineage import (
    TrainingRecordLineageFields,
    training_record_lineage_fields,
)

ROLEPLAY_OBSERVATION_TABLE_NAME = "sales_trainer_roleplay_observations"
ROLEPLAY_OBSERVATION_SCOPE_OWNER = "sales_trainer"
ROLEPLAY_OBSERVATION_MODULE_KEY = "realtime_roleplay"
ROLEPLAY_OBSERVATION_TOP_SIGNAL_LIMIT = 5
ROLEPLAY_OBSERVATION_SOURCES: tuple[str, ...] = ("heuristic", "llm_evaluator")
ROLEPLAY_OBSERVATION_STATUSES: tuple[str, ...] = (
    "pending",
    "completed",
    "failed",
    "ignored",
)

OutcomeRecordType = Literal[
    "audio_submission",
    "quiz_attempt",
    "business_etiquette_quiz_attempt",
    "ai_coach_session",
    "realtime_roleplay_session",
    "regrade",
]


class TrainingJourneyError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(slots=True)
class JourneyModule:
    module_key: str
    base_module_key: str
    title: str
    kind: str
    module_type: str
    order_index: int
    required: bool
    enabled: bool
    completion_rule: str
    target_unit_id: str | None
    target_unit_ids: tuple[str, ...] = ()
    capability_keys: tuple[str, ...] = ()
    learning_content_id: str | None = None
    exam_paper_id: str | None = None
    learning_unit_keys: tuple[str, ...] = ()
    learner_level_required: tuple[str, ...] = ()
    locked: bool = False
    block_reason: str | None = None
    lock_status: TrainingStage = "error_terminal"
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


class TrainingJourneyService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        read_repository: JourneyReadRepository | None = None,
        projection: TrainingJourneyProjection | None = None,
    ) -> None:
        self._db = db
        self._read_repository = read_repository or SqlAlchemyJourneyReadRepository(db)
        self._projection = projection or TrainingJourneyProjection()

    async def get_learner_journey(
        self,
        learner_id: str,
        *,
        viewer: JourneyViewer,
    ) -> dict[str, Any]:
        if str(viewer.user_id) != learner_id:
            raise TrainingJourneyError(
                "[TRAINING_JOURNEY_FORBIDDEN]",
                "学员只能查看自己的训练进度。",
                403,
            )
        learner = await self._read_repository.learner(learner_id)
        if learner is None:
            raise TrainingJourneyError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "学员训练记录不存在。",
                404,
            )
        return await self._build_journey(learner=learner, viewer=viewer)

    async def get_admin_journey(
        self,
        learner_id: str,
        *,
        viewer: JourneyViewer,
        team_department: str | None,
    ) -> dict[str, Any]:
        if not can_view_sales_trainer_records(cast(Any, viewer)):
            raise TrainingJourneyError(
                "[ROLE_REQUIRED]",
                "当前账号无权查看学员记录。",
                403,
            )
        learner = await self._read_repository.learner(learner_id)
        if learner is None:
            raise TrainingJourneyError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "学员训练记录不存在。",
                404,
            )
        if (
            team_department is not None
            and str(learner.department or "") != team_department
        ):
            raise TrainingJourneyError(
                "[TRAINING_RECORD_NOT_FOUND]",
                "学员训练记录不存在。",
                404,
            )
        return await self._build_journey(learner=learner, viewer=viewer)

    async def list_admin_journeys(
        self,
        *,
        viewer: JourneyViewer,
        team_department: str | None,
        department: str | None = None,
        training_stage: str | None = None,
        module_key: str | None = None,
        learner_level: str | None = None,
        role_level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        if not can_view_sales_trainer_records(cast(Any, viewer)):
            raise TrainingJourneyError(
                "[ROLE_REQUIRED]",
                "当前账号无权查看学员记录。",
                403,
            )
        filtered, raw_total = await self._filtered_admin_journeys(
            viewer=viewer,
            team_department=team_department,
            department=department,
            training_stage=training_stage,
            module_key=module_key,
            learner_level=learner_level,
            role_level=role_level,
            limit=offset + limit,
        )
        page = filtered[offset : offset + limit]
        return {
            "items": page,
            "total": len(filtered)
            if (training_stage or module_key or learner_level or role_level)
            else raw_total,
            "limit": limit,
            "offset": offset,
        }

    async def get_admin_analytics(
        self,
        *,
        viewer: JourneyViewer,
        team_department: str | None,
        department: str | None = None,
        training_stage: str | None = None,
        module_key: str | None = None,
        learner_level: str | None = None,
        role_level: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        journeys, raw_total = await self._filtered_admin_journeys(
            viewer=viewer,
            team_department=team_department,
            department=department,
            training_stage=training_stage,
            module_key=module_key,
            learner_level=learner_level,
            role_level=role_level,
            limit=limit,
        )
        filtered_total = (
            len(journeys)
            if (training_stage or module_key or learner_level or role_level)
            else raw_total
        )
        loaded_journeys = journeys
        module_scoped_journeys = self._projection._journeys_with_module_scope(
            loaded_journeys,
            module_key,
        )
        additive_observation = await self._analytics_additive_observation(
            journeys=loaded_journeys,
            module_key=module_key,
        )
        return {
            "generated_at": datetime.now(UTC),
            "summary": self._projection._analytics_summary(
                loaded_journeys, filtered_total
            ),
            "funnel": self._projection._analytics_funnel(loaded_journeys),
            "module_summaries": self._projection._analytics_modules(
                module_scoped_journeys
            ),
            "learning_topic_summaries": self._projection._analytics_learning_topics(
                loaded_journeys
            ),
            "weakness_heatmap": self._projection._analytics_weakness_heatmap(
                module_scoped_journeys
            ),
            "trend_data": self._projection._analytics_trend(module_scoped_journeys),
            "learner_level_summaries": self._projection._analytics_group_counts(
                loaded_journeys,
                key_fn=lambda journey: str(journey["learner_level"]["level_key"]),
                label_fn=lambda journey: str(journey["learner_level"]["label"]),
                source_fn=lambda journey: str(journey["learner_level"]["source"]),
            ),
            "role_level_summaries": self._projection._analytics_group_counts(
                loaded_journeys,
                key_fn=lambda journey: str(journey["role_level"]["level_key"]),
                label_fn=lambda journey: str(journey["role_level"]["label"]),
                source_fn=lambda journey: str(journey["role_level"]["source"]),
            ),
            "risk_learners": self._projection._analytics_risk_learners(
                module_scoped_journeys
            ),
            "additive_observation": additive_observation,
            "filters": {
                "department": team_department or department,
                "training_stage": training_stage,
                "module_key": module_key,
                "learner_level": learner_level,
                "role_level": role_level,
                "limit": limit,
            },
        }

    async def _filtered_admin_journeys(
        self,
        *,
        viewer: JourneyViewer,
        team_department: str | None,
        department: str | None,
        training_stage: str | None,
        module_key: str | None,
        learner_level: str | None,
        role_level: str | None,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        learners, raw_total = await self._list_learners_for_admin(
            team_department=team_department,
            department=department,
            limit=limit,
        )
        journeys: list[dict[str, Any]] = []
        for learner in learners:
            journey = await self._build_journey(learner=learner, viewer=viewer)
            if not _journey_matches_filters(
                journey,
                training_stage=training_stage,
                module_key=module_key,
                learner_level=learner_level,
                role_level=role_level,
            ):
                continue
            journeys.append(journey)
            if len(journeys) >= limit:
                break
        return journeys, raw_total

    async def _list_learners_for_admin(
        self,
        *,
        team_department: str | None,
        department: str | None,
        limit: int | None = None,
    ) -> tuple[list[JourneyLearnerProjection], int]:
        page = await self._read_repository.learners(
            team_department=team_department,
            department=department,
            limit=limit,
        )
        return list(page.items), page.total

    async def _build_journey(
        self,
        *,
        learner: JourneyLearnerProjection,
        viewer: JourneyViewer,
    ) -> dict[str, Any]:
        active = await SalesTrainerAssetRevisionService(self._db).active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        if active is None:
            raise TrainingJourneyError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "新人训练路径缺少 active revision，禁止回退到旧目录生成训练进度。",
                409,
            )
        path_payload = payload_from_revision(active)
        modules = self._journey_modules(path_payload.modules)
        learning_topics = await LearningTopicProjectionService(self._db).learner_topics(
            user_id=str(learner.user_id)
        )
        modules = self._without_learning_topic_source_modules(modules, learning_topics)
        outcomes = await self._outcomes_for_active_revision(
            learner_id=str(learner.user_id),
            path_revision_id=str(active.revision_id),
            path_revision_no=int(active.revision_no),
            modules=modules,
        )
        initial_module_payloads = [
            self._module_payload(
                module, outcomes.get(self._bucket_key(module), []), active
            )
            for module in modules
        ]
        initial_overall = self._projection._overall_progress(initial_module_payloads)
        initial_training_stage = self._projection._journey_stage(
            initial_module_payloads,
            path_payload.enabled,
        )
        learner_level = await self._learner_level(
            learner=learner,
            training_stage=initial_training_stage,
            overall=initial_overall,
        )
        role_level = await self._role_level(
            learner=learner,
            training_stage=initial_training_stage,
            overall=initial_overall,
        )
        self._apply_learner_level_required(modules, learner_level)
        module_payloads = [
            self._module_payload(
                module, outcomes.get(self._bucket_key(module), []), active
            )
            for module in modules
        ]
        overall = self._projection._overall_progress(module_payloads)
        diagnostics = self._projection._journey_diagnostics(
            path_payload.enabled, modules
        )
        training_stage = self._projection._journey_stage(
            module_payloads, path_payload.enabled
        )
        retraining_requests = await self._retraining_requests(
            learner_id=str(learner.user_id),
            modules=module_payloads,
            learning_topics=learning_topics,
        )
        return {
            "journey_id": (
                f"{learner.user_id}:{path_payload.path_key}:{active.revision_id}"
            ),
            "learner_id": str(learner.user_id),
            "learner_name": learner.name,
            "department": learner.department,
            "path_key": path_payload.path_key,
            "path_revision_id": str(active.revision_id),
            "path_revision_no": int(active.revision_no),
            "source": "active_revision",
            "legacy_snapshot_only": False,
            "role_capabilities": self._role_capabilities(viewer, learner),
            "learner_level": learner_level,
            "role_level": role_level,
            "training_stage": training_stage,
            "modules": module_payloads,
            "learning_topics": learning_topics,
            "overall_progress": overall,
            "retraining_requests": retraining_requests,
            "diagnostics": diagnostics,
            "generated_at": datetime.now(UTC),
        }

    def _journey_modules(
        self,
        path_modules: list[NewcomerPathModuleConfig],
    ) -> list[JourneyModule]:
        modules: list[JourneyModule] = []
        for module in sorted(path_modules, key=lambda item: item.order_index):
            modules.append(
                self._base_module(
                    module,
                    required=module.module_key != "business_skills",
                )
            )
            ai_module = self._ai_coach_module(module)
            if ai_module is not None:
                modules.append(ai_module)
        return modules

    def _without_learning_topic_source_modules(
        self,
        modules: list[JourneyModule],
        learning_topics: list[dict[str, Any]],
    ) -> list[JourneyModule]:
        source_module_keys = {
            str(topic.get("source_module_key") or "")
            for topic in learning_topics
            if topic.get("source_module_key")
        }
        if not source_module_keys:
            return modules
        return [
            module
            for module in modules
            if module.base_module_key not in source_module_keys
            and module.module_key not in source_module_keys
        ]

    def _base_module(
        self,
        module: NewcomerPathModuleConfig,
        *,
        required: bool = True,
    ) -> JourneyModule:
        kind = self._kind_for_module_type(module.module_type)
        diagnostics: list[dict[str, Any]] = []
        locked = not module.enabled
        block_reason = module.disabled_reason if locked else None
        lock_status: TrainingStage = "disabled" if locked else "error_terminal"
        if module.module_type == "realtime_placeholder":
            kind = "realtime_roleplay"
            locked = True
            lock_status = "disabled"
            block_reason = module.disabled_reason or "实时对练运行时尚未接入。"
            diagnostics.append(
                self._projection._diagnostic(
                    "[NEWCOMER_REALTIME_BINDING_INVALID]",
                    "实时对练缺少受治理的 runtime binding，当前只返回 unsupported 状态。",
                    terminal=True,
                )
            )
        elif module.module_type == "realtime_roleplay":
            kind = "realtime_roleplay"
            locked = True
            if not module.enabled:
                block_reason = module.disabled_reason or "实时对练未启用。"
            elif module.runtime_binding is None:
                block_reason = "实时对练缺少 runtime binding。"
                lock_status = "error_terminal"
                diagnostics.append(
                    self._projection._diagnostic(
                        "[NEWCOMER_REALTIME_BINDING_INVALID]",
                        "active path revision 中该模块缺少受治理的 runtime binding。",
                        terminal=True,
                    )
                )
            elif not module.runtime_binding.provider_readiness_snapshot.ready:
                block_reason = "实时对练 provider readiness 未通过。"
                lock_status = "error_terminal"
                diagnostics.append(
                    self._projection._diagnostic(
                        "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]",
                        "实时对练 provider readiness 未通过，learner 不得进入运行时。",
                        terminal=True,
                    )
                )
            else:
                locked = False
                block_reason = None
                lock_status = "error_terminal"
        elif module.enabled and not self._target_unit_ids(module):
            locked = True
            block_reason = "模块缺少 target_unit_id 绑定。"
            lock_status = "error_terminal"
            diagnostics.append(
                self._projection._diagnostic(
                    "[NEWCOMER_MODULE_BINDING_MISSING]",
                    "active path revision 中该模块缺少目标训练单元绑定。",
                    terminal=True,
                )
            )
        return JourneyModule(
            module_key=module.module_key,
            base_module_key=module.module_key,
            title=module.title,
            kind=kind,
            module_type=module.module_type,
            order_index=module.order_index,
            required=required,
            enabled=module.enabled,
            completion_rule=module.completion_rule,
            target_unit_id=module.target_unit_id,
            target_unit_ids=self._target_unit_ids(module),
            capability_keys=tuple(module.capability_keys),
            learning_content_id=module.learning_content_id,
            exam_paper_id=module.exam_paper_id,
            learning_unit_keys=tuple(
                unit.unit_key for unit in module.learning_units if unit.enabled
            ),
            learner_level_required=tuple(module.learner_level_required),
            locked=locked,
            block_reason=block_reason,
            lock_status=lock_status,
            diagnostics=diagnostics,
        )

    def _ai_coach_module(
        self,
        module: NewcomerPathModuleConfig,
    ) -> JourneyModule | None:
        if module.ai_coach is None:
            return None
        locked = False
        block_reason = None
        diagnostics: list[dict[str, Any]] = []
        try:
            ai_coach = AiCoachConfig.model_validate(module.ai_coach)
        except ValidationError:
            ai_coach = None
            locked = True
            block_reason = "AI Coach 配置非法。"
            diagnostics.append(
                self._projection._diagnostic(
                    "[AI_COACH_PROMPT_CONFIG_INVALID]",
                    "AI Coach 配置非法，不能作为已完成训练。",
                    terminal=True,
                )
            )
        if (
            ai_coach is not None
            and ai_coach.enabled
            and not ai_coach.prompt_template_id
        ):
            locked = True
            block_reason = "AI Coach 缺少生成 Prompt 绑定。"
            diagnostics.append(
                self._projection._diagnostic(
                    "[AI_COACH_PROMPT_TEMPLATE_MISSING]",
                    "AI Coach 已启用但缺少生成 Prompt 绑定。",
                    terminal=True,
                )
            )
        if ai_coach is not None and not ai_coach.enabled:
            locked = True
            block_reason = "AI Coach 未启用。"
        return JourneyModule(
            module_key=module.module_key,
            base_module_key=module.module_key,
            title=f"{module.title} AI Coach",
            kind="ai_coach",
            module_type="ai_coach",
            order_index=module.order_index,
            required=True,
            enabled=bool(ai_coach.enabled) if ai_coach is not None else False,
            completion_rule="passed",
            target_unit_id=None,
            target_unit_ids=(),
            capability_keys=tuple(module.capability_keys),
            learning_content_id=module.learning_content_id,
            exam_paper_id=module.exam_paper_id,
            learning_unit_keys=tuple(
                unit.unit_key for unit in module.learning_units if unit.enabled
            ),
            learner_level_required=tuple(module.learner_level_required),
            locked=locked,
            block_reason=block_reason,
            diagnostics=diagnostics,
        )

    def _apply_learner_level_required(
        self,
        modules: list[JourneyModule],
        learner_level: dict[str, Any],
    ) -> None:
        level_key = str(learner_level.get("level_key") or "")
        for module in modules:
            if not module.learner_level_required:
                continue
            if level_key in set(module.learner_level_required):
                continue
            module.locked = True
            module.lock_status = "disabled"
            module.block_reason = "当前学员等级暂不可进入该模块。"
            module.diagnostics.append(
                self._projection._diagnostic(
                    "[NEWCOMER_LEARNER_LEVEL_NOT_ALLOWED]",
                    "当前学员等级不满足 active path revision 的模块开放条件。",
                    severity="warning",
                    terminal=True,
                )
            )

    async def _outcomes_for_active_revision(
        self,
        *,
        learner_id: str,
        path_revision_id: str,
        path_revision_no: int,
        modules: list[JourneyModule],
    ) -> dict[str, list[dict[str, Any]]]:
        outcomes: dict[str, list[dict[str, Any]]] = {
            self._bucket_key(module): [] for module in modules
        }
        unit_to_module: dict[str, JourneyModule] = {}
        for module in modules:
            if module.kind not in {"audio_submission", "quiz_attempt"}:
                continue
            for target_unit_id in module.target_unit_ids:
                unit_to_module[target_unit_id] = module
        if unit_to_module:
            await self._collect_audio_outcomes(
                learner_id=learner_id,
                path_revision_id=path_revision_id,
                path_revision_no=path_revision_no,
                unit_to_module=unit_to_module,
                outcomes=outcomes,
            )
            await self._collect_quiz_outcomes(
                learner_id=learner_id,
                path_revision_id=path_revision_id,
                path_revision_no=path_revision_no,
                unit_to_module=unit_to_module,
                outcomes=outcomes,
            )
        await self._collect_business_etiquette_quiz_outcomes(
            learner_id=learner_id,
            path_revision_id=path_revision_id,
            path_revision_no=path_revision_no,
            modules=modules,
            outcomes=outcomes,
        )
        await self._collect_ai_coach_outcomes(
            learner_id=learner_id,
            path_revision_id=path_revision_id,
            path_revision_no=path_revision_no,
            modules=modules,
            outcomes=outcomes,
        )
        await self._collect_realtime_outcomes(
            learner_id=learner_id,
            path_revision_id=path_revision_id,
            path_revision_no=path_revision_no,
            modules=modules,
            outcomes=outcomes,
        )
        await self._collect_regrade_outcomes(
            path_revision_id=path_revision_id,
            path_revision_no=path_revision_no,
            modules=modules,
            outcomes=outcomes,
        )
        for history in outcomes.values():
            history.sort(
                key=lambda item: str(item.get("submitted_at") or ""), reverse=True
            )
        return outcomes

    async def _collect_audio_outcomes(
        self,
        *,
        learner_id: str,
        path_revision_id: str,
        path_revision_no: int,
        unit_to_module: dict[str, JourneyModule],
        outcomes: dict[str, list[dict[str, Any]]],
    ) -> None:
        result = await self._db.execute(
            select(SalesTrainerAudioSubmission)
            .where(
                SalesTrainerAudioSubmission.user_id == learner_id,
                SalesTrainerAudioSubmission.unit_id.in_(unit_to_module.keys()),
            )
            .order_by(SalesTrainerAudioSubmission.created_at.desc())
        )
        audio_service = AudioSubmissionService(self._db)
        for submission in result.scalars().all():
            payload = await audio_service.serialize_submission(submission)
            if payload.get("path_revision_id") != path_revision_id:
                continue
            module = unit_to_module.get(str(submission.unit_id or ""))
            if module is None:
                continue
            outcomes[self._bucket_key(module)].append(
                self._audio_outcome(module, payload, path_revision_id, path_revision_no)
            )

    async def _collect_quiz_outcomes(
        self,
        *,
        learner_id: str,
        path_revision_id: str,
        path_revision_no: int,
        unit_to_module: dict[str, JourneyModule],
        outcomes: dict[str, list[dict[str, Any]]],
    ) -> None:
        result = await self._db.execute(
            select(SalesTrainerQuizAttempt)
            .where(
                SalesTrainerQuizAttempt.user_id == learner_id,
                SalesTrainerQuizAttempt.unit_id.in_(unit_to_module.keys()),
            )
            .order_by(SalesTrainerQuizAttempt.submitted_at.desc())
        )
        quiz_service = QuizService(self._db)
        for attempt in result.scalars().all():
            payload = await quiz_service.serialize_attempt(attempt)
            lineage = training_record_lineage_fields(payload)
            if lineage["path_revision_id"] != path_revision_id:
                continue
            module = unit_to_module.get(str(attempt.unit_id))
            if module is None:
                continue
            outcomes[self._bucket_key(module)].append(
                self._quiz_outcome(
                    module,
                    payload,
                    lineage,
                    path_revision_id,
                    path_revision_no,
                )
            )

    async def _collect_business_etiquette_quiz_outcomes(
        self,
        *,
        learner_id: str,
        path_revision_id: str,
        path_revision_no: int,
        modules: list[JourneyModule],
        outcomes: dict[str, list[dict[str, Any]]],
    ) -> None:
        unit_to_module: dict[str, JourneyModule] = {}
        for module in modules:
            if module.kind != "quiz_attempt":
                continue
            for unit_key in module.learning_unit_keys:
                unit_to_module[unit_key] = module
        if not unit_to_module:
            return
        result = await self._db.execute(
            select(SalesTrainerBusinessEtiquetteQuizAttempt)
            .where(
                SalesTrainerBusinessEtiquetteQuizAttempt.user_id == learner_id,
                SalesTrainerBusinessEtiquetteQuizAttempt.path_revision_id
                == path_revision_id,
                SalesTrainerBusinessEtiquetteQuizAttempt.learning_unit_key.in_(
                    unit_to_module.keys()
                ),
            )
            .order_by(SalesTrainerBusinessEtiquetteQuizAttempt.submitted_at.desc())
        )
        for attempt in result.scalars().all():
            matched_module = unit_to_module.get(str(attempt.learning_unit_key))
            if matched_module is None:
                continue
            outcomes[self._bucket_key(matched_module)].append(
                self._business_etiquette_quiz_outcome(
                    matched_module,
                    attempt,
                    path_revision_id,
                    path_revision_no,
                )
            )

    async def _collect_ai_coach_outcomes(
        self,
        *,
        learner_id: str,
        path_revision_id: str,
        path_revision_no: int,
        modules: list[JourneyModule],
        outcomes: dict[str, list[dict[str, Any]]],
    ) -> None:
        ai_modules = {
            module.base_module_key: module
            for module in modules
            if module.kind == "ai_coach"
        }
        if not ai_modules:
            return
        result = await self._db.execute(
            select(SalesTrainerAiCoachSession)
            .where(
                SalesTrainerAiCoachSession.user_id == learner_id,
                SalesTrainerAiCoachSession.path_revision_id == path_revision_id,
                SalesTrainerAiCoachSession.module_key.in_(ai_modules.keys()),
            )
            .order_by(SalesTrainerAiCoachSession.created_at.desc())
        )
        for session in result.scalars().all():
            module = ai_modules.get(str(session.module_key))
            if module is None:
                continue
            outcomes[self._bucket_key(module)].append(
                self._ai_coach_outcome(
                    module,
                    session,
                    path_revision_id,
                    path_revision_no,
                )
            )

    async def _collect_realtime_outcomes(
        self,
        *,
        learner_id: str,
        path_revision_id: str,
        path_revision_no: int,
        modules: list[JourneyModule],
        outcomes: dict[str, list[dict[str, Any]]],
    ) -> None:
        realtime_modules = [
            module
            for module in modules
            if module.kind == "realtime_roleplay"
            and module.module_type == "realtime_roleplay"
        ]
        if not realtime_modules:
            return
        service = RuntimeOutcomeProjectionService(self._db)
        for module in realtime_modules:
            if module.locked:
                continue
            projections = await service.list_completed_for_external_binding(
                owner="sales_trainer",
                user_id=learner_id,
                path_revision_id=path_revision_id,
                path_revision_no=path_revision_no,
                module_key=module.module_key,
            )
            for projection in projections:
                outcomes[self._bucket_key(module)].append(
                    self._realtime_outcome(
                        module,
                        projection,
                        path_revision_id,
                        path_revision_no,
                    )
                )

    async def _collect_regrade_outcomes(
        self,
        *,
        path_revision_id: str,
        path_revision_no: int,
        modules: list[JourneyModule],
        outcomes: dict[str, list[dict[str, Any]]],
    ) -> None:
        target_to_bucket: dict[tuple[str, str], str] = {}
        for bucket_key, history in outcomes.items():
            for outcome in history:
                record_type = str(outcome.get("record_type") or "")
                if record_type not in {"audio_submission", "quiz_attempt"}:
                    continue
                source_record_id = str(outcome.get("source_record_id") or "")
                if source_record_id:
                    target_to_bucket[(record_type, source_record_id)] = bucket_key
        if not target_to_bucket:
            return

        module_by_bucket = {self._bucket_key(module): module for module in modules}
        result = await self._db.execute(
            select(SalesTrainerRegradeRun)
            .where(
                SalesTrainerRegradeRun.status.in_(("completed", "failed")),
                SalesTrainerRegradeRun.target_type.in_(
                    {target_type for target_type, _ in target_to_bucket}
                ),
                SalesTrainerRegradeRun.target_id.in_(
                    {target_id for _, target_id in target_to_bucket}
                ),
            )
            .order_by(SalesTrainerRegradeRun.created_at.desc())
        )
        for run in result.scalars().all():
            regrade_bucket_key = target_to_bucket.get(
                (str(run.target_type), str(run.target_id))
            )
            if regrade_bucket_key is None:
                continue
            module = module_by_bucket.get(regrade_bucket_key)
            if module is None:
                continue
            outcomes[regrade_bucket_key].append(
                self._regrade_outcome(
                    module,
                    run,
                    path_revision_id=path_revision_id,
                    path_revision_no=path_revision_no,
                )
            )

    def _audio_outcome(
        self,
        module: JourneyModule,
        payload: dict[str, Any],
        path_revision_id: str,
        path_revision_no: int,
    ) -> dict[str, Any]:
        score_result = payload.get("score_result") or {}
        status, failure_type, failure_code = self._audio_stage(payload)
        return self._outcome_payload(
            module=module,
            record_type="audio_submission",
            record_id=str(payload["submission_id"]),
            status=status,
            score=score_result.get("total_score"),
            max_score=100.0 if score_result else None,
            passed=score_result.get("passed") if score_result else None,
            submitted_at=payload.get("created_at"),
            completed_at=score_result.get("created_at") if score_result else None,
            path_revision_id=path_revision_id,
            path_revision_no=payload.get("path_revision_no"),
            active_path_revision_no=path_revision_no,
            snapshot_type="submission_snapshot",
            legacy_snapshot_only=bool(payload.get("legacy_snapshot_only")),
            failure_type=failure_type,
            failure_code=failure_code,
        )

    def _quiz_outcome(
        self,
        module: JourneyModule,
        payload: dict[str, Any],
        lineage: TrainingRecordLineageFields,
        path_revision_id: str,
        path_revision_no: int,
    ) -> dict[str, Any]:
        status, failure_type, failure_code = self._quiz_stage(payload)
        return self._outcome_payload(
            module=module,
            record_type="quiz_attempt",
            record_id=str(payload["attempt_id"]),
            status=status,
            score=payload.get("total_score"),
            max_score=payload.get("max_score"),
            passed=payload.get("passed"),
            submitted_at=payload.get("submitted_at"),
            completed_at=payload.get("submitted_at"),
            path_revision_id=path_revision_id,
            path_revision_no=lineage.get("path_revision_no"),
            active_path_revision_no=path_revision_no,
            snapshot_type="attempt_snapshot",
            legacy_snapshot_only=bool(lineage.get("legacy_snapshot_only")),
            failure_type=failure_type,
            failure_code=failure_code,
        )

    def _business_etiquette_quiz_outcome(
        self,
        module: JourneyModule,
        attempt: SalesTrainerBusinessEtiquetteQuizAttempt,
        path_revision_id: str,
        path_revision_no: int,
    ) -> dict[str, Any]:
        status, failure_type, failure_code = self._business_etiquette_quiz_stage(
            attempt
        )
        return self._outcome_payload(
            module=module,
            record_type="business_etiquette_quiz_attempt",
            record_id=str(attempt.attempt_id),
            status=status,
            score=float(attempt.total_score)
            if attempt.total_score is not None
            else None,
            max_score=float(attempt.max_score)
            if attempt.max_score is not None
            else None,
            passed=cast(bool | None, attempt.passed),
            submitted_at=attempt.submitted_at,
            completed_at=attempt.submitted_at
            if status in {"passed", "failed"}
            else None,
            path_revision_id=path_revision_id,
            path_revision_no=cast(int | None, attempt.path_revision_no),
            active_path_revision_no=path_revision_no,
            snapshot_type="attempt_snapshot",
            legacy_snapshot_only=False,
            failure_type=failure_type,
            failure_code=failure_code,
        )

    def _ai_coach_outcome(
        self,
        module: JourneyModule,
        session: SalesTrainerAiCoachSession,
        path_revision_id: str,
        path_revision_no: int,
    ) -> dict[str, Any]:
        status, passed, failure_type, failure_code = self._ai_coach_stage(session)
        return self._outcome_payload(
            module=module,
            record_type="ai_coach_session",
            record_id=str(session.session_id),
            status=status,
            score=float(session.total_score)
            if session.total_score is not None
            else None,
            max_score=float(session.max_score)
            if session.max_score is not None
            else None,
            passed=passed,
            submitted_at=session.created_at,
            completed_at=session.updated_at if status in {"passed", "failed"} else None,
            path_revision_id=path_revision_id,
            path_revision_no=cast(int | None, session.path_revision_no),
            active_path_revision_no=path_revision_no,
            snapshot_type="session_snapshot",
            legacy_snapshot_only=False,
            failure_type=failure_type,
            failure_code=failure_code,
        )

    def _realtime_outcome(
        self,
        module: JourneyModule,
        projection: RuntimeOutcomeProjection,
        path_revision_id: str,
        path_revision_no: int,
    ) -> dict[str, Any]:
        return self._outcome_payload(
            module=module,
            record_type="realtime_roleplay_session",
            record_id=projection.source_record_id,
            status="scored",
            score=projection.score,
            max_score=projection.max_score,
            passed=projection.passed,
            submitted_at=projection.submitted_at,
            completed_at=projection.completed_at,
            path_revision_id=path_revision_id,
            path_revision_no=path_revision_no,
            active_path_revision_no=path_revision_no,
            snapshot_type="runtime_outcome_snapshot",
            legacy_snapshot_only=False,
        )

    def _regrade_outcome(
        self,
        module: JourneyModule,
        run: SalesTrainerRegradeRun,
        *,
        path_revision_id: str,
        path_revision_no: int,
    ) -> dict[str, Any]:
        after_snapshot = json_dict_or_empty(run.after_snapshot_json)
        status, passed, failure_type, failure_code = self._regrade_stage(
            run,
            after_snapshot,
        )
        return {
            "outcome_id": f"regrade:{run.run_id}",
            "record_type": "regrade",
            "source_record_id": str(run.target_id),
            "module_key": module.module_key,
            "module_type": module.module_type,
            "kind": module.kind,
            "status": status,
            "score": self._projection._float_or_none(after_snapshot.get("total_score")),
            "max_score": self._projection._float_or_none(
                after_snapshot.get("max_score")
            ),
            "passed": passed,
            "failure_type": failure_type,
            "failure_code": failure_code,
            "submitted_at": run.created_at,
            "completed_at": run.completed_at,
            "path_revision_id": path_revision_id,
            "path_revision_no": path_revision_no,
            "snapshot_ref": {
                "snapshot_type": "regrade_snapshot",
                "legacy_snapshot_only": False,
                "regrade_unavailable": False,
            },
            "evidence": {
                "record_id": str(run.run_id),
                "record_type": "regrade",
                "occurred_at": run.completed_at,
            },
        }

    def _outcome_payload(
        self,
        *,
        module: JourneyModule,
        record_type: OutcomeRecordType,
        record_id: str,
        status: TrainingStage,
        score: Any,
        max_score: Any,
        passed: bool | None,
        submitted_at: Any,
        completed_at: Any,
        path_revision_id: str,
        path_revision_no: int | None,
        active_path_revision_no: int,
        snapshot_type: str,
        legacy_snapshot_only: bool,
        failure_type: str | None = None,
        failure_code: str | None = None,
    ) -> dict[str, Any]:
        return {
            "outcome_id": f"{record_type}:{record_id}",
            "record_type": record_type,
            "source_record_id": record_id,
            "module_key": module.module_key,
            "module_type": module.module_type,
            "kind": module.kind,
            "status": status,
            "score": self._projection._float_or_none(score),
            "max_score": self._projection._float_or_none(max_score),
            "passed": passed,
            "failure_type": failure_type,
            "failure_code": failure_code,
            "submitted_at": submitted_at,
            "completed_at": completed_at,
            "path_revision_id": path_revision_id,
            "path_revision_no": int(path_revision_no or active_path_revision_no),
            "snapshot_ref": {
                "snapshot_type": snapshot_type,
                "legacy_snapshot_only": legacy_snapshot_only,
                "regrade_unavailable": legacy_snapshot_only,
            },
            "evidence": {
                "record_id": record_id,
                "record_type": record_type,
                "occurred_at": submitted_at,
            },
        }

    def _module_payload(
        self,
        module: JourneyModule,
        history: list[dict[str, Any]],
        active: Any,
    ) -> dict[str, Any]:
        latest = history[0] if history else None
        status = self._projection._module_stage(module, latest)
        completion_satisfied = self._projection._completion_satisfied(module, latest)
        diagnostics = list(module.diagnostics)
        if module.kind == "ai_coach" and latest and latest.get("passed") is False:
            diagnostics.append(
                self._projection._diagnostic(
                    "[AI_COACH_NOT_MASTERED]",
                    "AI Coach 尚未达标，需要继续训练或补救。",
                    severity="warning",
                    terminal=False,
                )
            )
        return {
            "module_key": module.module_key,
            "title": module.title,
            "display_name": module.title,
            "kind": module.kind,
            "module_type": module.module_type,
            "order_index": module.order_index,
            "target_unit_id": module.target_unit_id,
            "target_unit_ids": list(module.target_unit_ids),
            "capability_keys": list(module.capability_keys),
            "learning_content_id": module.learning_content_id,
            "exam_paper_id": module.exam_paper_id,
            "enabled": module.enabled,
            "status": status,
            "stage": status,
            "passed": latest.get("passed") if latest else None,
            "score": latest.get("score") if latest else None,
            "max_score": latest.get("max_score") if latest else None,
            "required": module.required,
            "completion_satisfied": completion_satisfied,
            "locked": module.locked,
            "block_reason": module.block_reason,
            "learner_level_required": list(module.learner_level_required),
            "completion_rule": module.completion_rule,
            "source": {
                "path_revision_id": str(active.revision_id),
                "path_revision_no": int(active.revision_no),
            },
            "latest_outcome": latest,
            "outcome_history": history,
            "unmet_reasons": diagnostics,
            "diagnostics": diagnostics,
            "next_action": self._projection._next_action(module, status),
        }

    @staticmethod
    def _bucket_key(module: JourneyModule) -> str:
        return f"{module.kind}:{module.module_key}"

    async def _retraining_requests(
        self,
        *,
        learner_id: str,
        modules: list[dict[str, Any]],
        learning_topics: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        logs, _ = await OperationLogService(self._db).list_logs(
            target_type=READINESS_DOSSIER_TARGET_TYPE,
            target_id=learner_id,
            limit=20,
        )
        requests: list[dict[str, Any]] = []
        for log in logs:
            if log.action != REVIEW_ACTION_CREATED:
                continue
            metadata: dict[str, Any] = (
                log.metadata_json if isinstance(log.metadata_json, dict) else {}
            )
            decision = str(metadata.get("decision") or "")
            if decision != "require_retraining":
                if requests:
                    break
                return []
            task_value = metadata.get("retraining_task")
            if not isinstance(task_value, dict):
                continue
            task: dict[str, Any] = task_value
            capability_keys = unique_non_empty(metadata.get("capability_keys") or [])
            evidence_ids = unique_non_empty(metadata.get("source_evidence_ids") or [])
            target_modules = _retraining_target_modules(
                modules,
                learning_topics,
                evidence_ids=evidence_ids,
                capability_keys=capability_keys,
            )
            primary_target_path = next(
                (
                    str(item["target_path"])
                    for item in target_modules
                    if item.get("target_path") and not item.get("disabled")
                ),
                None,
            )
            requests.append(
                {
                    "request_id": str(log.log_id),
                    "task_id": str(task.get("task_id") or log.log_id),
                    "status": str(task.get("status") or "pending"),
                    "reason": metadata.get("reason"),
                    "capability_keys": capability_keys,
                    "capability_labels": [
                        capability_label(capability_key)
                        for capability_key in capability_keys
                    ],
                    "source_evidence_count": len(evidence_ids),
                    "target_modules": target_modules,
                    "primary_target_path": primary_target_path,
                    "created_at": log.created_at,
                }
            )
        return requests

    @staticmethod
    def _audio_stage(
        payload: dict[str, Any],
    ) -> tuple[TrainingStage, str | None, str | None]:
        status = str(payload.get("status") or "")
        if status == "scored":
            score = payload.get("score_result") or {}
            if score.get("passed") is True:
                return "passed", None, None
            if score.get("passed") is False:
                return "failed", None, None
            return "scored", None, None
        if status in {"uploaded", "transcribing", "transcribed", "scoring"}:
            return "processing", None, None
        if status in {"transcription_failed", "scoring_failed"}:
            return "error_terminal", "terminal", payload.get("error_code")
        return "in_progress", None, None

    @staticmethod
    def _quiz_stage(
        payload: dict[str, Any],
    ) -> tuple[TrainingStage, str | None, str | None]:
        status = str(payload.get("status") or "")
        if status == "scored":
            if payload.get("passed") is True:
                return "passed", None, None
            if payload.get("passed") is False:
                return "failed", None, None
            return "scored", None, None
        if status == "failed":
            return "error_terminal", "terminal", "[QUIZ_ATTEMPT_FAILED]"
        return "in_progress", None, None

    @staticmethod
    def _business_etiquette_quiz_stage(
        attempt: SalesTrainerBusinessEtiquetteQuizAttempt,
    ) -> tuple[TrainingStage, str | None, str | None]:
        if attempt.status == "scored":
            if attempt.passed is True:
                return "passed", None, None
            if attempt.passed is False:
                return "failed", None, None
            return "scored", None, None
        if attempt.status == "failed":
            return (
                "error_terminal",
                "terminal",
                "[BUSINESS_ETIQUETTE_UNIT_QUIZ_ATTEMPT_FAILED]",
            )
        return "in_progress", None, None

    @staticmethod
    def _ai_coach_stage(
        session: SalesTrainerAiCoachSession,
    ) -> tuple[TrainingStage, bool | None, str | None, str | None]:
        if session.status == "failed":
            return "error_terminal", None, "terminal", "[AI_COACH_SESSION_FAILED]"
        if session.mastery_state == "mastered":
            return "passed", True, None, None
        if session.mastery_state == "not_mastered":
            return "failed", False, None, None
        if session.status == "completed":
            return "scored", None, None, None
        return "in_progress", None, None, None

    @staticmethod
    def _regrade_stage(
        run: SalesTrainerRegradeRun,
        after_snapshot: dict[str, Any],
    ) -> tuple[TrainingStage, bool | None, str | None, str | None]:
        error_code = after_snapshot.get("error_code")
        if run.status == "failed" or error_code:
            return (
                "error_terminal",
                None,
                "terminal",
                str(error_code or "[REGRADING_FAILED]"),
            )
        if after_snapshot.get("passed") is True:
            return "passed", True, None, None
        if after_snapshot.get("passed") is False:
            return "failed", False, None, None
        return "scored", None, None, None

    @staticmethod
    def _kind_for_module_type(module_type: str) -> str:
        if module_type == "article_exam":
            return "quiz_attempt"
        if module_type in {"audio_scoring", "audio_scoring_group"}:
            return "audio_submission"
        if module_type in {"realtime_roleplay", "realtime_placeholder"}:
            return "realtime_roleplay"
        return module_type

    @staticmethod
    def _target_unit_ids(module: NewcomerPathModuleConfig) -> tuple[str, ...]:
        if module.module_type == "audio_scoring_group":
            return tuple(option.target_unit_id for option in module.duration_options)
        return (module.target_unit_id,) if module.target_unit_id else ()

    async def _analytics_additive_observation(
        self,
        *,
        journeys: list[dict[str, Any]],
        module_key: str | None,
    ) -> dict[str, Any]:
        migration_applied = await self._roleplay_observation_table_exists()
        session_scope = await self._realtime_observation_sessions_in_scope(
            journeys=journeys,
            module_key=module_key,
        )
        payload = self._empty_additive_observation_payload(
            storage_ready=migration_applied,
            migration_applied=migration_applied,
            session_count=len(session_scope),
        )
        if not migration_applied or not session_scope:
            return payload

        session_ids = [str(session.session_id) for session in session_scope]
        try:
            result = await self._db.execute(
                select(
                    SalesTrainerRoleplayObservation.session_id,
                    SalesTrainerRoleplayObservation.source,
                    SalesTrainerRoleplayObservation.evaluator_status,
                    SalesTrainerRoleplayObservation.signals_json,
                    SalesTrainerRoleplayObservation.created_at,
                ).where(SalesTrainerRoleplayObservation.session_id.in_(session_ids))
            )
        except SQLAlchemyError:
            payload["storage_ready"] = False
            return payload

        observed_session_ids: set[str] = set()
        high_risk_session_ids: set[str] = set()
        signal_counts: dict[str, int] = {}
        latest_observed_at: datetime | None = None
        observation_count = 0

        for (
            session_id,
            source,
            evaluator_status,
            signals_json,
            created_at,
        ) in result.all():
            session_id_str = str(session_id)
            observed_session_ids.add(session_id_str)
            observation_count += 1

            source_key = str(source or "unknown")
            payload["source_counts"][source_key] = (
                int(payload["source_counts"].get(source_key, 0)) + 1
            )

            status_key = self._roleplay_observation_status_key(evaluator_status)
            payload["status_counts"][status_key] = (
                int(payload["status_counts"].get(status_key, 0)) + 1
            )

            observed_at = self._utc_datetime_or_none(created_at)
            if observed_at is not None and (
                latest_observed_at is None or observed_at > latest_observed_at
            ):
                latest_observed_at = observed_at

            for signal in signals_json or []:
                signal_key = self._roleplay_observation_signal_key(signal)
                if signal_key is not None:
                    signal_counts[signal_key] = signal_counts.get(signal_key, 0) + 1
                if self._roleplay_observation_signal_is_high_risk(signal):
                    high_risk_session_ids.add(session_id_str)

        payload["observed_session_count"] = len(observed_session_ids)
        payload["observation_count"] = observation_count
        payload["top_signal_keys"] = [
            {"key": key, "count": count}
            for key, count in sorted(
                signal_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:ROLEPLAY_OBSERVATION_TOP_SIGNAL_LIMIT]
        ]
        payload["high_risk_session_count"] = len(high_risk_session_ids)
        payload["latest_observed_at"] = latest_observed_at
        return payload

    async def _realtime_observation_sessions_in_scope(
        self,
        *,
        journeys: list[dict[str, Any]],
        module_key: str | None,
    ) -> list[JourneyRoleplaySessionProjection]:
        if module_key and module_key != ROLEPLAY_OBSERVATION_MODULE_KEY:
            return []
        learner_ids = {
            str(journey.get("learner_id") or "")
            for journey in journeys
            if journey.get("learner_id")
        }
        if not learner_ids:
            return []
        path_revision_ids = {
            str(journey.get("path_revision_id") or "")
            for journey in journeys
            if journey.get("path_revision_id")
        }
        sessions = await self._read_repository.roleplay_sessions(
            learner_ids=frozenset(learner_ids)
        )
        return [
            session
            for session in sessions
            if self._practice_session_matches_observation_scope(
                session,
                path_revision_ids=path_revision_ids,
                module_key=module_key,
            )
        ]

    async def _roleplay_observation_table_exists(self) -> bool:
        try:
            connection = await self._db.connection()
            return bool(
                await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).has_table(
                        ROLEPLAY_OBSERVATION_TABLE_NAME
                    )
                )
            )
        except SQLAlchemyError:
            return False

    @staticmethod
    def _empty_additive_observation_payload(
        *,
        storage_ready: bool,
        migration_applied: bool,
        session_count: int,
    ) -> dict[str, Any]:
        return {
            "storage_ready": storage_ready,
            "migration_applied": migration_applied,
            "session_count": session_count,
            "observed_session_count": 0,
            "observation_count": 0,
            "source_counts": {source: 0 for source in ROLEPLAY_OBSERVATION_SOURCES},
            "status_counts": {status: 0 for status in ROLEPLAY_OBSERVATION_STATUSES},
            "top_signal_keys": [],
            "high_risk_session_count": 0,
            "latest_observed_at": None,
        }

    @staticmethod
    def _practice_session_matches_observation_scope(
        session: JourneyRoleplaySessionProjection,
        *,
        path_revision_ids: set[str],
        module_key: str | None,
    ) -> bool:
        binding = TrainingJourneyService._voice_external_binding(
            session.voice_policy_snapshot
        )
        if str(binding.get("owner") or "") != ROLEPLAY_OBSERVATION_SCOPE_OWNER:
            return False
        expected_module_key = module_key or ROLEPLAY_OBSERVATION_MODULE_KEY
        if str(binding.get("module_key") or "") != expected_module_key:
            return False
        if (
            path_revision_ids
            and str(binding.get("path_revision_id") or "") not in path_revision_ids
        ):
            return False
        return True

    @staticmethod
    def _voice_external_binding(snapshot: Any) -> Mapping[str, object]:
        if not isinstance(snapshot, Mapping):
            return {}
        binding = snapshot.get("external_binding")
        return binding if isinstance(binding, Mapping) else {}

    @staticmethod
    def _roleplay_observation_status_key(value: Any) -> str:
        normalized = str(value or "").strip()
        if normalized in ROLEPLAY_OBSERVATION_STATUSES:
            return normalized
        return normalized or "unknown"

    @staticmethod
    def _roleplay_observation_signal_key(signal: Any) -> str | None:
        if not isinstance(signal, dict):
            return None
        for field_name in ("key", "signal_type", "type"):
            value = signal.get(field_name)
            if value is None:
                continue
            normalized = str(value).strip()
            if normalized:
                return normalized
        return None

    @classmethod
    def _roleplay_observation_signal_is_high_risk(cls, signal: Any) -> bool:
        if not isinstance(signal, dict):
            return False
        severity = str(signal.get("severity") or "").strip().lower()
        if severity == "high":
            return True
        return cls._roleplay_observation_signal_key(signal) == "manual_review_required"

    @staticmethod
    def _utc_datetime_or_none(value: Any) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _role_capabilities(
        viewer: JourneyViewer,
        learner: JourneyLearnerProjection,
    ) -> list[dict[str, Any]]:
        is_self = str(viewer.user_id) == str(learner.user_id)
        return [
            {
                "capability_key": "learner_view_own_records",
                "allowed": is_self,
                "scope": "own" if is_self else "none",
                "reason_code": None if is_self else "[ROLE_REQUIRED]",
            },
            {
                "capability_key": "learner_enter",
                "allowed": is_self,
                "scope": "own" if is_self else "none",
                "reason_code": None if is_self else "[ROLE_REQUIRED]",
            },
            {
                "capability_key": "view_records",
                "allowed": can_view_sales_trainer_records(cast(Any, viewer)),
                "scope": "global"
                if can_view_sales_trainer_global_records(cast(Any, viewer))
                else "department"
                if can_view_sales_trainer_records(cast(Any, viewer))
                else "none",
                "reason_code": None
                if can_view_sales_trainer_records(cast(Any, viewer))
                else "[ROLE_REQUIRED]",
            },
        ]

    async def _learner_level(
        self,
        *,
        learner: JourneyLearnerProjection,
        training_stage: str,
        overall: dict[str, Any],
    ) -> dict[str, Any]:
        resolution = await BusinessRuleConfigService(self._db).resolve_active_config(
            SALES_TRAINER_LEARNER_LEVEL_POLICY_KEY,
        )
        policy = resolution.value
        if policy.get("enabled") is False or resolution.source == "database_disabled":
            return self._projection._learner_level_payload(
                policy=self._projection._default_learner_level_policy(),
                level=self._projection._default_learner_level_policy()["default_level"],
                source="training_projection",
                config_revision_id=None,
                fallback_applied=True,
                fallback_reason="policy_disabled",
                policy_key=SALES_TRAINER_LEARNER_LEVEL_POLICY_KEY,
                management_entry="/admin/business-rules/sales-trainer-learner-level",
            )

        matched_level = self._projection._match_learner_level(
            policy=policy,
            learner=learner,
            training_stage=training_stage,
            overall=overall,
        )
        source = (
            "org_rule" if resolution.source == "database" else "training_projection"
        )
        fallback_applied = resolution.fallback_reason is not None
        return self._projection._learner_level_payload(
            policy=policy,
            level=matched_level,
            source=source,
            config_revision_id=str(resolution.config_id)
            if resolution.config_id
            else None,
            fallback_applied=fallback_applied,
            fallback_reason=resolution.fallback_reason,
            policy_key=SALES_TRAINER_LEARNER_LEVEL_POLICY_KEY,
            management_entry="/admin/business-rules/sales-trainer-learner-level",
        )

    async def _role_level(
        self,
        *,
        learner: JourneyLearnerProjection,
        training_stage: str,
        overall: dict[str, Any],
    ) -> dict[str, Any]:
        resolution = await BusinessRuleConfigService(self._db).resolve_active_config(
            SALES_TRAINER_ROLE_LEVEL_POLICY_KEY,
        )
        policy = resolution.value
        if policy.get("enabled") is False or resolution.source == "database_disabled":
            default_policy = self._projection._default_role_level_policy()
            return self._projection._learner_level_payload(
                policy=default_policy,
                level=default_policy["default_level"],
                source="training_projection",
                config_revision_id=None,
                fallback_applied=True,
                fallback_reason="policy_disabled",
                policy_key=SALES_TRAINER_ROLE_LEVEL_POLICY_KEY,
                management_entry="/admin/business-rules/sales-trainer-role-level",
            )

        matched_level = self._projection._match_learner_level(
            policy=policy,
            learner=learner,
            training_stage=training_stage,
            overall=overall,
        )
        source = (
            "org_rule" if resolution.source == "database" else "training_projection"
        )
        fallback_applied = resolution.fallback_reason is not None
        return self._projection._learner_level_payload(
            policy=policy,
            level=matched_level,
            source=source,
            config_revision_id=str(resolution.config_id)
            if resolution.config_id
            else None,
            fallback_applied=fallback_applied,
            fallback_reason=resolution.fallback_reason,
            policy_key=SALES_TRAINER_ROLE_LEVEL_POLICY_KEY,
            management_entry="/admin/business-rules/sales-trainer-role-level",
        )


def _journey_matches_filters(
    journey: dict[str, Any],
    *,
    training_stage: str | None,
    module_key: str | None,
    learner_level: str | None,
    role_level: str | None,
) -> bool:
    training_stage = _normalise_filter_value(training_stage)
    module_key = _normalise_filter_value(module_key)
    learner_level = _normalise_filter_value(learner_level)
    role_level = _normalise_filter_value(role_level)
    if training_stage and journey.get("training_stage") != training_stage:
        return False
    if (
        module_key
        and not any(
            module.get("module_key") == module_key
            for module in journey.get("modules") or []
        )
        and not any(
            topic.get("topic_key") == module_key
            or topic.get("source_module_key") == module_key
            for topic in journey.get("learning_topics") or []
        )
    ):
        return False
    if learner_level:
        level = journey.get("learner_level") or {}
        if not isinstance(level, dict) or level.get("level_key") != learner_level:
            return False
    if role_level:
        level = journey.get("role_level") or {}
        if not isinstance(level, dict) or level.get("level_key") != role_level:
            return False
    return True


def _normalise_filter_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _learning_topic_practice_path(topic_key: str) -> str | None:
    if topic_key == "business_etiquette":
        return "/sales-trainer/learning-topics/business-etiquette"
    if topic_key == "customer_faq":
        return "/sales-trainer/learning-topics/customer-faq"
    return None


def _retraining_target_modules(
    modules: list[dict[str, Any]],
    learning_topics: list[dict[str, Any]],
    *,
    evidence_ids: list[str],
    capability_keys: list[str],
) -> list[dict[str, Any]]:
    evidence_set = set(evidence_ids)
    capability_set = set(capability_keys)
    evidence_matched = [
        module
        for module in modules
        if _module_matches_retraining_evidence(module, evidence_set)
    ]
    evidence_keys = {
        (str(module.get("kind") or ""), str(module.get("module_key") or ""))
        for module in evidence_matched
    }
    capability_matched = [
        module
        for module in modules
        if (
            str(module.get("kind") or ""),
            str(module.get("module_key") or ""),
        )
        not in evidence_keys
        and _module_matches_retraining_capability(module, capability_set)
    ]
    matched = (
        evidence_matched
        + capability_matched
        + _retraining_target_learning_topics(
            learning_topics,
            evidence_set=evidence_set,
            capability_set=capability_set,
        )
    )
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for module in matched:
        key = (str(module.get("kind") or ""), str(module.get("module_key") or ""))
        deduped.setdefault(key, module)
    return [
        _retraining_target_module_payload(module)
        for module in sorted(
            deduped.values(),
            key=lambda item: int(item.get("order_index") or 0),
        )
    ]


def _retraining_target_learning_topics(
    learning_topics: list[dict[str, Any]],
    *,
    evidence_set: set[str],
    capability_set: set[str],
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for topic in learning_topics:
        topic_key = str(topic.get("topic_key") or "")
        source_module_key = str(topic.get("source_module_key") or "")
        topic_capability_keys = _learning_topic_capability_keys(topic)
        evidence_matched = bool(
            evidence_set
            and source_module_key == "business_skills"
            and any(
                evidence_id.startswith("ai_coach_session:")
                or evidence_id.startswith("business_etiquette_quiz_attempt:")
                for evidence_id in evidence_set
            )
        )
        capability_matched = bool(capability_set.intersection(topic_capability_keys))
        if not evidence_matched and not capability_matched:
            continue
        raw_ai_coach = topic.get("ai_coach")
        ai_coach = raw_ai_coach if isinstance(raw_ai_coach, dict) else {}
        ai_available = bool(ai_coach.get("available"))
        coach_path = (
            str(ai_coach.get("coach_path"))
            if ai_available and ai_coach.get("coach_path")
            else None
        )
        topic_path = _learning_topic_practice_path(topic_key)
        matched.append(
            {
                "module_key": source_module_key or topic_key,
                "title": topic.get("title"),
                "kind": "ai_coach" if coach_path else "learning_topic",
                "module_type": "learning_topic_ai_coach"
                if coach_path
                else "learning_topic",
                "status": topic.get("status"),
                "order_index": topic.get("order_index"),
                "capability_keys": topic_capability_keys,
                "next_action": {
                    "label": "进入 AI 教练" if coach_path else "继续学习",
                    "target_path": coach_path or topic_path,
                    "disabled": (coach_path or topic_path) is None,
                    "disabled_reason": None
                    if (coach_path or topic_path)
                    else "学习专题暂不可用。",
                },
            }
        )
    return matched


def _learning_topic_capability_keys(topic: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for unit in topic.get("units") or []:
        if not isinstance(unit, dict):
            continue
        keys.extend(
            value
            for value in unit.get("capability_keys") or []
            if isinstance(value, str)
        )
    if keys:
        return unique_non_empty(keys)
    return module_capability_keys(
        {
            "module_key": topic.get("source_module_key") or topic.get("topic_key"),
            "title": topic.get("title"),
            "kind": "learning_topic",
            "module_type": "learning_topic",
        }
    )


def _module_matches_retraining_evidence(
    module: dict[str, Any],
    evidence_ids: set[str],
) -> bool:
    if not evidence_ids:
        return False
    outcomes = list(module.get("outcome_history") or [])
    latest = module.get("latest_outcome")
    if isinstance(latest, dict):
        outcomes.append(latest)
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        record_type = str(outcome.get("record_type") or "")
        record_id = str(outcome.get("source_record_id") or "")
        if record_type and record_id and f"{record_type}:{record_id}" in evidence_ids:
            return True
    return False


def _module_matches_retraining_capability(
    module: dict[str, Any],
    capability_keys: set[str],
) -> bool:
    if not capability_keys:
        return False
    return bool(capability_keys.intersection(module_capability_keys(module)))


def _retraining_target_module_payload(module: dict[str, Any]) -> dict[str, Any]:
    next_action_value = module.get("next_action")
    next_action: dict[str, Any] = (
        next_action_value if isinstance(next_action_value, dict) else {}
    )
    return {
        "module_key": module.get("module_key"),
        "title": module.get("title") or module.get("display_name"),
        "kind": module.get("kind"),
        "module_type": module.get("module_type"),
        "status": module.get("status") or module.get("stage"),
        "action_label": next_action.get("label"),
        "target_path": next_action.get("target_path"),
        "disabled": bool(next_action.get("disabled")) if next_action else True,
        "disabled_reason": next_action.get("disabled_reason") if next_action else None,
    }
