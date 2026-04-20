"""
v1-8: Composition components extracted from EnhancedSalesHandler.

- TTSComponent: TTS response generation (single-shot + streaming)
- CapabilityProcessor: Capability module execution & real-time feedback
- MessagePersistence: Database message storage operations
"""

from .capability_processor import CapabilityProcessor
from .message_persistence import MessagePersistence
from .tts_component import TTSComponent

__all__ = ["TTSComponent", "CapabilityProcessor", "MessagePersistence"]
