# Curriculum Published Asset Refs Lineage Slice

## Scope

This slice advances the unified publish governance goal for
`curriculum_practice` published asset references.

It does not claim the full published-governance goal is complete.

## Changes

- `PublishedAssetRef` and `PublishedAssetRefSchema` now carry optional
  `logical_id`, `revision_id`, and `revision_no`.
- PracticeTemplate `published_asset_refs` preserve revision lineage for
  revision-governed assets when the reference reader supplies active revision
  data.
- Database-backed asset reference reads now resolve active revision lineage
  through `sales_trainer_asset_active_revisions` using
  `resource_type + logical_id`.
- `curriculum_practice.schemas` was split into responsibility-focused schema
  modules while preserving the legacy `curriculum_practice.schemas` import
  surface.

## Regression Fixed

The first DB-backed lineage implementation attempted to fetch
`SalesTrainerAssetActiveRevision` with `(resource_type, logical_id)` via
`session.get()`. The table primary key is `active_ref_id`, so PracticeTemplate
publish and runtime dossier preview returned 500. The lineage reader now uses
an explicit `select()` by `resource_type` and `logical_id`.

## Verification

- `cd backend && venv/bin/python -m pytest tests/unit/test_practice_template_published_asset_refs.py tests/unit/test_published_asset_ref.py tests/unit/test_asset_ref_schema.py -q --no-cov`
  - Result: 15 passed.
- `cd backend && venv/bin/python -m pytest tests/integration/test_practice_template_api.py::test_should_publish_practice_template_when_gate_passes tests/integration/test_practice_template_api.py::test_should_preview_runtime_dossier_before_template_publish -q --no-cov`
  - Result after fix: 2 passed, 1 warning.
- `cd backend && venv/bin/python -m pytest tests/integration/test_practice_template_api.py::test_should_freeze_revision_lineage_in_published_asset_refs -q --no-cov`
  - Result: 1 passed, 1 warning.
  - Coverage: creates and publishes CaseItem/RoleProfile through admin APIs,
    publishes a PracticeTemplate, then asserts `case_item_ref` and
    `role_profile_ref` include `logical_id`, `revision_id`, and `revision_no`.
- `cd backend && venv/bin/python -m pytest tests/unit/test_practice_template_published_asset_refs.py tests/unit/test_published_asset_ref.py tests/unit/test_asset_ref_schema.py tests/integration/test_examiner_agent_api.py tests/integration/test_practice_template_api.py tests/integration/test_test_bank_api.py tests/integration/test_curriculum_learning_content_revisions.py tests/unit/test_curriculum_content_asset_revisions.py -q --no-cov`
  - Result: 45 passed, 1 warning.
- `cd backend && venv/bin/ruff check src/curriculum_practice/schemas.py src/curriculum_practice/asset_ref_schemas.py src/curriculum_practice/schema_types.py src/curriculum_practice/content_asset_schemas.py src/curriculum_practice/learning_content_schemas.py src/curriculum_practice/question_bank_schemas.py src/curriculum_practice/curriculum_runtime_schemas.py src/curriculum_practice/practice_template_schemas.py src/curriculum_practice/examiner_agent_schemas.py src/curriculum_practice/learner_schemas.py src/curriculum_practice/runtime_dossier_schemas.py src/curriculum_practice/publish_gate_schemas.py src/curriculum_practice/services/asset_references.py src/curriculum_practice/services/asset_reference_reader.py src/curriculum_practice/services/asset_reference_lineage.py src/curriculum_practice/services/published_asset_refs.py src/curriculum_practice/services/published_asset_ref_lineage.py tests/unit/test_practice_template_published_asset_refs.py tests/unit/test_published_asset_ref.py tests/unit/test_asset_ref_schema.py tests/integration/test_examiner_agent_api.py tests/integration/test_practice_template_api.py`
  - Result: All checks passed.

## File Size Check

Pure LOC after split:

- `backend/src/curriculum_practice/schemas.py`: 123
- `backend/src/curriculum_practice/content_asset_schemas.py`: 87
- `backend/src/curriculum_practice/question_bank_schemas.py`: 119
- `backend/src/curriculum_practice/curriculum_runtime_schemas.py`: 106
- `backend/src/curriculum_practice/practice_template_schemas.py`: 104
- `backend/src/curriculum_practice/examiner_agent_schemas.py`: 78
- `backend/src/curriculum_practice/learner_schemas.py`: 39
- `backend/src/curriculum_practice/runtime_dossier_schemas.py`: 26
- `backend/src/curriculum_practice/publish_gate_schemas.py`: 11
- `backend/src/curriculum_practice/services/asset_references.py`: 230
- `backend/src/curriculum_practice/services/asset_reference_reader.py`: 243
- `backend/src/curriculum_practice/services/asset_reference_lineage.py`: 39

## Remaining Goal Work

The broader goal remains active: sales_trainer path source-of-truth, UI natural
editing, rollback/regrade surfaces, RBAC, diagnostics, browser evidence, and
final quality gate still require completion evidence.
