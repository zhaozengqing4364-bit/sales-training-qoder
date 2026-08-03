"""Learner-safe Lesson and Quiz workspace projections."""

from __future__ import annotations

from typing import Any, Never
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning.content_access import (
    LearnerSourceAssetGrant,
    issue_learner_source_asset_grant,
)
from learning.contracts import LearningUnitRevisionDraft, QuizRevisionDraft
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningLessonAttempt,
    LearningQuizAttempt,
    LearningQuizRevision,
    LearningSourceAnchor,
    LearningSourceDocumentRevision,
    LearningUnitRevision,
)


class LearningWorkspaceProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detail_id: str | None
    status: str
    version: int
    task_id: str | None
    runner: dict[str, Any]
    available_commands: tuple[str, ...]


class LearningWorkspaceQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        *,
        organization_id: str,
        learner_id: str,
        activity_type: str,
        revision_id: str,
        attempt_id: str | None,
        activity_id: str | None = None,
    ) -> LearningWorkspaceProjection:
        if activity_type == "lesson":
            return await self._lesson(
                organization_id=organization_id,
                learner_id=learner_id,
                revision_id=revision_id,
                attempt_id=attempt_id,
                activity_id=activity_id,
            )
        if activity_type == "quiz":
            return await self._quiz(
                organization_id=organization_id,
                learner_id=learner_id,
                revision_id=revision_id,
                attempt_id=attempt_id,
            )
        raise LearningGovernanceError(
            "[LEARNING_ACTIVITY_TYPE_UNSUPPORTED]",
            "当前训练活动尚未配置可用的学习运行器。",
            503,
        )

    async def _lesson(
        self,
        *,
        organization_id: str,
        learner_id: str,
        revision_id: str,
        attempt_id: str | None,
        activity_id: str | None,
    ) -> LearningWorkspaceProjection:
        revision = await self._session.get(LearningUnitRevision, revision_id)
        if (
            revision is None
            or revision.organization_id != organization_id
            or revision.status not in {"published", "archived"}
        ):
            self._resource_not_found()
        draft = LearningUnitRevisionDraft.model_validate(revision.snapshot_json)
        anchors = (
            await self._session.execute(
                select(LearningSourceAnchor)
                .where(LearningSourceAnchor.organization_id == organization_id)
                .where(
                    LearningSourceAnchor.anchor_id.in_(
                        revision.source_anchor_ids_json
                    )
                )
            )
        ).scalars().all()
        source_labels = {item.anchor_id: item.label for item in anchors}
        source_revision_ids = draft.source_revision_ids()
        source_revisions = (
            await self._session.execute(
                select(LearningSourceDocumentRevision)
                .where(
                    LearningSourceDocumentRevision.organization_id
                    == organization_id
                )
                .where(
                    LearningSourceDocumentRevision.revision_id.in_(
                        source_revision_ids
                    )
                )
            )
        ).scalars().all()
        sources_by_id = {item.revision_id: item for item in source_revisions}
        detail = await self._lesson_detail(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
        )
        if detail is not None and detail.learning_unit_revision_id != revision_id:
            self._attempt_not_found()
        status = detail.status if detail is not None else "not_started"
        commands = {
            "not_started": ("start",),
            "in_progress": ("save_progress", "complete"),
            "completed": ("review",),
            "invalidated": ("start_relearn",),
        }.get(status, ())
        runner = {
            "kind": "lesson",
            "title": draft.title,
            "objectives": list(draft.objectives),
            "key_concepts": [
                {
                    "concept_id": item.concept_id,
                    "title": item.title,
                    "content": item.content,
                    "sources": [
                        source_labels[anchor_id]
                        for anchor_id in item.source_anchor_ids
                        if anchor_id in source_labels
                    ],
                }
                for item in draft.key_concepts
            ],
            "examples": [
                {
                    "example_id": item.example_id,
                    "title": item.title,
                    "content": item.content,
                    "sources": [
                        source_labels[anchor_id]
                        for anchor_id in item.source_anchor_ids
                        if anchor_id in source_labels
                    ],
                }
                for item in draft.examples
            ],
            "checkpoints": [
                {
                    "checkpoint_id": item.checkpoint_id,
                    "prompt": item.prompt,
                    "required": item.required,
                }
                for item in draft.checkpoint_contracts()
            ],
            "content_blocks": [
                self._public_content_block(
                    block=item,
                    organization_id=organization_id,
                    activity_id=activity_id,
                    source_labels=source_labels,
                    sources_by_id=sources_by_id,
                )
                for item in sorted(draft.content_blocks, key=lambda block: block.order)
            ],
            "practice_hints": list(draft.practice_hints),
            "progress": (
                None
                if detail is None
                else {
                    "completed_checkpoint_ids": list(
                        detail.completed_checkpoint_ids_json
                    ),
                    "reading_position": dict(detail.reading_position_json),
                    "last_saved_at": detail.last_saved_at,
                }
            ),
        }
        return LearningWorkspaceProjection(
            detail_id=detail.detail_id if detail is not None else None,
            status=status,
            version=detail.version if detail is not None else 0,
            task_id=None,
            runner=runner,
            available_commands=commands,
        )

    @staticmethod
    def _public_content_block(
        *,
        block: Any,
        organization_id: str,
        activity_id: str | None,
        source_labels: dict[str, str],
        sources_by_id: dict[str, LearningSourceDocumentRevision],
    ) -> dict[str, Any]:
        public: dict[str, Any] = {
            "type": block.type,
            "block_id": block.block_id,
            "title": block.title,
            "description": block.description,
            "order": block.order,
            "accessibility_alt": block.accessibility_alt,
        }
        if block.type == "checkpoint":
            public.update({"prompt": block.prompt, "required": block.required})
            return public
        source = sources_by_id.get(block.source_revision_id)
        public["source_label"] = source_labels.get(
            block.source_anchor_id,
            "训练材料",
        )
        if block.type == "rich_text":
            public["markdown"] = block.markdown
        elif block.type == "source_excerpt":
            public["excerpt"] = block.excerpt
        elif block.type == "slide_deck":
            public.update(
                {
                    "start_page": block.start_page,
                    "end_page": block.end_page,
                    "page_count": source.page_count if source is not None else None,
                }
            )
        elif block.type in {"video", "audio_example"}:
            public.update(
                {
                    "start_ms": block.start_ms,
                    "end_ms": block.end_ms,
                    "duration_ms": source.duration_ms if source is not None else None,
                }
            )
        elif block.type == "attachment":
            public.update(
                {
                    "download_label": block.download_label,
                    "filename": source.original_filename if source is not None else None,
                    "file_size_bytes": source.file_size_bytes if source is not None else None,
                }
            )
        if source is None or source.status not in {"published", "archived"}:
            public["availability"] = "unavailable"
            return public
        if source.source_type == "url":
            if (
                source.content_kind != "external_demo"
                or not source.source_uri.startswith("https://")
            ):
                public["availability"] = "unavailable"
                return public
            public.update(
                {
                    "availability": "external",
                    "external_url": source.source_uri,
                    "embed_allowed": False,
                }
            )
            return public
        if source.processing_state != "ready":
            public["availability"] = "unavailable"
            return public
        if activity_id is None:
            public["availability"] = "unavailable"
            return public
        token = issue_learner_source_asset_grant(
            LearnerSourceAssetGrant(
                organization_id=organization_id,
                activity_id=activity_id,
                block_id=block.block_id,
                source_revision_id=source.revision_id,
            )
        )
        base = (
            "/api/v1/newcomer-training/activities/"
            f"{quote(activity_id, safe='')}/assets/{quote(token, safe='')}"
        )
        access: dict[str, str] = {}
        if block.type == "slide_deck":
            access["preview_page_template"] = f"{base}/preview/pages/{{page}}"
            access["download"] = f"{base}/download"
        elif block.type in {"video", "audio_example"}:
            access["playback"] = f"{base}/playback"
        elif block.type == "attachment":
            access["download"] = f"{base}/download"
        public.update({"availability": "ready", "access": access})
        return public

    async def _quiz(
        self,
        *,
        organization_id: str,
        learner_id: str,
        revision_id: str,
        attempt_id: str | None,
    ) -> LearningWorkspaceProjection:
        revision = await self._session.get(LearningQuizRevision, revision_id)
        if (
            revision is None
            or revision.organization_id != organization_id
            or revision.status not in {"published", "archived"}
        ):
            self._resource_not_found()
        draft = QuizRevisionDraft.model_validate(revision.snapshot_json)
        detail = await self._quiz_detail(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
        )
        if detail is not None and detail.quiz_revision_id != revision_id:
            self._attempt_not_found()
        status = detail.status if detail is not None else "not_started"
        commands = {
            "not_started": ("start",),
            "in_progress": ("save_answers", "submit"),
            "scoring_pending": (),
            "needs_review": (),
            "scored": ("review_result",),
            "invalidated": ("start",),
        }.get(status, ())
        questions = []
        answers: list[dict[str, Any]] = []
        if detail is not None:
            questions = [self._public_question(item) for item in detail.question_snapshot_json]
            answers = [dict(item) for item in detail.answers_json]
        runner = {
            "kind": "quiz",
            "title": draft.title,
            "question_count": len(draft.questions),
            "rules": {
                "pass_threshold": draft.pass_threshold,
                "max_attempts": draft.max_attempts,
                "retry_interval_seconds": draft.retry_interval_seconds,
                "feedback_policy": draft.feedback_policy,
                "time_limit_minutes": draft.time_limit_minutes,
            },
            "questions": questions,
            "answers": answers,
            "result": (
                None
                if detail is None or detail.status != "scored"
                else {
                    "score": float(detail.score) if detail.score is not None else None,
                    "max_score": float(detail.max_score),
                    "passed": detail.passed,
                }
            ),
        }
        return LearningWorkspaceProjection(
            detail_id=detail.detail_id if detail is not None else None,
            status=status,
            version=detail.version if detail is not None else 0,
            task_id=detail.task_id if detail is not None else None,
            runner=runner,
            available_commands=commands,
        )

    async def _lesson_detail(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str | None,
    ) -> LearningLessonAttempt | None:
        if attempt_id is None:
            return None
        row = await self._session.scalar(
            select(LearningLessonAttempt)
            .where(LearningLessonAttempt.attempt_id == attempt_id)
            .limit(1)
        )
        if (
            row is None
            or row.organization_id != organization_id
            or row.learner_id != learner_id
        ):
            self._attempt_not_found()
        return row

    async def _quiz_detail(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str | None,
    ) -> LearningQuizAttempt | None:
        if attempt_id is None:
            return None
        row = await self._session.scalar(
            select(LearningQuizAttempt)
            .where(LearningQuizAttempt.attempt_id == attempt_id)
            .limit(1)
        )
        if (
            row is None
            or row.organization_id != organization_id
            or row.learner_id != learner_id
        ):
            self._attempt_not_found()
        return row

    @staticmethod
    def _public_question(question: dict[str, Any]) -> dict[str, Any]:
        return {
            "question_revision_id": question["question_revision_id"],
            "question_type": question["question_type"],
            "stem": question["stem"],
            "options": [
                {"option_id": item["option_id"], "text": item["text"]}
                for item in question.get("options", [])
            ],
            "points": question["points"],
        }

    @staticmethod
    def _resource_not_found() -> Never:
        raise LearningGovernanceError(
            "[LEARNING_RESOURCE_NOT_FOUND]",
            "学习资源不存在或不可访问。",
            404,
        )

    @staticmethod
    def _attempt_not_found() -> Never:
        raise LearningGovernanceError(
            "[LEARNING_ATTEMPT_NOT_FOUND]",
            "学习记录不存在或不可访问。",
            404,
        )


__all__ = ["LearningWorkspaceProjection", "LearningWorkspaceQueryService"]
