"""
Unit tests for Capability Base Module

Tests for:
- CapabilityResult: Result container for capability execution
- BaseCapability: Abstract base class for capabilities
- CapabilityRegistry: Singleton registry for capability modules
- CapabilityRunner: Capability lifecycle and execution manager

References:
- Requirements: R6, R7, R8 (Capability modules)
- Design: Section 1-3 (AgentContext, CapabilityRegistry, CapabilityRunner)
import asyncio
from typing import Any

import pytest

from agent.capabilities.base import BaseCapability, CapabilityResult
from agent.capabilities.registry import CapabilityRegistry
from agent.capabilities.runner import CapabilityRunner
from agent.context import AgentContext


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_context() -> AgentContext:
    """Create a sample AgentContext for testing."""
    return AgentContext(
        session_id="test-session-123",
        agent_id="test-agent-456",
        persona_id="test-persona-789",
        user_id="test-user-001",
        agent_config={
            "capabilities_config": {
                "test_capability": {"enabled": True, "param1": "value1"},
                "disabled_capability": {"enabled": False},
            }
        },
        persona_config={
            "test_capability": {"param1": "override_value"},
        },
    )


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the registry before and after each test."""
    CapabilityRegistry.clear()
    yield
    CapabilityRegistry.clear()


# =============================================================================
# Test CapabilityResult
# =============================================================================


class TestCapabilityResult:
    """Tests for CapabilityResult dataclass."""

    def test_successful_result_creation(self):
        """Should create successful result with data."""
        result = CapabilityResult(
            success=True,
            data={"detections": [{"category": "uncertain"}]},
        )
        assert result.success is True
        assert result.data == {"detections": [{"category": "uncertain"}]}
        assert result.should_interrupt is False
        assert result.fallback is None

    def test_failed_result_sets_default_fallback(self):
        """Should set default fallback code when success=False."""
        result = CapabilityResult(success=False)
        assert result.success is False
        assert result.fallback == "[CAPABILITY_ERROR]"

    def test_failed_result_preserves_custom_fallback(self):
        """Should preserve custom fallback code."""
        result = CapabilityResult(success=False, fallback="[TIMEOUT]")
        assert result.fallback == "[TIMEOUT]"

    def test_result_with_interrupt_flag(self):
        """Should handle should_interrupt flag."""
        result = CapabilityResult(
            success=True,
            data={"severity": "high"},
            should_interrupt=True,
        )
        assert result.should_interrupt is True

    def test_result_with_feedback(self):
        """Should handle feedback message."""
        result = CapabilityResult(
            success=True,
            feedback="检测到模糊表达",
        )
        assert result.feedback == "检测到模糊表达"

    def test_to_dict_minimal(self):
        """Should convert minimal result to dict."""
        result = CapabilityResult(success=True)
        d = result.to_dict()
        assert d == {"success": True}

    def test_to_dict_full(self):
        """Should convert full result to dict."""
        result = CapabilityResult(
            success=True,
            data={"key": "value"},
            should_interrupt=True,
            feedback="test feedback",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == {"key": "value"}
        assert d["should_interrupt"] is True
        assert d["feedback"] == "test feedback"

    def test_to_dict_failed_includes_fallback(self):
        """Should include fallback in dict for failed results."""
        result = CapabilityResult(success=False, fallback="[ERROR]")
        d = result.to_dict()
        assert d["fallback"] == "[ERROR]"


# =============================================================================
# Test BaseCapability
# =============================================================================


class TestBaseCapability:
    """Tests for BaseCapability abstract base class."""

    def test_capability_initialization(self):
        """Should initialize capability with config."""

        class TestCapability(BaseCapability):
            capability_id = "test"
            name = "Test Capability"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        cap = TestCapability({"enabled": True, "param": "value"})
        assert cap.config == {"enabled": True, "param": "value"}

    def test_is_enabled_default_true(self):
        """Should return True when enabled not specified."""

        class TestCapability(BaseCapability):
            capability_id = "test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        cap = TestCapability({})
        assert cap.is_enabled() is True

    def test_is_enabled_explicit_false(self):
        """Should return False when explicitly disabled."""

        class TestCapability(BaseCapability):
            capability_id = "test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        cap = TestCapability({"enabled": False})
        assert cap.is_enabled() is False

    def test_get_config_value_with_default(self):
        """Should return default when key not found."""

        class TestCapability(BaseCapability):
            capability_id = "test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        cap = TestCapability({"key1": "value1"})
        assert cap.get_config_value("key1") == "value1"
        assert cap.get_config_value("missing", "default") == "default"

    def test_validate_config_rejects_non_dict(self):
        """Should reject non-dict config."""

        class TestCapability(BaseCapability):
            capability_id = "test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        with pytest.raises(ValueError, match="Config must be a dictionary"):
            TestCapability("not a dict")

    @pytest.mark.asyncio
    async def test_on_session_start_sets_initialized(self, sample_context):
        """Should mark capability as initialized in context state."""

        class TestCapability(BaseCapability):
            capability_id = "test_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        cap = TestCapability({})
        await cap.on_session_start(sample_context)
        assert sample_context.state.get("test_cap_initialized") is True

    @pytest.mark.asyncio
    async def test_on_session_end_returns_usage_count(self, sample_context):
        """Should return usage count in session end stats."""

        class TestCapability(BaseCapability):
            capability_id = "test_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        cap = TestCapability({})
        sample_context.state["test_cap_count"] = 5
        stats = await cap.on_session_end(sample_context)
        assert stats == {"usage_count": 5}

    def test_update_usage_count(self, sample_context):
        """Should increment usage counter."""

        class TestCapability(BaseCapability):
            capability_id = "test_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        cap = TestCapability({})
        assert sample_context.state.get("test_cap_count", 0) == 0
        cap._update_usage_count(sample_context)
        assert sample_context.state["test_cap_count"] == 1
        cap._update_usage_count(sample_context)
        assert sample_context.state["test_cap_count"] == 2

    def test_repr(self):
        """Should return readable string representation."""

        class TestCapability(BaseCapability):
            capability_id = "test_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        cap = TestCapability({"enabled": True})
        assert "TestCapability" in repr(cap)
        assert "test_cap" in repr(cap)


# =============================================================================
# Test CapabilityRegistry
# =============================================================================


class TestCapabilityRegistry:
    """Tests for CapabilityRegistry singleton."""

    def test_register_capability(self):
        """Should register capability class."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "test_register"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        assert CapabilityRegistry.is_registered("test_register")
        assert CapabilityRegistry.get("test_register") is TestCapability

    def test_register_rejects_empty_id(self):
        """Should reject capability with empty ID."""
        with pytest.raises(ValueError, match="non-empty capability_id"):

            @CapabilityRegistry.register
            class BadCapability(BaseCapability):
                capability_id = ""

                async def execute(self, context, input_data):
                    return CapabilityResult(success=True)

    def test_register_rejects_duplicate_id(self):
        """Should reject duplicate capability ID from different class."""

        @CapabilityRegistry.register
        class FirstCapability(BaseCapability):
            capability_id = "duplicate_test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        with pytest.raises(ValueError, match="already registered"):

            @CapabilityRegistry.register
            class SecondCapability(BaseCapability):
                capability_id = "duplicate_test"

                async def execute(self, context, input_data):
                    return CapabilityResult(success=True)

    def test_register_allows_same_class_reregistration(self):
        """Should allow re-registration of the same class."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "reregister_test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        # Re-register same class should not raise
        CapabilityRegistry.register(TestCapability)
        assert CapabilityRegistry.count() == 1

    def test_unregister_capability(self):
        """Should unregister capability."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "unregister_test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        assert CapabilityRegistry.unregister("unregister_test") is True
        assert CapabilityRegistry.is_registered("unregister_test") is False

    def test_unregister_nonexistent_returns_false(self):
        """Should return False when unregistering nonexistent capability."""
        assert CapabilityRegistry.unregister("nonexistent") is False

    def test_get_returns_none_for_unknown(self):
        """Should return None for unknown capability ID."""
        assert CapabilityRegistry.get("unknown") is None

    def test_list_all(self):
        """Should list all registered capability IDs."""

        @CapabilityRegistry.register
        class Cap1(BaseCapability):
            capability_id = "cap1"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        @CapabilityRegistry.register
        class Cap2(BaseCapability):
            capability_id = "cap2"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        ids = CapabilityRegistry.list_all()
        assert "cap1" in ids
        assert "cap2" in ids

    def test_get_metadata(self):
        """Should return capability metadata."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "metadata_test"
            name = "Test Name"
            description = "Test Description"
            config_schema = {"type": "object"}

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        metadata = CapabilityRegistry.get_metadata("metadata_test")
        assert metadata["id"] == "metadata_test"
        assert metadata["name"] == "Test Name"
        assert metadata["description"] == "Test Description"
        assert metadata["config_schema"] == {"type": "object"}

    def test_get_metadata_returns_none_for_unknown(self):
        """Should return None for unknown capability."""
        assert CapabilityRegistry.get_metadata("unknown") is None

    def test_count(self):
        """Should return correct count of registered capabilities."""
        assert CapabilityRegistry.count() == 0

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "count_test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        assert CapabilityRegistry.count() == 1

    def test_clear(self):
        """Should clear all registered capabilities."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "clear_test"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        assert CapabilityRegistry.count() == 1
        CapabilityRegistry.clear()
        assert CapabilityRegistry.count() == 0


# =============================================================================
# Test CapabilityRunner
# =============================================================================


class TestCapabilityRunner:
    """Tests for CapabilityRunner."""

    def test_init_with_no_capabilities(self):
        """Should initialize with empty capabilities list."""
        runner = CapabilityRunner(agent_config={})
        assert len(runner) == 0

    def test_init_skips_disabled_capabilities(self):
        """Should skip disabled capabilities."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "disabled_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "disabled_cap": {"enabled": False},
                }
            }
        )
        assert len(runner) == 0

    def test_init_creates_enabled_capabilities(self):
        """Should create instances for enabled capabilities."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "enabled_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "enabled_cap": {"enabled": True},
                }
            }
        )
        assert len(runner) == 1
        assert runner.has_capability("enabled_cap")

    def test_init_merges_persona_config(self):
        """Should merge Persona configuration overrides."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "merge_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "merge_cap": {"enabled": True, "param1": "agent_value"},
                }
            },
            persona_config={
                "merge_cap": {"param1": "persona_value", "param2": "new_value"},
            },
        )
        cap = runner.get_capability("merge_cap")
        assert cap.config["param1"] == "persona_value"
        assert cap.config["param2"] == "new_value"

    @pytest.mark.asyncio
    async def test_run_all_returns_results(self, sample_context):
        """Should return results from all capabilities."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "run_all_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True, data={"input": input_data})

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "run_all_cap": {"enabled": True},
                }
            }
        )
        results = await runner.run_all(sample_context, "test input")
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].data["input"] == "test input"

    @pytest.mark.asyncio
    async def test_run_all_handles_exceptions(self, sample_context):
        """Should handle capability exceptions gracefully."""

        @CapabilityRegistry.register
        class FailingCapability(BaseCapability):
            capability_id = "failing_cap"

            async def execute(self, context, input_data):
                raise RuntimeError("Test error")

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "failing_cap": {"enabled": True},
                }
            }
        )
        results = await runner.run_all(sample_context, "test")
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].fallback == "[CAPABILITY_RUNTIME_ERROR]"

    @pytest.mark.asyncio
    async def test_run_all_converts_connection_errors(self, sample_context):
        """Should degrade infrastructure failures without breaking the pipeline."""

        @CapabilityRegistry.register
        class ConnectionFailingCapability(BaseCapability):
            capability_id = "connection_failing_cap"

            async def execute(self, context, input_data):
                raise ConnectionError("knowledge service disconnected")

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "connection_failing_cap": {"enabled": True},
                }
            }
        )

        results = await runner.run_all(sample_context, "test")

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].fallback == "[CAPABILITY_CONNECTION_ERROR]"

    @pytest.mark.asyncio
    async def test_run_all_propagates_cancelled_error(self, sample_context):
        """Should not disguise task cancellation as a capability failure."""

        @CapabilityRegistry.register
        class CancelledCapability(BaseCapability):
            capability_id = "cancelled_cap"

            async def execute(self, context, input_data):
                raise asyncio.CancelledError()

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "cancelled_cap": {"enabled": True},
                }
            }
        )

        with pytest.raises(asyncio.CancelledError):
            await runner.run_all(sample_context, "test")

    @pytest.mark.asyncio
    async def test_run_all_empty_returns_empty_list(self, sample_context):
        """Should return empty list when no capabilities."""
        runner = CapabilityRunner(agent_config={})
        results = await runner.run_all(sample_context, "test")
        assert results == []

    @pytest.mark.asyncio
    async def test_run_one_executes_single_capability(self, sample_context):
        """Should execute a single capability by ID."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "run_one_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True, data={"ran": True})

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "run_one_cap": {"enabled": True},
                }
            }
        )
        result = await runner.run_one("run_one_cap", sample_context, "test")
        assert result.success is True
        assert result.data["ran"] is True

    @pytest.mark.asyncio
    async def test_run_one_converts_os_errors(self, sample_context):
        """Should return a failure result for expected OS/service failures."""

        @CapabilityRegistry.register
        class OSErrorCapability(BaseCapability):
            capability_id = "os_error_cap"

            async def execute(self, context, input_data):
                raise OSError("socket reset")

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "os_error_cap": {"enabled": True},
                }
            }
        )

        result = await runner.run_one("os_error_cap", sample_context, "test")

        assert result is not None
        assert result.success is False
        assert result.fallback == "[CAPABILITY_ERROR]"

    @pytest.mark.asyncio
    async def test_run_one_returns_none_for_unknown(self, sample_context):
        """Should return None for unknown capability ID."""
        runner = CapabilityRunner(agent_config={})
        result = await runner.run_one("unknown", sample_context, "test")
        assert result is None

    @pytest.mark.asyncio
    async def test_on_session_start_calls_all_capabilities(self, sample_context):
        """Should call on_session_start for all capabilities."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "session_start_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "session_start_cap": {"enabled": True},
                }
            }
        )
        await runner.on_session_start(sample_context)
        assert sample_context.state.get("session_start_cap_initialized") is True

    @pytest.mark.asyncio
    async def test_on_session_end_collects_stats(self, sample_context):
        """Should collect stats from all capabilities."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "session_end_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "session_end_cap": {"enabled": True},
                }
            }
        )
        sample_context.state["session_end_cap_count"] = 3
        stats = await runner.on_session_end(sample_context)
        assert "session_end_cap" in stats
        assert stats["session_end_cap"]["usage_count"] == 3

    def test_list_capabilities(self):
        """Should list all initialized capability IDs."""

        @CapabilityRegistry.register
        class Cap1(BaseCapability):
            capability_id = "list_cap1"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        @CapabilityRegistry.register
        class Cap2(BaseCapability):
            capability_id = "list_cap2"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "list_cap1": {"enabled": True},
                    "list_cap2": {"enabled": True},
                }
            }
        )
        caps = runner.list_capabilities()
        assert "list_cap1" in caps
        assert "list_cap2" in caps

    def test_repr(self):
        """Should return readable string representation."""

        @CapabilityRegistry.register
        class TestCapability(BaseCapability):
            capability_id = "repr_cap"

            async def execute(self, context, input_data):
                return CapabilityResult(success=True)

        runner = CapabilityRunner(
            agent_config={
                "capabilities_config": {
                    "repr_cap": {"enabled": True},
                }
            }
        )
        assert "CapabilityRunner" in repr(runner)
        assert "repr_cap" in repr(runner)
