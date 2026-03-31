from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from common.knowledge_engine.config_repo import KnowledgeRankingProfileConfig


_NORMALIZE_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)


@dataclass(frozen=True)
class _ScoredRow:
    row: dict[str, Any]
    final_score: float


class KnowledgeReranker:
    """Project-owned business reranker with explainable score breakdowns."""

    def __init__(
        self,
        *,
        ranking_profiles: dict[str, KnowledgeRankingProfileConfig] | None = None,
    ) -> None:
        self._ranking_profiles = dict(ranking_profiles or {})

    def rerank(
        self,
        *,
        rows: list[dict[str, Any]],
        profile_key: str,
        query: str,
        normalized_query: str,
        resolved_entities: list[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not rows:
            return []

        profile = self._ranking_profiles.get(profile_key)
        if profile is None:
            return [
                self._decorate_passthrough(row)
                for row in rows[: max(1, top_k)]
            ]

        normalized_query_text = _normalize(normalized_query or query)
        normalized_entities = [_normalize(entity) for entity in resolved_entities if _normalize(entity)]
        query_remainder = normalized_query_text
        for entity in normalized_entities:
            query_remainder = query_remainder.replace(entity, "")
        seen_titles: dict[str, int] = {}
        scored_rows: list[_ScoredRow] = []

        for raw_row in rows:
            row = dict(raw_row)
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            title = str(row.get("document_title") or row.get("source") or metadata.get("document_title") or "")
            normalized_title = _normalize(title)
            content = str(row.get("content") or row.get("snippet") or "")
            normalized_content = _normalize(content)
            doc_type = str(metadata.get("doc_type") or row.get("doc_type") or "").strip().lower()
            section = str(metadata.get("section") or row.get("section") or "").strip().lower()
            retrieval_mode = str(row.get("retrieval_mode") or "").strip().lower()
            base_score = max(0.0, float(row.get("score") or 0.0))

            title_exact = 0.0
            if normalized_query_text and normalized_query_text in normalized_title:
                title_exact = profile.title_exact_boost
            elif normalized_entities and any(entity in normalized_title for entity in normalized_entities):
                if not query_remainder or any(token in normalized_title for token in _query_tokens(query_remainder)):
                    title_exact = profile.title_exact_boost
            entity_match = (
                profile.entity_match_boost
                if normalized_entities and any(entity in f"{normalized_title}{normalized_content}" for entity in normalized_entities)
                else 0.0
            )
            doc_type_weight = float(profile.doc_type_weights.get(doc_type, 0.0))
            section_weight = float(profile.section_weights.get(section, 0.0))

            title_occurrence = seen_titles.get(normalized_title, 0)
            diversity_penalty = 0.12 * title_occurrence if normalized_title else 0.0
            seen_titles[normalized_title] = title_occurrence + 1

            final_score = round(
                max(
                    0.0,
                    base_score + title_exact + entity_match + doc_type_weight + section_weight - diversity_penalty,
                ),
                4,
            )
            threshold = (
                profile.min_pass_score_keyword
                if retrieval_mode == "keyword_fallback"
                else profile.min_pass_score
            )
            row["score"] = final_score
            row["score_breakdown"] = {
                "strategy": "business_rerank",
                "base_score": round(base_score, 4),
                "title_exact": round(title_exact, 4),
                "entity_match": round(entity_match, 4),
                "doc_type": round(doc_type_weight, 4),
                "section": round(section_weight, 4),
                "diversity_penalty": round(diversity_penalty, 4),
                "threshold": round(float(threshold), 4),
            }
            row["ranking_passed"] = final_score >= threshold
            scored_rows.append(_ScoredRow(row=row, final_score=final_score))

        scored_rows.sort(key=lambda item: item.final_score, reverse=True)
        passed: list[dict[str, Any]] = []
        seen_passed_titles: set[str] = set()
        for item in scored_rows:
            row = item.row
            if not row.get("ranking_passed"):
                continue
            normalized_title = _normalize(
                row.get("document_title")
                or row.get("source")
                or (row.get("metadata") or {}).get("document_title")
                or ""
            )
            if normalized_title and normalized_title in seen_passed_titles:
                continue
            if normalized_title:
                seen_passed_titles.add(normalized_title)
            passed.append(row)
            if len(passed) >= max(1, top_k):
                break
        return passed

    @staticmethod
    def _decorate_passthrough(row: dict[str, Any]) -> dict[str, Any]:
        decorated = dict(row)
        decorated["score_breakdown"] = {
            "strategy": "passthrough",
            "base_score": round(max(0.0, float(row.get("score") or 0.0)), 4),
            "title_exact": 0.0,
            "entity_match": 0.0,
            "doc_type": 0.0,
            "section": 0.0,
            "diversity_penalty": 0.0,
            "threshold": 0.0,
        }
        decorated["ranking_passed"] = True
        return decorated



def _normalize(value: str) -> str:
    return "".join(_NORMALIZE_RE.findall(str(value or "").lower()))


def _query_tokens(value: str) -> list[str]:
    normalized = _normalize(value)
    if not normalized:
        return []
    return [token for token in (normalized[i:j] for i in range(len(normalized)) for j in range(i + 2, min(len(normalized), i + 6) + 1)) if token]
