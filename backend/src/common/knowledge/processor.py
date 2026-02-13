"""
Document Processor - Background task for document processing

Processes uploaded documents: read -> chunk -> embed -> store.

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 27 (Document Processing)
"""
from __future__ import annotations

import hashlib
import io
import os
from typing import Any

from common.ai.embedding_service import get_embedding_service
from common.monitoring.logger import get_logger

from .models import DocumentStatus
from .vector_store import get_knowledge_vector_store

logger = get_logger(__name__)

# 允许的文件上传目录（安全边界）
# 与 document.py 中的 DOCUMENT_STORAGE_PATH 保持一致
ALLOWED_UPLOAD_DIR = os.path.abspath(os.getenv("DOCUMENT_STORAGE_PATH", "./data/documents"))


class DocumentProcessor:
    """
    Processes documents for knowledge base ingestion.

    Pipeline:
    1. Read document content (txt, md, pdf, docx)
    2. Split into overlapping chunks
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
        Process a document: read -> chunk -> embed -> store.

        Args:
            doc_id: Document UUID
            file_path: Local file path
            file_type: File extension (txt, md, pdf, docx)
            document_title: Document title for metadata
            knowledge_base_id: Knowledge base UUID
            vector_collection: ChromaDB collection name

        Returns:
            dict with status, chunk_count, error_message
        """
        try:
            logger.info(f"Processing document {doc_id}: {file_path}")

            # Step 1: Read document content
            content = await self._read_document(file_path, file_type)
            if not content:
                return {
                    "status": DocumentStatus.FAILED.value,
                    "chunk_count": 0,
                    "error_message": "Failed to read document content"
                }

            # Step 2: Split into chunks
            chunks = self._split_into_chunks(content)
            if not chunks:
                return {
                    "status": DocumentStatus.FAILED.value,
                    "chunk_count": 0,
                    "error_message": "No content to process"
                }

            logger.info(f"Document {doc_id}: {len(chunks)} chunks created")

            # Step 3: Generate embeddings
            embedding_service = get_embedding_service()
            if not embedding_service.is_configured:
                logger.warning("Embedding service not configured, skipping vectorization")
                # Still mark as ready, but without vectors
                return {
                    "status": DocumentStatus.READY.value,
                    "chunk_count": len(chunks),
                    "error_message": "Embedding service not configured"
                }

            all_embeddings = []
            chunk_texts = [c["content"] for c in chunks]

            # Process in batches
            for i in range(0, len(chunk_texts), self.batch_size):
                batch = chunk_texts[i:i + self.batch_size]
                result = await embedding_service.embed_batch(batch)

                if not result.is_success:
                    logger.error(f"Embedding failed for batch {i}: {result.error}")
                    return {
                        "status": DocumentStatus.FAILED.value,
                        "chunk_count": 0,
                        "error_message": f"Embedding failed: {result.error}"
                    }

                all_embeddings.extend(result.value)

            logger.info(f"Document {doc_id}: {len(all_embeddings)} embeddings generated")

            # Step 4: Store in vector database
            vector_store = get_knowledge_vector_store()
            store_result = await vector_store.add_chunks(
                collection_name=vector_collection,
                chunks=chunks,
                embeddings=all_embeddings,
                document_id=doc_id,
                document_title=document_title,
            )

            if not store_result.is_success:
                return {
                    "status": DocumentStatus.FAILED.value,
                    "chunk_count": 0,
                    "error_message": f"Vector storage failed: {store_result.error}"
                }

            logger.info(f"Document {doc_id} processed successfully: {len(chunks)} chunks")
            return {
                "status": DocumentStatus.READY.value,
                "chunk_count": len(chunks),
                "error_message": None
            }

        except Exception as e:
            logger.error(f"Failed to process document {doc_id}: {e}")
            return {
                "status": DocumentStatus.FAILED.value,
                "chunk_count": 0,
                "error_message": str(e)
            }

    async def _read_document(self, file_path: str, file_type: str) -> str | None:
        """Read document content based on file type."""
        try:
            # 安全检查：确保文件路径在允许的目录内
            abs_path = os.path.abspath(file_path)
            if not abs_path.startswith(ALLOWED_UPLOAD_DIR):
                logger.error(f"Security: file path outside allowed directory: {file_path}")
                return None

            if file_type in ("txt", "md"):
                return await self._read_txt(file_path)
            elif file_type == "pdf":
                return await self._read_pdf(file_path)
            elif file_type == "docx":
                return await self._read_docx(file_path)
            else:
                logger.error(f"Unsupported file type: {file_type}")
                return None
        except Exception as e:
            logger.error(f"Failed to read document: {e}")
            return None

    async def _read_txt(self, file_path: str) -> str | None:
        """Read plain text file."""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read txt: {e}")
            return None

    async def _read_pdf(self, file_path: str) -> str | None:
        """Read PDF file (requires pypdf)."""
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                logger.warning("pypdf not installed, PDF reading disabled")
                return None

            if not os.path.exists(file_path):
                return None

            reader = PdfReader(file_path)
            text_parts = []
            image_text_parts = []
            for page_index, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(text.strip())

                image_texts = self._extract_text_from_pdf_images(page, page_index)
                if image_texts:
                    image_text_parts.extend(image_texts)

            merged_parts = text_parts + image_text_parts
            merged_content = "\n\n".join(part for part in merged_parts if part).strip()
            return merged_content or None
        except Exception as e:
            logger.error(f"Failed to read PDF: {e}")
            return None

    async def _read_docx(self, file_path: str) -> str | None:
        """Read DOCX file (requires python-docx)."""
        try:
            try:
                from docx import Document
            except ImportError:
                logger.warning("python-docx not installed, DOCX reading disabled")
                return None

            if not os.path.exists(file_path):
                return None

            doc = Document(file_path)
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)

            image_text_parts = self._extract_text_from_docx_images(doc)
            merged_parts = text_parts + image_text_parts
            merged_content = "\n\n".join(part for part in merged_parts if part).strip()
            return merged_content or None
        except Exception as e:
            logger.error(f"Failed to read DOCX: {e}")
            return None

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
                if not isinstance(content_type, str) or not content_type.startswith("image/"):
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
                import pytesseract
                from PIL import Image, ImageOps
            except ImportError:
                logger.debug("pytesseract/Pillow not installed, image OCR disabled")
                return None

            with Image.open(io.BytesIO(image_bytes)) as image:
                # Improve OCR accuracy for scanned docs.
                grayscale_image = ImageOps.autocontrast(image.convert("L"))
                # Try Chinese+English first, then fallback to English only.
                for lang in ("chi_sim+eng", "eng"):
                    try:
                        raw_text = pytesseract.image_to_string(
                            grayscale_image,
                            lang=lang,
                            config="--psm 6",
                        )
                        clean_text = self._normalize_text(raw_text)
                        if clean_text:
                            return clean_text
                    except Exception as ocr_error:
                        logger.debug(f"OCR attempt failed ({source}, lang={lang}): {ocr_error}")
        except Exception as e:
            logger.warning(f"Failed OCR for {source}: {e}")

        return None

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted OCR text to reduce noisy chunks."""
        if not text:
            return ""

        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        normalized = "\n".join(lines).strip()

        # Avoid storing tiny noisy OCR fragments (e.g. a single symbol).
        if len(normalized) < 6:
            return ""
        return normalized

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

            # Try to break at sentence boundary
            if end < len(content):
                # Look for Chinese period, English period, or newline
                last_period_cn = chunk_text.rfind("。")
                last_period_en = chunk_text.rfind(". ")
                last_newline = chunk_text.rfind("\n")
                break_point = max(last_period_cn, last_period_en, last_newline)

                if break_point > self.chunk_size // 2:
                    chunk_text = chunk_text[:break_point + 1]
                    end = start + break_point + 1

            chunk_content = chunk_text.strip()
            if chunk_content:  # Only add non-empty chunks
                chunks.append({
                    "index": index,
                    "content": chunk_content,
                    "metadata": {
                        "start_char": start,
                        "end_char": end
                    }
                })
                index += 1

            start = end - self.chunk_overlap

            # Prevent infinite loop
            if start >= len(content) - self.chunk_overlap:
                break

        return chunks

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
                collection_name=vector_collection,
                document_id=doc_id
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
