"""
Audio Archival Job - Archives old audio files

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful degradation
- V. Cost control - Efficient storage cleanup
"""

import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession
from common.error_handling.result import Result

logger = logging.getLogger(__name__)


class AudioArchivalJob:
    """
    Archives old audio files to save storage space

    Key responsibilities:
    - Identify sessions older than retention period
    - Archive audio files to cold storage
    - Update database with archive location
    - Clean up local files
    """

    def __init__(self):
        self.retention_days = 365  # 1 year retention
        self.audio_storage_path = "/data/audio"
        self.archive_storage_path = "/data/audio_archived"

    async def archive_old_audio(
        self, db: AsyncSession, batch_size: int = 100
    ) -> Result[dict]:
        """
        Archive audio files for sessions older than retention period

        Returns: Archive stats or Result.fail
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=self.retention_days)

            # Find sessions to archive
            query = (
                select(PracticeSession)
                .where(PracticeSession.start_time < cutoff_time)
                .where(PracticeSession.audio_url.isnot(None))
                .where(PracticeSession.archived.is_(False))
                .limit(batch_size)
            )

            result = await db.execute(query)
            sessions = result.scalars().all()

            if not sessions:
                return Result(
                    value={
                        "archived_count": 0,
                        "failed_count": 0,
                        "freed_space_bytes": 0,
                    }
                )

            archived_count = 0
            failed_count = 0
            freed_space = 0

            for session in sessions:
                try:
                    # Get audio file path
                    audio_path = session.audio_url

                    if not os.path.exists(audio_path):
                        logger.warning(
                            "Audio file not found",
                            extra={
                                "session_id": str(session.session_id),
                                "path": audio_path,
                            },
                        )
                        continue

                    # Get file size
                    file_size = os.path.getsize(audio_path)

                    # Create archive directory
                    archive_dir = os.path.join(
                        self.archive_storage_path, str(session.session_id)
                    )
                    os.makedirs(archive_dir, exist_ok=True)

                    # Move file to archive
                    archive_path = os.path.join(
                        archive_dir, os.path.basename(audio_path)
                    )
                    os.rename(audio_path, archive_path)

                    # Update database
                    session.audio_url = archive_path
                    session.archived = True
                    session.archived_at = datetime.now()

                    archived_count += 1
                    freed_space += file_size

                    logger.info(
                        "Audio file archived",
                        extra={
                            "session_id": str(session.session_id),
                            "archive_path": archive_path,
                        },
                    )

                except (SQLAlchemyError, OSError, ValueError, RuntimeError) as e:
                    logger.error(
                        "Failed to archive audio file",
                        extra={"session_id": str(session.session_id), "error": str(e)},
                        exc_info=True,
                    )
                    failed_count += 1

            await db.commit()

            stats = {
                "archived_count": archived_count,
                "failed_count": failed_count,
                "freed_space_bytes": freed_space,
                "freed_space_mb": round(freed_space / 1024 / 1024, 2),
            }

            logger.info("Audio archival batch complete", extra=stats)

            return Result(value=stats)

        except (SQLAlchemyError, OSError, ValueError, RuntimeError) as e:
            logger.error(
                "Failed to run audio archival job",
                extra={"error": str(e)},
                exc_info=True,
            )
            await db.rollback()
            return Result.fail(fallback="[ARCHIVAL_FAILED]")

    async def cleanup_orphaned_audio(self, db: AsyncSession) -> Result[dict]:
        """
        Clean up audio files that don't have corresponding sessions

        Returns: Cleanup stats or Result.fail
        """
        try:
            # Get all session IDs
            query = select(PracticeSession.session_id)
            result = await db.execute(query)
            session_ids = set(row[0] for row in result.all())

            # Scan audio directory for orphaned files
            orphaned_count = 0
            freed_space = 0

            if not os.path.exists(self.audio_storage_path):
                return Result(
                    value={
                        "orphaned_count": 0,
                        "freed_space_bytes": 0,
                    }
                )

            for root, dirs, files in os.walk(self.audio_storage_path):
                for file in files:
                    file_path = os.path.join(root, file)

                    # Check if file belongs to a session
                    # Assuming file names contain session IDs
                    is_orphaned = True
                    for session_id in session_ids:
                        if str(session_id) in file_path:
                            is_orphaned = False
                            break

                    if is_orphaned:
                        try:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            orphaned_count += 1
                            freed_space += file_size

                            logger.info(
                                "Orphaned audio file removed",
                                extra={"file_path": file_path},
                            )

                        except (
                            SQLAlchemyError,
                            OSError,
                            ValueError,
                            RuntimeError,
                        ) as e:
                            logger.error(
                                "Failed to remove orphaned file",
                                extra={"file_path": file_path, "error": str(e)},
                            )

            stats = {
                "orphaned_count": orphaned_count,
                "freed_space_bytes": freed_space,
                "freed_space_mb": round(freed_space / 1024 / 1024, 2),
            }

            logger.info("Orphaned audio cleanup complete", extra=stats)

            return Result(value=stats)

        except (SQLAlchemyError, OSError, ValueError, RuntimeError) as e:
            logger.error(
                "Failed to cleanup orphaned audio",
                extra={"error": str(e)},
                exc_info=True,
            )
            return Result.fail(fallback="[CLEANUP_FAILED]")

    async def get_storage_stats(self, db: AsyncSession) -> Result[dict]:
        """
        Get storage statistics for audio files

        Returns: Storage stats or Result.fail
        """
        try:
            # Calculate active audio storage
            active_size = 0
            active_count = 0

            if os.path.exists(self.audio_storage_path):
                for root, dirs, files in os.walk(self.audio_storage_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        active_size += os.path.getsize(file_path)
                        active_count += 1

            # Calculate archived audio storage
            archived_size = 0
            archived_count = 0

            if os.path.exists(self.archive_storage_path):
                for root, dirs, files in os.walk(self.archive_storage_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        archived_size += os.path.getsize(file_path)
                        archived_count += 1

            stats = {
                "active_count": active_count,
                "active_size_bytes": active_size,
                "active_size_mb": round(active_size / 1024 / 1024, 2),
                "archived_count": archived_count,
                "archived_size_bytes": archived_size,
                "archived_size_mb": round(archived_size / 1024 / 1024, 2),
                "total_size_mb": round((active_size + archived_size) / 1024 / 1024, 2),
            }

            logger.info("Storage stats calculated", extra=stats)

            return Result(value=stats)

        except (SQLAlchemyError, OSError, ValueError, RuntimeError) as e:
            logger.error(
                "Failed to get storage stats", extra={"error": str(e)}, exc_info=True
            )
            return Result.fail(fallback="[STATS_FAILED]")


# Singleton instance
audio_archival_job = AudioArchivalJob()
