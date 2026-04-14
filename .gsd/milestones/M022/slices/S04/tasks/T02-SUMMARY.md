---
id: T02
parent: S04
milestone: M022
key_files:
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D249 — Keep the org-boundary migration inside the modular monolith by introducing session/admin/auth compatibility readers and org rollout bindings before any org-owned asset cloning or service split.
duration: 
verification_result: passed
completed_at: 2026-04-14T08:32:24.940Z
blocker_discovered: false
---

# T02: Documented a reader-first org-boundary migration path for the modular monolith, including authz sequencing, compatibility-reader surfaces, and future SSO/CRM/org sync slots.

**Documented a reader-first org-boundary migration path for the modular monolith, including authz sequencing, compatibility-reader surfaces, and future SSO/CRM/org sync slots.**

## What Happened

I used the T01 matrix plus the current shipped ownership/auth seams in `backend/src/common/db/models.py`, `backend/src/common/auth/service.py`, `common/api/practice.py`, `admin/api/users.py`, and `admin/api/analytics.py` to turn the org/team/tenant target-state into an executable migration sequence rather than leaving it as a static concept table. The two durable planning artifacts now both say the same thing: stay inside the modular monolith, add organization/team compatibility readers to session/report/replay/history/admin truth surfaces first, move authz onto membership + access-scope readers before changing `users.role` semantics, keep agent/persona/knowledge/prompt/runtime assets on global-template plus org-rollout-binding seams instead of cloning org-owned rows, and treat future SSO/CRM/org sync work as provisioning/metadata adapters instead of new runtime authorities. I also recorded D249 so downstream slices inherit the same reader-first ordering rule and do not fork the org-boundary story when future enterprise work starts.

## Verification

Ran the exact task-plan grep gate after the final edits and continuity updates. It exited 0 and matched the new migration-path language, compatibility-reader surfaces, organization/team/tenant target-state references, and future SSO/CRM/org sync adapter slots in both `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` and `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`. I also confirmed the architectural decision write-back landed in `.gsd/DECISIONS.md` as D249 so the migration order is durable for downstream work.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "migration path|organization|team|tenant|SSO|CRM|org sync|compatibility reader" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` | 0 | ✅ pass | 27ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
