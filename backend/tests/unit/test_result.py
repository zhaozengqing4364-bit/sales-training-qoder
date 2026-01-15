"""
Unit tests for Result type (T024)
Constitution Principle I: User Experience Never Interrupts
Tests should fail first (TDD), then implement features
"""
import pytest

from common.error_handling.result import Result


class TestResultType:
    """Test Result type for error-free returns"""

    def test_result_ok_creates_successful_result(self):
        """T024-P1: Should create successful result with value"""
        result = Result.ok("test_value")
        assert result.is_success is True
        assert result.value == "test_value"
        assert result.fallback is None

    def test_result_fail_creates_failed_result(self):
        """T024-P2: Should create failed result with fallback"""
        result = Result.fail("[USE_BROWSER_ASR]")
        assert result.is_success is False
        assert result.fallback == "[USE_BROWSER_ASR]"
        assert result.value is None

    def test_result_unwrap_returns_value_on_success(self):
        """T024-P3: Should unwrap value when successful"""
        result = Result.ok(42)
        assert result.unwrap() == 42

    def test_result_unwrap_raises_on_failure(self):
        """T024-P4: Should raise ValueError when unwrapping failed result"""
        result = Result.fail("error message")
        with pytest.raises(ValueError, match="Cannot unwrap failed result"):
            result.unwrap()

    def test_result_unwrap_or_returns_value_on_success(self):
        """T024-P5: Should return value when successful"""
        result = Result.ok("success")
        assert result.unwrap_or("default") == "success"

    def test_result_unwrap_or_returns_default_on_failure(self):
        """T024-P6: Should return default when failed"""
        result = Result.fail("error")
        assert result.unwrap_or("default") == "default"

    def test_result_map_transforms_success(self):
        """T024-P7: Should map value on success"""
        result = Result.ok(5)
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_success is True
        assert mapped.value == 10

    def test_result_map_preserves_failure(self):
        """T024-P8: Should preserve failure on map"""
        result = Result.fail("error")
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_success is False
        assert mapped.fallback == "error"

    def test_result_map_catches_exceptions(self):
        """T024-P9: Should catch exceptions in map function"""
        result = Result.ok("not a number")
        mapped = result.map(lambda x: int(x))
        assert mapped.is_success is False
        assert "invalid literal" in mapped.fallback

    def test_result_with_none_value(self):
        """T024-P10: Should handle None value correctly"""
        result = Result.ok(None)
        assert result.is_success is True
        assert result.value is None

    def test_result_generic_type_support(self):
        """T024-P11: Should support generic types"""
        str_result: Result[str] = Result.ok("test")
        int_result: Result[int] = Result.ok(42)
        assert isinstance(str_result.value, str)
        assert isinstance(int_result.value, int)
