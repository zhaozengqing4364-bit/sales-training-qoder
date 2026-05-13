"""
v1-8: Composition components extracted from the legacy sales websocket monolith.

- TTSComponent: TTS response generation (single-shot + streaming)
- CapabilityProcessor: Capability module execution & real-time feedback
- MessagePersistence: Database message storage operations
- CurriculumStageRuntime: Curriculum template-stage progress tracking
"""

from .capability_processor import CapabilityProcessor
from .curriculum_stage_runtime import CurriculumStageRuntime
from .message_persistence import MessagePersistence
from .tts_component import TTSComponent

__all__ = [
    "TTSComponent",
    "CapabilityProcessor",
    "MessagePersistence",
    "CurriculumStageRuntime",
]
