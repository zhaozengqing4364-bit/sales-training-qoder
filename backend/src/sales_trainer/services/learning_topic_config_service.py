from __future__ import annotations

from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.ai_coach_policy import AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.schemas import (
    NewcomerLearningTopicConfig,
    NewcomerLearningTopicsPayload,
    NewcomerLearningTopicsSaveRequest,
    NewcomerPathModuleConfig,
)
from sales_trainer.services.asset_revision_service import (
    AssetChangeClass,
    AssetPublishResult,
    SalesTrainerAssetRevisionError,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.curriculum_practice_adapter import get_learning_content
from sales_trainer.services.customer_faq_parser import parse_customer_faq_material
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    payload_from_revision,
)
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService

NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE = "newcomer_learning_topics"
NEWCOMER_LEARNING_TOPICS_LOGICAL_ID = "newcomer_learning_topics_v1"
NEWCOMER_LEARNING_TOPICS_SCHEMA_VERSION = "newcomer_learning_topics_v1"
BUSINESS_ETIQUETTE_TOPIC_KEY = "business_etiquette"
BUSINESS_SKILLS_SOURCE_MODULE_KEY = "business_skills"
CUSTOMER_FAQ_TOPIC_KEY = "customer_faq"
CUSTOMER_FAQ_SOURCE_MODULE_KEY = "customer_faq"
CUSTOMER_FAQ_AUDIO_SCENARIO_KEY = "customer_faq_oral_drill"
LEARNING_TOPICS_MANAGEMENT_ENTRY = "/admin/sales-trainer/learning-topics"


class LearningTopicConfigError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NewcomerLearningTopicConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._revisions = SalesTrainerAssetRevisionService(db)
        self._logs = OperationLogService(db)

    async def get_config(self) -> dict[str, Any]:
        active = await self._active_revision()
        working = await self._working_revision()
        visible_revision = working or active
        payload = (
            payload_from_learning_topic_revision(visible_revision)
            if visible_revision
            else NewcomerLearningTopicsPayload()
        )
        return {
            "source": "active_revision" if active else "not_configured",
            "fallback_reason": "active_revision_missing" if active is None else None,
            "legacy_snapshot_only": False,
            "management_entry": LEARNING_TOPICS_MANAGEMENT_ENTRY,
            "permission": "sales_trainer.manage_modules",
            "payload": payload.model_dump(mode="json"),
            "active_revision_id": str(active.revision_id) if active else None,
            "active_revision_no": active.revision_no if active else None,
            "active_revision_snapshot": self._revisions.snapshot(active),
            "working_revision_id": str(working.revision_id) if working else None,
            "working_revision_no": working.revision_no if working else None,
            "has_unpublished_revision": working is not None,
            "diagnostics": self._diagnostics(
                active=active, working=working, payload=payload
            ),
        }

    async def active_payload(
        self,
    ) -> (
        tuple[
            NewcomerLearningTopicsPayload,
            SalesTrainerAssetRevision,
        ]
        | None
    ):
        active = await self._active_revision()
        if active is None:
            return None
        return payload_from_learning_topic_revision(active), active

    async def active_business_etiquette_topic(
        self,
    ) -> tuple[
        NewcomerLearningTopicConfig,
        SalesTrainerAssetRevision,
    ]:
        active = await self.active_payload()
        if active is None:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_ACTIVE_REVISION_MISSING]",
                "学习专题尚未发布，当前不可展示商务礼仪规范。",
                404,
            )
        payload, revision = active
        topic = business_etiquette_topic_from_payload(payload)
        if topic is None or not topic.enabled:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_NOT_CONFIGURED]",
                "商务礼仪规范学习专题未启用或未发布。",
                404,
            )
        return topic, revision

    async def active_customer_faq_topic(
        self,
    ) -> tuple[
        NewcomerLearningTopicConfig,
        SalesTrainerAssetRevision,
    ]:
        active = await self.active_payload()
        if active is None:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_ACTIVE_REVISION_MISSING]",
                "学习专题尚未发布，当前不可展示客户常见问答。",
                404,
            )
        payload, revision = active
        topic = customer_faq_topic_from_payload(payload)
        if topic is None or not topic.enabled:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_NOT_CONFIGURED]",
                "客户常见问答学习专题未启用或未发布。",
                404,
            )
        return topic, revision

    async def active_business_etiquette_module_config(
        self,
    ) -> tuple[
        str,
        int,
        NewcomerPathModuleConfig,
    ]:
        active_path = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        if active_path is None:
            raise LearningTopicConfigError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "新人训练路径尚未发布 active revision，学习专题不能启动训练。",
                409,
            )
        topic, _ = await self.active_business_etiquette_topic()
        return (
            str(active_path.revision_id),
            int(active_path.revision_no),
            module_config_from_learning_topic(topic),
        )

    async def save_config(
        self,
        payload: NewcomerLearningTopicsSaveRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> SalesTrainerAssetRevision:
        try:
            topic_payload = NewcomerLearningTopicsPayload.model_validate(
                payload.model_dump(mode="json", exclude={"reason"})
            )
        except ValidationError as exc:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_CONFIG_INVALID]",
                "学习专题配置格式错误。",
                422,
            ) from exc
        self._validate_payload_for_write(topic_payload)
        await self._validate_ai_coach_prompt_bindings(topic_payload)
        active = await self._active_revision()
        change_class = classify_learning_topic_change(active, topic_payload)
        try:
            revision = await self._revisions.save_working_revision(
                resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
                logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
                payload=topic_payload.model_dump(mode="json"),
                actor=actor,
                change_class=change_class,
                source_revision_id=str(active.revision_id) if active else None,
                reason=payload.reason,
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise LearningTopicConfigError(
                exc.code, exc.message, exc.status_code
            ) from exc
        await self._record_event(
            actor=actor,
            action="newcomer_learning_topics.save_working",
            before_revision_id=str(active.revision_id) if active else None,
            after_revision_id=str(revision.revision_id),
            reason=payload.reason,
            trace_id=trace_id,
            change_class=change_class,
        )
        await self._db.commit()
        return revision

    async def generate_business_etiquette_draft(
        self,
        *,
        actor: User,
        overwrite_working: bool = False,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> SalesTrainerAssetRevision:
        working = await self._working_revision()
        if working is not None and not overwrite_working:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_WORKING_REVISION_EXISTS]",
                "学习专题已有未发布草稿，请预览后发布，或明确覆盖草稿。",
                409,
            )
        active_path = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        if active_path is None:
            raise LearningTopicConfigError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "新人训练路径缺少 active revision，无法从商务技巧模块生成学习专题草稿。",
                409,
            )
        path_payload = payload_from_revision(active_path)
        source_module = next(
            (
                module
                for module in path_payload.modules
                if module.module_key == BUSINESS_SKILLS_SOURCE_MODULE_KEY
            ),
            None,
        )
        if source_module is None:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_SOURCE_MODULE_MISSING]",
                "active path 中未找到 business_skills 模块，无法生成商务礼仪规范草稿。",
                404,
            )
        topic_payload = NewcomerLearningTopicsPayload(
            topics=[
                NewcomerLearningTopicConfig(
                    topic_key=BUSINESS_ETIQUETTE_TOPIC_KEY,
                    source_module_key=BUSINESS_SKILLS_SOURCE_MODULE_KEY,
                    enabled=source_module.enabled,
                    title="商务礼仪规范",
                    description=source_module.description,
                    order_index=1,
                    learning_content_id=source_module.learning_content_id,
                    learning_units=list(source_module.learning_units),
                    ai_coach=source_module.ai_coach,
                    required=False,
                    blocks_next=False,
                    score_display_policy="quiz_attempt_score",
                )
            ]
        )
        self._validate_payload_for_write(topic_payload)
        await self._validate_ai_coach_prompt_bindings(topic_payload)
        active = await self._active_revision()
        change_class = classify_learning_topic_change(active, topic_payload)
        try:
            revision = await self._revisions.save_working_revision(
                resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
                logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
                payload=topic_payload.model_dump(mode="json"),
                actor=actor,
                change_class=change_class,
                source_revision_id=str(active.revision_id) if active else None,
                reason=reason or "从 active path business_skills 生成学习专题草稿",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise LearningTopicConfigError(
                exc.code, exc.message, exc.status_code
            ) from exc
        await self._record_event(
            actor=actor,
            action="newcomer_learning_topics.generate_business_etiquette_draft",
            before_revision_id=str(active.revision_id) if active else None,
            after_revision_id=str(revision.revision_id),
            reason=reason,
            trace_id=trace_id,
            change_class=change_class,
            extra_metadata={
                "source_path_revision_id": str(active_path.revision_id),
                "source_path_revision_no": active_path.revision_no,
                "overwrite_working": overwrite_working,
            },
        )
        await self._db.commit()
        return revision

    async def generate_customer_faq_draft(
        self,
        *,
        raw_text: str,
        actor: User,
        overwrite_working: bool = False,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> SalesTrainerAssetRevision:
        working = await self._working_revision()
        if working is not None and not overwrite_working:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_WORKING_REVISION_EXISTS]",
                "学习专题已有未发布草稿，请预览后发布，或明确覆盖草稿。",
                409,
            )
        parsed = parse_customer_faq_material(raw_text)
        if not parsed.cards:
            raise LearningTopicConfigError(
                "[CUSTOMER_FAQ_IMPORT_EMPTY]",
                "未从材料中解析到客户问答，请检查材料格式。",
                422,
            )
        active = await self._active_revision()
        base_payload = (
            payload_from_learning_topic_revision(working or active)
            if (working or active)
            else NewcomerLearningTopicsPayload()
        )
        topic_payload = _upsert_customer_faq_topic(base_payload, parsed)
        self._validate_payload_for_write(topic_payload)
        await self._validate_ai_coach_prompt_bindings(topic_payload)
        change_class = classify_learning_topic_change(active, topic_payload)
        try:
            revision = await self._revisions.save_working_revision(
                resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
                logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
                payload=topic_payload.model_dump(mode="json"),
                actor=actor,
                change_class=change_class,
                source_revision_id=str(active.revision_id) if active else None,
                reason=reason or "导入客户常见问答并生成学习专题草稿",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise LearningTopicConfigError(
                exc.code, exc.message, exc.status_code
            ) from exc
        await self._record_event(
            actor=actor,
            action="newcomer_learning_topics.generate_customer_faq_draft",
            before_revision_id=str(active.revision_id) if active else None,
            after_revision_id=str(revision.revision_id),
            reason=reason,
            trace_id=trace_id,
            change_class=change_class,
            extra_metadata={
                "topic_key": CUSTOMER_FAQ_TOPIC_KEY,
                "card_count": len(parsed.cards),
                "duplicate_group_count": len(parsed.duplicate_groups),
                "high_risk_count": parsed.high_risk_count,
                "escalation_count": parsed.escalation_count,
            },
        )
        await self._db.commit()
        return revision

    async def publish_preview(self) -> dict[str, Any]:
        active, working, payload = await self._prepare_publish_target()
        await self._validate_payload_for_publish(payload)
        return self._preview_payload(
            action="newcomer_learning_topics.publish",
            active=active,
            target=working,
            target_payload=payload,
        )

    async def publish_config(
        self,
        *,
        actor: User,
        reason: str,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        _, working, payload = await self._prepare_publish_target()
        await self._validate_payload_for_publish(payload)
        try:
            result = await self._revisions.publish_working_revision(
                working,
                actor=actor,
                reason=reason,
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise LearningTopicConfigError(
                exc.code, exc.message, exc.status_code
            ) from exc
        await self._record_event(
            actor=actor,
            action="newcomer_learning_topics.publish",
            before_revision_id=result.previous_revision_id,
            after_revision_id=str(result.revision.revision_id),
            reason=reason,
            trace_id=trace_id,
            change_class=str(result.revision.change_class),
        )
        await self._db.commit()
        return result

    async def rollback_preview(self, revision_id: str) -> dict[str, Any]:
        active = await self._active_revision()
        target = await self._revision_by_id(revision_id)
        payload = payload_from_learning_topic_revision(target)
        await self._validate_payload_for_publish(payload)
        return self._preview_payload(
            action="newcomer_learning_topics.rollback",
            active=active,
            target=target,
            target_payload=payload,
        )

    async def rollback_config(
        self,
        *,
        revision_id: str,
        actor: User,
        reason: str,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        target = await self._revision_by_id(revision_id)
        await self._validate_payload_for_publish(
            payload_from_learning_topic_revision(target)
        )
        try:
            result = await self._revisions.rollback_to_revision(
                target,
                actor=actor,
                reason=reason,
                trace_id=trace_id,
                expected_resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
                expected_logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise LearningTopicConfigError(
                exc.code, exc.message, exc.status_code
            ) from exc
        await self._record_event(
            actor=actor,
            action="newcomer_learning_topics.rollback",
            before_revision_id=result.previous_revision_id,
            after_revision_id=str(result.revision.revision_id),
            reason=reason,
            trace_id=trace_id,
            change_class=str(result.revision.change_class),
        )
        await self._db.commit()
        return result

    async def list_revisions(self) -> list[dict[str, Any]]:
        active = await self._active_revision()
        active_id = str(active.revision_id) if active else None
        revisions = await self._revisions.list_revisions(
            resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
            logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        )
        return [
            learning_topic_revision_summary(revision, active_id)
            for revision in revisions
        ]

    async def changed_high_risk_fields_for_publish(self) -> set[str]:
        active = await self._active_revision()
        working = await self._working_revision()
        if working is None:
            return set()
        return changed_learning_topic_ai_coach_high_risk_fields(
            payload_from_learning_topic_revision(active)
            if active is not None
            else None,
            payload_from_learning_topic_revision(working),
        )

    async def changed_high_risk_fields_for_rollback(self, revision_id: str) -> set[str]:
        active = await self._active_revision()
        target = await self._revision_by_id(revision_id)
        return changed_learning_topic_ai_coach_high_risk_fields(
            payload_from_learning_topic_revision(active)
            if active is not None
            else None,
            payload_from_learning_topic_revision(target),
        )

    async def _active_revision(self) -> SalesTrainerAssetRevision | None:
        return await self._revisions.active_revision(
            resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
            logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        )

    async def _working_revision(self) -> SalesTrainerAssetRevision | None:
        return await self._revisions.latest_working_revision(
            resource_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
            logical_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
        )

    async def _revision_by_id(self, revision_id: str) -> SalesTrainerAssetRevision:
        revision = await self._revisions.revision_by_id(revision_id)
        if revision is None:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_REVISION_NOT_FOUND]",
                "学习专题历史版本不存在。",
                404,
            )
        if (
            revision.resource_type != NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE
            or revision.logical_id != NEWCOMER_LEARNING_TOPICS_LOGICAL_ID
        ):
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_REVISION_TARGET_MISMATCH]",
                "学习专题回滚目标与当前配置不匹配。",
                409,
            )
        return revision

    async def _prepare_publish_target(
        self,
    ) -> tuple[
        SalesTrainerAssetRevision | None,
        SalesTrainerAssetRevision,
        NewcomerLearningTopicsPayload,
    ]:
        active = await self._active_revision()
        working = await self._working_revision()
        if working is None:
            raise LearningTopicConfigError(
                "[LEARNING_TOPIC_WORKING_REVISION_MISSING]",
                "没有待发布的学习专题草稿。",
                409,
            )
        return active, working, payload_from_learning_topic_revision(working)

    def _validate_payload_for_write(
        self, payload: NewcomerLearningTopicsPayload
    ) -> None:
        for topic in payload.topics:
            if topic.required or topic.blocks_next:
                raise LearningTopicConfigError(
                    "[LEARNING_TOPIC_CONFIG_INVALID]",
                    "学习专题必须保持非阻塞，required 和 blocks_next 只能为 false。",
                    422,
                )
            if topic.score_display_policy != "quiz_attempt_score":
                raise LearningTopicConfigError(
                    "[LEARNING_TOPIC_CONFIG_INVALID]",
                    "学习专题得分展示只能使用 quiz_attempt_score。",
                    422,
                )

    async def _validate_payload_for_publish(
        self,
        payload: NewcomerLearningTopicsPayload,
    ) -> None:
        self._validate_payload_for_write(payload)
        for topic in payload.topics:
            if not topic.enabled:
                continue
            if topic.content_kind == "faq_cards":
                published_cards = [
                    card for card in topic.faq_cards if card.status == "published"
                ]
                if not published_cards:
                    raise LearningTopicConfigError(
                        "[LEARNING_TOPIC_CARDS_MISSING]",
                        f"{topic.title} 缺少已发布问答卡片。",
                        409,
                    )
                card_keys = {card.card_key for card in published_cards}
                enabled_units = [unit for unit in topic.learning_units if unit.enabled]
                if not enabled_units:
                    raise LearningTopicConfigError(
                        "[LEARNING_TOPIC_UNITS_MISSING]",
                        f"{topic.title} 缺少启用的小单元配置。",
                        409,
                    )
                for unit in enabled_units:
                    unknown_card_keys = sorted(set(unit.source_card_keys) - card_keys)
                    if unknown_card_keys:
                        raise LearningTopicConfigError(
                            "[LEARNING_TOPIC_UNIT_CARDS_INVALID]",
                            f"{topic.title} 小单元“{unit.title}”绑定了不存在或未发布的问答卡片。",
                            409,
                        )
                if topic.ai_coach is not None and topic.ai_coach.enabled:
                    module = module_config_from_learning_topic(topic)
                    await SalesTrainerPathConfigService(
                        self._db
                    ).validate_ai_coach_prompt_bindings_for_modules([module])
                continue
            if not topic.learning_content_id:
                raise LearningTopicConfigError(
                    "[LEARNING_TOPIC_CONTENT_MISSING]",
                    f"{topic.title} 缺少已发布学习文章绑定。",
                    409,
                )
            content = await get_learning_content(self._db, topic.learning_content_id)
            if content is None or content.status != "published":
                raise LearningTopicConfigError(
                    "[LEARNING_TOPIC_CONTENT_INVALID]",
                    f"{topic.title} 绑定的学习文章不存在或未发布。",
                    409,
                )
            enabled_units = [unit for unit in topic.learning_units if unit.enabled]
            if not enabled_units:
                raise LearningTopicConfigError(
                    "[LEARNING_TOPIC_UNITS_MISSING]",
                    f"{topic.title} 缺少启用的小单元配置。",
                    409,
                )
            if topic.ai_coach is not None and topic.ai_coach.enabled:
                module = module_config_from_learning_topic(topic)
                await SalesTrainerPathConfigService(
                    self._db
                ).validate_ai_coach_prompt_bindings_for_modules([module])

    async def _validate_ai_coach_prompt_bindings(
        self,
        payload: NewcomerLearningTopicsPayload,
    ) -> None:
        modules = [
            module_config_from_learning_topic(topic)
            for topic in payload.topics
            if topic.ai_coach is not None and topic.ai_coach.enabled
        ]
        if modules:
            await SalesTrainerPathConfigService(
                self._db
            ).validate_ai_coach_prompt_bindings_for_modules(modules)

    def _preview_payload(
        self,
        *,
        action: Literal[
            "newcomer_learning_topics.publish",
            "newcomer_learning_topics.rollback",
        ],
        active: SalesTrainerAssetRevision | None,
        target: SalesTrainerAssetRevision,
        target_payload: NewcomerLearningTopicsPayload,
    ) -> dict[str, Any]:
        active_payload = (
            payload_from_learning_topic_revision(active) if active else None
        )
        changed_topic_keys = _changed_topic_keys(active_payload, target_payload)
        risk_reasons = []
        if any(
            topic.ai_coach and topic.ai_coach.enabled for topic in target_payload.topics
        ):
            risk_reasons.append("AI Coach 配置将影响后续学习专题入口。")
        return {
            "action": action,
            "permission": "sales_trainer.manage_modules",
            "requires_reason": True,
            "requires_trace_id": True,
            "future_only": True,
            "risk_level": "medium" if risk_reasons else "low",
            "risk_reasons": risk_reasons,
            "change_class": target.change_class,
            "target_revision_id": str(target.revision_id),
            "target_revision_no": target.revision_no,
            "target_revision_status": target.status,
            "impact_scope": {
                "future_learner_display_only": True,
                "historical_attempts_changed": False,
                "changed_topic_keys": changed_topic_keys,
                "topic_count": len(target_payload.topics),
            },
            "before_snapshot": self._revisions.snapshot(active),
            "after_snapshot": self._revisions.snapshot(target),
            "audit_event": {
                "action": action,
                "target_type": NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
                "target_id": NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
            },
            "rollback_hint": {
                "rollback_via_active_revision": True,
                "mutates_history": False,
                "historical_attempts_preserved": True,
            },
        }

    def _diagnostics(
        self,
        *,
        active: SalesTrainerAssetRevision | None,
        working: SalesTrainerAssetRevision | None,
        payload: NewcomerLearningTopicsPayload,
    ) -> list[dict[str, Any]]:
        diagnostics: list[dict[str, Any]] = []
        if active is None:
            diagnostics.append(
                {
                    "code": "[LEARNING_TOPIC_ACTIVE_REVISION_MISSING]",
                    "message": "学习专题尚未发布，前台不会展示任何学习专题。",
                    "severity": "warning",
                    "terminal": False,
                }
            )
        if working is not None:
            diagnostics.append(
                {
                    "code": "[LEARNING_TOPIC_WORKING_REVISION_EXISTS]",
                    "message": "学习专题存在未发布草稿，需发布后才会影响前台展示。",
                    "severity": "info",
                    "terminal": False,
                }
            )
        for topic in payload.topics:
            expected_unit_count = 8 if topic.topic_key == CUSTOMER_FAQ_TOPIC_KEY else 7
            if (
                topic.enabled
                and len([unit for unit in topic.learning_units if unit.enabled])
                != expected_unit_count
            ):
                diagnostics.append(
                    {
                        "code": "[LEARNING_TOPIC_UNIT_COUNT_REVIEW]",
                        "message": f"{topic.title} 当前启用小单元不是 {expected_unit_count} 个，请确认是否符合培训设计。",
                        "severity": "warning",
                        "terminal": False,
                    }
                )
        return diagnostics

    async def _record_event(
        self,
        *,
        actor: User,
        action: str,
        before_revision_id: str | None,
        after_revision_id: str,
        reason: str | None,
        trace_id: str | None,
        change_class: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = {
            "logical_id": NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
            "resource_type": NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
            "before_revision_id": before_revision_id,
            "after_revision_id": after_revision_id,
            "reason": reason,
            "trace_id": trace_id,
            "change_class": change_class,
            "impact_scope": "future_learners_only",
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        await self._logs.record(
            actor=actor,
            action=action,
            target_type=NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE,
            target_id=NEWCOMER_LEARNING_TOPICS_LOGICAL_ID,
            request_id=trace_id,
            metadata=metadata,
        )


def payload_from_learning_topic_revision(
    revision: SalesTrainerAssetRevision | None,
) -> NewcomerLearningTopicsPayload:
    if revision is None:
        return NewcomerLearningTopicsPayload()
    try:
        return NewcomerLearningTopicsPayload.model_validate(revision.payload_json)
    except ValidationError as exc:
        raise LearningTopicConfigError(
            "[LEARNING_TOPIC_REVISION_INVALID]",
            "学习专题历史版本内容无法读取。",
            500,
        ) from exc


def business_etiquette_topic_from_payload(
    payload: NewcomerLearningTopicsPayload,
) -> NewcomerLearningTopicConfig | None:
    return next(
        (
            topic
            for topic in payload.topics
            if topic.topic_key == BUSINESS_ETIQUETTE_TOPIC_KEY
        ),
        None,
    )


def customer_faq_topic_from_payload(
    payload: NewcomerLearningTopicsPayload,
) -> NewcomerLearningTopicConfig | None:
    return next(
        (
            topic
            for topic in payload.topics
            if topic.topic_key == CUSTOMER_FAQ_TOPIC_KEY
        ),
        None,
    )


def module_config_from_learning_topic(
    topic: NewcomerLearningTopicConfig,
) -> NewcomerPathModuleConfig:
    return NewcomerPathModuleConfig(
        module_key=topic.source_module_key,
        module_type="article_exam",
        enabled=topic.enabled,
        order_index=topic.order_index,
        title=topic.title,
        description=topic.description,
        learning_content_id=topic.learning_content_id,
        completion_rule="submitted",
        primary_action_label="开始学习",
        retry_action_label="继续学习",
        review_action_label="复盘学习",
        ai_coach=topic.ai_coach,
        learning_units=list(topic.learning_units),
    )


def _upsert_customer_faq_topic(
    payload: NewcomerLearningTopicsPayload,
    parsed: Any,
) -> NewcomerLearningTopicsPayload:
    cards_by_category = _customer_faq_cards_by_category(parsed.cards)
    units = _customer_faq_learning_units(cards_by_category)
    topic = NewcomerLearningTopicConfig(
        topic_key=CUSTOMER_FAQ_TOPIC_KEY,
        source_module_key=CUSTOMER_FAQ_SOURCE_MODULE_KEY,
        content_kind="faq_cards",
        enabled=True,
        title="客户常见问答",
        description="按客户真实问题训练新人标准口径、案例表达、风险边界和现场应答。",
        order_index=2,
        faq_cards=list(parsed.cards),
        duplicate_groups=list(parsed.duplicate_groups),
        evidence_cases=list(parsed.evidence_cases),
        audio_scenario_key=CUSTOMER_FAQ_AUDIO_SCENARIO_KEY,
        learning_units=units,
        required=False,
        blocks_next=False,
        score_display_policy="quiz_attempt_score",
    )
    topics = [
        item for item in payload.topics if item.topic_key != CUSTOMER_FAQ_TOPIC_KEY
    ]
    topics.append(topic)
    topics.sort(key=lambda item: item.order_index)
    return payload.model_copy(update={"topics": topics})


def _customer_faq_cards_by_category(cards: list[Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for card in cards:
        if getattr(card, "status", None) == "archived":
            continue
        category = str(getattr(card, "category", "") or "产品能力")
        result.setdefault(category, []).append(str(card.card_key))
    return result


def _customer_faq_learning_units(
    cards_by_category: dict[str, list[str]],
) -> list[Any]:
    from sales_trainer.schemas import BusinessEtiquetteTrainingUnitConfig

    unit_specs = [
        ("company_value", "公司与核心价值", ["产品能力", "行业案例"]),
        ("product_capability", "产品能力基础", ["产品能力", "合规审计"]),
        ("deployment_architecture", "部署与架构", ["部署架构"]),
        ("industry_cases", "行业案例", ["行业案例"]),
        ("competition_boundary", "竞品与替代关系", ["竞品关系"]),
        ("poc_delivery", "POC 与交付", ["交付问题", "商务政策"]),
        ("high_risk_technology", "高风险技术问题", ["技术限制", "部署架构"]),
        ("field_expression", "客户现场表达训练", ["商务政策", "竞品关系", "合规审计"]),
    ]
    all_card_keys = [
        card_key for card_keys in cards_by_category.values() for card_key in card_keys
    ]
    units = []
    for index, (unit_key, title, categories) in enumerate(unit_specs, start=1):
        card_keys: list[str] = []
        for category in categories:
            card_keys.extend(cards_by_category.get(category, []))
        if not card_keys and all_card_keys:
            card_keys = all_card_keys[(index - 1) :: len(unit_specs)]
        units.append(
            BusinessEtiquetteTrainingUnitConfig(
                unit_key=unit_key,
                title=title,
                description=f"学习并演练{title}相关客户问答。",
                order_index=index,
                enabled=True,
                source_card_keys=list(dict.fromkeys(card_keys))[:20],
                source_chapter_orders=[],
                capability_keys=["customer_perspective", "objection_handling"],
                require_reading=True,
                require_quiz=True,
                require_ai_coach=index in {5, 7, 8},
                ai_coach_required_capability_keys=[
                    "customer_perspective",
                    "objection_handling",
                ],
                ai_coach_block_next_until_passed=False,
                quiz_question_count=5,
                quiz_pass_threshold=80,
                allow_skip_reading=True,
                block_next_until_complete=False,
                empty_state_message="当前单元尚未绑定问答卡片，请管理员在客户常见问答专题中补齐。",
            )
        )
    return units


def classify_learning_topic_change(
    active: SalesTrainerAssetRevision | None,
    payload: NewcomerLearningTopicsPayload,
) -> AssetChangeClass:
    if active is None:
        return "binding"
    previous = payload_from_learning_topic_revision(active)
    if _topic_refs(previous) != _topic_refs(payload):
        return "binding"
    if changed_learning_topic_ai_coach_high_risk_fields(previous, payload):
        return "scoring_high_risk"
    return "semantic"


def learning_topic_revision_summary(
    revision: SalesTrainerAssetRevision,
    active_revision_id: str | None,
) -> dict[str, Any]:
    payload = payload_from_learning_topic_revision(revision)
    revision_id = str(revision.revision_id)
    return {
        "revision_id": revision_id,
        "revision_no": revision.revision_no,
        "status": revision.status,
        "change_class": revision.change_class,
        "title": "新人训练学习专题",
        "topic_count": len(payload.topics),
        "is_active": revision_id == active_revision_id,
        "is_working": str(revision.status) == "working",
        "source_revision_id": revision.source_revision_id,
        "payload_hash": revision.payload_hash,
        "reason": revision.reason,
        "trace_id": revision.trace_id,
        "created_by": revision.created_by,
        "published_by": revision.published_by,
        "created_at": revision.created_at,
        "published_at": revision.published_at,
    }


def changed_learning_topic_ai_coach_high_risk_fields(
    current_payload: NewcomerLearningTopicsPayload | None,
    incoming_payload: NewcomerLearningTopicsPayload,
) -> set[str]:
    current_by_key = _ai_coach_by_topic(
        current_payload or NewcomerLearningTopicsPayload()
    )
    incoming_by_key = _ai_coach_by_topic(incoming_payload)
    changed: set[str] = set()
    for topic_key, previous in current_by_key.items():
        if previous and topic_key not in incoming_by_key:
            changed.update(AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS)
    for topic_key, incoming in incoming_by_key.items():
        previous = current_by_key.get(topic_key, {})
        changed.update(
            field
            for field in AI_COACH_FIELDS_REQUIRING_MANAGE_PROMPTS
            if incoming.get(field) != previous.get(field)
        )
    return changed


def _ai_coach_by_topic(
    payload: NewcomerLearningTopicsPayload,
) -> dict[str, dict[str, Any]]:
    return {
        topic.topic_key: topic.ai_coach.model_dump(mode="json")
        if topic.ai_coach
        else {}
        for topic in payload.topics
    }


def _topic_refs(payload: NewcomerLearningTopicsPayload | None) -> list[tuple[Any, ...]]:
    if payload is None:
        return []
    return [
        (
            topic.topic_key,
            topic.enabled,
            topic.learning_content_id,
            tuple(
                (
                    unit.unit_key,
                    unit.enabled,
                    unit.order_index,
                    tuple(unit.source_chapter_orders),
                    tuple(unit.source_card_keys),
                    tuple(unit.capability_keys),
                    unit.quiz_question_count,
                    unit.quiz_pass_threshold,
                    unit.quiz_allow_retake,
                    unit.quiz_max_attempts,
                )
                for unit in sorted(
                    topic.learning_units, key=lambda item: item.order_index
                )
            ),
        )
        for topic in sorted(payload.topics, key=lambda item: item.order_index)
    ]


def _changed_topic_keys(
    previous: NewcomerLearningTopicsPayload | None,
    current: NewcomerLearningTopicsPayload,
) -> list[str]:
    previous_topics = {
        topic.topic_key: topic for topic in (previous.topics if previous else [])
    }
    changed: list[str] = []
    for topic in current.topics:
        if previous_topics.get(topic.topic_key) != topic:
            changed.append(topic.topic_key)
    return changed
