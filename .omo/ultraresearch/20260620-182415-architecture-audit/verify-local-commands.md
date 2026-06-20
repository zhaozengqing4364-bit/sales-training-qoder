# Local Verification Artifacts

## Repository scale

- Excluding common generated/dependency directories, `rg --files` found 2381 files.
- Top source/doc buckets: `backend` 1133, `web` 655, `evidence` 322, `docs` 84, `scripts` 24.
- Code line scan across Python/TS/TSX reported 485764 total lines.

## Large-file hotspots

- `web/src/lib/api/types.ts`: 6915 lines.
- `backend/tests/unit/test_stepfun_realtime_handler.py`: 5043 lines.
- `web/src/lib/api/client.ts`: 4721 lines.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`: 3350 lines.
- `backend/scripts/seed_presales_cio_first_visit.py`: 3136 lines.
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`: 2755 lines.
- `backend/src/sales_trainer/schemas.py`: 2716 lines.
- `backend/src/common/db/models.py`: 2661 lines.
- `backend/src/curriculum_practice/api.py`: 2551 lines.

## Cross-domain imports

Python AST scan found notable non-`common` edges:
- `sales_trainer -> curriculum_practice`: 11 imports across 9 files.
- `curriculum_practice -> sales_trainer`: 4 imports across 2 files.
- `sales_trainer -> prompt_templates`: 10 imports across 6 files.
- `evaluation -> prompt_templates`: 5 imports across 5 files.
- `evaluation -> admin/curriculum_practice/presentation_coach/sales_bot`: multiple direct edges.
- `sales_bot -> agent`: 37 imports across 10 files.

## Change pressure

Last-30-days churn hotspots include:
- `backend/scripts/seed_presales_cio_first_visit.py`: 3136 added lines.
- `web/src/lib/api/client-domains.ts`: 2786 churn.
- `backend/src/sales_trainer/schemas.py`: 2771 churn.
- `docs/api-contract/sales-trainer.md`: 2709 churn.
- `web/src/lib/api/types.ts`: 2648 churn.
- `backend/src/curriculum_practice/services/roleplay_contracts.py`: 2006 churn.

## Migration and tests

- Alembic versions: 89 files; current head: `20260616_086`.
- Tests discovered: 560 test files.
- Backend pytest config enforces `--cov-fail-under=48`.
- Dirty worktree at sampling time: 84 tracked modified files, 35 untracked files.

## Dependency entrypoints

Detected multiple lock/config authorities:
- root: `package-lock.json`, `package.json`, `pyproject.toml`, `uv.lock`
- backend: `pyproject.toml`, `requirements.txt`, `uv.lock`
- web: `package-lock.json`, `pnpm-lock.yaml`
- `.opencode/package-lock.json`
