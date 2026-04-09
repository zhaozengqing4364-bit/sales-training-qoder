from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from common.knowledge_engine.config_repo import KnowledgeRankingProfileConfig

_NORMALIZE_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)


@dataclass(frozen=True)
class _ScoredRow:
    row: dict[str, Any]
    final_score: float


def _normalize(value: str) -> str:
    return "".join(_NORMALIZE_RE.findall(str(value or "").lower()))


def _query_tokens(value: str) -> list[str]:
    normalized = _normalize(value)
    if not normalized:
        return []
    return [
        token
        for token in (
            normalized[i:j]
            for i in range(len(normalized))
            for j in range(i + 2, min(len(normalized), i + 6) + 1)
        )
        if token
    ]


def _extract_query_terms(query: str, candidate_limit: int = 16) -> list[str]:
    """Extract normalized keyword terms from a query for coverage scoring."""
    normalized = _normalize(query)
    if not normalized:
        return []
    terms: list[str] = []
    seen: set[str] = set()

    # Whole query as one term
    if normalized not in seen:
        seen.add(normalized)
        terms.append(normalized)

    # Chinese character groups
    for fragment in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if fragment not in seen:
            seen.add(fragment)
            terms.append(fragment)
            # Bigrams for longer Chinese fragments
            if len(fragment) >= 4:
                for ngram_size in (4, 3, 2):
                    if len(terms) >= candidate_limit:
                        break
                    for index in range(0, len(fragment) - ngram_size + 1):
                        ngram = fragment[index : index + ngram_size]
                        if ngram not in seen:
                            seen.add(ngram)
                            terms.append(ngram)
                        if len(terms) >= candidate_limit:
                            break

    # Alphanumeric tokens
    for fragment in re.findall(r"[a-z0-9]+", normalized):
        if len(fragment) >= 2 and fragment not in seen:
            seen.add(fragment)
            terms.append(fragment)

    return terms[:candidate_limit]


class KnowledgeReranker:
    """Unified scoring reranker that merges three legacy ranking stages.

    Stage 1 (was service.py _rerank_results): base * weight + coverage * weight + phrase + title + ratio
    Stage 2 (was cross_encoder): cross_encoder_score * cross_encoder_weight
    Stage 3 (was business rerank): title_exact + entity_match + doc_type + section - diversity

    Now all in one function, all weights read from KnowledgeRankingProfileConfig.
    """

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
            return [self._decorate_passthrough(row) for row in rows[: max(1, top_k)]]

        normalized_query_text = _normalize(normalized_query or query)
        compact_query = _normalize(query)
        normalized_entities = [
            _normalize(entity) for entity in resolved_entities if _normalize(entity)
        ]
        query_remainder = normalized_query_text
        for entity in normalized_entities:
            query_remainder = query_remainder.replace(entity, "")
        query_terms = _extract_query_terms(query, candidate_limit=16)

        seen_titles: dict[str, int] = {}
        scored_rows: list[_ScoredRow] = []

        for raw_row in rows:
            row = dict(raw_row)
            raw_metadata = row.get("metadata")
            metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
            title = str(
                row.get("document_title")
                or row.get("source")
                or metadata.get("document_title")
                or ""
            )
            normalized_title = _normalize(title)
            content = str(row.get("content") or row.get("snippet") or "")
            normalized_content = _normalize(content)
            doc_type = (
                str(metadata.get("doc_type") or row.get("doc_type") or "")
                .strip()
                .lower()
            )
            section = (
                str(metadata.get("section") or row.get("section") or "").strip().lower()
            )
            retrieval_mode = str(row.get("retrieval_mode") or "").strip().lower()
            base_score = max(0.0, float(row.get("score") or 0.0))
            cross_encoder_score = float(row.get("cross_encoder_score") or 0.0)

            # ── Component A: Base retrieval scoring (elevated from _rerank_results) ──
            combined_text = _normalize(f"{title} {content}")
            coverage = self._coverage_score(
                combined_text=combined_text,
                query_terms=query_terms,
            )
            phrase = (
                profile.phrase_bonus
                if compact_query and compact_query in combined_text
                else 0.0
            )
            title_term_bonus = self._title_term_bonus(
                title=title,
                query_terms=query_terms,
                max_bonus=profile.title_bonus_max,
            )
            ratio_bonus = 0.0
            if compact_query and combined_text:
                ratio_bonus = (
                    SequenceMatcher(
                        None,
                        compact_query[:48],
                        combined_text[: max(64, len(compact_query) * 3)],
                    ).ratio()
                    * profile.ratio_bonus_max
                )
            base_component = (
                profile.base_weight * base_score
                + profile.coverage_weight * coverage
                + phrase
                + title_term_bonus
                + ratio_bonus
            )

            # ── Component B: Cross-encoder fusion ──
            ce_component = (
                profile.cross_encoder_weight * cross_encoder_score
                if cross_encoder_score > 0
                else 0.0
            )

            # ── Component C: Business weighting ──
            title_exact = 0.0
            if normalized_query_text and normalized_query_text in normalized_title:
                title_exact = profile.title_exact_boost
            elif normalized_entities and any(
                entity in normalized_title for entity in normalized_entities
            ):
                if not query_remainder or any(
                    token in normalized_title
                    for token in _query_tokens(query_remainder)
                ):
                    title_exact = profile.title_exact_boost
            entity_match = (
                profile.entity_match_boost
                if normalized_entities
                and any(
                    entity in f"{normalized_title}{normalized_content}"
                    for entity in normalized_entities
                )
                else 0.0
            )
            doc_type_weight = float(profile.doc_type_weights.get(doc_type, 0.0))
            section_weight = float(profile.section_weights.get(section, 0.0))
            business_component = (
                title_exact + entity_match + doc_type_weight + section_weight
            )

            # ── Component D: Diversity penalty ──
            title_occurrence = seen_titles.get(normalized_title, 0)
            diversity = (
                profile.diversity_penalty * title_occurrence
                if normalized_title
                else 0.0
            )
            seen_titles[normalized_title] = title_occurrence + 1

            # ── Final score ──
            final_score = round(
                max(
                    0.0, base_component + ce_component + business_component - diversity
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
                "strategy": "unified_rerank",
                "base_component": round(base_component, 4),
                "base_score": round(base_score, 4),
                "coverage": round(coverage, 4),
                "phrase": round(phrase, 4),
                "title_term_bonus": round(title_term_bonus, 4),
                "ratio_bonus": round(ratio_bonus, 4),
                "cross_encoder_component": round(ce_component, 4),
                "title_exact": round(title_exact, 4),
                "entity_match": round(entity_match, 4),
                "doc_type": round(doc_type_weight, 4),
                "section": round(section_weight, 4),
                "diversity_penalty": round(diversity, 4),
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
    def _coverage_score(
        *,
        combined_text: str,
        query_terms: list[str],
    ) -> float:
        if not combined_text or not query_terms:
            return 0.0
        matched = sum(1 for term in query_terms if term and term in combined_text)
        return min(1.0, matched / max(1, len(query_terms)))

    @staticmethod
    def _title_term_bonus(
        *,
        title: str,
        query_terms: list[str],
        max_bonus: float,
    ) -> float:
        normalized_title = _normalize(title)
        if not normalized_title:
            return 0.0
        matched = sum(1 for term in query_terms if term and term in normalized_title)
        if matched <= 0:
            return 0.0
        per_term = max_bonus / max(1, min(3, matched))
        return min(max_bonus, matched * per_term)

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
