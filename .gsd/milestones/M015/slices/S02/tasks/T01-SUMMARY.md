---
id: T01
parent: S02
milestone: M015
key_files:
  - web/src/lib/auth-handler.ts
  - web/src/lib/auth-handler.test.ts
  - web/src/app/admin/records/page.tsx
  - web/src/app/admin/rag-profiles/page.tsx
  - web/src/app/admin/personas/[id]/page.tsx
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D183 — keep the native-dialog/hard-navigation inventory in `web/src/lib/auth-handler.ts` as `interruptiveUiInventory`, using tokenized primitive labels and explicit allowed-exception entries so the grep gate stays trustworthy.
duration: 
verification_result: passed
completed_at: 2026-04-11T17:53:06.053Z
blocker_discovered: false
---

# T01: Centralized the remaining native-dialog and hard-navigation inventory into a shared auth-handler seam map with focused proof.

**Centralized the remaining native-dialog and hard-navigation inventory into a shared auth-handler seam map with focused proof.**

## What Happened

I started from the slice grep gate and the planned authority files, then verified the real remaining usage points before touching code. The scan showed three cleanup families that matter for S02: delete confirmations in `web/src/app/admin/records/page.tsx` and `web/src/app/admin/rag-profiles/page.tsx`, auth redirects in `web/src/lib/auth-handler.ts` plus the admin/learner shell guards, and blocking feedback modals in `web/src/app/admin/personas/[id]/page.tsx`. I also confirmed the grep command still catches some non-navigation `window.location.href` reads in `ErrorBoundary` and `performance.ts`, plus the explicit admin error fallback, so T01 needed to distinguish true cleanup work from explained exceptions instead of just listing raw matches.

To make that durable, I added `interruptiveUiInventory` to `web/src/lib/auth-handler.ts` as the shared authority seam for this slice. Each entry records the file, primitive kind, category, target seam (`dialog`, `toast`, `router`, `auth-handler`, or `allowed-exception`), cleanup status, and a short rationale. I kept the primitive labels tokenized (`native-alert`, `location-assign`, etc.) so the inventory itself does not pollute the slice grep gate. I then added local inline inventory notes to the hottest admin touchpoints (`records`, `rag-profiles`, `personas/[id]`) so the eventual T02 cleanup can land on the correct seam without re-researching the page. Finally, I added a focused unit assertion in `web/src/lib/auth-handler.test.ts` to lock the presence of both the real cleanup items and the documented grep exceptions, recorded the pattern in `.gsd/KNOWLEDGE.md`, and saved decision D183 for the centralized inventory approach.

## Verification

Ran `npm --prefix web test -- --run src/lib/auth-handler.test.ts`, which passed 4/4 and proved the shared inventory exposes both the remaining cleanup set and the allowed-exception set. Re-ran the slice grep gate with `rg -n "\\b(alert|confirm)\\s*\\(|window\\.location(\\.assign|\\.href)" web/src`; it stayed intentionally non-empty at T01 stage, but now isolates only the real remaining cleanup points (`auth-handler`, `admin-shell`, `dashboard-shell`, `records`, `rag-profiles`, `personas/[id]`) plus the documented exceptions (`ErrorBoundary`, `performance.ts`, `app/admin/error.tsx`). Fresh LSP diagnostics were clean on `web/src/lib/auth-handler.ts`, `web/src/app/admin/records/page.tsx`, `web/src/app/admin/rag-profiles/page.tsx`, `web/src/app/admin/personas/*/page.tsx`, and `web/src/lib/auth-handler.test.ts`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix web test -- --run src/lib/auth-handler.test.ts` | 0 | ✅ pass | 820ms |
| 2 | `rg -n "\\b(alert|confirm)\\s*\\(|window\\.location(\\.assign|\\.href)" web/src` | 0 | ✅ pass | 20ms |

## Deviations

Added a focused auth-handler inventory unit test and centralized the classification table in code instead of leaving the inventory only in prose, so downstream tasks can import and update one authority seam. This stayed within the task goal of producing a durable classification map for every remaining usage point.

## Known Issues

The actual cleanup has not happened yet by design: `web/src/lib/auth-handler.ts`, `web/src/components/layout/admin-shell.tsx`, and `web/src/components/layout/dashboard-shell.tsx` still use hard browser redirects, while `web/src/app/admin/records/page.tsx`, `web/src/app/admin/rag-profiles/page.tsx`, and `web/src/app/admin/personas/[id]/page.tsx` still contain native confirm/alert calls. Those live hits are now explicitly tracked by `interruptiveUiInventory` for T02/T03 rather than being treated as unexplained regressions.

## Files Created/Modified

- `web/src/lib/auth-handler.ts`
- `web/src/lib/auth-handler.test.ts`
- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
