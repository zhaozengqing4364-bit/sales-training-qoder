---
id: S02
parent: M008
milestone: M008
provides:
  - Structured retrieval_facts payload available on both GET /api/v1/practice/sessions/{id}/knowledge-check and GET /api/v1/practice/sessions/{id}/report for completed sales sessions
  - Guaranteed parity: same session returns identical retrieval_facts through both routes
  - retrieval_facts includes: kb_binding status, latest_attempt with knowledge_base_ids and result_summaries, bounded recent_attempts, structured miss/failure explanations
requires:
  - slice: S01
    provides: Persisted voice_policy_snapshot.runtime_metrics.knowledge_retrieval ledger with bounded recent_attempts entries
affects:
  - S03
key_files:
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/conversation/session_evidence.py
  - backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
  - backend/tests/unit/test_session_evidence_service.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
key_decisions:
  - Single build_retrieval_facts() pure function as canonical normalizer for both report and knowledge-check routes (D120)
  - Copy-on-write projection overlay (sales-gated) for completed sessions; live sessions use live handler truth (D121)
  - Gated retrieval_facts on resolved_scenario_type==sales to avoid polluting presentation sessions which have a separate review path
  - Extracted _derive_retrieval_status_and_summary() to prevent vocabulary drift between build_retrieval_facts and build_session_runtime_diagnostics
  - Replicated bounds from stepfun_knowledge_helpers as module-level constants with source references
  - Contract tests assert exact structural parity while integration tests verify through real HTTP route handlers
patterns_established:
  - Pure normalizer → projection overlay → diagnostics passthrough: three-layer architecture for adding read-side facts without mutating persisted state
  - Sales-gated projection overlay: new evidence fields only attach to sales sessions, leaving presentation path untouched
  - Claim-truth independence: retrieval_facts and claim_truth are orthogonal surfaces tested explicitly at both contract and integration level
observability_surfaces:
  - practice_session_evidence_projection_built structured log now includes retrieval_facts_status field
drill_down_paths:
  - .gsd/milestones/M008/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M008/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M008/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M008/slices/S02/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-29T18:03:44.623Z
blocker_discovered: false
---

# S02: knowledge-check 与 report 共用检索真相

**Report and knowledge-check routes now return identical retrieval_facts for completed sales sessions through a shared build_retrieval_facts() normalizer wired as a projection-overlay seam**

## What Happened

S02 established a single-source-of-truth normalizer for retrieval facts and proved parity between the two canonical read surfaces.

**T01** created `build_retrieval_facts(voice_policy_snapshot)` in `runtime_diagnostics.py` — a pure function that reads from the persisted retrieval ledger (`voice_policy_snapshot.runtime_metrics.knowledge_retrieval`) and produces a structured `retrieval_facts` dict. This normalizer preserves `knowledge_base_ids` and `result_summaries` that the existing lean normalizer `_normalize_knowledge_retrieval_attempt` drops. A shared `_derive_retrieval_status_and_summary()` helper prevents status/summary vocabulary drift between the new function and the existing `build_session_runtime_diagnostics`. Bounds (MAX 10 entries, 8 KB IDs, 3 summaries, 240-char snippets) are replicated as module-level constants with source references. 17 new unit tests cover hit/miss/failure/empty/malformed/bounded/disabled/no-kb/not-ready scenarios.

**T02** wired the normalizer into `SessionEvidenceService.build_projection()` as a copy-on-write overlay gated on `resolved_scenario_type == "sales"`. This ensures completed sales sessions get `effectiveness_snapshot["retrieval_facts"]` derived from the persisted ledger without mutating the persisted `session.effectiveness_snapshot`. A `retrieval_facts_status` field was added to the structured log. 3 unit tests prove field appearance, non-mutation, and graceful skip.

**T03** extended `build_session_runtime_diagnostics()` to pass through `retrieval_facts` from the projection_effectiveness_snapshot when `live_runtime_active=False`. This means knowledge-check diagnostics for completed sessions reuse the exact same payload that the report route already computed. Live sessions always derive truth from the live handler. 4 unit tests prove reuse, live-session isolation, backward compatibility, and live-session projection ignore.

**T04** added contract and integration tests proving the parity guarantee. The same completed sales session returns structurally identical `retrieval_facts` through both report projection and knowledge-check diagnostics. Claim-truth independence is explicitly tested: retrieval status=hit with claim_truth=weak_evidence proves the fields are orthogonal. 5 tests (3 contract + 2 integration) all pass.

## Verification

All 4 task-level verification commands pass. Combined slice-level verification: 11 retrieval_facts-filtered tests across unit/contract/integration suites pass (0 failures). Full regression check: 34 unit tests + 26 contract/integration tests all pass. Key files verified: runtime_diagnostics.py (build_retrieval_facts + passthrough), session_evidence.py (sales-gated overlay), test_runtime_diagnostics_knowledge_retrieval.py (24 tests), test_session_evidence_service.py (10 tests), test_practice_evidence_contract.py (3 retrieval_facts tests), test_voice_runtime_session_snapshot.py (2 retrieval_facts tests).

## Requirements Advanced

- R010 — knowledge-check and report routes now share a single retrieval truth normalizer, so knowledge-backed sessions show consistent retrieval facts on both canonical surfaces
- R011 — retrieval_facts is persisted via projection overlay, making retrieval occurrence/hit-miss/failure explainable in report and replay contexts

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Live-session retrieval_facts is always None — live truth continues to come from the live handler, not from persisted projection. Presentation sessions do not get retrieval_facts (sales-gated). The retrieval_facts contract is limited to occurrence/hit-miss-failure/weak-evidence; it does not include `used_in_reasoning` (per D114/D116).

## Follow-ups

S03 will surface retrieval_facts in the report page UI. The frontend currently has no visibility into retrieval_facts — the data is available on both routes but not yet rendered.

## Files Created/Modified

- `backend/src/common/conversation/runtime_diagnostics.py` — Added build_retrieval_facts() pure normalizer with _normalize_retrieval_attempt_full() and _derive_retrieval_status_and_summary(); extended build_session_runtime_diagnostics() with retrieval_facts passthrough for completed sessions
- `backend/src/common/conversation/session_evidence.py` — Wired build_retrieval_facts() into build_projection() as sales-gated copy-on-write overlay with retrieval_facts_status structured log
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py` — 21 new unit tests: 17 for build_retrieval_facts (hit/miss/failure/empty/malformed/bounded/disabled/no-kb/not-ready) + 4 for diagnostics passthrough (reuse/live-session/backward-compat/ignore-projection)
- `backend/tests/unit/test_session_evidence_service.py` — 3 new unit tests for projection overlay: field appearance, non-mutation, graceful skip on missing voice_policy_snapshot
- `backend/tests/contract/test_practice_evidence_contract.py` — 3 contract tests: report/knowledge-check retrieval_facts parity, claim-truth independence (hit + weak_evidence), miss status parity
- `backend/tests/integration/test_voice_runtime_session_snapshot.py` — 2 integration tests: retrieval_facts parity through real HTTP handlers, claim-truth independence at integration level
