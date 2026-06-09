# Curriculum QuestionItem Revision Slice Evidence

Date: 2026-06-04

Scope: Stage 5 `curriculum_practice` alignment for general TestBank
`QuestionItem`.

## Behavior Proven

- Initial publish of a draft TestBank `QuestionItem` creates an immutable
  `curriculum_question_item` published revision and active pointer.
- Editing a published TestBank `QuestionItem` no longer returns
  `[QUESTION_ITEM_NOT_EDITABLE]` for ordinary edits.
- Editing a published TestBank `QuestionItem` saves a working revision and keeps
  the currently active row unchanged until republish.
- Reading the question after saving the working revision still returns the old
  active title.
- Publishing the working revision applies the frozen payload to the logical
  question, increments the question version, and moves the active pointer for
  future use.
- Existing TestBank API and contract tests continue to pass.
- The large `test_bank.py` service was split so touched files stay under the 250
  pure-LOC ceiling.

## Commands

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_test_bank_api.py::test_should_create_edit_filter_publish_archive_question_and_keep_snapshot_immutable -q --no-cov
```

Red result before implementation:
`409 [QUESTION_ITEM_NOT_EDITABLE]` when PUT updated a published question.

Green result after implementation: `1 passed, 1 warning`.

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_test_bank_api.py tests/contract/test_test_bank_api_contract.py -q --no-cov
```

Result: `8 passed, 1 warning`.

```bash
cd backend && venv/bin/ruff check src/curriculum_practice/services/test_bank.py src/curriculum_practice/services/test_bank_constants.py src/curriculum_practice/services/test_bank_questions.py src/curriculum_practice/services/test_bank_question_rules.py src/curriculum_practice/services/test_bank_question_revision_payloads.py src/curriculum_practice/services/test_bank_question_revision_service.py tests/integration/test_test_bank_api.py
```

Result: `All checks passed!`.

## File Size Guard

Pure LOC after split:

- `test_bank.py`: 216
- `test_bank_questions.py`: 247
- `test_bank_question_rules.py`: 78
- `test_bank_question_revision_payloads.py`: 238
- `test_bank_question_revision_service.py`: 173

## Residual Scope

This is one curriculum alignment slice only. The full unified publish governance
goal remains active: other `curriculum_practice` assets, full path-level
rollback, historical regrade, frontend browser acceptance, and cross-object
completion audit are not yet complete.
