# S01: 后端结论证据合同与跨路由一致性

**Goal:** Build a shared conclusion-evidence builder that attaches provenance (retrieval/transcript/audio sources) to each canonical conclusion (main_issue, next_goal, claim_truth) and prove that one completed session produces identical evidence_references on report, replay, and knowledge-check routes.
**Demo:** After this: After this slice, contract tests prove one completed session produces the same evidence_references (retrieval/transcript/audio sources for main_issue/next_goal/claim_truth) on report, replay, and knowledge-check.

## Tasks
- [x] **T01: Added projection-backed conclusion provenance to completed-session report and replay responses.** — Implement `build_conclusion_evidence_bundle()` in `backend/src/common/conversation/session_evidence.py` that inspects a `SessionEvidenceProjection` and produces structured provenance for each canonical conclusion (main_issue, next_goal, claim_truth). Each conclusion gets an `evidence_sources` dict with `retrieval_source`, `transcript_source`, and `audio_source` entries that describe whether retrieval facts, transcript turns, or audio segments contributed to that conclusion.

Wire the bundle into `SessionEvidenceService.build_projection()` so it is always present on the projection. Update the report route (`/practice/sessions/{id}/report`) and replay route (`/sessions/{id}/replay`) to include the new `conclusion_evidence` field in their responses.

Update `SessionReport` schema and replay response dict to carry the new field. Ensure the field is additive and backward-compatible — existing consumers that don't read it are unaffected.

Add structured logging for when the bundle is built, including per-source availability flags.
  - Estimate: 2h
  - Files: backend/src/common/conversation/session_evidence.py, backend/src/common/conversation/replay.py, backend/src/common/db/schemas.py, backend/src/common/api/practice.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/unit/test_session_evidence_service.py -x -q
- [x] **T02: Mirrored projection-backed conclusion evidence into knowledge-check and added cross-route parity contracts.** — Wire the knowledge-check route (`/practice/sessions/{id}/knowledge-check`) to include `conclusion_evidence` from the projection snapshot. The knowledge-check already builds `projection_effectiveness_snapshot` for completed sales sessions — extract `conclusion_evidence` from it and surface it in the diagnostics response.

Update `build_session_runtime_diagnostics()` to accept and pass through `conclusion_evidence` from the projection snapshot.

Write focused contract tests in `backend/tests/contract/test_conclusion_evidence_parity.py` that:
1. Create one completed sales session with retrieval ledger, transcript turns, and audio segments.
2. Hit report, replay, and knowledge-check routes.
3. Assert all three return the same `conclusion_evidence` structure with identical source availability, hit counts, and turn references.
4. Assert degraded sessions (no retrieval, no audio) still produce consistent `conclusion_evidence` across all routes.
5. Assert the field is `null` for presentation scenarios (not in scope for M010).

Run the full existing contract test suite to verify backward compatibility.
  - Estimate: 1.5h
  - Files: backend/src/common/conversation/runtime_diagnostics.py, backend/src/common/api/practice.py, backend/tests/contract/test_conclusion_evidence_parity.py
  - Verify: cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_conclusion_evidence_parity.py tests/contract/test_practice_evidence_contract.py -x -q
