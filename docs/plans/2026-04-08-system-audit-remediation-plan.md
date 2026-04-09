# System Audit Remediation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn `SYSTEM_AUDIT_REPORT.md` into a trustworthy execution backlog by separating stale findings from live defects, then fix the highest-value learner UX, frontend hygiene, auth/API contract, and realtime safety issues in a controlled order.

**Architecture:** Work from the existing repo seams rather than inventing new ones: learner routes under `web/src/app/(auth|dashboard|user)`, shared frontend helpers in `web/src/lib/*`, auth/session lifecycle in `backend/src/common/*`, and existing report/replay/history projection surfaces as the acceptance authority. Use discovery slices first for speculative performance/security/ops items.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, FastAPI, SQLAlchemy Async, Alembic, PostgreSQL/SQLite compatibility, Redis, WebSocket, pytest.

## Focused Verification Command Inventory (repo-root runnable)

Use the smallest existing focused command below before inventing a broader regression suite. The intent here is inventory only: later slices can copy one command directly when they touch the matching surface.

| Surface | Focused web command | Focused backend command | Coverage seam locked by the existing tests |
| --- | --- | --- | --- |
| auth | `npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(auth)/forgot-password/login-recovery.test.tsx" "src/app/(auth)/reset-password/login-reset.test.tsx"` | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_password_reset_api.py -x -q` | Login page, forgot/reset UX, cookie auth, secure login failures, password-reset token lifecycle |
| dashboard | `npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx"` | — | Dashboard hero/header CTA truthfulness and learner entry affordances |
| history | `npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx"` | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_history_evidence_flow.py -x -q` | Learner history list/statistics UI and projection-backed history/trend evidence |
| profile | `npm --prefix web test -- --run "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts"` | — | Password-management handoff, profile truthfulness, and persisted voice-speed preferences |
| practice | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"` | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_practice_evidence_flow.py -x -q` | Live practice entry, completed report/replay surfaces, retry focus, and shared evidence projection |
| lifecycle | `npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"` | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q` | Start/pause/resume/end transitions, terminal-state semantics, and REST lifecycle contract |
| websocket | `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/hooks/websocket/message-handlers.test.ts"` | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py backend/tests/integration/test_sales_realtime_reconnect_flow.py -x -q` | Reconnect lifecycle, message/status handling, trace-bearing websocket contract, and persisted reconnect recovery |
| admin | `npm --prefix web test -- --run "src/app/admin/users/page.test.tsx" "src/app/admin/users/[id]/page.test.tsx" "src/app/admin/analytics/page.test.tsx" "src/app/admin/knowledge/[id]/page.test.tsx"` | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/integration/test_admin_knowledge_answer_config_api.py backend/tests/integration/test_support_runtime_api.py -x -q` | Admin user management, supervisor drill-in, analytics/knowledge admin screens, config governance, and support-runtime RBAC |

### Reuse rule for downstream repair slices

- Prefer the repo-root runnable commands above over `cd web && ...` or `cd backend && ...` variants.
- Pick the smallest surface-specific command that still exercises the changed behavior; do not batch unrelated slices into one verification run.
- If a slice needs both learner-web and API proof, pair one web command with one backend command from the same row instead of inventing a new umbrella suite.

---

### Task 1: Normalize the audit before touching code

**Files:**
- Create/Update: `.gsd/analysis/ARCHITECTURE_SCAN_SYSTEM_AUDIT_2026-04-08.md`
- Create/Update: `.gsd/plans/GSD_PLAN_system-audit-repair.md`
- Inspect: `SYSTEM_AUDIT_REPORT.md`, `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/KNOWLEDGE.md`, `.gsd/milestones/M012/*`

**Step 1: Build the disposition matrix**
- Mark every audit item as one of:
  - `already-fixed`
  - `actionable-now`
  - `needs-discovery`
  - `deferred-by-product`
  - `contradicted-by-project-knowledge`

**Step 2: Record proof for stale findings**
- Examples already present in the repo:
  - forgot/reset password pages and backend API exist
  - WeCom button is disabled with “即将支持” copy
  - sidebar already includes 历史记录
  - practice page already supports pause/resume
  - leaderboard already explains score basis

**Step 3: Freeze the acceptance boundaries**
- Keep these explicit:
  - do **not** restore report export by default
  - do **not** mix full mobile support into current launchability work
  - do **not** promise i18n / dark mode / PWA as bugfixes

**Step 4: Save the GSD plan before implementation planning**
- The `.gsd/plans/*` doc is the authority plan.
- This `docs/plans/*` file is the execution handoff.

**Step 5: Commit planning artifacts**
```bash
git add .gsd/analysis/ARCHITECTURE_SCAN_SYSTEM_AUDIT_2026-04-08.md .gsd/plans/GSD_PLAN_system-audit-repair.md docs/plans/2026-04-08-system-audit-remediation-plan.md
git commit -m "docs: plan system audit remediation backlog"
```

---

### Task 2: Close learner launchability gaps without reopening deferred product bets

**Files:**
- Modify: `web/src/app/(dashboard)/page.tsx`
- Modify: `web/src/app/(dashboard)/profile/page.tsx`
- Modify: `web/src/app/(user)/practice/[sessionId]/page.tsx`
- Modify: `web/src/components/layout/sidebar.tsx`
- Test: `web/src/app/(auth)/login/page.test.tsx`
- Test: `web/src/app/(dashboard)/history/page.test.tsx`
- Test: `web/src/app/(user)/practice/[sessionId]/page.test.tsx`

**Step 1: Audit dashboard CTA reality**
Run through every clickable control on the dashboard and classify it as:
- real action
- deep-link to an existing route
- disabled with honest copy
- remove entirely

**Step 2: Add minimum onboarding**
- Keep it lightweight: “选模式 → 选场景 → 开始练习”.
- Reuse existing learner routes; do not create a new subsystem.

**Step 3: Fix profile affordances**
- Replace “修改密码 → 跳 forgot-password” with a deliberate password-management path.
- Either persist voice speed properly or hide it until the backend supports it cleanly.
- Remove or disable any profile “settings” that are still decorative.

**Step 4: Tighten practice entry UX**
- Add preflight expectations inside the existing practice page/shell.
- Clarify pause/resume/end failure copy.
- Gate or hide `/test-mic` from normal learner discovery.

**Step 5: Re-run learner-focused tests**
Run:
```bash
npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/page.test.tsx"
```
Expected: PASS on login/history/practice learner flows.

**Step 6: Commit**
```bash
git add web/src/app/(dashboard)/page.tsx web/src/app/(dashboard)/profile/page.tsx web/src/app/(user)/practice/[sessionId]/page.tsx web/src/components/layout/sidebar.tsx
git commit -m "feat: close learner launchability gaps from audit"
```

---

### Task 3: Remove frontend interaction anti-patterns systematically

**Files:**
- Modify: `web/src/components/ErrorBoundary.tsx`
- Modify: `web/src/lib/debug.ts`
- Modify: `web/src/lib/auth-handler.ts`
- Modify: `web/src/app/admin/records/page.tsx`
- Modify: `web/src/app/admin/rag-profiles/page.tsx`
- Modify: `web/src/app/admin/personas/[id]/page.tsx`
- Modify: `web/src/components/layout/admin-shell.tsx`
- Modify: `web/src/components/layout/dashboard-shell.tsx`
- Test: `web/src/app/admin/personas/[id]/page.test.tsx`
- Test: `web/src/hooks/use-practice-websocket.test.ts`

**Step 1: Replace alert/confirm usage**
- Use shared dialog / toast patterns.
- Preserve destructive confirmations.

**Step 2: Replace direct location navigation**
- Use router/auth-handler pathways instead of `window.location.assign` / `href`.
- Keep `window.location.reload()` only where a full reload is the explicit fallback.

**Step 3: Normalize frontend logging**
- Route business-page logs through shared debug / observability helpers.
- Keep instrumentation-specific logs only where they are intentional and documented.

**Step 4: Clean practice-page recording debug logs**
- Remove raw `console.log` tracing from the practice page.
- Keep durable diagnostic signals through the existing debug seam.

**Step 5: Verify the anti-patterns are gone**
Run:
```bash
rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)|console\.(log|error|warn|info)" web/src
```
Expected: only approved instrumentation/dev-only exceptions remain.

**Step 6: Re-run focused web tests**
Run:
```bash
npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"
```
Expected: PASS after the interaction cleanup.

**Step 7: Commit**
```bash
git add web/src/components/ErrorBoundary.tsx web/src/lib/debug.ts web/src/lib/auth-handler.ts web/src/app/admin/records/page.tsx web/src/app/admin/rag-profiles/page.tsx web/src/app/admin/personas/[id]/page.tsx web/src/components/layout/admin-shell.tsx web/src/components/layout/dashboard-shell.tsx
git commit -m "refactor: remove frontend interaction anti-patterns"
```

---

### Task 4: Formalize password reset and unify the auth/error contract

**Files:**
- Modify: `backend/src/common/auth/api.py`
- Modify: `backend/src/common/auth/service.py`
- Modify: `backend/src/common/db/models.py`
- Create: `backend/alembic/versions/*password_reset*.py`
- Test: `backend/tests/integration/test_auth_login_api.py`
- Test: new/updated password reset focused tests

**Step 1: Write/extend failing tests first**
Cover:
- token creation
- expiry
- one-time use
- invalid token rejection
- password update path
- safe response for unknown emails

**Step 2: Move reset token storage to a real schema seam**
- No request-time `CREATE TABLE IF NOT EXISTS`.
- Use a model + Alembic migration.

**Step 3: Separate transport from policy**
- Introduce an email delivery seam even if local/dev still uses a mock sink.
- Make rate-limit behavior explicit and testable.

**Step 4: Clarify auth modes**
- Shared env password vs per-user hashed password vs reset-password flow must be explainable in code and tests.
- Reduce accidental policy drift.

**Step 5: Re-run backend auth tests**
Run serially:
```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
```
Expected: PASS.

**Step 6: Commit**
```bash
git add backend/src/common/auth/api.py backend/src/common/auth/service.py backend/src/common/db/models.py backend/alembic/versions
git commit -m "feat: formalize password reset auth flow"
```

---

### Task 5: Prove session lifecycle concurrency before patching runtime behavior

**Files:**
- Modify: `backend/src/common/db/session_lifecycle.py`
- Test: `backend/tests/unit/test_session_lifecycle_service.py`
- Test: `backend/tests/integration/test_session_lifecycle_api.py`
- Optional follow-up: `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`

**Step 1: Add race-oriented failing tests**
Target scenarios like:
- pause + end issued close together
- resume + end overlap
- duplicate end requests
- terminal-state re-entry

**Step 2: Pick the smallest safe concurrency strategy**
- row lock if needed
- optimistic versioning if sufficient
- keep sales/presentation terminal-state differences intact

**Step 3: Re-verify API semantics**
- Make sure public behavior still matches the current session status contract.
- Do not regress report/replay unlock semantics.

**Step 4: Run focused backend tests serially**
```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py -x -q
```
Expected: PASS.

**Step 5: Commit**
```bash
git add backend/src/common/db/session_lifecycle.py backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py
git commit -m "fix: harden session lifecycle concurrency behavior"
```

---

### Task 6: Turn speculative audit risks into evidence-backed follow-up work

**Files:**
- Inspect: `backend/src/common/analytics/*`
- Inspect: `backend/src/common/conversation/session_evidence.py`
- Inspect: `backend/src/presentation_coach/api/presentations.py`
- Inspect: `web/src/hooks/use-practice-websocket.ts`
- Create/Update: discovery artifacts under `.gsd/analysis/` or `docs/`

**Step 1: Database performance discovery**
- Look for hot query paths in analytics/history/leaderboard/projection.
- Record candidate N+1 / index / slow-query areas.
- Do not add speculative indexes without proof.

**Step 2: Realtime memory/resource discovery**
- Check websocket queue cleanup, backpressure buffers, event listeners, `useEffect` cleanup paths.
- Convert “maybe leak” into specific findings.

**Step 3: Upload/concurrency discovery**
- Review presentation upload/replace flows for race windows.
- Decide whether active-session blockers already cover the real risk.

**Step 4: Dependency/ops governance baseline**
- Record `npm audit`, Python vulnerability scan, license scan approach, update cadence, and backup/restore runbook gaps.

**Step 5: Save only evidence-backed follow-up slices**
- Each speculative risk becomes either:
  - verified issue → new implementation slice
  - no current evidence → closed/no-op note
  - deferred operations work → runbook/process item

**Step 6: Verify discovery gates**
Run serial backend proof where relevant:
```bash
backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q
```
Expected: PASS while discovery artifacts capture findings.

**Step 7: Commit**
```bash
git add .gsd/analysis docs
git commit -m "docs: capture audit discovery baselines"
```

---

Plan complete and saved to `docs/plans/2026-04-08-system-audit-remediation-plan.md`. Two execution options:

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration
2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
