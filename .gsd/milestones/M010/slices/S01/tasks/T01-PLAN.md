---
estimated_steps: 4
estimated_files: 4
skills_used: []
---

# T01: Build shared conclusion-evidence bundle and wire into projection-backed routes

Implement `build_conclusion_evidence_bundle()` in `backend/src/common/conversation/session_evidence.py` that inspects a `SessionEvidenceProjection` and produces structured provenance for each canonical conclusion (main_issue, next_goal, claim_truth). Each conclusion gets an `evidence_sources` dict with `retrieval_source`, `transcript_source`, and `audio_source` entries that describe whether retrieval facts, transcript turns, or audio segments contributed to that conclusion.

Wire the bundle into `SessionEvidenceService.build_projection()` so it is always present on the projection. Update the report route (`/practice/sessions/{id}/report`) and replay route (`/sessions/{id}/replay`) to include the new `conclusion_evidence` field in their responses.

Update `SessionReport` schema and replay response dict to carry the new field. Ensure the field is additive and backward-compatible — existing consumers that don't read it are unaffected.

Add structured logging for when the bundle is built, including per-source availability flags.

## Inputs

- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/db/schemas.py`
- `backend/src/common/api/practice.py`

## Expected Output

- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/replay.py`
- `backend/src/common/db/schemas.py`
- `backend/src/common/api/practice.py`

## Verification

cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/unit/test_session_evidence_service.py -x -q

## Observability Impact

Signals added: `projection_conclusion_evidence_built` log with retrieval_available / transcript_available / audio_available flags. How a future agent inspects: read the `conclusion_evidence` field from any report/replay JSON response. Failure state exposed: individual source entries show `available: false` with reason when evidence layer is absent.
