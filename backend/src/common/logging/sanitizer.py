"""
Log Sanitizer - Prevent sensitive information leakage in logs

Implements Constitution Principle VI: Data privacy and compliance
- Masks API keys, passwords, tokens in log output
- Prevents accidental exposure of credentials
- GDPR/个保法 compliant logging

Requirements: P1-FIXES.md Issue #17
"""

import re
from re import Pattern
from typing import Any


class LogSanitizer:
    """
    Log sanitizer for masking sensitive information

    Patterns:
    - API keys (api_key, api-key)
    - Passwords
    - Tokens (JWT, Bearer)
    - Secrets
    - Authorization headers

    Usage:
        sanitized = LogSanitizer.sanitize_string(log_message)
        sanitized_dict = LogSanitizer.sanitize_dict(log_data)
    """

    # Sensitive field patterns (regex)
    SENSITIVE_PATTERNS: dict[str, Pattern] = {
        "api_key": re.compile(
            r'(api[_-]?key["\s:=]+)([a-zA-Z0-9-_]{20,})', re.IGNORECASE
        ),
        "password": re.compile(r'(password["\s:=]+)([^\s,}"]+)', re.IGNORECASE),
        "token": re.compile(r'(token["\s:=]+)([a-zA-Z0-9-_.]{20,})', re.IGNORECASE),
        "secret": re.compile(r'(secret["\s:=]+)([a-zA-Z0-9-_]{20,})', re.IGNORECASE),
        "authorization": re.compile(r"(Bearer\s+)([a-zA-Z0-9-_.]{20,})", re.IGNORECASE),
    }

    # Sensitive field names (exact match, case-insensitive)
    SENSITIVE_FIELDS = {
        "password",
        "api_key",
        "api-key",
        "secret_key",
        "secret-key",
        "access_token",
        "access-token",
        "refresh_token",
        "refresh-token",
        "private_key",
        "private-key",
        "credit_card",
        "credit-card",
        "jwt_secret",
        "jwt-secret",
        "database_url",
        "database-url",
        "auth_token",
        "auth-token",
        "bearer_token",
        "bearer-token",
    }

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """
        Sanitize a string by masking sensitive patterns

        Args:
            text: Input string that may contain sensitive data

        Returns:
            Sanitized string with sensitive data masked
        """
        if not text or not isinstance(text, str):
            return text

        result = text
        for pattern_name, pattern in cls.SENSITIVE_PATTERNS.items():
            result = pattern.sub(
                lambda m: f"{m.group(1)}{cls._mask(m.group(2))}", result
            )

        return result

    @classmethod
    def sanitize_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Sanitize a dictionary by masking sensitive fields

        Args:
            data: Dictionary that may contain sensitive fields

        Returns:
            Sanitized dictionary
        """
        if not isinstance(data, dict):
            return data

        result: dict[str, Any] = {}
        for key, value in data.items():
            key_lower = key.lower()

            # Check if key is a sensitive field
            if key_lower in cls.SENSITIVE_FIELDS:
                result[key] = cls._mask(str(value))
            elif isinstance(value, dict):
                result[key] = cls.sanitize_dict(value)
            elif isinstance(value, str):
                result[key] = cls.sanitize_string(value)
            elif isinstance(value, list):
                result[key] = cls._sanitize_list(value)
            else:
                result[key] = value

        return result

    @classmethod
    def _sanitize_list(cls, items: list[Any]) -> list[Any]:
        """Sanitize a list of items"""
        result: list[Any] = []
        for item in items:
            if isinstance(item, dict):
                result.append(cls.sanitize_dict(item))
            elif isinstance(item, str):
                result.append(cls.sanitize_string(item))
            elif isinstance(item, list):
                result.append(cls._sanitize_list(item))
            else:
                result.append(item)
        return result

    @staticmethod
    def _mask(value: str, show_chars: int = 4) -> str:
        """
        Mask a sensitive value

        Args:
            value: Value to mask
            show_chars: Number of characters to show at start

        Returns:
            Masked value (e.g., "abcd****")
        """
        if not value:
            return "***"

        if len(value) <= show_chars:
            return "***"

        return f"{value[:show_chars]}{'*' * (len(value) - show_chars)}"

    @classmethod
    def mask_database_url(cls, url: str) -> str:
        """
        Mask password in database URL

        Args:
            url: Database connection URL

        Returns:
            URL with password masked
        """
        if not url:
            return url

        # Pattern: protocol://user:password@host
        pattern = re.compile(r"(://[^:]+:)([^@]+)(@)")
        return pattern.sub(r"\1***\3", url)


# Convenience function for structlog integration
def sanitize_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Structlog processor for log sanitization

    Usage:
        structlog.configure(
            processors=[
                sanitize_processor,
                structlog.processors.JSONRenderer()
            ]
        )
    """
    return LogSanitizer.sanitize_dict(event_dict)
