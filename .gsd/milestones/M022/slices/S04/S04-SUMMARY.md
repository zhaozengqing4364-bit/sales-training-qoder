---
id: S04
parent: M022
milestone: M022
provides:
  - A durable organization/team/member/tenant target-state contract for downstream enterprise milestones.
  - A reader-first modular-monolith migration path covering authz, analytics, asset rollout binding, and integration slots.
  - Explicit service-split triggers and out-of-scope enterprise guardrails so future slices do not overbuild too early.
requires:
  - slice: S01
    provides: The methodology-aware rubric seam that future org/team read-sides must reuse instead of inventing another sales taxonomy.
  - slice: S02
    provides: The global-template plus runtime-binding asset contract that S04 keeps as the content/control-plane migration baseline.
  - slice: S03
    provides: The locked manager/admin truth-surface boundary that S04 reuses for future org/team scope-aware readers.
affects:
  - future enterprise milestone planning
  - post-M022 roadmap prioritization
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  - .codex/roadmap/PROJECT_FUTURE.md
  - .gsd/DECISIONS.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D248 — Treat organization as the authz/account boundary, team as the coaching cohort boundary, tenant as a future heavier isolation slot, and keep agent/persona/knowledge on a global-template plus org-rollout-binding migration path.
  - D249 — Keep the org-boundary migration inside the modular monolith by introducing session/admin/auth compatibility readers and org rollout bindings before any org-owned asset cloning or service split.
  - D250 — Keep post-M022 organization/team/member rollout inside the modular monolith by default, and only consider service split after real organization-scoped write, membership-sync, and org-level analytics/export/compliance pressure appears.
patterns_established:
  - Separate organization/team/member/tenant explicitly before touching ownership or authz implementation.
  - Add scope-aware compatibility readers before changing write-path authority or cloning content assets.
  - Treat external enterprise systems as provisioning/metadata adapters until the internal org/member/team seams already exist.
  - Write architecture scan, durable plan, future roadmap, decisions, and knowledge guardrails together so enterprise language cannot drift from the actual execution contract.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M022/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M022/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M022/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T08:42:41.727Z
blocker_discovered: false
---

# S04: Organization / team / tenant target-state plan

**S04 turned organization/team/tenant work from an abstract future idea into a reader-first enterprise roadmap contract anchored in the current modular monolith and current truth surfaces.**

## What Happened

# S04: Organization / team / tenant target-state plan

**Organization/team/tenant work now has one executable target-state contract: keep enterprise rollout inside the current modular monolith by default, add scope-aware readers and membership authz before asset ownership changes, and treat SSO/CRM/org-sync as provisioning adapters rather than runtime authorities.**

## What Happened

S04 closed M022 by converting the repository's implicit single-organization assumptions into an explicit enterprise migration contract. T01 audited the current ownership and authz model across `users`, `practice_sessions`, `manager_interventions`, agent/persona/knowledge assets, auth helpers, and admin truth surfaces, then wrote that inventory into the architecture scan. The resulting target-state matrix now clearly separates **organization** as the account/authz/analytics boundary, **team** as the manager/coaching cohort boundary, **member** as the per-organization membership seam, and **tenant** as a heavier future isolation slot that stays out of current scope. It also fixed the asset rule: agent/persona/knowledge should remain on a `global template + org rollout binding` path first, instead of prematurely cloning today's global rows into org-owned assets.

T02 turned that matrix into an execution order. The durable plan and architecture scan now both lock the same reader-first migration path: first add `organization_id` / `team_id` compatibility readers to session/report/replay/history/admin surfaces; then introduce `organization_member` plus team assignment so authz can move from global role checks toward `platform role + membership role + access scope`; only after that should content/control-plane rollout binding evolve; and external systems such as SSO, CRM, and org sync must stay metadata/provisioning adapters rather than taking over runtime truth. This keeps the current modular monolith intact while creating a safe org-aware seam for future work.

T03 bound that contract to downstream roadmap execution. `.codex/roadmap/PROJECT_FUTURE.md` is no longer a placeholder stub; it now mirrors the same priority order, stay-in-monolith default, explicit service-split trigger test, and anti-goals. Future enterprise work now has a single entry rule: if the requirement is still just scope-aware readers, membership authz, org rollout binding, or organization metadata, it belongs inside the monolith. A service split is only justified when organization-scoped write paths, membership sync, or org analytics/export/compliance require independent scale, failure isolation, release cadence, or retention boundaries that the modular monolith can no longer safely absorb.

Across the slice, S04 intentionally did **not** implement multi-tenant runtime, SSO/CRM production integration, org sync automation, or new org dashboards. Instead it delivered the contract that future slices can directly reuse without rerunning a full-repository investigation. That is the main closure value of S04: downstream roadmap/planning agents now have one durable answer for where organization/team/member ownership belongs, how authz should evolve, which current surfaces must be reused, and when architecture churn is actually warranted.

## Verification

Fresh slice-close verification reran every slice-plan gate and all of them passed. `rg -n "user_id|role|owner|agent_id|persona_id|knowledge_base|organization|tenant|team" backend/src/common backend/src/admin web/src/app/admin .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` passed, confirming the current codebase still exposes the real global-user/global-role ownership seams while the architecture scan documents the new org/team/tenant target-state boundary. `rg -n "migration path|organization|team|tenant|SSO|CRM|org sync|compatibility reader" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` passed, proving the reader-first migration path, authz sequencing, and integration-slot rules are written into both durable planning artifacts. `rg -n "organization|team|tenant|monolith|service split|out-of-scope|SSO|CRM" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .codex/roadmap/PROJECT_FUTURE.md` passed, confirming the roadmap handoff, monolith default, service-split triggers, and explicit out-of-scope guardrails now exist in both planning surfaces. A focused decision/knowledge check also confirmed D248, D249, D250, and the S04 org-boundary gotcha are already recorded, so downstream agents can rely on the same boundary without rediscovering it.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

- Future enterprise work should be planned as organization/member/team seams on current truth surfaces, not as a parallel multi-tenant platform initiative.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

S04 is intentionally a contract/roadmap slice, not an implementation slice. The shipped product is still global-user/global-role and single-org by default: there is no `organization_member` table, no scope-aware session/admin readers, no org rollout binding in runtime storage, and no SSO/CRM/org-sync automation yet.

## Follow-ups

Turn the S04 contract into the next enterprise milestone by implementing `organization_member` + team assignment, scope-aware readers on session/report/replay/history/admin surfaces, and `global template + org rollout binding` visibility. Keep future enterprise work inside the modular monolith unless the recorded service-split trigger conditions become true.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Added the current-state ownership inventory, target-state matrix, and reader-first migration contract for organization/team/member/tenant work.
- `.gsd/plans/GSD_PLAN_post-M018-next-wave.md` — Added the S04 roadmap contract, migration phases, compatibility-reader surfaces, monolith default, and out-of-scope guardrails.
- `.codex/roadmap/PROJECT_FUTURE.md` — Replaced the previous stub with a concrete enterprise roadmap profile covering priority order, candidate scoring, stay-in-monolith rules, service-split triggers, and anti-goals.
- `.gsd/DECISIONS.md` — Recorded D248-D250 so the org-boundary separation, migration order, and service-split rule are durable.
- `.gsd/KNOWLEDGE.md` — Captured the org-boundary gotcha warning future agents not to fork runtime/report truth by cloning org-owned assets too early.
