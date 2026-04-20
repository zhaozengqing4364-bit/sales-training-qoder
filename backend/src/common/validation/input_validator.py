"""
Input Validator - Prevent SQL injection and validate user inputs

Implements Constitution Principle VI: Data privacy and compliance
- Validates user input to prevent SQL injection
- Sanitizes search keywords
- Enforces input length limits

Requirements: P1-FIXES.md Issue #21
"""

import re


class InputValidator:
    """
    Input validator for preventing SQL injection and other attacks

    Features:
    - Alphanumeric validation
    - Email validation
    - SQL injection detection
    - Search keyword sanitization

    Usage:
        # Validate alphanumeric
        safe_id = InputValidator.validate_alphanumeric(user_input)

        # Sanitize search keyword
        safe_keyword = InputValidator.sanitize_search_keyword(keyword)

        # Check for SQL injection
        if InputValidator.contains_sql_injection(user_input):
            raise ValueError("Invalid input")
    """

    # Allowed alphanumeric pattern
    ALPHANUMERIC_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    # Email pattern (basic)
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    # UUID pattern
    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    # SQL keywords that may indicate injection
    SQL_KEYWORDS: set[str] = {
        "select",
        "insert",
        "update",
        "delete",
        "drop",
        "create",
        "alter",
        "exec",
        "execute",
        "union",
        "script",
        "--",
        ";",
        "or",
        "and",
        "where",
        "from",
        "table",
        "database",
        "grant",
        "revoke",
        "truncate",
        "merge",
        "call",
    }

    # Dangerous characters
    DANGEROUS_CHARS = {";", "--", "/*", "*/", "'", '"', "\\", "%", "_"}

    @classmethod
    def validate_alphanumeric(
        cls, value: str, field_name: str = "field", max_length: int = 100
    ) -> str:
        """
        Validate that value contains only alphanumeric characters

        Args:
            value: Input value
            field_name: Name of field for error message
            max_length: Maximum allowed length

        Returns:
            Validated value

        Raises:
            ValueError: If validation fails
        """
        if not value:
            raise ValueError(f"{field_name} cannot be empty")

        if len(value) > max_length:
            raise ValueError(f"{field_name} exceeds maximum length of {max_length}")

        if not cls.ALPHANUMERIC_PATTERN.match(value):
            raise ValueError(
                f"{field_name} can only contain letters, numbers, underscores, and hyphens"
            )

        return value

    @classmethod
    def validate_uuid(cls, value: str, field_name: str = "id") -> str:
        """
        Validate UUID format

        Args:
            value: Input value
            field_name: Name of field for error message

        Returns:
            Validated UUID string

        Raises:
            ValueError: If validation fails
        """
        if not value:
            raise ValueError(f"{field_name} cannot be empty")

        if not cls.UUID_PATTERN.match(value):
            raise ValueError(f"{field_name} must be a valid UUID")

        return value.lower()

    @classmethod
    def validate_email(cls, value: str) -> str:
        """
        Validate email format

        Args:
            value: Email address

        Returns:
            Validated email

        Raises:
            ValueError: If validation fails
        """
        if not value:
            raise ValueError("Email cannot be empty")

        if len(value) > 254:
            raise ValueError("Email is too long")

        if not cls.EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email format")

        return value.lower()

    @classmethod
    def contains_sql_injection(cls, value: str) -> bool:
        """
        Check if value contains potential SQL injection

        Args:
            value: Input value to check

        Returns:
            True if SQL injection detected
        """
        if not value:
            return False

        value_lower = value.lower()

        # Check for SQL keywords
        for keyword in cls.SQL_KEYWORDS:
            if keyword in value_lower:
                return True

        # Check for dangerous patterns
        dangerous_patterns = [
            r"\bOR\b.*=.*\b",  # OR 1=1
            r"\bAND\b.*=.*\b",  # AND 1=1
            r"'\s*OR\s*'",  # ' OR '
            r'"\s*OR\s*"',  # " OR "
            r";\s*\w+",  # ; DROP
            r"--\s*$",  # -- comment
            r"/\*",  # /* comment
            r"\*/",  # */ comment
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True

        return False

    @classmethod
    def sanitize_search_keyword(cls, keyword: str, max_length: int = 100) -> str:
        """
        Sanitize search keyword for safe use in LIKE queries

        Args:
            keyword: Search keyword
            max_length: Maximum allowed length

        Returns:
            Sanitized keyword

        Raises:
            ValueError: If keyword contains SQL injection
        """
        if not keyword:
            return ""

        # Check length
        if len(keyword) > max_length:
            raise ValueError(f"Search keyword exceeds maximum length of {max_length}")

        # Check for SQL injection
        if cls.contains_sql_injection(keyword):
            raise ValueError("Search keyword contains invalid characters")

        # Escape special LIKE characters
        sanitized = keyword.replace("%", r"\%")
        sanitized = sanitized.replace("_", r"\_")

        return sanitized

    @classmethod
    def sanitize_string(
        cls, value: str, max_length: int = 1000, allow_newlines: bool = False
    ) -> str:
        """
        Sanitize a general string input

        Args:
            value: Input string
            max_length: Maximum allowed length
            allow_newlines: Whether to allow newlines

        Returns:
            Sanitized string
        """
        if not value:
            return ""

        # Trim whitespace
        value = value.strip()

        # Check length
        if len(value) > max_length:
            value = value[:max_length]

        # Remove null bytes
        value = value.replace("\x00", "")

        # Handle newlines
        if not allow_newlines:
            value = value.replace("\n", " ").replace("\r", "")

        return value

    @classmethod
    def validate_sort_field(cls, field: str, allowed_fields: set[str]) -> str:
        """
        Validate sort field against allowed fields

        Args:
            field: Sort field name
            allowed_fields: Set of allowed field names

        Returns:
            Validated field name

        Raises:
            ValueError: If field not allowed
        """
        if not field:
            raise ValueError("Sort field cannot be empty")

        # Remove potential direction suffix
        clean_field = field.lstrip("-+")

        if clean_field not in allowed_fields:
            raise ValueError(f"Invalid sort field: {field}")

        return field


# Convenience functions for common validations
def validate_id(value: str) -> str:
    """Validate ID (UUID or alphanumeric)"""
    try:
        return InputValidator.validate_uuid(value)
    except ValueError:
        return InputValidator.validate_alphanumeric(value, "id")


def validate_search_keyword(keyword: str) -> str:
    """Validate and sanitize search keyword"""
    return InputValidator.sanitize_search_keyword(keyword)
