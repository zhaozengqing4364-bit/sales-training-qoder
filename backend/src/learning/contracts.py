"""Closed contracts for source, curated content, and question production."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LearningActor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    capabilities: frozenset[str] = Field(default_factory=frozenset)
    trace_id: str | None = Field(default=None, max_length=160)


class PageLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["page"] = "page"
    page: int = Field(ge=1)
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> PageLocator:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return self


class TimeRangeLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["time_range"] = "time_range"
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> TimeRangeLocator:
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class ParagraphLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["paragraph"] = "paragraph"
    paragraph_id: str = Field(min_length=1, max_length=160)
    start_offset: int = Field(default=0, ge=0)
    end_offset: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_offsets(self) -> ParagraphLocator:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return self


SourceLocator = Annotated[
    PageLocator | TimeRangeLocator | ParagraphLocator,
    Field(discriminator="type"),
]


class SourceAnchorDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    anchor_key: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=240)
    locator: SourceLocator
    excerpt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class SourceDocumentRevisionDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_label: str = Field(min_length=1, max_length=120)
    source_type: Literal["file", "url", "manual"]
    content_kind: Literal[
        "document",
        "slide_deck",
        "demo_video",
        "external_demo",
        "script",
        "example_audio",
        "attachment",
    ] = "document"
    source_uri: str = Field(min_length=1, max_length=1_000)
    file_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parser_version: str = Field(min_length=1, max_length=120)
    parse_status: Literal["pending", "ready", "failed"]
    original_filename: str | None = Field(default=None, max_length=255)
    trusted_mime_type: str | None = Field(default=None, max_length=160)
    file_extension: str | None = Field(
        default=None,
        max_length=16,
        pattern=r"^[a-z0-9]+$",
    )
    file_size_bytes: int | None = Field(default=None, ge=0)
    language: str | None = Field(default=None, max_length=32)
    page_count: int | None = Field(default=None, ge=1)
    duration_ms: int | None = Field(default=None, ge=1)
    preview_version: str | None = Field(default=None, max_length=120)
    processing_state: Literal[
        "pending",
        "processing",
        "partial",
        "ready",
        "failed",
        "cancelled",
    ]
    processing_stage: str | None = Field(default=None, max_length=120)
    failure_code: str | None = Field(default=None, max_length=120)
    failure_message: str | None = Field(default=None, max_length=500)
    manual_content: str | None = Field(default=None, max_length=100_000)

    @model_validator(mode="before")
    @classmethod
    def backfill_multimedia_contract(cls, value: Any) -> Any:
        """Keep snapshots created before the multimedia contract readable."""

        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        parse_status = str(normalized.get("parse_status") or "pending")
        if "content_kind" not in normalized and normalized.get("source_type") == "url":
            # Historical URL revisions predate the explicit multimedia kind. They
            # represented externally hosted demonstrations, so preserve that
            # meaning instead of making old snapshots unreadable.
            normalized["content_kind"] = "external_demo"
        legacy_processing_contract = "processing_state" not in normalized
        normalized.setdefault(
            "processing_state",
            {"ready": "ready", "failed": "failed"}.get(parse_status, "pending"),
        )
        if legacy_processing_contract and parse_status == "failed":
            normalized.setdefault("failure_code", "legacy_parse_failed")
            normalized.setdefault(
                "failure_message",
                "历史材料解析未完成，可重新提交处理。",
            )
        return normalized

    @model_validator(mode="after")
    def validate_controlled_source(self) -> SourceDocumentRevisionDraft:
        if self.source_type == "file" and not self.source_uri.startswith(
            "artifact://"
        ):
            raise ValueError("file sources require a controlled artifact ref")
        if self.source_type == "url":
            if not self.source_uri.startswith("https://"):
                raise ValueError("external sources require an https URL")
            if self.content_kind != "external_demo":
                raise ValueError("url sources must use external_demo content_kind")
        if self.source_type == "manual" and self.content_kind not in {
            "script",
            "document",
        }:
            raise ValueError("manual sources must be a script or managed document")
        if (
            self.source_type == "manual"
            and self.content_kind == "script"
            and not (self.manual_content or "").strip()
        ):
            raise ValueError("manual script sources require manual_content")
        if self.source_type != "manual" and self.manual_content is not None:
            raise ValueError("only manual sources may carry manual_content")
        expected_parse_status = {
            "pending": "pending",
            "processing": "pending",
            "ready": "ready",
            "partial": "failed",
            "failed": "failed",
            "cancelled": "failed",
        }[self.processing_state]
        if self.parse_status != expected_parse_status:
            raise ValueError("parse_status and processing_state are inconsistent")
        if self.processing_state in {"failed", "partial"} and not self.failure_code:
            raise ValueError("failed or partial processing requires failure_code")
        if self.processing_state == "ready" and self.failure_code is not None:
            raise ValueError("ready processing cannot carry a failure_code")
        return self


class LearningConceptDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    concept_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=20_000)
    source_anchor_ids: tuple[str, ...] = Field(min_length=1, max_length=50)


class LearningExampleDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    example_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=20_000)
    source_anchor_ids: tuple[str, ...] = Field(min_length=1, max_length=50)


class LearningCheckpointDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    checkpoint_id: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=2_000)
    required: bool = True


class LearningContentBlockBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    block_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2_000)
    order: int = Field(ge=0, le=10_000)
    accessibility_alt: str = Field(min_length=1, max_length=500)


class SourceBackedContentBlock(LearningContentBlockBase):
    source_revision_id: str = Field(min_length=1, max_length=160)
    source_anchor_id: str = Field(min_length=1, max_length=160)


class RichTextContentBlock(SourceBackedContentBlock):
    type: Literal["rich_text"] = "rich_text"
    markdown: str = Field(min_length=1, max_length=50_000)


class SourceExcerptContentBlock(SourceBackedContentBlock):
    type: Literal["source_excerpt"] = "source_excerpt"
    excerpt: str = Field(min_length=1, max_length=30_000)


class SlideDeckContentBlock(SourceBackedContentBlock):
    type: Literal["slide_deck"] = "slide_deck"
    start_page: int = Field(default=1, ge=1)
    end_page: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_page_range(self) -> SlideDeckContentBlock:
        if self.end_page is not None and self.end_page < self.start_page:
            raise ValueError("end_page must be >= start_page")
        return self


class VideoContentBlock(SourceBackedContentBlock):
    type: Literal["video"] = "video"
    start_ms: int = Field(default=0, ge=0)
    end_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_time_range(self) -> VideoContentBlock:
        if self.end_ms is not None and self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class AudioExampleContentBlock(SourceBackedContentBlock):
    type: Literal["audio_example"] = "audio_example"
    start_ms: int = Field(default=0, ge=0)
    end_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_time_range(self) -> AudioExampleContentBlock:
        if self.end_ms is not None and self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class AttachmentContentBlock(SourceBackedContentBlock):
    type: Literal["attachment"] = "attachment"
    download_label: str = Field(min_length=1, max_length=120)


class CheckpointContentBlock(LearningContentBlockBase):
    type: Literal["checkpoint"] = "checkpoint"
    prompt: str = Field(min_length=1, max_length=2_000)
    required: bool = True


LearningContentBlock = Annotated[
    RichTextContentBlock
    | SourceExcerptContentBlock
    | SlideDeckContentBlock
    | VideoContentBlock
    | AudioExampleContentBlock
    | AttachmentContentBlock
    | CheckpointContentBlock,
    Field(discriminator="type"),
]


class LearningUnitRevisionDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_label: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    objectives: tuple[str, ...] = Field(min_length=1, max_length=30)
    key_concepts: tuple[LearningConceptDraft, ...] = Field(
        default_factory=tuple, max_length=100
    )
    examples: tuple[LearningExampleDraft, ...] = Field(default_factory=tuple)
    checkpoints: tuple[LearningCheckpointDraft, ...] = Field(
        default_factory=tuple, max_length=100
    )
    practice_hints: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    content_blocks: tuple[LearningContentBlock, ...] = Field(
        default_factory=tuple,
        max_length=300,
    )

    @model_validator(mode="after")
    def validate_stable_ids(self) -> LearningUnitRevisionDraft:
        if not self.key_concepts and not self.content_blocks:
            raise ValueError("learning unit requires legacy concepts or content_blocks")
        checkpoint_blocks = tuple(
            item for item in self.content_blocks if item.type == "checkpoint"
        )
        if not self.checkpoints and not checkpoint_blocks:
            raise ValueError("learning unit requires at least one checkpoint")
        for values, label in (
            (self.key_concepts, "concept_id"),
            (self.examples, "example_id"),
            (self.checkpoints, "checkpoint_id"),
        ):
            ids = [str(getattr(item, label)) for item in values]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{label} must be unique")
        block_ids = [item.block_id for item in self.content_blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("block_id must be unique")
        block_orders = [item.order for item in self.content_blocks]
        if len(block_orders) != len(set(block_orders)):
            raise ValueError("content block order must be unique")
        legacy_checkpoint_ids = {item.checkpoint_id for item in self.checkpoints}
        block_checkpoint_ids = {
            item.block_id
            for item in checkpoint_blocks
        }
        if legacy_checkpoint_ids & block_checkpoint_ids:
            raise ValueError(
                "legacy checkpoint_id and checkpoint content block id cannot overlap"
            )
        return self

    def source_anchor_ids(self) -> tuple[str, ...]:
        anchor_ids = [
            anchor_id
            for item in self.key_concepts
            for anchor_id in item.source_anchor_ids
        ]
        anchor_ids.extend(
            anchor_id
            for item in self.examples
            for anchor_id in item.source_anchor_ids
        )
        anchor_ids.extend(
            item.source_anchor_id
            for item in self.content_blocks
            if isinstance(item, SourceBackedContentBlock)
        )
        return tuple(dict.fromkeys(anchor_ids))

    def source_revision_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                item.source_revision_id
                for item in self.content_blocks
                if isinstance(item, SourceBackedContentBlock)
            )
        )

    def exact_source_references(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (item.source_revision_id, item.source_anchor_id)
            for item in self.content_blocks
            if isinstance(item, SourceBackedContentBlock)
        )

    def checkpoint_contracts(self) -> tuple[LearningCheckpointDraft, ...]:
        block_checkpoints = tuple(
            LearningCheckpointDraft(
                checkpoint_id=item.block_id,
                prompt=item.prompt,
                required=item.required,
            )
            for item in self.content_blocks
            if isinstance(item, CheckpointContentBlock)
        )
        return self.checkpoints + block_checkpoints


class QuestionGenerationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_revision_id: str = Field(min_length=1, max_length=160)
    learning_unit_revision_id: str = Field(min_length=1, max_length=160)
    requested_count: int = Field(ge=1, le=100)
    prompt_template_id: str = Field(min_length=1, max_length=160)
    prompt_revision_id: str = Field(min_length=1, max_length=160)
    prompt_contract_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    model_routing_profile_id: str = Field(min_length=1, max_length=160)
    model_routing_revision_id: str = Field(min_length=1, max_length=160)
    input_schema_version: Literal["question-generation-input-v1"]
    output_schema_version: Literal["question-generation-output-v1"]


class QuestionOption(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    option_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=2_000)
    is_correct: bool


class QuestionCandidateContent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_type: Literal[
        "single_choice", "multiple_choice", "true_false", "short_answer"
    ]
    stem: str = Field(min_length=8, max_length=5_000)
    options: tuple[QuestionOption, ...] = Field(default_factory=tuple, max_length=20)
    reference_answer: str | None = Field(default=None, max_length=10_000)
    rubric: dict[str, object] | None = None
    explanation: str = Field(min_length=5, max_length=10_000)
    difficulty: Literal["easy", "medium", "hard"]
    competency_keys: tuple[str, ...] = Field(min_length=1, max_length=20)
    source_anchor_ids: tuple[str, ...] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_answer_contract(self) -> QuestionCandidateContent:
        option_ids = [item.option_id for item in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("option_id must be unique")
        correct_count = sum(item.is_correct for item in self.options)
        if self.question_type == "single_choice":
            if len(self.options) < 2 or correct_count != 1:
                raise ValueError("single_choice requires exactly one correct option")
        elif self.question_type == "multiple_choice":
            if len(self.options) < 2 or correct_count < 1:
                raise ValueError("multiple_choice requires correct options")
        elif self.question_type == "true_false":
            if len(self.options) != 2 or correct_count != 1:
                raise ValueError("true_false requires two options and one answer")
        elif not self.reference_answer or not self.rubric:
            raise ValueError("short_answer requires reference_answer and rubric")
        if self.question_type != "short_answer" and (
            self.reference_answer is not None or self.rubric is not None
        ):
            raise ValueError("objective questions cannot carry short-answer keys")
        return self


class QuestionGenerationOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    questions: tuple[QuestionCandidateContent, ...] = Field(min_length=1, max_length=100)


class QuizQuestionBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_revision_id: str = Field(min_length=1, max_length=160)
    points: float = Field(gt=0, le=100)


class ShortAnswerScoringPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_template_id: str = Field(min_length=1, max_length=160)
    prompt_revision_id: str = Field(min_length=1, max_length=160)
    prompt_contract_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    model_routing_profile_id: str = Field(min_length=1, max_length=160)
    model_routing_revision_id: str = Field(min_length=1, max_length=160)
    input_schema_version: Literal["short-answer-input-v1"]
    output_schema_version: Literal["short-answer-output-v1"]


class QuizRevisionDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_label: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    questions: tuple[QuizQuestionBinding, ...] = Field(min_length=1, max_length=200)
    pass_threshold: float = Field(ge=0, le=100)
    max_attempts: int = Field(ge=1, le=100)
    retry_interval_seconds: int = Field(ge=0, le=604_800)
    feedback_policy: Literal["none", "after_submit", "after_pass"]
    time_limit_minutes: int | None = Field(default=None, ge=1, le=1_440)
    shuffle_questions: bool = False
    shuffle_options: bool = False
    short_answer_scoring: ShortAnswerScoringPolicy | None = None

    @model_validator(mode="after")
    def validate_attempt_and_question_rules(self) -> QuizRevisionDraft:
        revision_ids = [item.question_revision_id for item in self.questions]
        if len(revision_ids) != len(set(revision_ids)):
            raise ValueError("question_revision_id must be unique")
        if self.max_attempts > 1 and self.retry_interval_seconds < 1:
            raise ValueError("retry_interval_seconds is required when retries are enabled")
        return self


__all__ = [
    "LearningActor",
    "LearningUnitRevisionDraft",
    "QuestionCandidateContent",
    "QuestionGenerationOutput",
    "QuestionGenerationRequest",
    "QuizRevisionDraft",
    "SourceAnchorDraft",
    "SourceDocumentRevisionDraft",
]
