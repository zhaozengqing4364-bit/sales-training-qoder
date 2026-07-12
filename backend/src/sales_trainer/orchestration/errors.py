"""Typed errors emitted by newcomer-training orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sales_trainer.orchestration.graph import PathIssue


class NewcomerOrchestrationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PathValidationError(NewcomerOrchestrationError):
    def __init__(self, issues: Sequence[PathIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "[NEWCOMER_PATH_VALIDATION_FAILED]",
            "训练路径还有需要处理的配置问题。",
            422,
        )


class PathRevisionConflictError(NewcomerOrchestrationError):
    def __init__(self) -> None:
        super().__init__(
            "[NEWCOMER_PATH_REVISION_CONFLICT]",
            "训练路径已被其他人更新，请保留当前内容并重新载入最新版本后再保存。",
            409,
        )
