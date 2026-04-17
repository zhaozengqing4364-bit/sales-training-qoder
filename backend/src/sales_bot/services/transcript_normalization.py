"""Transcript normalization service for ASR lexicon corrections."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranscriptReplacement:
    alias: str
    canonical_term: str
    count: int


@dataclass(frozen=True)
class TranscriptNormalizationResult:
    raw_text: str
    normalized_text: str
    replacements: list[dict[str, Any]] = field(default_factory=list)


class TranscriptNormalizationService:
    """Apply app-layer lexicon normalization to ASR transcripts."""

    def normalize(
        self,
        *,
        text: str,
        tool_policy: dict[str, Any] | None,
        is_final: bool,
    ) -> TranscriptNormalizationResult:
        raw_text = str(text or "")
        normalized_text = raw_text
        if not raw_text.strip():
            return TranscriptNormalizationResult(
                raw_text=raw_text,
                normalized_text=raw_text,
                replacements=[],
            )

        policy = tool_policy if isinstance(tool_policy, dict) else {}
        if not bool(policy.get("transcript_normalization_enabled", False)):
            return TranscriptNormalizationResult(
                raw_text=raw_text,
                normalized_text=raw_text,
                replacements=[],
            )
        if not is_final and not bool(
            policy.get("transcript_normalization_apply_to_interim", False)
        ):
            return TranscriptNormalizationResult(
                raw_text=raw_text,
                normalized_text=raw_text,
                replacements=[],
            )

        entries = policy.get("transcript_normalization_lexicon")
        if not isinstance(entries, list):
            entries = []

        replacements: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            canonical_term = str(entry.get("canonical_term") or "").strip()
            aliases = entry.get("aliases")
            if not canonical_term or not isinstance(aliases, list):
                continue
            replace_on_final_only = bool(entry.get("replace_on_final_only", True))
            if replace_on_final_only and not is_final:
                continue

            for alias in sorted(
                {
                    str(item).strip()
                    for item in aliases
                    if str(item).strip() and str(item).strip() != canonical_term
                },
                key=len,
                reverse=True,
            ):
                pattern = re.escape(alias)
                normalized_text, replace_count = re.subn(
                    pattern,
                    canonical_term,
                    normalized_text,
                )
                if replace_count > 0:
                    replacements.append(
                        {
                            "alias": alias,
                            "canonical_term": canonical_term,
                            "count": replace_count,
                        }
                    )

        return TranscriptNormalizationResult(
            raw_text=raw_text,
            normalized_text=normalized_text,
            replacements=replacements,
        )
