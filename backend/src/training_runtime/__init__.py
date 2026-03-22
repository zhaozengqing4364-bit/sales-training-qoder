"""Training runtime descriptor exports."""

from .models import TrainingRuntimeDescriptor, TrainingRuntimeSubject
from .service import build_training_runtime_descriptor

__all__ = [
    "TrainingRuntimeDescriptor",
    "TrainingRuntimeSubject",
    "build_training_runtime_descriptor",
]
