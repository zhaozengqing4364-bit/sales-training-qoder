"""
Document Processor - Background task for document processing

Processes uploaded documents: read -> chunk -> embed -> store.

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 27 (Document Processing)
"""
from __future__ import annotations

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
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)
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

            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"Failed to read DOCX: {e}")
            return None

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
