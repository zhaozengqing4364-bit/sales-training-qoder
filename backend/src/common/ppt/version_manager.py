"""
PPT Version Manager - Manages multiple versions of PPT uploads

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful degradation
- V. Cost control - Efficient storage
"""

import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import Presentation
from common.error_handling.result import Result

logger = logging.getLogger(__name__)


@dataclass
class PPTVersion:
    """Represents a version of a PPT"""

    version_id: uuid.UUID
    presentation_id: uuid.UUID
    version_number: int
    filename: str
    file_path: str
    uploaded_at: datetime
    is_current: bool


class VersionManager:
    """
    Manages version history for PPT uploads

    Key responsibilities:
    - Store multiple versions of the same PPT
    - Track which version is current
    - Enable rollback to previous versions
    - Clean up old versions
    """

    def __init__(self) -> None:
        self.storage_base_path = "/data/ppt_versions"
        self.max_versions_per_presentation = 5

    async def create_version(
        self,
        db: AsyncSession,
        presentation_id: uuid.UUID,
        file_path: str,
        filename: str,
    ) -> Result[PPTVersion]:
        """
        Create a new version for a presentation

        Returns: PPTVersion or Result.fail
        """
        try:
            presentation_key = str(presentation_id)
            # Get current version number
            result = await db.execute(
                select(Presentation).where(
                    Presentation.presentation_id == presentation_key
                )
            )
            presentation = result.scalar_one_or_none()

            if not presentation:
                return Result.fail(fallback="[PRESENTATION_NOT_FOUND]")

            version_number = int(getattr(presentation, "version_number", 0) or 0) + 1
            version_id = uuid.uuid4()

            # Create version directory
            version_dir = os.path.join(
                self.storage_base_path, str(presentation_id), f"v{version_number}"
            )
            os.makedirs(version_dir, exist_ok=True)

            # Copy file to version directory
            version_file_path = os.path.join(version_dir, filename)
            shutil.copy2(file_path, version_file_path)

            # Update presentation version
            setattr(presentation, "version_number", version_number)
            if hasattr(presentation, "updated_at"):
                setattr(presentation, "updated_at", datetime.now())

            await db.commit()

            version = PPTVersion(
                version_id=version_id,
                presentation_id=presentation_id,
                version_number=version_number,
                filename=filename,
                file_path=version_file_path,
                uploaded_at=datetime.now(),
                is_current=True,
            )

            logger.info(
                "PPT version created",
                extra={
                    "presentation_id": str(presentation_id),
                    "version": version_number,
                },
            )

            return Result(value=version)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to create version",
                extra={"presentation_id": str(presentation_id), "error": str(e)},
                exc_info=True,
            )
            return Result.fail(fallback="[VERSION_CREATE_FAILED]")

    async def get_version_history(
        self, db: AsyncSession, presentation_id: uuid.UUID
    ) -> Result[list[PPTVersion]]:
        """
        Get version history for a presentation

        Returns: List of PPTVersion or Result.fail
        """
        try:
            version_dir = os.path.join(self.storage_base_path, str(presentation_id))

            if not os.path.exists(version_dir):
                return Result(value=[])

            versions = []

            # List all version directories
            for entry in os.listdir(version_dir):
                if entry.startswith("v"):
                    version_number = int(entry[1:])

                    # Get files in version directory
                    version_path = os.path.join(version_dir, entry)
                    files = os.listdir(version_path)

                    if files:
                        filename = files[0]
                        file_path = os.path.join(version_path, filename)

                        # Get file modification time
                        uploaded_at = datetime.fromtimestamp(
                            os.path.getmtime(file_path)
                        )

                        version = PPTVersion(
                            version_id=uuid.uuid4(),
                            presentation_id=presentation_id,
                            version_number=version_number,
                            filename=filename,
                            file_path=file_path,
                            uploaded_at=uploaded_at,
                            is_current=(
                                version_number
                                == self._get_current_version(db, presentation_id)
                            ),
                        )

                        versions.append(version)

            # Sort by version number descending
            versions.sort(key=lambda v: v.version_number, reverse=True)

            return Result(value=versions)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to get version history",
                extra={"presentation_id": str(presentation_id), "error": str(e)},
                exc_info=True,
            )
            return Result.fail(fallback="[VERSION_HISTORY_FAILED]")

    async def rollback_to_version(
        self, db: AsyncSession, presentation_id: uuid.UUID, version_number: int
    ) -> Result[bool]:
        """
        Rollback presentation to a specific version

        Returns: True or Result.fail
        """
        try:
            # Get version file path
            version_file_path = os.path.join(
                self.storage_base_path, str(presentation_id), f"v{version_number}"
            )

            if not os.path.exists(version_file_path):
                return Result.fail(fallback="[VERSION_NOT_FOUND]")

            # Get files in version directory
            files = os.listdir(version_file_path)
            if not files:
                return Result.fail(fallback="[VERSION_FILE_NOT_FOUND]")

            version_filename = files[0]

            # Copy file to current location
            current_file_path = os.path.join(
                "/data/presentations", str(presentation_id), version_filename
            )

            os.makedirs(os.path.dirname(current_file_path), exist_ok=True)
            shutil.copy2(
                os.path.join(version_file_path, version_filename), current_file_path
            )

            # Update presentation version
            result = await db.execute(
                select(Presentation).where(
                    Presentation.presentation_id == str(presentation_id)
                )
            )
            presentation = result.scalar_one_or_none()

            if presentation:
                setattr(presentation, "version_number", version_number)
                if hasattr(presentation, "updated_at"):
                    setattr(presentation, "updated_at", datetime.now())
                await db.commit()

            logger.info(
                "Presentation rolled back",
                extra={
                    "presentation_id": str(presentation_id),
                    "version": version_number,
                },
            )

            return Result(value=True)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to rollback",
                extra={
                    "presentation_id": str(presentation_id),
                    "version": version_number,
                    "error": str(e),
                },
                exc_info=True,
            )
            return Result.fail(fallback="[ROLLBACK_FAILED]")

    async def cleanup_old_versions(
        self, db: AsyncSession, presentation_id: uuid.UUID
    ) -> Result[bool]:
        """
        Clean up old versions, keeping only the most recent N versions

        Returns: True or Result.fail
        """
        try:
            result = await self.get_version_history(db, presentation_id)

            if not result.is_success:
                return Result.fail(fallback="[CLEANUP_FAILED]")

            versions = result.unwrap_or([])

            # Keep only the most recent N versions
            if len(versions) <= self.max_versions_per_presentation:
                return Result(value=True)

            # Delete old versions
            versions_to_delete = versions[self.max_versions_per_presentation :]

            for version in versions_to_delete:
                version_dir = os.path.join(
                    self.storage_base_path,
                    str(presentation_id),
                    f"v{version.version_number}",
                )

                if os.path.exists(version_dir):
                    shutil.rmtree(version_dir)

            logger.info(
                "Old versions cleaned up",
                extra={
                    "presentation_id": str(presentation_id),
                    "deleted": len(versions_to_delete),
                },
            )

            return Result(value=True)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to cleanup old versions",
                extra={"presentation_id": str(presentation_id), "error": str(e)},
                exc_info=True,
            )
            return Result.fail(fallback="[CLEANUP_FAILED]")

    def _get_current_version(self, db: AsyncSession, presentation_id: uuid.UUID) -> int:
        """Get current version number from database"""
        try:
            import asyncio

            async def _get() -> int:
                result = await db.execute(
                    select(Presentation).where(
                        Presentation.presentation_id == str(presentation_id)
                    )
                )
                presentation = result.scalar_one_or_none()
                return int(getattr(presentation, "version_number", 0) or 0)

            return asyncio.run(_get())
        except Exception as e:
            logger.warning(
                "Failed to resolve current presentation version",
                extra={"presentation_id": str(presentation_id), "error": str(e)},
            )
            return 0


# Singleton instance
version_manager = VersionManager()
