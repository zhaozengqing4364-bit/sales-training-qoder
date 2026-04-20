---
id: M022
title: "Sales productization / manager truth / organization-ready roadmap"
status: complete
completed_at: 2026-04-14T08:55:39.152Z
key_decisions:
  - Add new sales semantics as additive canonical-kernel metadata plus compatibility readers instead of replacing the shipped score/report schema.
  - Keep industry pack as a composed asset on existing agent/persona/knowledge/scenario surfaces and expose inspectable contract endpoints rather than building a second content platform.
  - Downgrade non-authoritative admin-home surfaces to inventory/link copy instead of inventing fake live manager metrics.
  - Treat manager-lite, admin analytics, and admin user detail/interventions as the only currently productized manager/admin truth surfaces.
  - Keep enterprise/org-boundary work reader-first and modular-monolith-first, with SSO/CRM/org-sync as provisioning/metadata adapters rather than runtime authorities.
key_files:
  - backend/src/common/effectiveness/methodology.py
  - backend/src/common/effectiveness/canonical.py
  - backend/src/agent/services/industry_pack_contract.py
  - backend/src/common/db/voice_policy_snapshot.py
  - backend/src/common/conversation/schemas.py
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/admin/api/users.py
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/admin/personas/[id]/page.tsx
  - web/src/app/admin/agents/[id]/page.tsx
  - web/src/app/admin/page.tsx
  - .codex/roadmap/PROJECT_FUTURE.md
lessons_learned:
  - When productizing a new sales concept, add it to the canonical evidence/session-snapshot/read-side seams first; parallel schemas and page-local heuristics recreate drift immediately.
  - If an operator surface has no real backend authority, downgrade it to inventory/link copy instead of fake-connecting it to demo numbers.
  - Composed assets over existing admin surfaces are often a safer first step than building a new content platform; frozen runtime provenance gives downstream readers a more honest contract.
  - Enterprise readiness should begin with scope-aware readers, membership/authz seams, and rollout bindings inside the modular monolith; external SSO/CRM/org-sync should stay adapter-only until the internal org boundary is real.
---

# M022: Sales productization / manager truth / organization-ready roadmap

**M022 turned the sales-training stack into a more productized, truth-backed system by shipping methodology-aware rubric semantics, inspectable industry-pack/runtime provenance, honest manager/admin truth surfaces, and an executable organization/team/tenant migration roadmap.**

## What Happened

M022 assembled four deliberately connected slices into one coherent product boundary. S01 established the first code-owned sales methodology/rubric contract and threaded it through realtime, completed-session projection, compatibility readers, and learner report copy so sales quality can be explained with one shared vocabulary instead of per-surface heuristics. S02 then made persona/scenario/customer-pressure/industry-pack work operational on the existing admin/runtime surfaces by publishing composed-asset contract endpoints and freezing immutable runtime provenance into `voice_policy_snapshot_ref.runtime_binding` for detail/report/replay readers. S03 drew an honest manager/admin boundary: admin home now keeps only the live effectiveness card on backend authority, while manager-lite, `/admin/analytics`, and `/admin/users/[id]` remain the only currently productized manager/admin truth surfaces. S04 completed the enterprise-ready planning layer by documenting the current single-org assumptions, the organization/team/member/tenant target-state split, the reader-first migration order, modular-monolith-by-default execution, and the adapter-only role of SSO/CRM/org-sync.

Across the milestone, the recurring pattern was to make new concepts additive to existing authority seams instead of spawning parallel platforms: methodology lives on canonical evaluation + compatibility readers, industry pack remains a composed asset over current agent/persona/knowledge/scenario surfaces, manager truth is constrained to already evidence-backed screens, and enterprise planning stays inside the current monolith until scope-aware readers, membership authz, and rollout bindings become real. That keeps the shipped learner/admin product honest today while giving the next milestone a concrete, reusable contract for future organization-scoped work.

## Success Criteria Results

## Success criteria verification

The roadmap did not expose a separate `Success Criteria` section in the preloaded context; M022 encoded acceptance through the slice overview `After this` outcomes. Verification was performed against those outcomes directly.

- ✅ **Methodology-aware rubric is now a real shared contract across sales surfaces.** S01 introduced `backend/src/common/effectiveness/methodology.py`, mirrored it through `canonical_evaluation_kernel.methodology` and `compatibility_readers.sales_methodology_rubric_v1`, and exposed the same semantics on the learner report explainer surface. Slice evidence recorded fresh proof from `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "sales and (report or replay or history or analytics)" -x -q` (24 selected tests passed) and `npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` (24/24 passed).
- ✅ **Persona / scenario / customer-pressure / industry-pack behavior is inspectable through existing admin entrypoints instead of a prompt-only setup.** S02 shipped `backend/src/agent/services/industry_pack_contract.py`, froze `voice_policy_snapshot_ref.runtime_binding`, and added the admin persona `Industry Pack 合同` plus admin agent `Industry Pack 运行合同` cards. Slice evidence recorded `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q` (352 tests passed, 2 skipped) plus focused web proof for both admin detail pages.
- ✅ **Manager/admin decision surfaces now stay on canonical evidence or explicitly downgrade to inventory.** S03 fixed the truth boundary by keeping only the admin-home effectiveness card on live authority and by reusing `web/src/components/admin/manager-lite-panel.tsx`, `backend/src/common/analytics/admin_analytics_service.py`, and `backend/src/admin/api/users.py` as the shipped manager/admin truth seam. The slice summary explicitly recorded `verification_result: passed`, and the key proof files lock the admin-home truth boundary and projection-backed analytics/user detail authority.
- ✅ **Organization / team / tenant work now has an executable, boundary-honest roadmap instead of a vague future note.** S04 wrote the target-state matrix, reader-first migration order, modular-monolith default, service-split triggers, and adapter guardrails into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, `.codex/roadmap/PROJECT_FUTURE.md`, and decisions D248-D250. Fresh S04 close-out proof explicitly captured the three `rg` inventory commands that verified the code/docs boundary and migration plan.

## Code-change verification

- ✅ Branch-level non-`.gsd` diff verification passed using the repository's real integration branch: `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'`.
- Evidence: the diff returned extensive non-`.gsd` changes, including shipped backend/web/doc files such as `backend/src/common/effectiveness/methodology.py`, `backend/src/common/effectiveness/canonical.py`, `backend/src/agent/services/industry_pack_contract.py`, `backend/src/common/db/voice_policy_snapshot.py`, `web/src/app/admin/page.tsx`, `web/src/app/admin/personas/[id]/page.tsx`, `web/src/app/admin/agents/[id]/page.tsx`, and `.codex/roadmap/PROJECT_FUTURE.md`.

## Horizontal checklist

- The preloaded roadmap context did not expose a separate Horizontal Checklist section. Nothing additional beyond the verified slice outcomes was left unchecked.

## Definition of Done Results

## Definition of done verification

- ✅ **All slices complete.** `gsd_milestone_status(M022)` returned S01/S02/S03/S04 all in `complete` state, each with all 3/3 tasks done.
- ✅ **All slice summaries exist.** `find .gsd/milestones/M022/slices -type f \( -name 'S??-SUMMARY.md' -o -name 'T??-SUMMARY.md' \) | sort` returned all four slice summaries plus all twelve task summaries.
- ✅ **Cross-slice integration is coherent with declared dependencies.**
  - S03 consumes the methodology-aware rubric semantics established by S01 instead of inventing a manager-only taxonomy.
  - S03 and later roadmap work reuse the immutable `voice_policy_snapshot_ref.runtime_binding` provenance introduced by S02.
  - S04 builds the enterprise target-state on top of the already-shipped methodology / industry-pack / manager truth seams instead of reopening them.
  - `.gsd/PROJECT.md`, `.gsd/KNOWLEDGE.md`, the architecture scan, and the post-M018 plan all align on the same boundary: no second content platform, no fake manager OS, no premature service split.

## Decision re-evaluation

| Decision | Still valid? | Evidence | Revisit next milestone? |
|---|---|---|---|
| D244 — industry pack stays a composed asset over existing agent/persona/knowledge/scenario surfaces | Yes | S02 shipped read-only contract endpoints and admin/runtime inspection surfaces without creating a standalone platform | No |
| D245 — runtime provenance should freeze into `voice_policy_snapshot_ref.runtime_binding` | Yes | S02 reused the frozen runtime-binding seam across detail/report/replay and documented it as the downstream authority | No |
| D246 — admin home keeps only the live effectiveness card and downgrades the rest to inventory | Yes | S03 delivered the downgraded admin-home boundary and locked it with focused page tests | No |
| D247 — productized manager/admin truth surfaces are manager-lite + admin analytics + admin user detail/interventions only | Yes | S03 documentation and code now consistently frame these as the only shipped truth surfaces | No |
| D248 — organization/team/tenant must stay separate, with assets global-first and rollout bindings before org-owned rows | Yes | S04 documented the target-state split and the anti-pattern of cloning current assets into org-owned rows too early | No |
| D249 — org migration stays reader-first and modular-monolith-first | Yes | S04 wrote the reader-first migration order into architecture/roadmap artifacts and no slice violated it | No |
| D250 — service split happens only after real org-scoped scale/isolation/release pressures exist; SSO/CRM/org-sync remain adapters | Yes | S04 formalized service-split triggers and adapter-only guardrails; nothing built in M022 contradicts that boundary | No |

## Requirement Outcomes

## Requirement status transitions

- **No requirement status changed during M022.** No requirement moved between Active / Validated / Deferred / Blocked / Out of Scope, so no `gsd_requirement_update` call was required before milestone completion.
- **R012 was advanced but not re-statused.** The milestone materially extended the validated long-term-governance story by keeping methodology, industry-pack governance, manager/admin truth, and enterprise planning on inspectable existing surfaces instead of prompt-only setup or placeholder dashboards. However, R012 was already in `validated` state before M022, so the correct outcome is additional supporting evidence without a status transition.
- **No requirement was invalidated or re-scoped.** The delivered work stayed additive to the existing product boundary and did not remove or weaken previously validated capability claims.

## Deviations

No product-scope deviation blocked completion. Close-out verification did use the repository's actual integration branch (`origin/001-ai-practice-system`) instead of `main`, because this repo does not use `main` as the merge base. The roadmap also expressed acceptance through slice overview outcomes rather than a separate Success Criteria/Horizontal Checklist section, so milestone verification followed those shipped outcomes directly.

## Follow-ups

Next milestone work should start from the locked M022 boundaries: (1) if deeper sales methodology coverage is needed, extend the shared methodology contract instead of adding surface-local scoring; (2) if manager/admin tooling expands, reuse manager-lite/admin analytics/admin user detail as the truth seam rather than reviving fake homepage summaries; (3) enterprise work should begin with org/team/member compatibility readers, membership authz, and global-template-to-org rollout bindings inside the modular monolith before any service split or org-owned asset cloning.
