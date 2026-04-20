---
id: T03
parent: S04
milestone: M019
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D218 — M020-M022 should reuse the assembled release-truth workflow bundle plus router-backed doc/spec drift proof until a new authority surface is explicitly promoted.
duration: 
verification_result: passed
completed_at: 2026-04-13T09:02:14.178Z
blocker_discovered: false
---

# T03: Locked the assembled release gate into a reusable repo-root bundle with router-backed doc/spec drift proof and an explicit admin-home truthfulness handoff.

**Locked the assembled release gate into a reusable repo-root bundle with router-backed doc/spec drift proof and an explicit admin-home truthfulness handoff.**

## What Happened

I executed T03 as a narrow writeback task on top of the already-live S04 surfaces instead of reopening workflow or runtime implementation. In `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` I tightened the assembled release-gate section so downstream work now has one explicit repo-root reuse bundle: the release-truth workflow, the NFR companion workflow, the focused web/backend checks, a router-backed `docs/api-contract` versus live-route inventory proof, and a negative inventory proof for legacy specs and admin home fake stats. I also corrected the broader planning theme text so future roadmap reading no longer says metrics/error/doc surfaces are simply ‘not connected’; the real risk is mis-promoting legacy specs or weak truth surfaces into authority. In `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` I updated the M019-S04 planning contract so M020-M022 default to reusing that same bundle unless they explicitly promote a new release surface, and I carried the admin home demo-stat gap forward as an M022-S03 input instead of letting it drift back into release-gate language. Finally, I added a knowledge entry documenting a non-obvious gotcha: `backend/src/main.py` still contains stale inline route-summary wording (`/api/v1/sessions`), so route modules plus repo-root drift greps—not top-level comments—are the trustworthy contract authority. I also recorded D218 so the downstream release-authority bundle is preserved as a project decision.

## Verification

I reran the exact task-plan grep gate after the edits and confirmed both the architecture scan and the next-wave plan still expose the required `release gate|metrics|error reporting|doc contract|repo-root` proof lines. I then ran a router-backed repo-root inventory proof across `docs/api-contract`, `backend/src/common/api/practice.py`, `backend/src/admin/api/release_verification.py`, and `backend/src/support/api/runtime_status.py`, which passed and showed the current doc-contract authority still matches the live practice, release-verification, and support-runtime route families. Finally, I ran a focused truthfulness/drift grep across the architecture scan, plan, knowledge log, `web/src/app/admin/page.tsx`, and `backend/src/main.py`, which passed and reconfirmed that the admin home still mixes live top-card metrics with hardcoded dashboard numbers and that the `main.py` inline route summary remains legacy-only commentary rather than release authority.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "release gate|metrics|error reporting|doc contract|repo-root" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md` | 0 | ✅ pass | 26ms |
| 2 | `rg -n "/practice/sessions|/admin/release-verification|/support/runtime" docs/api-contract backend/src/common/api/practice.py backend/src/admin/api/release_verification.py backend/src/support/api/runtime_status.py` | 0 | ✅ pass | 15ms |
| 3 | `rg -n "api.internal.health|api.analyticsOpen.getDashboard|2,543|84|42%|68%|75%|450 GB|legacy /api/v1/sessions|doc-contract drift gotcha" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md .gsd/KNOWLEDGE.md web/src/app/admin/page.tsx backend/src/main.py` | 0 | ✅ pass | 13ms |

## Deviations

Minor local adaptation: the architecture scan and next-wave plan already contained most of the assembled release-gate structure before T03 execution, so I focused this task on tightening the downstream reuse rule, adding the router-backed doc/live-route proof, and fixing the remaining stale planning language rather than inventing a second release-gate model.

## Known Issues

`web/src/app/admin/page.tsx` still contains hardcoded operational/demo stats and static log/alert copy outside the top live metrics card; this remains an explicit M022-S03 truth-surface input, not a release-gate blocker for T03. `backend/src/main.py` also still carries stale top-level route summary comments such as `/api/v1/sessions`; the task documents that drift but intentionally does not treat those comments as authority.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
