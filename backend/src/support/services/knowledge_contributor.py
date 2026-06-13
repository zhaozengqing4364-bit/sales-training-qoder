from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.schemas import AssetGovernanceSummary
from common.knowledge.contributors import (
    register_knowledge_governance_summary_contributor,
)
from support.services.runtime_status_service import RuntimeStatusService

SUPPORT_KNOWLEDGE_GOVERNANCE_CONTRIBUTOR = "support.knowledge_governance"


async def build_support_knowledge_governance_summary(
    db: AsyncSession,
    item: Any,
    documents: list[Any],
    now: datetime,
) -> dict[str, Any] | None:
    governance_indexes = await RuntimeStatusService(db).build_asset_governance_indexes()
    seven_days_ago = now - timedelta(days=7)
    item_updated_at = RuntimeStatusService._coerce_datetime(item.updated_at)
    latest_document = max(
        documents,
        key=lambda document: (
            RuntimeStatusService._coerce_datetime(document.created_at)
            or datetime.min.replace(tzinfo=UTC)
        ),
        default=None,
    )
    latest_document_created_at = (
        RuntimeStatusService._coerce_datetime(latest_document.created_at)
        if latest_document is not None
        else None
    )
    last_changed_at = item_updated_at
    latest_change_type = "knowledge_base_updated"
    latest_change_label = "知识库配置更新"
    if (
        latest_document is not None
        and latest_document_created_at is not None
        and (item_updated_at is None or latest_document_created_at >= item_updated_at)
    ):
        last_changed_at = latest_document_created_at
        latest_change_type = "document_uploaded"
        latest_change_label = f"最近文档：{latest_document.title}"

    change_count_7d = sum(
        1
        for document in documents
        if (
            RuntimeStatusService._coerce_datetime(document.created_at)
            or datetime.min.replace(tzinfo=UTC)
        )
        >= seven_days_ago
    )
    if item_updated_at is not None and item_updated_at >= seven_days_ago:
        change_count_7d += 1

    extra_anomalies: list[dict[str, Any]] = []
    failed_documents = [
        document for document in documents if str(document.status) == "failed"
    ]
    if failed_documents:
        failed_at_values = [
            RuntimeStatusService._coerce_datetime(document.created_at)
            for document in failed_documents
        ]
        latest_failed_at = max(
            (value for value in failed_at_values if value is not None),
            default=None,
        )
        extra_anomalies.append(
            {
                "source": "asset",
                "kind": "document_failed",
                "severity": "warning",
                "summary": f"{len(failed_documents)} 个文档处理失败，需复核解析链路。",
                "detected_at": latest_failed_at,
                "session_id": None,
            }
        )

    processing_documents = [
        document
        for document in documents
        if str(document.status) in {"pending", "processing"}
    ]
    if processing_documents:
        processing_at_values = [
            RuntimeStatusService._coerce_datetime(document.created_at)
            for document in processing_documents
        ]
        latest_processing_at = max(
            (value for value in processing_at_values if value is not None),
            default=None,
        )
        extra_anomalies.append(
            {
                "source": "asset",
                "kind": "document_processing",
                "severity": "warning",
                "summary": f"{len(processing_documents)} 个文档仍在处理中。",
                "detected_at": latest_processing_at,
                "session_id": None,
            }
        )

    summary = RuntimeStatusService.build_asset_governance_summary(
        governance_indexes.get("knowledge_base", {}).get(str(item.id)),
        last_changed_at=last_changed_at,
        latest_change_type=latest_change_type,
        latest_change_label=latest_change_label,
        change_count_7d=change_count_7d,
        extra_anomalies=extra_anomalies,
    )
    return AssetGovernanceSummary.model_validate(summary).model_dump(mode="json")


def register_support_knowledge_contributor() -> None:
    register_knowledge_governance_summary_contributor(
        SUPPORT_KNOWLEDGE_GOVERNANCE_CONTRIBUTOR,
        build_support_knowledge_governance_summary,
    )
