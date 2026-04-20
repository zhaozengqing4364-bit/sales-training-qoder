---
id: T03
parent: S03
milestone: M004
provides: []
requires: []
affects: []
key_files: ["backend/src/training_runtime/models.py", "backend/src/training_runtime/service.py", "backend/tests/unit/test_training_runtime_service.py", "web/src/lib/api/types.ts", "web/src/app/(user)/practice/[sessionId]/runtime-lock.ts", "web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts", "web/src/app/(user)/practice/[sessionId]/page.tsx", "web/src/app/(user)/practice/[sessionId]/page.test.tsx", ".gsd/DECISIONS.md", ".codex/loop/state.json", ".codex/loop/log.md"]
key_decisions: ["Project the learner retry focus from persisted `voice_policy_snapshot.focus_intent` onto `runtime_descriptor.focus_intent` so the practice page stays on one typed session-metadata surface.", "Thread carry-forward focus through `usePracticeRuntimeLock`, which already owns `/practice/{sessionId}` metadata sync, instead of adding a second fetch or a retry-specific onboarding surface."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh verification is green. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_training_runtime_service.py` passed 2 backend unit tests covering sales-only runtime descriptor focus projection. The slice T01 backend gate `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` passed 9 tests. The exact slice T02 report/replay CTA gate `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` passed 14 tests. The new practice-page focus suite `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts' 'src/hooks/use-practice-websocket.test.ts'` passed 15 tests, including the new callout and runtime-lock coverage. The exact planned T03 gate `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'` also passed 11 tests. I caught and discarded one locally mistyped replay path before completion so the recorded T02 proof uses the exact `.test.tsx` paths rather than a silently skipped Vitest run."
completed_at: 2026-03-26T00:41:00.759Z
blocker_discovered: false
---

# T03: Surfaced carry-forward retry focus on the learner practice page via the runtime descriptor

> Surfaced carry-forward retry focus on the learner practice page via the runtime descriptor

## What Happened
---
id: T03
parent: S03
milestone: M004
key_files:
  - backend/src/training_runtime/models.py
  - backend/src/training_runtime/service.py
  - backend/tests/unit/test_training_runtime_service.py
  - web/src/lib/api/types.ts
  - web/src/app/(user)/practice/[sessionId]/runtime-lock.ts
  - web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Project the learner retry focus from persisted `voice_policy_snapshot.focus_intent` onto `runtime_descriptor.focus_intent` so the practice page stays on one typed session-metadata surface.
  - Thread carry-forward focus through `usePracticeRuntimeLock`, which already owns `/practice/{sessionId}` metadata sync, instead of adding a second fetch or a retry-specific onboarding surface.
duration: ""
verification_result: passed
completed_at: 2026-03-26T00:41:00.761Z
blocker_discovered: false
---

# T03: Surfaced carry-forward retry focus on the learner practice page via the runtime descriptor

**Surfaced carry-forward retry focus on the learner practice page via the runtime descriptor**

## What Happened

I extended the training runtime descriptor so sales sessions can project the already-persisted `voice_policy_snapshot.focus_intent` as a typed `runtime_descriptor.focus_intent` field, instead of making the learner page parse raw snapshot data itself. On the frontend, I threaded that field through `usePracticeRuntimeLock`, which was the real local seam around `/practice/{sessionId}` metadata, and rendered a compact targeted-retry callout on the practice page that explains this is a focused re-practice and shows the carried-forward main issue plus next-goal guidance. To keep the change tight, I reused the existing session fetch and current practice entry chain; there is no second fetch and no extra onboarding step. I added backend unit coverage for the sales-only runtime descriptor projection, added runtime-lock and practice-page focused tests for the learner-visible callout, kept the planned websocket hook suite green, recorded the runtime-descriptor seam decision in `.gsd/DECISIONS.md`, and updated the safe-grow loop state/log so the next unit can close the slice cleanly.

## Verification

Fresh verification is green. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_training_runtime_service.py` passed 2 backend unit tests covering sales-only runtime descriptor focus projection. The slice T01 backend gate `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` passed 9 tests. The exact slice T02 report/replay CTA gate `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` passed 14 tests. The new practice-page focus suite `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts' 'src/hooks/use-practice-websocket.test.ts'` passed 15 tests, including the new callout and runtime-lock coverage. The exact planned T03 gate `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'` also passed 11 tests. I caught and discarded one locally mistyped replay path before completion so the recorded T02 proof uses the exact `.test.tsx` paths rather than a silently skipped Vitest run.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_training_runtime_service.py` | 0 | ✅ pass | 7455ms |
| 2 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` | 0 | ✅ pass | 8116ms |
| 3 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 1417ms |
| 4 | `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts' 'src/hooks/use-practice-websocket.test.ts'` | 0 | ✅ pass | 1779ms |
| 5 | `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'` | 0 | ✅ pass | 1693ms |


## Deviations

The task plan named `backend/src/training_runtime/service.py`, `web/src/app/(user)/practice/[sessionId]/page.tsx`, and `web/src/hooks/use-practice-websocket.test.ts`, but the real local seam also required `backend/src/training_runtime/models.py`, `web/src/lib/api/types.ts`, `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts`, `web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts`, and a new `web/src/app/(user)/practice/[sessionId]/page.test.tsx` so the typed runtime-descriptor field could reach the page and stay covered.

## Known Issues

None.

## Files Created/Modified

- `backend/src/training_runtime/models.py`
- `backend/src/training_runtime/service.py`
- `backend/tests/unit/test_training_runtime_service.py`
- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts`
- `web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts`
- `web/src/app/(user)/practice/[sessionId]/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`


## Deviations
The task plan named `backend/src/training_runtime/service.py`, `web/src/app/(user)/practice/[sessionId]/page.tsx`, and `web/src/hooks/use-practice-websocket.test.ts`, but the real local seam also required `backend/src/training_runtime/models.py`, `web/src/lib/api/types.ts`, `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts`, `web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts`, and a new `web/src/app/(user)/practice/[sessionId]/page.test.tsx` so the typed runtime-descriptor field could reach the page and stay covered.

## Known Issues
None.
