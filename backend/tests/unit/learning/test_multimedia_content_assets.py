from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from common.storage import DocumentStorageService
from learning.application import LearningGovernanceService
from learning.content_access import (
    LearnerSourceAssetGrant,
    issue_learner_source_asset_grant,
    verify_learner_source_asset_grant,
)
from learning.contracts import (
    LearningActor,
    LearningUnitRevisionDraft,
    SourceAnchorDraft,
    SourceDocumentRevisionDraft,
)
from learning.errors import LearningGovernanceError
from learning.lesson_runtime import LessonAttemptContext, LessonRuntimeService
from learning.models import (
    LearningSourceDocument,
    LearningSourceDocumentRevision,
    LearningUnitRevision,
)
from learning.multimedia import (
    PREVIEW_VERSION,
    SourceProcessingResult,
    SourceUploadError,
    SourceUploadPolicy,
    process_source_file,
    stage_source_upload,
    validate_source_file,
)
from learning.source_ingestion import (
    SourceDocumentIngestionProcessor,
    SourceIngestionError,
    source_document_artifact_uri,
    source_document_file_path,
)
from learning.workspace import LearningWorkspaceQueryService


def _upload_policy(**changes: object) -> SourceUploadPolicy:
    return replace(
        SourceUploadPolicy(
            document_max_bytes=5 * 1024 * 1024,
            media_max_bytes=5 * 1024 * 1024,
            attachment_max_bytes=5 * 1024 * 1024,
            zip_max_entries=100,
            zip_max_uncompressed_bytes=5 * 1024 * 1024,
            zip_max_ratio=100,
            video_codecs=frozenset({"h264"}),
            audio_codecs=frozenset({"aac"}),
        ),
        **changes,
    )


def _write_pptx_package(
    path,
    *,
    main_content_type: str = (
        "application/vnd.openxmlformats-officedocument.presentationml."
        "presentation.main+xml"
    ),
    extra: bytes | None = None,
) -> None:
    content_types = f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/ppt/presentation.xml" ContentType="{main_content_type}"/>
</Types>"""
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("ppt/presentation.xml", "<p:presentation xmlns:p='urn:test'/>")
        if extra is not None:
            package.writestr("ppt/media/repeated.bin", extra)


def _learning_actor() -> LearningActor:
    return LearningActor(
        organization_id="org-1",
        actor_id="content-admin",
        capabilities=frozenset(
            {"learning.source.manage", "learning.content.manage"}
        ),
    )


async def _published_document_source(
    test_db,
    *,
    suffix: str,
):
    service = LearningGovernanceService(test_db)
    actor = _learning_actor()
    document = await service.create_source_document(
        actor=actor,
        stable_key=f"source-{suffix}",
        title=f"材料 {suffix}",
        idempotency_key=f"create-source-{suffix}",
    )
    revision = await service.save_source_revision(
        actor=actor,
        document_id=document.document_id,
        draft=SourceDocumentRevisionDraft(
            revision_label="首版",
            source_type="file",
            content_kind="document",
            source_uri=f"artifact://learning/source/{suffix}.txt",
            file_hash=(suffix[0].lower() if suffix[0].lower() in "abcdef" else "a")
            * 64,
            parser_version="parser-v1",
            parse_status="ready",
            processing_state="ready",
        ),
        expected_document_version=document.version,
        idempotency_key=f"save-source-{suffix}",
    )
    revision = await service.publish_source_revision(
        actor=actor,
        revision_id=revision.revision_id,
        expected_revision_version=revision.version,
        idempotency_key=f"publish-source-{suffix}",
    )
    anchor = await service.create_source_anchor(
        actor=actor,
        source_revision_id=revision.revision_id,
        draft=SourceAnchorDraft(
            anchor_key=f"anchor-{suffix}",
            label=f"来源 {suffix}",
            locator={
                "type": "paragraph",
                "paragraph_id": f"paragraph-{suffix}",
                "start_offset": 0,
                "end_offset": 10,
            },
            excerpt_hash="b" * 64,
        ),
        idempotency_key=f"create-anchor-{suffix}",
    )
    return service, actor, revision, anchor


def test_legacy_source_contract_backfills_safe_multimedia_state() -> None:
    failed = SourceDocumentRevisionDraft.model_validate(
        {
            "revision_label": "历史失败修订",
            "source_type": "file",
            "source_uri": "artifact://learning/source/document/hash.txt",
            "file_hash": "a" * 64,
            "parser_version": "legacy-parser",
            "parse_status": "failed",
        }
    )
    external = SourceDocumentRevisionDraft.model_validate(
        {
            "revision_label": "历史外链修订",
            "source_type": "url",
            "source_uri": "https://example.com/demo",
            "file_hash": "b" * 64,
            "parser_version": "manual-review-v1",
            "parse_status": "ready",
        }
    )

    assert failed.processing_state == "failed"
    assert failed.failure_code == "legacy_parse_failed"
    assert failed.failure_message == "历史材料解析未完成，可重新提交处理。"
    assert external.content_kind == "external_demo"
    assert external.processing_state == "ready"


def test_checkpoint_contract_merges_legacy_and_block_contracts() -> None:
    draft = LearningUnitRevisionDraft.model_validate(
        {
            "revision_label": "混合检查点",
            "title": "新人学习单元",
            "objectives": ["完成两项检查"],
            "checkpoints": [
                {
                    "checkpoint_id": "legacy-checkpoint",
                    "prompt": "复述核心价值",
                    "required": True,
                }
            ],
            "content_blocks": [
                {
                    "type": "checkpoint",
                    "block_id": "block-checkpoint",
                    "title": "现场检查",
                    "order": 1,
                    "accessibility_alt": "现场检查点",
                    "prompt": "完成一次场景说明",
                    "required": False,
                }
            ],
        }
    )

    assert [item.checkpoint_id for item in draft.checkpoint_contracts()] == [
        "legacy-checkpoint",
        "block-checkpoint",
    ]


def test_checkpoint_contract_rejects_cross_contract_duplicate_id() -> None:
    with pytest.raises(ValidationError, match="cannot overlap"):
        LearningUnitRevisionDraft.model_validate(
            {
                "revision_label": "冲突检查点",
                "title": "新人学习单元",
                "objectives": ["完成检查"],
                "checkpoints": [
                    {
                        "checkpoint_id": "same-checkpoint",
                        "prompt": "复述核心价值",
                    }
                ],
                "content_blocks": [
                    {
                        "type": "checkpoint",
                        "block_id": "same-checkpoint",
                        "title": "重复检查",
                        "order": 1,
                        "accessibility_alt": "重复检查点",
                        "prompt": "再次复述核心价值",
                    }
                ],
            }
        )


def test_pptx_validation_requires_authentic_main_content_type(tmp_path) -> None:
    valid = tmp_path / "valid.pptx"
    forged = tmp_path / "forged.pptx"
    _write_pptx_package(valid)
    _write_pptx_package(forged, main_content_type="application/octet-stream")

    validate_source_file(valid, file_type="pptx", policy=_upload_policy())
    with pytest.raises(SourceUploadError) as caught:
        validate_source_file(forged, file_type="pptx", policy=_upload_policy())

    assert caught.value.code == "source_ooxml_content_type_mismatch"


def test_pptx_validation_rejects_zip_bomb_ratio(tmp_path) -> None:
    path = tmp_path / "bomb.pptx"
    _write_pptx_package(path, extra=b"A" * (512 * 1024))

    with pytest.raises(SourceUploadError) as caught:
        validate_source_file(
            path,
            file_type="pptx",
            policy=_upload_policy(zip_max_ratio=2),
        )

    assert caught.value.code == "source_zip_bomb_detected"


@pytest.mark.asyncio
async def test_legacy_ppt_upload_has_actionable_rejection(tmp_path) -> None:
    upload = UploadFile(filename="legacy.ppt", file=BytesIO(b"legacy-ppt"))

    with pytest.raises(SourceUploadError) as caught:
        await stage_source_upload(
            upload,
            content_kind="slide_deck",
            storage=DocumentStorageService(str(tmp_path)),
            policy=_upload_policy(),
        )

    assert caught.value.code == "source_ppt_conversion_required"
    assert ".pptx" in caught.value.message


@pytest.mark.asyncio
async def test_attachment_processing_creates_bindable_full_file_anchor(tmp_path) -> None:
    storage = DocumentStorageService(str(tmp_path))
    path = tmp_path / "attachment.txt"
    path.write_text("附件内容", encoding="utf-8")

    result = await process_source_file(
        file_path=path,
        file_type="txt",
        content_kind="attachment",
        storage=storage,
    )

    assert result.processing_state == "ready"
    assert result.manifest["kind"] == "attachment"
    assert result.anchors[0]["anchor_key"] == "full-attachment"
    assert result.anchors[0]["locator"]["type"] == "paragraph"


def test_learner_asset_grant_is_opaque_and_tamper_evident() -> None:
    grant = LearnerSourceAssetGrant(
        organization_id="org-1",
        activity_id="lesson-1",
        block_id="slide-block",
        source_revision_id="source-revision-1",
    )
    token = issue_learner_source_asset_grant(grant)
    tampered = ("A" if token[0] != "A" else "B") + token[1:]

    assert verify_learner_source_asset_grant(token) == grant
    assert verify_learner_source_asset_grant(tampered) is None


@pytest.mark.asyncio
async def test_learning_block_rejects_anchor_from_another_exact_revision(
    test_db,
) -> None:
    service, actor, first_revision, _ = await _published_document_source(
        test_db,
        suffix="a-first",
    )
    _, _, _, second_anchor = await _published_document_source(
        test_db,
        suffix="b-second",
    )
    unit = await service.create_learning_unit(
        actor=actor,
        stable_key="exact-source-unit",
        title="精确来源单元",
        idempotency_key="create-exact-source-unit",
    )
    draft = LearningUnitRevisionDraft.model_validate(
        {
            "revision_label": "首版",
            "title": "精确来源单元",
            "objectives": ["保持来源版本与位置一致"],
            "content_blocks": [
                {
                    "type": "rich_text",
                    "block_id": "explanation",
                    "title": "核心说明",
                    "order": 1,
                    "accessibility_alt": "核心说明正文",
                    "source_revision_id": first_revision.revision_id,
                    "source_anchor_id": second_anchor.anchor_id,
                    "markdown": "这段精编内容必须绑定同一材料修订的位置。",
                },
                {
                    "type": "checkpoint",
                    "block_id": "confirm-source",
                    "title": "学习检查",
                    "order": 2,
                    "accessibility_alt": "学习检查点",
                    "prompt": "确认来源一致",
                },
            ],
        }
    )

    with pytest.raises(LearningGovernanceError) as caught:
        await service.save_learning_unit_revision(
            actor=actor,
            unit_id=unit.unit_id,
            draft=draft,
            expected_unit_version=unit.version,
            idempotency_key="save-mismatched-exact-source",
        )

    assert caught.value.code == "[LEARNING_EXACT_SOURCE_REFERENCE_INVALID]"


@pytest.mark.asyncio
async def test_new_learning_block_rejects_archived_source_revision(test_db) -> None:
    service, actor, source_revision, anchor = await _published_document_source(
        test_db,
        suffix="c-archived",
    )
    persisted = await test_db.get(
        LearningSourceDocumentRevision,
        source_revision.revision_id,
    )
    assert persisted is not None
    persisted.status = "archived"
    await test_db.flush()
    unit = await service.create_learning_unit(
        actor=actor,
        stable_key="archived-source-unit",
        title="归档来源单元",
        idempotency_key="create-archived-source-unit",
    )
    draft = LearningUnitRevisionDraft.model_validate(
        {
            "revision_label": "首版",
            "title": "归档来源单元",
            "objectives": ["不得建立新的归档引用"],
            "content_blocks": [
                {
                    "type": "rich_text",
                    "block_id": "archived-explanation",
                    "title": "历史说明",
                    "order": 1,
                    "accessibility_alt": "历史说明正文",
                    "source_revision_id": source_revision.revision_id,
                    "source_anchor_id": anchor.anchor_id,
                    "markdown": "归档材料只能继续服务既有冻结尝试。",
                },
                {
                    "type": "checkpoint",
                    "block_id": "archived-checkpoint",
                    "title": "学习检查",
                    "order": 2,
                    "accessibility_alt": "学习检查点",
                    "prompt": "确认归档限制",
                },
            ],
        }
    )

    with pytest.raises(LearningGovernanceError) as caught:
        await service.save_learning_unit_revision(
            actor=actor,
            unit_id=unit.unit_id,
            draft=draft,
            expected_unit_version=unit.version,
            idempotency_key="save-archived-source",
        )

    assert caught.value.code == "[LEARNING_SOURCE_REVISION_UNAVAILABLE]"


@pytest.mark.asyncio
async def test_frozen_lesson_attempt_can_read_archived_exact_revisions(test_db) -> None:
    service, actor, source_revision, anchor = await _published_document_source(
        test_db,
        suffix="d-frozen",
    )
    unit = await service.create_learning_unit(
        actor=actor,
        stable_key="frozen-lesson-unit",
        title="冻结学习单元",
        idempotency_key="create-frozen-lesson-unit",
    )
    unit_revision = await service.save_learning_unit_revision(
        actor=actor,
        unit_id=unit.unit_id,
        draft=LearningUnitRevisionDraft.model_validate(
            {
                "revision_label": "首版",
                "title": "冻结学习单元",
                "objectives": ["继续读取已冻结的历史训练内容"],
                "content_blocks": [
                    {
                        "type": "rich_text",
                        "block_id": "frozen-explanation",
                        "title": "冻结说明",
                        "order": 1,
                        "accessibility_alt": "冻结说明正文",
                        "source_revision_id": source_revision.revision_id,
                        "source_anchor_id": anchor.anchor_id,
                        "markdown": "活跃训练尝试继续读取原先冻结的材料。",
                    },
                    {
                        "type": "checkpoint",
                        "block_id": "frozen-checkpoint",
                        "title": "学习检查",
                        "order": 2,
                        "accessibility_alt": "冻结内容检查点",
                        "prompt": "确认已阅读冻结内容",
                    },
                ],
            }
        ),
        expected_unit_version=unit.version,
        idempotency_key="save-frozen-lesson-unit",
    )
    unit_revision = await service.publish_learning_unit_revision(
        actor=actor,
        revision_id=unit_revision.revision_id,
        expected_revision_version=unit_revision.version,
        idempotency_key="publish-frozen-lesson-unit",
    )
    lesson = await LessonRuntimeService(test_db).start_or_resume(
        context=LessonAttemptContext(
            organization_id="org-1",
            learner_id="learner-1",
            enrollment_id="enrollment-1",
            path_revision_id="path-revision-1",
            activity_id="lesson-frozen",
            attempt_id="attempt-frozen",
            learning_unit_revision_id=unit_revision.revision_id,
            required_checkpoint_ids=("frozen-checkpoint",),
        ),
        idempotency_key="start-frozen-lesson",
    )
    persisted_source = await test_db.get(
        LearningSourceDocumentRevision,
        source_revision.revision_id,
    )
    persisted_unit = await test_db.get(
        LearningUnitRevision,
        unit_revision.revision_id,
    )
    assert persisted_source is not None and persisted_unit is not None
    persisted_source.status = "archived"
    persisted_unit.status = "archived"
    await test_db.flush()

    workspace = await LearningWorkspaceQueryService(test_db).get(
        organization_id="org-1",
        learner_id="learner-1",
        activity_type="lesson",
        revision_id=unit_revision.revision_id,
        attempt_id="attempt-frozen",
        activity_id="lesson-frozen",
    )

    assert workspace.detail_id == lesson.detail_id
    assert workspace.status == "in_progress"
    assert workspace.runner["content_blocks"][0]["availability"] == "ready"
    assert "source_revision_id" not in workspace.runner["content_blocks"][0]


@pytest.mark.asyncio
async def test_processing_result_is_fenced_by_source_fingerprint(
    test_db,
    tmp_path,
) -> None:
    storage = DocumentStorageService(str(tmp_path))
    file_hash = "c" * 64
    document_id = "source-document-fenced"
    revision_id = "source-revision-fenced"
    path = source_document_file_path(
        storage=storage,
        organization_id="org-1",
        document_id=document_id,
        file_hash=file_hash,
        file_type="txt",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("第一代处理输入", encoding="utf-8")
    now = datetime.now(UTC)
    test_db.add_all(
        [
            LearningSourceDocument(
                document_id=document_id,
                organization_id="org-1",
                stable_key="source-fenced",
                title="处理代际隔离材料",
                status="draft",
                working_revision_id=revision_id,
                version=1,
                creation_idempotency_key_hash="d" * 64,
                creation_fingerprint="e" * 64,
                created_by="admin-1",
                created_at=now,
                updated_at=now,
            ),
            LearningSourceDocumentRevision(
                revision_id=revision_id,
                document_id=document_id,
                organization_id="org-1",
                revision_no=1,
                revision_label="工作修订",
                status="working",
                source_type="file",
                content_kind="document",
                source_uri=source_document_artifact_uri(
                    document_id=document_id,
                    file_hash=file_hash,
                    file_type="txt",
                ),
                file_hash=file_hash,
                parser_version="pending-parser",
                parse_status="pending",
                original_filename="source.txt",
                trusted_mime_type="text/plain; charset=utf-8",
                file_extension="txt",
                file_size_bytes=path.stat().st_size,
                processing_state="pending",
                processing_stage="registered",
                content_hash="f" * 64,
                version=1,
                save_idempotency_key_hash="1" * 64,
                save_fingerprint="2" * 64,
                created_by="admin-1",
                created_at=now,
            ),
        ]
    )
    await test_db.commit()
    processor = SourceDocumentIngestionProcessor(test_db, storage=storage)
    plan = await processor.prepare(
        organization_id="org-1",
        revision_id=revision_id,
        file_hash=file_hash,
        file_type="txt",
    )
    plan = await processor.mark_processing(plan=plan)
    await test_db.commit()

    revision = await test_db.get(LearningSourceDocumentRevision, revision_id)
    assert revision is not None
    revision.original_filename = "source-changed-with-same-hash.txt"
    await test_db.flush()

    with pytest.raises(SourceIngestionError) as caught:
        await processor.apply(
            plan=plan,
            parser_result=SourceProcessingResult(
                processing_state="ready",
                chunk_count=1,
                artifact_available=True,
                manifest={
                    "version": PREVIEW_VERSION,
                    "kind": "document",
                    "sections": [],
                },
                anchors=(),
            ),
        )

    assert caught.value.code == "source_document_revision_changed"
