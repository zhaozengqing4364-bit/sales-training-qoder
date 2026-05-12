"""Shared score snapshot normalization utilities."""

from __future__ import annotations

from typing import Any


def _coerce_bounded_score(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, normalized))


def normalize_score_snapshot(
    score_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Canonicalize score snapshots to the stable `overall_score` contract."""
    if not isinstance(score_snapshot, dict):
        return None

    normalized: dict[str, Any] = {}

    dimension_scores_raw = score_snapshot.get("dimension_scores")
    normalized_dimensions: dict[str, float] = {}
    if isinstance(dimension_scores_raw, dict):
        for key, raw_value in dimension_scores_raw.items():
            if not isinstance(key, str) or not key:
                continue
            normalized_value = _coerce_bounded_score(raw_value)
            if normalized_value is None:
                continue
            normalized_dimensions[key] = normalized_value

    overall_score = _coerce_bounded_score(score_snapshot.get("overall_score"))
    if overall_score is None:
        overall_score = _coerce_bounded_score(score_snapshot.get("overall"))
    if overall_score is None and normalized_dimensions:
        overall_score = round(
            sum(normalized_dimensions.values()) / len(normalized_dimensions),
            2,
        )

    if overall_score is not None:
        normalized["overall_score"] = overall_score
    if normalized_dimensions:
        normalized["dimension_scores"] = normalized_dimensions

    stage_name = score_snapshot.get("stage_name")
    if isinstance(stage_name, str) and stage_name.strip():
        normalized["stage_name"] = stage_name.strip()

    suggestions = score_snapshot.get("suggestions")
    if isinstance(suggestions, list):
        normalized_suggestions = [
            item.strip()
            for item in suggestions
            if isinstance(item, str) and item.strip()
        ]
        if normalized_suggestions:
            normalized["suggestions"] = normalized_suggestions

    canonical_kernel = score_snapshot.get("canonical_evaluation_kernel")
    if isinstance(canonical_kernel, dict) and canonical_kernel:
        normalized["canonical_evaluation_kernel"] = canonical_kernel

    compatibility_readers = score_snapshot.get("compatibility_readers")
    if isinstance(compatibility_readers, dict) and compatibility_readers:
        normalized["compatibility_readers"] = compatibility_readers

    return normalized or None
