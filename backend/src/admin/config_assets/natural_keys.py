"""Cross-instance stable keys for config asset import/export."""

from __future__ import annotations

import re
from hashlib import sha256

_ASSET_REF_PATTERN = re.compile(
    r"^(agent|persona|situation_pack|case_item|role_profile|knowledge_base|"
    r"learning_content|question_category|question_item|scoring_ruleset|"
    r"voice_runtime_profile|examiner_agent|practice_template|training_task):"
    r"([a-z][a-z0-9_-]*)$"
)
_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def topology_ref(asset_type: str, natural_key: str) -> str:
    return f"{asset_type}:{natural_key}"


def parse_topology_ref(ref: str) -> tuple[str, str]:
    match = _ASSET_REF_PATTERN.fullmatch(ref.strip())
    if match is None:
        raise ValueError(f"[INVALID_TOPOLOGY_REF] {ref}")
    return match.group(1), match.group(2)


def derive_natural_key(
    asset_type: str,
    *,
    name: str | None = None,
    code: str | None = None,
    version: str | int | None = None,
) -> str:
    if asset_type == "situation_pack":
        key = (code or "").strip()
        if key and _SLUG_PATTERN.fullmatch(key):
            return key
    if asset_type == "scoring_ruleset" and version is not None:
        key = str(version).strip()
        if key and _SLUG_PATTERN.fullmatch(key):
            return key
    text = (name or code or "").strip()
    if not text:
        raise ValueError(f"[NATURAL_KEY_MISSING] asset_type={asset_type}")
    slug = slugify_name(text)
    if not _SLUG_PATTERN.fullmatch(slug):
        raise ValueError(f"[INVALID_NATURAL_KEY] {slug}")
    return slug


def slugify_name(name: str) -> str:
    lowered = name.strip().lower()
    ascii_text = lowered.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if slug and _SLUG_PATTERN.fullmatch(slug):
        return slug[:120]
    digest = sha256(name.strip().encode("utf-8")).hexdigest()[:12]
    return f"asset-{digest}"


def asset_identity(
    asset_type: str,
    natural_key: str,
    namespace: str = "default",
) -> str:
    return f"{asset_type}:{namespace}:{natural_key}"
