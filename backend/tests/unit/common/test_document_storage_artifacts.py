from __future__ import annotations

import pytest

from common.storage.document import DocumentStorageService


def test_parse_artifact_round_trip(tmp_path):
    storage = DocumentStorageService(base_path=str(tmp_path))
    file_path = tmp_path / "kb-1" / "doc-1.docx"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"PK\x03\x04")

    artifact = {
        "artifact_version": "2026-03-14",
        "chunks": [
            {
                "index": 0,
                "content": "石犀签约案例",
                "metadata": {"source_mode": "table", "element_types": ["table_row"]},
            }
        ],
        "phase_timings": {"parse_ms": 12.5},
    }

    saved_path = storage.save_parse_artifact(file_path, artifact)

    assert saved_path == str(file_path.with_name("doc-1.docx.parsed.json"))
    assert storage.load_parse_artifact(file_path) == artifact


@pytest.mark.asyncio
async def test_delete_document_removes_companion_parse_artifact(tmp_path):
    storage = DocumentStorageService(base_path=str(tmp_path))
    kb_id = "kb-2"
    doc_id = "doc-2"
    file_type = "docx"

    file_path = storage.get_document_path(kb_id, doc_id, file_type)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"PK\x03\x04")
    artifact_path = storage.get_parse_artifact_path(file_path)
    artifact_path.write_text('{"chunks": []}', encoding="utf-8")

    deleted = await storage.delete_document(kb_id, doc_id, file_type)

    assert deleted is True
    assert not file_path.exists()
    assert not artifact_path.exists()
