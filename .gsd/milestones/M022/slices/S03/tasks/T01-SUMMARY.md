---
id: T01
parent: S03
milestone: M022
key_files:
  - web/src/app/admin/page.tsx
  - web/src/app/admin/page.test.tsx
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D246 — Keep only the admin-home effectiveness card on live authority and downgrade the remaining admin-home ops cards to inventory; reuse admin analytics, manager-lite, and admin user detail/interventions as the current P0 manager/admin truth surfaces.
duration: 
verification_result: passed
completed_at: 2026-04-14T07:52:15.727Z
blocker_discovered: false
---

# T01: Downgraded the admin home’s fake ops stats to truth-surface inventory and documented the real manager/admin evidence surfaces.

**Downgraded the admin home’s fake ops stats to truth-surface inventory and documented the real manager/admin evidence surfaces.**

## What Happened

I executed T01 as an honesty-first inventory pass instead of trying to invent a second stats layer. In `web/src/app/admin/page.tsx`, I kept only the top effectiveness card on real live authority (`api.internal.health()` plus `api.analyticsOpen.getDashboard({ days: 7 })`) and added an explicit “管理首页真实度说明” banner so the page now states which surface is real and which ones are still pending. I then removed the hardcoded fake admin-home literals for total users, active sessions, system health resources, and storage, replacing them with “待接真实统计” inventory copy and dialog descriptions that point operators back to the real surfaces (`/admin/users`, `/admin/analytics`, `/admin/logs`) instead of pretending the fake numbers are live. To make the downgrade durable, I added `web/src/app/admin/page.test.tsx` as a fail-first regression test that proves the banner is present, the live effectiveness metrics still render, and the old fake literals are absent. Finally, I wrote the inventory and priority order back into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`: admin analytics, manager-lite, and admin user detail/interventions are the current projection-backed P0 truth surfaces, while the remaining admin-home cards and lower draft action areas must stay downgraded until T02 wires real stats.

## Verification

Focused verification passed. `npm --prefix web test -- --run src/app/admin/page.test.tsx` finished 1/1 green after the fail-first admin page proof was added. The exact task-plan grep gate (`rg -n "2543|84|placeholder|demo|mock|dummy|manager-lite|analytics" web/src/app/admin web/src/components/admin backend/src/common/analytics backend/src/admin/api`) still exited 0 and showed the intended manager/admin/analytics surfaces for this inventory task. A targeted follow-up grep (`rg -n "2,543|84|42%|68%|75%|450 GB" web/src/app/admin/page.tsx`) exited 1, which is the expected success condition because the hardcoded fake admin-home literals are now gone. I also checked LSP diagnostics on `web/src/app/admin/page.tsx` and `web/src/app/admin/page.test.tsx`; both stayed clean. For UI verification, I started the local Next dev server with `bg_shell`, but browser automation could not proceed because the Playwright Chromium binary is missing in this environment; I stopped the temporary server before finishing so no stale background jobs remained.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/app/admin/page.test.tsx` | 0 | ✅ pass | 3890ms |
| 2 | `rg -n "2543|84|placeholder|demo|mock|dummy|manager-lite|analytics" web/src/app/admin web/src/components/admin backend/src/common/analytics backend/src/admin/api` | 0 | ✅ pass | 120ms |
| 3 | `rg -n "2,543|84|42%|68%|75%|450 GB" web/src/app/admin/page.tsx` | 1 | ✅ pass | 90ms |

## Deviations

Added a focused `web/src/app/admin/page.test.tsx` regression proof and recorded decision D246 so the honesty downgrade is durable; the task plan only named the page and architecture scan, but fail-first testing and decision capture were required by the execution workflow. I also updated `.codex/loop/state.json` and `.codex/loop/log.md` per the repository's safe-grow continuity rules.

## Known Issues

Browser verification in this harness is currently blocked because the Playwright Chromium binary is not installed, so the UI proof for this task comes from the focused Vitest page test plus static grep checks. Also, the lower admin-home quick-action / activity / alert areas remain explicitly marked as draft or inventory-only surfaces; they still need T02/T03 truthification or removal before they can be treated as real ops tooling.

## Files Created/Modified

- `web/src/app/admin/page.tsx`
- `web/src/app/admin/page.test.tsx`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
