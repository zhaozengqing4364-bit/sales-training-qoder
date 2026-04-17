"""
BaseCapability - Abstract Base Class for Agent Capabilities

Provides the foundation for all capability modules in the agent platform.
Capabilities are modular features that can be enabled/configured per Agent,
such as fuzzy word detection, sales stage recognition, and real-time scoring.

References:
- Requirements: R6, R7, R8 (Capability modules)
- Design: Section 1-3 (AgentContext, CapabilityRegistry, CapabilityRunner)
- Template: .kiro/templates/backend/capability.py

Usage:
    from agent.capabilities.base import BaseCapability, CapabilityConfig, CapabilityResult
    from agent.context import AgentContext

    class MyCapability(BaseCapability):
        capability_id = "my_capability"
        name = "My Capability"
        description = "Does something useful"

        async def execute(self, context: AgentContext, input_data: Any) -> CapabilityResult:
            # Implementation
            return CapabilityResult(success=True, data={"result": "value"})
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from agent.context import AgentContext
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# Type alias for capability configuration
# Configuration is a dictionary with string keys and any values
# Typically loaded from Agent.capabilities_config or Persona overrides
CapabilityConfig = dict[str, Any]

# Security constants
MAX_CONFIG_SIZE_BYTES = 10 * 1024  # 10KB max config size
MAX_CONFIG_DEPTH = 5  # Maximum nesting depth


@dataclass
class CapabilityResult:
    """
    Standardized result container for capability execution.

    All capability modules return this type to ensure consistent
    handling by the CapabilityRunner and WebSocket handlers.

    Attributes:
        success: Whether the capability executed successfully
        data: Result data (capability-specific structure)
        should_interrupt: Whether to interrupt the conversation flow
                         (e.g., for high-severity fuzzy word detection)
        feedback: Optional feedback message for the user
        fallback: Error code when success=False (e.g., "[TIMEOUT]", "[CAPABILITY_ERROR]")

    Examples:
        # Successful execution with data
        CapabilityResult(
            success=True,
            data={"detections": [{"category": "uncertain", "matched": ["大概"]}]},
            should_interrupt=True,
            feedback="检测到模糊表达"
        )

        # Failed execution with fallback
        CapabilityResult(
            success=False,
            fallback="[TIMEOUT]"
        )
    """

    success: bool
    data: dict[str, Any] | None = None
    should_interrupt: bool = False
    feedback: str | None = None
    fallback: str | None = None

    def __post_init__(self) -> None:
        """Validate result state after initialization."""
        if not self.success and self.fallback is None:
            self.fallback = "[CAPABILITY_ERROR]"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert result to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the result.
        """
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.should_interrupt:
            result["should_interrupt"] = self.should_interrupt
        if self.feedback is not None:
            result["feedback"] = self.feedback
        if self.fallback is not None:
            result["fallback"] = self.fallback
        return result


class BaseCapability(ABC):
    """
    Abstract base class for all capability modules.

    Capabilities are modular features that can be enabled and configured
    per Agent. They execute during conversation turns to provide real-time
    analysis and feedback.

    Class Attributes:
        capability_id: Unique identifier for the capability (e.g., "fuzzy_detection")
        name: Human-readable name (e.g., "模糊词检测")
        description: Brief description of what the capability does
        config_schema: JSON Schema defining valid configuration options

    Instance Attributes:
        config: Configuration dictionary for this capability instance

    Lifecycle:
        1. __init__(config): Initialize with configuration
        2. on_session_start(context): Called when session begins
        3. execute(context, input_data): Called for each conversation turn
        4. on_session_end(context): Called when session ends, returns stats

    Example:
        @CapabilityRegistry.register
        class FuzzyDetectionCapability(BaseCapability):
            capability_id = "fuzzy_detection"
            name = "模糊词检测"
            description = "检测用户语音中的模糊表达"

            config_schema = {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "cooldown_seconds": {"type": "number", "default": 10}
                }
            }

            async def execute(self, context, input_data):
                # Detection logic
                return CapabilityResult(success=True, data={"detections": []})
    """

    # Class-level attributes (must be overridden by subclasses)
    capability_id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    config_schema: ClassVar[dict[str, Any]] = {}

    def __init__(self, config: CapabilityConfig) -> None:
        """
        Initialize capability with configuration.

        Args:
            config: Configuration dictionary, typically from Agent.capabilities_config
                   merged with Persona overrides.
        """
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """
        Validate configuration against config_schema.

        Performs security checks:
        - Type validation (must be dict)
        - Size limit (max 10KB)
        - Depth limit (max 5 levels)

        Override this method for custom validation logic.
        """
        # Basic validation - ensure config is a dict
        if not isinstance(self.config, dict):
            raise ValueError(f"Config must be a dictionary, got {type(self.config)}")

        # Size limit check
        try:
            config_json = json.dumps(self.config, ensure_ascii=False)
            config_size = len(config_json.encode('utf-8'))
            if config_size > MAX_CONFIG_SIZE_BYTES:
                raise ValueError(
                    f"Config size {config_size} bytes exceeds "
                    f"limit of {MAX_CONFIG_SIZE_BYTES} bytes"
                )
        except (TypeError, ValueError) as e:
            if "exceeds limit" in str(e):
                raise
            raise ValueError(f"Config is not JSON serializable: {e}")

        # Depth limit check
        def check_depth(obj: Any, current_depth: int = 0) -> int:
            if current_depth > MAX_CONFIG_DEPTH:
                return current_depth
            if isinstance(obj, dict):
                if not obj:
                    return current_depth
                return max(check_depth(v, current_depth + 1) for v in obj.values())
            elif isinstance(obj, list):
                if not obj:
                    return current_depth
                return max(check_depth(item, current_depth + 1) for item in obj)
            return current_depth

        depth = check_depth(self.config)
        if depth > MAX_CONFIG_DEPTH:
            raise ValueError(
                f"Config nesting depth {depth} exceeds limit of {MAX_CONFIG_DEPTH}"
            )

    def is_enabled(self) -> bool:
        """
        Check if this capability is enabled in the configuration.

        Returns:
            True if enabled, False otherwise.
        """
        return self.config.get("enabled", True)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value with optional default.

        Args:
            key: Configuration key to retrieve
            default: Default value if key not found

        Returns:
            Configuration value or default.
        """
        return self.config.get(key, default)

    @abstractmethod
    async def execute(
        self,
        context: AgentContext,
        input_data: Any,
    ) -> CapabilityResult:
        """
        Execute the capability's main logic.

        This method is called for each conversation turn where the capability
        is enabled. It should analyze the input and return results.

        Args:
            context: AgentContext with session state and configuration
            input_data: Input to process (typically user text or conversation data)

        Returns:
            CapabilityResult with success status and any output data.

        Raises:
            Should not raise exceptions - catch and return CapabilityResult
            with success=False and appropriate fallback code.
        """
        pass

    async def on_session_start(self, context: AgentContext) -> None:
        """
        Called when a practice session begins.

        Use this to initialize session-specific state in context.state.

        Args:
            context: AgentContext for the new session
        """
        # Default: mark capability as initialized in state
        context.state[f"{self.capability_id}_initialized"] = True

    async def on_session_end(self, context: AgentContext) -> dict[str, Any]:
        """
        Called when a practice session ends.

        Use this to collect statistics and cleanup resources.

        Args:
            context: AgentContext for the ending session

        Returns:
            Dictionary of statistics for this capability's session activity.
        """
        # Default: return usage count
        return {
            "usage_count": context.state.get(f"{self.capability_id}_count", 0),
        }

    def _update_usage_count(self, context: AgentContext) -> None:
        """
        Increment the usage counter for this capability.

        Call this in execute() to track how many times the capability ran.

        Args:
            context: AgentContext to update
        """
        key = f"{self.capability_id}_count"
        context.state[key] = context.state.get(key, 0) + 1

    def __repr__(self) -> str:
        """Return string representation of the capability."""
        return (
            f"<{self.__class__.__name__}"
            f"(id={self.capability_id}, enabled={self.is_enabled()})>"
        )
