"""Compatibility exports for neutral realtime message persistence."""

from training_runtime.realtime.message_persistence import (
    extract_analysis_patch_fields,
    normalize_message_persistence_payload,
    normalize_score_snapshot,
    patch_existing_message_analysis,
    save_stepfun_message,
)

__all__ = [
    "extract_analysis_patch_fields",
    "normalize_message_persistence_payload",
    "normalize_score_snapshot",
    "patch_existing_message_analysis",
    "save_stepfun_message",
]
