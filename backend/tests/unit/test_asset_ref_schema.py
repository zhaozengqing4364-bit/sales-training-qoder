from __future__ import annotations

from curriculum_practice.schemas import (
    CurriculumVersionRef,
    LearningContentRef,
    PublishedTemplateRef,
)
from curriculum_practice.schemas import (
    TestBankRef as QuestionRef,
)


def test_should_serialize_learning_and_test_bank_refs_with_shared_asset_shape() -> None:
    learning_ref = LearningContentRef(
        asset_id="learning-1",
        version=2,
        hash="sha256:learning",
    )
    question_ref = QuestionRef(
        asset_id="question-1",
        version=3,
        hash="sha256:question",
    )

    assert learning_ref.model_dump() == {
        "asset_type": "learning_content",
        "asset_id": "learning-1",
        "version": 2,
        "hash": "sha256:learning",
        "snapshot_label": "published",
    }
    assert question_ref.model_dump() == {
        "asset_type": "question_item",
        "asset_id": "question-1",
        "version": 3,
        "hash": "sha256:question",
        "snapshot_label": "published",
    }


def test_should_preserve_existing_published_template_and_curriculum_ref_shapes() -> None:
    template_ref = PublishedTemplateRef(
        asset_id="template-1",
        version=1,
        hash="sha256:template",
    )
    curriculum_ref = CurriculumVersionRef(
        asset_type="practice_template",
        asset_id="template-2",
        version="2026.05",
        hash="sha256:curriculum",
        snapshot_label="superseded",
    )

    assert template_ref.model_dump() == {
        "asset_type": "practice_template",
        "asset_id": "template-1",
        "version": 1,
        "hash": "sha256:template",
        "snapshot_label": "published",
    }
    assert curriculum_ref.model_dump() == {
        "asset_type": "practice_template",
        "asset_id": "template-2",
        "version": "2026.05",
        "hash": "sha256:curriculum",
        "snapshot_label": "superseded",
    }
