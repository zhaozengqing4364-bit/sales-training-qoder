# Curriculum LearningContent Revision Slice Evidence

Date: 2026-06-04

Scope: Stage 5 curriculum_practice alignment for `LearningContent`.

## Behavior Proven

- Initial publish of a draft `LearningContent` creates an immutable
  `curriculum_learning_content` published revision and active pointer.
- Editing a published `LearningContent` no longer mutates the active content.
  It saves a working revision with `source_revision_id` pointing at the active
  revision.
- Editing a chapter that belongs to a published `LearningContent` no longer
  mutates the live `LearningChapter` row. It saves the changed chapter payload
  into a working revision and returns the still-active chapter content.
- Adding a chapter to a published `LearningContent` no longer inserts a live
  `LearningChapter` row immediately. It saves the new chapter in a working
  revision; current reads keep the old chapter list until republish.
- Deleting a chapter from a published `LearningContent` no longer removes the
  live `LearningChapter` row immediately. It removes the chapter only from the
  working revision payload until republish.
- Reordering chapters on a published `LearningContent` no longer changes live
  `order_index` values immediately. It stores the new order only in the working
  revision payload until republish.
- Reading the content before republish still returns the old active payload.
- Publishing the working revision applies it to the logical object and moves the
  active pointer for future learners.
- Publishing a working revision that contains chapter changes applies the
  frozen chapter payload to `LearningChapter` rows only at publish time.
- Existing learning content API create/chapter/publish tests still pass.

## Commands

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_curriculum_learning_content_revisions.py -q --no-cov
```

Red result before implementation:
`AttributeError: 'NoneType' object has no attribute 'payload_json'`.

Green result after implementation: `1 passed, 1 warning`.

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_learning_content_api.py tests/integration/test_curriculum_learning_content_revisions.py -q --no-cov
```

Result after content metadata slice: `8 passed, 1 warning`.

Result after chapter future-revision slice: `9 passed, 1 warning`.

Result after chapter-add future-revision slice: `10 passed, 1 warning`.

Result after chapter-delete/reorder future-revision slice: `12 passed, 1 warning`.

```bash
cd backend && venv/bin/ruff check src/curriculum_practice/services/learning_contents.py src/curriculum_practice/services/learning_chapter_service.py src/curriculum_practice/services/learning_content_publish_gates.py src/curriculum_practice/services/learning_content_serializers.py src/curriculum_practice/services/learning_content_revision_payloads.py src/curriculum_practice/services/learning_content_revision_apply.py src/curriculum_practice/services/learning_content_revision_service.py tests/integration/test_curriculum_learning_content_revisions.py
```

Result: `All checks passed!`.

## File Size Guard

Pure LOC after split:

- `learning_contents.py`: 197
- `learning_chapter_service.py`: 238
- `learning_content_publish_gates.py`: 50
- `learning_content_serializers.py`: 43
- `learning_content_revision_payloads.py`: 190
- `learning_content_chapter_revision_payloads.py`: 87
- `learning_content_revision_apply.py`: 75
- `learning_content_revision_service.py`: 194
- `learning_content_chapter_revision_service.py`: 201

## Residual Scope

This is one curriculum alignment slice only. The full goal remains active:
other `curriculum_practice` assets, full rollback UI/API coverage, regrade,
browser acceptance, and cross-object requirement audit are not yet complete.
