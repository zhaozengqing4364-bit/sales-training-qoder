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
PASSWORD_RESET_RATE_LIMIT_CALLS = 1
PASSWORD_RESET_RATE_LIMIT_PERIOD_SECONDS = 60
PASSWORD_RESET_DELIVERY_STATUS_PENDING = "pending"
PASSWORD_RESET_DELIVERY_STATUS_SENT = "sent"
PASSWORD_RESET_DELIVERY_STATUS_FAILED = "failed"
PASSWORD_RESET_INVALIDATION_REASON_SUPERSEDED = "superseded"
PASSWORD_RESET_INVALIDATION_REASON_EXPIRED = "expired"
PASSWORD_RESET_ERROR_MAX_LENGTH = 240


class InvalidResetPasswordTokenError(Exception):
    """Raised when a reset token is missing, expired, revoked, or already consumed."""


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


def build_password_reset_email_service() -> EmailService:
    """Resolve the configured password-reset delivery transport."""
    transport = os.getenv("PASSWORD_RESET_EMAIL_TRANSPORT", "console").strip().lower()
    if transport in {"", "console"}:
        return ConsoleEmailService()

    logger.warning(
        "Unknown password reset email transport; falling back to console",
        transport=transport,
    )
    return ConsoleEmailService()


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
        self.email_service = email_service or build_password_reset_email_service()
        self.frontend_base_url = frontend_base_url or os.getenv(
            "PASSWORD_RESET_BASE_URL",
            "/reset-password",
        )

    async def request_password_reset(self, email: str) -> None:
        normalized_email = email.strip().lower()
        result = await self.db.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        if user is None or not getattr(user, "is_active", False):
            logger.info("Password reset requested for unknown or inactive account")
            return

        now = datetime.now(UTC)
        user_id = str(user.user_id)
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_reset_token(raw_token)
        expires_at = now + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRY_MINUTES)

        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.invalidated_at.is_(None),
            )
            .values(
                invalidated_at=now,
                invalidation_reason=PASSWORD_RESET_INVALIDATION_REASON_SUPERSEDED,
            )
        )

        reset_token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            delivery_status=PASSWORD_RESET_DELIVERY_STATUS_PENDING,
        )
        self.db.add(reset_token)
        await self.db.commit()
        await self.db.refresh(reset_token)

        logger.info(
            "Password reset token issued",
            user_id=user_id,
            token_id=str(reset_token.id),
            expires_at=expires_at.isoformat(),
        )

        await self._deliver_reset_email(
            reset_token=reset_token,
            recipient=normalized_email,
            raw_token=raw_token,
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

        if reset_token is None:
            logger.warning("Password reset rejected: token not found")
            raise InvalidResetPasswordTokenError("missing token")

        if reset_token.used_at is not None:
            logger.warning(
                "Password reset rejected: token already consumed",
                token_id=str(reset_token.id),
            )
            raise InvalidResetPasswordTokenError("consumed token")

        if reset_token.invalidated_at is not None:
            logger.warning(
                "Password reset rejected: token already invalidated",
                token_id=str(reset_token.id),
                reason=reset_token.invalidation_reason,
            )
            raise InvalidResetPasswordTokenError("revoked token")

        if self._coerce_utc(reset_token.expires_at) <= now:
            reset_token.invalidated_at = now
            reset_token.invalidation_reason = PASSWORD_RESET_INVALIDATION_REASON_EXPIRED
            await self.db.commit()
            logger.info(
                "Password reset token expired",
                token_id=str(reset_token.id),
                user_id=str(reset_token.user_id),
            )
            raise InvalidResetPasswordTokenError("expired token")

        result = await self.db.execute(
            select(User).where(User.user_id == str(reset_token.user_id))
        )
        user = result.scalar_one_or_none()
        if user is None or not getattr(user, "is_active", False):
            logger.warning(
                "Password reset rejected: token user missing or inactive",
                token_id=str(reset_token.id),
                user_id=str(reset_token.user_id),
            )
            raise InvalidResetPasswordTokenError("missing active user")

        user.hashed_password = pwd_context.hash(new_password)
        reset_token.used_at = now
        await self.db.commit()

        logger.info(
            "Password reset token consumed",
            user_id=str(user.user_id),
            token_id=str(reset_token.id),
        )

    async def _deliver_reset_email(
        self,
        *,
        reset_token: PasswordResetToken,
        recipient: str,
        raw_token: str,
    ) -> None:
        attempted_at = datetime.now(UTC)
        reset_url = self._build_reset_url(raw_token)

        try:
            await self.email_service.send_password_reset_email(
                recipient=recipient,
                reset_url=reset_url,
            )
        except Exception as exc:  # noqa: BLE001 - keep auth seam resilient to delivery outages
            reset_token.delivery_status = PASSWORD_RESET_DELIVERY_STATUS_FAILED
            reset_token.delivery_attempted_at = attempted_at
            reset_token.delivery_error = self._format_delivery_error(exc)
            await self.db.commit()
            logger.warning(
                "Password reset email delivery failed",
                token_id=str(reset_token.id),
                user_id=str(reset_token.user_id),
                error=reset_token.delivery_error,
            )
            return

        reset_token.delivery_status = PASSWORD_RESET_DELIVERY_STATUS_SENT
        reset_token.delivery_attempted_at = attempted_at
        reset_token.delivery_error = None
        await self.db.commit()

        logger.info(
            "Password reset email delivered",
            token_id=str(reset_token.id),
            user_id=str(reset_token.user_id),
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

    @staticmethod
    def _format_delivery_error(exc: Exception) -> str:
        payload = f"{exc.__class__.__name__}: {str(exc).strip()}".strip()
        if not payload:
            payload = exc.__class__.__name__
        return payload[:PASSWORD_RESET_ERROR_MAX_LENGTH]


def _mask_email(email: str) -> str:
    local_part, _, domain_part = email.partition("@")
    if not domain_part:
        return "***"
    if len(local_part) <= 2:
        masked_local = f"{local_part[:1]}***"
    else:
        masked_local = f"{local_part[:2]}***"
    return f"{masked_local}@{domain_part}"
