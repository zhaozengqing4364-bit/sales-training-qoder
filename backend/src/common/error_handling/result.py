"""
Result type wrapper for error-free returns
Constitution Principle I: User Experience Never Interrupts
All functions should return Result instead of raising exceptions to user-facing code
"""
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar('T')


@dataclass
class Result(Generic[T]):
    """
    Result type for error handling without exceptions
    Always contains either a value or a fallback, never raises to user
    """
    value: T | None = None
    fallback: str | None = None
    is_success: bool = True

    @classmethod
    def ok(cls, value: T) -> 'Result[T]':
        """Create successful result"""
        return cls(value=value, is_success=True)

    @classmethod
    def fail(cls, fallback: str) -> 'Result[T]':
        """Create failed result with fallback message/action"""
        return cls(fallback=fallback, is_success=False)

    def unwrap(self) -> T:
        """Get value, raise error if failed (internal use only)"""
        if not self.is_success:
            raise ValueError(f"Cannot unwrap failed result: {self.fallback}")
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get value or default if failed"""
        return self.value if self.is_success else default

    def map(self, fn) -> 'Result':
        """Transform value if success, preserve failure"""
        if self.is_success and self.value is not None:
            try:
                return Result.ok(fn(self.value))
            except Exception as e:
                return Result.fail(str(e))
        return self
