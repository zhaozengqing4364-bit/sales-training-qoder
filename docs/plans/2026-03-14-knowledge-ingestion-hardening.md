# Knowledge Ingestion Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the current knowledge-document ingestion flow from string-first parsing to structured parsing with quality gates, companion parse artifacts, richer preview metadata, and optional PaddleOCR-first image OCR fallback.

**Architecture:** Keep the existing FastAPI + local file storage + Chroma pipeline, but insert a structured `ParseResult` layer inside the processor. Persist a JSON companion artifact next to each uploaded file, generate chunks from parsed elements instead of raw text when possible, and make preview prefer the parse artifact so operators inspect the same source of truth used for chunking.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic v2, local document storage, ChromaDB, Pillow, pytesseract, optional PaddleOCR

---

### Task 1: Add failing tests for structured parsing and preview source-of-truth

**Files:**
- Modify: `backend/tests/unit/common/test_document_processor_image_ocr.py`
- Modify: `backend/tests/unit/common/test_knowledge_service_preview_fallback.py`

**Step 1: Write the failing tests**

- Add a test asserting DOCX parsing returns structured elements, chunk metadata, and explicit parse warnings/quality data for table-centric docs.
- Add a test asserting preview uses the stored parse artifact before vector/source fallbacks.
- Add a test asserting empty-but-valid structured docs fail with an explicit parse error code instead of a generic read failure.

**Step 2: Run tests to verify they fail**

Run:
```bash
pytest backend/tests/unit/common/test_document_processor_image_ocr.py backend/tests/unit/common/test_knowledge_service_preview_fallback.py -q
```

**Step 3: Confirm failures are the intended gaps**

- Missing structured parse APIs or artifact support.
- Preview still ignores parse artifact.
- Generic parse failure code still returned.

### Task 2: Implement structured parse results and companion artifact persistence

**Files:**
- Modify: `backend/src/common/knowledge/processor.py`
- Modify: `backend/src/common/storage/document.py`

**Step 1: Add minimal structured parsing model**

- Introduce typed parse result containers for elements, warnings, metrics, chunks, and phase timings.
- Keep existing public processor surface compatible where possible.

**Step 2: Implement companion artifact storage**

- Save a JSON artifact next to each document file.
- Add load/delete helpers in storage service.

**Step 3: Implement minimal code**

- Parse DOCX/PDF/TXT/MD into structured elements.
- Add parse-quality validation with explicit error codes.
- Generate chunk metadata from parsed elements.
- Add optional PaddleOCR-first image OCR with fallback to pytesseract.

### Task 3: Make preview use the parse artifact as the primary source of truth

**Files:**
- Modify: `backend/src/common/knowledge/service.py`
- Modify: `backend/src/common/knowledge/schemas.py`

**Step 1: Read artifact first**

- Load stored parse artifact and return artifact chunks when available.
- Preserve fallback order for degraded paths.

**Step 2: Enrich preview metadata**

- Include element/source metadata needed for operator debugging.

**Step 3: Keep behavior backward compatible**

- Continue supporting vector/source fallback when artifact is absent or invalid.

### Task 4: Wire artifact lifecycle into delete/reprocess flows and log phase timings

**Files:**
- Modify: `backend/src/common/knowledge/api.py`
- Modify: `backend/src/common/knowledge/service.py`

**Step 1: Ensure artifact cleanup/rebuild**

- Delete companion artifacts when deleting documents.
- Overwrite artifacts when reprocessing.

**Step 2: Add phase timing logging**

- Log `parse/chunk/embed/store` timings from the processor result.

### Task 5: Run focused verification

**Files:**
- Test: `backend/tests/unit/common/test_document_processor_image_ocr.py`
- Test: `backend/tests/unit/common/test_knowledge_service_preview_fallback.py`

**Step 1: Run focused tests**

Run:
```bash
pytest backend/tests/unit/common/test_document_processor_image_ocr.py backend/tests/unit/common/test_knowledge_service_preview_fallback.py -q
```

**Step 2: Run a broader knowledge-module safety pass**

Run:
```bash
pytest backend/tests/unit/common/test_knowledge_service_fallback.py backend/tests/unit/common/test_embedding_service_resilience.py -q
```

**Step 3: Review diff**

Run:
```bash
git diff -- backend/src/common/knowledge backend/src/common/storage backend/tests/unit/common docs/plans
```
