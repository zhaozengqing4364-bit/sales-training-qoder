"""Durable highlight review lists and governed sharing.

This service owns the G-04/G-10 safety boundary:
- learners can persist selected replay highlights across devices;
- share links are consent-gated, TTL-bound, revocable, audited, and desensitized;
- adaptive/share policy evaluation remains delegated to the growth safety policy.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.db.models import (
    ConversationMessage,
    HighlightReview,
    HighlightReviewItem,
    HighlightReviewShare,
    HighlightReviewShareAccessLog,
    PracticeSession,
    User,
)
from common.error_handling.result import Result
from common.growth.safety_policies import GrowthSafetyPolicyService
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

HIGHLIGHT_REVIEW_SCHEMA_VERSION = "highlight_review_v1"
HIGHLIGHT_REVIEW_LIMIT = 3
DESENSITIZATION_VERSION = "highlight_share_desensitized_v1"
PUBLIC_SHARE_PATH_TEMPLATE = "/api/v1/sessions/highlight-reviews/shared/{token}"

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
_LONG_DIGIT_PATTERN = re.compile(r"(?<!\d)\d{8,}(?!\d)")


def hash_share_token(token: str) -> str:
    """Hash a one-time-visible share token before storage."""

    return hashlib.sha256(f"highlight-review-share:{token}".encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _coerce_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _trim_text(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _desensitize_text(value: str | None, *, limit: int = 280) -> str | None:
    cleaned = _trim_text(value, limit=limit)
    if cleaned is None:
        return None
    cleaned = _EMAIL_PATTERN.sub("[email]", cleaned)
    cleaned = _PHONE_PATTERN.sub("[phone]", cleaned)
    cleaned = _LONG_DIGIT_PATTERN.sub("[number]", cleaned)
    return cleaned


def _stage_label(message: ConversationMessage, override: str | None) -> str | None:
    if override:
        return _trim_text(override, limit=80)
    if message.sales_stage:
        return str(message.sales_stage)
    return None


def _reason(message: ConversationMessage, override: str | None) -> str | None:
    return (
        _trim_text(override, limit=500)
        or _trim_text(_optional_str(getattr(message, "highlight_reason", None)), limit=500)
        or _trim_text(_optional_str(getattr(message, "ai_feedback", None)), limit=500)
    )


def _suggested_response(
    message: ConversationMessage,
    override: str | None,
) -> str | None:
    if override:
        return _trim_text(override, limit=1000)
    if message.highlight_type != "bad":
        return None
    return "先承接客户问题，再补充一条可验证的案例、数据或 ROI 证据。"


def _is_admin(user: User) -> bool:
    return str(getattr(user, "role", "user")).lower() == "admin"


def _share_status(share: HighlightReviewShare, *, now: datetime | None = None) -> str:
    current_time = now or _now()
    if share.revoked_at is not None:
        return "revoked"
    if _coerce_aware(share.expires_at) <= current_time:
        return "expired"
    return "active"


class HighlightReviewService:
    """Persistence and controlled sharing for learner-selected highlights."""

    def __init__(
        self,
        *,
        policy_service: GrowthSafetyPolicyService | None = None,
    ) -> None:
        self.policy_service = policy_service or GrowthSafetyPolicyService()

    async def get_review(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        current_user: User,
    ) -> Result[dict[str, Any] | None]:
        session_result = await self._load_accessible_session(
            db=db,
            session_id=session_id,
            current_user=current_user,
        )
        if not session_result.is_success:
            return Result.fail(session_result.fallback or "[SESSION_NOT_FOUND]")
        session = session_result.value
        if session is None:
            return Result.fail("[SESSION_NOT_FOUND]")

        review = await self._load_review(
            db=db,
            session_id=session_id,
            user_id=str(session.user_id),
        )
        share_policy = self._share_policy_payload(session)
        if review is None:
            return Result.ok(None)
        return Result.ok(self._review_payload(review, share_policy=share_policy))

    async def save_review(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        current_user: User,
        title: str | None,
        items: list[dict[str, Any]],
    ) -> Result[dict[str, Any]]:
        session_result = await self._load_accessible_session(
            db=db,
            session_id=session_id,
            current_user=current_user,
            owner_only=True,
        )
        if not session_result.is_success:
            return Result.fail(session_result.fallback or "[SESSION_NOT_FOUND]")
        session = session_result.value
        if session is None:
            return Result.fail("[SESSION_NOT_FOUND]")

        unique_message_ids: list[str] = []
        item_by_message_id: dict[str, dict[str, Any]] = {}
        for item in items:
            raw_id = str(item.get("message_id") or item.get("id") or "").strip()
            if not raw_id or raw_id in item_by_message_id:
                continue
            unique_message_ids.append(raw_id)
            item_by_message_id[raw_id] = item
            if len(unique_message_ids) >= HIGHLIGHT_REVIEW_LIMIT:
                break

        messages = await self._load_highlight_messages(
            db=db,
            session_id=session_id,
            message_ids=unique_message_ids,
        )
        if len(messages) != len(unique_message_ids):
            return Result.fail("[HIGHLIGHT_MESSAGE_NOT_FOUND]")

        try:
            review = await self._load_review(
                db=db,
                session_id=session_id,
                user_id=str(session.user_id),
            )
            if review is None:
                review = HighlightReview(
                    session_id=session_id,
                    user_id=str(session.user_id),
                    schema_version=HIGHLIGHT_REVIEW_SCHEMA_VERSION,
                )
                db.add(review)
                await db.flush()

            setattr(review, "title", _trim_text(title, limit=160))
            setattr(review, "schema_version", HIGHLIGHT_REVIEW_SCHEMA_VERSION)
            setattr(review, "updated_at", _now())

            await db.execute(
                delete(HighlightReviewItem).where(
                    HighlightReviewItem.review_id == review.review_id
                )
            )
            message_by_id = {str(message.id): message for message in messages}
            for index, message_id in enumerate(unique_message_ids):
                message = message_by_id[message_id]
                source_item = item_by_message_id[message_id]
                review_item = self._build_review_item(
                    review_id=str(review.review_id),
                    message=message,
                    source_item=source_item,
                    sort_order=index,
                )
                db.add(review_item)

            await db.commit()
            review = await self._load_review(
                db=db,
                session_id=session_id,
                user_id=str(session.user_id),
            )
            if review is None:
                return Result.fail("[HIGHLIGHT_REVIEW_NOT_FOUND]")
            return Result.ok(
                self._review_payload(
                    review,
                    share_policy=self._share_policy_payload(session),
                )
            )
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.warning(
                "highlight_review_save_failed",
                session_id=session_id,
                user_id=str(current_user.user_id),
                error=str(exc),
            )
            return Result.fail("[HIGHLIGHT_REVIEW_SAVE_FAILED]")

    async def create_share(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        current_user: User,
        consent_granted: bool,
        consent_text: str | None,
        ttl_days: int | None,
        channel: str = "wecom",
    ) -> Result[dict[str, Any]]:
        if channel != "wecom":
            return Result.fail("[SHARE_CHANNEL_UNSUPPORTED]")
        if not consent_granted:
            return Result.fail("[SHARE_CONSENT_REQUIRED]")

        session_result = await self._load_accessible_session(
            db=db,
            session_id=session_id,
            current_user=current_user,
            owner_only=True,
        )
        if not session_result.is_success:
            return Result.fail(session_result.fallback or "[SESSION_NOT_FOUND]")
        session = session_result.value
        if session is None:
            return Result.fail("[SESSION_NOT_FOUND]")

        policy = self.policy_service.evaluate_wecom_share(session).value or {}
        if policy.get("status") != "available":
            return Result.fail("[WECOM_SHARE_NOT_AVAILABLE]")

        review = await self._load_review(
            db=db,
            session_id=session_id,
            user_id=str(session.user_id),
        )
        if review is None or not review.items:
            return Result.fail("[HIGHLIGHT_REVIEW_EMPTY]")

        resolved_ttl_days = min(
            int(ttl_days or policy.get("ttl_days") or 7), int(policy["ttl_days"])
        )
        token = secrets.token_urlsafe(32)
        share = HighlightReviewShare(
            review_id=str(review.review_id),
            user_id=str(session.user_id),
            channel="wecom",
            token_hash=hash_share_token(token),
            consent_granted=True,
            consent_text=_trim_text(consent_text, limit=1000)
            or "用户同意通过企业微信内部只读试点分享脱敏高光复习清单。",
            policy_version=str(policy.get("policy_version") or policy.get("version")),
            policy_snapshot=policy,
            ttl_days=resolved_ttl_days,
            expires_at=_now() + timedelta(days=resolved_ttl_days),
            desensitization_version=DESENSITIZATION_VERSION,
        )
        db.add(share)
        await db.flush()
        db.add(
            self._audit_log(
                share_id=str(share.share_id),
                event_type="created",
                actor_user_id=str(current_user.user_id),
                status="success",
                details={
                    "channel": "wecom",
                    "ttl_days": resolved_ttl_days,
                    "policy_version": share.policy_version,
                    "desensitization_version": DESENSITIZATION_VERSION,
                },
            )
        )

        try:
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.warning(
                "highlight_review_share_create_failed",
                session_id=session_id,
                user_id=str(current_user.user_id),
                error=str(exc),
            )
            return Result.fail("[HIGHLIGHT_SHARE_CREATE_FAILED]")

        await db.refresh(share)
        payload = self._share_summary(share)
        payload["share_token"] = token
        payload["public_api_path"] = PUBLIC_SHARE_PATH_TEMPLATE.format(token=token)
        return Result.ok(payload)

    async def revoke_share(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        share_id: str,
        current_user: User,
        reason: str | None,
    ) -> Result[dict[str, Any]]:
        session_result = await self._load_accessible_session(
            db=db,
            session_id=session_id,
            current_user=current_user,
            owner_only=True,
        )
        if not session_result.is_success:
            return Result.fail(session_result.fallback or "[SESSION_NOT_FOUND]")
        session = session_result.value
        if session is None:
            return Result.fail("[SESSION_NOT_FOUND]")

        share = await self._load_share_for_session(
            db=db,
            session_id=session_id,
            user_id=str(session.user_id),
            share_id=share_id,
        )
        if share is None:
            return Result.fail("[HIGHLIGHT_SHARE_NOT_FOUND]")

        if share.revoked_at is None:
            share.revoked_at = _now()
            share.revoked_by_user_id = str(current_user.user_id)
            share.revoked_reason = _trim_text(reason, limit=200) or "user_revoked"
            share.updated_at = _now()
            db.add(
                self._audit_log(
                    share_id=str(share.share_id),
                    event_type="revoked",
                    actor_user_id=str(current_user.user_id),
                    status="success",
                    details={"reason": share.revoked_reason},
                )
            )

        try:
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.warning(
                "highlight_review_share_revoke_failed",
                share_id=share_id,
                user_id=str(current_user.user_id),
                error=str(exc),
            )
            return Result.fail("[HIGHLIGHT_SHARE_REVOKE_FAILED]")

        await db.refresh(share)
        return Result.ok(self._share_summary(share))

    async def get_shared_review(
        self,
        *,
        db: AsyncSession,
        token: str,
        viewer_label: str | None = None,
        client_hint: str | None = None,
    ) -> Result[dict[str, Any]]:
        token_hash = hash_share_token(token)
        result = await db.execute(
            select(HighlightReviewShare)
            .options(
                selectinload(HighlightReviewShare.review).selectinload(
                    HighlightReview.items
                )
            )
            .where(HighlightReviewShare.token_hash == token_hash)
        )
        share = result.scalar_one_or_none()
        if share is None:
            return Result.fail("[HIGHLIGHT_SHARE_NOT_FOUND]")

        status = _share_status(share)
        if status != "active":
            db.add(
                self._audit_log(
                    share_id=str(share.share_id),
                    event_type="denied",
                    viewer_label=_trim_text(viewer_label, limit=120),
                    client_fingerprint=self._client_fingerprint(client_hint),
                    status="blocked",
                    details={"reason": status},
                )
            )
            await db.commit()
            return Result.fail("[HIGHLIGHT_SHARE_INACTIVE]")

        setattr(share, "last_accessed_at", _now())
        setattr(share, "access_count", int(share.access_count or 0) + 1)
        db.add(
            self._audit_log(
                share_id=str(share.share_id),
                event_type="accessed",
                viewer_label=_trim_text(viewer_label, limit=120),
                client_fingerprint=self._client_fingerprint(client_hint),
                status="success",
                details={"channel": share.channel},
            )
        )
        await db.commit()
        await db.refresh(share)
        return Result.ok(self._shared_payload(share))

    async def _load_accessible_session(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        current_user: User,
        owner_only: bool = False,
    ) -> Result[PracticeSession]:
        result = await db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return Result.fail("[SESSION_NOT_FOUND]")
        if str(session.user_id) != str(current_user.user_id) and (
            owner_only or not _is_admin(current_user)
        ):
            return Result.fail("[ACCESS_DENIED]")
        return Result.ok(session)

    async def _load_highlight_messages(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        message_ids: list[str],
    ) -> list[ConversationMessage]:
        if not message_ids:
            return []
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .where(ConversationMessage.id.in_(message_ids))
            .where(ConversationMessage.is_highlight.is_(True))
        )
        messages = list(result.scalars().all())
        message_order = {
            message_id: index for index, message_id in enumerate(message_ids)
        }
        return sorted(
            messages, key=lambda message: message_order.get(str(message.id), 0)
        )

    async def _load_review(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        user_id: str,
    ) -> HighlightReview | None:
        result = await db.execute(
            select(HighlightReview)
            .options(
                selectinload(HighlightReview.items),
                selectinload(HighlightReview.shares),
            )
            .where(HighlightReview.session_id == session_id)
            .where(HighlightReview.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _load_share_for_session(
        self,
        *,
        db: AsyncSession,
        session_id: str,
        user_id: str,
        share_id: str,
    ) -> HighlightReviewShare | None:
        result = await db.execute(
            select(HighlightReviewShare)
            .join(
                HighlightReview,
                HighlightReview.review_id == HighlightReviewShare.review_id,
            )
            .where(HighlightReview.session_id == session_id)
            .where(HighlightReview.user_id == user_id)
            .where(HighlightReviewShare.share_id == share_id)
        )
        return result.scalar_one_or_none()

    def _build_review_item(
        self,
        *,
        review_id: str,
        message: ConversationMessage,
        source_item: dict[str, Any],
        sort_order: int,
    ) -> HighlightReviewItem:
        return HighlightReviewItem(
            review_id=review_id,
            message_id=str(message.id),
            turn_number=max(1, int(message.turn_number or 1)),
            role=str(message.role),
            content_excerpt=_trim_text(
                _optional_str(getattr(message, "content", None)), limit=1000
            )
            or "",
            reason=_reason(message, source_item.get("reason")),
            stage_name=_stage_label(message, source_item.get("stage_name")),
            issue_label=_trim_text(source_item.get("issue_label"), limit=80),
            suggested_response=_suggested_response(
                message,
                source_item.get("suggested_response"),
            ),
            sort_order=sort_order,
            source_payload={
                "highlight_type": message.highlight_type,
                "source": "conversation_message",
            },
        )

    def _share_policy_payload(self, session: PracticeSession) -> dict[str, Any]:
        policy_result = self.policy_service.evaluate_wecom_share(session)
        if not policy_result.is_success or not isinstance(policy_result.value, dict):
            return {
                "feature": "wecom_share",
                "status": "blocked_by_governance",
                "enabled": False,
            }
        return policy_result.value

    @staticmethod
    def _review_item_payload(item: HighlightReviewItem) -> dict[str, Any]:
        return {
            "item_id": str(item.item_id),
            "message_id": str(item.message_id),
            "turn_number": int(item.turn_number),
            "role": item.role,
            "content": item.content_excerpt,
            "reason": item.reason,
            "stage_name": item.stage_name,
            "issue_label": item.issue_label,
            "suggested_response": item.suggested_response,
            "sort_order": int(item.sort_order or 0),
        }

    def _review_payload(
        self,
        review: HighlightReview,
        *,
        share_policy: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "review_id": str(review.review_id),
            "session_id": str(review.session_id),
            "user_id": str(review.user_id),
            "schema_version": review.schema_version,
            "title": review.title,
            "items": [self._review_item_payload(item) for item in review.items],
            "shares": [self._share_summary(share) for share in review.shares],
            "share_policy": share_policy,
            "updated_at": review.updated_at,
        }

    @staticmethod
    def _share_summary(share: HighlightReviewShare) -> dict[str, Any]:
        return {
            "share_id": str(share.share_id),
            "channel": share.channel,
            "status": _share_status(share),
            "consent_granted": bool(share.consent_granted),
            "policy_version": share.policy_version,
            "ttl_days": int(share.ttl_days),
            "expires_at": share.expires_at,
            "revoked_at": share.revoked_at,
            "created_at": share.created_at,
            "access_count": int(share.access_count or 0),
            "desensitization_version": share.desensitization_version,
        }

    @staticmethod
    def _shared_payload(share: HighlightReviewShare) -> dict[str, Any]:
        review = share.review
        session_ref = str(review.session_id)[-8:]
        return {
            "share_id": str(share.share_id),
            "channel": share.channel,
            "status": _share_status(share),
            "expires_at": share.expires_at,
            "source_session_ref": f"session-{session_ref}",
            "desensitization_version": share.desensitization_version,
            "items": [
                {
                    "turn_number": int(item.turn_number),
                    "role": item.role,
                    "content_excerpt": _desensitize_text(item.content_excerpt) or "",
                    "reason": _desensitize_text(item.reason, limit=180),
                    "stage_name": _desensitize_text(item.stage_name, limit=80),
                    "issue_label": _desensitize_text(item.issue_label, limit=80),
                    "suggested_response": _desensitize_text(
                        item.suggested_response,
                        limit=280,
                    ),
                }
                for item in review.items
            ],
            "audit_notice": "此链接为企业微信内部只读试点，访问会记录审计日志；内容已脱敏且不包含学员身份、音频或完整报告。",
        }

    @staticmethod
    def _client_fingerprint(client_hint: str | None) -> str | None:
        cleaned = _trim_text(client_hint, limit=500)
        if cleaned is None:
            return None
        return hashlib.sha256(cleaned.encode()).hexdigest()

    @staticmethod
    def _audit_log(
        *,
        share_id: str,
        event_type: str,
        status: str,
        actor_user_id: str | None = None,
        viewer_label: str | None = None,
        client_fingerprint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> HighlightReviewShareAccessLog:
        return HighlightReviewShareAccessLog(
            share_id=share_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            viewer_label=viewer_label,
            client_fingerprint=client_fingerprint,
            status=status,
            details=details or {},
        )
