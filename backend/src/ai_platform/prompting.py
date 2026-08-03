"""Immutable prompt revision resolution and the shared strict compiler."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_platform.contracts import AIErrorClassification
from ai_platform.errors import AIPlatformError, PromptRevisionNotPublishedError
from prompt_templates.renderer import get_renderer, render_template


def compute_prompt_revision_content_hash(
    *,
    template_id: str,
    business_purpose: str,
    revision_id: str,
    revision_no: int,
    template: str,
    variables: tuple[str, ...],
    input_schema_version: str,
    output_schema_version: str,
) -> str:
    canonical = {
        "template_id": template_id,
        "business_purpose": business_purpose,
        "revision_id": revision_id,
        "revision_no": revision_no,
        "template": template,
        "variables": sorted(variables),
        "input_schema_version": input_schema_version,
        "output_schema_version": output_schema_version,
    }
    digest = hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


class PublishedPromptRevisionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    template_id: str = Field(min_length=1)
    business_purpose: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    revision_no: int = Field(ge=1)
    status: Literal["published"]
    template: str = Field(min_length=1)
    variables: tuple[str, ...]
    input_schema_version: str = Field(min_length=1)
    output_schema_version: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_immutable_content(self) -> PublishedPromptRevisionSnapshot:
        actual_variables = set(get_renderer().extract_variables(self.template))
        if (
            len(set(self.variables)) != len(self.variables)
            or set(self.variables) != actual_variables
        ):
            raise ValueError(
                "declared prompt variables must exactly match template variables"
            )
        if self.content_hash != self.recomputed_content_hash():
            raise ValueError("prompt revision content hash mismatch")
        return self

    def recomputed_content_hash(self) -> str:
        return compute_prompt_revision_content_hash(
            template_id=self.template_id,
            business_purpose=self.business_purpose,
            revision_id=self.revision_id,
            revision_no=self.revision_no,
            template=self.template,
            variables=self.variables,
            input_schema_version=self.input_schema_version,
            output_schema_version=self.output_schema_version,
        )


class CompiledPrompt(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    template_id: str
    revision_id: str
    revision_no: int
    rendered_prompt: str
    input_schema_version: str
    output_schema_version: str
    runtime_consumer: str
    model_routing_revision_id: str
    contract_hash: str


class PromptPreviewRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    template_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    business_purpose: str = Field(min_length=1)
    input_schema_version: str = Field(min_length=1)
    output_schema_version: str = Field(min_length=1)
    variables: dict[str, Any]
    runtime_consumer: str = Field(min_length=1)
    model_routing_revision_id: str = Field(min_length=1)


class PublishedPromptRevisionResolver(Protocol):
    async def resolve_published(
        self, *, template_id: str, revision_id: str
    ) -> PublishedPromptRevisionSnapshot:
        """Resolve exactly one published revision or fail closed."""


class StaticPublishedPromptRevisionResolver:
    """Deterministic resolver useful for composition roots and contract tests."""

    def __init__(self, revisions: list[PublishedPromptRevisionSnapshot]) -> None:
        self._revisions = {
            (revision.template_id, revision.revision_id): revision
            for revision in revisions
        }

    async def resolve_published(
        self, *, template_id: str, revision_id: str
    ) -> PublishedPromptRevisionSnapshot:
        try:
            return self._revisions[(template_id, revision_id)]
        except KeyError as exc:
            raise PromptRevisionNotPublishedError() from exc


class StrictPromptCompiler:
    """Canonical compiler used by both preview and runtime execution."""

    CONTRACT_VERSION = "governed-ai-prompt-contract.v1"

    def compile(
        self,
        *,
        revision: PublishedPromptRevisionSnapshot,
        variables: dict[str, Any],
        runtime_consumer: str,
        model_routing_revision_id: str,
    ) -> CompiledPrompt:
        actual_variables = set(get_renderer().extract_variables(revision.template))
        if (
            revision.content_hash != revision.recomputed_content_hash()
            or set(revision.variables) != actual_variables
        ):
            raise AIPlatformError(
                code="AI_PROMPT_REVISION_INTEGRITY_FAILED",
                classification=AIErrorClassification.PROMPT_CONTRACT_MISMATCH,
                message="已发布提示词修订版完整性校验失败。",
            )
        result = render_template(revision.template, variables, strict=True)
        if not result.success:
            raise AIPlatformError(
                code="AI_PROMPT_RENDER_FAILED",
                classification=AIErrorClassification.INPUT_SCHEMA_INVALID,
                message=result.error_message or "提示词渲染失败。",
            )
        if result.extra_variables:
            raise AIPlatformError(
                code="AI_PROMPT_VARIABLES_INVALID",
                classification=AIErrorClassification.INPUT_SCHEMA_INVALID,
                message="提示词变量包含已发布契约之外的字段。",
            )

        canonical = {
            "contract_version": self.CONTRACT_VERSION,
            "template_id": revision.template_id,
            "business_purpose": revision.business_purpose,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "revision_content_hash": revision.content_hash,
            "input_schema_version": revision.input_schema_version,
            "output_schema_version": revision.output_schema_version,
            "runtime_consumer": runtime_consumer,
            "model_routing_revision_id": model_routing_revision_id,
            "rendered_prompt": result.rendered,
        }
        digest = hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return CompiledPrompt(
            template_id=revision.template_id,
            revision_id=revision.revision_id,
            revision_no=revision.revision_no,
            rendered_prompt=result.rendered,
            input_schema_version=revision.input_schema_version,
            output_schema_version=revision.output_schema_version,
            runtime_consumer=runtime_consumer,
            model_routing_revision_id=model_routing_revision_id,
            contract_hash=f"sha256:{digest}",
        )


class PromptCompilationService:
    """Preview seam; runtime receives the same compiler instance by injection."""

    def __init__(
        self,
        *,
        resolver: PublishedPromptRevisionResolver,
        compiler: StrictPromptCompiler,
    ) -> None:
        self._resolver = resolver
        self._compiler = compiler

    async def preview(self, request: PromptPreviewRequest) -> CompiledPrompt:
        revision = await self._resolver.resolve_published(
            template_id=request.template_id,
            revision_id=request.revision_id,
        )
        if (
            revision.business_purpose != request.business_purpose
            or revision.input_schema_version != request.input_schema_version
            or revision.output_schema_version != request.output_schema_version
        ):
            raise AIPlatformError(
                code="AI_PROMPT_CONTRACT_MISMATCH",
                classification=AIErrorClassification.PROMPT_CONTRACT_MISMATCH,
                message="预览请求与已发布提示词修订版不一致。",
            )
        return self._compiler.compile(
            revision=revision,
            variables=request.variables,
            runtime_consumer=request.runtime_consumer,
            model_routing_revision_id=request.model_routing_revision_id,
        )


class LegacyMutablePromptTemplateAdapter:
    """Explicit non-bridge for the legacy mutable PromptTemplate table.

    The legacy row has neither an immutable revision id nor a publication state.
    Treating ``is_active`` as ``published`` would make exact replay impossible, so
    this adapter intentionally fails closed until a real revision snapshot exists.
    """

    async def resolve_published(
        self, *, template_id: str, revision_id: str
    ) -> PublishedPromptRevisionSnapshot:
        del template_id, revision_id
        raise PromptRevisionNotPublishedError()
