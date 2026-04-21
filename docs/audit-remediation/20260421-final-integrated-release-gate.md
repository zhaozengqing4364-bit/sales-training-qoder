# 2026-04-21 Final Integrated Release Gate

- Team: `read-omx-context-full-audit-de`
- Worker: `worker-6`
- Task: `11` / Final integrated release gate after all lanes complete
- Gate timestamp: 2026-04-21 15:10 CST / 07:10 UTC
- Checked HEAD: `38a3f79b46d8abe9165b7c1f1a2a3e009df6e542`
- Gate verdict: **FAIL**

## 1. Scope and state

All original lane tasks were terminal when this gate started:

- Completed: tasks `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`.
- Final verification task `11` was already claimed by `worker-6`.
- No Docker/deploy/ops source changes were allowed or made by this final gate.

The final gate was read-only except for this documentation report and the tracker status vocabulary correction described below.

## 2. Tracker status vocabulary correction

The integrated tracker had drifted back to disallowed `pending` values for all 58 Q/UX/G rows. Task 6 requires the tracker to use only:

- `implemented`
- `verified-not-present`
- `deferred-with-adr`
- `blocked-by-product-decision`
- `failed`

Final gate corrected the status column conservatively:

- `54` rows: `deferred-with-adr`
- `4` rows: `blocked-by-product-decision` (`Q-20`, `Q-27`, `G-08`, `G-10`)
- `0` rows: `pending`

No rows were promoted to `implemented` because the integrated gate is red.

## 3. Command evidence

| Check | Command | Result | Classification |
| --- | --- | --- | --- |
| HEAD | `git rev-parse HEAD` | PASS: `38a3f79b46d8abe9165b7c1f1a2a3e009df6e542` | Baseline fact |
| Clean worktree at gate start | `git status --short --branch` | PASS: `## HEAD (no branch)` | Baseline fact |
| Whitespace | `git diff --check` | PASS | Gate pass |
| Tracker sanity before correction | Python Q/UX/G assertion | FAIL: 58 `pending` statuses | Introduced integration/docs drift; corrected by final gate |
| Disallowed Docker/deploy/ops scan | `git diff --name-only HEAD~30..HEAD` with ops/deploy patterns | PASS: no matching paths | Gate pass |
| Web typecheck | `pnpm --dir web exec tsc --noEmit --pretty false` | FAIL | Current integration blocker |
| Web targeted lint | `pnpm --dir web exec eslint ... --quiet` | FAIL | Current integration blocker; partly historical React Compiler debt, partly active source issues |
| Web targeted tests | `pnpm --dir web exec vitest run ... --reporter=dot` | FAIL: 10/12 files passed, 147/172 tests passed, 25 failed | Current integration blocker |
| Backend targeted regression subset | `pytest` selected auth/history/session/StepFun/audio/presentation tests | FAIL: 23/34 passed, 11 failed | Mostly pre-existing to final task; still release blocking |
| Backend focused Lane A/B subset | `pytest` selected capability/presentation/ws/knowledge/policy tests | FAIL: 119/120 passed, 1 failed | Current integration blocker in capability fallback contract |
| Backend ruff | `cd backend && ruff check src tests --quiet` | FAIL | Current source lint errors plus historical test lint debt |
| Whitespace after docs/tracker correction | `git diff --check` | PASS | Gate pass |
| Tracker sanity after correction | Python Q/UX/G assertion | PASS: 58 rows, all IDs present, statuses allowed | Gate pass after docs-only correction |

## 4. Final web blockers

### 4.1 TypeScript blockers

`pnpm --dir web exec tsc --noEmit --pretty false` failed with unresolved identifiers in `web/src/app/(user)/practice/[sessionId]/page.tsx`:

- `setPresentationProgress` at lines 494, 505, 514, 1125.
- `presentationProgress` at lines 1106, 1112, 1123, 1128.

Classification: **current integration blocker**, likely from the final merge of PPT progress / live practice surfaces. This is not a historical baseline failure because earlier Lane C/Lane E task-local checks reported web typecheck pass before final integration.

### 4.2 ESLint / React Compiler blockers

Targeted lint failed with 18 errors including:

- `react-hooks/set-state-in-effect` in:
  - `web/src/app/(auth)/login/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts`
- `react-hooks/refs` in `web/src/hooks/use-practice-websocket.ts` for ref writes during render.
- `react-hooks/immutability` in `web/src/hooks/use-practice-websocket.ts` because `connect` is referenced before declaration in a callback path.

Classification: mixed.

- Some set-state-in-effect issues existed during earlier gate refreshes.
- The current `use-practice-websocket.ts` and final practice-page positions are active integration blockers and must be resolved or explicitly accepted as a scoped lint baseline before release.

### 4.3 Targeted Vitest blockers

Targeted Vitest failed with 25 test failures:

- `src/hooks/websocket/message-handlers.test.ts` has 2 failures because `addAiMessageIfNew` now receives a third dedupe key argument while tests expect two arguments.
- `src/app/(user)/practice/[sessionId]/page.test.tsx` has 23 failures caused by `ReferenceError: presentationProgress is not defined` during page render.

Classification: current integration blocker. The page runtime error is aligned with the TypeScript failures above.

## 5. Final backend blockers

### 5.1 Targeted regression subset: 11 failures

The selected backend regression subset still fails on:

- WebSocket auth precedence: implementation returns cookie token when the test expects query token if `Authorization` is empty.
- History statistics contract: payload includes extra `score_basis` compared with test expectation.
- Session manager stats contract: tracked-session runtime shape is expanded compared with test expectation.
- StepFun reconnect snapshots include extra `reconnect_state` compared with persistence tests.
- Audio segment registration re-registers `(session, sequence)` as `422` instead of idempotent `200`.
- Presentation upload/replace contract tests hit role-guard mismatches.
- Presentation admin role-guard message includes `[ADMIN_REQUIRED]` where the test expects plain Chinese message.

Classification: these 11 failures were already present in earlier Lane F refreshes before task 11, so they are **pre-existing to the final gate task**. They remain release blockers unless the team accepts a baseline or updates contracts/tests intentionally.

### 5.2 Focused Lane A/B subset: 1 failure

`tests/unit/test_capability_base.py::TestCapabilityRunner::test_run_one_converts_os_errors` fails because the implementation returns:

- actual: `[CAPABILITY_IO_ERROR]`
- expected: `[CAPABILITY_ERROR]`

Classification: current integration contract mismatch. Either update the test contract if the more specific fallback is intended, or restore the expected fallback.

### 5.3 Backend ruff blockers

`ruff check src tests --quiet` fails with source and test lint errors. Source-level examples include:

- duplicate `calculate_pcm_duration_ms` imports/definition in sales TTS paths.
- `settings` undefined in `sales_bot/websocket/components/tts_component.py`.

Historical test lint debt also remains, including import ordering, unused imports, whitespace, `datetime.UTC` upgrade warnings, and `TimeoutError` alias cleanup.

Classification: source-level ruff errors are current release blockers; broad test lint debt is historical but still blocks the configured command.

## 6. Historical vs introduced summary

| Category | Status |
| --- | --- |
| Historical/pre-existing to final task | Backend 11-test regression subset; broad backend test ruff debt; some React Compiler set-state-in-effect issues previously observed |
| Introduced/current integration blockers | Practice page `presentationProgress` undefined TypeScript/runtime failures; websocket message-handler test signature mismatch; capability fallback contract mismatch; sales TTS ruff source errors |
| Docs-only correction by final gate | Tracker status vocabulary repaired from disallowed `pending` to allowed statuses |
| Clean/acceptable | No Docker/deploy/ops path changes detected; `git diff --check` passed |

## 7. Final decision

**FAIL: do not release / do not mark the integrated audit-remediation work as verified.**

Required before re-running final gate:

1. Fix `presentationProgress` / `setPresentationProgress` integration in the practice page.
2. Resolve or intentionally update `message-handlers.test.ts` for the third `addAiMessageIfNew` dedupe-key argument.
3. Resolve targeted React Compiler lint failures or create an accepted scoped lint baseline.
4. Resolve backend source ruff errors in TTS duration paths.
5. Resolve or explicitly baseline the 11 backend regression failures.
6. Resolve the capability fallback contract mismatch.
7. Keep the tracker status vocabulary within the allowed set.
