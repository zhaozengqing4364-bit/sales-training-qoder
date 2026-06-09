# Curriculum PracticeTemplate Revision Slice Evidence

Date: 2026-06-04

Scope: Stage 5 `curriculum_practice` alignment for `PracticeTemplate`.

## Behavior Proven

- Initial publish of a draft `PracticeTemplate` creates a
  `curriculum_practice_template` published revision and active pointer.
- Editing a published `PracticeTemplate` no longer returns the old draft-only
  lock behavior for ordinary edits.
- Editing a published `PracticeTemplate` saves a working revision and keeps the
  active/live template payload unchanged until republish.
- Reading the template after saving the working revision still returns the old
  active description.
- Republishing applies the frozen working payload, increments `version` to 2,
  and moves the active pointer by publishing that same revision.
- Existing `PracticeTemplate`, `CaseItem`, and `RoleProfile` integration flows
  continue to pass.
- Publish gate resolution still goes through the existing business-rule-backed
  situation pack configuration path.

## Commands

```bash
cd backend && venv/bin/ruff check src/curriculum_practice/services/practice_templates.py src/curriculum_practice/services/practice_template_revision_payloads.py src/curriculum_practice/services/practice_template_revision_metadata.py src/curriculum_practice/services/practice_template_revision_service.py src/curriculum_practice/services/practice_template_publish_gate_factory.py tests/integration/test_practice_template_api.py
```

Result: `All checks passed!`.

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_practice_template_api.py::test_should_stage_future_revision_when_published_practice_template_is_edited -q --no-cov
```

Result: `1 passed, 1 warning`.

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_practice_template_api.py -q --no-cov
```

Result: `12 passed, 1 warning`.

Warning: third-party `chromadb` uses deprecated
`asyncio.iscoroutinefunction` under Python 3.14. This warning is unrelated to
the PracticeTemplate revision slice.

## File Size Guard

Pure LOC after split:

- `practice_templates.py`: 146
- `practice_template_revision_payloads.py`: 169
- `practice_template_revision_metadata.py`: 107
- `practice_template_revision_service.py`: 227
- `practice_template_publish_gate_factory.py`: 40

## Residual Scope

This is one curriculum alignment slice only. The full unified publish governance
goal remains active: `CaseItem`, `RoleProfile`, `ExaminerAgent`, full
`published_asset_refs` revision id/hash upgrades, `curriculum_snapshot` lineage,
frontend natural-edit UI, rollback, high-risk regrade, browser acceptance, and
cross-object completion audit are not yet complete.
