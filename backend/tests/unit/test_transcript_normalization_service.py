"""Unit tests for transcript normalization service."""

from __future__ import annotations

from sales_bot.services.transcript_normalization import TranscriptNormalizationService


def test_normalize_final_transcript_replaces_aliases_and_tracks_replacements():
    service = TranscriptNormalizationService()

    result = service.normalize(
        text="我们这次重点讲石溪平台和食犀方案",
        tool_policy={
            "transcript_normalization_enabled": True,
            "transcript_normalization_lexicon": [
                {
                    "canonical_term": "石犀",
                    "aliases": ["石溪", "食犀"],
                    "scope": "global",
                    "replace_on_final_only": True,
                }
            ],
        },
        is_final=True,
    )

    assert result.normalized_text == "我们这次重点讲石犀平台和石犀方案"
    assert result.raw_text == "我们这次重点讲石溪平台和食犀方案"
    assert len(result.replacements) == 2


def test_normalize_interim_transcript_respects_final_only_flag():
    service = TranscriptNormalizationService()

    result = service.normalize(
        text="先看石溪平台",
        tool_policy={
            "transcript_normalization_enabled": True,
            "transcript_normalization_apply_to_interim": True,
            "transcript_normalization_lexicon": [
                {
                    "canonical_term": "石犀",
                    "aliases": ["石溪"],
                    "scope": "global",
                    "replace_on_final_only": True,
                }
            ],
        },
        is_final=False,
    )

    assert result.normalized_text == "先看石溪平台"
    assert result.replacements == []
