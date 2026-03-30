---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: Added projection-level evidence_degradation and partial route wiring, but replay parity is still blocked by the replay response schema dropping the new field.

Add `evidence_degradation` as a new computed field on SessionEvidenceProjection, built from existing S01 provenance signals and session state. The field carries four canonical layers (retrieval, transcript, audio, enhanced_report) with status/token/explanation per layer. Wire it through report, replay, and knowledge-check routes. Extend the parity contract test to assert identical degradation payloads across all three routes for happy-path, retrieval-missing, audio-missing, and enhanced-report-failed scenarios.

## Inputs

- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/replay.py`
- `backend/tests/contract/test_conclusion_evidence_parity.py`

## Expected Output

- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/runtime_diagnostics.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/conversation/replay.py`
- `backend/tests/contract/test_conclusion_evidence_parity.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q

## Observability Impact

Structured log projection_evidence_degradation_built with per-layer status (retrieval_ok/degraded, transcript_ok/degraded, audio_ok/degraded, enhanced_report_ok/degraded) emitted inside build_projection().
