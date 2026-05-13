from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CurriculumAnalyticsSummary:
    assigned_count: int
    completed_count: int
    completion_rate: float
    top_weak_dimension: str | None
    average_score_delta: float


@dataclass(slots=True)
class CurriculumHeatmapCell:
    template_id: str
    template_name: str
    dimension: str
    average_score: float
    sample_count: int


@dataclass(slots=True)
class CurriculumScoreTrendPoint:
    date: str
    average_score: float
    sample_count: int


@dataclass(slots=True)
class CurriculumReviewOutcomes:
    approved: int
    rejected: int
    calibrated: int
    retraining_required: int


@dataclass(slots=True)
class CurriculumRetrainingConversion:
    created: int
    started: int
    completed: int


@dataclass(slots=True)
class CurriculumAnalyticsCacheInfo:
    enabled: bool
    hit: bool
    ttl_seconds: int | None


@dataclass(slots=True)
class CurriculumAnalyticsDashboard:
    summary: CurriculumAnalyticsSummary
    heatmap: list[CurriculumHeatmapCell]
    score_trend: list[CurriculumScoreTrendPoint]
    review_outcomes: CurriculumReviewOutcomes
    retraining_conversion: CurriculumRetrainingConversion
    cache: CurriculumAnalyticsCacheInfo
