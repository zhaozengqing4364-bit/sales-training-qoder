from __future__ import annotations

from datetime import UTC, datetime

from scripts.inventory_newcomer_foundation_authoring import (
    REPORT_SCHEMA_VERSION,
    _extract_legacy_activities,
    build_inventory_report,
    render_markdown,
)

FIXED_TIME = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)


def _legacy() -> dict[str, object]:
    return {
        "active_paths": [
            {
                "logical_id": "default",
                "activities": [
                    {
                        "activity_id": "ppt-intro",
                        "title": "石犀ppt讲解",
                        "activity_type": "audio_assessment",
                        "material_id": "material-1",
                        "scoring_prompt_id": "prompt-1",
                        "is_focus_activity": True,
                    },
                    {
                        "activity_id": "demo-intro",
                        "title": "demo讲解",
                        "activity_type": "audio_assessment",
                        "material_id": None,
                        "scoring_prompt_id": None,
                        "is_focus_activity": True,
                    },
                ],
            }
        ],
        "materials": [
            {
                "material_id": "material-1",
                "name": "石犀科技-企业介绍标准版（202606版）.pptx",
                "material_type": "attachment",
                "status": "published",
                "versions": [
                    {
                        "version_id": "version-1",
                        "status": "published",
                        "file_hash": "same-hash",
                    }
                ],
            }
        ],
        "scoring_prompts": [
            {
                "prompt_id": "prompt-1",
                "name": "PPT 讲解评分",
                "contract_hash": "sha256:safe",
            }
        ],
        "counts": {
            "active_paths": 1,
            "activities": 2,
            "materials": 1,
            "material_versions": 1,
            "scoring_prompts": 1,
        },
    }


def _organization(*, duplicate_hash: bool = False) -> dict[str, object]:
    sources: list[dict[str, object]] = [
        {
            "resource_id": "source-1",
            "stable_key": "company-intro",
            "title": "企业介绍",
            "revisions": [
                {"revision_id": "source-revision-1", "file_hash": "same-hash"}
            ],
        }
    ]
    if duplicate_hash:
        sources.append(
            {
                "resource_id": "source-2",
                "stable_key": "company-intro-copy",
                "title": "企业介绍副本",
                "revisions": [
                    {"revision_id": "source-revision-2", "file_hash": "same-hash"}
                ],
            }
        )
    return {
        "organization_id": "org-a",
        "foundation": {"source_documents": sources, "counts": {}},
    }


def test_should_extract_focus_activities_without_prompt_or_payload_text() -> None:
    activities = _extract_legacy_activities(
        {
            "schema_version": "newcomer_training_orchestration_v1",
            "phases": [
                {
                    "phase_id": "material",
                    "modules": [
                        {
                            "module_id": "audio",
                            "activities": [
                                {
                                    "activity_id": "ppt-intro",
                                    "title": "石犀ppt讲解",
                                    "type": "audio_assessment",
                                    "description": "must not be copied",
                                    "config": {
                                        "material_id": "material-1",
                                        "scoring_rubric_id": "prompt-1",
                                        "example_transcript": "protected body",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    assert activities == [
        {
            "activity_id": "ppt-intro",
            "title": "石犀ppt讲解",
            "activity_type": "audio_assessment",
            "phase_id": "material",
            "module_id": "audio",
            "material_id": "material-1",
            "scoring_prompt_id": "prompt-1",
            "is_focus_activity": True,
        }
    ]
    assert "protected body" not in str(activities)


def test_should_build_stable_redacted_read_only_report() -> None:
    legacy = _legacy()
    legacy["system_prompt"] = "never emit this"

    first = build_inventory_report(
        legacy=legacy,
        organizations=[_organization()],
        generated_at=FIXED_TIME,
    )
    second = build_inventory_report(
        legacy=legacy,
        organizations=[_organization()],
        generated_at=FIXED_TIME,
    )

    assert first == second
    assert first["schema_version"] == REPORT_SCHEMA_VERSION
    assert first["mode"] == "read_only"
    assert first["writes_performed"] == 0
    assert "never emit this" not in str(first)
    organization = first["organizations"][0]  # type: ignore[index]
    material = organization["mapping_candidates"]["materials"][0]  # type: ignore[index]
    assert material["disposition"] == "reuse_exact_hash"
    activities = organization["mapping_candidates"]["focus_activities"]  # type: ignore[index]
    assert activities[0]["disposition"] == "ready_for_dry_run"
    assert activities[1]["disposition"] == "needs_input"


def test_should_report_duplicate_hash_as_conflict() -> None:
    report = build_inventory_report(
        legacy=_legacy(),
        organizations=[_organization(duplicate_hash=True)],
        generated_at=FIXED_TIME,
    )

    organization = report["organizations"][0]  # type: ignore[index]
    candidate = organization["mapping_candidates"]["materials"][0]  # type: ignore[index]
    assert candidate["disposition"] == "conflict_same_hash_multiple_targets"
    assert organization["conflicts"] == [
        {
            "object_type": "sales_trainer_material",
            "object_id": "material-1",
            "reason": "conflict_same_hash_multiple_targets",
        }
    ]


def test_should_report_duplicate_legacy_material_identity_conflict() -> None:
    legacy = _legacy()
    materials = legacy["materials"]  # type: ignore[assignment]
    materials.append(  # type: ignore[union-attr]
        {
            "material_id": "material-2",
            "name": "石犀科技-企业介绍标准版（202606版）.pptx",
            "material_type": "attachment",
            "status": "draft",
            "versions": [],
        }
    )

    report = build_inventory_report(
        legacy=legacy,
        organizations=[_organization()],
        generated_at=FIXED_TIME,
    )

    conflicts = report["legacy"]["material_conflicts"]  # type: ignore[index]
    assert conflicts[0]["code"] == "LEGACY_MATERIAL_SAME_NAME_INCOMPLETE_HASH"
    organization = report["organizations"][0]  # type: ignore[index]
    second = organization["mapping_candidates"]["materials"][1]
    assert second["disposition"] == "conflict_legacy_material_identity"


def test_should_not_auto_reuse_hash_with_multiple_legacy_logical_objects() -> None:
    legacy = _legacy()
    materials = legacy["materials"]  # type: ignore[assignment]
    materials.append(  # type: ignore[union-attr]
        {
            "material_id": "material-2",
            "name": "另一个逻辑材料.pptx",
            "material_type": "ppt_deck",
            "status": "published",
            "versions": [
                {
                    "version_id": "version-2",
                    "status": "published",
                    "file_hash": "same-hash",
                }
            ],
        }
    )

    report = build_inventory_report(
        legacy=legacy,
        organizations=[_organization()],
        generated_at=FIXED_TIME,
    )

    organization = report["organizations"][0]  # type: ignore[index]
    candidates = organization["mapping_candidates"]["materials"]
    assert {candidate["disposition"] for candidate in candidates} == {
        "conflict_legacy_material_identity"
    }


def test_should_mark_legacy_prompts_unverifiable_and_redact_secret_variants() -> None:
    legacy = _legacy()
    legacy["api_key"] = "never emit api key"
    legacy["credentials"] = {"password": "never emit password"}

    report = build_inventory_report(
        legacy=legacy,
        organizations=[_organization()],
        generated_at=FIXED_TIME,
    )

    unverifiable = report["legacy"]["unverifiable_items"]  # type: ignore[index]
    assert unverifiable == [
        {
            "object_type": "sales_trainer_audio_score_prompt",
            "object_id": "prompt-1",
            "reason": "requires_governed_prompt_model_schema_review",
            "referenced_by_activity_ids": [],
        }
    ]
    assert "never emit" not in str(report)


def test_should_render_markdown_without_sensitive_fields() -> None:
    report = build_inventory_report(
        legacy=_legacy(),
        organizations=[_organization()],
        generated_at=FIXED_TIME,
    )

    markdown = render_markdown(report)

    assert "石犀ppt讲解" in markdown
    assert "demo讲解" in markdown
    assert "石犀科技-企业介绍标准版（202606版）.pptx" in markdown
    assert "system_prompt" not in markdown
    assert "只读" in markdown
    assert "迁移前均需治理合同复核" in markdown
