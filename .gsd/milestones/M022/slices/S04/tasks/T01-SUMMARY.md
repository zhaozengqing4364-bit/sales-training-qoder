---
id: T01
parent: S04
milestone: M022
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - D248 — Treat organization as the authz/account boundary, team as the coaching cohort boundary, tenant as a future heavier isolation slot, and keep agent/persona/knowledge on a global-template plus org-rollout-binding migration path.
duration: 
verification_result: passed
completed_at: 2026-04-14T08:24:29.917Z
blocker_discovered: false
---

# T01: Documented the current single-org ownership model and a concrete organization/team/tenant target-state matrix in the next-wave architecture and plan docs.

**Documented the current single-org ownership model and a concrete organization/team/tenant target-state matrix in the next-wave architecture and plan docs.**

## What Happened

I audited the shipped ownership/authz seams across `users`, `practice_sessions`, `manager_interventions`, agent/persona models, knowledge models, `common/auth`, `common/api/practice.py`, `admin/api/users.py`, `admin/api/analytics.py`, and the current admin truth surfaces. That audit confirmed the product is still global-user/global-role and `session.user_id` centric: learner read/write paths are owned by `practice_sessions.user_id`, manager/admin surfaces aggregate cross-user data behind a global admin guard, and most control-plane assets only expose `created_by/updated_by` audit fields rather than organization ownership. I then wrote the findings back into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` as an explicit current-state inventory plus a target-state matrix that separates organization, team, member, platform role, org/team role, access scope, and tenant. The same target-state contract was mirrored into `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` so downstream S04 work can reuse one agreed boundary: organization is the future authz/account boundary, team is the coaching/analytics cohort boundary, tenant remains a heavier future isolation slot, and agent/persona/knowledge assets should move through global-template plus org-rollout-binding seams instead of immediate table cloning. I also recorded decision D248 with that architectural split and added a knowledge note warning future agents not to fork the runtime/report truth line by making assets org-owned before membership/authz compatibility readers exist.

## Verification

Ran the task-plan grep gate after the doc write-back to confirm the repository still exposes the shipped `user_id`/`role`/`agent_id`/`persona_id`/`knowledge_base` seams in code while the updated architecture scan and post-M018 plan now include the new organization/team/tenant target-state language. The command exited successfully and matched both the real current-state evidence in backend/admin/web surfaces and the new target-state documentation in the two durable planning artifacts.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "user_id|role|owner|agent_id|persona_id|knowledge_base|organization|tenant|team" backend/src/common backend/src/admin web/src/app/admin .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md` | 0 | ✅ pass | 53ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
