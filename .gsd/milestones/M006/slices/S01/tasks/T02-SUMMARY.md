---
id: T02
parent: S01
milestone: M006
provides: []
requires: []
affects: []
key_files: ["web/src/lib/admin/drill-in.ts", "web/src/app/admin/users/[id]/page.test.tsx", ".gsd/DECISIONS.md", ".gsd/milestones/M006/slices/S01/tasks/T02-SUMMARY.md", ".codex/loop/state.json", ".codex/loop/log.md"]
key_decisions: ["Derived missing `focusNote` values for `focusBucket=not_passed` from the shared drill-in helper instead of trusting every launcher or stored URL to include the note explicitly.", "Kept the user-detail page on the shared helper seam rather than adding page-local fallback logic for risk-bucket banner and prefill state."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Fresh focused verification passed. `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'` passed with 10/10 tests after the helper change, and `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/drill-in.test.ts' 'src/app/admin/users/[id]/page.test.tsx'` passed with 16/16 tests to prove the shared helper and destination page still agree on the round-trip contract. LSP diagnostics were clean for `web/src/lib/admin/drill-in.ts`, `web/src/app/admin/users/[id]/page.tsx`, and `web/src/app/admin/users/[id]/page.test.tsx`. A live browser spot-check on the local stack remained blocked by dev-login auth not persisting through the Next.js server boundary, which produced backend 401s and a redirect back to `/login`; this was an environment/session issue rather than a regression in the drill-in helper."
completed_at: 2026-03-27T03:28:21.349Z
blocker_discovered: false
---

# T02: Made admin user-detail drill-ins recover shared not-passed guidance text and locked the banner/prefill contract in tests.

> Made admin user-detail drill-ins recover shared not-passed guidance text and locked the banner/prefill contract in tests.

## What Happened
---
id: T02
parent: S01
milestone: M006
key_files:
  - web/src/lib/admin/drill-in.ts
  - web/src/app/admin/users/[id]/page.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/milestones/M006/slices/S01/tasks/T02-SUMMARY.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - Derived missing `focusNote` values for `focusBucket=not_passed` from the shared drill-in helper instead of trusting every launcher or stored URL to include the note explicitly.
  - Kept the user-detail page on the shared helper seam rather than adding page-local fallback logic for risk-bucket banner and prefill state.
duration: ""
verification_result: passed
completed_at: 2026-03-27T03:28:21.350Z
blocker_discovered: false
---

# T02: Made admin user-detail drill-ins recover shared not-passed guidance text and locked the banner/prefill contract in tests.

**Made admin user-detail drill-ins recover shared not-passed guidance text and locked the banner/prefill contract in tests.**

## What Happened

I treated the remaining T02 gap as a destination-side contract issue rather than another launcher refactor. First I added a focused UserDetailPage regression for a `focusBucket=not_passed&focusIssueFamily=objection_response` URL that omits `focusNote`; that failed because the banner rendered but the suggested note line and textarea prefill stayed empty. I then updated `readAdminUserDrillInContext(...)` in `web/src/lib/admin/drill-in.ts` so not-passed drill-ins recover the shared default note from the same issue-family mapping already used by the launcher helper whenever the destination URL still carries an issue family. The page component itself remained unchanged on the shared helper seam, and I tightened the existing risk-bucket page coverage to assert the supervisor-focus select is prefilled from the shared launcher contract as well. I also recorded the read-side fallback choice in D086 and updated the Safe Grow continuity files so the next turn starts at S01/T03 instead of reopening the drill-in parser work.

## Verification

Fresh focused verification passed. `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'` passed with 10/10 tests after the helper change, and `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/drill-in.test.ts' 'src/app/admin/users/[id]/page.test.tsx'` passed with 16/16 tests to prove the shared helper and destination page still agree on the round-trip contract. LSP diagnostics were clean for `web/src/lib/admin/drill-in.ts`, `web/src/app/admin/users/[id]/page.tsx`, and `web/src/app/admin/users/[id]/page.test.tsx`. A live browser spot-check on the local stack remained blocked by dev-login auth not persisting through the Next.js server boundary, which produced backend 401s and a redirect back to `/login`; this was an environment/session issue rather than a regression in the drill-in helper.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1130ms |
| 2 | `cd web && pnpm dlx npm@11.6.1 test -- --run 'src/lib/admin/drill-in.test.ts' 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1080ms |
| 3 | `lsp diagnostics: web/src/lib/admin/drill-in.ts, web/src/app/admin/users/\[id\]/page.tsx, web/src/app/admin/users/\[id\]/page.test.tsx` | 0 | ✅ pass | 100ms |


## Deviations

None.

## Known Issues

Local browser proof for the shipped admin route is still blocked by dev-login session persistence across the 127.0.0.1:3444 backend and 127.0.0.1:3445 web server boundary. Focused tests and diagnostics passed, so this did not block the task contract.

## Files Created/Modified

- `web/src/lib/admin/drill-in.ts`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/milestones/M006/slices/S01/tasks/T02-SUMMARY.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`


## Deviations
None.

## Known Issues
Local browser proof for the shipped admin route is still blocked by dev-login session persistence across the 127.0.0.1:3444 backend and 127.0.0.1:3445 web server boundary. Focused tests and diagnostics passed, so this did not block the task contract.
