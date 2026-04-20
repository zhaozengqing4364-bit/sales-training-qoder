---
estimated_steps: 3
estimated_files: 6
skills_used:
  - agent-browser
  - safe-grow
  - verification-before-completion
---

# T03: Capture one fresh localhost same-session closure proof on the shipped route family

**Slice:** S04 — 最终集成验证与封板
**Milestone:** M007

## Description

Use the real localhost route family as the final product proof bar. The executor should load `agent-browser`, `safe-grow`, and `verification-before-completion`. This task must prove one real sales session on the shipped learner/runtime/report/replay family and leave behind a compact artifact that distinguishes a genuine completion/replay regression from host-alignment, stale-server, or optional-enhancement noise.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| repo-root backend/web dev servers started with `bg_shell` | stop and fix readiness or host mismatch before attempting browser proof | use `bg_shell wait_for_ready` / bounded browser waits instead of polling loops | verify the active app title/route family before trusting any browser result |
| same-host auth cookie continuity | treat mixed `localhost` / `127.0.0.1` hosts as an environment error, not a product regression | restart the proof on a clean same-host stack | do not reuse a session whose browser/API ownership cannot be confirmed |
| supporting session/report/replay APIs | record the failing route and persisted status in the proof artifact, then decide whether the failure is canonical or optional noise | keep the proof bounded and note the timeout explicitly instead of forcing close-out | reject proof conclusions drawn from mismatched session IDs, stale route state, or incomplete API payloads |

## Load Profile

- **Shared resources**: one backend server, one web dev server, browser session state, and one real sales session.
- **Per-operation cost**: one end-to-end learner/report/replay session plus a small number of supporting API reads.
- **10x breakpoint**: stale dev servers, parallel pytest/background jobs, or repeated browser retries that pollute logs and session state; keep this to one clean proof run.

## Negative Tests

- **Malformed inputs**: stale session IDs, wrong host cookies, or mismatched route family URLs must invalidate the proof.
- **Error paths**: replay still blocked before completion, report readable during `scoring`, and optional enhanced-report noise that should not be misclassified as the canonical blocker.
- **Boundary conditions**: same-session persisted promotion to `completed`, replay unlock on that same session, and clean teardown of every temporary `bg_shell` process.

## Steps

1. Start backend and web from repo root on the same host (`localhost:3444` and `localhost:3445`) with `bg_shell`, create one real sales session, and keep the practice flow on `/practice/{sessionId}` instead of alternate debug routes or mixed hosts.
2. Follow that exact session through `/practice/{sessionId}`, `/practice/{sessionId}/report`, `/practice/{sessionId}/replay`, and the supporting `/api/v1/practice/sessions/{id}` / `/knowledge-check` / replay/highlights APIs so the artifact records the truthful sequence: report readable during `scoring`, persisted promotion to `completed`, then replay unlock on the same session.
3. Save a compact proof artifact with session ID, commands, browser assertions, and any acceptable optional-noise diagnostics, then stop every temporary background process before leaving the task.

## Must-Haves

- [ ] Same-host cookies only (`localhost` ↔ `localhost`).
- [ ] One real same-session path is used with no cross-session stitching.
- [ ] The proof artifact names the persisted-state transition and replay unlock explicitly, and all temporary servers/jobs are stopped before the task ends.

## Verification

- Use `bg_shell` to run `PYTHONPATH=backend/src backend/venv/bin/uvicorn main:app --app-dir backend/src --port 3444` and `pnpm --dir web exec next dev --hostname localhost --port 3445`, wait for readiness, then prove one session through `/practice/{sessionId}` -> `/practice/{sessionId}/report` -> `/practice/{sessionId}/replay` with browser assertions and supporting API checks on the same session.
- After saving `.artifacts/m007-s04-final-closure-proof.md`, stop every temporary `bg_shell` process before finishing.

## Observability Impact

- Signals added/changed: localhost proof records `report_generation_triggered`, `sales_session_finalized`, `report_generation_failed` / `no_scoring_context_available` when present, plus the persisted session status transition.
- How a future agent inspects this: read `.artifacts/m007-s04-final-closure-proof.md`, replay the browser/API steps, and check that no stray dev servers remain.
- Failure state exposed: whether live product truth still wedges at `status="scoring"`, whether replay unlock regressed, or whether the issue is only host/cookie or optional-noise confusion.

## Inputs

- `backend/src/common/api/practice.py` — shipped learner/report/knowledge-check API family
- `backend/src/common/conversation/replay.py` — replay/highlights gate on the shipped family
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — learner route entrypoint
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — report route on the same session family
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — replay route on the same session family
- `.artifacts/m007-s02-same-session/session-proof.md` — prior localhost blocker artifact for comparison
- `.artifacts/m007-s03-authority-audit.md` — generated-state drift audit that close-out must retire
- `.gsd/KNOWLEDGE.md` — durable runtime/browser traps already documented

## Expected Output

- `.artifacts/m007-s04-final-closure-proof.md` — fresh same-session localhost proof with route-family, persisted-state, and browser/API evidence
