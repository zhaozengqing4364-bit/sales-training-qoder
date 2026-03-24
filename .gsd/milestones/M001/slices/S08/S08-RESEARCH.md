# S08: 桌面端发布验收与可观测性收口 — Research

**Date:** 2026-03-23

## Requirement Focus

S08 is not introducing a new user capability from scratch; it is the release-closure slice that must re-prove and operationalize already validated milestone outcomes. The slice directly supports the already-validated launch-critical requirements that list `M001/S08` as a supporting slice or are explicitly called out by the roadmap handoff:

- **R001 / R002** — desktop sales runtime must stay recoverable and diagnosable under reconnect / timeout / end-failure conditions.
- **R005** — the learner report must remain the canonical trustworthy read surface even when optional enhancement layers fail.
- **Integrated release proof of R003 / R007 / R008** — S08 must prove that the sales value baseline, supervisor trend view, and PPT postmortem still hold together as one desktop release story.
- **R011 (supporting, not owning)** — any new observability/readiness surface should reuse the same session evidence line instead of inventing a second truth source.

## Summary

This slice is best treated as **targeted final assembly work**, not a new feature area. The core routes already exist and have slice-level proof: the sales practice page (`/practice/[sessionId]`), the canonical shared report page (`/practice/[sessionId]/report`), the supervisor detail page (`/admin/users/[id]`), and the read-only support runtime page (`/support/runtime`). The planner should keep the scope tight and use the existing canonical surfaces rather than creating a new release console.

The main code gap is **observability truth**, not page count. The shipped support/runtime surface currently reads only coarse `PracticeSession` status counts plus `SystemLog` rows. That is not enough for M001 launch closure. It currently counts `status="scoring"` as a completed session, which can hide stuck terminal flows, and most M001-critical anomalies (projection failures, sales knowledge/search failures, upstream StepFun instability, PPT `missing_page_metadata`, non-evaluable completed sessions) do **not** currently become `SystemLog` rows. The result is a support page that can look healthy while the actual milestone-critical paths are degraded.

The safest recommendation is: **extend `/support/runtime` into an evidence-backed release-health read model sourced from persisted session data and the canonical session evidence projection, then use that surface plus existing pages/UAT recipes to run the release proof.** Do **not** make the generic `release_verification` subsystem or the placeholder `runtime_metrics_service` the primary source of truth for this slice.

## Recommendation

Use the existing support-runtime page as the S08 observability home, but change its data source and semantics before doing milestone UAT.

Recommended approach:

1. **Backend first:** add a small support/runtime service that queries recent sessions, batch-loads messages, and classifies release-relevant anomalies from authoritative persisted data.
   - Reuse `SessionEvidenceService.build_projection(...)` and the batch-loading pattern already proven in `HistoryService`.
   - Stop treating `status="scoring"` as a successful completion. Break it out explicitly, ideally with a “stuck scoring” threshold.
   - Derive support-facing warning/blocking items from session evidence and `voice_policy_snapshot.runtime_metrics`, not from stdout-only logs.

2. **Frontend second:** expand `/support/runtime` to show a release-health summary and a typed anomaly list for support/admin users.
   - Keep the page read-only. `practice._can_read_session(...)` is admin-or-owner only, so support users should see identifiers and summaries, not report deep links that bypass RBAC.
   - The page should distinguish **blocking** vs **warning** signals and should make it obvious which anomalies are core product regressions vs optional enhancement noise.

3. **Release proof last:** once the support/runtime surface is trustworthy, run a browser-first release audit in waves, reusing the existing S01/S06/S07 UAT recipes.
   - This follows the `frontend-audit` skill rule: map the real surface first, then audit it in browser waves; do not reduce launch proof to one happy path or start from Playwright-style automation.
   - This also follows `verification-before-completion`: no launch-ready claim without fresh backend + frontend + live runtime evidence in this slice.

### Approach comparison

**A. Extend `/support/runtime` with evidence-backed release health** — **Recommended**
- Smallest safe change.
- Reuses already-authoritative session/report/projection data.
- Gives S08 an in-product observability surface that matches M001 semantics.

**B. Reuse `/admin/release-verification` as the primary release surface** — Not recommended as the first move
- Existing FR40 machinery is real, but generic.
- `verification_runner.py` runs backend checks only; it does not cover Vitest, browser UAT, localhost host-alignment pitfalls, or the audio/page-turn proof needed by M001.
- Good optional follow-up for durable RC recording, not the truth source for this slice.

**C. Ship only docs/UAT with no code changes** — Not recommended
- Current support/runtime data is too weak and can report false green states.
- S08 would lack an operational surface for the very failures it is supposed to make diagnosable.

## Implementation Landscape

### Key Files

- `backend/src/support/api/runtime_status.py` — current `/support/runtime/overview` and `/support/runtime/faults` endpoints. Today it only counts broad session statuses and `SystemLog` rows. It also counts `status="scoring"` as completed, which can hide stuck terminal/report paths.
- `web/src/app/(dashboard)/support/runtime/page.tsx` — current support/admin runtime page. Right now it renders three coarse cards and a raw fault list; no M001 release-health semantics, no blocking/warning split, and no test coverage.
- `web/src/lib/api/types.ts` — support runtime response types already exist here; expand them together with the backend contract.
- `web/src/lib/api/client.ts` — `api.supportRuntime.getOverview/getFaults` already exist; keep using this client path instead of adding a second frontend fetch surface.
- `backend/src/common/conversation/session_evidence.py` — authoritative projection builder for `evaluable`, `not_evaluable_reason`, `overall_result`, and presentation degraded reasons. This is the right classifier for S08 anomaly summaries.
- `backend/src/common/analytics/history_service.py` — already solves the hard part of batch-loading `ConversationMessage` rows and projecting many sessions efficiently. Copy its `build_history_entries(...)` / `_load_messages_by_session(...)` pattern rather than re-querying one session at a time.
- `backend/src/common/api/practice.py` — current canonical report route and the only place that fully parses sales `voice_policy_snapshot.runtime_metrics` into meaningful `knowledge-check` / `kb_lock_status` / `upstream_disconnect_count_5m` semantics. If S08 needs the same classifications, extract a shared helper from here rather than duplicating the parsing logic.
- `backend/src/presentation_coach/services/presentation_report_service.py` — authoritative source for PPT degraded semantics such as `missing_page_metadata`; support/runtime aggregation should reuse these meanings.
- `backend/tests/contract/test_support_runtime.py` — current support-runtime contract guardrail. Extend it once the new overview/fault shapes are defined.
- `backend/tests/integration/test_support_runtime_api.py` — current support-runtime integration guardrail. Best place to lock `scoring` handling, projection-based anomaly classification, and severity filtering.
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — learner runtime page with reconnect / retry-end diagnostics from S01; still a core S08 release-proof surface.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — canonical report page for both sales and presentation; already distinguishes optional enhanced-report/highlights failures from the core evidence path.
- `web/src/app/admin/users/[id]/page.tsx` — supervisor trend page from S06; needed for milestone-wide release proof.
- `.gsd/milestones/M001/slices/S01/S01-UAT.md` — reusable live sales reconnect / terminal-failure recipe.
- `.gsd/milestones/M001/slices/S06/S06-UAT.md` — reusable supervisor `/admin/users/{id}` proof recipe.
- `.gsd/milestones/M001/slices/S07/S07-UAT.md` — reusable localhost-aligned presentation report/runtime recipe.
- `backend/src/common/analytics/release_verification_service.py` / `backend/src/common/analytics/verification_runner.py` / `backend/src/admin/api/release_verification.py` / `docs/api-contract/release-verification.md` — existing generic release-candidate subsystem. Useful if S08 later wants durable recording of the final checks, but not sufficient as the primary S08 truth source.
- `backend/src/common/analytics/runtime_metrics_service.py` — contains placeholder values (`99.5`, `0.3`, `185.0`) for several reliability/performance fields. Do **not** use this service as launch evidence.

### Natural seams

1. **Support-runtime backend truth seam**
   - Add a service layer such as `backend/src/support/services/runtime_status_service.py` or similar.
   - Keep `runtime_status.py` thin.
   - Reuse `HistoryService` batching + `SessionEvidenceService` projection instead of hand-rolled SQL-only summaries.

2. **Knowledge/runtime diagnostic parsing seam**
   - The `knowledge-check` status classification currently lives inline in `common/api/practice.py`.
   - If S08 wants support/runtime to talk about `search_failed`, `kb_not_ready`, `kb_lock_status`, or `upstream_unstable` using the same semantics as the learner report, extract a shared helper first.

3. **Support-runtime frontend seam**
   - `web/src/app/(dashboard)/support/runtime/page.tsx` can be upgraded in place.
   - Add a focused `page.test.tsx` here; none exists today.
   - Keep read-only RBAC intact. No support-only deep links into owner/admin-only report routes.

4. **Release-proof artifacts seam**
   - S08 should reuse and compose the existing slice UAT docs instead of inventing brand-new manual recipes.
   - The likely new durable artifacts are `.gsd/milestones/M001/slices/S08/S08-UAT.md` and an S08 summary/assessment, not a large new product module.

### Build Order

1. **Fix the support-runtime truth model before touching the page.**
   - First decision: what persisted data actually proves a blocking vs warning anomaly?
   - Minimum high-value set the codebase can already support:
     - `stuck_scoring` or separate `scoring_sessions` count (do not count `scoring` as completed)
     - `projection_failed` for recent completed sessions whose `SessionEvidenceService` projection cannot be built
     - `not_evaluable_completed` using `projection.evaluable == false`
     - `presentation_degraded_missing_page_metadata`
     - `knowledge_search_failed` / `kb_not_ready` / `kb_lock_blocked_*`
     - `upstream_unstable` or recent `upstream_disconnect_count_5m > 0` from `voice_policy_snapshot.runtime_metrics`
     - `optional_report_failed` from `PracticeSession.report_status == "failed"` (warning, not blocking)
   - This backend contract unblocks everything else.

2. **Then wire the support/runtime UI.**
   - Render a release-health summary that clearly separates blocking vs warning counts.
   - Show typed fault items with scenario/session identifiers and concise summaries.
   - Keep the current page shell and refresh flow.

3. **Then lock it with tests.**
   - Backend contract + integration tests for new overview/fault fields and severity rules.
   - New web page test covering success, warning-heavy, blocking-heavy, and load-failure states.

4. **Only after the support page is trustworthy, do the slice-close release proof.**
   - Reuse the canonical product surfaces in browser/runtime waves:
     1. sales practice reconnect / retry-end failure visibility
     2. sales report with optional enhancement degradation isolated from canonical evidence
     3. supervisor trend page
     4. PPT postmortem happy + degraded paths
     5. support/runtime page showing the resulting anomalies/health counters

## Verification Strategy

This slice should verify in three layers.

### 1. Backend/API regression

Use the already-proven slice suites plus new support-runtime coverage:

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/integration/test_session_lifecycle_api.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py tests/integration/test_admin_users_api.py tests/contract/test_presentation_report_contract.py tests/integration/test_presentation_report_flow.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_support_runtime.py tests/integration/test_support_runtime_api.py`
- If a dedicated backend service is added, give it a focused unit file (for example `tests/unit/test_support_runtime_service.py`) and run it separately.

### 2. Frontend regression

- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/hooks/websocket/message-handlers.test.ts'`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx' 'src/app/(dashboard)/support/runtime/page.test.tsx'`

### 3. Live/browser release waves

Follow the `frontend-audit` pattern: route map first, then wave-by-wave browser proof.

Preflight constraints already proven by earlier slices and still relevant here:

- Run `cd backend && venv/bin/alembic upgrade head` before judging admin/projection-backed surfaces.
- Keep frontend and backend on the same loopback host (`localhost` + `localhost`), not mixed with `127.0.0.1`.
- For S05-style local sales websocket proof, if StepFun loops with `1006` and backend logs mention SOCKS proxy support, install `python-socks` before assuming a regression.
- For S07-style PPT proof, do **not** use the websocket `type:"text"` shortcut; use real audio chunks + `page_change`.

Recommended live wave order:

1. **Sales runtime** — reuse S01 reconnect/end-failure UAT.
2. **Canonical sales report** — reuse S03/S05 report behavior and confirm optional enhanced/highlights failures stay warning-only.
3. **Supervisor trend page** — reuse S06 `/admin/users/{id}` UAT.
4. **PPT postmortem** — reuse S07 happy/degraded report UAT.
5. **Support/runtime** — confirm the page/API surfaces the above issues with correct blocking/warning semantics instead of false-green counts.

## Constraints and Non-Recommendations

- Do **not** make `/admin/release-verification` the first-class S08 product surface. It is generic, admin-only, and its runner covers backend checks only.
- Do **not** use `RuntimeMetricsService` as release evidence. Several of its key reliability/performance values are placeholders.
- Do **not** expand RBAC to let support users read learner reports just for S08. Keep support/runtime read-only and diagnostic.
- Do **not** solve S08 by adding more unrelated pages. This slice should follow `safe-grow`: one issue, smallest safe change, immediate verification.

## Skill Discovery

Relevant installed skills already available in this repo/session:

- `frontend-audit` — best fit for the browser-first release proof.
- `agent-browser` — useful if the executor wants CLI browser automation.
- `best-practices` / `verification-before-completion` — directly relevant to release gating.
- `react-best-practices` / `vercel-react-best-practices` — optional help for the support runtime page changes.

Promising non-installed backend-stack skills discovered during research (do **not** install automatically):

- `npx skills add wshobson/agents@fastapi-templates` — highest-install FastAPI result (8.8K installs); useful only if the executor wants extra FastAPI structure guidance.
- `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` — most directly relevant SQLAlchemy/Alembic review skill for the projection/support-runtime backend work.
- `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` — lighter-weight SQLAlchemy ORM option.

For S08 itself, the existing installed skills are already sufficient; these are only optional fallback aids.
