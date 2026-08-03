from __future__ import annotations

import pytest

from foundation_release_composition import FoundationReleaseDependencyAdapter
from learning.application import LearningGovernanceService
from learning.contracts import (
    LearningActor,
    LearningUnitRevisionDraft,
    QuestionCandidateContent,
    QuizRevisionDraft,
    SourceAnchorDraft,
    SourceDocumentRevisionDraft,
)


def _learning_actor() -> LearningActor:
    return LearningActor(
        organization_id="org-1",
        actor_id="release-admin",
        capabilities=frozenset(
            {
                "learning.source.manage",
                "learning.content.manage",
                "learning.question.manage",
                "learning.question.publish",
                "learning.quiz.manage",
            }
        ),
    )


@pytest.mark.asyncio
async def test_release_adapter_publishes_complete_working_learning_closure(
    test_db,
) -> None:
    actor = _learning_actor()
    service = LearningGovernanceService(test_db)
    document = await service.create_source_document(
        actor=actor,
        stable_key="working-source",
        title="工作材料",
        idempotency_key="create-working-source",
    )
    source = await service.save_source_revision(
        actor=actor,
        document_id=document.document_id,
        draft=SourceDocumentRevisionDraft(
            revision_label="首版",
            source_type="url",
            source_uri="https://example.com/foundation",
            file_hash="a" * 64,
            parser_version="manual-review-v1",
            parse_status="ready",
        ),
        expected_document_version=document.version,
        idempotency_key="save-working-source",
    )
    anchor = await service.create_source_anchor(
        actor=actor,
        source_revision_id=source.revision_id,
        draft=SourceAnchorDraft.model_validate(
            {
                "anchor_key": "value-page",
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
        idempotency_key="anchor-working-source",
    )
    unit = await service.create_learning_unit(
        actor=actor,
        stable_key="working-unit",
        title="客户价值学习",
        idempotency_key="create-working-unit",
    )
    unit_revision = await service.save_learning_unit_revision(
        actor=actor,
        unit_id=unit.unit_id,
        draft=LearningUnitRevisionDraft.model_validate(
            {
                "revision_label": "首版",
                "title": "客户价值学习",
                "objectives": ["能说明客户价值"],
                "key_concepts": [
                    {
                        "concept_id": "value",
                        "title": "客户价值",
                        "content": "先确认客户目标，再说明业务价值。",
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
        idempotency_key="save-working-unit",
    )
    question_revision = await service.save_manual_question_revision(
        actor=actor,
        stable_key="approved-question",
        content=QuestionCandidateContent.model_validate(
            {
                "question_type": "single_choice",
                "stem": "说明价值前应先做什么？",
                "options": [
                    {"option_id": "a", "text": "确认客户目标", "is_correct": True},
                    {"option_id": "b", "text": "直接报价", "is_correct": False},
                ],
                "reference_answer": None,
                "rubric": None,
                "explanation": "价值说明必须建立在客户目标上。",
                "difficulty": "easy",
                "competency_keys": ["customer_understanding"],
                "source_anchor_ids": [anchor.anchor_id],
            }
        ),
        expected_question_version=None,
        idempotency_key="save-approved-question",
        review_reason="答案、来源和能力映射已人工核对",
    )
    quiz = await service.create_quiz(
        actor=actor,
        stable_key="working-quiz",
        title="客户价值测验",
        idempotency_key="create-working-quiz",
    )
    quiz_revision = await service.save_quiz_revision(
        actor=actor,
        quiz_id=quiz.quiz_id,
        draft=QuizRevisionDraft.model_validate(
            {
                "revision_label": "首版",
                "title": "客户价值测验",
                "questions": [
                    {
                        "question_revision_id": question_revision.revision_id,
                        "points": 100,
                    }
                ],
                "pass_threshold": 80,
                "max_attempts": 2,
                "retry_interval_seconds": 60,
                "feedback_policy": "after_submit",
            }
        ),
        expected_quiz_version=quiz.version,
        idempotency_key="save-working-quiz",
    )

    adapter = FoundationReleaseDependencyAdapter(test_db)
    dependencies = [
        await adapter.inspect_resource(
            organization_id="org-1",
            resource_type=resource_type,
            revision_id=revision_id,
        )
        for resource_type, revision_id in (
            ("source_document", source.revision_id),
            ("question", question_revision.revision_id),
            ("learning_unit", unit_revision.revision_id),
            ("quiz", quiz_revision.revision_id),
        )
    ]
    assert all(item.publish_required and not item.issues for item in dependencies)

    for dependency in dependencies:
        published = await adapter.publish(
            organization_id="org-1",
            actor_id="release-admin",
            capability_set=frozenset({"newcomer.path.publish"}),
            dependency=dependency,
            idempotency_key=f"publish:{dependency.revision_id}",
            reason="新人训练首版发布",
            trace_id="trace-release-closure",
        )
        assert published.status == "published"
        assert published.publish_required is False

