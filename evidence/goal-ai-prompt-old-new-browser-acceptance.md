# Goal Slice Evidence: AI Prompt Old/New Isolation

Timestamp: 2026-06-04T05:24:00Z

Scope:

- Verified that historical audio scoring keeps the original prompt hash.
- Verified that the high-risk regrade preview resolves the active target prompt revision and produces a different prompt hash.
- Verified that the preview remains append-only and does not overwrite the original score.

QA object:

- Audio submission: `49ec020b-b761-4580-86b8-28e5afac69c7`
- Source score result: `df61c91c-527e-46ef-b50e-5239715eda77`
- Prompt logical id: `a764b195-5914-4c24-8d6b-b14cd91a6c81`
- Target prompt revision: `441ad3a6-d879-4ffd-a3f2-b2c2ae2b8c25`

Browser evidence:

- `evidence/goal-ai-prompt-old-new-regrade-preview.png`
- `evidence/goal-ai-prompt-old-new-browser.json`

Visible browser text proves:

- Original score card still shows `88`.
- Original prompt hash remains visible as `source-promp`.
- Regrade preview uses a new prompt hash prefix `7512e5927795`.
- The panel says `只追加结果，不覆盖原始评分`.

Network evidence:

- `evidence/goal-ai-prompt-old-new-preview.network-response`

Important response fields:

```json
{
  "target_revision_id": "441ad3a6-d879-4ffd-a3f2-b2c2ae2b8c25",
  "before_prompt_version": 1,
  "before_prompt_hash": "source-prompt-hash",
  "after_prompt_version": 2,
  "after_prompt_hash": "7512e592779508555397d6dd4c47595eaf176d9d4f957f4c0d00e9a975cbe0f5",
  "history_overwrite": false,
  "future_records_changed": false
}
```

Validation commands:

```bash
cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_score_prompt_api.py tests/integration/test_newcomer_training_path_audio_regrade_api.py tests/unit/test_newcomer_training_path_score_prompts.py tests/unit/test_newcomer_training_path_audio_lineage.py -q --no-cov
cd web && npx vitest run 'src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.test.tsx' src/lib/api/client-domains.test.ts src/lib/api/sales-trainer.test.ts --pool=threads --maxWorkers=1
cd web && npx tsc --noEmit
```

Results:

- Backend focused tests: 5 passed, 1 ChromaDB deprecation warning.
- Frontend focused tests: 3 files / 21 tests passed.
- Web typecheck: passed.

Important caveat:

- The live regrade preview reached the current AI scoring service and returned `[DEUCATE_RESPONSE_INVALID]`; therefore this slice proves the new prompt revision/hash was used, not that the external model produced a valid score in this browser run.
- The separate append-only audio regrade browser evidence still proves a completed regrade run does not overwrite the original score.

Remaining goal scope:

- Broader operation-log rollup for publish, rollback, binding changes, and regrade remains open.
- Final full quality gate and completion audit remain open.
