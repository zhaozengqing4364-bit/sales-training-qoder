# S02: 统一分层降级分类

**Goal:** Introduce a unified four-layer degradation taxonomy (retrieval, transcript, audio, enhanced_report) on the existing projection seam, so sessions with partial evidence produce explicit layered degradation tokens that are consistent across report, replay, and knowledge-check.
**Demo:** After this: After this slice, sessions with partial evidence (missing retrieval, missing audio, or degraded transcript) produce explicit layered degradation tokens that are consistent across report, replay, and knowledge-check.

## Tasks
- [x] **T01: Added projection-level evidence_degradation and partial route wiring, but replay parity is still blocked by the replay response schema dropping the new field.** — Add `evidence_degradation` as a new computed field on SessionEvidenceProjection, built from existing S01 provenance signals and session state. The field carries four canonical layers (retrieval, transcript, audio, enhanced_report) with status/token/explanation per layer. Wire it through report, replay, and knowledge-check routes. Extend the parity contract test to assert identical degradation payloads across all three routes for happy-path, retrieval-missing, audio-missing, and enhanced-report-failed scenarios.
  - Estimate: 2h
  - Files: backend/src/common/conversation/session_evidence.py, backend/src/common/conversation/runtime_diagnostics.py, backend/src/common/api/practice.py, backend/src/common/conversation/replay.py, backend/tests/contract/test_conclusion_evidence_parity.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q
  - Blocker: Replay parity is still broken because backend/src/common/conversation/schemas.py replay response models do not yet declare evidence_degradation, so replay serializes the field as null/missing even though ReplayService adds it to the response dict.
- [x] **T02: Add TS EvidenceDegradation types, degraded_reasons mirror, and update admin analytics test expectations for four-layer taxonomy** — The Pydantic replay schema fix is already applied (evidence_degradation added to ReplayDataResponse). Remaining work:

1. In `backend/src/common/conversation/session_evidence.py`, extend `_build_evidence_completeness()` to mirror canonical degradation layer tokens into the returned dict's `degraded_reasons` list. For each layer in `evidence_degradation` where `status == "degraded"`, append the layer's token (e.g. `"retrieval_degraded"`, `"audio_degraded"`, `"enhanced_report_degraded"`) to `degraded_reasons`. Only do this for sales sessions — do NOT overwrite presentation-specific `degraded_reasons`. Keep existing `missing_fields` logic intact.

2. Add the TS type `EvidenceDegradationLayer` and `EvidenceDegradation` in `web/src/lib/api/types.ts`:
   ```typescript
   export interface EvidenceDegradationLayer {
     status: "ok" | "degraded";
     token?: string;
     explanation?: string;
   }
   export interface EvidenceDegradation {
     retrieval: EvidenceDegradationLayer;
     transcript: EvidenceDegradationLayer;
     audio: EvidenceDegradationLayer;
     enhanced_report: EvidenceDegradationLayer;
   }
   ```
   Add `evidence_degradation?: EvidenceDegradation | null` to `SessionEvidenceContract`.
   Add `evidence_degradation?: EvidenceDegradation | null` to `KnowledgeCheckDiagnostics`.

3. Run existing admin analytics and history projection tests to verify the compatibility mirror did not break anything.
  - Estimate: 1h
  - Files: backend/src/common/conversation/session_evidence.py, web/src/lib/api/types.ts, backend/tests/unit/common/test_admin_analytics_service.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py backend/tests/contract/test_conclusion_evidence_parity.py -x -q && cd web && npx tsc --noEmit --pretty 2>&1 | head -30
