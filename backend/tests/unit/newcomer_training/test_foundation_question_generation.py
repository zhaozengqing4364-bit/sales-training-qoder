from __future__ import annotations

import pytest

from ai_platform import BudgetScope, DataClassification
from ai_platform.models import AIModelRoutingProfileRecord, AIPromptRevisionRecord
from ai_platform.prompting import compute_prompt_revision_content_hash
from ai_platform.routing import (
    PublishedModelRoutingProfileSnapshot,
    compute_model_routing_profile_content_hash,
)
from foundation_question_generation import (
    FoundationQuestionGenerationPolicyService,
    FoundationQuestionGenerationSelection,
)
from learning.application import LearningGovernanceService
from learning.contracts import (
    LearningActor,
    LearningUnitRevisionDraft,
    SourceAnchorDraft,
    SourceDocumentRevisionDraft,
)


@pytest.mark.asyncio
async def test_admin_question_generation_builds_hidden_exact_prompt_contract(
    test_db,
) -> None:
    actor = LearningActor(
        organization_id="org-1",
        actor_id="question-editor",
        capabilities=frozenset(
            {
                "learning.source.manage",
                "learning.content.manage",
                "learning.question.generate",
            }
        ),
    )
    learning = LearningGovernanceService(test_db)
    document = await learning.create_source_document(
        actor=actor,
        stable_key="published-source",
        title="销售基础材料",
        idempotency_key="create-source",
    )
    source = await learning.save_source_revision(
        actor=actor,
        document_id=document.document_id,
        draft=SourceDocumentRevisionDraft(
            revision_label="首版",
            source_type="url",
            source_uri="https://example.com/sales",
            file_hash="a" * 64,
            parser_version="manual-review-v1",
            parse_status="ready",
        ),
        expected_document_version=document.version,
        idempotency_key="save-source",
    )
    source = await learning.publish_source_revision(
        actor=actor,
        revision_id=source.revision_id,
        expected_revision_version=source.version,
        idempotency_key="publish-source",
    )
    anchor = await learning.create_source_anchor(
        actor=actor,
        source_revision_id=source.revision_id,
        draft=SourceAnchorDraft.model_validate(
            {
                "anchor_key": "value",
                "label": "客户价值",
                "locator": {
                    "type": "page",
                    "page": 1,
                    "start_offset": 0,
                    "end_offset": 20,
                },
                "excerpt_hash": "b" * 64,
            }
        ),
        idempotency_key="create-anchor",
    )
    unit = await learning.create_learning_unit(
        actor=actor,
        stable_key="published-unit",
        title="客户价值",
        idempotency_key="create-unit",
    )
    unit_revision = await learning.save_learning_unit_revision(
        actor=actor,
        unit_id=unit.unit_id,
        draft=LearningUnitRevisionDraft.model_validate(
            {
                "revision_label": "首版",
                "title": "客户价值",
                "objectives": ["能说明客户价值"],
                "key_concepts": [
                    {
                        "concept_id": "value",
                        "title": "客户价值",
                        "content": "先确认目标，再说明价值。",
                        "source_anchor_ids": [anchor.anchor_id],
                    }
                ],
                "examples": [],
                "checkpoints": [
                    {
                        "checkpoint_id": "value-check",
                        "prompt": "说明客户价值",
                        "required": True,
                    }
                ],
                "practice_hints": [],
            }
        ),
        expected_unit_version=unit.version,
        idempotency_key="save-unit",
    )
    unit_revision = await learning.publish_learning_unit_revision(
        actor=actor,
        revision_id=unit_revision.revision_id,
        expected_revision_version=unit_revision.version,
        idempotency_key="publish-unit",
    )

    template = (
        "材料 {{ source_revision_id }}\n"
        "学习修订 {{ learning_unit_revision_id }}\n"
        "数量 {{ requested_count }}\n"
        "内容 {{ learning_unit_json }}\n"
        "来源 {{ source_anchors_json }}"
    )
    variables = (
        "learning_unit_json",
        "learning_unit_revision_id",
        "requested_count",
        "source_anchors_json",
        "source_revision_id",
    )
    prompt = AIPromptRevisionRecord(
        template_id="question-generation",
        revision_id="question-generation-v1",
        revision_no=1,
        status="published",
        business_purpose="newcomer_question_generation",
        template_text=template,
        variables_json=list(variables),
        input_schema_version="question-generation-input-v1",
        output_schema_version="question-generation-output-v1",
        content_hash=compute_prompt_revision_content_hash(
            template_id="question-generation",
            business_purpose="newcomer_question_generation",
            revision_id="question-generation-v1",
            revision_no=1,
            template=template,
            variables=variables,
            input_schema_version="question-generation-input-v1",
            output_schema_version="question-generation-output-v1",
        ),
    )
    route_snapshot = PublishedModelRoutingProfileSnapshot(
        profile_id="question-generation-models",
        business_purpose="newcomer_question_generation",
        revision_id="question-route-v1",
        revision_no=1,
        status="published",
        provider="deterministic",
        model="question-model-v1",
        temperature=0,
        max_output_tokens=1_024,
        timeout_seconds=30,
        timeout_policy_ref="question-generation-default",
        max_provider_retries=1,
        max_schema_retries=1,
        retry_policy_ref="question-generation-default",
        requests_per_minute=30,
        rate_limit_scopes=(BudgetScope.ORGANIZATION,),
        budget_scope=BudgetScope.ORGANIZATION,
        budget_limit_minor_units=1_000,
        budget_reservation_minor_units=10,
        budget_window_seconds=3_600,
        currency="CNY",
        circuit_failure_threshold=3,
        circuit_recovery_seconds=30,
        allowed_data_classifications=(DataClassification.INTERNAL,),
    )
    route = AIModelRoutingProfileRecord(
        profile_id=route_snapshot.profile_id,
        revision_id=route_snapshot.revision_id,
        revision_no=route_snapshot.revision_no,
        status="published",
        snapshot_json=route_snapshot.model_dump(mode="json"),
        content_hash=compute_model_routing_profile_content_hash(route_snapshot),
    )
    test_db.add_all([prompt, route])
    await test_db.flush()

    policy = FoundationQuestionGenerationPolicyService(test_db)
    options = await policy.list_options(actor=actor)
    request = await policy.build_request(
        actor=actor,
        selection=FoundationQuestionGenerationSelection(
            source_revision_id=source.revision_id,
            learning_unit_revision_id=unit_revision.revision_id,
            requested_count=5,
            prompt_template_id=prompt.template_id,
            prompt_revision_id=prompt.revision_id,
            model_routing_profile_id=route.profile_id,
            model_routing_revision_id=route.revision_id,
        ),
    )

    assert options["ready"] is True
    assert options["prompt_options"] == [
        {
            "template_id": "question-generation",
            "revision_id": "question-generation-v1",
            "revision_no": 1,
            "label": "题目生成模板 · 第 1 版",
        }
    ]
    assert request.prompt_contract_hash.startswith("sha256:")
    assert request.model_routing_revision_id == "question-route-v1"
    assert template not in str(options)

