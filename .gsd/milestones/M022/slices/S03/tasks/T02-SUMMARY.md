---
id: T02
parent: S03
milestone: M022
key_files:
  - web/src/app/admin/page.tsx
  - web/src/app/admin/page.test.tsx
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-14T08:04:26.501Z
blocker_discovered: false
---

# T02: Removed the admin home’s remaining fake action/log/alert surfaces and left it linking only to real manager/admin evidence views.

**Removed the admin home’s remaining fake action/log/alert surfaces and left it linking only to real manager/admin evidence views.**

## What Happened

I executed T02 as a read-side honesty pass on the admin home instead of inventing another summary layer. `web/src/app/admin/page.tsx` now keeps only the live effectiveness card backed by `api.internal.health()` and `api.analyticsOpen.getDashboard({ days: 7 })`, while the rest of the page is rebuilt around two explicit states: (1) direct links into the current real manager/admin surfaces (`/admin/users`, `/admin/analytics`, `/admin/logs`) and (2) inventory-only cards for gaps that still lack a unified authority. This removed the remaining faux operator affordances from the home page — the old announcement modal, fake config values, fake log console, fake alerts, and fake activity feed no longer render. I extended `web/src/app/admin/page.test.tsx` in fail-first fashion so it now proves both sides of the boundary: the live effectiveness metrics still render from the mocked real APIs, and the old fake strings (`GPT-4-Turbo`, quota alerts, backup activity rows, etc.) are absent while the new real-entry links are present. I did not need to change `manager-lite` or backend admin analytics code for this task because the existing manager-lite panel and `admin_analytics_service` were already aligned to projection-backed evidence; the exact task-plan verification bundle confirms those surfaces still agree with the rewritten home-page boundary.

## Verification

Focused verification passed. I first ran the fail-first admin-home proof and then greened it after replacing the lower home-page faux surfaces with explicit truth-surface links and inventory copy. The exact task-plan verification command also passed unchanged: the web side finished 3/3 tests green across `src/app/admin/page.test.tsx` and `src/components/admin/manager-lite-panel.test.tsx`, and the backend side finished 5/5 green in `backend/tests/unit/common/test_admin_analytics_service.py`, confirming the manager-lite lists, not-passed/trend/calibration-adjacent analytics payloads, and admin home boundary all still sit on the same evidence line. I also re-checked LSP diagnostics on the touched page and test files; both were clean. For UI runtime verification, I attempted browser automation against `http://127.0.0.1:3000/admin`, but Playwright could not launch because the Chromium binary is missing in this environment, so browser verification remains an environment limitation rather than a product regression.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/app/admin/page.test.tsx` | 0 | ✅ pass | 4213ms |
| 2 | `npm --prefix web test -- --run "src/app/admin/page.test.tsx" "src/components/admin/manager-lite-panel.test.tsx" && backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py -x -q` | 0 | ✅ pass | 9001ms |

## Deviations

No product-scope deviation. The only local adaptation was narrowing the implementation to the admin home read side because the existing manager-lite and backend admin analytics surfaces were already truth-aligned and only needed to stay green under the slice verification bundle.

## Known Issues

Browser automation for localhost remains blocked in this harness because the Playwright Chromium binary is not installed (`browserType.launch` failed before navigation). The shipped page behavior is covered by the focused Vitest proof and the exact slice verification bundle instead.

## Files Created/Modified

- `web/src/app/admin/page.tsx`
- `web/src/app/admin/page.test.tsx`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
