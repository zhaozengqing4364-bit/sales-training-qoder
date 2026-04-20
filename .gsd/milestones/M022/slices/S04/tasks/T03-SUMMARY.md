---
id: T03
parent: S04
milestone: M022
key_files:
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .codex/roadmap/PROJECT_FUTURE.md
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D250 — Keep post-M022 organization/team/member rollout inside the modular monolith by default, and only consider service split after real organization-scoped write, membership-sync, and org-level analytics/export/compliance pressure appears.
duration: 
verification_result: passed
completed_at: 2026-04-14T08:37:54.709Z
blocker_discovered: false
---

# T03: Bound the org-boundary target state to the next enterprise roadmap with a modular-monolith default, explicit service-split triggers, and out-of-scope enterprise guardrails.

**Bound the org-boundary target state to the next enterprise roadmap with a modular-monolith default, explicit service-split triggers, and out-of-scope enterprise guardrails.**

## What Happened

I turned the M022/S04 organization/team/tenant target-state contract into a concrete downstream roadmap handoff instead of leaving it only inside the slice plan. In `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, the M022-S04 section now explicitly says when future enterprise work should stay inside the modular monolith: scope-aware readers on existing learner/manager/admin truth surfaces, membership-first authz, org rollout bindings, and organization metadata seams all remain monolith work by default. The same section now also names the next enterprise inputs to schedule (`organization_member` plus team assignment, session/report/replay/history/admin scope-aware readers, `global template + org rollout binding`, organization account metadata inventory, and provisioning adapter contracts for SSO/CRM/org sync), defines the exact service-split trigger test, and records the out-of-scope guardrail against multi-tenant runtime work, direct SSO/CRM production integration, new org dashboards, or rewriting current global rows straight into org-owned rows. I then rewrote `.codex/roadmap/PROJECT_FUTURE.md` from a blank growth-profile stub into a reader-first enterprise roadmap profile that mirrors the same product promise, evidence snapshot, priority order, candidate scoring, modular-monolith default, service-split conditions, and anti-goals. Finally, I recorded D250 so downstream milestones inherit one durable rule: org/team/member rollout stays inside the modular monolith until real scale, failure-isolation, release-cadence, or compliance pressure proves a service split is warranted.

## Verification

Ran the exact task-plan grep gate after the documentation write-back and confirmed it matched the new organization/team/tenant, monolith, service split, out-of-scope, SSO, and CRM roadmap language in both `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` and `.codex/roadmap/PROJECT_FUTURE.md`. I also ran a focused grep against `.gsd/DECISIONS.md` to verify that D250 captured the same modular-monolith default, service-split triggers, and SSO/CRM/org-sync adapter boundary.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "organization|team|tenant|monolith|service split|out-of-scope|SSO|CRM" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .codex/roadmap/PROJECT_FUTURE.md` | 0 | ✅ pass | 36ms |
| 2 | `rg -n "modular monolith|service split|SSO|CRM|org sync" .gsd/DECISIONS.md` | 0 | ✅ pass | 12ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
- `.codex/roadmap/PROJECT_FUTURE.md`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
