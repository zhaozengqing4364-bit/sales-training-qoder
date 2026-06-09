# Goal Slice Evidence: Score Prompt Natural Edit

Timestamp: 2026-06-03T17:04:48Z

Scope:

- Admin score standard form now treats published prompts as editable future-only revisions.
- Admin score standard list no longer exposes copy-draft as the normal published edit path.
- Admin score standard create/edit copy explains that saves create a pending revision and only affect future learners/scores.
- Backend API integration covers updating a published score prompt through `PUT /api/v1/admin/sales-trainer/audio-score-prompts/{prompt_id}`.

Commands:

```bash
cd web && npx vitest run src/components/admin/sales-trainer/score-prompt-form.test.tsx --pool=threads --maxWorkers=1
cd web && npx vitest run src/components/admin/sales-trainer/score-prompt-form.test.tsx src/app/admin/sales-trainer/score-standards/page.test.tsx --pool=threads --maxWorkers=1
cd web && npx tsc --noEmit
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_score_prompts.py tests/integration/test_newcomer_training_path_score_prompt_api.py -q --no-cov
```

Results:

- Score prompt form focused Vitest: 2 passed.
- Score standards page + form focused Vitest: 3 passed.
- Web typecheck: passed.
- Backend score prompt unit + integration pytest: 2 passed, 1 existing ChromaDB deprecation warning.

Regression locked:

- Published score prompt editing shows `编辑将生成新修订`.
- Published score prompt submit calls `onSubmit` instead of copy-draft.
- Score standards list shows `编辑` and no `复制草稿` action for published rows.
- Published score prompt API update returns 200, leaves active payload/version unchanged, and stores the new payload in a `working` `sales_trainer_audio_score_prompt` revision with `change_class=scoring_high_risk`.

Remaining goal scope:

- Unit/question/paper draft-only locks and copy-draft UI text still remain.
- Full rollback, history drawer, explicit regrade, curriculum_practice parity, and full browser acceptance remain incomplete.
