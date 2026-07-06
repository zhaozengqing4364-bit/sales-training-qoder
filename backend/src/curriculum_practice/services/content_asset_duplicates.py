from __future__ import annotations

import uuid

from curriculum_practice.models import CaseItem
from curriculum_practice.services.content_asset_payloads import (
    case_item_content_hash,
    case_item_payload,
    copy_suffix,
)
from curriculum_practice.services.orm_payload_typing import orm_str


def build_case_item_duplicate(
    item: CaseItem,
    *,
    actor_id: str | None,
) -> CaseItem:
    payload = case_item_payload(item)
    payload["customer_role"] = copy_suffix(orm_str(item.customer_role))
    return CaseItem(
        case_item_id=str(uuid.uuid4()),
        industry=item.industry,
        company_profile=item.company_profile,
        customer_role=str(payload["customer_role"]),
        pain_points=list(item.pain_points or []),
        objections=list(item.objections or []),
        hidden_information=item.hidden_information,
        success_criteria=list(item.success_criteria or []),
        allowed_disclosure_policy=item.allowed_disclosure_policy or {},
        version=1,
        content_hash=case_item_content_hash(payload),
        status="draft",
        created_by=actor_id,
        updated_by=actor_id,
    )
