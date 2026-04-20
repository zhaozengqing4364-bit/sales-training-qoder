"""
AgentContext - Capability Module Execution Context

Provides runtime context for capability modules during practice sessions.
Contains session state, configuration, and conversation history.

References:
- Requirements: R6, R7, R8 (Capability modules)
- Design: Section 1 (AgentContext)
"""
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# State management constants
MAX_STATE_ENTRIES = 100  # Maximum number of state keys
MAX_STATE_VALUE_SIZE = 50 * 1024  # 50KB max per state value
MAX_CONVERSATION_HISTORY = 200  # Maximum messages in history


@dataclass
class AgentContext:
    """
    Capability module execution context.

    Provides all necessary information for capability modules to execute,
    including session identifiers, configuration, state, and conversation history.

    Attributes:
        session_id: Unique identifier for the practice session
        agent_id: ID of the Agent being used
        persona_id: ID of the Persona being interacted with
        user_id: ID of the user in the session
        state: Mutable session state (capabilities can read/write)
        conversation_history: List of conversation messages
        agent_config: Agent configuration including capabilities_config
        persona_config: Persona configuration including behavior_config
        turn_count: Number of conversation turns completed
        start_time: Session start timestamp
        trace_id: Unique ID for request tracing/debugging
    """

    # Required identifiers
    session_id: str
    agent_id: str
    persona_id: str
    user_id: str

    # Mutable state (capabilities can read/write)
    state: dict[str, Any] = field(default_factory=dict)

    # Conversation history
    conversation_history: list[dict[str, Any]] = field(default_factory=list)

    # Configuration
    agent_config: dict[str, Any] = field(default_factory=dict)
    persona_config: dict[str, Any] = field(default_factory=dict)

    # Runtime metadata
    turn_count: int = 0
    start_time: datetime | None = None
    trace_id: str | None = None

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.start_time is None:
            self.start_time = datetime.now(UTC)
        if self.trace_id is None:
            self.trace_id = str(uuid.uuid4())

    def get_scoring_weights(self) -> list[dict[str, Any]] | None:
        """
        Get scoring weights, with Persona config taking priority over Agent config.

        Returns:
            List of scoring dimension configurations, or None if not configured.
            Each dimension has: {"name": str, "weight": float}
        """
        # Persona scoring_weights takes priority
        persona_weights = self.persona_config.get("scoring_weights")
        if persona_weights:
            return persona_weights

        # Fall back to Agent capabilities_config
        capabilities_config = self.agent_config.get("capabilities_config", {})
        scoring_config = capabilities_config.get("scoring", {})
        return scoring_config.get("dimensions")

    def get_capability_config(self, capability_id: str) -> dict[str, Any]:
        """
        Get configuration for a specific capability.

        Merges Agent and Persona configurations, with Persona taking priority.

        Args:
            capability_id: The capability identifier (e.g., "fuzzy_detection")

        Returns:
            Merged configuration dictionary for the capability.
        """
        # Get base config from Agent
        capabilities_config = self.agent_config.get("capabilities_config", {})
        base_config = capabilities_config.get(capability_id, {}).copy()

        # Merge Persona overrides if present
        persona_overrides = self.persona_config.get(capability_id, {})
        base_config.update(persona_overrides)

        return base_config

    def add_message(
        self,
        role: str,
        content: str,
        **metadata: Any,
    ) -> None:
        """
        Add a message to conversation history.

        Automatically limits history size to prevent memory growth.

        Args:
            role: Message role ("user" or "assistant")
            content: Message text content
            **metadata: Additional metadata (timestamp, audio_url, etc.)
        """
        message = {
            "role": role,
            "content": content,
            "turn_number": self.turn_count,
            "timestamp": datetime.now(UTC).isoformat(),
            **metadata,
        }
        self.conversation_history.append(message)

        # Limit history size
        if len(self.conversation_history) > MAX_CONVERSATION_HISTORY:
            # Keep most recent messages
            self.conversation_history = (
                self.conversation_history[-MAX_CONVERSATION_HISTORY:]
            )
            logger.debug(
                f"Conversation history trimmed to "
                f"{MAX_CONVERSATION_HISTORY} messages",
                session_id=self.session_id
            )

    def get_recent_messages(self, count: int = 5) -> list[dict[str, Any]]:
        """
        Get the most recent messages from conversation history.

        Args:
            count: Number of recent messages to return

        Returns:
            List of recent messages, most recent last.
        """
        return self.conversation_history[-count:] if self.conversation_history else []

    def increment_turn(self) -> int:
        """
        Increment the turn counter and return the new value.

        Returns:
            The new turn count after incrementing.
        """
        self.turn_count += 1
        return self.turn_count

    def get_session_duration_ms(self) -> int:
        """
        Calculate session duration in milliseconds.

        Returns:
            Duration since session start in milliseconds.
        """
        if self.start_time is None:
            return 0
        delta = datetime.now(UTC) - self.start_time
        return int(delta.total_seconds() * 1000)

    def get_knowledge_base_ids(self) -> list[str]:
        """
        Get combined knowledge base IDs from Agent and Persona.

        Returns:
            Deduplicated list of knowledge base IDs.
        """
        agent_kb_ids = self.agent_config.get("default_knowledge_base_ids", [])
        persona_kb_ids = self.persona_config.get("knowledge_base_ids", [])

        # Combine and deduplicate while preserving order
        seen = set()
        combined = []
        for kb_id in agent_kb_ids + persona_kb_ids:
            if kb_id not in seen:
                seen.add(kb_id)
                combined.append(kb_id)

        return combined
