---
estimated_steps: 9
estimated_files: 3
skills_used: []
---

# T02: Mirror conclusion evidence into knowledge-check and write cross-route parity contract tests

Wire the knowledge-check route (`/practice/sessions/{id}/knowledge-check`) to include `conclusion_evidence` from the projection snapshot. The knowledge-check already builds `projection_effectiveness_snapshot` for completed sales sessions — extract `conclusion_evidence` from it and surface it in the diagnostics response.

Update `build_session_runtime_diagnostics()` to accept and pass through `conclusion_evidence` from the projection snapshot.

Write focused contract tests in `backend/tests/contract/test_conclusion_evidence_parity.py` that:
1. Create one completed sales session with retrieval ledger, transcript turns, and audio segments.
2. Hit report, replay, and knowledge-check routes.
3. Assert all three return the same `conclusion_evidence` structure with identical source availability, hit counts, and turn references.
4. Assert degraded sessions (no retrieval, no audio) still produce consistent `conclusion_evidence` across all routes.
5. Assert the field is `null` for presentation scenarios (not in scope for M010).

Run the full existing contract test suite to verify backward compatibility.

## Inputs

- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/tests/contract/test_practice_evidence_contract.py`

## Expected Output

- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/tests/contract/test_conclusion_evidence_parity.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_conclusion_evidence_parity.py tests/contract/test_practice_evidence_contract.py -x -q

## Observability Impact

How a future agent inspects: call GET /api/v1/practice/sessions/{id}/knowledge-check and check `conclusion_evidence` field matches report/replay. Failure state exposed: parity test explicitly compares all three routes and reports which field diverged.
