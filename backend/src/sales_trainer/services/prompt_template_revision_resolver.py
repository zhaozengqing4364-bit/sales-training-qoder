"""Prompt-template (template_id, revision_id) loader for AI coach.

Background
----------
The existing ``PromptTemplateService.get_template(template_id)`` returns the
**current head** of the template row only. There is no first-class
``PromptTemplateRevision`` table in the schema, so we cannot load a historical
revision by primary key. Per the upstream service report
(``promptSvcReport.recommendation``), the recommended short-term mitigation is
to (a) reconstruct historical snapshots from ``SystemLog`` rows with
``action = "prompt_template.governance_migrate"`` and (b) key caches on
``(template_id, updated_at)`` to guard against in-place update races.

This module wraps the existing ``PromptTemplateService`` without modifying its
schema or API surface. It is intentionally narrow in scope: it only resolves
``(template_id, prompt_revision_id)`` for the AI coach flow.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import SystemLog
from common.monitoring.logger import get_logger
from prompt_templates.models import PromptTemplate
from prompt_templates.service import PromptTemplateService

logger = get_logger(__name__)


PROMPT_REVISION_RESOLVE_AUDIT_ACTION = "prompt_template.governance_migrate"

# Result codes (kept short and human-readable; admin UI maps these to banners).
RESULT_OK = "ok"
RESULT_REVISION_NOT_FOUND = "revision_not_found"
RESULT_AUDIT_HISTORY_UNAVAILABLE = "audit_history_unavailable"
RESULT_HEAD_USED_AS_FALLBACK = "head_used_as_fallback"


@dataclass(slots=True)
class PromptRevisionSnapshot:
    """Resolved view of a prompt template at a given revision marker.

    Attributes:
        template_id: Original template UUID.
        prompt_revision_id: Revision marker supplied by the caller. May equal
            ``updated_at_iso`` when the caller uses the short-term mitigation
            strategy.
        resolved_from: Where the snapshot came from ("head" / "audit_before"
            / "head_fallback_unresolved").
        updated_at_iso: ``updated_at`` of the underlying row at the time of
            resolution. Always set, even for audit-reconstructed rows, to
            preserve cache-key stability.
        template: The Pydantic ``PromptTemplate`` payload.
    """

    template_id: str
    prompt_revision_id: str
    resolved_from: str
    updated_at_iso: str
    template: PromptTemplate


@dataclass
class _RevisionCacheEntry:
    snapshot: PromptRevisionSnapshot
    cached_at: float = field(default_factory=time.time)


class _RevisionCache:
    """Tiny LRU-ish cache keyed on (template_id, updated_at_iso).

    The cache is bounded and time-bounded; it is intentionally process-local
    so it does not need invalidation hooks in ``PromptTemplateService``.
    """

    def __init__(self, *, max_entries: int = 128, ttl_seconds: float = 300.0) -> None:
        self._max = max_entries
        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str], _RevisionCacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str]) -> PromptRevisionSnapshot | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() - entry.cached_at > self._ttl:
                self._store.pop(key, None)
                return None
            return entry.snapshot

    def put(self, key: tuple[str, str], snapshot: PromptRevisionSnapshot) -> None:
        with self._lock:
            if len(self._store) >= self._max:
                # Drop the oldest entry to bound memory.
                oldest_key = min(
                    self._store,
                    key=lambda k: self._store[k].cached_at,
                )
                self._store.pop(oldest_key, None)
            self._store[key] = _RevisionCacheEntry(snapshot=snapshot)


_CACHE = _RevisionCache()


def _isoformat(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        try:
            iso_value = value.isoformat()
            return iso_value if isinstance(iso_value, str) else str(iso_value)
        except Exception:  # pragma: no cover - defensive
            return str(value)
    return str(value)


def _is_uuid_like(value: str) -> bool:
    """Cheap check; we don't need a full RFC 4122 validator here."""
    if not value or not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,36}", value.strip()))


def _snapshot_from_dict(
    *,
    template_id: str,
    prompt_revision_id: str,
    before: dict[str, Any],
) -> PromptTemplate | None:
    """Materialize a ``PromptTemplate`` from a stored ``before`` snapshot.

    The audit ``before`` payload is the template row prior to a governance
    migration. We rebuild a Pydantic model from those fields; missing fields
    are tolerated because the audit schema is intentionally narrow.
    """
    if not isinstance(before, dict):
        return None
    try:
        return PromptTemplate.model_validate(
            {
                "id": template_id,
                "name": before.get("name") or "(reconstructed)",
                "prompt_type": before.get("prompt_type") or "system",
                "category": before.get("category") or "common",
                "template": before.get("template") or "",
                "variables": before.get("variables") or [],
                "is_active": bool(before.get("is_active", True)),
                "is_default": bool(before.get("is_default", False)),
                "is_system": bool(before.get("is_system", False)),
                "created_at": before.get("created_at"),
                "updated_at": before.get("updated_at"),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "ai_coach_prompt_revision_reconstruct_failed",
            template_id=template_id,
            error=str(exc),
        )
        return None


async def _load_audit_snapshot(
    db: AsyncSession,
    *,
    template_id: str,
    prompt_revision_id: str,
) -> dict[str, Any] | None:
    """Find the audit row whose ``before`` matches the requested revision.

    The migration audit stores the entire pre-migration row under
    ``details['before']``. We match on ``template_id`` and pick the audit
    whose ``updated_at`` field equals ``prompt_revision_id`` (the short-term
    mitigation strategy). Falls back to the most recent audit for that
    template when the caller did not supply an ``updated_at`` marker.
    """
    stmt = (
        select(SystemLog)
        .where(SystemLog.action == PROMPT_REVISION_RESOLVE_AUDIT_ACTION)
        .order_by(SystemLog.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    best_match: dict[str, Any] | None = None
    for row in rows:
        try:
            details_raw = getattr(row, "details", None)
            details = json.loads(details_raw if isinstance(details_raw, str) else "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(details, dict):
            continue
        if str(details.get("template_id")) != str(template_id):
            continue
        before = details.get("before")
        if not isinstance(before, dict):
            continue
        updated_at = _isoformat(before.get("updated_at"))
        if (
            prompt_revision_id
            and updated_at
            and updated_at == prompt_revision_id
        ):
            return before
        # Track the most recent as fallback.
        if best_match is None:
            best_match = before
    return best_match


class PromptTemplateRevisionResolverError(Exception):
    """Raised for hard failures (e.g. caller supplied a non-UUID template_id).

    Soft cases (audit unavailable, revision unresolved) are returned via the
    Result-like ``PromptRevisionResolution`` return value below.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(slots=True)
class PromptRevisionResolution:
    """Result of a revision resolution attempt.

    Attributes:
        status: One of ``RESULT_OK``, ``RESULT_HEAD_USED_AS_FALLBACK``,
            ``RESULT_REVISION_NOT_FOUND``, ``RESULT_AUDIT_HISTORY_UNAVAILABLE``.
        snapshot: Always populated; for non-OK statuses this is the current
            head of the template so the AI coach can still continue, but the
            caller is expected to surface the status to the admin console.
    """

    status: str
    snapshot: PromptRevisionSnapshot


class PromptTemplateRevisionResolver:
    """Sales-trainer wrapper that loads ``(template_id, prompt_revision_id)``.

    Behaviour summary
    -----------------
    * If ``prompt_revision_id`` is empty / None → return the current head
      (``resolved_from = "head"``).
    * If ``prompt_revision_id`` is an ISO ``updated_at`` marker → look up
      the matching governance-migrate audit; if found, return the
      ``before`` snapshot (``resolved_from = "audit_before"``).
    * If no audit match is found → return the current head with
      ``status = RESULT_HEAD_USED_AS_FALLBACK`` and
      ``resolved_from = "head_fallback_unresolved"`` so the caller can
      surface a banner.
    """

    def __init__(self, db: AsyncSession, *, service: PromptTemplateService | None = None) -> None:
        self._db = db
        self._service = service or PromptTemplateService(db)

    async def resolve(
        self,
        *,
        template_id: str,
        prompt_revision_id: str | None,
    ) -> PromptRevisionResolution:
        if not _is_uuid_like(template_id):
            raise PromptTemplateRevisionResolverError(
                "[PROMPT_TEMPLATE_INVALID_ID]",
                "template_id must be a UUID",
            )

        normalised_template_id = str(UUID(template_id))
        normalised_revision = (prompt_revision_id or "").strip() or None

        # Fast path: no revision requested -> current head.
        if not normalised_revision:
            snapshot = await self._load_head_snapshot(
                template_id=normalised_template_id,
                prompt_revision_id="head",
            )
            return PromptRevisionResolution(
                status=RESULT_OK, snapshot=snapshot
            )

        cache_key = (normalised_template_id, normalised_revision)
        cached = _CACHE.get(cache_key)
        if cached is not None:
            return PromptRevisionResolution(status=RESULT_OK, snapshot=cached)

        # If the caller did not supply a usable session (e.g. unit tests with a
        # mocked service), we cannot consult SystemLog. Skip the audit lookup
        # and fall straight through to the head-fallback path so the runtime
        # still gets a valid snapshot with a clear status.
        if self._db is None:
            head = await self._load_head_snapshot(
                template_id=normalised_template_id,
                prompt_revision_id=normalised_revision,
            )
            if (
                normalised_revision
                and normalised_revision == head.updated_at_iso
            ):
                return PromptRevisionResolution(status=RESULT_OK, snapshot=head)
            head.resolved_from = "head_fallback_unresolved"
            return PromptRevisionResolution(
                status=RESULT_HEAD_USED_AS_FALLBACK, snapshot=head
            )

        audit_before = await _load_audit_snapshot(
            self._db,
            template_id=normalised_template_id,
            prompt_revision_id=normalised_revision,
        )
        if audit_before is not None:
            template = _snapshot_from_dict(
                template_id=normalised_template_id,
                prompt_revision_id=normalised_revision,
                before=audit_before,
            )
            if template is not None:
                snapshot = PromptRevisionSnapshot(
                    template_id=normalised_template_id,
                    prompt_revision_id=normalised_revision,
                    resolved_from="audit_before",
                    updated_at_iso=_isoformat(audit_before.get("updated_at"))
                    or normalised_revision,
                    template=template,
                )
                _CACHE.put(cache_key, snapshot)
                return PromptRevisionResolution(
                    status=RESULT_OK, snapshot=snapshot
                )

        # Soft fallback: surface the head with an explicit status so callers
        # can show an admin banner and the contract hash can still be keyed
        # on (template_id, updated_at) to prevent in-place update races.
        head = await self._load_head_snapshot(
            template_id=normalised_template_id,
            prompt_revision_id=normalised_revision,
        )
        if normalised_revision and normalised_revision == head.updated_at_iso:
            # Caller happened to pass the current updated_at; treat as OK.
            return PromptRevisionResolution(status=RESULT_OK, snapshot=head)
        head.resolved_from = "head_fallback_unresolved"
        return PromptRevisionResolution(
            status=RESULT_HEAD_USED_AS_FALLBACK, snapshot=head
        )

    async def _load_head_snapshot(
        self,
        *,
        template_id: str,
        prompt_revision_id: str,
    ) -> PromptRevisionSnapshot:
        template = await self._service.get_template(UUID(template_id))
        if template is None:
            raise PromptTemplateRevisionResolverError(
                "[PROMPT_TEMPLATE_NOT_FOUND]",
                f"PromptTemplate {template_id} not found",
            )
        return PromptRevisionSnapshot(
            template_id=template_id,
            prompt_revision_id=prompt_revision_id,
            resolved_from="head",
            updated_at_iso=_isoformat(getattr(template, "updated_at", None)),
            template=template,
        )


__all__ = [
    "PromptTemplateRevisionResolver",
    "PromptTemplateRevisionResolverError",
    "PromptRevisionResolution",
    "PromptRevisionSnapshot",
    "RESULT_OK",
    "RESULT_REVISION_NOT_FOUND",
    "RESULT_AUDIT_HISTORY_UNAVAILABLE",
    "RESULT_HEAD_USED_AS_FALLBACK",
]
