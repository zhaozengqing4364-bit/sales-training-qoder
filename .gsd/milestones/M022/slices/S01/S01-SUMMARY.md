---
id: S01
parent: M022
milestone: M022
provides:
  - One code-owned sales methodology/rubric contract reusable by S02 persona/scenario/industry-pack work and S03 manager/admin truth surfaces.
  - One shared transition payload (`sales_methodology_rubric_v1`) so current sales consumers can adopt methodology semantics without breaking existing report/realtime/read-side contracts.
  - One boundary-honest learner/manager explanation seam that states what the first round does cover and what it still does not claim.
requires:
  - slice: S01
    provides: This slice establishes the methodology authority seam consumed by later M022 slices.
affects:
  - S02
  - S03
  - S04
key_files:
  - backend/src/common/effectiveness/methodology.py
  - backend/src/common/effectiveness/canonical.py
  - backend/src/agent/capabilities/realtime_scoring.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/services/practice_session_service.py
  - backend/src/common/api/practice.py
  - docs/api-contract/effectiveness.md
  - docs/api-contract/README.md
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - Keep methodology-aware sales rubric semantics additive to the canonical kernel and compatibility readers instead of replacing the shipped score schema.
  - Expose shared methodology status through `canonical_evaluation_kernel.methodology` and mirror it through `compatibility_readers.sales_methodology_rubric_v1` for transition consumers.
  - Keep the existing learner report headline stable and surface the new methodology language in a dedicated rubric explainer card.
patterns_established:
  - Introduce new sales semantics as additive canonical-kernel metadata plus compatibility readers, not as a second top-level score schema.
  - Derive methodology status once in shared backend effectiveness code so realtime, report, replay, history, and admin surfaces cannot drift independently.
  - Keep outward learner/manager language boundary-honest: if runtime stage support is missing, document that limit explicitly instead of inflating copy.
observability_surfaces:
  - `canonical_evaluation_kernel.methodology` is now the primary cross-surface health signal for sales methodology parity.
  - `compatibility_readers.sales_methodology_rubric_v1` is the transition reader that should stay identical to the canonical methodology summary until compat retirement.
  - The learner report rubric explainer and docs/api-contract/effectiveness.md are the outward explanation surfaces that should stay aligned with the backend contract.
drill_down_paths:
  - .gsd/milestones/M022/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M022/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M022/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-14T05:43:17.667Z
blocker_discovered: false
---

# S01: Methodology-aware sales rubric 收口

**Shipped the first methodology-aware sales rubric contract and wired the same rubric semantics through realtime, projection-backed read surfaces, and learner-facing report explanations.**

## What Happened

S01 turned M022’s methodology idea into a real shared contract instead of planner prose. T01 introduced `backend/src/common/effectiveness/methodology.py` as the code-owned authority for five first-round sales rubrics — `discovery_qualification`, `value_story`, `evidence_proof`, `objection_reframe`, and `next_step_commitment` — and tied each rubric to existing canonical dimensions, current `sales_stage` coverage, `main_issue` / `next_goal` families, and shipped evidence paths. T02 then wired that contract into the canonical evaluation builder so sales realtime snapshots, completed-session projection/read-side consumers, and transition readers all consume the same methodology summary through `canonical_evaluation_kernel.methodology` and `compatibility_readers.sales_methodology_rubric_v1` instead of inventing per-surface rubric logic. T03 wrote the same semantics back into docs and the learner report page: the report now explains the five rubric lenses in-product, while docs/api-contract and the architecture scan explicitly state the current first-round boundary that qualification still lives inside `opening + discovery` until the runtime stage contract changes.

This slice establishes a reusable pattern for the remaining milestone: add new sales semantics additively on top of the canonical kernel plus compatibility readers, keep learner/admin/read-side contracts stable, and make the outward language boundary-honest. The immediate downstream value is that S02 persona/scenario/industry-pack work and S03 manager/admin truth-surface work can now reuse one explicit definition of what “good sales behavior” means, rather than translating discovery/value/evidence/objection/next-step differently in each subsystem.

Operational readiness for this runtime-adjacent slice is simple but important: the health signal is cross-surface parity of the methodology block on sales realtime/report/replay/history/admin payloads; the failure signal is any surface missing the methodology payload or disagreeing on rubric status while still showing canonical scores; the recovery path is to route the consumer back to `common.effectiveness.methodology` + the shared canonical builder and rerun the focused backend parity bundle plus the learner report test; the current monitoring gap is that there is still no dedicated admin truth panel that compares methodology parity across surfaces automatically, so the proof remains test- and contract-led.

## Verification

Fresh slice-close verification passed on every planned gate. `rg -n "sales_stage|realtime_scoring|effectiveness|main_issue|next_goal|dimension_scores" backend/src/common backend/src/agent docs/api-contract` exited 0 and confirmed the methodology contract is discoverable on the existing effectiveness/realtime/report authority seams. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "sales and (report or replay or history or analytics)" -x -q` passed with 24 selected tests green (plus 1 skipped), proving the shared sales report/replay/history/analytics bundle still aligns after the methodology wiring. `rg -n "qualification|discovery|value|objection|next-step|rubric" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md 'web/src/app/(user)/practice/[sessionId]/report/page.tsx'` exited 0 and confirmed the outward rubric language exists in docs, architecture inventory, and the learner report page. As an extra learner-surface guard, `npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` passed 24/24 tests, confirming the shared report UI still renders correctly after the rubric explainer addition.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Two deliberate boundary-preserving deviations were kept. First, qualification remains merged into `opening + discovery` because the shipped `sales_stage` runtime still has no standalone qualification stage. Second, the learner report kept its existing top-line summary copy and introduced methodology language through a dedicated explainer card, which made the new contract visible without destabilizing the existing report summary contract.

## Known Limitations

This is only the first-round methodology contract. It does not yet claim full sales-methodology coverage, it does not add a standalone qualification stage, and there is not yet a dedicated manager/admin UI that audits methodology parity visually across surfaces. Transition consumers may still read the mirrored compatibility reader while downstream slices complete the broader productization work.

## Follow-ups

S02 should bind persona/scenario/customer-pressure/industry-pack assets to this shared methodology contract instead of creating pack-local scoring language. S03 should use the same contract to make manager/admin truth surfaces evidence-backed and remove remaining demo/drift explanations. A later slice can only introduce a standalone qualification stage after the underlying `sales_stage` runtime contract changes as well.

## Files Created/Modified

- `backend/src/common/effectiveness/methodology.py` — Added the first-round code-owned sales methodology contract and shared rubric summary builder.
- `backend/src/common/effectiveness/canonical.py` — Attached methodology summaries to the canonical evaluation kernel and compatibility readers for sales surfaces.
- `backend/src/agent/capabilities/realtime_scoring.py` — Passed stage context into the shared methodology/canonical builder so live score snapshots expose the same rubric semantics.
- `backend/src/common/conversation/session_evidence.py` — Rebuilt completed-session sales methodology context from shared aligned evidence so report/replay/history/admin consumers stay consistent.
- `backend/src/common/services/practice_session_service.py` — Threaded stage-aware realtime snapshot context into persisted session evidence compatibility paths.
- `backend/src/common/api/practice.py` — Kept sales read-side/practice compatibility routes aligned with the shared methodology-aware effectiveness helpers.
- `docs/api-contract/effectiveness.md` — Documented the first-round methodology/rubric contract, learner-facing interpretation rules, and boundary-honest qualification behavior.
- `docs/api-contract/README.md` — Surfaced the methodology contract as a first-round API-contract concern and linked the new documentation.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Added a learner-visible rubric explainer card that exposes the five first-round methodology lenses and their current boundary.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Recorded the methodology authority line and downstream reuse rule for the rest of M022.
- `.gsd/KNOWLEDGE.md` — Captured the qualification-stage gotcha and the canonical methodology consumption seam for future slices.
- `.gsd/PROJECT.md` — Refreshed project state to record M022/S01 as complete and to describe the new methodology authority seam.
