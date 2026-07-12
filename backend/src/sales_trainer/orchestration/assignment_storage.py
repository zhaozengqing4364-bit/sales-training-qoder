"""Safe storage boundary for assignment attachments."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from fastapi import UploadFile

from common.cos.signing import CosConfigError, get_cos_signing_service
from sales_trainer.orchestration.errors import NewcomerOrchestrationError

ALLOWED_ASSIGNMENT_MIME_TYPES = frozenset(
    {
        "text/plain",
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
)


@dataclass(frozen=True, slots=True)
class StoredAssignmentFile:
    storage_key: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "storage_key": self.storage_key,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


class AssignmentStorage(Protocol):
    async def store(
        self, *, file: UploadFile, learner_id: str, max_size_bytes: int
    ) -> StoredAssignmentFile: ...


class ConfiguredAssignmentStorage:
    async def store(
        self, *, file: UploadFile, learner_id: str, max_size_bytes: int
    ) -> StoredAssignmentFile:
        content_type = (file.content_type or "application/octet-stream").lower()
        if content_type not in ALLOWED_ASSIGNMENT_MIME_TYPES:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ASSIGNMENT_FILE_TYPE_UNSUPPORTED]",
                "不支持这种附件格式。",
                422,
            )
        body = await file.read()
        if not body or len(body) > max_size_bytes:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ASSIGNMENT_FILE_SIZE_INVALID]",
                "附件为空或超过大小限制。",
                422,
            )
        filename = _safe_filename(file.filename or "attachment")
        object_key = f"newcomer-assignments/{learner_id}/{uuid.uuid4().hex}-{filename}"
        backend = os.getenv("NEWCOMER_ASSIGNMENT_STORAGE_BACKEND", "local").lower()
        if backend == "cos":
            try:
                stored = get_cos_signing_service().upload_object(
                    object_key, body, content_type=content_type
                )
            except CosConfigError as exc:
                raise NewcomerOrchestrationError(
                    "[NEWCOMER_ASSIGNMENT_STORAGE_UNAVAILABLE]",
                    "附件存储暂不可用。",
                    503,
                ) from exc
            storage_key = f"cos://{stored}"
        elif backend == "local":
            root = Path(
                os.getenv("NEWCOMER_ASSIGNMENT_LOCAL_ROOT", "uploads/assignments")
            )
            target = root / object_key.removeprefix("newcomer-assignments/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            storage_key = str(target)
        else:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ASSIGNMENT_STORAGE_BACKEND_INVALID]",
                "附件存储配置无效。",
                503,
            )
        return StoredAssignmentFile(
            storage_key=storage_key,
            filename=filename,
            content_type=content_type,
            size_bytes=len(body),
            sha256=sha256(body).hexdigest(),
        )


def _safe_filename(value: str) -> str:
    name = Path(value).name
    normalized = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name).strip("._")
    return (normalized or "attachment")[:180]


__all__ = [
    "ALLOWED_ASSIGNMENT_MIME_TYPES",
    "AssignmentStorage",
    "ConfiguredAssignmentStorage",
    "StoredAssignmentFile",
]
