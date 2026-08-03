"""Opaque learner grants for exact source assets.

Tokens are locators, not authorization.  Every delivery request still reloads
the learner's activity workspace and matches the block token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass

from common.config import settings


@dataclass(frozen=True, slots=True)
class LearnerSourceAssetGrant:
    organization_id: str
    activity_id: str
    block_id: str
    source_revision_id: str


def issue_learner_source_asset_grant(grant: LearnerSourceAssetGrant) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "o": grant.organization_id,
            "a": grant.activity_id,
            "b": grant.block_id,
            "r": grant.source_revision_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(_secret(), encoded, hashlib.sha256).digest()
    return (
        encoded.decode("ascii")
        + "."
        + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    )


def verify_learner_source_asset_grant(token: str) -> LearnerSourceAssetGrant | None:
    try:
        encoded_text, signature_text = token.split(".", 1)
        encoded = encoded_text.encode("ascii")
        actual = _decode_urlsafe(signature_text)
        expected = hmac.new(_secret(), encoded, hashlib.sha256).digest()
        if not hmac.compare_digest(actual, expected):
            return None
        payload = json.loads(_decode_urlsafe(encoded_text))
        if not isinstance(payload, dict) or payload.get("v") != 1:
            return None
        values = [payload.get(key) for key in ("o", "a", "b", "r")]
        if not all(isinstance(item, str) and 0 < len(item) <= 160 for item in values):
            return None
        return LearnerSourceAssetGrant(
            organization_id=str(payload["o"]),
            activity_id=str(payload["a"]),
            block_id=str(payload["b"]),
            source_revision_id=str(payload["r"]),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        return None


def _decode_urlsafe(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _secret() -> bytes:
    # Non-development startup already rejects an absent/unsafe SECRET_KEY.
    value = settings.SECRET_KEY or "development-learning-source-access-key"
    return f"learning-source-access:v1:{value}".encode()


__all__ = [
    "LearnerSourceAssetGrant",
    "issue_learner_source_asset_grant",
    "verify_learner_source_asset_grant",
]
