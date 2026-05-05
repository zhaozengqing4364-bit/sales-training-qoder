"""OSS Signing Service — generates presigned PUT/GET URLs for browser-direct uploads.

Pure HMAC computation via oss2.Auth; no network I/O during signing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import oss2

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class OssConfigError(Exception):
    """Raised when required ALI_OSS_* environment variables are missing."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            f"OSS credentials not configured — missing env vars: {', '.join(missing)}. "
            "Set ALI_OSS_ACCESS_KEY_ID, ALI_OSS_ACCESS_KEY_SECRET, ALI_OSS_BUCKET, ALI_OSS_ENDPOINT."
        )


_REQUIRED_ENV_VARS = (
    "ALI_OSS_ACCESS_KEY_ID",
    "ALI_OSS_ACCESS_KEY_SECRET",
    "ALI_OSS_BUCKET",
    "ALI_OSS_ENDPOINT",
)


@dataclass(frozen=True)
class PresignedPutResult:
    """Result of a presigned PUT URL generation."""

    url: str
    object_key: str
    expires_at: str  # ISO-8601


class OssSigningService:
    """Generates presigned URLs for browser-direct audio upload to Alibaba Cloud OSS.

    Reads credentials from environment variables at instantiation time so that
    a missing-configuration error surfaces early (at import / first use) rather
    than on every request.
    """

    def __init__(self) -> None:
        missing = [k for k in _REQUIRED_ENV_VARS if not os.getenv(k)]
        if missing:
            raise OssConfigError(missing)

        self._access_key_id = os.environ["ALI_OSS_ACCESS_KEY_ID"]
        self._access_key_secret = os.environ["ALI_OSS_ACCESS_KEY_SECRET"]
        self._bucket_name = os.environ["ALI_OSS_BUCKET"]
        self._endpoint = os.environ["ALI_OSS_ENDPOINT"]

        self._auth = oss2.Auth(self._access_key_id, self._access_key_secret)
        self._bucket = oss2.Bucket(self._auth, self._endpoint, self._bucket_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_put_url(
        self,
        object_key: str,
        content_type: str = "audio/webm",
        expires: int = 900,
    ) -> PresignedPutResult:
        """Return a presigned PUT URL for *object_key*.

        Parameters
        ----------
        object_key:
            Full OSS object path, e.g. ``audio/{session_id}/seg_0001.webm``.
        content_type:
            MIME type to enforce on upload.
        expires:
            URL validity in seconds (default 15 min).

        Returns
        -------
        PresignedPutResult with url, object_key, and expires_at.
        """
        url: str = self._bucket.sign_url(
            "PUT",
            object_key,
            expires=expires,
            headers={"Content-Type": content_type},
        )
        expires_at = datetime.now(UTC) + timedelta(seconds=expires)

        logger.info(
            "audio_upload_url_generated",
            object_key=object_key,
            content_type=content_type,
            expires_in=expires,
        )

        return PresignedPutResult(
            url=url,
            object_key=object_key,
            expires_at=expires_at.isoformat(),
        )

    def generate_get_url(
        self,
        object_key: str,
        expires: int = 3600,
    ) -> str:
        """Return a presigned GET URL for *object_key*.

        Parameters
        ----------
        object_key:
            Full OSS object path.
        expires:
            URL validity in seconds (default 1 hour).

        Returns
        -------
        The signed URL string.
        """
        url: str = self._bucket.sign_url("GET", object_key, expires=expires)
        return url

    @staticmethod
    def build_object_key(session_id: str, segment_sequence: int) -> str:
        """Construct the canonical OSS key for an audio segment.

        Format: ``audio/{session_id}/seg_{sequence:04d}.webm``
        """
        return f"audio/{session_id}/seg_{segment_sequence:04d}.webm"


# ---------------------------------------------------------------------------
# Module-level singleton (lazy)
# ---------------------------------------------------------------------------

_instance: OssSigningService | None = None


def get_oss_signing_service() -> OssSigningService:
    """Return the module-level OssSigningService singleton.

    Raises OssConfigError on first call if env vars are missing.
    """
    global _instance
    if _instance is None:
        _instance = OssSigningService()
    return _instance
