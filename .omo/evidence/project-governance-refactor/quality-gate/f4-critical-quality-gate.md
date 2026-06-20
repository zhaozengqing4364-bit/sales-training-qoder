# F4 Critical Quality Gate

Date: 2026-06-20

## Command

- `bash scripts/critical-quality-gate.sh`

## Result

Failed.

The gate started the local smoke stack, completed the early checks, and stopped the stack on failure.

Passed phases:

- Secret hygiene scan: passed, `93 files scanned`.
- Smoke stack bootstrap: passed.
- Alembic upgrade during smoke bootstrap: passed.
- Web typecheck: passed.
- Vitest with coverage: passed, `16 passed (16)`, `161 passed (161)`.
- Playwright smoke E2E partial result: `7 passed`, `2 failed`.

Failed phase:

- Playwright smoke E2E.

Failed tests:

- `tests/e2e/smoke.spec.ts:352` - `practice session smoke`
  - Failure: `page.goto` timed out after `30000ms`.
  - Important observation: the Playwright page snapshot shows the practice page reached the connected state with visible `已连接`, `进行中`, and `销售对练`, so the app route rendered but the navigation did not reach the default `load` wait condition.
  - Evidence:
    - `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-practice-session-smoke-chromium/error-context.md`
    - `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-practice-session-smoke-chromium/trace.zip`
    - `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-practice-session-smoke-chromium/test-failed-1.png`

- `tests/e2e/smoke.spec.ts:432` - `support runtime smoke`
  - Failure: after login, `page` remained at `http://localhost:3445/login`; expected `/`.
  - Backend log observation: the matching login request was accepted and logged as `User logged in`, so the failure is on the frontend route/session/navigation side rather than an auth API rejection.
  - Evidence:
    - `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-support-runtime-smoke-chromium/error-context.md`
    - `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-support-runtime-smoke-chromium/trace.zip`
    - `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-support-runtime-smoke-chromium/test-failed-1.png`

## Root-Cause Classification

Classified as a quality-gate infrastructure/runtime red light, not a proven Task 1-24 functional regression.

Observed evidence:

- Backend logs show practice session creation, WebSocket acceptance, StepFun realtime handler selection, and lifecycle transitions for the failed practice session.
- Backend logs do not show a corresponding `500`, traceback, permission denial, or auth rejection for these two failures.
- Frontend logs show repeated Turbopack HMR/internal errors and a fatal Turbopack panic:
  - `Resource path "src/app/(dashboard)/page.tsx" needs to be on project filesystem "web"`.
  - `Module ... client-segment.js ... was instantiated ... but the module factory is not available`.
  - A Next panic file was reported under `/var/folders/.../next-panic-4eea2f090c9978ce27b0eb0946a8b5e5.log`.
- `web/tests/e2e/smoke.spec.ts` has an unrelated pre-existing working-tree diff. This verification wave did not modify or stage that file.

## Release Decision

Do not claim release readiness.

The release candidate gate is executed and red. The next owner should either:

- stabilize the smoke frontend server by running the gate against a non-Turbopack dev server or production build, then rerun `bash scripts/critical-quality-gate.sh`; or
- explicitly accept this as an external environment/toolchain failure with separate release approval.
