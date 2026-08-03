#!/usr/bin/env python3
"""Generate a read-only Legacy -> Foundation authoring inventory.

The command intentionally has no apply/migrate flag.  It emits only safe metadata,
hashes and revision references; prompt bodies, storage keys, source URIs, learner data
and protected file contents never enter the report.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.models import CoachProfileRevision
from audio_assessment.models import AudioActivityResourceRevision
from common.db.model_registry.registration import register_all_models
from common.db.session import AsyncSessionLocal
from learning.models import (
    LearningQuestion,
    LearningQuestionCandidate,
    LearningQuestionRevision,
    LearningQuiz,
    LearningQuizRevision,
    LearningSourceDocument,
    LearningSourceDocumentRevision,
    LearningUnit,
    LearningUnitRevision,
)
from newcomer_training.models import (
    NewcomerPath,
    NewcomerPathRevision,
    NewcomerReleasePlan,
)
from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)

REPORT_SCHEMA_VERSION = "foundation_authoring_inventory_v1"
LEGACY_PATH_RESOURCE_TYPE = "newcomer_training_path_orchestration"
STANDARD_PACK_ACTOR = "system:foundation-pack"
FOCUS_ACTIVITY_TITLES = frozenset({"石犀ppt讲解", "demo讲解"})
FOCUS_MATERIAL_NAME = "石犀科技-企业介绍标准版（202606版）.pptx"

_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "credential",
        "credentials",
        "password",
        "private_key",
        "refresh_token",
        "system_prompt",
        "scoring_template",
        "prompt_body",
        "raw_prompt",
        "raw_response",
        "payload_json",
        "snapshot_json",
        "storage_key",
        "source_uri",
        "transcript",
        "token",
        "secret",
    }
)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _items(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_name(value: str | None) -> str:
    return "".join((value or "").split()).casefold()


def _normalize_hash(value: str | None) -> str | None:
    normalized = (value or "").strip().casefold().removeprefix("sha256:")
    return normalized or None


def _safe_contract_hash(value: Mapping[str, object]) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def _seed_source(actor_id: str | None) -> str:
    return (
        "foundation_standard_pack"
        if actor_id == STANDARD_PACK_ACTOR
        else "administrator_or_other"
    )


def _safe_revision(
    *,
    revision_id: str,
    revision_no: int,
    status: str,
    content_hash: str | None,
    created_by: str | None,
    revision_label: str | None = None,
) -> dict[str, object]:
    return {
        "revision_id": revision_id,
        "revision_no": revision_no,
        "revision_label": revision_label,
        "status": status,
        "content_hash": content_hash,
        "seed_source": _seed_source(created_by),
    }


def _extract_legacy_activities(payload: object) -> list[dict[str, object]]:
    """Extract only migration-safe activity metadata from a Legacy path payload."""

    root = _mapping(payload)
    activities: list[dict[str, object]] = []
    for phase_value in _items(root.get("phases")):
        phase = _mapping(phase_value)
        for module_value in _items(phase.get("modules")):
            module = _mapping(module_value)
            for activity_value in _items(module.get("activities")):
                activity = _mapping(activity_value)
                config = _mapping(activity.get("config"))
                activity_id = _string(activity.get("activity_id"))
                title = _string(activity.get("title"))
                if activity_id is None or title is None:
                    continue
                activities.append(
                    {
                        "activity_id": activity_id,
                        "title": title,
                        "activity_type": _string(activity.get("type")) or "unknown",
                        "phase_id": _string(phase.get("phase_id")),
                        "module_id": _string(module.get("module_id")),
                        "material_id": _string(config.get("material_id")),
                        "scoring_prompt_id": _string(config.get("scoring_rubric_id")),
                        "is_focus_activity": title in FOCUS_ACTIVITY_TITLES,
                    }
                )
    return sorted(
        activities, key=lambda item: (str(item["title"]), str(item["activity_id"]))
    )


def _redact(value: object) -> object:
    """Defence-in-depth redaction for all externally rendered inventory values."""

    if isinstance(value, Mapping):
        return {
            str(key): _redact(item)
            for key, item in value.items()
            if str(key).casefold() not in _SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def _foundation_source_matches(
    material: Mapping[str, object],
    sources: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    versions = [_mapping(item) for item in _items(material.get("versions"))]
    selected_hashes = {
        normalized
        for version in versions
        if (normalized := _normalize_hash(_string(version.get("file_hash"))))
    }
    normalized_name = _normalize_name(_string(material.get("name")))
    hash_matches: list[dict[str, object]] = []
    name_matches: list[dict[str, object]] = []
    for source_value in sources:
        source = _mapping(source_value)
        source_revisions = [_mapping(item) for item in _items(source.get("revisions"))]
        matching_revisions = [
            revision
            for revision in source_revisions
            if _normalize_hash(_string(revision.get("file_hash"))) in selected_hashes
            and selected_hashes
        ]
        safe_ref = {
            "document_id": source.get("resource_id"),
            "stable_key": source.get("stable_key"),
            "title": source.get("title"),
            "revision_ids": sorted(
                str(revision.get("revision_id")) for revision in matching_revisions
            ),
        }
        if matching_revisions:
            hash_matches.append(safe_ref)
        if (
            normalized_name
            and _normalize_name(_string(source.get("title"))) == normalized_name
        ):
            name_matches.append(safe_ref)
    return hash_matches, name_matches


def _material_mapping_candidate(
    material: Mapping[str, object],
    sources: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    hash_matches, name_matches = _foundation_source_matches(material, sources)
    versions = [_mapping(item) for item in _items(material.get("versions"))]
    published_versions = [
        version for version in versions if version.get("status") == "published"
    ]
    has_hash = any(_normalize_hash(_string(item.get("file_hash"))) for item in versions)
    if len(hash_matches) == 1:
        disposition = "reuse_exact_hash"
    elif len(hash_matches) > 1:
        disposition = "conflict_same_hash_multiple_targets"
    elif len(name_matches) > 1:
        disposition = "conflict_same_name_multiple_targets"
    elif len(name_matches) == 1:
        disposition = "needs_hash_verification"
    elif not published_versions:
        disposition = "needs_input_no_published_version"
    elif not has_hash:
        disposition = "needs_input_missing_hash"
    else:
        disposition = "create_source_document"
    return {
        "legacy_type": "sales_trainer_material",
        "legacy_id": material.get("material_id"),
        "legacy_name": material.get("name"),
        "target_type": "source_document",
        "content_kind": _material_content_kind(material),
        "disposition": disposition,
        "exact_hash_matches": hash_matches,
        "same_name_matches": name_matches,
        "is_focus_material": material.get("name") == FOCUS_MATERIAL_NAME,
    }


def _material_content_kind(material: Mapping[str, object]) -> str:
    material_type = _string(material.get("material_type"))
    name = (_string(material.get("name")) or "").casefold()
    if material_type == "ppt_deck" or name.endswith((".ppt", ".pptx")):
        return "slide_deck"
    if material_type == "script":
        return "script"
    if material_type == "example_audio":
        return "example_audio"
    return "attachment"


def _activity_mapping_candidate(
    activity: Mapping[str, object],
    *,
    material_ids: set[str],
    prompt_ids: set[str],
) -> dict[str, object]:
    material_id = _string(activity.get("material_id"))
    prompt_id = _string(activity.get("scoring_prompt_id"))
    missing: list[str] = []
    if material_id is None or material_id not in material_ids:
        missing.append("legacy_material")
    if prompt_id is None or prompt_id not in prompt_ids:
        missing.append("verifiable_scoring_prompt")
    title = _string(activity.get("title")) or ""
    return {
        "legacy_type": "sales_trainer_path_activity",
        "legacy_id": activity.get("activity_id"),
        "legacy_title": title,
        "target_activity_type": "audio_assessment",
        "target_resources": ["audio_material", "scoring_scheme"],
        "content_requirement": "slide_deck"
        if title == "石犀ppt讲解"
        else "demo_or_script",
        "disposition": "needs_input" if missing else "ready_for_dry_run",
        "missing_dependencies": missing,
        "is_focus_activity": title in FOCUS_ACTIVITY_TITLES,
    }


def _legacy_material_conflicts(
    materials: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_name: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    by_hash: dict[str, set[str]] = defaultdict(set)
    for material in materials:
        by_name[_normalize_name(_string(material.get("name")))].append(material)
        material_id = _string(material.get("material_id"))
        if material_id is None:
            continue
        for version_value in _items(material.get("versions")):
            version = _mapping(version_value)
            normalized_hash = _normalize_hash(_string(version.get("file_hash")))
            if normalized_hash:
                by_hash[normalized_hash].add(material_id)
    conflicts: list[dict[str, object]] = []
    for normalized_name, group in sorted(by_name.items()):
        if not normalized_name or len(group) < 2:
            continue
        material_ids = sorted(
            value
            for material in group
            if (value := _string(material.get("material_id"))) is not None
        )
        hashes = {
            normalized_hash
            for material in group
            for version_value in _items(material.get("versions"))
            if (
                normalized_hash := _normalize_hash(
                    _string(_mapping(version_value).get("file_hash"))
                )
            )
        }
        has_missing_hash = any(
            not any(
                _normalize_hash(_string(_mapping(version).get("file_hash")))
                for version in _items(material.get("versions"))
            )
            for material in group
        )
        if len(hashes) > 1:
            code = "LEGACY_MATERIAL_SAME_NAME_DIFFERENT_HASH"
        elif has_missing_hash:
            code = "LEGACY_MATERIAL_SAME_NAME_INCOMPLETE_HASH"
        else:
            code = "LEGACY_MATERIAL_SAME_NAME_SAME_HASH_MERGE_CANDIDATE"
        conflicts.append(
            {
                "code": code,
                "normalized_name": normalized_name,
                "material_ids": material_ids,
                "known_hash_count": len(hashes),
            }
        )
    for normalized_hash, hash_material_ids in sorted(by_hash.items()):
        if len(hash_material_ids) > 1:
            conflicts.append(
                {
                    "code": "LEGACY_MATERIAL_SAME_HASH_MULTIPLE_LOGICAL_OBJECTS",
                    "hash": normalized_hash,
                    "material_ids": sorted(hash_material_ids),
                }
            )
    return conflicts


def build_inventory_report(
    *,
    legacy: Mapping[str, object],
    organizations: Sequence[Mapping[str, object]],
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build a deterministic, safe report from already read-only metadata."""

    material_values = [_mapping(item) for item in _items(legacy.get("materials"))]
    prompt_values = [_mapping(item) for item in _items(legacy.get("scoring_prompts"))]
    path_values = [_mapping(item) for item in _items(legacy.get("active_paths"))]
    legacy_material_conflicts = _legacy_material_conflicts(material_values)
    material_conflict_codes: dict[str, list[str]] = defaultdict(list)
    for conflict in legacy_material_conflicts:
        for material_id in _items(conflict.get("material_ids")):
            material_conflict_codes[str(material_id)].append(str(conflict["code"]))
    activities = [
        _mapping(activity)
        for path in path_values
        for activity in _items(path.get("activities"))
    ]
    material_ids = {
        value
        for item in material_values
        if (value := _string(item.get("material_id"))) is not None
    }
    prompt_ids = {
        value
        for item in prompt_values
        if (value := _string(item.get("prompt_id"))) is not None
    }
    organization_reports: list[dict[str, object]] = []
    for organization_value in sorted(
        organizations, key=lambda item: str(item.get("organization_id") or "")
    ):
        organization = _mapping(organization_value)
        foundation = _mapping(organization.get("foundation"))
        sources = [
            _mapping(item) for item in _items(foundation.get("source_documents"))
        ]
        material_candidates = [
            _material_mapping_candidate(material, sources)
            for material in material_values
        ]
        for candidate in material_candidates:
            legacy_id = str(candidate.get("legacy_id") or "")
            codes = sorted(material_conflict_codes.get(legacy_id, []))
            candidate["legacy_conflicts"] = codes
            blocking_codes = [
                code
                for code in codes
                if code != "LEGACY_MATERIAL_SAME_NAME_SAME_HASH_MERGE_CANDIDATE"
            ]
            if blocking_codes:
                candidate["disposition"] = "conflict_legacy_material_identity"
        activity_candidates = [
            _activity_mapping_candidate(
                activity,
                material_ids=material_ids,
                prompt_ids=prompt_ids,
            )
            for activity in activities
            if activity.get("is_focus_activity") is True
        ]
        conflicts = list(legacy_material_conflicts) + [
            {
                "object_type": candidate["legacy_type"],
                "object_id": candidate["legacy_id"],
                "reason": candidate["disposition"],
            }
            for candidate in material_candidates
            if str(candidate["disposition"]).startswith("conflict_")
        ]
        missing_dependencies = [
            {
                "object_type": candidate["legacy_type"],
                "object_id": candidate["legacy_id"],
                "missing": candidate.get("missing_dependencies", []),
            }
            for candidate in activity_candidates
            if candidate.get("missing_dependencies")
        ]
        create_sources = sum(
            candidate["disposition"] == "create_source_document"
            for candidate in material_candidates
        )
        ready_activities = sum(
            candidate["disposition"] == "ready_for_dry_run"
            for candidate in activity_candidates
        )
        organization_reports.append(
            {
                "organization_id": organization.get("organization_id"),
                "foundation": foundation,
                "mapping_candidates": {
                    "materials": material_candidates,
                    "focus_activities": activity_candidates,
                },
                "conflicts": conflicts,
                "missing_dependencies": missing_dependencies,
                "estimated_new_objects": {
                    "source_documents": create_sources,
                    "audio_materials": ready_activities,
                    "scoring_schemes": ready_activities,
                    "path_activities": ready_activities,
                },
                "recommended_migration_order": [
                    "resolve_organization_scope",
                    "resolve_material_hash_and_file_availability",
                    "create_or_reuse_source_document_revisions",
                    "review_scoring_prompt_contracts",
                    "create_audio_material_and_scoring_scheme_working_revisions",
                    "clone_path_and_upsert_focus_activities",
                    "validate_release_plan_without_publishing",
                ],
            }
        )
    legacy_report = dict(legacy)
    legacy_report["material_conflicts"] = legacy_material_conflicts
    legacy_report["unverifiable_items"] = [
        {
            "object_type": "sales_trainer_audio_score_prompt",
            "object_id": prompt.get("prompt_id"),
            "reason": "requires_governed_prompt_model_schema_review",
            "referenced_by_activity_ids": prompt.get("referenced_by_activity_ids", []),
        }
        for prompt in prompt_values
    ]
    report: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "mode": "read_only",
        "writes_performed": 0,
        "legacy_scope": "global_unscoped",
        "legacy": legacy_report,
        "organizations": organization_reports,
        "unresolved_scope": (
            []
            if not material_values and not activities
            else [
                {
                    "code": "LEGACY_ORGANIZATION_SCOPE_UNRESOLVED",
                    "message": (
                        "Legacy sales_trainer authoring rows have no organization_id; "
                        "a target organization must be selected before dry-run/apply."
                    ),
                }
            ]
        ),
        "safety": {
            "database_mode": "read_only_transaction_when_supported",
            "apply_supported": False,
            "redacted_fields": sorted(_SENSITIVE_KEYS),
        },
    }
    return _redact(report)  # type: ignore[return-value]


async def _enable_read_only_transaction(session: AsyncSession) -> None:
    connection = await session.connection()
    if connection.dialect.name == "postgresql":
        await session.execute(text("SET TRANSACTION READ ONLY"))


async def collect_inventory(
    session: AsyncSession,
    *,
    organization_ids: Sequence[str] = (),
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Read all required metadata without flushing or committing any ORM state."""

    register_all_models()
    await _enable_read_only_transaction(session)
    active_rows = (
        await session.execute(
            select(SalesTrainerAssetActiveRevision, SalesTrainerAssetRevision)
            .join(
                SalesTrainerAssetRevision,
                SalesTrainerAssetRevision.revision_id
                == SalesTrainerAssetActiveRevision.active_revision_id,
            )
            .where(
                SalesTrainerAssetActiveRevision.resource_type
                == LEGACY_PATH_RESOURCE_TYPE
            )
            .order_by(SalesTrainerAssetActiveRevision.logical_id.asc())
        )
    ).all()
    active_paths = [
        {
            "logical_id": active.logical_id,
            "active_revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "status": revision.status,
            "payload_hash": revision.payload_hash,
            "schema_version": _string(
                _mapping(revision.payload_json).get("schema_version")
            ),
            "title": _string(_mapping(revision.payload_json).get("title")),
            "activities": _extract_legacy_activities(revision.payload_json),
        }
        for active, revision in active_rows
    ]

    materials = list(
        (
            await session.execute(
                select(SalesTrainerMaterial).order_by(
                    SalesTrainerMaterial.name.asc(),
                    SalesTrainerMaterial.material_id.asc(),
                )
            )
        ).scalars()
    )
    versions = list(
        (
            await session.execute(
                select(SalesTrainerMaterialVersion).order_by(
                    SalesTrainerMaterialVersion.material_id.asc(),
                    SalesTrainerMaterialVersion.created_at.asc(),
                    SalesTrainerMaterialVersion.version_id.asc(),
                )
            )
        ).scalars()
    )
    versions_by_material: dict[str, list[dict[str, object]]] = defaultdict(list)
    for version in versions:
        versions_by_material[str(version.material_id)].append(
            {
                "version_id": version.version_id,
                "version_label": version.version_label,
                "title": version.title,
                "file_name": version.file_name,
                "content_type": version.content_type,
                "file_size_bytes": version.file_size_bytes,
                "file_hash": version.file_hash,
                "status": version.status,
            }
        )
    legacy_materials: list[dict[str, object]] = []
    for material in materials:
        material_id = str(material.material_id)
        legacy_materials.append(
            {
                "material_id": material_id,
                "material_key": material.material_key,
                "name": material.name,
                "material_type": material.material_type,
                "purpose": material.purpose,
                "status": material.status,
                "current_version_id": material.current_version_id,
                "versions": versions_by_material.get(material_id, []),
            }
        )

    prompts = list(
        (
            await session.execute(
                select(SalesTrainerAudioScorePrompt).order_by(
                    SalesTrainerAudioScorePrompt.name.asc(),
                    SalesTrainerAudioScorePrompt.prompt_id.asc(),
                )
            )
        ).scalars()
    )
    prompt_references: dict[str, list[str]] = defaultdict(list)
    for path in active_paths:
        for activity_value in _items(path.get("activities")):
            activity = _mapping(activity_value)
            prompt_id = _string(activity.get("scoring_prompt_id"))
            activity_id = _string(activity.get("activity_id"))
            if prompt_id and activity_id:
                prompt_references[prompt_id].append(activity_id)
    legacy_prompts = [
        {
            "prompt_id": prompt.prompt_id,
            "name": prompt.name,
            "purpose": prompt.purpose,
            "status": prompt.status,
            "version": prompt.version,
            "verification_state": "requires_governed_contract_review",
            "contract_hash": _safe_contract_hash(
                {
                    "system_prompt": prompt.system_prompt,
                    "scoring_template": prompt.scoring_template,
                    "output_schema": prompt.output_schema,
                    "learner_rubric": prompt.learner_rubric,
                }
            ),
            "output_schema_keys": sorted(
                str(key) for key in _mapping(prompt.output_schema)
            ),
            "learner_rubric_keys": sorted(
                str(key) for key in _mapping(prompt.learner_rubric)
            ),
            "referenced_by_activity_ids": sorted(
                prompt_references[str(prompt.prompt_id)]
            ),
        }
        for prompt in prompts
    ]

    organization_filter = tuple(sorted(set(organization_ids)))
    foundation = await _collect_foundation(
        session,
        organization_ids=organization_filter,
    )
    legacy = {
        "active_paths": active_paths,
        "materials": legacy_materials,
        "scoring_prompts": legacy_prompts,
        "counts": {
            "active_paths": len(active_paths),
            "activities": sum(len(path["activities"]) for path in active_paths),
            "materials": len(legacy_materials),
            "material_versions": len(versions),
            "scoring_prompts": len(legacy_prompts),
        },
    }
    report = build_inventory_report(
        legacy=legacy,
        organizations=foundation,
        generated_at=generated_at,
    )
    await session.rollback()
    return report


async def _collect_foundation(
    session: AsyncSession,
    *,
    organization_ids: Sequence[str],
) -> list[dict[str, object]]:
    models = (
        LearningSourceDocument,
        LearningSourceDocumentRevision,
        LearningUnit,
        LearningUnitRevision,
        LearningQuestion,
        LearningQuestionRevision,
        LearningQuestionCandidate,
        LearningQuiz,
        LearningQuizRevision,
        AudioActivityResourceRevision,
        CoachProfileRevision,
        NewcomerPath,
        NewcomerPathRevision,
        NewcomerReleasePlan,
    )
    rows: dict[type[Any], list[Any]] = {}
    for model in models:
        statement = select(model)
        if organization_ids:
            statement = statement.where(model.organization_id.in_(organization_ids))
        rows[model] = list((await session.execute(statement)).scalars())

    discovered = set(organization_ids)
    for model_rows in rows.values():
        discovered.update(str(row.organization_id) for row in model_rows)
    organizations: list[dict[str, object]] = []
    for organization_id in sorted(discovered):
        organizations.append(
            {
                "organization_id": organization_id,
                "foundation": _foundation_organization_summary(
                    organization_id=organization_id,
                    rows=rows,
                ),
            }
        )
    return organizations


def _foundation_organization_summary(
    *,
    organization_id: str,
    rows: Mapping[type[Any], Sequence[Any]],
) -> dict[str, object]:
    def scoped(model: type[Any]) -> list[Any]:
        return [
            row for row in rows.get(model, ()) if row.organization_id == organization_id
        ]

    source_revisions = scoped(LearningSourceDocumentRevision)
    unit_revisions = scoped(LearningUnitRevision)
    question_revisions = scoped(LearningQuestionRevision)
    quiz_revisions = scoped(LearningQuizRevision)
    path_revisions = scoped(NewcomerPathRevision)
    return {
        "source_documents": _logical_resource_rows(
            resource_type="source_document",
            resources=scoped(LearningSourceDocument),
            revisions=source_revisions,
            identity_attr="document_id",
            revision_parent_attr="document_id",
            label_attr="revision_label",
            extra_revision=lambda revision: {
                "file_hash": revision.file_hash,
                "parse_status": revision.parse_status,
                "source_type": revision.source_type,
            },
        ),
        "learning_units": _logical_resource_rows(
            resource_type="learning_unit",
            resources=scoped(LearningUnit),
            revisions=unit_revisions,
            identity_attr="unit_id",
            revision_parent_attr="unit_id",
            label_attr="revision_label",
        ),
        "questions": _logical_resource_rows(
            resource_type="question",
            resources=scoped(LearningQuestion),
            revisions=question_revisions,
            identity_attr="question_id",
            revision_parent_attr="question_id",
            label_attr=None,
            extra_revision=lambda revision: {"question_type": revision.question_type},
        ),
        "question_candidate_counts": _status_counts(scoped(LearningQuestionCandidate)),
        "quizzes": _logical_resource_rows(
            resource_type="quiz",
            resources=scoped(LearningQuiz),
            revisions=quiz_revisions,
            identity_attr="quiz_id",
            revision_parent_attr="quiz_id",
            label_attr="revision_label",
        ),
        "audio_resources": _revision_only_resource_rows(
            scoped(AudioActivityResourceRevision),
            resource_type_attr="resource_type",
        ),
        "coach_profiles": _revision_only_resource_rows(
            scoped(CoachProfileRevision),
            fixed_resource_type="coach_profile",
        ),
        "paths": _logical_resource_rows(
            resource_type="path",
            resources=scoped(NewcomerPath),
            revisions=path_revisions,
            identity_attr="path_id",
            revision_parent_attr="path_id",
            label_attr="revision_label",
            extra_resource=lambda path: {
                "active_release_plan_id": path.active_release_plan_id
            },
        ),
        "release_plans": [
            {
                "release_plan_id": plan.release_plan_id,
                "path_id": plan.path_id,
                "path_revision_id": plan.path_revision_id,
                "status": plan.status,
                "version": plan.version,
                "contract_hash": plan.contract_hash,
            }
            for plan in sorted(
                scoped(NewcomerReleasePlan),
                key=lambda item: (item.path_id, item.version, item.release_plan_id),
            )
        ],
        "counts": {
            "source_documents": len(scoped(LearningSourceDocument)),
            "learning_units": len(scoped(LearningUnit)),
            "questions": len(scoped(LearningQuestion)),
            "question_candidates": len(scoped(LearningQuestionCandidate)),
            "quizzes": len(scoped(LearningQuiz)),
            "audio_resource_revisions": len(scoped(AudioActivityResourceRevision)),
            "coach_profile_revisions": len(scoped(CoachProfileRevision)),
            "paths": len(scoped(NewcomerPath)),
            "release_plans": len(scoped(NewcomerReleasePlan)),
        },
    }


def _logical_resource_rows(
    *,
    resource_type: str,
    resources: Sequence[Any],
    revisions: Sequence[Any],
    identity_attr: str,
    revision_parent_attr: str,
    label_attr: str | None,
    extra_revision: Any = None,
    extra_resource: Any = None,
) -> list[dict[str, object]]:
    revisions_by_parent: dict[str, list[Any]] = defaultdict(list)
    for revision in revisions:
        revisions_by_parent[str(getattr(revision, revision_parent_attr))].append(
            revision
        )
    result: list[dict[str, object]] = []
    for resource in sorted(
        resources,
        key=lambda item: (
            str(getattr(item, "stable_key", "")),
            str(getattr(item, identity_attr)),
        ),
    ):
        identity = str(getattr(resource, identity_attr))
        revision_rows: list[dict[str, object]] = []
        for revision in sorted(
            revisions_by_parent.get(identity, []),
            key=lambda item: (item.revision_no, item.revision_id),
        ):
            safe = _safe_revision(
                revision_id=revision.revision_id,
                revision_no=revision.revision_no,
                revision_label=(
                    str(getattr(revision, label_attr)) if label_attr else None
                ),
                status=revision.status,
                content_hash=getattr(revision, "content_hash", None),
                created_by=getattr(revision, "created_by", None),
            )
            if extra_revision is not None:
                safe.update(extra_revision(revision))
            revision_rows.append(safe)
        safe_resource: dict[str, object] = {
            "resource_type": resource_type,
            "resource_id": identity,
            "stable_key": getattr(resource, "stable_key", None),
            "title": getattr(resource, "title", None),
            "status": resource.status,
            "working_revision_id": resource.working_revision_id,
            "published_revision_id": resource.published_revision_id,
            "pointer_source": "persisted",
            "revisions": revision_rows,
        }
        if extra_resource is not None:
            safe_resource.update(extra_resource(resource))
        result.append(safe_resource)
    return result


def _revision_only_resource_rows(
    revisions: Sequence[Any],
    *,
    resource_type_attr: str | None = None,
    fixed_resource_type: str | None = None,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for revision in revisions:
        resource_type = (
            str(getattr(revision, resource_type_attr))
            if resource_type_attr
            else str(fixed_resource_type)
        )
        grouped[(resource_type, revision.stable_key)].append(revision)
    result: list[dict[str, object]] = []
    for (resource_type, stable_key), values in sorted(grouped.items()):
        ordered = sorted(values, key=lambda item: (item.revision_no, item.revision_id))
        working = [item for item in ordered if item.status == "working"]
        published = [item for item in ordered if item.status == "published"]
        latest = ordered[-1]
        result.append(
            {
                "resource_type": resource_type,
                "resource_id": None,
                "stable_key": stable_key,
                "title": getattr(latest, "title", None)
                or _string(_mapping(latest.snapshot_json).get("title")),
                "status": latest.status,
                "working_revision_id": working[-1].revision_id if working else None,
                "published_revision_id": (
                    published[-1].revision_id if published else None
                ),
                "pointer_source": "derived_missing_logical_container",
                "revisions": [
                    _safe_revision(
                        revision_id=revision.revision_id,
                        revision_no=revision.revision_no,
                        revision_label=getattr(revision, "revision_label", None),
                        status=revision.status,
                        content_hash=revision.content_hash,
                        created_by=revision.created_by,
                    )
                    for revision in ordered
                ],
            }
        )
    return result


def _status_counts(rows: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.status)] += 1
    return dict(sorted(counts.items()))


def render_markdown(report: Mapping[str, object]) -> str:
    legacy = _mapping(report.get("legacy"))
    counts = _mapping(legacy.get("counts"))
    lines = [
        "# 新人训练内容生产只读清单",
        "",
        f"- Schema：`{report.get('schema_version')}`",
        f"- 生成时间：`{report.get('generated_at')}`",
        "- 模式：只读；不支持 apply；写入数始终为 0。",
        "- Legacy 组织范围：全局且未分组织，迁移前必须人工选择目标组织。",
        "",
        "## Legacy 摘要",
        "",
        f"- Active 路径：{counts.get('active_paths', 0)}",
        f"- 活动：{counts.get('activities', 0)}",
        f"- 材料 / 版本：{counts.get('materials', 0)} / {counts.get('material_versions', 0)}",
        (
            f"- 评分 Prompt 元数据：{counts.get('scoring_prompts', 0)}"
            "（正文已脱敏；迁移前均需治理合同复核）"
        ),
        "",
    ]
    for organization_value in _items(report.get("organizations")):
        organization = _mapping(organization_value)
        foundation = _mapping(organization.get("foundation"))
        mapping = _mapping(organization.get("mapping_candidates"))
        lines.extend(
            [
                f"## 组织 `{organization.get('organization_id')}`",
                "",
                "### Foundation 计数",
                "",
            ]
        )
        for key, value in sorted(_mapping(foundation.get("counts")).items()):
            lines.append(f"- {key}: {value}")
        lines.extend(["", "### 重点迁移候选", ""])
        for candidate_value in _items(mapping.get("focus_activities")):
            candidate = _mapping(candidate_value)
            missing = ", ".join(
                str(item) for item in _items(candidate.get("missing_dependencies"))
            )
            lines.append(
                f"- `{candidate.get('legacy_title')}` → `audio_assessment`："
                f"{candidate.get('disposition')}"
                + (f"；缺失 {missing}" if missing else "")
            )
        for candidate_value in _items(mapping.get("materials")):
            candidate = _mapping(candidate_value)
            if candidate.get("is_focus_material") is True:
                lines.append(
                    f"- `{candidate.get('legacy_name')}` → `source_document/slide_deck`："
                    f"{candidate.get('disposition')}"
                )
        if not _items(mapping.get("focus_activities")):
            lines.append("- 未定位到 `石犀ppt讲解` 或 `demo讲解`。")
        lines.append("")
    if not _items(report.get("organizations")):
        lines.extend(
            [
                "## 组织清单",
                "",
                "未发现 Foundation 组织数据；如需评估纯 Legacy 库，请显式传入 `--organization-id`。",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--organization-id",
        action="append",
        default=[],
        help="Limit Foundation inventory and project global Legacy candidates to this organization.",
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="stdout format when no output file is requested.",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        return await collect_inventory(
            session,
            organization_ids=tuple(args.organization_id),
        )


def main() -> None:
    args = _arguments()
    report = asyncio.run(_run(args))
    json_text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    markdown_text = render_markdown(report)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json_text, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown_text, encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        sys.stdout.write(json_text if args.format == "json" else markdown_text)


if __name__ == "__main__":
    main()
