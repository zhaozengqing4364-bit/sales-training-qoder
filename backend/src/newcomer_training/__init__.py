"""Public contracts for the newcomer foundation-training domain.

Business modules may import from this package surface. Persistence declarations and
delivery wiring remain internal implementation details.
"""

from newcomer_training.contracts import (
    ActivityDefinition,
    ActivityType,
    PathRevisionDraft,
    StageDefinition,
)

__all__ = [
    "ActivityDefinition",
    "ActivityType",
    "PathRevisionDraft",
    "StageDefinition",
]
