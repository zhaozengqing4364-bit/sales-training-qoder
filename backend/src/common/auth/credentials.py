"""Shared managed-credential helpers without persistence side effects."""

from __future__ import annotations

import os
import secrets


def temporary_password_ttl_hours() -> int:
    raw = os.getenv("AUTH_TEMPORARY_PASSWORD_TTL_HOURS", "72").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 72


def generate_temporary_password() -> str:
    while True:
        value = secrets.token_urlsafe(15)
        if any(char.isalpha() for char in value) and any(
            char.isdigit() for char in value
        ):
            return value


def normalize_email(value: object) -> str:
    return str(value or "").strip().lower()
