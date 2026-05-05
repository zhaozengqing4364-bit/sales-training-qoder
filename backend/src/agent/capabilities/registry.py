"""
CapabilityRegistry - Singleton Registry for Capability Modules

Provides a centralized registry for discovering and instantiating capability
modules. Capabilities register themselves using the @CapabilityRegistry.register
decorator, enabling dynamic discovery and configuration.

References:
- Requirements: R6, R7, R8 (Capability modules)
- Design: Section 2 (CapabilityRegistry)

Usage:
    # Register a capability using decorator
    @CapabilityRegistry.register
    class FuzzyDetectionCapability(BaseCapability):
        capability_id = "fuzzy_detection"
        ...

    # Get a capability class by ID
    cap_class = CapabilityRegistry.get("fuzzy_detection")
    if cap_class:
        instance = cap_class(config)

    # List all registered capabilities
    all_ids = CapabilityRegistry.list_all()

    # Get capability metadata
    metadata = CapabilityRegistry.get_metadata("fuzzy_detection")
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from common.monitoring.logger import get_logger

if TYPE_CHECKING:
    from .base import BaseCapability

logger = get_logger(__name__)


class CapabilityRegistry:
    """
    Singleton registry for capability modules.

    This class maintains a global registry of all available capability classes,
    allowing dynamic discovery and instantiation based on configuration.

    The registry uses class methods to provide singleton-like behavior without
    requiring explicit instantiation. Thread-safe for concurrent access.

    Class Attributes:
        _capabilities: Dictionary mapping capability_id to capability class
        _initialized: Flag to track if registry has been initialized
        _lock: Threading lock for thread-safe operations

    Example:
        # Registration (typically in capability module)
        @CapabilityRegistry.register
        class MyCapability(BaseCapability):
            capability_id = "my_capability"
            name = "My Capability"
            ...

        # Discovery and instantiation
        cap_class = CapabilityRegistry.get("my_capability")
        if cap_class:
            instance = cap_class({"enabled": True})
    """

    _capabilities: dict[str, type[BaseCapability]] = {}
    _initialized: bool = False
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def register(cls, capability_class: type[BaseCapability]) -> type[BaseCapability]:
        """
        Register a capability class with the registry.

        This method can be used as a decorator to automatically register
        capability classes when they are defined. Thread-safe.

        Args:
            capability_class: The capability class to register. Must have a
                            valid capability_id class attribute.

        Returns:
            The registered capability class (unchanged), allowing use as decorator.

        Raises:
            ValueError: If capability_id is empty or already registered.

        Example:
            @CapabilityRegistry.register
            class FuzzyDetectionCapability(BaseCapability):
                capability_id = "fuzzy_detection"
                ...
        """
        capability_id = getattr(capability_class, "capability_id", "")

        if not capability_id:
            raise ValueError(
                f"Capability class {capability_class.__name__} "
                "must have a non-empty capability_id"
            )

        with cls._lock:
            if capability_id in cls._capabilities:
                existing = cls._capabilities[capability_id]
                # Allow re-registration of the same class (e.g., during module reload)
                if existing is not capability_class:
                    raise ValueError(
                        f"Capability ID '{capability_id}' is already "
                        f"registered by {existing.__name__}"
                    )
                logger.debug(
                    f"Capability '{capability_id}' re-registered (same class)",
                    capability_id=capability_id,
                )
                return capability_class

            cls._capabilities[capability_id] = capability_class
            logger.info(
                f"Registered capability: {capability_id}",
                capability_id=capability_id,
                class_name=capability_class.__name__,
            )

        return capability_class

    @classmethod
    def unregister(cls, capability_id: str) -> bool:
        """
        Unregister a capability from the registry.

        Primarily used for testing or dynamic capability management. Thread-safe.

        Args:
            capability_id: The ID of the capability to unregister.

        Returns:
            True if the capability was unregistered, False if not found.
        """
        with cls._lock:
            if capability_id in cls._capabilities:
                del cls._capabilities[capability_id]
                logger.info(
                    f"Unregistered capability: {capability_id}",
                    capability_id=capability_id,
                )
                return True
        return False

    @classmethod
    def get(cls, capability_id: str) -> type[BaseCapability] | None:
        """
        Get a capability class by its ID. Thread-safe.

        Args:
            capability_id: The unique identifier of the capability.

        Returns:
            The capability class if found, None otherwise.

        Example:
            cap_class = CapabilityRegistry.get("fuzzy_detection")
            if cap_class:
                instance = cap_class(config)
        """
        with cls._lock:
            return cls._capabilities.get(capability_id)

    @classmethod
    def list_all(cls) -> list[str]:
        """
        List all registered capability IDs. Thread-safe.

        Returns:
            List of capability IDs in registration order.

        Example:
            ids = CapabilityRegistry.list_all()
            # ['fuzzy_detection', 'sales_stage', 'realtime_scoring']
        """
        with cls._lock:
            return list(cls._capabilities.keys())

    @classmethod
    def get_all(cls) -> dict[str, type[BaseCapability]]:
        """
        Get all registered capability classes. Thread-safe.

        Returns:
            Dictionary mapping capability_id to capability class.

        Example:
            all_caps = CapabilityRegistry.get_all()
            for cap_id, cap_class in all_caps.items():
                logger.info("%s: %s", cap_id, cap_class.name)
        """
        with cls._lock:
            return cls._capabilities.copy()

    @classmethod
    def get_metadata(cls, capability_id: str) -> dict[str, Any] | None:
        """
        Get metadata for a registered capability. Thread-safe.

        Returns capability class attributes useful for UI display
        and configuration.

        Args:
            capability_id: The unique identifier of the capability.

        Returns:
            Dictionary with capability metadata, or None if not found.
            Includes: id, name, description, config_schema

        Example:
            metadata = CapabilityRegistry.get_metadata("fuzzy_detection")
            # {
            #     "id": "fuzzy_detection",
            #     "name": "模糊词检测",
            #     "description": "检测用户语音中的模糊表达",
            #     "config_schema": {...}
            # }
        """
        with cls._lock:
            cap_class = cls._capabilities.get(capability_id)
            if cap_class is None:
                return None

            return {
                "id": cap_class.capability_id,
                "name": getattr(cap_class, "name", ""),
                "description": getattr(cap_class, "description", ""),
                "config_schema": getattr(cap_class, "config_schema", {}),
            }

    @classmethod
    def list_metadata(cls) -> list[dict[str, Any]]:
        """
        Get metadata for all registered capabilities. Thread-safe.

        Returns:
            List of metadata dictionaries for all capabilities.

        Example:
            all_metadata = CapabilityRegistry.list_metadata()
            for meta in all_metadata:
                logger.info("%s: %s", meta["name"], meta["description"])
        """
        with cls._lock:
            return [
                {
                    "id": cap_class.capability_id,
                    "name": getattr(cap_class, "name", ""),
                    "description": getattr(cap_class, "description", ""),
                    "config_schema": getattr(cap_class, "config_schema", {}),
                }
                for cap_class in cls._capabilities.values()
            ]

    @classmethod
    def is_registered(cls, capability_id: str) -> bool:
        """
        Check if a capability is registered. Thread-safe.

        Args:
            capability_id: The unique identifier to check.

        Returns:
            True if registered, False otherwise.
        """
        with cls._lock:
            return capability_id in cls._capabilities

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered capabilities. Thread-safe.

        WARNING: This is primarily for testing. Use with caution in production.
        """
        with cls._lock:
            cls._capabilities.clear()
            logger.warning("Capability registry cleared")

    @classmethod
    def count(cls) -> int:
        """
        Get the number of registered capabilities. Thread-safe.

        Returns:
            Number of registered capabilities.
        """
        with cls._lock:
            return len(cls._capabilities)
