"""
Document Processor - Background task for document processing

Processes uploaded documents: parse -> chunk -> embed -> store.

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 27 (Document Processing)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import io
import os
import re
from tempfile import NamedTemporaryFile
import time
from typing import Any

from common.ai.embedding_service import get_embedding_service
from common.monitoring.logger import get_logger
from common.storage import get_document_storage_service

from .models import DocumentStatus
from .vector_store import get_knowledge_vector_store

logger = get_logger(__name__)

# 允许的文件上传目录（安全边界）
# 与 document.py 中的 DOCUMENT_STORAGE_PATH 保持一致
ALLOWED_UPLOAD_DIR = os.path.abspath(
    os.getenv("DOCUMENT_STORAGE_PATH", "./data/documents")
)
PARSE_ARTIFACT_VERSION = "2026-03-14"
MIN_PARSE_TEXT_LENGTH = 6
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


@dataclass(slots=True)
class ParsedElement:
    """A typed content element extracted from the source document."""

    element_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParseResult:
    """Structured parse result used as the source of truth for chunking and preview."""

    content: str
    elements: list[ParsedElement]
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    parser_version: str = PARSE_ARTIFACT_VERSION

    def to_artifact(
        self,
        *,
        file_type: str,
        chunks: list[dict[str, Any]],
        phase_timings: dict[str, float],
    ) -> dict[str, Any]:
        return {
            "artifact_version": self.parser_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "file_type": file_type,
            "content": self.content,
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
            "phase_timings": dict(phase_timings),
            "elements": [
                {
                    "element_type": element.element_type,
                    "text": element.text,
                    "metadata": dict(element.metadata),
                }
                for element in self.elements
            ],
            "chunks": chunks,
        }


class DocumentProcessor:
    """
    Processes documents for knowledge base ingestion.

    Pipeline:
    1. Parse document into structured elements
    2. Split parsed content into chunks
    3. Generate embeddings via EmbeddingService
    4. Store in ChromaDB via KnowledgeVectorStore
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 10,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.batch_size = batch_size  # Batch size for embedding API calls
        self._paddle_ocr_instance: Any | None = None
        self._paddle_ocr_init_failed = False

    async def process_document(
        self,
        doc_id: str,
        file_path: str,
        file_type: str,
        document_title: str,
        knowledge_base_id: str,
        vector_collection: str,
    ) -> dict[str, Any]:
        """
        Process a document: parse -> chunk -> embed -> store.

        Args:
            doc_id: Document UUID
            file_path: Local file path
            file_type: File extension (txt, md, pdf, docx)
            document_title: Document title for metadata
            knowledge_base_id: Knowledge base UUID
            vector_collection: ChromaDB collection name

        Returns:
            dict with status, chunk_count, error_message and processing metadata
        """
        phase_timings: dict[str, float] = {
            "parse_ms": 0.0,
            "chunk_ms": 0.0,
            "embed_ms": 0.0,
            "store_ms": 0.0,
        }
        parse_result: ParseResult | None = None
        artifact_path: str | None = None

        try:
            logger.info(f"Processing document {doc_id}: {file_path}")

            parse_started_at = time.monotonic()
            parse_result = await self._parse_document(file_path, file_type)
            phase_timings["parse_ms"] = round(
                (time.monotonic() - parse_started_at) * 1000, 1
            )
            if parse_result is None:
                return self._build_failure_result(
                    "[PARSE_READ_FAILED] Failed to parse document content",
                    phase_timings=phase_timings,
                )

            parse_error = self._validate_parse_result(parse_result)
            if parse_error is not None:
                return self._build_failure_result(
                    parse_error,
                    phase_timings=phase_timings,
                    parse_result=parse_result,
                )

            chunk_started_at = time.monotonic()
            chunks = self._build_chunks_from_parse_result(parse_result)
            phase_timings["chunk_ms"] = round(
                (time.monotonic() - chunk_started_at) * 1000, 1
            )
            if not chunks:
                return self._build_failure_result(
                    "[PARSE_EMPTY_STRUCTURED_DOC] No structured content to process",
                    phase_timings=phase_timings,
                    parse_result=parse_result,
                )

            logger.info(f"Document {doc_id}: {len(chunks)} chunks created")

            storage = get_document_storage_service()
            artifact_payload = parse_result.to_artifact(
                file_type=file_type,
                chunks=chunks,
                phase_timings=phase_timings,
            )
            artifact_path = storage.save_parse_artifact(file_path, artifact_payload)
            if artifact_path is None:
                parse_result.warnings.append("[PARSE_ARTIFACT_SAVE_FAILED]")

            embedding_service = get_embedding_service()
            if not embedding_service.is_configured:
                logger.error(
                    "Embedding service not configured, cannot build searchable vectors"
                )
                return self._build_failure_result(
                    "[EMBEDDING_NOT_CONFIGURED] Embedding service not configured",
                    phase_timings=phase_timings,
                    parse_result=parse_result,
                    artifact_path=artifact_path,
                )

            all_embeddings = []
            chunk_texts = [c["content"] for c in chunks]

            embed_started_at = time.monotonic()
            for i in range(0, len(chunk_texts), self.batch_size):
                batch = chunk_texts[i : i + self.batch_size]
                result = await embedding_service.embed_batch(batch)

                if not result.is_success:
                    failure_message = result.fallback or "[EMBEDDING_FAILED]"
                    logger.error(f"Embedding failed for batch {i}: {failure_message}")
                    phase_timings["embed_ms"] = round(
                        (time.monotonic() - embed_started_at) * 1000, 1
                    )
                    return self._build_failure_result(
                        f"Embedding failed: {failure_message}",
                        phase_timings=phase_timings,
                        parse_result=parse_result,
                        artifact_path=artifact_path,
                    )

                all_embeddings.extend(result.value)
            phase_timings["embed_ms"] = round(
                (time.monotonic() - embed_started_at) * 1000, 1
            )

            logger.info(
                f"Document {doc_id}: {len(all_embeddings)} embeddings generated"
            )

            store_started_at = time.monotonic()
            vector_store = get_knowledge_vector_store()
            store_result = await vector_store.add_chunks(
                collection_name=vector_collection,
                chunks=chunks,
                embeddings=all_embeddings,
                document_id=doc_id,
                document_title=document_title,
            )
            phase_timings["store_ms"] = round(
                (time.monotonic() - store_started_at) * 1000, 1
            )

            if not store_result.is_success:
                failure_message = store_result.fallback or "[VECTOR_STORAGE_FAILED]"
                return self._build_failure_result(
                    f"Vector storage failed: {failure_message}",
                    phase_timings=phase_timings,
                    parse_result=parse_result,
                    artifact_path=artifact_path,
                )

            logger.info(
                "Document processed successfully",
                document_id=doc_id,
                chunk_count=len(chunks),
                phase_timings=phase_timings,
                parse_metrics=parse_result.metrics,
                parse_warnings=parse_result.warnings,
            )
            return {
                "status": DocumentStatus.READY.value,
                "chunk_count": len(chunks),
                "error_message": None,
                "phase_timings": phase_timings,
                "parse_warnings": list(parse_result.warnings),
                "parse_metrics": dict(parse_result.metrics),
                "artifact_path": artifact_path,
            }

        except Exception as e:
            logger.error(f"Failed to process document {doc_id}: {e}")
            return self._build_failure_result(
                str(e),
                phase_timings=phase_timings,
                parse_result=parse_result,
                artifact_path=artifact_path,
            )

    def _build_failure_result(
        self,
        error_message: str,
        *,
        phase_timings: dict[str, float],
        parse_result: ParseResult | None = None,
        artifact_path: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": DocumentStatus.FAILED.value,
            "chunk_count": 0,
            "error_message": error_message,
            "phase_timings": dict(phase_timings),
            "parse_warnings": list(parse_result.warnings) if parse_result else [],
            "parse_metrics": dict(parse_result.metrics) if parse_result else {},
            "artifact_path": artifact_path,
        }

    async def _parse_document(self, file_path: str, file_type: str) -> ParseResult | None:
        """Parse document into structured elements based on file type."""
        try:
            abs_path = os.path.abspath(file_path)
            if not abs_path.startswith(ALLOWED_UPLOAD_DIR):
                logger.error(
                    f"Security: file path outside allowed directory: {file_path}"
                )
                return None

            if file_type in ("txt", "md"):
                return await self._parse_text_file(file_path, file_type)
            if file_type == "pdf":
                return await self._parse_pdf(file_path)
            if file_type == "docx":
                return await self._parse_docx(file_path)

            logger.error(f"Unsupported file type: {file_type}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse document: {e}")
            return None

    async def _read_document(self, file_path: str, file_type: str) -> str | None:
        """Read document content based on file type."""
        parse_result = await self._parse_document(file_path, file_type)
        if parse_result is None or not parse_result.content.strip():
            return None
        return parse_result.content

    async def _read_txt(self, file_path: str) -> str | None:
        """Read plain text file."""
        parse_result = await self._parse_text_file(file_path, "txt")
        if parse_result is None:
            return None
        return parse_result.content or None

    async def _read_pdf(self, file_path: str) -> str | None:
        """Read PDF file and return merged text content."""
        parse_result = await self._parse_pdf(file_path)
        if parse_result is None:
            return None
        return parse_result.content or None

    async def _read_docx(self, file_path: str) -> str | None:
        """Read DOCX file and return merged text content."""
        parse_result = await self._parse_docx(file_path)
        if parse_result is None:
            return None
        return parse_result.content or None

    async def _parse_text_file(
        self,
        file_path: str,
        file_type: str,
    ) -> ParseResult | None:
        """Parse plain text or markdown file into structured paragraphs."""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None

            with open(file_path, encoding="utf-8") as f:
                raw_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read text file: {e}")
            return None

        elements: list[ParsedElement] = []
        warnings: list[str] = []
        metrics: dict[str, Any] = {
            "paragraph_count": 0,
            "heading_count": 0,
            "table_row_count": 0,
            "ocr_block_count": 0,
        }

        for block in _PARAGRAPH_SPLIT_RE.split(raw_content):
            text = self._normalize_text_block(block)
            if not text:
                continue
            element_type = "heading" if file_type == "md" and text.startswith("#") else "paragraph"
            if element_type == "heading":
                metrics["heading_count"] += 1
            else:
                metrics["paragraph_count"] += 1
            elements.append(
                ParsedElement(
                    element_type=element_type,
                    text=text,
                    metadata={"source_mode": "native_text"},
                )
            )

        return self._finalize_parse_result(elements, warnings, metrics)

    async def _parse_pdf(self, file_path: str) -> ParseResult | None:
        """Parse PDF file into page-scoped structured elements."""
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                logger.warning("pypdf not installed, PDF reading disabled")
                return None

            if not os.path.exists(file_path):
                return None

            reader = PdfReader(file_path)
            elements: list[ParsedElement] = []
            warnings: list[str] = []
            metrics: dict[str, Any] = {
                "page_count": len(reader.pages),
                "paragraph_count": 0,
                "heading_count": 0,
                "table_row_count": 0,
                "ocr_block_count": 0,
            }

            for page_index, page in enumerate(reader.pages, start=1):
                text = self._normalize_text_block(page.extract_text() or "")
                if text:
                    elements.append(
                        ParsedElement(
                            element_type="paragraph",
                            text=text,
                            metadata={
                                "page": page_index,
                                "source_mode": "native_text",
                            },
                        )
                    )
                    metrics["paragraph_count"] += 1

                image_texts = self._extract_text_from_pdf_images(page, page_index)
                for image_index, image_text in enumerate(image_texts, start=1):
                    elements.append(
                        ParsedElement(
                            element_type="image_ocr",
                            text=image_text,
                            metadata={
                                "page": page_index,
                                "image_index": image_index,
                                "source_mode": "ocr",
                            },
                        )
                    )
                    metrics["ocr_block_count"] += 1

            if metrics["paragraph_count"] == 0 and metrics["ocr_block_count"] > 0:
                warnings.append("[OCR_ONLY_CONTENT]")

            return self._finalize_parse_result(elements, warnings, metrics)
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            return None

    async def _parse_docx(self, file_path: str) -> ParseResult | None:
        """Parse DOCX file into structured paragraph/table/image elements."""
        try:
            try:
                from docx import Document
            except ImportError:
                logger.warning("python-docx not installed, DOCX reading disabled")
                return None

            if not os.path.exists(file_path):
                return None

            doc = Document(file_path)
            elements: list[ParsedElement] = []
            warnings: list[str] = []
            metrics: dict[str, Any] = {
                "paragraph_count": 0,
                "heading_count": 0,
                "table_row_count": 0,
                "ocr_block_count": 0,
            }

            for para in getattr(doc, "paragraphs", []) or []:
                text = self._normalize_text_block(getattr(para, "text", ""))
                if not text:
                    continue
                elements.append(
                    ParsedElement(
                        element_type="paragraph",
                        text=text,
                        metadata={"source_mode": "native_text"},
                    )
                )
                metrics["paragraph_count"] += 1

            table_elements = self._extract_docx_table_elements(doc)
            elements.extend(table_elements)
            metrics["table_row_count"] = len(table_elements)
            if table_elements and metrics["paragraph_count"] == 0:
                warnings.append("[DOCX_TABLE_ONLY]")

            image_texts = self._extract_text_from_docx_images(doc)
            for image_index, image_text in enumerate(image_texts, start=1):
                elements.append(
                    ParsedElement(
                        element_type="image_ocr",
                        text=image_text,
                        metadata={
                            "image_index": image_index,
                            "source_mode": "ocr",
                        },
                    )
                )
                metrics["ocr_block_count"] += 1

            if metrics["paragraph_count"] == 0 and metrics["ocr_block_count"] > 0:
                warnings.append("[OCR_ONLY_CONTENT]")

            return self._finalize_parse_result(elements, warnings, metrics)
        except Exception as e:
            logger.error(f"Failed to parse DOCX: {e}")
            return None

    def _finalize_parse_result(
        self,
        elements: list[ParsedElement],
        warnings: list[str],
        metrics: dict[str, Any],
    ) -> ParseResult:
        """Normalize elements, assign positions, and compute aggregate metrics."""
        normalized_elements: list[ParsedElement] = []
        for index, element in enumerate(elements):
            text = self._normalize_text_block(element.text)
            if not text:
                continue
            metadata = dict(element.metadata)
            metadata.setdefault("element_index", index)
            normalized_elements.append(
                ParsedElement(
                    element_type=element.element_type,
                    text=text,
                    metadata=metadata,
                )
            )

        content = self._hydrate_element_positions(normalized_elements)
        non_whitespace_text = "".join(content.split())
        metrics = dict(metrics)
        metrics["element_count"] = len(normalized_elements)
        metrics["character_count"] = len(content)
        metrics["non_whitespace_char_count"] = len(non_whitespace_text)

        return ParseResult(
            content=content,
            elements=normalized_elements,
            warnings=self._dedupe_list(warnings),
            metrics=metrics,
        )

    def _validate_parse_result(self, parse_result: ParseResult) -> str | None:
        """Validate parse quality and return an explicit error code on failure."""
        content = parse_result.content.strip()
        non_whitespace_char_count = int(
            parse_result.metrics.get("non_whitespace_char_count")
            or len("".join(content.split()))
        )
        if not content:
            return "[PARSE_EMPTY_STRUCTURED_DOC] No structured content extracted"
        if non_whitespace_char_count < MIN_PARSE_TEXT_LENGTH:
            return "[PARSE_EMPTY_STRUCTURED_DOC] Extracted content too short for indexing"
        if not parse_result.elements:
            return "[PARSE_EMPTY_STRUCTURED_DOC] No structured elements extracted"
        return None

    def _extract_docx_table_elements(self, doc: Any) -> list[ParsedElement]:
        """Extract structured elements from DOCX tables."""
        table_elements: list[ParsedElement] = []
        seen_rows: set[str] = set()

        try:
            for table_index, table in enumerate(getattr(doc, "tables", []) or [], start=1):
                for row_index, row in enumerate(getattr(table, "rows", []) or [], start=1):
                    row_parts: list[str] = []
                    for cell in getattr(row, "cells", []) or []:
                        cell_text = self._normalize_docx_cell_text(getattr(cell, "text", ""))
                        if cell_text:
                            row_parts.append(cell_text)

                    if not row_parts:
                        continue

                    row_text = " | ".join(row_parts)
                    if row_text in seen_rows:
                        continue

                    seen_rows.add(row_text)
                    table_elements.append(
                        ParsedElement(
                            element_type="table_row",
                            text=row_text,
                            metadata={
                                "table_index": table_index,
                                "row_index": row_index,
                                "column_count": len(row_parts),
                                "source_mode": "table",
                            },
                        )
                    )
        except Exception as e:
            logger.warning(f"DOCX table text extraction skipped: {e}")

        return table_elements

    def _extract_text_from_docx_tables(self, doc: Any) -> list[str]:
        """Extract text from DOCX tables for compatibility with legacy callers."""
        return [element.text for element in self._extract_docx_table_elements(doc)]

    def _normalize_docx_cell_text(self, text: str) -> str:
        """Normalize DOCX table cell text without dropping short but meaningful labels."""
        if not text:
            return ""

        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def _extract_text_from_pdf_images(self, page: Any, page_index: int) -> list[str]:
        """Extract OCR text from images embedded in a PDF page."""
        image_texts: list[str] = []
        try:
            page_images = getattr(page, "images", None)
            if not page_images:
                return image_texts

            for image_index, image in enumerate(page_images, start=1):
                image_bytes = getattr(image, "data", None)
                if not image_bytes:
                    continue

                ocr_text = self._ocr_image_bytes(
                    image_bytes,
                    source=f"pdf_page_{page_index}_image_{image_index}",
                )
                if ocr_text:
                    image_texts.append(ocr_text)
        except Exception as e:
            logger.warning(f"PDF image OCR skipped on page {page_index}: {e}")

        return image_texts

    def _extract_text_from_docx_images(self, doc: Any) -> list[str]:
        """Extract OCR text from images embedded in a DOCX document."""
        image_texts: list[str] = []
        try:
            rels = getattr(getattr(doc, "part", None), "rels", {}) or {}
            if not rels:
                return image_texts

            seen_images: set[str] = set()
            for rel in rels.values():
                target_part = getattr(rel, "target_part", None)
                content_type = getattr(target_part, "content_type", "")
                if not isinstance(content_type, str) or not content_type.startswith(
                    "image/"
                ):
                    continue

                image_bytes = getattr(target_part, "blob", None)
                if not image_bytes:
                    continue

                image_hash = hashlib.md5(image_bytes).hexdigest()
                if image_hash in seen_images:
                    continue
                seen_images.add(image_hash)

                ocr_text = self._ocr_image_bytes(
                    image_bytes,
                    source=f"docx_image_{len(seen_images)}",
                )
                if ocr_text:
                    image_texts.append(ocr_text)
        except Exception as e:
            logger.warning(f"DOCX image OCR skipped: {e}")

        return image_texts

    def _ocr_image_bytes(self, image_bytes: bytes, source: str) -> str | None:
        """Run OCR on image bytes and return normalized text."""
        try:
            try:
                from PIL import Image, ImageOps
            except ImportError:
                logger.debug("Pillow not installed, image OCR disabled")
                return None

            with Image.open(io.BytesIO(image_bytes)) as image:
                grayscale_image = ImageOps.autocontrast(image.convert("L"))
                provider = os.getenv("KNOWLEDGE_OCR_PROVIDER", "auto").strip().lower()

                if provider in {"auto", "paddle"}:
                    paddle_text = self._ocr_with_paddle(grayscale_image, source)
                    if paddle_text:
                        return paddle_text

                if provider == "disabled":
                    return None

                return self._ocr_with_tesseract(grayscale_image, source)
        except Exception as e:
            logger.warning(f"Failed OCR for {source}: {e}")

        return None

    def _ocr_with_paddle(self, image: Any, source: str) -> str | None:
        """Use PaddleOCR when available for Chinese-first OCR environments."""
        ocr = self._get_paddle_ocr()
        if ocr is None:
            return None

        try:
            with NamedTemporaryFile(suffix=".png", delete=True) as temp_file:
                image.save(temp_file.name, format="PNG")

                if hasattr(ocr, "predict"):
                    raw_result = ocr.predict(temp_file.name)
                elif hasattr(ocr, "ocr"):
                    raw_result = ocr.ocr(temp_file.name, cls=True)
                else:
                    logger.debug("Unsupported PaddleOCR interface detected")
                    return None

            texts = self._extract_paddle_texts(raw_result)
            return self._normalize_text("\n".join(texts))
        except Exception as e:
            logger.debug(f"PaddleOCR failed ({source}): {e}")
            return None

    def _get_paddle_ocr(self) -> Any | None:
        """Lazily initialize PaddleOCR if available."""
        if self._paddle_ocr_init_failed:
            return None
        if self._paddle_ocr_instance is not None:
            return self._paddle_ocr_instance

        try:
            from paddleocr import PaddleOCR
        except ImportError:
            self._paddle_ocr_init_failed = True
            logger.debug("paddleocr not installed, PaddleOCR disabled")
            return None

        lang = os.getenv("KNOWLEDGE_OCR_LANG", "ch")
        try:
            self._paddle_ocr_instance = PaddleOCR(lang=lang)
        except TypeError:
            self._paddle_ocr_instance = PaddleOCR(use_angle_cls=True, lang=lang)
        except Exception as e:
            self._paddle_ocr_init_failed = True
            logger.warning(f"Failed to initialize PaddleOCR: {e}")
            return None
        return self._paddle_ocr_instance

    def _extract_paddle_texts(self, raw_result: Any) -> list[str]:
        """Collect OCR texts from multiple PaddleOCR result shapes."""
        texts: list[str] = []

        def _collect(node: Any) -> None:
            if node is None:
                return
            if isinstance(node, str):
                stripped = node.strip()
                if stripped:
                    texts.append(stripped)
                return
            if isinstance(node, dict):
                for key in ("rec_texts", "texts"):
                    value = node.get(key)
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, str) and item.strip():
                                texts.append(item.strip())
                nested = node.get("res")
                if nested is not None:
                    _collect(nested)
                for value in node.values():
                    if isinstance(value, (dict, list, tuple)):
                        _collect(value)
                return
            if isinstance(node, (list, tuple)):
                if (
                    len(node) == 2
                    and isinstance(node[1], (list, tuple))
                    and node[1]
                    and isinstance(node[1][0], str)
                ):
                    texts.append(node[1][0].strip())
                    return
                for item in node:
                    _collect(item)
                return

            for attr in ("rec_texts", "texts", "res"):
                value = getattr(node, attr, None)
                if value is not None:
                    _collect(value)

        _collect(raw_result)
        return self._dedupe_list(texts)

    def _ocr_with_tesseract(self, image: Any, source: str) -> str | None:
        """Fallback OCR implementation using pytesseract."""
        try:
            import pytesseract
        except ImportError:
            logger.debug("pytesseract not installed, tesseract OCR disabled")
            return None

        for lang in ("chi_sim+eng", "eng"):
            try:
                raw_text = pytesseract.image_to_string(
                    image,
                    lang=lang,
                    config="--psm 6",
                )
                clean_text = self._normalize_text(raw_text)
                if clean_text:
                    return clean_text
            except Exception as ocr_error:
                logger.debug(
                    f"Tesseract OCR attempt failed ({source}, lang={lang}): {ocr_error}"
                )
        return None

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted OCR text to reduce noisy chunks."""
        if not text:
            return ""

        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        normalized = "\n".join(lines).strip()

        if len(normalized) < MIN_PARSE_TEXT_LENGTH:
            return ""
        return normalized

    def _normalize_text_block(self, text: str) -> str:
        """Normalize a text block while preserving meaningful line breaks."""
        if not text:
            return ""
        lines = [line.strip() for line in str(text).splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines).strip()

    def _hydrate_element_positions(self, elements: list[ParsedElement]) -> str:
        """Assign absolute character positions for each parsed element."""
        parts: list[str] = []
        cursor = 0

        for index, element in enumerate(elements):
            if parts:
                separator = "\n\n"
                parts.append(separator)
                cursor += len(separator)

            start = cursor
            parts.append(element.text)
            cursor += len(element.text)

            metadata = dict(element.metadata)
            metadata["element_index"] = index
            metadata["char_start"] = start
            metadata["char_end"] = cursor
            element.metadata = metadata

        return "".join(parts).strip()

    def _build_chunks_from_parse_result(
        self,
        parse_result: ParseResult,
    ) -> list[dict[str, Any]]:
        """Build chunks from structured elements while preserving element boundaries."""
        chunks: list[dict[str, Any]] = []
        current_elements: list[ParsedElement] = []

        for element in parse_result.elements:
            if len(element.text) > self.chunk_size:
                if current_elements:
                    chunks.append(
                        self._build_chunk_from_elements(
                            current_elements,
                            index=len(chunks),
                            warnings=parse_result.warnings,
                        )
                    )
                    current_elements = []
                for overflow_chunk in self._split_long_element(element, len(chunks), parse_result.warnings):
                    chunks.append(overflow_chunk)
                continue

            prospective = current_elements + [element]
            if current_elements and len(self._join_element_texts(prospective)) > self.chunk_size:
                chunks.append(
                    self._build_chunk_from_elements(
                        current_elements,
                        index=len(chunks),
                        warnings=parse_result.warnings,
                    )
                )
                current_elements = self._tail_overlap_elements(current_elements)
                while (
                    current_elements
                    and len(self._join_element_texts(current_elements + [element])) > self.chunk_size
                ):
                    current_elements = current_elements[1:]
            current_elements.append(element)

        if current_elements:
            chunks.append(
                self._build_chunk_from_elements(
                    current_elements,
                    index=len(chunks),
                    warnings=parse_result.warnings,
                )
            )

        return chunks

    def _split_into_chunks(self, content: str) -> list[dict[str, Any]]:
        """
        Split content into overlapping chunks.

        Uses sentence-aware splitting to avoid breaking mid-sentence.
        """
        if not content:
            return []

        chunks = []
        start = 0
        index = 0

        while start < len(content):
            end = start + self.chunk_size
            chunk_text = content[start:end]

            if end < len(content):
                last_period_cn = chunk_text.rfind("。")
                last_period_en = chunk_text.rfind(". ")
                last_newline = chunk_text.rfind("\n")
                break_point = max(last_period_cn, last_period_en, last_newline)

                if break_point > self.chunk_size // 2:
                    chunk_text = chunk_text[: break_point + 1]
                    end = start + break_point + 1

            chunk_content = chunk_text.strip()
            if chunk_content:
                chunks.append(
                    {
                        "index": index,
                        "content": chunk_content,
                        "metadata": {"start_char": start, "end_char": end},
                    }
                )
                index += 1

            start = end - self.chunk_overlap
            if start >= len(content) - self.chunk_overlap:
                break

        return chunks

    def _split_long_element(
        self,
        element: ParsedElement,
        chunk_index_start: int,
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        """Split a single oversized element using legacy text chunking."""
        base_chunks = self._split_into_chunks(element.text)
        chunks: list[dict[str, Any]] = []
        base_start = int(element.metadata.get("char_start") or 0)
        for offset, base_chunk in enumerate(base_chunks):
            relative_start = int(base_chunk.get("metadata", {}).get("start_char") or 0)
            relative_end = int(base_chunk.get("metadata", {}).get("end_char") or 0)
            chunk = self._build_chunk_from_elements(
                [element],
                index=chunk_index_start + offset,
                warnings=warnings,
                start_char=base_start + relative_start,
                end_char=base_start + relative_end,
                content=str(base_chunk.get("content") or ""),
            )
            chunks.append(chunk)
        return chunks

    def _build_chunk_from_elements(
        self,
        elements: list[ParsedElement],
        *,
        index: int,
        warnings: list[str],
        start_char: int | None = None,
        end_char: int | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Build a chunk and aggregate metadata from its source elements."""
        text = content or self._join_element_texts(elements).strip()
        pages = [
            int(element.metadata["page"])
            for element in elements
            if isinstance(element.metadata.get("page"), int)
        ]
        source_modes = [
            str(element.metadata.get("source_mode"))
            for element in elements
            if element.metadata.get("source_mode")
        ]
        table_rows = [
            int(element.metadata["row_index"])
            for element in elements
            if isinstance(element.metadata.get("row_index"), int)
        ]

        if start_char is None:
            start_char = int(elements[0].metadata.get("char_start") or 0)
        if end_char is None:
            end_char = int(elements[-1].metadata.get("char_end") or start_char)

        metadata: dict[str, Any] = {
            "start_char": start_char,
            "end_char": end_char,
            "element_types": self._dedupe_list(
                [element.element_type for element in elements if element.element_type]
            ),
            "source_mode": (
                source_modes[0]
                if len(set(source_modes)) == 1 and source_modes
                else "mixed"
                if source_modes
                else "native_text"
            ),
            "parser_version": PARSE_ARTIFACT_VERSION,
        }
        if warnings:
            metadata["warning_codes"] = self._dedupe_list(warnings)
        if pages:
            metadata["page"] = min(pages)
            metadata["page_end"] = max(pages)
        if table_rows:
            metadata["table_row_start"] = min(table_rows)
            metadata["table_row_end"] = max(table_rows)

        return {
            "index": index,
            "content": text,
            "metadata": metadata,
        }

    def _join_element_texts(self, elements: list[ParsedElement]) -> str:
        return "\n\n".join(element.text for element in elements if element.text).strip()

    def _tail_overlap_elements(self, elements: list[ParsedElement]) -> list[ParsedElement]:
        """Carry tail elements forward to preserve overlap across structured chunks."""
        if self.chunk_overlap <= 0:
            return []

        overlap_elements: list[ParsedElement] = []
        overlap_chars = 0
        for element in reversed(elements):
            element_length = len(element.text) + (2 if overlap_elements else 0)
            overlap_elements.insert(0, element)
            overlap_chars += element_length
            if overlap_chars >= self.chunk_overlap:
                break
        return overlap_elements

    def _dedupe_list(self, values: list[str]) -> list[str]:
        """Preserve order while removing duplicates and blank strings."""
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    async def delete_document_vectors(
        self,
        doc_id: str,
        vector_collection: str,
    ) -> bool:
        """
        Delete vectors for a document.

        Args:
            doc_id: Document UUID
            vector_collection: ChromaDB collection name

        Returns:
            True if successful
        """
        try:
            vector_store = get_knowledge_vector_store()
            result = await vector_store.delete_document_chunks(
                collection_name=vector_collection, document_id=doc_id
            )
            return result.is_success
        except Exception as e:
            logger.error(f"Failed to delete document vectors: {e}")
            return False


# Singleton instance
_document_processor: DocumentProcessor | None = None


def get_document_processor() -> DocumentProcessor:
    """Get singleton DocumentProcessor instance."""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor
