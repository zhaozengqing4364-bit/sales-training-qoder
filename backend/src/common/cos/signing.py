"""Tencent Cloud COS signing helpers for browser-direct audio upload."""

from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class CosConfigError(Exception):
    """Raised when required Tencent COS environment variables are missing."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            "COS credentials not configured - missing env vars: "
            f"{', '.join(missing)}. Set TENCENT_COS_SECRET_ID, "
            "TENCENT_COS_SECRET_KEY, TENCENT_COS_BUCKET, TENCENT_COS_REGION."
        )


_REQUIRED_ENV_VARS = (
    "TENCENT_COS_SECRET_ID",
    "TENCENT_COS_SECRET_KEY",
    "TENCENT_COS_BUCKET",
    "TENCENT_COS_REGION",
)


@dataclass(frozen=True)
class PresignedPutResult:
    """Result of a presigned PUT URL generation."""

    url: str
    object_key: str
    expires_at: str


class CosSigningService:
    """Generates presigned Tencent COS URLs from environment configuration."""

    def __init__(self) -> None:
        self._secret_id = os.getenv("TENCENT_COS_SECRET_ID", "")
        self._secret_key = os.getenv("TENCENT_COS_SECRET_KEY", "")
        self._bucket = os.getenv("TENCENT_COS_BUCKET", "")
        self._region = os.getenv("TENCENT_COS_REGION", "")
        self._scheme = os.getenv("TENCENT_COS_SCHEME", "https")
        self._domain = os.getenv("TENCENT_COS_DOMAIN", "").strip()
        self._public_read = _env_truthy(os.getenv("TENCENT_COS_PUBLIC_READ", "false"))
        self._client = None

    def generate_put_url(
        self,
        object_key: str,
        content_type: str = "audio/webm",
        expires: int = 900,
        *,
        sha256: str | None = None,
    ) -> PresignedPutResult:
        """Return a presigned PUT URL for *object_key*."""
        client = self._require_client()
        headers = {"Content-Type": content_type}
        if sha256:
            headers["x-cos-meta-sha256"] = sha256
        url = client.get_presigned_url(
            Method="PUT",
            Bucket=self._bucket,
            Key=object_key,
            Expired=expires,
            Headers=headers,
        )
        expires_at = datetime.now(UTC) + timedelta(seconds=expires)
        logger.info(
            "sales_trainer_cos_upload_url_generated",
            object_key=object_key,
            content_type=content_type,
            expires_in=expires,
        )
        return PresignedPutResult(
            url=str(url),
            object_key=object_key,
            expires_at=expires_at.isoformat(),
        )

    def generate_get_url(self, object_key: str, expires: int = 3600) -> str:
        """Return a presigned GET URL for *object_key*."""
        if self._domain and self._public_read:
            return _build_public_url(self._domain, object_key)
        client = self._require_client()
        return str(
            client.get_presigned_url(
                Method="GET",
                Bucket=self._bucket,
                Key=object_key,
                Expired=expires,
            )
        )

    def upload_object(
        self,
        object_key: str,
        body: bytes,
        *,
        content_type: str = "audio/webm",
    ) -> str:
        """Upload bytes to Tencent COS and return the stored object key."""
        client = self._require_client()
        normalized_key = _normalize_object_key(object_key)
        client.put_object(
            Bucket=self._bucket,
            Key=normalized_key,
            Body=body,
            ContentType=content_type,
        )
        logger.info(
            "sales_trainer_cos_object_uploaded",
            object_key=normalized_key,
            content_type=content_type,
            size_bytes=len(body),
        )
        return normalized_key

    def get_object_size(self, object_key: str) -> int:
        """Return the remote object size without downloading the object."""
        client = self._require_client()
        normalized_key = _normalize_object_key(object_key)
        try:
            response = client.head_object(Bucket=self._bucket, Key=normalized_key)
        except Exception as exc:
            if _looks_like_not_found(exc):
                raise FileNotFoundError(normalized_key) from exc
            raise
        for key in (
            "Content-Length",
            "content-length",
            "ContentLength",
            "content_length",
        ):
            if key in response:
                return int(response[key])
        raise RuntimeError("COS head_object response did not include content length.")

    def get_object_metadata(self, object_key: str) -> dict[str, Any]:
        """Return verified size/hash metadata without exposing credentials."""

        client = self._require_client()
        normalized_key = _normalize_object_key(object_key)
        try:
            response = client.head_object(Bucket=self._bucket, Key=normalized_key)
        except Exception as exc:
            if _looks_like_not_found(exc):
                raise FileNotFoundError(normalized_key) from exc
            raise
        size: int | None = None
        for key in (
            "Content-Length",
            "content-length",
            "ContentLength",
            "content_length",
        ):
            if key in response:
                size = int(response[key])
                break
        if size is None:
            raise RuntimeError("COS head_object response did not include content length.")
        headers = response.get("headers") if isinstance(response.get("headers"), dict) else {}
        sha256 = (
            response.get("x-cos-meta-sha256")
            or response.get("X-Cos-Meta-Sha256")
            or headers.get("x-cos-meta-sha256")
            or headers.get("X-Cos-Meta-Sha256")
        )
        content_type = (
            response.get("Content-Type")
            or response.get("content-type")
            or headers.get("Content-Type")
            or headers.get("content-type")
        )
        return {
            "size_bytes": size,
            "sha256": str(sha256 or ""),
            "content_type": content_type,
        }

    def download_to_file(self, object_key: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._require_client().download_file(
            Bucket=self._bucket,
            Key=_normalize_object_key(object_key),
            DestFilePath=str(destination),
        )

    def upload_file(
        self,
        object_key: str,
        source: Path,
        *,
        content_type: str,
        sha256: str,
    ) -> None:
        self._require_client().upload_file(
            Bucket=self._bucket,
            Key=_normalize_object_key(object_key),
            LocalFilePath=str(source),
            PartSize=10,
            MAXThread=4,
            EnableMD5=True,
            ContentType=content_type,
            Metadata={"sha256": sha256},
        )

    def delete_object(self, object_key: str) -> None:
        self._require_client().delete_object(
            Bucket=self._bucket,
            Key=_normalize_object_key(object_key),
        )

    def list_object_keys(self, prefix: str) -> list[str]:
        """List every object under one non-empty project prefix."""
        normalized_prefix = _normalize_project_prefix(prefix)
        client = self._require_client()
        marker = ""
        keys: list[str] = []
        while True:
            response = client.list_objects(
                Bucket=self._bucket,
                Prefix=normalized_prefix,
                Marker=marker,
                MaxKeys=1000,
            )
            contents = response.get("Contents") or []
            if isinstance(contents, dict):
                contents = [contents]
            keys.extend(
                str(item["Key"])
                for item in contents
                if isinstance(item, dict)
                and isinstance(item.get("Key"), str)
                and str(item["Key"]).startswith(normalized_prefix)
            )
            truncated = str(response.get("IsTruncated", "false")).lower() == "true"
            if not truncated:
                break
            marker = str(response.get("NextMarker") or "")
            if not marker:
                raise RuntimeError("COS listing was truncated without a next marker.")
        return keys

    def delete_object_keys(self, object_keys: list[str], *, prefix: str) -> None:
        """Delete an already enumerated key set; bucket-wide deletion is impossible."""
        if not object_keys:
            return
        normalized_prefix = _normalize_project_prefix(prefix)
        normalized_keys = [_normalize_object_key(key) for key in object_keys]
        if any(not key.startswith(normalized_prefix) for key in normalized_keys):
            raise ValueError("COS delete key escaped the confirmed project prefix.")
        client = self._require_client()
        for offset in range(0, len(normalized_keys), 1000):
            batch = normalized_keys[offset : offset + 1000]
            client.delete_objects(
                Bucket=self._bucket,
                Delete={
                    "Object": [{"Key": object_key} for object_key in batch],
                    "Quiet": "true",
                },
            )

    def _require_client(self) -> Any:
        if self._client is not None:
            return self._client
        missing = [key for key in _REQUIRED_ENV_VARS if not os.getenv(key)]
        if missing:
            raise CosConfigError(missing)
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:
            raise CosConfigError(["qcloud_cos"]) from exc

        config = CosConfig(
            Region=self._region,
            SecretId=self._secret_id,
            SecretKey=self._secret_key,
            Scheme=self._scheme,
        )
        self._client = CosS3Client(config)
        return self._client


def _build_public_url(domain: str, object_key: str) -> str:
    base = domain.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    normalized_key = _normalize_object_key(object_key)
    quoted_key = quote(normalized_key, safe="/")
    return f"{base}/{quoted_key}"


def _env_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_object_key(object_key: str) -> str:
    normalized_key = posixpath.normpath(object_key.lstrip("/"))
    if normalized_key == "." or normalized_key.startswith("../"):
        raise ValueError("Invalid COS object key.")
    return normalized_key


def _normalize_project_prefix(prefix: str) -> str:
    if not prefix or prefix.startswith("/") or not prefix.endswith("/"):
        raise ValueError("COS project prefix must be non-empty and end with '/'.")
    normalized = _normalize_object_key(prefix)
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def _looks_like_not_found(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if str(status) == "404":
        return True
    code = getattr(exc, "code", None)
    if str(code).lower() in {"nosuchkey", "notfound", "404"}:
        return True
    message = str(exc).lower()
    return "not found" in message or "nosuchkey" in message or "no such key" in message


_instance: CosSigningService | None = None


def get_cos_signing_service() -> CosSigningService:
    """Return the module-level CosSigningService singleton."""
    global _instance
    if _instance is None:
        _instance = CosSigningService()
    return _instance
