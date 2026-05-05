"""
Audio Storage Service

Provides audio file storage and retrieval functionality.
Supports local file storage with configurable retention.

References:
- Requirements: R9 (Message Storage)
- Design: Section 23 (Audio Storage)

Environment Variables:
- AUDIO_STORAGE_PATH: Base path for audio storage (default: ./data/audio)
- AUDIO_RETENTION_DAYS: Days to retain audio files (default: 30)
- AUDIO_BASE_URL: Base URL for audio file access (optional, for CDN)
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# Configuration from environment
AUDIO_STORAGE_PATH = os.getenv("AUDIO_STORAGE_PATH", "./data/audio")
AUDIO_RETENTION_DAYS = int(os.getenv("AUDIO_RETENTION_DAYS", "30"))
AUDIO_BASE_URL = os.getenv("AUDIO_BASE_URL", "")


class AudioStorageService:
    """
    Service for storing and retrieving audio files.

    Supports:
    - Local file storage with organized directory structure
    - URL generation for file access
    - Retention-based cleanup

    Directory Structure:
        {AUDIO_STORAGE_PATH}/
        └── {session_id}/
            └── {message_id}.{format}
    """

    def __init__(self, base_path: str | None = None):
        """
        Initialize audio storage service.

        Args:
            base_path: Override base storage path (uses env var if not provided)
        """
        self.base_path = Path(base_path or AUDIO_STORAGE_PATH)
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """Ensure base storage directory exists."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Audio storage path: {self.base_path}")
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to create audio storage path: {e}")

    async def save_audio(
        self,
        session_id: str,
        message_id: str,
        audio_data: bytes,
        format: str = "mp3",
    ) -> str | None:
        """
        Save audio data to storage.

        Args:
            session_id: Practice session UUID
            message_id: Message UUID
            audio_data: Raw audio bytes
            format: Audio format (default: mp3)

        Returns:
            URL/path to the saved audio file, or None if save failed.
        """
        if not audio_data:
            logger.warning("Empty audio data, skipping save")
            return None

        try:
            # Create session directory
            session_dir = self.base_path / session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            filename = f"{message_id}.{format}"
            file_path = session_dir / filename

            # Write audio data
            file_path.write_bytes(audio_data)

            logger.info(
                f"Saved audio file: {file_path}",
                session_id=session_id,
                message_id=message_id,
                size_bytes=len(audio_data),
            )

            # Return URL or path
            return self.get_audio_url(session_id, message_id, format)

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(
                f"Failed to save audio: {e}",
                session_id=session_id,
                message_id=message_id,
            )
            return None

    def get_audio_url(
        self,
        session_id: str,
        message_id: str,
        format: str = "mp3",
    ) -> str:
        """
        Get URL/path for an audio file.

        Args:
            session_id: Practice session UUID
            message_id: Message UUID
            format: Audio format (default: mp3)

        Returns:
            URL or local path to the audio file.
        """
        filename = f"{message_id}.{format}"

        if AUDIO_BASE_URL:
            # Return CDN/external URL
            return f"{AUDIO_BASE_URL}/{session_id}/{filename}"
        else:
            # Return local path
            return str(self.base_path / session_id / filename)

    def get_audio_path(
        self,
        session_id: str,
        message_id: str,
        format: str = "mp3",
    ) -> Path:
        """
        Get local file path for an audio file.

        Args:
            session_id: Practice session UUID
            message_id: Message UUID
            format: Audio format (default: mp3)

        Returns:
            Path object to the audio file.
        """
        return self.base_path / session_id / f"{message_id}.{format}"

    def audio_exists(
        self,
        session_id: str,
        message_id: str,
        format: str = "mp3",
    ) -> bool:
        """
        Check if an audio file exists.

        Args:
            session_id: Practice session UUID
            message_id: Message UUID
            format: Audio format (default: mp3)

        Returns:
            True if file exists, False otherwise.
        """
        return self.get_audio_path(session_id, message_id, format).exists()

    async def delete_audio(
        self,
        session_id: str,
        message_id: str,
        format: str = "mp3",
    ) -> bool:
        """
        Delete an audio file.

        Args:
            session_id: Practice session UUID
            message_id: Message UUID
            format: Audio format (default: mp3)

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            file_path = self.get_audio_path(session_id, message_id, format)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted audio file: {file_path}")
                return True
            return False
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to delete audio: {e}")
            return False

    async def delete_session_audio(self, session_id: str) -> int:
        """
        Delete all audio files for a session.

        Args:
            session_id: Practice session UUID

        Returns:
            Number of files deleted.
        """
        try:
            session_dir = self.base_path / session_id
            if not session_dir.exists():
                return 0

            count = 0
            for file_path in session_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()
                    count += 1

            # Remove empty directory
            if session_dir.exists() and not any(session_dir.iterdir()):
                session_dir.rmdir()

            logger.info(f"Deleted {count} audio files for session {session_id}")
            return count

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to delete session audio: {e}")
            return 0

    async def cleanup_old_files(self, retention_days: int | None = None) -> int:
        """
        Clean up audio files older than retention period.

        Args:
            retention_days: Override retention period (uses env var if not provided)

        Returns:
            Number of files deleted.
        """
        days = retention_days or AUDIO_RETENTION_DAYS
        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        deleted_count = 0

        try:
            for session_dir in self.base_path.iterdir():
                if not session_dir.is_dir():
                    continue

                for file_path in session_dir.iterdir():
                    if not file_path.is_file():
                        continue

                    # Check file modification time
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1

                # Remove empty session directories
                if session_dir.exists() and not any(session_dir.iterdir()):
                    session_dir.rmdir()

            logger.info(
                f"Cleaned up {deleted_count} old audio files (retention: {days} days)"
            )
            return deleted_count

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return deleted_count

    def get_storage_stats(self) -> dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage stats (total_files, total_size_bytes, sessions).
        """
        total_files = 0
        total_size = 0
        sessions = 0

        try:
            for session_dir in self.base_path.iterdir():
                if not session_dir.is_dir():
                    continue

                sessions += 1
                for file_path in session_dir.iterdir():
                    if file_path.is_file():
                        total_files += 1
                        total_size += file_path.stat().st_size

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to get storage stats: {e}")

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "sessions": sessions,
            "base_path": str(self.base_path),
            "retention_days": AUDIO_RETENTION_DAYS,
        }


# Singleton instance
_audio_storage_service: AudioStorageService | None = None


def get_audio_storage_service() -> AudioStorageService:
    """Get singleton AudioStorageService instance."""
    global _audio_storage_service
    if _audio_storage_service is None:
        _audio_storage_service = AudioStorageService()
    return _audio_storage_service
