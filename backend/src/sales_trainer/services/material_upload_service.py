from __future__ import annotations

import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from common.cos.signing import CosConfigError, get_cos_signing_service
from common.db.models import User
from sales_trainer.models import SalesTrainerMaterial, SalesTrainerMaterialVersion
from sales_trainer.schemas import SalesTrainerMaterialVersionCreate
from sales_trainer.services.material_service import (
    MaterialServiceError,
    SalesTrainerMaterialService,
)
from sales_trainer.services.operation_log_service import OperationLogService

DEFAULT_MAX_MATERIAL_MB: Final = 300
DEFAULT_ALLOWED_MATERIAL_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        "application/msword",
        "application/octet-stream",
        "application/pdf",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "audio/mp4",
        "audio/mpeg",
        "audio/wav",
        "audio/webm",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/markdown",
        "text/plain",
    }
)


@dataclass(frozen=True, slots=True)
class StoredMaterialFile:
    file_name: str
    content_type: str
    size_bytes: int
    storage_key: str
    file_hash: str
    storage_backend: str


class SalesTrainerMaterialUploadService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._materials = SalesTrainerMaterialService(db)
        self._logs = OperationLogService(db)

    async def upload_version_file(
        self,
        material: SalesTrainerMaterial,
        *,
        file: UploadFile,
        version_label: str,
        title: str,
        release_notes: str | None,
        actor: User,
    ) -> SalesTrainerMaterialVersion:
        stored_file = await self._store_upload(file, material_id=material.material_id)
        version = await self._materials.create_version(
            material,
            SalesTrainerMaterialVersionCreate(
                version_label=version_label.strip(),
                title=title.strip(),
                file_name=stored_file.file_name,
                content_type=stored_file.content_type,
                file_size_bytes=stored_file.size_bytes,
                storage_key=stored_file.storage_key,
                file_hash=stored_file.file_hash,
                release_notes=release_notes.strip() if release_notes else None,
            ),
            actor=actor,
        )
        await self._logs.record(
            actor=actor,
            action="material_version_uploaded",
            target_type="sales_trainer_material_version",
            target_id=version.version_id,
            metadata={
                "material_id": material.material_id,
                "version_label": version.version_label,
                "file_name": stored_file.file_name,
                "content_type": stored_file.content_type,
                "file_size_bytes": stored_file.size_bytes,
                "file_hash": stored_file.file_hash,
                "storage_backend": stored_file.storage_backend,
            },
        )
        await self._db.commit()
        await self._db.refresh(version)
        return version

    async def _store_upload(
        self,
        file: UploadFile,
        *,
        material_id: str,
    ) -> StoredMaterialFile:
        file_name = _safe_file_name(file.filename or "training-material")
        content_type = _resolve_content_type(file_name, file.content_type)
        _validate_content_type(content_type)
        raw = await file.read()
        if not raw:
            raise MaterialServiceError(
                "[MATERIAL_FILE_EMPTY]",
                "上传材料文件不能为空。",
                status_code=422,
            )
        _validate_file_size(len(raw))
        file_hash = sha256(raw).hexdigest()
        storage_backend = os.getenv("SALES_TRAINER_MATERIAL_STORAGE_BACKEND", "local")
        storage_backend = storage_backend.strip().lower()
        if storage_backend == "cos":
            storage_key = _store_cos_file(
                material_id=material_id,
                file_name=file_name,
                content_type=content_type,
                raw=raw,
            )
            return StoredMaterialFile(
                file_name=file_name,
                content_type=content_type,
                size_bytes=len(raw),
                storage_key=storage_key,
                file_hash=file_hash,
                storage_backend="cos",
            )
        if storage_backend != "local":
            raise MaterialServiceError(
                "[MATERIAL_UPLOAD_BACKEND_UNSUPPORTED]",
                "当前材料上传接口仅支持本地存储或 COS；其他对象存储请先使用文件地址登记版本。",
                status_code=503,
            )
        storage_key = _store_local_file(
            material_id=material_id,
            file_name=file_name,
            raw=raw,
        )
        return StoredMaterialFile(
            file_name=file_name,
            content_type=content_type,
            size_bytes=len(raw),
            storage_key=storage_key,
            file_hash=file_hash,
            storage_backend="local",
        )


def _safe_file_name(filename: str) -> str:
    value = Path(filename).name.strip()
    return value or "training-material"


def _resolve_content_type(filename: str, upload_content_type: str | None) -> str:
    guessed_type = mimetypes.guess_type(filename)[0]
    if upload_content_type and upload_content_type != "application/octet-stream":
        return upload_content_type
    return guessed_type or upload_content_type or "application/octet-stream"


def _validate_content_type(content_type: str) -> None:
    allowed = {
        item.strip()
        for item in os.getenv(
            "SALES_TRAINER_MATERIAL_ALLOWED_MIME_TYPES",
            ",".join(sorted(DEFAULT_ALLOWED_MATERIAL_MIME_TYPES)),
        ).split(",")
        if item.strip()
    }
    if content_type not in allowed:
        raise MaterialServiceError(
            "[MATERIAL_FILE_TYPE_NOT_ALLOWED]",
            "不支持的材料文件格式。",
            status_code=422,
        )


def _validate_file_size(size_bytes: int) -> None:
    raw_max_mb = os.getenv(
        "SALES_TRAINER_MATERIAL_MAX_FILE_SIZE_MB",
        str(DEFAULT_MAX_MATERIAL_MB),
    )
    try:
        max_mb = int(raw_max_mb)
    except ValueError as exc:
        raise MaterialServiceError(
            "[MATERIAL_SIZE_CONFIG_INVALID]",
            "材料文件大小上限配置非法。",
            status_code=500,
        ) from exc
    if max_mb <= 0:
        raise MaterialServiceError(
            "[MATERIAL_SIZE_CONFIG_INVALID]",
            "材料文件大小上限配置非法。",
            status_code=500,
        )
    if size_bytes > max_mb * 1024 * 1024:
        raise MaterialServiceError(
            "[MATERIAL_FILE_TOO_LARGE]",
            "材料文件超过配置大小上限。",
            status_code=413,
        )


def _store_local_file(
    *,
    material_id: str,
    file_name: str,
    raw: bytes,
) -> str:
    base = Path(
        os.getenv("SALES_TRAINER_MATERIAL_STORAGE_PATH", "./data/sales_trainer_materials")
    ).resolve()
    storage_path = base / material_id / f"{uuid.uuid4().hex}{_safe_extension(file_name)}"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        storage_path.write_bytes(raw)
    except OSError as exc:
        raise MaterialServiceError(
            "[MATERIAL_UPLOAD_FAILED]",
            "材料文件保存失败。",
            status_code=500,
        ) from exc
    return str(storage_path)


def _store_cos_file(
    *,
    material_id: str,
    file_name: str,
    content_type: str,
    raw: bytes,
) -> str:
    object_key = (
        f"sales-trainer/materials/{material_id}/"
        f"{uuid.uuid4().hex}{_safe_extension(file_name)}"
    )
    try:
        stored_key = get_cos_signing_service().upload_object(
            object_key,
            raw,
            content_type=content_type,
        )
    except CosConfigError as exc:
        raise MaterialServiceError("[COS_NOT_CONFIGURED]", str(exc), status_code=503) from exc
    return f"cos://{stored_key}"


def _safe_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if re.fullmatch(r"\.[a-z0-9]{1,12}", suffix or ""):
        return suffix
    return ".bin"
