"""Password reset service and email transport abstractions."""

from __future__ import annotations

import hashlib
import os
import secrets
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import pwd_context
from common.db.models import PasswordResetToken, User
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

PASSWORD_RESET_TOKEN_EXPIRY_MINUTES = 30
PASSWORD_RESET_MIN_LENGTH = 8


class InvalidResetPasswordTokenError(Exception):
    """Raised when a reset token is missing, expired, or already consumed."""


class EmailService(ABC):
    """Abstract email transport for password reset delivery."""

    @abstractmethod
    async def send_password_reset_email(self, *, recipient: str, reset_url: str) -> None:
        """Deliver a password-reset message to the recipient."""


class ConsoleEmailService(EmailService):
    """Development email transport that prints a local-only reset link to stdout."""

    async def send_password_reset_email(self, *, recipient: str, reset_url: str) -> None:
        print(
            "[MOCK EMAIL] password reset requested "
            f"recipient={_mask_email(recipient)} reset_link={reset_url}"
        )


class PasswordResetService:
    """Issues and consumes one-time password reset tokens."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        email_service: EmailService | None = None,
        frontend_base_url: str | None = None,
    ) -> None:
        self.db = db
        self.email_service = email_service or ConsoleEmailService()
        self.frontend_base_url = frontend_base_url or os.getenv(
            "PASSWORD_RESET_BASE_URL",
            "/reset-password",
        )

    async def request_password_reset(self, email: str) -> None:
        normalized_email = email.strip().lower()
        result = await self.db.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        if user is None or not getattr(user, "is_active", False):
            return

        now = datetime.now(UTC)
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_reset_token(raw_token)
        expires_at = now + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRY_MINUTES)

        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == str(user.user_id),
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )

        reset_token = PasswordResetToken(
            user_id=str(user.user_id),
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(reset_token)
        await self.db.commit()
        await self.db.refresh(reset_token)

        logger.info(
            "Password reset token issued",
            user_id=str(user.user_id),
            token_id=str(reset_token.id),
            expires_at=expires_at.isoformat(),
        )

        await self.email_service.send_password_reset_email(
            recipient=normalized_email,
            reset_url=self._build_reset_url(raw_token),
        )

    async def reset_password(self, token: str, new_password: str) -> None:
        normalized_token = token.strip()
        if not normalized_token:
            raise InvalidResetPasswordTokenError("missing token")
        if len(new_password) < PASSWORD_RESET_MIN_LENGTH:
            raise ValueError(f"密码至少需要 {PASSWORD_RESET_MIN_LENGTH} 个字符")

        token_hash = self._hash_reset_token(normalized_token)
        now = datetime.now(UTC)

        result = await self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        reset_token = result.scalar_one_or_none()

        if (
            reset_token is None
            or reset_token.used_at is not None
            or self._coerce_utc(reset_token.expires_at) <= now
        ):
            raise InvalidResetPasswordTokenError("invalid or expired token")

        result = await self.db.execute(
            select(User).where(User.user_id == str(reset_token.user_id))
        )
        user = result.scalar_one_or_none()
        if user is None or not getattr(user, "is_active", False):
            raise InvalidResetPasswordTokenError("missing active user")

        user.hashed_password = pwd_context.hash(new_password)
        reset_token.used_at = now
        await self.db.commit()

        logger.info(
            "Password reset token consumed",
            user_id=str(user.user_id),
            token_id=str(reset_token.id),
        )

    def _build_reset_url(self, token: str) -> str:
        base = self.frontend_base_url.rstrip("/")
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}token={token}"

    @staticmethod
    def _hash_reset_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _mask_email(email: str) -> str:
    local_part, _, domain_part = email.partition("@")
    if not domain_part:
        return "***"
    if len(local_part) <= 2:
        masked_local = f"{local_part[:1]}***"
    else:
        masked_local = f"{local_part[:2]}***"
    return f"{masked_local}@{domain_part}"
