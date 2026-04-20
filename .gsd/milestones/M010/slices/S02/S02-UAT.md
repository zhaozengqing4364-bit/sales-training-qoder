# S02: 统一分层降级分类 — UAT

**Milestone:** M010
**Written:** 2026-03-30T04:02:17.445Z

# S02: 统一分层降级分类 — UAT

**Milestone:** M010
**Written:** 2026-03-30

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S02 ships a backend contract and shared API typing change, not a new learner-facing UI. The acceptance question is whether completed-session report, replay, and knowledge-check surfaces return the same layered degradation payload for the supported evidence-loss scenarios while preserving compatibility consumers.

## Preconditions

- Backend test database and fixtures are runnable from repo root.
- Python virtualenv exists at `backend/venv`.
- The branch includes the S02 backend and type-contract changes.
- No local code changes are pending after verification commands are started.

## Smoke Test

Run:

`backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py -x -q`

**Expected:** The parity contract passes and proves report, replay, and knowledge-check agree on both `conclusion_evidence` and `evidence_degradation` for the seeded route-family scenarios.

## Test Cases

### 1. Happy-path completed sales session returns all four layers as OK on all three routes

1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py -k happy_path_sales_session -x -q`
2. Confirm the seeded sales session includes retrieval hits and audio segments.
3. **Expected:** Report, replay, and knowledge-check all return identical `evidence_degradation` with:
   - `retrieval.status = ok`, `token = retrieval_ok`
   - `transcript.status = ok`, `token = transcript_ok`
   - `audio.status = ok`, `token = audio_ok`
   - `enhanced_report.status = ok`, `token = enhanced_report_ok`

### 2. Retrieval-missing session degrades only the retrieval layer with a concrete explanation

1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py -k retrieval_missing -x -q`
2. Inspect the expected payload in the test fixture.
3. **Expected:** Report, replay, and knowledge-check all return identical `evidence_degradation` where only `retrieval` is degraded, `token = no_retrieval_facts`, and `explanation = no_voice_policy_snapshot`; transcript, audio, and enhanced_report remain `ok`.

### 3. Audio-missing session degrades only the audio layer

1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py -k audio_missing -x -q`
2. Confirm the seeded session clears audio-bearing message duration evidence and segment rows.
3. **Expected:** Report, replay, and knowledge-check all return identical `evidence_degradation` where only `audio` is degraded, `token = no_audio_segments`, and `explanation = no_audio_segments`.

### 4. Enhanced-report failure remains explicit instead of pretending the evidence chain is complete

1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py -k enhanced_report_degraded -x -q`
2. Confirm the seeded session uses `report_status="failed"` and `report_error="REPORT_GENERATION_FAILED"`.
3. **Expected:** Report, replay, and knowledge-check all return identical `evidence_degradation` where only `enhanced_report` is degraded, `token = report_generation_failed`, and `explanation = REPORT_GENERATION_FAILED`.

### 5. Presentation sessions stay out of scope and must keep the taxonomy null

1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py -k presentation -x -q`
2. Inspect both the conclusion-evidence and degradation assertions.
3. **Expected:** Presentation report, replay, and knowledge-check payloads all return `evidence_degradation = null` and do not silently reuse the sales taxonomy.

### 6. Compatibility readers still see canonical degraded reasons after the taxonomy lands

1. Run:
   `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q`
2. Review the admin analytics degraded-reason distribution assertions.
3. **Expected:** Admin analytics and history projection tests pass using canonical mirrored tokens such as `no_retrieval_facts`, `no_scored_turns`, and `no_audio_segments`, proving the old compatibility read surface still works.

## Edge Cases

### Replay serialization seam

1. Remove or comment the `evidence_degradation` field declaration from `backend/src/common/conversation/schemas.py` in a local scratch check.
2. Re-run the parity contract.
3. **Expected:** Replay parity fails even if the replay service still adds the field to its payload dict; this confirms the schema layer is a real part of the contract and must stay in sync.

### Live runtime knowledge-check bypass

1. Inspect `backend/src/common/api/practice.py` and `backend/src/common/conversation/runtime_diagnostics.py` for the `live_runtime_active` branch.
2. **Expected:** When the session is still live, knowledge-check does not claim completed-session `evidence_degradation`; it only mirrors the projection-backed taxonomy when the session is completed and the projection is authoritative.

## Failure Signals

- Report, replay, and knowledge-check disagree on the `evidence_degradation` payload for the same seeded session.
- Replay returns `null`/missing `evidence_degradation` while report and knowledge-check still return a populated payload.
- Admin analytics or history tests fall back to older `message_scores` / `stage_evidence` degraded reasons instead of canonical taxonomy tokens.
- Presentation sessions unexpectedly receive a non-null sales degradation payload.
- A repo-wide TypeScript run reports new errors in `web/src/lib/api/types.ts` attributable to `EvidenceDegradation` additions rather than the known unrelated baseline failures.

## Requirements Proved By This UAT

- R028 — Proves the system now surfaces explicit layered degradation reasons for retrieval, transcript, audio, and enhanced-report gaps on the existing report/replay/knowledge-check route family without silent drift.

## Not Proven By This UAT

- Learner-facing report/replay UI rendering of the layered taxonomy; that is the follow-on responsibility of M010/S03.
- Presentation-specific degradation taxonomy beyond the explicit `null` out-of-scope behavior.
- Repo-wide frontend type health; `npx tsc --noEmit` still has unrelated pre-existing failures outside this slice.

## Notes for Tester

Treat the parity contract as the highest-authority proof surface for S02. If route outputs diverge, check `SessionEvidenceService.build_projection()` first, then `backend/src/common/conversation/schemas.py` for replay serialization, and only then inspect route handlers. Do not infer regression from page copy or optional enhanced-report noise for this slice; S02 is about the backend degradation contract, not user-facing rendering.
