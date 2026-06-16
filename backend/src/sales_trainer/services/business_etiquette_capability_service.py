from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.schemas import (
    BusinessEtiquetteCapabilityConfig,
    BusinessEtiquetteCapabilitySnapshotResponse,
    BusinessEtiquetteChapterCapabilityBinding,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)
from sales_trainer.services.operation_log_service import OperationLogService

CapabilitySnapshotSource = Literal[
    "working_revision",
    "active_revision",
    "default_seed",
]

CAPABILITY_SNAPSHOT_KEY = "capability_snapshot"
CAPABILITY_SNAPSHOT_SCHEMA_VERSION = 1
BUSINESS_ETIQUETTE_CAPABILITY_MANAGEMENT_ENTRY = (
    "/admin/sales-trainer/articles/capabilities"
)


class BusinessEtiquetteCapabilityServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BusinessEtiquetteCapabilityService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._revisions = SalesTrainerAssetRevisionService(db)
        self._logs = OperationLogService(db)

    async def get_snapshot(
        self,
        *,
        training_pack_key: str | None = None,
    ) -> BusinessEtiquetteCapabilitySnapshotResponse:
        logical_id = _normalize_training_pack_key(training_pack_key)
        working_revision = await self._revisions.latest_working_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        active_revision = await self._revisions.active_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        source_revision = working_revision or active_revision
        if source_revision is not None:
            snapshot = _snapshot_from_payload(source_revision.payload_json)
            if snapshot is not None:
                return _snapshot_response(
                    logical_id=logical_id,
                    capabilities=snapshot["capabilities"],
                    chapter_bindings=snapshot["chapter_bindings"],
                    source=(
                        "working_revision"
                        if working_revision is not None
                        else "active_revision"
                    ),
                    working_revision=working_revision,
                    active_revision=active_revision,
                    original_chapter_count=_original_chapter_count(
                        source_revision.payload_json
                    ),
                    needs_save=False,
                )

        default_snapshot = default_business_etiquette_capability_snapshot()
        return _snapshot_response(
            logical_id=logical_id,
            capabilities=default_snapshot["capabilities"],
            chapter_bindings=default_snapshot["chapter_bindings"],
            source="default_seed",
            working_revision=working_revision,
            active_revision=active_revision,
            original_chapter_count=_original_chapter_count(
                source_revision.payload_json if source_revision is not None else {}
            ),
            needs_save=True,
        )

    async def save_snapshot(
        self,
        *,
        capabilities: list[BusinessEtiquetteCapabilityConfig],
        chapter_bindings: list[BusinessEtiquetteChapterCapabilityBinding],
        actor: User,
        training_pack_key: str | None = None,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> BusinessEtiquetteCapabilitySnapshotResponse:
        return await self._save_snapshot(
            capabilities=capabilities,
            chapter_bindings=chapter_bindings,
            actor=actor,
            training_pack_key=training_pack_key,
            reason=reason or "保存商务礼仪能力点快照草稿",
            trace_id=trace_id,
            audit_action="business_etiquette_training_pack.capabilities_saved",
            audit_metadata={},
        )

    async def update_capability_status(
        self,
        *,
        capability_key: str,
        status: Literal["published", "archived"],
        actor: User,
        training_pack_key: str | None = None,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> BusinessEtiquetteCapabilitySnapshotResponse:
        snapshot = await self.get_snapshot(training_pack_key=training_pack_key)
        found = False
        capabilities: list[BusinessEtiquetteCapabilityConfig] = []
        for capability in snapshot.capabilities:
            if capability.capability_key == capability_key:
                found = True
                capabilities.append(capability.model_copy(update={"status": status}))
            else:
                capabilities.append(capability)
        if not found:
            raise BusinessEtiquetteCapabilityServiceError(
                "[BUSINESS_ETIQUETTE_CAPABILITY_NOT_FOUND]",
                "能力点不存在。",
                404,
            )
        action_label = "发布" if status == "published" else "归档"
        return await self._save_snapshot(
            capabilities=capabilities,
            chapter_bindings=snapshot.chapter_bindings,
            actor=actor,
            training_pack_key=snapshot.training_pack_key,
            reason=reason or f"{action_label}商务礼仪能力点 {capability_key}",
            trace_id=trace_id,
            audit_action=(
                "business_etiquette_training_pack.capability_published"
                if status == "published"
                else "business_etiquette_training_pack.capability_archived"
            ),
            audit_metadata={
                "capability_key": capability_key,
                "status": status,
            },
        )

    async def published_capabilities_by_key(
        self,
        *,
        training_pack_key: str | None = None,
    ) -> dict[str, BusinessEtiquetteCapabilityConfig]:
        logical_id = _normalize_training_pack_key(training_pack_key)
        active_revision = await self._revisions.active_revision(
            resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
            logical_id=logical_id,
        )
        if active_revision is None:
            return {}
        snapshot = _snapshot_from_payload(active_revision.payload_json)
        if snapshot is None:
            return {}
        return {
            capability.capability_key: capability
            for capability in snapshot["capabilities"]
            if capability.status == "published"
        }

    async def _save_snapshot(
        self,
        *,
        capabilities: list[BusinessEtiquetteCapabilityConfig],
        chapter_bindings: list[BusinessEtiquetteChapterCapabilityBinding],
        actor: User,
        training_pack_key: str | None,
        reason: str,
        trace_id: str | None,
        audit_action: str,
        audit_metadata: dict[str, Any],
    ) -> BusinessEtiquetteCapabilitySnapshotResponse:
        logical_id = _normalize_training_pack_key(training_pack_key)
        base_revision = await self._base_revision_for_save(logical_id)
        validated_capabilities, validated_bindings = _validate_snapshot(
            capabilities=capabilities,
            chapter_bindings=chapter_bindings,
            base_payload=base_revision.payload_json,
        )
        payload = deepcopy(base_revision.payload_json or {})
        updated_at = datetime.now(UTC)
        payload[CAPABILITY_SNAPSHOT_KEY] = {
            "schema_version": CAPABILITY_SNAPSHOT_SCHEMA_VERSION,
            "capabilities": [
                capability.model_dump(mode="json")
                for capability in validated_capabilities
            ],
            "chapter_bindings": [
                binding.model_dump(mode="json") for binding in validated_bindings
            ],
            "updated_by": str(actor.user_id),
            "updated_at": updated_at.isoformat(),
            "management_entry": BUSINESS_ETIQUETTE_CAPABILITY_MANAGEMENT_ENTRY,
        }
        payload["training_pack_key"] = logical_id

        try:
            working_revision = await self._revisions.save_working_revision(
                resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
                logical_id=logical_id,
                payload=payload,
                actor=actor,
                change_class="semantic",
                source_revision_id=str(base_revision.revision_id),
                reason=reason,
                trace_id=trace_id,
            )
            active_revision = await self._revisions.active_revision(
                resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
                logical_id=logical_id,
            )
            await self._logs.record(
                actor=actor,
                action=audit_action,
                target_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
                target_id=logical_id,
                request_id=trace_id,
                metadata={
                    "training_pack_key": logical_id,
                    "source_revision_id": str(base_revision.revision_id),
                    "working_revision_id": str(working_revision.revision_id),
                    "working_revision_no": working_revision.revision_no,
                    "active_revision_id": (
                        str(active_revision.revision_id)
                        if active_revision is not None
                        else None
                    ),
                    "capability_count": len(validated_capabilities),
                    "chapter_binding_count": len(validated_bindings),
                    "trace_id": trace_id,
                    **audit_metadata,
                },
            )
            await self._db.commit()
        except Exception:
            await self._db.rollback()
            raise

        return _snapshot_response(
            logical_id=logical_id,
            capabilities=validated_capabilities,
            chapter_bindings=validated_bindings,
            source="working_revision",
            working_revision=working_revision,
            active_revision=active_revision,
            original_chapter_count=_original_chapter_count(payload),
            needs_save=False,
        )

    async def _base_revision_for_save(
        self,
        logical_id: str,
    ) -> SalesTrainerAssetRevision:
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
        raise BusinessEtiquetteCapabilityServiceError(
            "[BUSINESS_ETIQUETTE_TRAINING_PACK_REVISION_MISSING]",
            "请先导入商务礼仪训练包资料，再保存能力点快照。",
            409,
        )


def default_business_etiquette_capability_snapshot() -> dict[str, Any]:
    return {
        "schema_version": CAPABILITY_SNAPSHOT_SCHEMA_VERSION,
        "capabilities": [
            _capability(
                "respect_boundaries",
                "尊重与分寸感",
                "能识别商务场景中的边界、顺序、尊重表达和不越界行为。",
            ),
            _capability(
                "professional_image",
                "职业形象与仪态",
                "能根据场合管理着装、仪态、时间观念和第一印象。",
            ),
            _capability(
                "meeting_social_actions",
                "见面社交动作",
                "能完成称呼、介绍、握手、名片、目光和微笑等见面动作。",
            ),
            _capability(
                "business_communication",
                "商务沟通表达",
                "能在电话、当面、书面沟通中表达清楚、礼貌且专业。",
            ),
            _capability(
                "reception_visit_execution",
                "接待拜访准备与执行",
                "能完成拜访准备、接待引导、座次、茶水、送别和跟进。",
            ),
            _capability(
                "meeting_negotiation_order",
                "会议洽谈秩序",
                "能遵守会议纪律、发言边界、洽谈顺序和线上会议规范。",
            ),
            _capability(
                "dining_social_boundary",
                "餐饮应酬边界",
                "能处理餐桌座次、敬酒、买单和商务应酬边界。",
            ),
            _capability(
                "repair_reflection_internalization",
                "失误补救与复盘内化",
                "能在礼仪失误后及时补救，并通过复盘内化为稳定行为。",
            ),
        ],
        "chapter_bindings": [
            {"chapter_order": 1, "capability_keys": ["respect_boundaries"]},
            {"chapter_order": 2, "capability_keys": ["professional_image"]},
            {"chapter_order": 3, "capability_keys": ["meeting_social_actions"]},
            {"chapter_order": 4, "capability_keys": ["business_communication"]},
            {
                "chapter_order": 5,
                "capability_keys": ["reception_visit_execution"],
            },
            {
                "chapter_order": 6,
                "capability_keys": ["meeting_negotiation_order"],
            },
            {"chapter_order": 7, "capability_keys": ["dining_social_boundary"]},
            {
                "chapter_order": 8,
                "capability_keys": ["repair_reflection_internalization"],
            },
        ],
    }


def _capability(
    capability_key: str,
    display_name: str,
    description: str,
) -> dict[str, Any]:
    return {
        "capability_key": capability_key,
        "display_name": display_name,
        "description": description,
        "mastery_levels": [
            {
                "level_key": "not_mastered",
                "display_name": "未掌握",
                "min_score": 0,
                "description": "尚不能稳定识别或完成该能力要求。",
            },
            {
                "level_key": "basic_mastery",
                "display_name": "基本掌握",
                "min_score": 70,
                "description": "能在常见场景中完成基本动作，是默认达标线。",
            },
            {
                "level_key": "mastered",
                "display_name": "已掌握",
                "min_score": 85,
                "description": "能在多数商务场景中稳定应用。",
            },
            {
                "level_key": "field_ready",
                "display_name": "可上场",
                "min_score": 95,
                "description": "能在复杂场景中独立应用并处理变化。",
            },
        ],
        "default_threshold": 70,
        "evidence_rules": [
            {
                "evidence_type": "quiz_question",
                "weight": 1,
                "required": True,
                "description": "小单元测验题目命中该能力点并达到阈值。",
            },
            {
                "evidence_type": "ai_coach_card",
                "weight": 1,
                "required": True,
                "description": "AI 教练训练卡能给出符合场景的回答或判断。",
            },
            {
                "evidence_type": "manual_review",
                "weight": 0.5,
                "required": False,
                "description": "带教人或管理员人工复盘确认。",
            },
        ],
        "owner_scope": "business_etiquette_training_pack",
        "status": "draft",
    }


def _normalize_training_pack_key(training_pack_key: str | None) -> str:
    logical_id = (
        training_pack_key or DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY
    ).strip()
    if not logical_id:
        raise BusinessEtiquetteCapabilityServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_CONFIG_INVALID]",
            "商务礼仪训练包 key 不能为空。",
            400,
        )
    return logical_id


def _snapshot_from_payload(
    payload: dict[str, Any] | None,
) -> dict[str, list[Any]] | None:
    if not payload:
        return None
    raw_snapshot = payload.get(CAPABILITY_SNAPSHOT_KEY)
    if not isinstance(raw_snapshot, dict):
        return None
    raw_capabilities = raw_snapshot.get("capabilities")
    raw_chapter_bindings = raw_snapshot.get("chapter_bindings")
    if not isinstance(raw_capabilities, list) or not isinstance(
        raw_chapter_bindings,
        list,
    ):
        raise BusinessEtiquetteCapabilityServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_CONFIG_INVALID]",
            "商务礼仪能力点快照结构非法。",
            409,
        )
    try:
        return {
            "capabilities": [
                BusinessEtiquetteCapabilityConfig.model_validate(item)
                for item in raw_capabilities
            ],
            "chapter_bindings": [
                BusinessEtiquetteChapterCapabilityBinding.model_validate(item)
                for item in raw_chapter_bindings
            ],
        }
    except ValueError as exc:
        raise BusinessEtiquetteCapabilityServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_CONFIG_INVALID]",
            "商务礼仪能力点快照内容非法。",
            409,
        ) from exc


def _validate_snapshot(
    *,
    capabilities: list[BusinessEtiquetteCapabilityConfig],
    chapter_bindings: list[BusinessEtiquetteChapterCapabilityBinding],
    base_payload: dict[str, Any] | None,
) -> tuple[
    list[BusinessEtiquetteCapabilityConfig],
    list[BusinessEtiquetteChapterCapabilityBinding],
]:
    if not capabilities:
        raise BusinessEtiquetteCapabilityServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_CONFIG_INVALID]",
            "至少需要配置一个商务礼仪能力点。",
            422,
        )
    capability_keys = [capability.capability_key for capability in capabilities]
    duplicate_keys = sorted(
        {key for key in capability_keys if capability_keys.count(key) > 1}
    )
    if duplicate_keys:
        raise BusinessEtiquetteCapabilityServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_CONFIG_INVALID]",
            f"能力点 key 重复：{', '.join(duplicate_keys)}。",
            422,
        )
    active_keys = {
        capability.capability_key
        for capability in capabilities
        if capability.status != "archived"
    }
    for binding in chapter_bindings:
        if not binding.capability_keys:
            raise BusinessEtiquetteCapabilityServiceError(
                "[BUSINESS_ETIQUETTE_CAPABILITY_BINDING_INVALID]",
                f"第 {binding.chapter_order} 章至少需要绑定一个能力点。",
                422,
            )
        unknown_keys = sorted(set(binding.capability_keys) - active_keys)
        if unknown_keys:
            raise BusinessEtiquetteCapabilityServiceError(
                "[BUSINESS_ETIQUETTE_CAPABILITY_BINDING_INVALID]",
                f"第 {binding.chapter_order} 章绑定了不存在或已归档的能力点："
                f"{', '.join(unknown_keys)}。",
                422,
            )
    chapter_orders = [binding.chapter_order for binding in chapter_bindings]
    duplicate_chapter_orders = sorted(
        {order for order in chapter_orders if chapter_orders.count(order) > 1}
    )
    if duplicate_chapter_orders:
        raise BusinessEtiquetteCapabilityServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_BINDING_INVALID]",
            "章节能力点绑定不能包含重复章节。",
            422,
        )
    expected_orders = _available_chapter_orders(base_payload or {})
    invalid_orders = sorted(set(chapter_orders) - expected_orders)
    if expected_orders and invalid_orders:
        raise BusinessEtiquetteCapabilityServiceError(
            "[BUSINESS_ETIQUETTE_CAPABILITY_BINDING_INVALID]",
            f"章节能力点绑定引用了不存在的原文章节：{invalid_orders}。",
            422,
        )
    return capabilities, chapter_bindings


def _available_chapter_orders(payload: dict[str, Any]) -> set[int]:
    raw_chapters = payload.get("original_chapters")
    if isinstance(raw_chapters, list):
        orders = {
            int(chapter["order_index"])
            for chapter in raw_chapters
            if isinstance(chapter, dict) and isinstance(chapter.get("order_index"), int)
        }
        if orders:
            return orders
    chapter_count = _original_chapter_count(payload)
    if chapter_count is None:
        return set()
    return set(range(1, chapter_count + 1))


def _original_chapter_count(payload: dict[str, Any] | None) -> int | None:
    if not payload:
        return None
    raw_count = payload.get("original_chapter_count")
    return raw_count if isinstance(raw_count, int) else None


def _snapshot_response(
    *,
    logical_id: str,
    capabilities: list[BusinessEtiquetteCapabilityConfig] | list[dict[str, Any]],
    chapter_bindings: (
        list[BusinessEtiquetteChapterCapabilityBinding] | list[dict[str, Any]]
    ),
    source: CapabilitySnapshotSource,
    working_revision: SalesTrainerAssetRevision | None,
    active_revision: SalesTrainerAssetRevision | None,
    original_chapter_count: int | None,
    needs_save: bool,
) -> BusinessEtiquetteCapabilitySnapshotResponse:
    validated_capabilities = [
        BusinessEtiquetteCapabilityConfig.model_validate(item)
        for item in capabilities
    ]
    validated_bindings = [
        BusinessEtiquetteChapterCapabilityBinding.model_validate(item)
        for item in chapter_bindings
    ]
    return BusinessEtiquetteCapabilitySnapshotResponse(
        training_pack_key=logical_id,
        source=source,
        working_revision_id=(
            str(working_revision.revision_id)
            if working_revision is not None
            else None
        ),
        working_revision_no=(
            working_revision.revision_no if working_revision is not None else None
        ),
        active_revision_id=(
            str(active_revision.revision_id) if active_revision is not None else None
        ),
        active_revision_no=(
            active_revision.revision_no if active_revision is not None else None
        ),
        has_unpublished_revision=working_revision is not None,
        schema_version=CAPABILITY_SNAPSHOT_SCHEMA_VERSION,
        capabilities=validated_capabilities,
        chapter_bindings=validated_bindings,
        original_chapter_count=original_chapter_count,
        needs_save=needs_save,
        management_entry=BUSINESS_ETIQUETTE_CAPABILITY_MANAGEMENT_ENTRY,
    )
