# S04: Organization / team / tenant target-state plan — UAT

**Milestone:** M022
**Written:** 2026-04-14T08:42:41.728Z

# S04: Organization / team / tenant target-state plan — UAT

**Milestone:** M022  
**Written:** 2026-04-14

# S04 UAT — Organization/team/tenant roadmap is executable and bounded

## Preconditions
- Use the repository at the current M022/S04 close-out state.
- Open these artifacts: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, `.codex/roadmap/PROJECT_FUTURE.md`, `.gsd/DECISIONS.md`, and `.gsd/KNOWLEDGE.md`.
- Understand that this slice is a **contract/roadmap** slice, not a runtime implementation slice.

## Test Case 1 — Current-state single-org assumptions are explicitly documented
1. Open the M022/S04 section in `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`.
   - Expected: the document explicitly states that current ownership/authz is still based on global `users.user_id`, global `users.role`, and `practice_sessions.user_id` / `manager_interventions` row-level ownership.
2. Review the current-state inventory rows.
   - Expected: the scan names the hidden single-organization assumptions for identity/auth, learner session ownership, manager interventions, admin analytics/users, global content assets, and session-frozen runtime bindings.
3. Check the stated risk.
   - Expected: the document explains why these assumptions block future enterprise work if left implicit.

## Test Case 2 — Target-state matrix clearly separates organization, team, member, and tenant
1. In the same architecture-scan section, find the target-state concept boundary.
   - Expected: `organization`, `team`, `member`, and `tenant` are each defined separately.
2. Confirm the meaning of each concept.
   - Expected: `organization` is the account/authz/analytics boundary; `team` is the manager/coaching cohort; `member` is a global user’s org membership seam; `tenant` is a future heavier isolation slot and is not treated as the same thing as organization.
3. Check the asset rule.
   - Expected: agent/persona/knowledge are described as `global template + org rollout binding`, not as assets that must be cloned into org-owned rows immediately.
4. Cross-check the same concepts in `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`.
   - Expected: the plan repeats the same target-state definitions rather than inventing a second vocabulary.

## Test Case 3 — Migration path is reader-first and stays inside the modular monolith by default
1. In `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, locate the S04 migration path phases.
   - Expected: the first step is adding `organization_id` / `team_id` compatibility readers to session/report/replay/history/admin surfaces.
2. Review the next phases.
   - Expected: authz moves to `organization_member` + team assignment before asset ownership changes; rollout binding comes before org-owned content rows; external integrations remain adapters.
3. Confirm the ordering rule.
   - Expected: the plan explicitly says session/read-side scope reader → authz write path → asset rollout binding → external integration automation.
4. Confirm the architecture scan says the same thing.
   - Expected: the architecture scan mirrors the same reader-first modular-monolith migration order.

## Test Case 4 — Existing truth surfaces are reused instead of inventing a second enterprise product
1. Review the analytics/authz rules in the plan and architecture scan.
   - Expected: future org/team work must reuse `manager-lite-panel`, `/admin/users/[id]`, `/admin/analytics`, session/report/replay/history surfaces, and current auth helpers as the migration seams.
2. Check for alternative UI promises.
   - Expected: there is no claim that a new org dashboard, separate manager OS, or direct enterprise runtime authority already exists.
3. Verify the content/control-plane rule.
   - Expected: org rollout binding is described as additive to existing global templates, not as a reason to rebuild the current runtime/report evidence line.

## Test Case 5 — Future roadmap has explicit stay-in-monolith rules, service-split triggers, and out-of-scope guardrails
1. Open `.codex/roadmap/PROJECT_FUTURE.md`.
   - Expected: it contains a real future-growth profile, not an empty stub.
2. Review the priority order.
   - Expected: the top priorities are organization/team authz seam inside the monolith, org rollout binding for content/control plane, provisioning adapter contracts, and service split only after real pressure.
3. Review the `stay in monolith when` and `service split when` sections.
   - Expected: scope-aware readers, membership authz, rollout binding, and organization metadata remain monolith work; service split requires real pressure such as independent scale, failure isolation, release cadence, or retention/compliance boundaries.
4. Review the out-of-scope/anti-goals sections.
   - Expected: tenant implementation, SSO/CRM production integration, direct external-authority takeover, new org service/tenant service, fake enterprise dashboards, and skipping compatibility readers are all explicitly rejected for now.

## Test Case 6 — Decisions and reusable gotchas are recorded for downstream slices
1. Open `.gsd/DECISIONS.md` and locate D248, D249, and D250.
   - Expected: the decisions record the organization/team/member/tenant boundary, reader-first modular-monolith migration path, and service-split trigger rule.
2. Open `.gsd/KNOWLEDGE.md` and locate the S04 org-boundary note.
   - Expected: it warns future agents not to clone current asset tables into org-owned rows before membership/authz seams exist, because that would fork the runtime/report truth line.
3. Cross-check the roadmap and plan language.
   - Expected: downstream planning artifacts and decisions agree on the same boundary instead of drifting.

## Edge Cases
- If a future requirement only adds org/team scope readers or membership authz, it should still fall under the modular-monolith path and should **not** trigger a service split by itself.
- If someone proposes tenant isolation or direct SSO/CRM integration before organization/member/team seams exist, the artifacts should make clear that this is out of scope and violates the S04 contract.
- If a future slice adds org-aware asset ownership, it must preserve the `global template + org rollout binding` explanation until compatibility readers and membership authz are already in place.
- If new enterprise UI is proposed, it must reuse or truthfully extend current real manager/admin surfaces rather than presenting placeholder org dashboards as shipped capability.
