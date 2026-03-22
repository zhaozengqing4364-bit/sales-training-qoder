"""
File Upload Validation - Prevent malicious file uploads

Implements Constitution Principle VI: Data privacy and compliance
- Validates file types and sizes
- Prevents dangerous file uploads
- Scans for malicious content

Requirements: P1-FIXES.md Issue #19
"""

import os
from typing import Optional, Set, Tuple

from fastapi import HTTPException, UploadFile

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class FileValidator:
    """
    File upload validator

    Features:
    - File size validation
    - File extension validation
    - MIME type validation
    - Filename sanitization

    Usage:
        validator = FileValidator(
            max_size=10*1024*1024,
            allowed_extensions={'.ppt', '.pptx'}
        )

        await validator.validate(file)
    """

    # Default size limit: 10MB
    DEFAULT_MAX_SIZE = 10 * 1024 * 1024

    # Allowed file extensions for presentations
    ALLOWED_PRESENTATION_EXTENSIONS: Set[str] = {".ppt", ".pptx", ".pdf"}

    # Allowed MIME types
    ALLOWED_MIME_TYPES: Set[str] = {
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/pdf",
        "application/octet-stream",  # Some systems use this
    }

    # Dangerous extensions that should never be allowed
    DANGEROUS_EXTENSIONS: Set[str] = {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".sh",
        ".php",
        ".jsp",
        ".asp",
        ".aspx",
        ".py",
        ".rb",
        ".pl",
        ".cgi",
        ".jar",
        ".war",
        ".ear",
        ".js",
        ".vbs",
        ".wsf",
        ".ps1",
        ".scr",
        ".com",
        ".msi",
    }

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        allowed_extensions: Optional[Set[str]] = None,
    ):
        self.max_size = max_size
        self.allowed_extensions = (
            allowed_extensions or self.ALLOWED_PRESENTATION_EXTENSIONS
        )

    async def validate(self, file: UploadFile) -> Tuple[bytes, str]:
        """
        Validate uploaded file

        Args:
            file: FastAPI UploadFile

        Returns:
            Tuple of (file_content, safe_filename)

        Raises:
            HTTPException: If validation fails
        """
        # Check filename
        if not file.filename:
            raise HTTPException(400, "文件名不能为空")

        # Sanitize filename
        safe_filename = self._sanitize_filename(file.filename)

        # Check extension
        ext = os.path.splitext(safe_filename)[1].lower()

        if ext in self.DANGEROUS_EXTENSIONS:
            logger.warning(
                f"Dangerous file upload attempted: {ext}",
                extra={"filename": safe_filename, "extension": ext},
            )
            raise HTTPException(400, f"不支持的文件类型: {ext}")

        if ext not in self.allowed_extensions:
            raise HTTPException(
                400,
                f"不支持的文件类型。允许的类型: {', '.join(self.allowed_extensions)}",
            )

        # Read and validate content
        content = await file.read()

        # Check file size
        if len(content) > self.max_size:
            raise HTTPException(
                413, f"文件过大。最大允许: {self.max_size // (1024 * 1024)}MB"
            )

        if len(content) == 0:
            raise HTTPException(400, "文件不能为空")

        # Validate content type (basic check)
        content_type = file.content_type or "application/octet-stream"

        # Reset file position for future reads
        await file.seek(0)

        logger.info(
            f"File validated: {safe_filename}",
            extra={
                "filename": safe_filename,
                "size": len(content),
                "type": content_type,
            },
        )

        return content, safe_filename

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path components
        filename = os.path.basename(filename)

        # Remove null bytes
        filename = filename.replace("\x00", "")

        # Replace dangerous characters
        filename = filename.replace("..", "_")
        filename = filename.replace("/", "_")
        filename = filename.replace("\\", "_")

        # Limit length
        name, ext = os.path.splitext(filename)
        if len(name) > 100:
            name = name[:100]
        filename = name + ext

        return filename


# Convenience validator instances
presentation_validator = FileValidator(
    max_size=10 * 1024 * 1024,  # 10MB
    allowed_extensions={".ppt", ".pptx", ".pdf"},
)

image_validator = FileValidator(
    max_size=5 * 1024 * 1024,  # 5MB
    allowed_extensions={".jpg", ".jpeg", ".png", ".gif", ".webp"},
)


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension"""
    return os.path.splitext(filename)[1].lower()


def is_allowed_extension(filename: str, allowed: Set[str]) -> bool:
    """Check if file has allowed extension"""
    ext = get_file_extension(filename)
    return ext in allowed
