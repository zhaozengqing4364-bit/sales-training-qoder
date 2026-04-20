"""
Evaluation Module

Provides staged evaluation and comprehensive reporting capabilities.
"""

from evaluation.triggers.base_trigger import BaseTrigger, TriggerContext
from evaluation.triggers.keyword import KeywordTrigger
from evaluation.triggers.stage_transition import StageTransitionTrigger
from evaluation.triggers.time_interval import TimeIntervalTrigger
from evaluation.triggers.turn_count import TurnCountTrigger

# Services are imported separately to avoid circular dependencies
# from src.evaluation.services.staged_evaluation import (
#     StagedEvaluationService,
#     StageEvaluationResult,
#     StageConfig,
# )
# from src.evaluation.services.comprehensive_report import (
#     ComprehensiveReportService,
#     ComprehensiveReport,
#     DimensionScore,
# )

__all__ = [
    # Triggers
    "BaseTrigger",
    "TriggerContext",
    "KeywordTrigger",
    "StageTransitionTrigger",
    "TimeIntervalTrigger",
    "TurnCountTrigger",
    # Services (import directly from services module)
    # "StagedEvaluationService",
    # "StageEvaluationResult",
    # "StageConfig",
    # "ComprehensiveReportService",
    # "ComprehensiveReport",
    # "DimensionScore",
]
