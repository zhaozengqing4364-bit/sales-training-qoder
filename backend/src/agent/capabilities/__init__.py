"""
Agent Capabilities Module

Provides modular capability system for AI agents including:
- BaseCapability: Abstract base class for all capabilities
- CapabilityConfig: Configuration type alias
- CapabilityResult: Standardized result container
- CapabilityRegistry: Singleton registry for capability discovery
- CapabilityRunner: Orchestrates capability execution

Capability Modules:
- FuzzyDetectionCapability: 模糊词检测
- SalesStageCapability: 销售阶段识别
- RealtimeScoringCapability: 实时评分
- KnowledgeRetrievalCapability: 知识库检索

References:
- Requirements: R5, R6, R7, R8 (Capability modules)
- Design: Sections 1-3, 7-10
"""

from .base import (
    BaseCapability,
    CapabilityConfig,
    CapabilityResult,
)

# Import capabilities to trigger registration
from .fuzzy_detection import FuzzyDetectionCapability
from .knowledge_retrieval import KnowledgeRetrievalCapability
from .realtime_scoring import RealtimeScoringCapability
from .registry import CapabilityRegistry
from .runner import CapabilityRunner
from .sales_stage import SalesStageCapability

__all__ = [
    "BaseCapability",
    "CapabilityConfig",
    "CapabilityResult",
    "CapabilityRegistry",
    "CapabilityRunner",
    "FuzzyDetectionCapability",
    "SalesStageCapability",
    "RealtimeScoringCapability",
    "KnowledgeRetrievalCapability",
]
