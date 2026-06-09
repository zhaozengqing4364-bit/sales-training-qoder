# Curriculum CaseItem Revision Slice Evidence

Date: 2026-06-04

Scope: Stage 5 `curriculum_practice` alignment for `CaseItem`.

## Behavior Proven

- Publishing a draft `CaseItem` with a real actor creates a
  `curriculum_case_item` published revision and active pointer.
- Editing a published `CaseItem` saves a future-only working revision instead of
  mutating the active row.
- Reading the `CaseItem` after saving a working revision still returns the old
  active customer role.
- Republishing applies the frozen working payload, increments `version` to 2,
  and publishes that same working revision as the active revision.
- Existing `CaseItem`/`RoleProfile` unit tests continue to pass.
- Existing `PracticeTemplate` integration flows continue to pass, proving the
  content-asset split did not break template publishing or references.
- `content_assets.py` was split below the 250 pure-LOC ceiling while preserving
  legacy exports used by existing callers.

## Commands

```bash
cd backend && venv/bin/python -m pytest tests/unit/test_curriculum_content_asset_revisions.py -q --no-cov
```

Red result before implementation: failed because no
`curriculum_case_item` published revision existed after publish.

Green result after implementation: `1 passed`.

```bash
cd backend && venv/bin/ruff check src/curriculum_practice/services/content_assets.py src/curriculum_practice/services/content_asset_duplicates.py src/curriculum_practice/services/role_profile_asset_service.py src/curriculum_practice/services/content_asset_payloads.py src/curriculum_practice/services/content_asset_references.py src/curriculum_practice/services/content_asset_revision_metadata.py src/curriculum_practice/services/case_item_revision_service.py tests/unit/test_curriculum_content_asset_revisions.py tests/unit/test_case_item_role_profile_assets.py
```

Result: `All checks passed!`.

```bash
cd backend && venv/bin/python -m pytest tests/unit/test_curriculum_content_asset_revisions.py tests/unit/test_case_item_role_profile_assets.py -q --no-cov
```

Result: `18 passed`.

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_practice_template_api.py -q --no-cov
```

Result: `12 passed, 1 warning`.

Warning: third-party `chromadb` uses deprecated
`asyncio.iscoroutinefunction` under Python 3.14. This warning is unrelated to
the CaseItem revision slice.

## File Size Guard

Pure LOC after split:

- `content_assets.py`: 249
- `content_asset_duplicates.py`: 31
- `role_profile_asset_service.py`: 176
- `content_asset_payloads.py`: 158
- `content_asset_references.py`: 31
- `content_asset_revision_metadata.py`: 65
- `case_item_revision_service.py`: 167

## Residual Scope

This is one curriculum alignment slice only. The full unified publish governance
goal remains active: `RoleProfile`, `ExaminerAgent`, full `published_asset_refs`
revision id/hash upgrades, `curriculum_snapshot` lineage, frontend natural-edit
UI, rollback, high-risk regrade, browser acceptance, and cross-object
completion audit are not yet complete.
