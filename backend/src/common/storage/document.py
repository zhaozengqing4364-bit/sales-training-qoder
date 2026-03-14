"""
Document Storage Service

Provides document file storage and retrieval functionality.
Supports local file storage with configurable retention.

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 27 (Document Storage)

Environment Variables:
- DOCUMENT_STORAGE_PATH: Base path for document storage (default: ./data/documents)
- DOCUMENT_BASE_URL: Base URL for document file access (optional, for CDN)
"""
import json
import os
from pathlib import Path
from typing import Any

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# Configuration from environment
DOCUMENT_STORAGE_PATH = os.getenv("DOCUMENT_STORAGE_PATH", "./data/documents")
DOCUMENT_BASE_URL = os.getenv("DOCUMENT_BASE_URL", "")


class DocumentStorageService:
    """
    Service for storing and retrieving document files.

    Supports:
    - Local file storage with organized directory structure
    - URL generation for file access
    - File deletion

    Directory Structure:
        {DOCUMENT_STORAGE_PATH}/
        └── {knowledge_base_id}/
            └── {document_id}.{format}
    """

    def __init__(self, base_path: str | None = None):
        """
        Initialize document storage service.

        Args:
            base_path: Override base storage path (uses env var if not provided)
        """
        self.base_path = Path(base_path or DOCUMENT_STORAGE_PATH)
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """Ensure base storage directory exists."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Document storage path: {self.base_path}")
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to create document storage path: {e}")

    async def save_document(
        self,
        knowledge_base_id: str,
        document_id: str,
        file_data: bytes,
        file_type: str,
    ) -> str | None:
        """
        Save document data to storage.

        Args:
            knowledge_base_id: Knowledge base UUID
            document_id: Document UUID
            file_data: Raw file bytes
            file_type: File extension (pdf, docx, txt, md, xlsx, xls)

        Returns:
            Path to the saved file, or None if save failed.
        """
        if not file_data:
            logger.warning("Empty file data, skipping save")
            return None

        try:
            # Create knowledge base directory
            kb_dir = self.base_path / knowledge_base_id
            kb_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            filename = f"{document_id}.{file_type}"
            file_path = kb_dir / filename

            # Write file data
            file_path.write_bytes(file_data)

            logger.info(
                f"Saved document file: {file_path}",
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                size_bytes=len(file_data),
            )

            # Return local path
            return str(file_path)

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(
                f"Failed to save document: {e}",
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
            )
            return None

    def get_document_url(
        self,
        knowledge_base_id: str,
        document_id: str,
        file_type: str,
    ) -> str:
        """
        Get URL/path for a document file.

        Args:
            knowledge_base_id: Knowledge base UUID
            document_id: Document UUID
            file_type: File extension

        Returns:
            URL or local path to the document file.
        """
        filename = f"{document_id}.{file_type}"

        if DOCUMENT_BASE_URL:
            # Return CDN/external URL
            return f"{DOCUMENT_BASE_URL}/{knowledge_base_id}/{filename}"
        else:
            # Return local path
            return str(self.base_path / knowledge_base_id / filename)

    def get_document_path(
        self,
        knowledge_base_id: str,
        document_id: str,
        file_type: str,
    ) -> Path:
        """
        Get local file path for a document file.

        Args:
            knowledge_base_id: Knowledge base UUID
            document_id: Document UUID
            file_type: File extension

        Returns:
            Path object to the document file.
        """
        return self.base_path / knowledge_base_id / f"{document_id}.{file_type}"

    def get_parse_artifact_path(self, file_path: str | Path) -> Path:
        """Get companion structured parse artifact path for a document."""
        source_path = Path(file_path)
        return source_path.with_name(f"{source_path.name}.parsed.json")

    def save_parse_artifact(self, file_path: str | Path, artifact: dict[str, Any]) -> str | None:
        """Persist structured parse artifact next to the source document."""
        try:
            artifact_path = self.get_parse_artifact_path(file_path)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            logger.info("Saved document parse artifact", artifact_path=str(artifact_path))
            return str(artifact_path)
        except (OSError, TypeError, ValueError) as e:
            logger.warning(f"Failed to save parse artifact: {e}", file_path=str(file_path))
            return None

    def load_parse_artifact(self, file_path: str | Path) -> dict[str, Any] | None:
        """Load structured parse artifact for a document."""
        try:
            artifact_path = self.get_parse_artifact_path(file_path)
            if not artifact_path.exists():
                return None
            return json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to load parse artifact: {e}", file_path=str(file_path))
            return None

    def delete_parse_artifact(self, file_path: str | Path) -> bool:
        """Delete structured parse artifact for a document if present."""
        try:
            artifact_path = self.get_parse_artifact_path(file_path)
            if not artifact_path.exists():
                return False
            artifact_path.unlink()
            logger.info("Deleted document parse artifact", artifact_path=str(artifact_path))
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.warning(f"Failed to delete parse artifact: {e}", file_path=str(file_path))
            return False

    def document_exists(
        self,
        knowledge_base_id: str,
        document_id: str,
        file_type: str,
    ) -> bool:
        """
        Check if a document file exists.

        Args:
            knowledge_base_id: Knowledge base UUID
            document_id: Document UUID
            file_type: File extension

        Returns:
            True if file exists, False otherwise.
        """
        return self.get_document_path(knowledge_base_id, document_id, file_type).exists()

    async def delete_document(
        self,
        knowledge_base_id: str,
        document_id: str,
        file_type: str,
    ) -> bool:
        """
        Delete a document file.

        Args:
            knowledge_base_id: Knowledge base UUID
            document_id: Document UUID
            file_type: File extension

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            file_path = self.get_document_path(knowledge_base_id, document_id, file_type)
            self.delete_parse_artifact(file_path)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted document file: {file_path}")
                return True
            return False
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    async def delete_knowledge_base_documents(self, knowledge_base_id: str) -> int:
        """
        Delete all document files for a knowledge base.

        Args:
            knowledge_base_id: Knowledge base UUID

        Returns:
            Number of files deleted.
        """
        try:
            kb_dir = self.base_path / knowledge_base_id
            if not kb_dir.exists():
                return 0

            count = 0
            for file_path in kb_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()
                    count += 1

            # Remove empty directory
            if kb_dir.exists() and not any(kb_dir.iterdir()):
                kb_dir.rmdir()

            logger.info(f"Deleted {count} document files for KB {knowledge_base_id}")
            return count

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to delete KB documents: {e}")
            return 0

    def get_storage_stats(self) -> dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage stats.
        """
        total_files = 0
        total_size = 0
        knowledge_bases = 0

        try:
            for kb_dir in self.base_path.iterdir():
                if not kb_dir.is_dir():
                    continue

                knowledge_bases += 1
                for file_path in kb_dir.iterdir():
                    if file_path.is_file():
                        total_files += 1
                        total_size += file_path.stat().st_size

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to get storage stats: {e}")

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "knowledge_bases": knowledge_bases,
            "base_path": str(self.base_path),
        }


# Singleton instance
_document_storage_service: DocumentStorageService | None = None


def get_document_storage_service() -> DocumentStorageService:
    """Get singleton DocumentStorageService instance."""
    global _document_storage_service
    if _document_storage_service is None:
        _document_storage_service = DocumentStorageService()
    return _document_storage_service
