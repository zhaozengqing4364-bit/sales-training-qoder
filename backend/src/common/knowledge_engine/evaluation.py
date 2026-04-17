from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common.knowledge_engine.engine import KnowledgeAnswerEngine
from common.knowledge_engine.schemas import (
    KnowledgeAnswerRequest,
    KnowledgeAnswerResult,
)


@dataclass(frozen=True)
class KnowledgeAnswerEvalExpectation:
    answerability: str
    source_status: str
    blocked_text: str | None
    final_text: str | None
    unsupported_claims: list[str] = field(default_factory=list)
    citation_titles: list[str] = field(default_factory=list)
    rewritten_queries: list[str] = field(default_factory=list)
    executed_queries: list[str] = field(default_factory=list)
    profile_key: str | None = None
    compat_source_status: str | None = None
    search_failure_count: int | None = None
    blocked_reason: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KnowledgeAnswerEvalExpectation:
        return cls(
            answerability=str(payload.get("answerability") or "unanswered"),
            source_status=str(payload.get("source_status") or "not_run"),
            blocked_text=_optional_exact_text(payload.get("blocked_text")),
            final_text=_optional_exact_text(payload.get("final_text")),
            unsupported_claims=_string_list(payload.get("unsupported_claims")),
            citation_titles=_string_list(payload.get("citation_titles")),
            rewritten_queries=_string_list(payload.get("rewritten_queries")),
            executed_queries=_string_list(payload.get("executed_queries")),
            profile_key=_normalize_optional_text(payload.get("profile_key")),
            compat_source_status=_normalize_optional_text(payload.get("compat_source_status")),
            search_failure_count=_optional_int(payload.get("search_failure_count")),
            blocked_reason=_normalize_optional_text(payload.get("blocked_reason")),
        )


@dataclass(frozen=True)
class KnowledgeAnswerEvalCase:
    case_id: str
    query: str
    expected: KnowledgeAnswerEvalExpectation
    runtime_options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KnowledgeAnswerEvalCase:
        case_id = str(payload.get("id") or "").strip()
        query = str(payload.get("query") or "").strip()
        if not case_id:
            raise ValueError("Knowledge answer eval case requires non-empty id")
        if not query:
            raise ValueError(f"Knowledge answer eval case {case_id} requires non-empty query")
        expected_payload = payload.get("expected")
        if not isinstance(expected_payload, dict):
            raise ValueError(f"Knowledge answer eval case {case_id} requires expected dict")
        runtime_options = dict(payload.get("runtime_options")) if isinstance(payload.get("runtime_options"), dict) else {}
        return cls(
            case_id=case_id,
            query=query,
            expected=KnowledgeAnswerEvalExpectation.from_dict(expected_payload),
            runtime_options=runtime_options,
        )


@dataclass(frozen=True)
class KnowledgeAnswerEvalMismatch:
    field: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class KnowledgeAnswerEvalCaseResult:
    case_id: str
    passed: bool
    mismatches: list[KnowledgeAnswerEvalMismatch] = field(default_factory=list)
    executed_queries: list[str] = field(default_factory=list)
    answerability: str = "unanswered"
    source_status: str = "not_run"
    profile_key: str | None = None


@dataclass(frozen=True)
class KnowledgeAnswerEvalRunResult:
    passed: bool
    total_cases: int
    passed_cases: int
    failed_case_ids: list[str] = field(default_factory=list)
    results: list[KnowledgeAnswerEvalCaseResult] = field(default_factory=list)


RuntimeOptionsBuilder = Callable[[KnowledgeAnswerEvalCase], dict[str, Any]]


class KnowledgeAnswerEngineEvaluationHarness:
    """Run fixture-driven deterministic evaluation cases against the knowledge answer engine."""

    def __init__(
        self,
        *,
        engine: KnowledgeAnswerEngine,
        runtime_options_builder: RuntimeOptionsBuilder | None = None,
    ) -> None:
        self._engine = engine
        self._runtime_options_builder = runtime_options_builder or (lambda case: dict(case.runtime_options))

    def evaluate_cases(self, cases: list[KnowledgeAnswerEvalCase]) -> KnowledgeAnswerEvalRunResult:
        results = [self.evaluate_case(case) for case in cases]
        failed_case_ids = [result.case_id for result in results if not result.passed]
        return KnowledgeAnswerEvalRunResult(
            passed=not failed_case_ids,
            total_cases=len(results),
            passed_cases=sum(1 for result in results if result.passed),
            failed_case_ids=failed_case_ids,
            results=results,
        )

    def evaluate_case(self, case: KnowledgeAnswerEvalCase) -> KnowledgeAnswerEvalCaseResult:
        result = self._engine.answer(
            KnowledgeAnswerRequest(
                query=case.query,
                knowledge_base_ids=["kb-eval"],
                entrypoint="evaluation",
                runtime_options=self._runtime_options_builder(case),
            )
        )
        executed_queries = _extract_executed_queries(result)
        mismatches = _compare_case_result(case=case, result=result, executed_queries=executed_queries)
        retrieval_summary = dict(result.retrieval_summary)
        return KnowledgeAnswerEvalCaseResult(
            case_id=case.case_id,
            passed=not mismatches,
            mismatches=mismatches,
            executed_queries=executed_queries,
            answerability=result.answerability,
            source_status=result.source_status,
            profile_key=_normalize_optional_text(retrieval_summary.get("profile_key")),
        )

    @staticmethod
    def load_cases(path: str | Path) -> list[KnowledgeAnswerEvalCase]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Knowledge answer eval fixture must be a list")
        return [KnowledgeAnswerEvalCase.from_dict(item) for item in payload]


def _compare_case_result(
    *,
    case: KnowledgeAnswerEvalCase,
    result: KnowledgeAnswerResult,
    executed_queries: list[str],
) -> list[KnowledgeAnswerEvalMismatch]:
    mismatches: list[KnowledgeAnswerEvalMismatch] = []
    expected = case.expected
    retrieval_summary = dict(result.retrieval_summary)

    _append_mismatch(mismatches, "answerability", expected.answerability, result.answerability)
    _append_mismatch(mismatches, "source_status", expected.source_status, result.source_status)
    _append_mismatch(mismatches, "blocked_text", expected.blocked_text, result.blocked_text)
    _append_mismatch(mismatches, "final_text", expected.final_text, result.final_text)
    _append_mismatch(mismatches, "unsupported_claims", expected.unsupported_claims, list(result.unsupported_claims))
    _append_mismatch(
        mismatches,
        "citation_titles",
        expected.citation_titles,
        [citation.document_title for citation in result.citations],
    )
    _append_mismatch(mismatches, "rewritten_queries", expected.rewritten_queries, list(result.rewritten_queries))
    _append_mismatch(mismatches, "executed_queries", expected.executed_queries, executed_queries)

    if expected.profile_key is not None:
        _append_mismatch(mismatches, "profile_key", expected.profile_key, retrieval_summary.get("profile_key"))
    if expected.compat_source_status is not None:
        _append_mismatch(
            mismatches,
            "compat_source_status",
            expected.compat_source_status,
            retrieval_summary.get("compat_source_status"),
        )
    if expected.search_failure_count is not None:
        _append_mismatch(
            mismatches,
            "search_failure_count",
            expected.search_failure_count,
            retrieval_summary.get("search_failure_count"),
        )
    if expected.blocked_reason is not None or retrieval_summary.get("blocked_reason") is not None:
        _append_mismatch(
            mismatches,
            "blocked_reason",
            expected.blocked_reason,
            _normalize_optional_text(retrieval_summary.get("blocked_reason")),
        )

    return mismatches


def _append_mismatch(
    mismatches: list[KnowledgeAnswerEvalMismatch],
    field: str,
    expected: Any,
    actual: Any,
) -> None:
    if expected != actual:
        mismatches.append(KnowledgeAnswerEvalMismatch(field=field, expected=expected, actual=actual))


def _extract_executed_queries(result: KnowledgeAnswerResult) -> list[str]:
    execution_trace = result.retrieval_summary.get("execution_trace")
    executed_steps = execution_trace.get("executed_steps") if isinstance(execution_trace, dict) else []
    queries: list[str] = []
    for step in executed_steps:
        if not isinstance(step, dict):
            continue
        query = _normalize_optional_text(step.get("query"))
        if query:
            queries.append(query)
    return queries


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_optional_text(value: Any) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _optional_exact_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
