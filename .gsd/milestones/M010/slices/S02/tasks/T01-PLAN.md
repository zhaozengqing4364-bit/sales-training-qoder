---
estimated_steps: 7
estimated_files: 5
skills_used:
  - fastapi-python
  - pydantic
---

# T01: Build shared degradation taxonomy on projection and prove cross-route parity

**Slice:** S02 — 统一分层降级分类
**Milestone:** M010

## Description

Add `evidence_degradation` as a new additive computed field on `SessionEvidenceProjection`. The field carries four canonical layers — retrieval, transcript, audio, enhanced_report — each with a status (ok/degraded), canonical token, and compact explanation. Build it once inside `build_projection()`, wire it through report, replay, and knowledge-check routes, and extend the parity contract test to assert all three routes produce identical degradation payloads for multiple degradation scenarios.

## Steps

1. **Add `_build_evidence_degradation()` static method on `SessionEvidenceService`** in `backend/src/common/conversation/session_evidence.py`.
   - Signature: `_build_evidence_degradation(cls, *, session, messages, effectiveness_snapshot, voice_policy_snapshot, conclusion_evidence, scenario_type) -> dict[str, Any] | None`
   - Returns `None` for non-sales sessions (presentation stays `null`).
   - Four layers, each derived from existing signals:
     - **retrieval layer**: check `conclusion_evidence.*.retrieval_source.available` — if any conclusion has `available: False`, mark `retrieval_degraded` with token `no_retrieval_facts`. Use the reason from `retrieval_source.reason` for the explanation.
     - **transcript layer**: check `conclusion_evidence.*.transcript_source.available` — if any conclusion has `available: False`, mark `transcript_degraded` with token `no_scored_turns`.
     - **audio layer**: check `conclusion_evidence.*.audio_source.available` — if any conclusion has `available: False`, mark `audio_degraded` with token from `audio_source.reason` (e.g. `no_audio_segments`, `no_voice_policy_snapshot`).
     - **enhanced_report layer**: check `session.report_status` — if `"failed"`, mark `enhanced_report_degraded` with token `report_generation_failed`; if `None` or `"completed"`, mark ok. Use `session.report_error` for explanation if available.
   - Shape per layer:
     ```python
     {
         "status": "ok" | "degraded",
         "token": "retrieval_ok" | "retrieval_degraded" | ...,  # canonical token
         "explanation": "..." | None,  # human-readable reason, None when ok
     }
     ```
   - Return dict with four keys: `retrieval`, `transcript`, `audio`, `enhanced_report`.

2. **Wire `evidence_degradation` into `build_projection()`** in the same file.
   - Call `_build_evidence_degradation(...)` after `conclusion_evidence` is built (it depends on the conclusion bundle).
   - Add `evidence_degradation=evidence_degradation` to the `SessionEvidenceProjection` return.
   - Add a structured log `projection_evidence_degradation_built` with per-layer status flags.
   - Note: `SessionEvidenceProjection` is a NamedTuple/dataclass — add the field there too. Check the class definition in the same file or its import location.

3. **Pass `evidence_degradation` through knowledge-check** in `backend/src/common/conversation/runtime_diagnostics.py`.
   - Add parameter `evidence_degradation: dict[str, Any] | None = None` to `build_session_runtime_diagnostics()`.
   - Add `"evidence_degradation": evidence_degradation` to the returned dict.
   - For live sessions (`live_runtime_active=True`), pass `None` — degradation taxonomy is for completed sessions only.

4. **Wire into report route** in `backend/src/common/api/practice.py`.
   - After `conclusion_evidence` is wired (~line 1606), also include `evidence_degradation=projection.evidence_degradation` (or `None` for presentation sessions, matching the conclusion_evidence pattern).

5. **Wire into replay route** in `backend/src/common/conversation/replay.py`.
   - Include `evidence_degradation` from the projection in the replay response payload alongside `evidence_completeness`, `conclusion_evidence`, etc.

6. **Extend parity contract tests** in `backend/tests/contract/test_conclusion_evidence_parity.py`.
   - Add helper `_extract_evidence_degradation(data)` that safely extracts `evidence_degradation` from route response data.
   - Add test `test_report_replay_and_knowledge_check_share_same_evidence_degradation_for_happy_path_sales_session`:
     - Seeds a session with retrieval hit + audio segments (existing happy-path fixture).
     - Asserts all three routes return identical `evidence_degradation` with all four layers `status: "ok"`.
   - Add test `test_report_replay_and_knowledge_check_share_same_evidence_degradation_when_retrieval_missing`:
     - Seeds session without retrieval (existing `include_retrieval_hit=False` fixture).
     - Asserts retrieval layer is `degraded` with token `no_retrieval_facts`, others ok.
   - Add test `test_report_replay_and_knowledge_check_share_same_evidence_degradation_when_audio_missing`:
     - Seeds session without audio segments (existing `include_audio_segments=False` fixture).
     - Asserts audio layer is `degraded` with token `no_audio_segments`, others ok.
   - Add test `test_evidence_degradation_null_for_presentation_sessions`:
     - Seeds a presentation session (existing fixture).
     - Asserts `evidence_degradation is None` on all three routes.
   - Add test `test_evidence_degradation_marks_enhanced_report_degraded_when_report_failed`:
     - Seeds a sales session with `report_status="failed"`, `report_error="REPORT_GENERATION_FAILED"`.
     - Asserts enhanced_report layer is `degraded` with token `report_generation_failed`.

7. **Add unit tests** in `backend/tests/unit/test_session_evidence_service.py` (if file exists) or inline in the parity test.
   - Test the builder directly: verify each layer's derivation from conclusion_evidence signals and session state.
   - Test that the builder returns `None` for presentation scenario_type.

## Must-Haves

- [ ] `evidence_degradation` field on projection with four canonical layers (retrieval, transcript, audio, enhanced_report)
- [ ] Report, replay, and knowledge-check all expose identical `evidence_degradation` for the same completed sales session
- [ ] Parity contract tests cover happy-path, retrieval-missing, audio-missing, enhanced-report-failed, and presentation scenarios
- [ ] Structured log `projection_evidence_degradation_built` emitted per projection build
- [ ] `evidence_degradation` is `null` for presentation sessions

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q`
- All existing parity tests continue to pass (no regression from S01)
- New degradation parity tests pass with assertions on all four layers across all three routes

## Observability Impact

- Signals added: `projection_evidence_degradation_built` structured log with `retrieval_status`, `transcript_status`, `audio_status`, `enhanced_report_status` flags
- How a future agent inspects: grep for `projection_evidence_degradation_built` in backend logs to see per-layer degradation state per projection build
- Failure state exposed: degraded layer tokens explicitly name which evidence source is missing and why

## Inputs

- `backend/src/common/conversation/session_evidence.py` — projection builder with S01's `build_conclusion_evidence_bundle()` and `_build_evidence_completeness()`
- `backend/src/common/conversation/runtime_diagnostics.py` — knowledge-check mirror seam accepting `conclusion_evidence`
- `backend/src/common/api/practice.py` — report route wiring for projection fields
- `backend/src/common/conversation/replay.py` — replay response payload construction
- `backend/tests/contract/test_conclusion_evidence_parity.py` — existing parity test fixtures and `_fetch_route_family()` helper

## Expected Output

- `backend/src/common/conversation/session_evidence.py` — new `_build_evidence_degradation()` method and `evidence_degradation` field on projection
- `backend/src/common/conversation/runtime_diagnostics.py` — `evidence_degradation` parameter passthrough in `build_session_runtime_diagnostics()`
- `backend/src/common/api/practice.py` — `evidence_degradation` wired into report response
- `backend/src/common/conversation/replay.py` — `evidence_degradation` wired into replay response
- `backend/tests/contract/test_conclusion_evidence_parity.py` — new parity tests for degradation taxonomy
