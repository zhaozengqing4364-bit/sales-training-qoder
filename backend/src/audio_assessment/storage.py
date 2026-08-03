"""Configured storage adapters for direct, verified audio-part uploads."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from audio_assessment.ports import (
    AudioObjectMetadata,
    AudioObjectStoragePort,
    PresignedAudioPart,
    StoredAudioObject,
)
from common.cos.signing import (
    CosConfigError,
    CosSigningService,
    get_cos_signing_service,
)
from common.oss.signing import (
    OssConfigError,
    OssSigningService,
    get_oss_signing_service,
)


class AudioStorageError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        self.code = code
        self.safe_message = message
        self.retryable = retryable
        super().__init__(message)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("wb") as writer:
        shutil.copyfileobj(reader, writer, length=1024 * 1024)


def _append_file(source: Path, destination: Path) -> None:
    with source.open("rb") as reader, destination.open("ab") as writer:
        shutil.copyfileobj(reader, writer, length=1024 * 1024)


def _safe_local_path(root: Path, object_key: str) -> Path:
    candidate = (root / object_key).resolve()
    if root not in candidate.parents:
        raise AudioStorageError(
            "audio_object_key_invalid",
            "音频对象路径无效。",
            retryable=False,
        )
    return candidate


class LocalAudioObjectStorage(AudioObjectStoragePort):
    """Development adapter; each HTTP part is streamed to disk, never buffered."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = (
            root
            or Path(
                os.getenv(
                    "AUDIO_ASSESSMENT_LOCAL_STORAGE_PATH",
                    "./data/audio_assessment",
                )
            )
        ).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return "local"

    @property
    def root(self) -> Path:
        return self._root

    def presign_part(
        self,
        *,
        upload_session_id: str,
        part_number: int,
        object_key: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        expires_seconds: int,
    ) -> PresignedAudioPart:
        del size_bytes
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_seconds)
        return PresignedAudioPart(
            upload_url=(
                "/api/v1/newcomer-training/audio-upload-sessions/"
                f"{quote(upload_session_id, safe='')}/parts/{part_number}/content"
            ),
            object_key=object_key,
            expires_at=expires_at.isoformat(),
            required_headers={
                "Content-Type": content_type,
                "X-Audio-Sha256": sha256,
            },
        )

    async def head(self, object_key: str) -> AudioObjectMetadata:
        path = _safe_local_path(self._root, object_key)
        if not path.is_file():
            raise AudioStorageError(
                "audio_object_not_found",
                "上传分片不存在，请重新上传该分片。",
                retryable=True,
            )
        return AudioObjectMetadata(
            object_key=object_key,
            size_bytes=path.stat().st_size,
            sha256=await asyncio.to_thread(_sha256_file, path),
            content_type=None,
        )

    async def write_part_stream(
        self,
        *,
        object_key: str,
        chunks: AsyncIterator[bytes],
        expected_size_bytes: int,
        expected_sha256: str,
    ) -> AudioObjectMetadata:
        """Atomically persist one local-development part without buffering it."""

        destination = _safe_local_path(self._root, object_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(
            f".{destination.name}.{uuid.uuid4().hex}.uploading"
        )
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with temporary.open("xb") as writer:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size_bytes += len(chunk)
                    if size_bytes > expected_size_bytes:
                        raise AudioStorageError(
                            "audio_upload_part_too_large",
                            "上传分片大小与草稿不一致，请重新上传该分片。",
                            retryable=False,
                        )
                    digest.update(chunk)
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            actual_sha256 = digest.hexdigest()
            if size_bytes != expected_size_bytes or actual_sha256 != expected_sha256:
                raise AudioStorageError(
                    "audio_upload_part_integrity_mismatch",
                    "上传分片与草稿不一致，请重新上传该分片。",
                    retryable=False,
                )
            temporary.replace(destination)
            return AudioObjectMetadata(
                object_key=object_key,
                size_bytes=size_bytes,
                sha256=actual_sha256,
                content_type=None,
            )
        finally:
            temporary.unlink(missing_ok=True)

    async def materialize(
        self, object_keys: tuple[str, ...], destination: Path
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        for object_key in object_keys:
            source = _safe_local_path(self._root, object_key)
            if not source.is_file():
                raise AudioStorageError(
                    "audio_object_not_found",
                    "上传分片不存在，请重新上传该分片。",
                    retryable=True,
                )
            await asyncio.to_thread(_append_file, source, destination)

    async def store_file(
        self,
        *,
        object_key: str,
        source: Path,
        content_type: str,
        sha256: str,
    ) -> StoredAudioObject:
        actual_hash = await asyncio.to_thread(_sha256_file, source)
        if actual_hash != sha256:
            raise AudioStorageError(
                "audio_normalized_hash_mismatch",
                "标准化音频完整性校验失败。",
                retryable=False,
            )
        destination = _safe_local_path(self._root, object_key)
        await asyncio.to_thread(_copy_file, source, destination)
        return StoredAudioObject(
            artifact_ref=f"artifact://audio/local/{object_key}",
            object_key=object_key,
            size_bytes=destination.stat().st_size,
            sha256=actual_hash,
            content_type=content_type,
        )

    def signed_get_url(self, object_key: str, *, expires_seconds: int) -> str:
        del expires_seconds
        return (
            "/api/v1/newcomer-training/audio-artifacts/content/"
            f"{quote(object_key, safe='')}"
        )

    async def delete(self, object_keys: tuple[str, ...]) -> None:
        for object_key in object_keys:
            path = _safe_local_path(self._root, object_key)
            await asyncio.to_thread(path.unlink, missing_ok=True)


class CloudAudioObjectStorage(AudioObjectStoragePort):
    def __init__(self, backend: str) -> None:
        if backend not in {"oss", "cos"}:
            raise ValueError("cloud audio storage backend must be oss or cos")
        self._backend = backend

    @property
    def backend_name(self) -> str:
        return self._backend

    def _signer(self) -> OssSigningService | CosSigningService:
        try:
            return (
                get_oss_signing_service()
                if self._backend == "oss"
                else get_cos_signing_service()
            )
        except (OssConfigError, CosConfigError) as exc:
            raise AudioStorageError(
                "audio_storage_not_configured",
                "对象存储暂不可用，录音草稿仍保留在当前设备。",
                retryable=True,
            ) from exc

    def presign_part(
        self,
        *,
        upload_session_id: str,
        part_number: int,
        object_key: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        expires_seconds: int,
    ) -> PresignedAudioPart:
        del upload_session_id, part_number, size_bytes
        try:
            result = self._signer().generate_put_url(
                object_key,
                content_type=content_type,
                expires=expires_seconds,
                sha256=sha256,
            )
        except AudioStorageError:
            raise
        except Exception as exc:
            raise AudioStorageError(
                "audio_upload_signing_failed",
                "暂时无法创建上传地址，请稍后重试。",
                retryable=True,
            ) from exc
        metadata_header = (
            "x-oss-meta-sha256" if self._backend == "oss" else "x-cos-meta-sha256"
        )
        return PresignedAudioPart(
            upload_url=result.url,
            object_key=result.object_key,
            expires_at=result.expires_at,
            required_headers={
                "Content-Type": content_type,
                metadata_header: sha256,
            },
        )

    async def head(self, object_key: str) -> AudioObjectMetadata:
        try:
            metadata = await asyncio.to_thread(
                self._signer().get_object_metadata,
                object_key,
            )
        except FileNotFoundError as exc:
            raise AudioStorageError(
                "audio_object_not_found",
                "上传分片不存在，请重新上传该分片。",
                retryable=True,
            ) from exc
        except AudioStorageError:
            raise
        except Exception as exc:
            raise AudioStorageError(
                "audio_storage_head_failed",
                "暂时无法校验上传结果，请稍后重试。",
                retryable=True,
            ) from exc
        return AudioObjectMetadata(
            object_key=object_key,
            size_bytes=int(metadata["size_bytes"]),
            sha256=str(metadata.get("sha256") or ""),
            content_type=(
                str(metadata["content_type"]) if metadata.get("content_type") else None
            ),
        )

    async def materialize(
        self, object_keys: tuple[str, ...], destination: Path
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        work_dir = destination.parent / f".{destination.name}.parts"
        work_dir.mkdir(parents=True, exist_ok=True)
        try:
            for index, object_key in enumerate(object_keys, start=1):
                part_path = work_dir / f"part-{index:05d}"
                try:
                    await asyncio.to_thread(
                        self._signer().download_to_file,
                        object_key,
                        part_path,
                    )
                except Exception as exc:
                    raise AudioStorageError(
                        "audio_storage_download_failed",
                        "暂时无法读取已上传录音，请稍后重试。",
                        retryable=True,
                    ) from exc
                await asyncio.to_thread(_append_file, part_path, destination)
        finally:
            await asyncio.to_thread(shutil.rmtree, work_dir, True)

    async def store_file(
        self,
        *,
        object_key: str,
        source: Path,
        content_type: str,
        sha256: str,
    ) -> StoredAudioObject:
        try:
            await asyncio.to_thread(
                self._signer().upload_file,
                object_key,
                source,
                content_type=content_type,
                sha256=sha256,
            )
        except Exception as exc:
            raise AudioStorageError(
                "audio_storage_write_failed",
                "标准化音频暂时无法保存，请稍后重试。",
                retryable=True,
            ) from exc
        return StoredAudioObject(
            artifact_ref=f"artifact://audio/{self._backend}/{object_key}",
            object_key=object_key,
            size_bytes=source.stat().st_size,
            sha256=sha256,
            content_type=content_type,
        )

    def signed_get_url(self, object_key: str, *, expires_seconds: int) -> str:
        try:
            return str(
                self._signer().generate_get_url(
                    object_key,
                    expires=expires_seconds,
                )
            )
        except Exception as exc:
            raise AudioStorageError(
                "audio_download_signing_failed",
                "暂时无法创建试听地址，请稍后重试。",
                retryable=True,
            ) from exc

    async def delete(self, object_keys: tuple[str, ...]) -> None:
        for object_key in object_keys:
            try:
                await asyncio.to_thread(self._signer().delete_object, object_key)
            except Exception as exc:
                raise AudioStorageError(
                    "audio_storage_delete_failed",
                    "暂时无法清理未完成录音。",
                    retryable=True,
                ) from exc


def build_audio_object_storage() -> AudioObjectStoragePort:
    backend = (
        (
            os.getenv("AUDIO_ASSESSMENT_STORAGE_BACKEND")
            or os.getenv("SALES_TRAINER_AUDIO_STORAGE_BACKEND")
            or "local"
        )
        .strip()
        .lower()
    )
    if backend == "local":
        return LocalAudioObjectStorage()
    if backend in {"oss", "cos"}:
        return CloudAudioObjectStorage(backend)
    raise AudioStorageError(
        "audio_storage_backend_invalid",
        "录音存储配置无效，请联系管理员。",
        retryable=False,
    )


__all__ = [
    "AudioStorageError",
    "CloudAudioObjectStorage",
    "LocalAudioObjectStorage",
    "build_audio_object_storage",
]
