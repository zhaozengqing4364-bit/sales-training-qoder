---
estimated_steps: 19
estimated_files: 3
skills_used: []
---

# T02: Add TS types, degraded_reasons compatibility mirror, and verify admin analytics

The Pydantic replay schema fix is already applied (evidence_degradation added to ReplayDataResponse). Remaining work:

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

## Inputs

- `backend/src/common/conversation/session_evidence.py`
- `web/src/lib/api/types.ts`

## Expected Output

- `backend/src/common/conversation/session_evidence.py — _build_evidence_completeness() extended with degradation token mirror`
- `web/src/lib/api/types.ts — EvidenceDegradation, EvidenceDegradationLayer types and updated SessionEvidenceContract, KnowledgeCheckDiagnostics`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py backend/tests/contract/test_conclusion_evidence_parity.py -x -q && cd web && npx tsc --noEmit --pretty 2>&1 | head -30
