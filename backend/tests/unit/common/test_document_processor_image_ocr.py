from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import common.knowledge.processor as processor_module
from common.knowledge.models import DocumentStatus
from common.knowledge.processor import DocumentProcessor


def test_extract_text_from_docx_images_deduplicates_same_blob(monkeypatch):
    processor = DocumentProcessor()

    image_blob = b"same-image-bytes"
    rels = {
        "r1": SimpleNamespace(
            target_part=SimpleNamespace(content_type="image/png", blob=image_blob)
        ),
        "r2": SimpleNamespace(
            target_part=SimpleNamespace(content_type="image/png", blob=image_blob)
        ),
        "r3": SimpleNamespace(
            target_part=SimpleNamespace(content_type="application/xml", blob=b"ignored")
        ),
    }
    fake_doc = SimpleNamespace(part=SimpleNamespace(rels=rels))

    calls: list[str] = []

    def fake_ocr(image_bytes: bytes, source: str) -> str | None:
        calls.append(source)
        if image_bytes == image_blob:
            return "图片中的文字"
        return None

    monkeypatch.setattr(processor, "_ocr_image_bytes", fake_ocr)

    results = processor._extract_text_from_docx_images(fake_doc)

    assert results == ["图片中的文字"]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_read_pdf_combines_extracted_text_and_image_ocr(monkeypatch, tmp_path):
    file_path = tmp_path / "image_pdf.pdf"
    file_path.write_bytes(b"%PDF-1.4 fake")

    fake_page = SimpleNamespace(
        extract_text=lambda: "第一页文本",
        images=[SimpleNamespace(data=b"page-image")],
    )
    fake_reader = SimpleNamespace(pages=[fake_page])

    monkeypatch.setitem(
        sys.modules,
        "pypdf",
        SimpleNamespace(PdfReader=lambda _: fake_reader),
    )

    processor = DocumentProcessor()
    monkeypatch.setattr(
        processor,
        "_extract_text_from_pdf_images",
        lambda page, page_index: ["图片OCR内容"],
    )

    content = await processor._read_pdf(str(file_path))

    assert content is not None
    assert "第一页文本" in content
    assert "图片OCR内容" in content


@pytest.mark.asyncio
async def test_read_docx_combines_paragraph_text_and_image_ocr(monkeypatch, tmp_path):
    file_path = tmp_path / "image_doc.docx"
    file_path.write_bytes(b"PK\x03\x04 fake")

    fake_doc = SimpleNamespace(
        paragraphs=[SimpleNamespace(text="文档段落A"), SimpleNamespace(text="  ")],
    )

    monkeypatch.setitem(
        sys.modules,
        "docx",
        SimpleNamespace(Document=lambda _: fake_doc),
    )

    processor = DocumentProcessor()
    monkeypatch.setattr(
        processor,
        "_extract_text_from_docx_images",
        lambda doc: ["文档图片OCR内容"],
    )

    content = await processor._read_docx(str(file_path))

    assert content is not None
    assert "文档段落A" in content
    assert "文档图片OCR内容" in content


@pytest.mark.asyncio
async def test_process_document_fails_when_embedding_service_not_configured(
    monkeypatch,
):
    processor = DocumentProcessor()
    monkeypatch.setattr(
        processor,
        "_read_document",
        AsyncMock(return_value="企业产品资料：A系列、B系列。"),
    )
    monkeypatch.setattr(
        processor,
        "_split_into_chunks",
        lambda _content: [
            {
                "index": 0,
                "content": "企业产品资料：A系列、B系列。",
                "metadata": {"start_char": 0, "end_char": 15},
            }
        ],
    )

    embedding_service = SimpleNamespace(is_configured=False)
    monkeypatch.setattr(
        processor_module,
        "get_embedding_service",
        lambda: embedding_service,
    )

    result = await processor.process_document(
        doc_id="doc-1",
        file_path="/tmp/dummy.txt",
        file_type="txt",
        document_title="产品文档",
        knowledge_base_id="kb-1",
        vector_collection="kb_collection_1",
    )

    assert result["status"] == DocumentStatus.FAILED.value
    assert result["chunk_count"] == 0
    assert "[EMBEDDING_NOT_CONFIGURED]" in str(result["error_message"])
