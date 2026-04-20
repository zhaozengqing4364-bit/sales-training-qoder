# T02 CONTEXT-DRAFT

## Status
- Task **not completed**.
- Workspace was restored to a stable baseline before wrap-up.
- No blocker invalidating the slice plan was discovered.

## What I verified before stopping
- `backend/tests/contract/test_practice_evidence_contract.py -k "voice_policy_snapshot_ref_frozen"` passes again after cleanup.
- `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx"` passes again after cleanup.

## What I investigated
- T01 already exposes read-only contract endpoints:
  - `GET /api/v1/admin/agents/industry-pack-contract`
  - `GET /api/v1/admin/personas/industry-pack-contract`
  - `GET /api/v1/scenarios/sales/runtime-contract`
- Runtime already freezes `persona_policy`, `customer_pressure`, `knowledge_base_ids`, and `source.customer_pressure_source` into `practice_sessions.voice_policy_snapshot`, but `voice_policy_snapshot_ref` still does **not** project a compact industry-pack summary.
- Admin pages currently do **not** consume the T01 contract endpoints.

## Attempted path (reverted to keep repo stable)
I started a fail-first path to:
1. extend `voice_policy_snapshot_ref` with an `industry_pack_summary`, and
2. make admin persona / agent pages render contract details from the T01 endpoints.

Because the context-budget wrap-up arrived mid-edit, I reverted the incomplete test and file changes so the repo would not be left in a broken state.

## Recommended resume plan
1. **Backend first (fail-first again):**
   - Add a focused unit/contract test asserting `voice_policy_snapshot_ref` includes a compact industry-pack summary derived from the frozen snapshot.
   - Best seams:
     - `backend/src/common/db/voice_policy_snapshot.py`
     - `backend/src/common/db/schemas.py`
     - optionally `backend/src/common/conversation/schemas.py` for replay schema parity
   - Suggested summary shape:
     - `industry_pack_strategy`
     - `customer_pressure_source`
     - `sales_focus`
     - `value_axes`
     - `objection_axes`
     - `expected_customer_questions`
     - `knowledge_base_ids`
     - `runtime_impacts`
   - Likely reusable source helper: `backend/src/agent/services/industry_pack_contract.py`

2. **Admin UI second:**
   - Add client types + methods for the two existing contract endpoints in `web/src/lib/api/types.ts` and `web/src/lib/api/client.ts`.
   - Wire `web/src/app/admin/personas/[id]/page.tsx` to show the persona contract/runtime-target mapping.
   - Wire `web/src/app/admin/agents/[id]/page.tsx` to show the composed-entrypoint contract and runtime authorities.
   - Keep the pages read-only; do **not** create a second pack-management platform.

3. **Verification after implementation:**
   - Required task-plan bundle:
     - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q`
     - `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx"`
   - Also run a focused agent-page test if you add one.

## Important cleanup note
- I removed the temporary file `web/src/app/admin/agents/[id]/page.test.tsx` because it was only part of the abandoned in-progress attempt.
- `web/src/app/admin/personas/[id]/page.test.tsx` was restored to its original passing state.
- `backend/tests/contract/test_practice_evidence_contract.py` was restored to its original passing state after a mid-edit duplication issue.
