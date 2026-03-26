---
id: T03
parent: S02
milestone: M005
provides: []
requires: []
affects: []
key_files: ["backend/src/common/analytics/history_service.py", "backend/src/admin/api/users.py", "backend/tests/integration/test_admin_users_api.py", "web/src/lib/api/types.ts", "web/src/app/admin/users/[id]/page.tsx", "web/src/app/admin/users/[id]/page.test.tsx", ".gsd/DECISIONS.md", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Derive manager intervention results on the `/api/v1/admin/users/{id}/sessions` read path from persisted interventions plus session-evidence projections instead of mutating intervention rows during admin reads.", "Prefer the latest evaluable completed session after an intervention when deciding the current manager result; only fall back to thin-evidence completed sessions when no evaluable follow-up exists yet."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the full task-plan verifier `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py`, which passed all 15 admin user integration tests including the new intervention-result regression. Also ran `cd web && /usr/bin/time -p pnpm exec vitest run 'src/app/admin/users/[id]/page.test.tsx'`, which passed all 6 focused admin user detail page tests after surfacing the linked result on the intervention card."
completed_at: 2026-03-26T08:01:50.909Z
blocker_discovered: false
---

# T03: Linked supervisor interventions to the latest meaningful session evidence and surfaced the result on the admin user detail page.

> Linked supervisor interventions to the latest meaningful session evidence and surfaced the result on the admin user detail page.

## What Happened
---
id: T03
parent: S02
milestone: M005
key_files:
  - backend/src/common/analytics/history_service.py
  - backend/src/admin/api/users.py
  - backend/tests/integration/test_admin_users_api.py
  - web/src/lib/api/types.ts
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/app/admin/users/[id]/page.test.tsx
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Derive manager intervention results on the `/api/v1/admin/users/{id}/sessions` read path from persisted interventions plus session-evidence projections instead of mutating intervention rows during admin reads.
  - Prefer the latest evaluable completed session after an intervention when deciding the current manager result; only fall back to thin-evidence completed sessions when no evaluable follow-up exists yet.
duration: ""
verification_result: passed
completed_at: 2026-03-26T08:01:50.910Z
blocker_discovered: false
---

# T03: Linked supervisor interventions to the latest meaningful session evidence and surfaced the result on the admin user detail page.

**Linked supervisor interventions to the latest meaningful session evidence and surfaced the result on the admin user detail page.**

## What Happened

Added a read-side manager intervention result projection on `/api/v1/admin/users/{id}/sessions` by combining persisted interventions with `HistoryService` and the existing session-evidence projection. The backend now normalizes intervention issue families against the current report/replay vocabulary and derives the latest meaningful outcome per intervention, preferring the newest evaluable completed session and only falling back to thin-evidence completions when no evaluable follow-up exists yet. The admin user detail page now renders that derived result directly on each intervention card and links straight to the matching unified report, so supervisors can see whether a later session improved the targeted issue family without leaving the current surface. Added backend integration coverage for improved/not-evaluable/pending outcomes and a focused page test for the new intervention-card result block.

## Verification

Ran the full task-plan verifier `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py`, which passed all 15 admin user integration tests including the new intervention-result regression. Also ran `cd web && /usr/bin/time -p pnpm exec vitest run 'src/app/admin/users/[id]/page.test.tsx'`, which passed all 6 focused admin user detail page tests after surfacing the linked result on the intervention card.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && /usr/bin/time -p venv/bin/python -m pytest -c pyproject.toml tests/integration/test_admin_users_api.py` | 0 | ✅ pass | 6900ms |
| 2 | `cd web && /usr/bin/time -p pnpm exec vitest run 'src/app/admin/users/[id]/page.test.tsx'` | 0 | ✅ pass | 1730ms |


## Deviations

Extended the planned backend-only file set with the typed frontend response/update on `web/src/lib/api/types.ts`, `web/src/app/admin/users/[id]/page.tsx`, and `web/src/app/admin/users/[id]/page.test.tsx` because a backend payload alone would not surface the linked result on the current admin page.

## Known Issues

None.

## Files Created/Modified

- `backend/src/common/analytics/history_service.py`
- `backend/src/admin/api/users.py`
- `backend/tests/integration/test_admin_users_api.py`
- `web/src/lib/api/types.ts`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`


## Deviations
Extended the planned backend-only file set with the typed frontend response/update on `web/src/lib/api/types.ts`, `web/src/app/admin/users/[id]/page.tsx`, and `web/src/app/admin/users/[id]/page.test.tsx` because a backend payload alone would not surface the linked result on the current admin page.

## Known Issues
None.
