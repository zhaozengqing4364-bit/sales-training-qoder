from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from curriculum_practice.schema_types import (
    QuestionDifficulty,
    QuestionLifecycleStatus,
    TestBankImportStatus,
)


class QuestionCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=160)
    parent_id: str | None = Field(None, min_length=1, max_length=36)
    description: str | None = Field(None, max_length=2000)
    usage_scope: str = Field("general", min_length=1, max_length=50)
    order_index: int = Field(1, ge=1)


class QuestionCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=160)
    parent_id: str | None = Field(None, min_length=1, max_length=36)
    description: str | None = Field(None, max_length=2000)
    usage_scope: str | None = Field(None, min_length=1, max_length=50)
    order_index: int | None = Field(None, ge=1)


class QuestionCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: str
    parent_id: str | None = None
    name: str
    description: str | None = None
    usage_scope: str = "general"
    order_index: int
    created_at: object
    updated_at: object


class QuestionCategoryListResponse(BaseModel):
    items: list[QuestionCategoryResponse]
    total: int


class QuestionItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(..., min_length=1, max_length=36)
    title: str = Field(..., min_length=1, max_length=200)
    stem: str = Field(..., min_length=1)
    reference_answer: str | None = Field(None, max_length=8000)
    scoring_criteria: dict[str, object] = Field(default_factory=dict)
    scoring_dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    usage_scope: str = Field("general", min_length=1, max_length=50)
    difficulty: QuestionDifficulty = "medium"
    safety_flagged: bool = False
    department: str | None = Field(None, min_length=1, max_length=120)


class QuestionItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str | None = Field(None, min_length=1, max_length=36)
    title: str | None = Field(None, min_length=1, max_length=200)
    stem: str | None = Field(None, min_length=1)
    reference_answer: str | None = Field(None, max_length=8000)
    scoring_criteria: dict[str, object] | None = None
    scoring_dimensions: list[str] | None = None
    tags: list[str] | None = None
    usage_scope: str | None = Field(None, min_length=1, max_length=50)
    difficulty: QuestionDifficulty | None = None
    safety_flagged: bool | None = None
    department: str | None = Field(None, min_length=1, max_length=120)


class QuestionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: str
    category_id: str
    title: str
    stem: str
    reference_answer: str | None = None
    scoring_criteria: dict[str, object]
    scoring_dimensions: list[str]
    tags: list[str]
    usage_scope: str = "general"
    difficulty: QuestionDifficulty
    status: QuestionLifecycleStatus
    safety_flagged: bool
    department: str | None = None
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object


class QuestionItemListResponse(BaseModel):
    items: list[QuestionItemResponse]
    total: int


class QuestionGenerationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_content_id: str = Field(..., min_length=1, max_length=36)
    chapter_id: str = Field(..., min_length=1, max_length=36)


class QuestionGenerationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    stem: str = Field(..., min_length=1)
    reference_answer: str = Field(..., min_length=1, max_length=8000)
    scoring_criteria: dict[str, object]
    scoring_dimensions: list[str] = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    difficulty: QuestionDifficulty = "medium"
    source_learning_content_id: str = Field(..., min_length=1, max_length=36)
    source_chapter_id: str = Field(..., min_length=1, max_length=36)


class QuestionGenerationPreviewResponse(BaseModel):
    drafts: list[QuestionGenerationDraft]


class QuestionGenerationConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(..., min_length=1, max_length=36)
    drafts: list[QuestionGenerationDraft] = Field(..., min_length=1, max_length=5)


class QuestionGenerationConfirmResponse(BaseModel):
    items: list[QuestionItemResponse]
    total: int


class TestBankImportErrorResponse(BaseModel):
    row: int
    field: str
    message: str


class TestBankImportResultResponse(BaseModel):
    imported: int
    failed: int
    errors: list[TestBankImportErrorResponse]


class TestBankImportJobResponse(BaseModel):
    task_id: str
    status: TestBankImportStatus
    result: TestBankImportResultResponse
