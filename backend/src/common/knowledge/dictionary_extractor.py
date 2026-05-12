"""LLM-assisted KB dictionary draft extraction helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator

from common.ai.llm_service import get_llm_service
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

MAX_ALIASES_PER_TERM = 5
DEFAULT_CHUNK_LIMIT = 50
ALLOWED_ALIAS_REASONS = {
    "homophone",
    "near_homophone",
    "common_asr_typo",
    "abbreviation",
    "spelling_variant",
    "format_variant",
}


class DictionaryLLMService(Protocol):
    @property
    def is_configured(self) -> bool: ...

    @property
    def provider(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    async def generate(
        self,
        prompt: str,
        session_id: str,
        system_message: str | None = None,
        context: dict[str, Any] | None = None,
        *,
        allow_fallback_response: bool = True,
    ) -> Result[str]: ...


class DictionaryAliasSuggestion(BaseModel):
    alias: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., max_length=50)
    confidence: int = Field(default=80, ge=0, le=100)

    @field_validator("alias")
    @classmethod
    def _strip_alias(cls, value: str) -> str:
        return value.strip()

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, value: str) -> str:
        reason = value.strip().lower().replace("-", "_")
        return reason if reason in ALLOWED_ALIAS_REASONS else "spelling_variant"


class DictionaryExtractionCandidate(BaseModel):
    canonical_term: str = Field(..., min_length=2, max_length=255)
    aliases: list[DictionaryAliasSuggestion] = Field(default_factory=list)
    term_type: str = Field(default="other", max_length=50)
    confidence: int = Field(default=80, ge=0, le=100)
    evidence_snippet: str | None = Field(default=None, max_length=500)
    generation_rationale: str | None = Field(default=None, max_length=500)
    risk_markers: list[str] = Field(default_factory=list, max_length=10)
    source_chunk_id: str | None = None
    source_document_id: str | None = None
    source_chunk_index: int | str | None = None

    @field_validator("canonical_term")
    @classmethod
    def _strip_term(cls, value: str) -> str:
        return value.strip()

    @field_validator("aliases")
    @classmethod
    def _dedupe_aliases(
        cls, value: list[DictionaryAliasSuggestion]
    ) -> list[DictionaryAliasSuggestion]:
        seen: set[str] = set()
        aliases: list[DictionaryAliasSuggestion] = []
        for item in value:
            alias = item.alias.strip()
            if alias and alias not in seen:
                aliases.append(item)
                seen.add(alias)
            if len(aliases) >= MAX_ALIASES_PER_TERM:
                break
        return aliases


@dataclass(frozen=True)
class DictionaryExtractionChunk:
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int | str
    content: str
    metadata: dict[str, Any]


class DictionaryExtractor:
    """Extract KB-scoped dictionary candidates with the configured global LLM."""

    def __init__(
        self,
        llm_service: DictionaryLLMService | None = None,
        *,
        chunk_limit: int = DEFAULT_CHUNK_LIMIT,
    ) -> None:
        self.llm_service = llm_service or get_llm_service()
        self.chunk_limit = max(1, min(chunk_limit, DEFAULT_CHUNK_LIMIT))

    def select_high_value_chunks(
        self, chunks: list[DictionaryExtractionChunk]
    ) -> list[DictionaryExtractionChunk]:
        scored = [chunk for chunk in chunks if chunk.content.strip()]
        scored.sort(key=self._chunk_score, reverse=True)
        return scored[: self.chunk_limit]

    async def extract(
        self,
        *,
        kb_id: str,
        chunks: list[DictionaryExtractionChunk],
        limit: int,
    ) -> Result[list[DictionaryExtractionCandidate]]:
        selected = self.select_high_value_chunks(chunks)
        if not selected:
            return Result.ok([])
        if not self.llm_service.is_configured:
            return Result.fail("[LLM_NOT_CONFIGURED]")

        prompt = self._build_prompt(kb_id=kb_id, chunks=selected, limit=limit)
        result = await self.llm_service.generate(
            prompt=prompt,
            session_id=f"kb_dictionary_extract:{kb_id}",
            system_message=(
                "你是知识库词典抽取助手。只返回严格 JSON，不要输出解释性文本。"
            ),
            context={"scenario": "knowledge_dictionary_extraction", "kb_id": kb_id},
            allow_fallback_response=False,
        )
        if not result.is_success or not result.value:
            return Result.fail(result.fallback or "[LLM_EXTRACTION_FAILED]")

        try:
            candidates = self._parse_candidates(str(result.value), selected)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning("Dictionary extraction output rejected", error=str(exc))
            return Result.fail("[LLM_EXTRACTION_INVALID_JSON]")
        return Result.ok(candidates[: max(1, min(limit, 100))])

    @staticmethod
    def candidate_metadata(
        candidate: DictionaryExtractionCandidate,
        *,
        provider: str,
        model_name: str,
        method: str = "llm",
        fallback_reason: str | None = None,
        is_potential_duplicate: bool = False,
        duplicate_of_canonical_term: str | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "method": method,
            "llm_provider": provider,
            "llm_model": model_name,
            "generation_rationale": candidate.generation_rationale,
            "alias_reasons": {item.alias: item.reason for item in candidate.aliases},
            "alias_confidence": {item.alias: item.confidence for item in candidate.aliases},
            "risk_markers": candidate.risk_markers,
            "evidence_snippet": candidate.evidence_snippet,
            "chunk_id": candidate.source_chunk_id,
            "document_id": candidate.source_document_id,
            "chunk_index": candidate.source_chunk_index,
            "is_potential_duplicate": is_potential_duplicate,
        }
        if duplicate_of_canonical_term:
            metadata["duplicate_of_canonical_term"] = duplicate_of_canonical_term
        if fallback_reason:
            metadata["fallback_reason"] = fallback_reason
        return {key: value for key, value in metadata.items() if value is not None}

    @staticmethod
    def _chunk_score(chunk: DictionaryExtractionChunk) -> tuple[int, int]:
        cjk_terms = re.findall(r"[\u4e00-\u9fff]{2,12}", chunk.content)
        latin_terms = re.findall(r"[A-Za-z][A-Za-z0-9._-]{1,30}", chunk.content)
        unique_terms = len(set(cjk_terms + latin_terms))
        return (unique_terms, min(len(chunk.content), 2000))

    @staticmethod
    def _strip_json_wrapper(raw: str) -> str:
        text = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S)
        if fenced:
            return fenced.group(1).strip()
        return text

    def _parse_candidates(
        self, raw: str, chunks: list[DictionaryExtractionChunk]
    ) -> list[DictionaryExtractionCandidate]:
        payload = json.loads(self._strip_json_wrapper(raw))
        if isinstance(payload, dict):
            raw_items = payload.get("items") or payload.get("entries") or []
        else:
            raw_items = payload
        if not isinstance(raw_items, list):
            raise ValueError("extraction output must be a list")

        chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
        candidates: list[DictionaryExtractionCandidate] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            candidate = DictionaryExtractionCandidate.model_validate(item)
            chunk = self._resolve_candidate_chunk(candidate, chunk_map, chunks)
            if chunk is None:
                continue
            if candidate.canonical_term not in chunk.content:
                continue
            if candidate.evidence_snippet and candidate.evidence_snippet not in chunk.content:
                candidate.risk_markers.append("evidence_snippet_not_found")
            candidate.source_chunk_id = chunk.chunk_id
            candidate.source_document_id = chunk.document_id
            candidate.source_chunk_index = chunk.chunk_index
            candidates.append(candidate)
        return candidates

    @staticmethod
    def _resolve_candidate_chunk(
        candidate: DictionaryExtractionCandidate,
        chunk_map: dict[str, DictionaryExtractionChunk],
        chunks: list[DictionaryExtractionChunk],
    ) -> DictionaryExtractionChunk | None:
        if candidate.source_chunk_id and candidate.source_chunk_id in chunk_map:
            return chunk_map[candidate.source_chunk_id]
        for chunk in chunks:
            if candidate.canonical_term in chunk.content:
                return chunk
        return None

    @staticmethod
    def _build_prompt(
        *,
        kb_id: str,
        chunks: list[DictionaryExtractionChunk],
        limit: int,
    ) -> str:
        chunk_lines = []
        for chunk in chunks:
            content = chunk.content.strip().replace("\n", " ")[:1200]
            chunk_lines.append(
                json.dumps(
                    {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "document_title": chunk.document_title,
                        "chunk_index": chunk.chunk_index,
                        "content": content,
                    },
                    ensure_ascii=False,
                )
            )
        return (
            "从以下知识库切片中抽取最多 "
            f"{max(1, min(limit, 100))} 个知识库词典草稿候选。\n"
            "要求：标准词 canonical_term 必须逐字出现在对应 content 中；"
            "aliases 最多 5 个；alias reason 只能是 homophone, near_homophone, "
            "common_asr_typo, abbreviation, spelling_variant, format_variant；"
            "所有结果只用于人工审核草稿。\n"
            "返回 JSON：{\"items\":[{\"canonical_term\":string,\"aliases\":[{\"alias\":string,"
            "\"reason\":string,\"confidence\":number}],\"term_type\":string,\"confidence\":number,"
            "\"evidence_snippet\":string,\"generation_rationale\":string,\"risk_markers\":[string],"
            "\"source_chunk_id\":string}]}。\n"
            f"knowledge_base_id: {kb_id}\nchunks:\n" + "\n".join(chunk_lines)
        )
