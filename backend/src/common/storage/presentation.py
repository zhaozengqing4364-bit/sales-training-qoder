"""
Presentation Storage Service

Provides PPT/PDF file storage and retrieval functionality.
Adapted from DocumentStorageService for presentation files.

Environment Variables:
- PPT_STORAGE_PATH: Base path for presentation storage (default: ./data/presentations)
- PPT_BASE_URL: Base URL for presentation file access (optional, for CDN)
"""

import os
from pathlib import Path

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# Configuration from environment
PPT_STORAGE_PATH = os.getenv("PPT_STORAGE_PATH", "./data/presentations")
PPT_BASE_URL = os.getenv("PPT_BASE_URL", "")


class PresentationStorageService:
    """
    Service for storing and retrieving presentation files (PPT/PDF).

    Supports:
    - Local file storage with organized directory structure
    - URL generation for file access
    - File deletion

    Directory Structure:
        {PPT_STORAGE_PATH}/
        └── {presentation_id}/
            └── {presentation_id}.{format}
    """

    def __init__(self, base_path: str | None = None):
        """
        Initialize presentation storage service.

        Args:
            base_path: Override base storage path (uses env var if not provided)
        """
        self.base_path = Path(base_path or PPT_STORAGE_PATH)
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """Ensure base storage directory exists."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"PPT storage path: {self.base_path}")
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to create PPT storage path: {e}")

    async def save_presentation(
        self,
        presentation_id: str,
        file_data: bytes,
        file_type: str,
    ) -> str | None:
        """
        Save presentation data to storage.

        Args:
            presentation_id: Presentation UUID
            file_data: Raw file bytes
            file_type: File extension (ppt, pptx, pdf)

        Returns:
            Path to saved file, or None if save failed.
        """
        if not file_data:
            logger.warning("Empty file data, skipping save")
            return None

        try:
            # Create presentation directory
            pres_dir = self.base_path / presentation_id
            pres_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            filename = f"{presentation_id}.{file_type}"
            file_path = pres_dir / filename

            # Validate path is within base directory (security)
            resolved_path = file_path.resolve()
            if not str(resolved_path).startswith(str(self.base_path.resolve())):
                logger.error(f"Invalid file path (path traversal attempt): {file_path}")
                return None

            # Write file data
            file_path.write_bytes(file_data)

            logger.info(
                f"Saved presentation file: {file_path}",
                presentation_id=presentation_id,
                size_bytes=len(file_data),
                file_type=file_type,
            )

            # Return local path
            return str(file_path)

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(
                f"Failed to save presentation: {e}",
                presentation_id=presentation_id,
                exc_info=True,
            )
            return None

    def get_presentation_url(
        self,
        presentation_id: str,
        file_type: str,
    ) -> str:
        """
        Get URL/path for a presentation file.

        Args:
            presentation_id: Presentation UUID
            file_type: File extension

        Returns:
            URL or local path to presentation file.
        """
        filename = f"{presentation_id}.{file_type}"

        if PPT_BASE_URL:
            # Return CDN/external URL
            return f"{PPT_BASE_URL}/{presentation_id}/{filename}"
        else:
            # Return local path
            return str(self.base_path / presentation_id / filename)

    def get_presentation_path(
        self,
        presentation_id: str,
        file_type: str,
    ) -> Path:
        """
        Get local file path for a presentation file.

        Args:
            presentation_id: Presentation UUID
            file_type: File extension

        Returns:
            Path object to presentation file.
        """
        return self.base_path / presentation_id / f"{presentation_id}.{file_type}"

    def presentation_exists(
        self,
        presentation_id: str,
        file_type: str,
    ) -> bool:
        """
        Check if a presentation file exists.

        Args:
            presentation_id: Presentation UUID
            file_type: File extension

        Returns:
            True if file exists, False otherwise.
        """
        return self.get_presentation_path(presentation_id, file_type).exists()

    async def delete_presentation(
        self,
        presentation_id: str,
        file_type: str,
    ) -> bool:
        """
        Delete a presentation file.

        Args:
            presentation_id: Presentation UUID
            file_type: File extension

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            file_path = self.get_presentation_path(presentation_id, file_type)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted presentation file: {file_path}")
                return True
            return False
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to delete presentation: {e}", exc_info=True)
            return False


# Singleton instance
_presentation_storage_service: PresentationStorageService | None = None


def get_presentation_storage_service() -> PresentationStorageService:
    """Get singleton PresentationStorageService instance."""
    global _presentation_storage_service
    if _presentation_storage_service is None:
        _presentation_storage_service = PresentationStorageService()
    return _presentation_storage_service
