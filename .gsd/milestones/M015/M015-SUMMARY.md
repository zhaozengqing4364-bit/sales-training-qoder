---
id: M015
title: "Frontend hygiene 与 learner shell 保护收口"
status: complete
completed_at: 2026-04-11T19:02:51.152Z
key_decisions:
  - D180/D182 — keep raw console limited to the shared debug seam/bootstrap exceptions and route all business diagnostics through `debug.*`
  - D181 — use `debug.durableError(scope, error, context)` as the durable frontend failure seam for route and boundary errors
  - D183/D184 — centralize interruptive UI inventory in `auth-handler` and route auth redirects/destructive admin actions through router/dialog/toast seams
  - D185/D186/D187 — close learner-shell fallback coverage at shared learner-core route loaders/errors while keeping responsive/timezone leftovers as explicit deferred baseline facts
key_files:
  - web/src/lib/debug.ts
  - web/src/lib/console-boundary.test.ts
  - web/src/lib/auth-handler.ts
  - web/src/components/providers/app-providers.tsx
  - web/src/components/layout/dashboard-shell.tsx
  - web/src/components/layout/admin-shell.tsx
  - web/src/app/admin/records/page.tsx
  - web/src/app/admin/rag-profiles/page.tsx
  - web/src/app/admin/personas/[id]/page.tsx
  - web/src/components/learner/learner-route-loading-state.tsx
  - web/src/app/(dashboard)/loading.tsx
  - web/src/app/(auth)/loading.tsx
  - web/src/app/(auth)/error.tsx
  - web/src/app/(user)/practice/[sessionId]/loading.tsx
  - web/src/app/learner-shell-baseline.test.ts
lessons_learned:
  - In this repository, milestone close-out must use `origin/001-ai-practice-system` as the integration branch for the non-`.gsd` diff gate; `main` is not a valid verification base here.
  - For hygiene/fallback milestones, one explicit cross-slice proof bundle is more trustworthy than trusting slice-local green checks in isolation.
  - Some roadmap files encode acceptance only in the slice overview `After this` column; close-out should verify those shipped outcomes directly and record the absence of extra success-criteria/horizontal-checklist sections instead of inventing new ones.
---

# M015: Frontend hygiene 与 learner shell 保护收口

**M015 closed the frontend hygiene cleanup by proving shared debug/auth/dialog/router seams and learner-shell loading/error fallbacks now hold across the shipped web surfaces.**

## What Happened

M015 deliberately treated frontend hygiene as a closure milestone instead of a frontend rewrite. S01 collapsed business-page logging onto the shared `debug` seam and moved learner/admin route-failure reporting onto `debug.durableError(...)`, with raw console restricted to the intended bootstrap/debug boundary. S02 replaced remaining business-path native dialogs and hard browser redirects with the shared `ConfirmDialog`/toast/router/`authHandler` seams, so auth expiry, destructive admin actions, and persona feedback no longer rely on browser primitives. S03 then closed learner-shell route protection by adding explicit loading/error coverage for learner dashboard/auth/practice routes and locking the remaining responsive/timezone risks as deliberate deferred baseline facts rather than silently expanding scope.

Milestone close-out reran fresh evidence instead of trusting slice-local claims. The branch-level code-existence gate had to use this repository’s real integration branch (`origin/001-ai-practice-system`, not `main`, which is not a valid ref here); against that base, `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'` reported extensive non-`.gsd/` implementation changes including the key M015 web surfaces. Cross-slice integration was then reverified with one focused web bundle: `npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx src/lib/auth-handler.test.ts src/components/layout/dashboard-shell.test.tsx src/components/layout/admin-shell.test.tsx src/app/admin/records/page.test.tsx src/app/admin/rag-profiles/page.test.tsx "src/app/admin/personas/[id]/page.test.tsx" src/app/learner-shell-baseline.test.ts "src/app/(user)/practice/[sessionId]/error.test.tsx" "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`, which passed 14 files / 69 tests. The only stderr output was expected mocked failure-path logging while asserting toast/blocking fallbacks.

## Decision Re-evaluation

| Decision | Re-evaluation | Status |
|---|---|---|
| D180 / D182 — raw console stays limited to bootstrap + shared debug seam, business/runtime callers use `debug.*` | Still valid. Fresh `console-boundary` + `debug` proof and slice-close inventory evidence show the boundary held without blocking legitimate diagnostics. | Keep |
| D181 — route error surfaces use `debug.durableError(scope, error, context)` | Still valid. Error-reporting and learner route error tests passed, and S03 reused the same durable seam instead of introducing a second learner-shell reporter. | Keep |
| D183 / D184 — native dialog and hard-navigation inventory lives in `auth-handler`, auth redirects go through router-aware `authHandler`, destructive admin flows use ConfirmDialog + toast | Still valid. Fresh auth-handler, dashboard/admin shell, records, rag-profile, and persona tests proved the seam works across auth expiry and destructive flows. | Keep |
| D185 / D186 / D187 — learner-shell closure happens at shared dashboard/auth/practice loaders, scoped to learner-core routes, while remaining responsive/timezone issues stay explicitly deferred | Still valid. `learner-shell-baseline.test.ts` and learner report/replay/history/practice proof show route-shell closure now exists and the remaining UX debt is intentionally documented rather than hidden. | Keep |

The roadmap did not expose a separate Success Criteria or Horizontal Checklist block beyond the slice overview; per the project knowledge note, close-out therefore treated each slice overview “After this” outcome as the milestone acceptance criteria and recorded that no additional horizontal checklist items were present. No requirement status transitioned during M015: the milestone tightened frontend consistency and learner-shell protection, but it did not add, validate, defer, or invalidate any explicit requirement rows.

## Success Criteria Results

The roadmap’s explicit acceptance criteria were encoded in the slice overview “After this” column rather than in a separate success-criteria section.

- ✅ **S01 — 前端业务页面中的 console 输出被统一收口到共享 debug/observability seam。** Evidence: S01 summary records raw console narrowed to `web/src/lib/debug.ts` plus `web/src/instrumentation*.ts`, route failures migrated to `debug.durableError(...)`, and the fresh close-out bundle passed `src/lib/console-boundary.test.ts`, `src/lib/debug.test.ts`, and `src/components/error-reporting.test.tsx`.
- ✅ **S02 — 业务页面中的原生弹窗和直接浏览器跳转被替换为 toast/dialog/router/auth-handler seam。** Evidence: S02 summary records destructive admin flows and auth redirects moved onto shared seams; the fresh close-out bundle passed `src/lib/auth-handler.test.ts`, `src/components/layout/dashboard-shell.test.tsx`, `src/components/layout/admin-shell.test.tsx`, `src/app/admin/records/page.test.tsx`, `src/app/admin/rag-profiles/page.test.tsx`, and `src/app/admin/personas/[id]/page.test.tsx`.
- ✅ **S03 — learner 核心路由都有 error/loading fallback，且 baseline responsive/a11y/timezone 风险有记录和低风险修复。** Evidence: S03 summary records new dashboard/auth/practice loaders, auth error surface, and the baseline proof file; the fresh close-out bundle passed `src/app/learner-shell-baseline.test.ts`, `src/app/(user)/practice/[sessionId]/error.test.tsx`, `src/app/(dashboard)/history/page.test.tsx`, `src/app/(user)/practice/[sessionId]/report/page.test.tsx`, and `src/app/(user)/practice/[sessionId]/replay/page.test.tsx`.

Result: all milestone acceptance criteria were met with fresh close-out evidence.

## Definition of Done Results

- ✅ **All slices complete:** `gsd_milestone_status(milestoneId: "M015")` reported S01, S02, and S03 all in `complete` status, each with 3/3 tasks done.
- ✅ **All slice summaries exist:** `find .gsd/milestones/M015 -maxdepth 3 \( -name '*-SUMMARY.md' -o -name '*-ROADMAP.md' -o -name '*-PLAN.md' -o -name '*-UAT.md' \) | sort` returned `M015-ROADMAP.md` plus `S01-SUMMARY.md`, `S02-SUMMARY.md`, and `S03-SUMMARY.md` (along with their plan/UAT companions).
- ✅ **Cross-slice integration works:** the fresh close-out command `npm --prefix web test -- --run ...` passed 14 files / 69 tests covering the console boundary, error-reporting seam, auth/router seam, admin destructive flows, learner-shell baseline, and learner report/replay/history/practice surfaces.
- ✅ **Milestone shipped real code, not only planning artifacts:** the branch-level diff gate against `origin/001-ai-practice-system` returned extensive non-`.gsd/` changes, including the M015 web files named in the slice summaries.
- ✅ **Horizontal checklist:** none was present in the roadmap beyond the slice overview, so there were no additional checklist items to close.

## Requirement Outcomes

No requirement status transitions occurred during M015.

- `R022` and `R023` remain active and unchanged; M015 improved frontend hygiene and learner-shell safety, but it did not alter retrieval-truth requirement scope or validation state.
- No new requirements were surfaced by S01, S02, or S03.
- No requirements were invalidated, deferred, or newly validated as part of milestone close-out.

Result: `.gsd/REQUIREMENTS.md` does not need status updates for this milestone close-out.

## Deviations

None. Close-out used the repository’s real integration branch (`origin/001-ai-practice-system`) for the required code-diff verification, which is the documented equivalent of the generic `main` example in the auto-mode prompt.

## Follow-ups

Future milestones can now build on the sealed seams instead of reopening hygiene work: keep raw console and interruptive-UI boundaries enforced by their focused tests, and if mobile-density or timezone semantics become in-scope product work, update `web/src/app/learner-shell-baseline.test.ts` together with the implementation so the deferred baseline facts stay truthful.
