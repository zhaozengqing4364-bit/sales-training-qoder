---
id: S01
parent: M010
milestone: M010
provides:
  - conclusion_evidence field on SessionEvidenceProjection with per-conclusion provenance (retrieval/transcript/audio sources)
  - Cross-route parity: report, replay, knowledge-check all read from the same projection-backed bundle
  - Dedicated parity contract tests asserting identical evidence across all three routes
requires:
  []
affects:
  - S02
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/schemas.py
  - backend/src/common/db/schemas.py
  - backend/src/common/api/practice.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/tests/contract/test_conclusion_evidence_parity.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/unit/test_session_evidence_service.py
key_decisions:
  - Built conclusion_evidence inside SessionEvidenceService.build_projection() so report and replay share one provenance bundle — no route-local provenance logic.
  - Kept the field additive and null for presentation sessions to preserve backward compatibility.
  - Knowledge-check reads conclusion_evidence from the already-built projection snapshot instead of rebuilding — follows the same mirror pattern used for retrieval_facts.
  - Locked cross-route parity with a dedicated contract module that compares report, replay, and knowledge-check directly for sales happy-path, degraded, and presentation sessions.
patterns_established:
  - Projection-as-single-truth-source: build provenance once on the projection, mirror to diagnostics/routes. Future cross-route fields should follow this pattern.
  - Dedicated parity contract module: test_conclusion_evidence_parity.py seeds sessions once and asserts all routes agree. S02's degradation taxonomy tests should extend this module.
observability_surfaces:
  - projection_conclusion_evidence_built structured log with retrieval_available, transcript_available, audio_available flags per projection build
drill_down_paths:
  - .gsd/milestones/M010/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M010/slices/S01/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-30T02:04:49.521Z
blocker_discovered: false
---

# S01: 后端结论证据合同与跨路由一致性

**Built shared conclusion-evidence provenance on SessionEvidenceService.build_projection() and proved report, replay, and knowledge-check produce identical evidence_references for each canonical conclusion.**

## What Happened

T01 implemented `build_conclusion_evidence_bundle()` as a static method on `SessionEvidenceService`, called inside `build_projection()` so the provenance bundle is always available on the projection. Each canonical conclusion (main_issue, next_goal, claim_truth) gets an `evidence_sources` dict with `retrieval_source`, `transcript_source`, and `audio_source` entries describing whether retrieval facts, transcript turns, or audio segments contributed. The report and replay routes were wired to include the new `conclusion_evidence` field; the field is additive and `null` for presentation sessions. Structured logging with per-source availability flags was added. 37 focused tests passed.

T02 extended the knowledge-check route to extract `conclusion_evidence` from the already-built projection snapshot and thread it through `build_session_runtime_diagnostics()`, avoiding a second provenance build. A dedicated parity contract module (`test_conclusion_evidence_parity.py`) seeds completed sales sessions and asserts report, replay, and knowledge-check return identical evidence structures for happy-path, degraded (no retrieval, no audio), and presentation sessions. The degraded fixture was tightened to truly exercise the no-audio path. 29 targeted tests and 83 full contract tests passed.

## Verification

Slice-level verification ran the combined contract and unit test suite: `backend/venv/bin/python -m pytest -c backend/pyproject.toml tests/contract/test_conclusion_evidence_parity.py tests/contract/test_practice_evidence_contract.py tests/unit/test_session_evidence_service.py -x -q` → 40 passed. Full backward-compatibility sweep: `backend/venv/bin/python -m pytest -c backend/pyproject.toml tests/contract -x -q` → 83 passed, 0 failures.

## Requirements Advanced

- R027 — Validated: conclusion provenance (retrieval/transcript/audio sources for main_issue, next_goal, claim_truth) now attached to all three completed-session routes with contract-enforced parity.

## Requirements Validated

- R027 — 40 focused tests + 83 full contract tests pass. Parity contract asserts identical conclusion_evidence structure across report, replay, knowledge-check for happy-path, degraded, and presentation sessions.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Conclusion evidence is `null` for presentation sessions — presentation scenario provenance is out of scope for M010.

## Follow-ups

None.

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py` — Added build_conclusion_evidence_bundle() static method and wired it into build_projection(); emits projection_conclusion_evidence_built log.
- `backend/src/common/conversation/replay.py` — Included conclusion_evidence from projection in replay response payload.
- `backend/src/common/conversation/schemas.py` — Added ConclusionEvidenceSource and ConclusionEvidenceBundle schema classes.
- `backend/src/common/db/schemas.py` — Added conclusion_evidence field to SessionReport schema.
- `backend/src/common/api/practice.py` — Wired conclusion_evidence into report route response; extracted from projection for knowledge-check and passed to build_session_runtime_diagnostics().
- `backend/src/common/conversation/runtime_diagnostics.py` — Updated build_session_runtime_diagnostics() to accept and pass through conclusion_evidence.
- `backend/tests/contract/test_conclusion_evidence_parity.py` — New parity contract: seeds completed sessions and asserts report/replay/knowledge-check produce identical conclusion_evidence across happy-path, degraded, and presentation scenarios.
- `backend/tests/contract/test_practice_evidence_contract.py` — Extended existing evidence contract tests to cover conclusion_evidence on report and replay.
- `backend/tests/unit/test_session_evidence_service.py` — Added unit tests for build_conclusion_evidence_bundle() covering retrieval/transcript/audio availability permutations.
