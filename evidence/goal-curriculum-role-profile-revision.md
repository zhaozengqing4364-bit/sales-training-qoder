# Curriculum RoleProfile Revision Slice Evidence

Date: 2026-06-04

Scope: Stage 5 `curriculum_practice` alignment for `RoleProfile`.

## Behavior Proven

- Publishing a draft `RoleProfile` with a real actor creates a
  `curriculum_role_profile` published revision and active pointer.
- Editing a published `RoleProfile` saves a future-only working revision instead
  of mutating the active row.
- Reading the `RoleProfile` after saving a working revision still returns the
  old active pressure level.
- Republishing applies the frozen working payload, increments `version` to 2,
  and publishes that same working revision as the active revision.
- Existing `CaseItem`/`RoleProfile` unit tests continue to pass.
- Existing `PracticeTemplate` integration flows continue to pass, proving the
  RoleProfile revision path did not break template publishing or references.

## Commands

```bash
cd backend && venv/bin/python -m pytest tests/unit/test_curriculum_content_asset_revisions.py -q --no-cov
```

Red result before implementation: failed because no
`curriculum_role_profile` published revision existed after publish.

Green result after implementation: `2 passed`.

```bash
cd backend && venv/bin/python -m pytest tests/unit/test_curriculum_content_asset_revisions.py tests/unit/test_case_item_role_profile_assets.py -q --no-cov
```

Result: `19 passed`.

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_practice_template_api.py -q --no-cov
```

Result: `12 passed, 1 warning`.

```bash
cd backend && venv/bin/ruff check src/curriculum_practice/services/content_assets.py src/curriculum_practice/services/content_asset_duplicates.py src/curriculum_practice/services/role_profile_asset_service.py src/curriculum_practice/services/content_asset_payloads.py src/curriculum_practice/services/content_asset_references.py src/curriculum_practice/services/content_asset_revision_metadata.py src/curriculum_practice/services/case_item_revision_service.py src/curriculum_practice/services/role_profile_revision_service.py tests/unit/test_curriculum_content_asset_revisions.py tests/unit/test_case_item_role_profile_assets.py
```

Result: `All checks passed!`.

Warning: third-party `chromadb` uses deprecated
`asyncio.iscoroutinefunction` under Python 3.14. This warning is unrelated to
the RoleProfile revision slice.

## File Size Guard

Pure LOC after split:

- `content_assets.py`: 249
- `role_profile_asset_service.py`: 208
- `role_profile_revision_service.py`: 173
- `content_asset_payloads.py`: 205
- `content_asset_revision_metadata.py`: 127
- `case_item_revision_service.py`: 167

## Residual Scope

This is one curriculum alignment slice only. The full unified publish governance
goal remains active: `ExaminerAgent`, full `published_asset_refs` revision
id/hash upgrades, `curriculum_snapshot` lineage, frontend natural-edit UI,
rollback, high-risk regrade, browser acceptance, and cross-object completion
audit are not yet complete.
