from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAssetRevision,
    SalesTrainerBusinessEtiquetteQuestionDraft,
    SalesTrainerBusinessEtiquetteQuizAttempt,
)
from sales_trainer.schemas import (
    AiCoachConfig,
    BusinessEtiquetteReleaseAiCoachConfigImpactResponse,
    BusinessEtiquetteReleaseCapabilityImpactResponse,
    BusinessEtiquetteReleaseChapterChangeResponse,
    BusinessEtiquetteReleaseConfigResponse,
    BusinessEtiquetteReleaseImpactResponse,
    BusinessEtiquetteReleaseImpactSummaryResponse,
    BusinessEtiquetteReleaseLearnerImpactResponse,
    BusinessEtiquetteReleaseLearningUnitImpactResponse,
    BusinessEtiquetteReleasePublishRequest,
    BusinessEtiquetteReleasePublishResponse,
    BusinessEtiquetteReleaseQuestionDraftImpactResponse,
    BusinessEtiquetteReleaseQuestionImpactResponse,
    BusinessEtiquetteReleaseStrategy,
    BusinessEtiquetteRetrainingAssignmentRequest,
    BusinessEtiquetteRetrainingAssignmentResponse,
    NewcomerPathConfigPayload,
)
from sales_trainer.services.ai_coach_chat_service import AiCoachChatService
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    CAPABILITY_SNAPSHOT_KEY,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.business_etiquette_learning_service import (
    BUSINESS_SKILLS_MODULE_KEY,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import SalesTrainerPathConfigError
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService

BUSINESS_ETIQUETTE_RELEASE_MANAGEMENT_ENTRY = (
    "/admin/sales-trainer/articles/import"
)


@dataclass(frozen=True, slots=True)
class BusinessEtiquetteReleaseSettings:
    default_strategy: BusinessEtiquetteReleaseStrategy = "future_learners_only"
    allow_voluntary_switch: bool = True
    allow_assigned_retraining: bool = True
    max_assigned_retraining_users: int = 100
    notification_template: str = (
        "商务礼仪训练包已更新，你可以选择重练最新版以重新校准能力。"
    )
    large_change_chapter_threshold: int = 2

    def validate(self) -> None:
        if self.max_assigned_retraining_users <= 0:
            raise BusinessEtiquetteReleaseServiceError(
                "[BUSINESS_ETIQUETTE_RELEASE_CONFIG_INVALID]",
                "商务礼仪重练指派人数上限配置非法。",
                500,
            )
        if self.large_change_chapter_threshold <= 0:
            raise BusinessEtiquetteReleaseServiceError(
                "[BUSINESS_ETIQUETTE_RELEASE_CONFIG_INVALID]",
                "商务礼仪影响分析阈值配置非法。",
                500,
            )
        if not self.notification_template.strip():
            raise BusinessEtiquetteReleaseServiceError(
                "[BUSINESS_ETIQUETTE_RELEASE_CONFIG_INVALID]",
                "商务礼仪重练通知文案配置缺失。",
                500,
            )


class BusinessEtiquetteReleaseServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BusinessEtiquetteReleaseService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        settings: BusinessEtiquetteReleaseSettings | None = None,
        chat_service: AiCoachChatService | None = None,
        logs: OperationLogService | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or BusinessEtiquetteReleaseSettings()
        self._revisions = SalesTrainerAssetRevisionService(db)
        self._logs = logs or OperationLogService(db)
        self._chat = chat_service or AiCoachChatService(db, logs=self._logs)

    async def preview_release_impact(
        self,
        *,
        training_pack_key: str | None = None,
        target_revision_id: str | None = None,
    ) -> BusinessEtiquetteReleaseImpactResponse:
        self._settings.validate()
        logical_id = _normalize_training_pack_key(training_pack_key)
        active_revision = await self._revisions.active_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        target_revision = await self._target_revision(logical_id, target_revision_id)
        return await self._impact_response(
            logical_id=logical_id,
            active_revision=active_revision,
            target_revision=target_revision,
        )

    async def publish_release(
        self,
        payload: BusinessEtiquetteReleasePublishRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> BusinessEtiquetteReleasePublishResponse:
        self._settings.validate()
        logical_id = _normalize_training_pack_key(payload.training_pack_key)
        self._validate_strategy(payload.strategy, payload.assigned_user_ids)
        working_revision = await self._revisions.latest_working_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        if working_revision is None:
            raise BusinessEtiquetteReleaseServiceError(
                "[BUSINESS_ETIQUETTE_RELEASE_WORKING_REVISION_MISSING]",
                "商务礼仪训练包没有可发布的草稿版本。",
                409,
            )
        active_before = await self._revisions.active_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        impact = await self._impact_response(
            logical_id=logical_id,
            active_revision=active_before,
            target_revision=working_revision,
        )
        publish_result = await self._revisions.publish_working_revision(
            working_revision,
            actor=actor,
            reason=payload.reason,
            trace_id=trace_id,
        )
        created_session_ids: list[str] = []
        if payload.strategy == "assign_retraining":
            created_session_ids = await self._create_retraining_sessions(
                user_ids=payload.assigned_user_ids,
                actor=actor,
            )
        await self._logs.record(
            actor=actor,
            action="business_etiquette_training_pack.released",
            target_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            target_id=logical_id,
            request_id=trace_id,
            metadata={
                "training_pack_key": logical_id,
                "active_revision_id": str(publish_result.revision.revision_id),
                "active_revision_no": publish_result.revision.revision_no,
                "previous_revision_id": publish_result.previous_revision_id,
                "strategy": payload.strategy,
                "assigned_user_ids": payload.assigned_user_ids,
                "created_session_ids": created_session_ids,
                "reason": payload.reason,
                "impact_summary": impact.summary.model_dump(mode="json"),
            },
        )
        await self._db.commit()
        return BusinessEtiquetteReleasePublishResponse(
            training_pack_key=logical_id,
            active_revision_id=str(publish_result.revision.revision_id),
            active_revision_no=publish_result.revision.revision_no,
            previous_revision_id=publish_result.previous_revision_id,
            strategy=payload.strategy,
            impact_summary=impact.summary,
            created_session_ids=created_session_ids,
        )

    async def start_voluntary_retraining(
        self,
        *,
        actor: User,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        self._settings.validate()
        if not self._settings.allow_voluntary_switch:
            raise BusinessEtiquetteReleaseServiceError(
                "[BUSINESS_ETIQUETTE_VOLUNTARY_RETRAINING_DISABLED]",
                "当前商务礼仪训练包不允许学员自愿切换新版重练。",
                409,
            )
        session = await self._chat.create_session_shell(
            user_id=str(actor.user_id),
            module_key=BUSINESS_SKILLS_MODULE_KEY,
            resume_strategy="new",
            actor=actor,
        )
        stored_session = await self._db.get(
            SalesTrainerAiCoachSession,
            session.session_id,
        )
        await self._logs.record(
            actor=actor,
            action="business_etiquette_training_pack.voluntary_retraining_started",
            target_type="sales_trainer_ai_coach_session",
            target_id=session.session_id,
            request_id=trace_id,
            metadata={
                "module_key": BUSINESS_SKILLS_MODULE_KEY,
                "reason": reason,
                "path_revision_id": (
                    _optional_str(stored_session.path_revision_id)
                    if stored_session is not None
                    else None
                ),
                "path_revision_no": (
                    stored_session.path_revision_no
                    if stored_session is not None
                    else None
                ),
            },
        )
        await self._db.commit()
        return session.session_id

    async def assign_retraining(
        self,
        payload: BusinessEtiquetteRetrainingAssignmentRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> BusinessEtiquetteRetrainingAssignmentResponse:
        self._settings.validate()
        logical_id = _normalize_training_pack_key(payload.training_pack_key)
        self._validate_strategy("assign_retraining", payload.user_ids)
        created_session_ids = await self._create_retraining_sessions(
            user_ids=payload.user_ids,
            actor=actor,
        )
        await self._logs.record(
            actor=actor,
            action="business_etiquette_training_pack.retraining_assigned",
            target_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            target_id=logical_id,
            request_id=trace_id,
            metadata={
                "training_pack_key": logical_id,
                "assigned_user_ids": payload.user_ids,
                "created_session_ids": created_session_ids,
                "reason": payload.reason,
            },
        )
        await self._db.commit()
        return BusinessEtiquetteRetrainingAssignmentResponse(
            training_pack_key=logical_id,
            assigned_user_ids=payload.user_ids,
            created_session_ids=created_session_ids,
            reason=payload.reason,
        )

    async def _impact_response(
        self,
        *,
        logical_id: str,
        active_revision: SalesTrainerAssetRevision | None,
        target_revision: SalesTrainerAssetRevision,
    ) -> BusinessEtiquetteReleaseImpactResponse:
        path_payload = await self._path_payload()
        module = _business_skills_module(path_payload)
        chapter_changes = _chapter_changes(
            active_revision.payload_json if active_revision is not None else {},
            target_revision.payload_json or {},
        )
        impacted_capabilities = _capability_changes(
            active_revision.payload_json if active_revision is not None else {},
            target_revision.payload_json or {},
        )
        changed_chapter_orders = {
            item.chapter_order for item in chapter_changes
        }
        changed_capability_keys = {
            item.capability_key for item in impacted_capabilities
        }
        impacted_units = _impacted_units(
            module,
            changed_chapter_orders=changed_chapter_orders,
            changed_capability_keys=changed_capability_keys,
        )
        impacted_question_drafts, impacted_questions = await self._question_impacts(
            logical_id=logical_id,
            changed_chapter_orders=changed_chapter_orders,
            changed_capability_keys=changed_capability_keys,
        )
        impacted_ai_configs = _impacted_ai_coach_configs(module, impacted_units)
        active_learners = await self._active_learners(active_revision)
        recommended_user_ids = [
            learner.user_id
            for learner in active_learners
            if learner.has_active_ai_coach_session or changed_chapter_orders
        ]
        summary = BusinessEtiquetteReleaseImpactSummaryResponse(
            changed_chapter_count=len(chapter_changes),
            impacted_learning_unit_count=len(impacted_units),
            impacted_question_count=len(impacted_questions),
            impacted_question_draft_count=len(impacted_question_drafts),
            impacted_capability_count=len(impacted_capabilities),
            impacted_ai_coach_config_count=len(impacted_ai_configs),
            active_learner_count=len(active_learners),
            recommended_retraining_user_count=len(recommended_user_ids),
            is_large_change=(
                len(chapter_changes) >= self._settings.large_change_chapter_threshold
            ),
        )
        return BusinessEtiquetteReleaseImpactResponse(
            training_pack_key=logical_id,
            active_revision_id=(
                str(active_revision.revision_id) if active_revision is not None else None
            ),
            active_revision_no=(
                active_revision.revision_no if active_revision is not None else None
            ),
            target_revision_id=str(target_revision.revision_id),
            target_revision_no=target_revision.revision_no,
            target_revision_status=str(target_revision.status),  # type: ignore[arg-type]
            strategy_options=self._strategy_options(),
            config=self._config_response(),
            summary=summary,
            chapter_changes=chapter_changes,
            impacted_learning_units=impacted_units,
            impacted_questions=impacted_questions,
            impacted_question_drafts=impacted_question_drafts,
            impacted_capabilities=impacted_capabilities,
            impacted_ai_coach_configs=impacted_ai_configs,
            active_learners=active_learners,
            recommended_retraining_user_ids=recommended_user_ids,
        )

    async def _target_revision(
        self,
        logical_id: str,
        target_revision_id: str | None,
    ) -> SalesTrainerAssetRevision:
        if target_revision_id:
            revision = await self._revisions.revision_by_id(target_revision_id)
            if (
                revision is None
                or revision.resource_type != BUSINESS_ETIQUETTE_RESOURCE_TYPE
                or revision.logical_id != logical_id
            ):
                raise BusinessEtiquetteReleaseServiceError(
                    "[BUSINESS_ETIQUETTE_RELEASE_TARGET_NOT_FOUND]",
                    "指定的商务礼仪训练包版本不存在。",
                    404,
                )
            return revision
        working_revision = await self._revisions.latest_working_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        if working_revision is not None:
            return working_revision
        active_revision = await self._revisions.active_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        if active_revision is not None:
            return active_revision
        raise BusinessEtiquetteReleaseServiceError(
            "[BUSINESS_ETIQUETTE_RELEASE_REVISION_MISSING]",
            "请先导入商务礼仪训练包资料，再查看发布影响。",
            409,
        )

    async def _path_payload(self) -> NewcomerPathConfigPayload:
        try:
            path_response = await SalesTrainerPathConfigService(self._db).get_config()
        except SalesTrainerPathConfigError as exc:
            raise BusinessEtiquetteReleaseServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        return NewcomerPathConfigPayload.model_validate(path_response["path"])

    async def _question_impacts(
        self,
        *,
        logical_id: str,
        changed_chapter_orders: set[int],
        changed_capability_keys: set[str],
    ) -> tuple[
        list[BusinessEtiquetteReleaseQuestionDraftImpactResponse],
        list[BusinessEtiquetteReleaseQuestionImpactResponse],
    ]:
        result = await self._db.execute(
            select(SalesTrainerBusinessEtiquetteQuestionDraft).where(
                SalesTrainerBusinessEtiquetteQuestionDraft.training_pack_key
                == logical_id
            )
        )
        draft_impacts: list[BusinessEtiquetteReleaseQuestionDraftImpactResponse] = []
        question_impacts: list[BusinessEtiquetteReleaseQuestionImpactResponse] = []
        for draft in result.scalars().all():
            capability_keys = [str(key) for key in list(draft.capability_keys or [])]
            impacted = (
                not changed_chapter_orders
                and not changed_capability_keys
            ) or int(draft.chapter_order) in changed_chapter_orders or bool(
                set(capability_keys) & changed_capability_keys
            )
            if not impacted:
                continue
            if draft.status == "converted" and draft.question_id:
                question_impacts.append(
                    BusinessEtiquetteReleaseQuestionImpactResponse(
                        question_id=str(draft.question_id),
                        draft_id=str(draft.draft_id),
                        title=str(draft.title),
                        question_type=str(draft.question_type),  # type: ignore[arg-type]
                        chapter_order=int(draft.chapter_order),
                        capability_keys=capability_keys,
                    )
                )
            else:
                draft_impacts.append(
                    BusinessEtiquetteReleaseQuestionDraftImpactResponse(
                        draft_id=str(draft.draft_id),
                        title=str(draft.title),
                        question_type=str(draft.question_type),  # type: ignore[arg-type]
                        status=str(draft.status),  # type: ignore[arg-type]
                        chapter_order=int(draft.chapter_order),
                        capability_keys=capability_keys,
                    )
                )
        return draft_impacts, question_impacts

    async def _active_learners(
        self,
        active_revision: SalesTrainerAssetRevision | None,
    ) -> list[BusinessEtiquetteReleaseLearnerImpactResponse]:
        sources: dict[str, set[str]] = defaultdict(set)
        latest_path_revision_no: dict[str, int | None] = {}
        latest_pack_revision_no: dict[str, int | None] = {}
        active_session_by_user: dict[str, bool] = {}
        if active_revision is not None:
            quiz_result = await self._db.execute(
                select(SalesTrainerBusinessEtiquetteQuizAttempt).where(
                    SalesTrainerBusinessEtiquetteQuizAttempt.training_pack_revision_id
                    == str(active_revision.revision_id)
                )
            )
            for attempt in quiz_result.scalars().all():
                user_id = str(attempt.user_id)
                sources[user_id].add("quiz_attempt")
                latest_path_revision_no[user_id] = attempt.path_revision_no
                latest_pack_revision_no[user_id] = attempt.training_pack_revision_no
                active_session_by_user.setdefault(user_id, False)
        session_result = await self._db.execute(
            select(SalesTrainerAiCoachSession).where(
                SalesTrainerAiCoachSession.module_key == BUSINESS_SKILLS_MODULE_KEY
            )
        )
        for session in session_result.scalars().all():
            user_id = str(session.user_id)
            sources[user_id].add("ai_coach_session")
            latest_path_revision_no[user_id] = session.path_revision_no
            latest_pack_revision_no.setdefault(user_id, None)
            active_session_by_user[user_id] = (
                active_session_by_user.get(user_id, False)
                or str(session.status) == "in_progress"
            )
        if not sources:
            return []
        user_result = await self._db.execute(
            select(User).where(User.user_id.in_(sorted(sources)))
        )
        users = {str(user.user_id): user for user in user_result.scalars().all()}
        return [
            BusinessEtiquetteReleaseLearnerImpactResponse(
                user_id=user_id,
                user_name=getattr(users.get(user_id), "name", None),
                department=getattr(users.get(user_id), "department", None),
                source_record_types=sorted(sources[user_id]),  # type: ignore[arg-type]
                latest_path_revision_no=latest_path_revision_no.get(user_id),
                latest_training_pack_revision_no=latest_pack_revision_no.get(user_id),
                has_active_ai_coach_session=active_session_by_user.get(user_id, False),
            )
            for user_id in sorted(sources)
        ]

    async def _create_retraining_sessions(
        self,
        *,
        user_ids: list[str],
        actor: User,
    ) -> list[str]:
        created: list[str] = []
        for user_id in user_ids:
            user = await self._db.get(User, user_id)
            if user is None:
                raise BusinessEtiquetteReleaseServiceError(
                    "[BUSINESS_ETIQUETTE_RETRAINING_USER_NOT_FOUND]",
                    f"指定重练用户不存在：{user_id}。",
                    404,
                )
            session = await self._chat.create_session_shell(
                user_id=user_id,
                module_key=BUSINESS_SKILLS_MODULE_KEY,
                resume_strategy="new",
                actor=actor,
            )
            created.append(session.session_id)
        return created

    def _validate_strategy(
        self,
        strategy: BusinessEtiquetteReleaseStrategy,
        assigned_user_ids: list[str],
    ) -> None:
        if strategy == "allow_voluntary_switch" and not self._settings.allow_voluntary_switch:
            raise BusinessEtiquetteReleaseServiceError(
                "[BUSINESS_ETIQUETTE_RELEASE_STRATEGY_DISABLED]",
                "当前配置不允许老学员自愿切换新版。",
                409,
            )
        if strategy == "assign_retraining":
            if not self._settings.allow_assigned_retraining:
                raise BusinessEtiquetteReleaseServiceError(
                    "[BUSINESS_ETIQUETTE_RELEASE_STRATEGY_DISABLED]",
                    "当前配置不允许指定人群重练。",
                    409,
                )
            if not assigned_user_ids:
                raise BusinessEtiquetteReleaseServiceError(
                    "[BUSINESS_ETIQUETTE_RETRAINING_USERS_REQUIRED]",
                    "指定人群重练必须提供用户名单。",
                    422,
                )
            if len(assigned_user_ids) > self._settings.max_assigned_retraining_users:
                raise BusinessEtiquetteReleaseServiceError(
                    "[BUSINESS_ETIQUETTE_RETRAINING_USER_LIMIT_EXCEEDED]",
                    "指定重练用户数超过后台配置上限。",
                    422,
                )

    def _strategy_options(self) -> list[BusinessEtiquetteReleaseStrategy]:
        options: list[BusinessEtiquetteReleaseStrategy] = ["future_learners_only"]
        if self._settings.allow_voluntary_switch:
            options.append("allow_voluntary_switch")
        if self._settings.allow_assigned_retraining:
            options.append("assign_retraining")
        return options

    def _config_response(self) -> BusinessEtiquetteReleaseConfigResponse:
        return BusinessEtiquetteReleaseConfigResponse(
            default_strategy=self._settings.default_strategy,
            allow_voluntary_switch=self._settings.allow_voluntary_switch,
            allow_assigned_retraining=self._settings.allow_assigned_retraining,
            max_assigned_retraining_users=(
                self._settings.max_assigned_retraining_users
            ),
            notification_template=self._settings.notification_template,
            large_change_chapter_threshold=(
                self._settings.large_change_chapter_threshold
            ),
            management_entry=BUSINESS_ETIQUETTE_RELEASE_MANAGEMENT_ENTRY,
        )


def _normalize_training_pack_key(training_pack_key: str | None) -> str:
    logical_id = (
        training_pack_key or DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY
    ).strip()
    if not logical_id:
        raise BusinessEtiquetteReleaseServiceError(
            "[BUSINESS_ETIQUETTE_RELEASE_CONFIG_INVALID]",
            "商务礼仪训练包 key 不能为空。",
            400,
        )
    return logical_id


def _payload_chapters(payload: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    raw_chapters = (payload or {}).get("original_chapters")
    if not isinstance(raw_chapters, list):
        return {}
    chapters: dict[int, dict[str, Any]] = {}
    for raw in raw_chapters:
        if not isinstance(raw, dict) or not isinstance(raw.get("order_index"), int):
            continue
        chapters[int(raw["order_index"])] = raw
    return chapters


def _chapter_changes(
    active_payload: dict[str, Any] | None,
    target_payload: dict[str, Any],
) -> list[BusinessEtiquetteReleaseChapterChangeResponse]:
    active_chapters = _payload_chapters(active_payload)
    target_chapters = _payload_chapters(target_payload)
    changes: list[BusinessEtiquetteReleaseChapterChangeResponse] = []
    for order in sorted(set(active_chapters) | set(target_chapters)):
        active = active_chapters.get(order)
        target = target_chapters.get(order)
        active_hash = _optional_str(active.get("content_hash")) if active else None
        target_hash = _optional_str(target.get("content_hash")) if target else None
        if active is None:
            change_type = "added"
        elif target is None:
            change_type = "removed"
        elif active_hash != target_hash:
            change_type = "changed"
        else:
            continue
        title = _optional_str((target or active or {}).get("title")) or f"第 {order} 章"
        changes.append(
            BusinessEtiquetteReleaseChapterChangeResponse(
                chapter_order=order,
                title=title,
                change_type=change_type,  # type: ignore[arg-type]
                previous_content_hash=active_hash,
                target_content_hash=target_hash,
            )
        )
    return changes


def _capability_map(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    snapshot = (payload or {}).get(CAPABILITY_SNAPSHOT_KEY)
    if not isinstance(snapshot, dict):
        return {}
    raw_capabilities = snapshot.get("capabilities")
    if not isinstance(raw_capabilities, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for raw in raw_capabilities:
        if not isinstance(raw, dict) or not isinstance(raw.get("capability_key"), str):
            continue
        result[str(raw["capability_key"])] = raw
    return result


def _capability_changes(
    active_payload: dict[str, Any] | None,
    target_payload: dict[str, Any],
) -> list[BusinessEtiquetteReleaseCapabilityImpactResponse]:
    active_map = _capability_map(active_payload)
    target_map = _capability_map(target_payload)
    changes: list[BusinessEtiquetteReleaseCapabilityImpactResponse] = []
    for key in sorted(set(active_map) | set(target_map)):
        active = active_map.get(key)
        target = target_map.get(key)
        if active is None:
            change_type = "added"
        elif target is None:
            change_type = "removed"
        elif _capability_fingerprint(active) != _capability_fingerprint(target):
            change_type = "changed"
        else:
            continue
        display_name = (
            _optional_str((target or active or {}).get("display_name"))
            or key
        )
        changes.append(
            BusinessEtiquetteReleaseCapabilityImpactResponse(
                capability_key=key,
                display_name=display_name,
                change_type=change_type,  # type: ignore[arg-type]
                previous_status=_optional_str(active.get("status")) if active else None,  # type: ignore[arg-type]
                target_status=_optional_str(target.get("status")) if target else None,  # type: ignore[arg-type]
            )
        )
    return changes


def _capability_fingerprint(raw: dict[str, Any]) -> tuple[Any, ...]:
    return (
        raw.get("display_name"),
        raw.get("description"),
        raw.get("mastery_levels"),
        raw.get("default_threshold"),
        raw.get("evidence_rules"),
        raw.get("status"),
    )


def _business_skills_module(path_payload: NewcomerPathConfigPayload) -> Any | None:
    for module in path_payload.modules:
        if module.module_key == BUSINESS_SKILLS_MODULE_KEY:
            return module
    return None


def _impacted_units(
    module: Any | None,
    *,
    changed_chapter_orders: set[int],
    changed_capability_keys: set[str],
) -> list[BusinessEtiquetteReleaseLearningUnitImpactResponse]:
    if module is None:
        return []
    impacts: list[BusinessEtiquetteReleaseLearningUnitImpactResponse] = []
    for unit in getattr(module, "learning_units", []) or []:
        unit_chapters = {int(order) for order in unit.source_chapter_orders}
        unit_capabilities = {str(key) for key in unit.capability_keys}
        impacted_chapters = sorted(unit_chapters & changed_chapter_orders)
        impacted_capabilities = sorted(unit_capabilities & changed_capability_keys)
        if not impacted_chapters and not impacted_capabilities:
            continue
        impacts.append(
            BusinessEtiquetteReleaseLearningUnitImpactResponse(
                unit_key=unit.unit_key,
                title=unit.title,
                source_chapter_orders=list(unit.source_chapter_orders),
                capability_keys=list(unit.capability_keys),
                impacted_chapter_orders=impacted_chapters,
                impacted_capability_keys=impacted_capabilities,
                require_quiz=unit.require_quiz,
                require_ai_coach=unit.require_ai_coach,
            )
        )
    return impacts


def _impacted_ai_coach_configs(
    module: Any | None,
    impacted_units: list[BusinessEtiquetteReleaseLearningUnitImpactResponse],
) -> list[BusinessEtiquetteReleaseAiCoachConfigImpactResponse]:
    if module is None:
        return []
    impacted_unit_keys = {unit.unit_key for unit in impacted_units}
    if not impacted_unit_keys:
        return []
    try:
        config = AiCoachConfig.model_validate(module.ai_coach)
    except Exception:
        config = None
    result: list[BusinessEtiquetteReleaseAiCoachConfigImpactResponse] = []
    for unit in getattr(module, "learning_units", []) or []:
        if unit.unit_key not in impacted_unit_keys or not unit.require_ai_coach:
            continue
        result.append(
            BusinessEtiquetteReleaseAiCoachConfigImpactResponse(
                unit_key=unit.unit_key,
                title=unit.title,
                prompt_template_id=(
                    config.prompt_template_id if config is not None else None
                ),
                scoring_prompt_template_id=(
                    config.scoring_prompt_template_id if config is not None else None
                ),
                allowed_training_card_types=(
                    list(config.allowed_training_card_types)
                    if config is not None
                    else []
                ),
                affected_reason="小单元章节或能力点发生变化，需要复核训练卡与评分 prompt 是否仍匹配。",
            )
        )
    return result


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
