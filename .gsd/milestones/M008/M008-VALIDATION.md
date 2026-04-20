---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M008

## Success Criteria Checklist
## Success criteria checklist

_Roadmap note: `M008-ROADMAP.md` has no explicit `Success Criteria` block, so validation reconciles against the vision, slice demo claims, and planned verification classes._

- [x] **Persisted retrieval ledger can answer whether retrieval happened, what was queried, what came back, and why it missed or failed.**
  - Evidence: S01 summary documents provider-neutral `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts`, backward-compatible flat metrics, and diagnostics fallback.
  - Evidence: S01 UAT covers hit, miss, failure/no-op paths, copy-on-write persistence, and route-level frozen-ref proof.
  - Evidence: recorded verify artifacts under `.gsd/milestones/M008/slices/S01/tasks/` show exit code 0 / verdict `pass`.

- [x] **The same completed sales session exposes matching retrieval truth on both canonical read surfaces: `/api/v1/practice/sessions/{id}/knowledge-check` and `/api/v1/practice/sessions/{id}/report`.**
  - Evidence: S02 summary documents shared `build_retrieval_facts()` normalizer, sales-gated projection overlay, and diagnostics passthrough.
  - Evidence: S02 contract + integration coverage explicitly asserts structural parity and claim-truth independence.
  - Evidence: recorded verify artifacts under `.gsd/milestones/M008/slices/S02/tasks/` show exit code 0 / verdict `pass`.

- [x] **Learner report page renders retrieval truth from the canonical report payload, including KB binding and hit/miss/failure/weak-evidence explanations, while keeping PPT reports clean.**
  - Evidence: S03 summary documents report-page rendering from `effectiveness_snapshot.retrieval_facts`, shared formatting helpers, PPT suppression, and weak-evidence coexistence.
  - Evidence: S03 focused Vitest suite passed 17/17 and covers hit, miss, `search_failed`, absent/malformed data, and PPT suppression.
  - Evidence: recorded verify artifacts under `.gsd/milestones/M008/slices/S03/tasks/` show exit code 0 / verdict `pass`.

- [ ] **Fresh learner-facing browser/UAT evidence for the shipped `/practice/{sessionId}/report` experience was captured.**
  - Gap: S03 includes a solid UAT script, but validation found no M008 browser artifact or recorded live execution evidence beyond the focused Vitest suite.
  - Impact: minor. The UI behavior is strongly covered by tests, but the planned UAT class was not retired with a concrete runtime proof artifact.

## Slice Delivery Audit
## Slice delivery audit

| Slice | Planned deliverable | Evidence found | Audit |
|---|---|---|---|
| S01 | Persist retrieval ledger in session snapshot so the same session can answer whether retrieval occurred, what it queried, result count, and miss/failure cause. | S01 summary shows bounded `recent_attempts` persistence, flat-field compatibility, and diagnostics fallback; S01 UAT covers normalization, persistence, fallback, integration, and contract proof. | **Delivered** |
| S02 | Make `/knowledge-check` and canonical `/report` return the same retrieval truth for the same completed session. | S02 summary shows shared `build_retrieval_facts()` seam and projection overlay; contract/integration tests explicitly assert parity and claim-truth independence. | **Delivered** |
| S03 | Show KB binding and retrieval hit/miss/failure/weak-evidence explanations on the learner report page. | S03 summary shows report-page rendering from canonical `retrieval_facts`; focused Vitest proves hit/miss/failure/absence/malformed/PPT cases. | **Delivered, with attention note:** live browser/UAT execution evidence was not captured in milestone artifacts. |

## Verification class audit

| Class | Planned requirement | Evidence | Status |
|---|---|---|---|
| Contract | Runtime-metrics seam, `SessionEvidenceService`, and practice evidence contract prove matching retrieval facts across canonical surfaces. | S01 contract proof for snapshot-ref stability; S02 contract tests for report/knowledge-check parity and claim-truth independence. | **Addressed** |
| Integration | Real FastAPI route family proves the same session exposes the same retrieval ledger summary and degradation classification. | S02 integration tests on real HTTP handlers; S01 integration tests on current session/detail surfaces. | **Addressed** |
| Operational | Not-triggered, miss, retrieval failure, and hit-but-weak remain visible instead of collapsing into abstract support. | S02 unit coverage for disabled/no-kb/not-ready/empty/miss/failure/hit; S03 report-page tests for miss/search_failed/weak-evidence/absence. | **Addressed** |
| UAT | Learner can see KB binding, retrieval occurrence, and concrete hit/miss/failure explanation on `/practice/{sessionId}/report`. | S03 UAT script defines the flow, but validation found no recorded browser/runtime proof artifact for M008. | **Needs attention** |

## Deferred work inventory

- Capture one fresh browser/UAT artifact against the running `/practice/{sessionId}/report` flow for a sales session with `retrieval_facts` present (and ideally one PPT suppression check) if the milestone is reopened or if a close-out evidence bundle is required.

## Cross-Slice Integration
## Cross-slice integration

- **S01 → S02:** aligned.
  - Planned handoff: persisted `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts` becomes the read-side source for canonical retrieval truth.
  - Delivered: S02 consumes that exact ledger via `build_retrieval_facts()` and overlays `effectiveness_snapshot.retrieval_facts` without mutating persisted state.

- **S02 → S03:** aligned.
  - Planned handoff: canonical report payload exposes `effectiveness_snapshot.retrieval_facts` for learner-facing rendering.
  - Delivered: S03 reads the report payload directly, renders retrieval truth from `effectiveness_snapshot.retrieval_facts`, and keeps `/knowledge-check` supplemental-only.

- **Scenario gating:** aligned.
  - S02 sales-gates `retrieval_facts` to avoid polluting presentation sessions.
  - S03 mirrors that boundary by suppressing the retrieval section for PPT reports and asserting `/knowledge-check` is not called.

- **Vocabulary / explanation consistency:** aligned.
  - S02 centralizes retrieval status and explanation derivation in shared backend normalizers.
  - S03 consumes canonical payload semantics rather than inventing a second retrieval truth source.

## Boundary mismatches

No material slice-boundary mismatch found. The only unresolved integration-adjacent gap is evidence depth: the learner-facing UAT class lacks a recorded live browser proof artifact even though the backend and frontend seams themselves line up.

## Requirement Coverage
## Requirement coverage

| Requirement | Milestone contribution | Coverage assessment |
|---|---|---|
| R010 — existing admin Persona/knowledge → practice → runtime retrieval → knowledge-check/report/replay chain must sustain real knowledge-backed sales questioning. | S01 persisted auditable retrieval ledger state; S02 made report and knowledge-check share the same retrieval truth normalizer on canonical routes. | **Covered / advanced.** M008 strengthens the already-validated chain by making retrieval behavior inspectable and consistent across canonical read surfaces. |
| R011 — session content/evidence must remain retrievable, replayable, and explainable. | S01 adds persisted retrieval ledger entries; S02 overlays explainable `retrieval_facts`; S03 exposes retrieval truth to the learner on the report page. | **Covered / advanced.** M008 extends session explainability without changing requirement status. |
| R005 — learner report should be structured, concrete, and grounded in real session facts. | S03 surfaces retrieval hit/miss/failure/weak-evidence context directly on the report page. | **Strengthened incidentally.** Helpful evidence improvement, but not part of the milestone’s explicitly listed requirement transitions in this validation unit. |

No scoped requirement appears uncovered. No requirement status transition is needed from this validation pass; the milestone advances already-validated requirements rather than establishing first-time validation.


## Verdict Rationale
M008 delivered the planned retrieval-truth seam end to end: S01 persisted a bounded retrieval ledger with flat-field compatibility, S02 established canonical report/knowledge-check parity through a shared normalizer and projection overlay, and S03 exposed that canonical truth on the learner report page while preserving PPT gating. Contract, integration, and operational verification classes are all substantively addressed by recorded passing evidence. The remaining gap is narrower: the planned learner-facing UAT class is represented by a test script and strong focused Vitest coverage, but validation found no recorded live browser/runtime proof artifact for M008. That is a real evidence gap, but it is not large enough to justify remediation slices because the delivered seams and automated verification are coherent and complete.
