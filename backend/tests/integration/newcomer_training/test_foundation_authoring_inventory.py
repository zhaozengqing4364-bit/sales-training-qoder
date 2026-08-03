from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.inventory_newcomer_foundation_authoring import collect_inventory
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from learning.models import (
    LearningSourceDocument,
    LearningSourceDocumentRevision,
)
from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)

FIXED_TIME = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_should_inventory_empty_database_without_writes(
    test_db: AsyncSession,
    test_engine: AsyncEngine,
) -> None:
    statements: list[str] = []

    def record_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement.strip())

    event.listen(test_engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        report = await collect_inventory(
            test_db,
            organization_ids=("org-empty",),
            generated_at=FIXED_TIME,
        )
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", record_statement)

    assert report["writes_performed"] == 0
    assert report["legacy"]["counts"] == {  # type: ignore[index]
        "active_paths": 0,
        "activities": 0,
        "materials": 0,
        "material_versions": 0,
        "scoring_prompts": 0,
    }
    organization = report["organizations"][0]  # type: ignore[index]
    assert organization["organization_id"] == "org-empty"
    assert organization["foundation"]["counts"]["source_documents"] == 0
    assert statements
    assert all(statement.upper().startswith("SELECT") for statement in statements)


@pytest.mark.asyncio
async def test_should_isolate_foundation_organizations(
    test_db: AsyncSession,
) -> None:
    for suffix in ("a", "b"):
        document_id = f"document-{suffix}"
        revision_id = f"source-revision-{suffix}"
        test_db.add(
            LearningSourceDocument(
                document_id=document_id,
                organization_id=f"org-{suffix}",
                stable_key=f"source-{suffix}",
                title=f"Source {suffix}",
                status="active",
                working_revision_id=None,
                published_revision_id=revision_id,
                version=1,
                creation_idempotency_key_hash=f"create-{suffix}",
                creation_fingerprint=f"fingerprint-{suffix}",
                created_by="system:foundation-pack",
            )
        )
        test_db.add(
            LearningSourceDocumentRevision(
                revision_id=revision_id,
                document_id=document_id,
                organization_id=f"org-{suffix}",
                revision_no=1,
                revision_label="v1",
                status="published",
                source_type="manual",
                source_uri=f"controlled://source-{suffix}",
                file_hash=f"hash-{suffix}",
                parser_version="manual-v1",
                parse_status="ready",
                content_hash=f"content-{suffix}",
                version=1,
                save_idempotency_key_hash=f"save-{suffix}",
                save_fingerprint=f"save-fingerprint-{suffix}",
                created_by="system:foundation-pack",
            )
        )
    await test_db.commit()

    report = await collect_inventory(
        test_db,
        organization_ids=("org-a",),
        generated_at=FIXED_TIME,
    )

    assert [item["organization_id"] for item in report["organizations"]] == [  # type: ignore[index]
        "org-a"
    ]
    assert "controlled://" not in str(report)
    assert "org-b" not in str(report)


@pytest.mark.asyncio
async def test_should_locate_current_ppt_demo_fixture_and_preserve_rows(
    test_db: AsyncSession,
) -> None:
    payload = {
        "schema_version": "newcomer_training_orchestration_v1",
        "title": "新人训练路径",
        "phases": [
            {
                "phase_id": "materials",
                "title": "材料讲解",
                "order_index": 1,
                "modules": [
                    {
                        "module_id": "audio",
                        "title": "录音讲解模块",
                        "order_index": 1,
                        "completion_policy": {"mode": "all_required"},
                        "activities": [
                            {
                                "activity_id": "ppt-intro",
                                "title": "石犀ppt讲解",
                                "type": "audio_assessment",
                                "order_index": 1,
                                "config": {
                                    "material_id": "material-ppt",
                                    "scoring_rubric_id": "prompt-ppt",
                                    "pass_score": 80,
                                },
                            },
                            {
                                "activity_id": "demo-intro",
                                "title": "demo讲解",
                                "type": "audio_assessment",
                                "order_index": 2,
                                "config": {
                                    "material_id": None,
                                    "scoring_rubric_id": None,
                                    "pass_score": 80,
                                },
                            },
                        ],
                    }
                ],
            }
        ],
    }
    test_db.add(
        SalesTrainerAssetRevision(
            revision_id="legacy-path-revision",
            resource_type="newcomer_training_path_orchestration",
            logical_id="default",
            revision_no=7,
            status="published",
            payload_json=payload,
            payload_hash="legacy-path-hash",
            change_class="semantic",
        )
    )
    test_db.add(
        SalesTrainerAssetActiveRevision(
            active_ref_id="legacy-path-active",
            resource_type="newcomer_training_path_orchestration",
            logical_id="default",
            active_revision_id="legacy-path-revision",
        )
    )
    test_db.add(
        SalesTrainerMaterial(
            material_id="material-ppt",
            material_key="company-intro-ppt",
            name="石犀科技-企业介绍标准版（202606版）.pptx",
            material_type="attachment",
            purpose="training_activity",
            status="published",
            current_version_id="material-ppt-v1",
        )
    )
    test_db.add(
        SalesTrainerMaterialVersion(
            version_id="material-ppt-v1",
            material_id="material-ppt",
            version_label="v1",
            title="石犀科技企业介绍",
            file_name="石犀科技-企业介绍标准版（202606版）.pptx",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "presentationml.presentation"
            ),
            file_size_bytes=1024,
            storage_key="protected/legacy/company-intro.pptx",
            file_hash="ppt-file-hash",
            status="published",
        )
    )
    test_db.add(
        SalesTrainerAudioScorePrompt(
            prompt_id="prompt-ppt",
            name="PPT 讲解评分",
            purpose="ppt_explanation",
            system_prompt="protected prompt body",
            scoring_template="protected scoring body",
            output_schema={"score": "number"},
            learner_rubric={"clarity": "清晰度"},
            version=1,
            status="published",
        )
    )
    test_db.add(
        LearningSourceDocument(
            document_id="foundation-source-ppt",
            organization_id="org-current",
            stable_key="company-intro-ppt",
            title="石犀科技企业介绍",
            status="active",
            published_revision_id="foundation-source-ppt-v1",
            version=1,
            creation_idempotency_key_hash="create-source",
            creation_fingerprint="source-fingerprint",
            created_by="system:foundation-pack",
        )
    )
    test_db.add(
        LearningSourceDocumentRevision(
            revision_id="foundation-source-ppt-v1",
            document_id="foundation-source-ppt",
            organization_id="org-current",
            revision_no=1,
            revision_label="v1",
            status="published",
            source_type="file",
            source_uri="artifact://protected-source",
            file_hash="ppt-file-hash",
            parser_version="ppt-v1",
            parse_status="ready",
            content_hash="ppt-content-hash",
            version=1,
            save_idempotency_key_hash="save-source",
            save_fingerprint="save-source-fingerprint",
            created_by="system:foundation-pack",
        )
    )
    await test_db.commit()
    before = int(
        await test_db.scalar(select(func.count(SalesTrainerMaterial.material_id))) or 0
    )

    report = await collect_inventory(
        test_db,
        organization_ids=("org-current",),
        generated_at=FIXED_TIME,
    )

    after = int(
        await test_db.scalar(select(func.count(SalesTrainerMaterial.material_id))) or 0
    )
    assert before == after == 1
    assert "protected prompt body" not in str(report)
    assert "protected/legacy" not in str(report)
    assert "artifact://protected" not in str(report)
    assert report["legacy"]["unverifiable_items"] == [  # type: ignore[index]
        {
            "object_type": "sales_trainer_audio_score_prompt",
            "object_id": "prompt-ppt",
            "reason": "requires_governed_prompt_model_schema_review",
            "referenced_by_activity_ids": ["ppt-intro"],
        }
    ]
    organization = report["organizations"][0]  # type: ignore[index]
    focus = organization["mapping_candidates"]["focus_activities"]
    assert [item["legacy_title"] for item in focus] == ["demo讲解", "石犀ppt讲解"]
    material = organization["mapping_candidates"]["materials"][0]
    assert material["is_focus_material"] is True
    assert material["content_kind"] == "slide_deck"
    assert material["disposition"] == "reuse_exact_hash"
