# sales_trainer — Sales Trainer Backend

Admin + learner REST domain for sales training units, question banks, quiz attempts, audio submissions, scoring, materials, paths, records, and operation logs.

## Local Structure

```
backend/src/sales_trainer/
├── api.py          # Router surface; keep thin
├── models.py       # SQLAlchemy entities
├── schemas.py      # Pydantic request/response DTOs
├── permissions.py  # Role checks and access helpers
├── rules.py        # Stable rule predicates only
├── services/       # Unit, question, quiz, audio, material, prompt, path, record workflows
└── tasks/          # Async scoring/transcription task entrypoints
```

## Where to Look

| Concern | Location |
|---------|----------|
| API contract | `docs/api-contract/sales-trainer.md` |
| System design | `docs/design/sales-trainer-system.md` |
| Router registration | `backend/src/router_registry.py` |
| DB migrations | `backend/alembic/versions/` |
| Unit coverage | `backend/tests/unit/test_sales_trainer_services.py` |
| Contract / integration coverage | `backend/tests/contract/`, `backend/tests/integration/` |

## Responsibility Split

- `api.py` validates transport shape, injects auth/session, calls services, returns schemas.
- `services/*` orchestrate workflows and persistence. Keep model mutation here, not in route handlers.
- `permissions.py` is the local authority for admin/user access checks.
- `rules.py` holds stable predicates. Adjustable business policy belongs in persisted config, templates, or admin-managed records.
- `tasks/*` are process entrypoints; they must call services rather than duplicating scoring/transcription logic.

## Configuration & Admin Rules

- Training units, question categories, scoring prompts, scoring standards, material metadata, paths, and status filters are business-managed data. Do not encode them as magic strings or thresholds in API handlers.
- Defaults must be safe when config records are missing; illegal config should fail with typed, user-actionable errors.
- Any publish, rollback, archive, scoring, material upload, or manual correction path must leave an operation-log/audit trail.
- Permission changes stay centralized in `permissions.py` and router registration; do not scatter role checks across services.

## Hard Rules

- NEVER bypass `services/*` by constructing ORM rows directly in routes or tasks.
- NEVER place scoring dimensions, prompt text, material categories, or status transition policy in page/API ad hoc strings.
- ALWAYS update `docs/api-contract/sales-trainer.md` when request/response/error semantics change.
- ALWAYS add or adjust tests for config hit, missing config, illegal config, and default behavior when a configurable rule changes.
- For audio submission flows, classify ASR/scoring failures as terminal vs transient before adding retry behavior.

## Boundary: NOT a Realtime Runtime

This module is the **Newcomer Training Path** (异步学习 / 录音提交 / 考卷 / 文章 / 路径). It is **NOT** a realtime voice-practice runtime. Concretely:

- MUST NOT `import` from `sales_bot/`, `training_runtime/`, or `practice_sessions/` to create or mutate realtime sessions.
- MUST NOT mount WebSocket endpoints on `/ws/sales/*` or `/ws/presentation/*` from this module.
- Realtime concerns (StepFun handler, VoiceRuntimeProfile, KB Lock evaluation) belong to `sales_bot/`. The only realtime-adjacent thing in this module is `audio_submission_service.py` (上传已录制的音频用于离线评分), which uses ASR/transcription services only.

Examiner voice sessions (different WS contract) live in `curriculum_practice/`. See [`backend/src/curriculum_practice/AGENTS.md`](../curriculum_practice/AGENTS.md).
