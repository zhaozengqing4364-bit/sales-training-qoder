"""
CapabilityRunner - Manages Capability Module Lifecycle and Execution

Provides orchestration for capability modules during practice sessions.
Handles initialization, parallel execution, and session lifecycle events.

References:
- Requirements: R6, R7, R8 (Capability modules)
- Design: Section 3 (CapabilityRunner)

Usage:
    from agent.capabilities.runner import CapabilityRunner
    from agent.context import AgentContext

    # Initialize with Agent and Persona configuration
    runner = CapabilityRunner(agent_config, persona_config)

    # Session lifecycle
    await runner.on_session_start(context)

    # Execute all capabilities for a conversation turn
    results = await runner.run_all(context, user_text)

    # End session and collect stats
    stats = await runner.on_session_end(context)
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from common.monitoring.logger import get_logger

from .base import BaseCapability, CapabilityResult
from .registry import CapabilityRegistry

if TYPE_CHECKING:
    from agent.context import AgentContext

logger = get_logger(__name__)

# Timeout and error handling constants
CAPABILITY_TIMEOUT_SECONDS = 5.0  # Max time for single capability execution
DEFAULT_ERROR_CODE = "[CAPABILITY_ERROR]"

# Error code mapping for specific exception types
ERROR_CODE_MAP: dict[type, str] = {
    asyncio.TimeoutError: "[CAPABILITY_TIMEOUT]",
    ValueError: "[CAPABILITY_INVALID_INPUT]",
    ConnectionError: "[CAPABILITY_CONNECTION_ERROR]",
    PermissionError: "[CAPABILITY_PERMISSION_DENIED]",
    OSError: "[CAPABILITY_IO_ERROR]",
    RuntimeError: "[CAPABILITY_RUNTIME_ERROR]",
}

RECOVERABLE_CAPABILITY_ERRORS = (
    ConnectionError,
    OSError,
    RuntimeError,
    ValueError,
    KeyError,
)


class CapabilityRunner:
    """
    Capability module runner - manages lifecycle and execution.

    Orchestrates capability modules during practice sessions, handling:
    - Initialization based on Agent/Persona configuration
    - Parallel execution of all enabled capabilities
    - Session start/end lifecycle events
    - Error handling and fallback responses

    Attributes:
        capabilities: List of initialized capability instances
        agent_config: Agent configuration dictionary
        persona_config: Persona configuration dictionary (optional)

    Example:
        # Initialize runner with configurations
        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "fuzzy_detection": {"enabled": True, "cooldown_seconds": 10},
                    "sales_stage": {"enabled": True},
                    "realtime_scoring": {"enabled": False}
                }
            },
            persona_config={
                "fuzzy_detection": {"cooldown_seconds": 5}  # Override
            }
        )

        # Start session
        await runner.on_session_start(context)

        # Execute on each turn
        results = await runner.run_all(context, "用户说的话")

        # End session
        stats = await runner.on_session_end(context)
    """

    def __init__(
        self,
        agent_config: dict[str, Any],
        persona_config: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the capability runner with configuration.

        Args:
            agent_config: Agent configuration containing capabilities_config
            persona_config: Optional Persona configuration for overrides
        """
        self.agent_config = agent_config
        self.persona_config = persona_config or {}
        self.capabilities: list[BaseCapability] = []
        self._init_capabilities()

    def _init_capabilities(self) -> None:
        """
        Initialize capability instances based on configuration.

        Reads capabilities_config from agent_config, instantiates enabled
        capabilities, and merges Persona configuration overrides.
        """
        caps_config = self.agent_config.get("capabilities_config", {})

        for cap_id, config in caps_config.items():
            # Skip disabled capabilities
            if not config.get("enabled", False):
                logger.debug(
                    f"Capability '{cap_id}' is disabled, skipping",
                    capability_id=cap_id,
                )
                continue

            # Get capability class from registry
            cap_class = CapabilityRegistry.get(cap_id)
            if cap_class is None:
                logger.warning(
                    f"Capability '{cap_id}' not found in registry",
                    capability_id=cap_id,
                )
                continue

            # Merge Persona configuration overrides
            merged_config = {**config}
            persona_overrides = self.persona_config.get(cap_id, {})
            if persona_overrides:
                merged_config.update(persona_overrides)
                logger.debug(
                    f"Applied Persona overrides for '{cap_id}'",
                    capability_id=cap_id,
                    overrides=persona_overrides,
                )

            # Instantiate capability
            try:
                capability = cap_class(merged_config)
                self.capabilities.append(capability)
                logger.info(
                    f"Initialized capability: {cap_id}",
                    capability_id=cap_id,
                    config=merged_config,
                )
            except (RuntimeError, ValueError, KeyError) as e:
                logger.error(
                    f"Failed to initialize capability '{cap_id}': {e}",
                    capability_id=cap_id,
                    error=str(e),
                )

    async def run_all(
        self,
        context: AgentContext,
        input_data: Any,
    ) -> list[CapabilityResult]:
        """
        Execute all capabilities in parallel with timeout protection.

        Runs all initialized capabilities concurrently using asyncio.gather,
        with per-capability timeout to prevent blocking. Handles exceptions
        gracefully and returns fallback results for failed capabilities.

        Args:
            context: AgentContext with session state and configuration
            input_data: Input to process (typically user text)

        Returns:
            List of CapabilityResult objects, one per capability.
            Failed capabilities return CapabilityResult with success=False.

        Example:
            results = await runner.run_all(context, "用户说的话")
            for result in results:
                if result.success and result.should_interrupt:
                    # Handle interruption (e.g., fuzzy word detected)
                    pass
        """
        if not self.capabilities:
            logger.debug("No capabilities to run")
            return []

        async def run_with_timeout(cap: BaseCapability) -> CapabilityResult:
            """Execute a single capability with timeout protection."""
            try:
                return await asyncio.wait_for(
                    cap.execute(context, input_data),
                    timeout=CAPABILITY_TIMEOUT_SECONDS
                )
            except asyncio.CancelledError:
                logger.info(
                    f"Capability '{cap.capability_id}' cancelled",
                    capability_id=cap.capability_id,
                    session_id=getattr(context, "session_id", None),
                )
                raise
            except TimeoutError:
                logger.error(
                    f"Capability '{cap.capability_id}' timed out "
                    f"after {CAPABILITY_TIMEOUT_SECONDS}s",
                    capability_id=cap.capability_id,
                    session_id=getattr(context, "session_id", None),
                )
                return CapabilityResult(
                    success=False,
                    fallback="[CAPABILITY_TIMEOUT]",
                )
            except (ConnectionError, OSError, RuntimeError, ValueError, KeyError) as e:
                error_code = self._get_error_code(e)
                logger.error(
                    f"Capability '{cap.capability_id}' failed: {e}",
                    capability_id=cap.capability_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    session_id=getattr(context, "session_id", None),
                )
                return CapabilityResult(
                    success=False,
                    fallback=error_code,
                )

        # Create tasks for parallel execution with timeout
        tasks = [run_with_timeout(cap) for cap in self.capabilities]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)

        return list(results)

    def _get_error_code(self, error: Exception) -> str:
        """
        Get appropriate error code for an exception.

        Args:
            error: The exception that occurred

        Returns:
            Error code string for the exception type.
        """
        for error_type, code in ERROR_CODE_MAP.items():
            if isinstance(error, error_type):
                return code
        return DEFAULT_ERROR_CODE

    async def run_one(
        self,
        capability_id: str,
        context: AgentContext,
        input_data: Any,
    ) -> CapabilityResult | None:
        """
        Execute a single capability by ID with timeout protection.

        Useful when you need to run a specific capability outside the
        normal parallel execution flow.

        Args:
            capability_id: The ID of the capability to run
            context: AgentContext with session state and configuration
            input_data: Input to process

        Returns:
            CapabilityResult if capability found and executed, None otherwise.
        """
        for cap in self.capabilities:
            if cap.capability_id == capability_id:
                try:
                    return await asyncio.wait_for(
                        cap.execute(context, input_data),
                        timeout=CAPABILITY_TIMEOUT_SECONDS
                    )
                except asyncio.CancelledError:
                    logger.info(
                        f"Capability '{capability_id}' cancelled",
                        capability_id=capability_id,
                        session_id=getattr(context, "session_id", None),
                    )
                    raise
                except TimeoutError:
                    logger.error(
                        f"Capability '{capability_id}' timed out "
                        f"after {CAPABILITY_TIMEOUT_SECONDS}s",
                        capability_id=capability_id,
                        session_id=getattr(context, "session_id", None),
                    )
                    return CapabilityResult(
                        success=False,
                        fallback="[CAPABILITY_TIMEOUT]",
                    )
                except (
                    ConnectionError,
                    OSError,
                    RuntimeError,
                    ValueError,
                    KeyError,
                ) as e:
                    error_code = self._get_error_code(e)
                    logger.error(
                        f"Capability '{capability_id}' failed: {e}",
                        capability_id=capability_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    return CapabilityResult(
                        success=False,
                        fallback=error_code,
                    )

        logger.warning(
            f"Capability '{capability_id}' not found in runner",
            capability_id=capability_id,
        )
        return None

    async def on_session_start(self, context: AgentContext) -> None:
        """
        Call on_session_start for all capabilities.

        Should be called when a practice session begins to allow
        capabilities to initialize session-specific state.

        Args:
            context: AgentContext for the new session
        """
        logger.info(
            "Starting session for capabilities",
            session_id=context.session_id,
            capability_count=len(self.capabilities),
        )

        for cap in self.capabilities:
            try:
                await cap.on_session_start(context)
            except (RuntimeError, ValueError, KeyError) as e:
                logger.error(
                    f"Capability '{cap.capability_id}' on_session_start failed: {e}",
                    capability_id=cap.capability_id,
                    error=str(e),
                    session_id=context.session_id,
                )

    async def on_session_end(self, context: AgentContext) -> dict[str, Any]:
        """
        Call on_session_end for all capabilities and collect statistics.

        Should be called when a practice session ends to allow
        capabilities to cleanup and report statistics.

        Args:
            context: AgentContext for the ending session

        Returns:
            Dictionary mapping capability_id to statistics dict.

        Example:
            stats = await runner.on_session_end(context)
            # {
            #     "fuzzy_detection": {"usage_count": 5, "detections": 3},
            #     "sales_stage": {"usage_count": 10, "stage_changes": 4}
            # }
        """
        logger.info(
            "Ending session for capabilities",
            session_id=context.session_id,
            capability_count=len(self.capabilities),
        )

        stats: dict[str, Any] = {}

        for cap in self.capabilities:
            try:
                cap_stats = await cap.on_session_end(context)
                stats[cap.capability_id] = cap_stats
            except (RuntimeError, ValueError, KeyError) as e:
                logger.error(
                    f"Capability '{cap.capability_id}' on_session_end failed: {e}",
                    capability_id=cap.capability_id,
                    error=str(e),
                    session_id=context.session_id,
                )
                stats[cap.capability_id] = {"error": str(e)}

        return stats

    def get_capability(self, capability_id: str) -> BaseCapability | None:
        """
        Get a capability instance by ID.

        Args:
            capability_id: The ID of the capability to retrieve

        Returns:
            The capability instance if found, None otherwise.
        """
        for cap in self.capabilities:
            if cap.capability_id == capability_id:
                return cap
        return None

    def has_capability(self, capability_id: str) -> bool:
        """
        Check if a capability is initialized in this runner.

        Args:
            capability_id: The ID of the capability to check

        Returns:
            True if the capability is initialized, False otherwise.
        """
        return any(cap.capability_id == capability_id for cap in self.capabilities)

    def list_capabilities(self) -> list[str]:
        """
        List all initialized capability IDs.

        Returns:
            List of capability IDs that are initialized in this runner.
        """
        return [cap.capability_id for cap in self.capabilities]

    def __len__(self) -> int:
        """Return the number of initialized capabilities."""
        return len(self.capabilities)

    def __repr__(self) -> str:
        """Return string representation of the runner."""
        cap_ids = ", ".join(self.list_capabilities())
        return f"<CapabilityRunner(capabilities=[{cap_ids}])>"
