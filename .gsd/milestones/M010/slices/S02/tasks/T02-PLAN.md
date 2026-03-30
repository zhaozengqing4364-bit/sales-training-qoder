---
estimated_steps: 7
estimated_files: 5
skills_used:
  - pydantic
  - fastapi-python
---

# T02: Update Pydantic response models, TS types, and compatibility mirrors

**Slice:** S02 — 统一分层降级分类
**Milestone:** M010

## Description

T01 introduces `evidence_degradation` on the projection and routes. This task closes the anti-drift gap: update Pydantic response models so FastAPI does not silently trim the new field, update TS types so the frontend seam stays aligned, and mirror canonical degradation tokens into `evidence_completeness.degraded_reasons` for backward compatibility with admin analytics and history consumers.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Pydantic schema mismatch | Field silently dropped from API response | N/A | Stale TS type causes runtime undefined access |
| Admin analytics compatibility | Degraded reasons vanish from admin dashboard | N/A | Empty degraded_reasons list if mirror is broken |

## Negative Tests

- **Missing evidence_degradation on projection**: If projection returns null evidence_degradation, response schemas should still serialize (field is Optional).
- **Presentation session**: evidence_degradation should be null on response; evidence_completeness.degraded_reasons should NOT contain sales layer tokens.
- **Admin analytics with no degraded_reasons**: _extract_degraded_reasons should return empty list, not crash.

## Steps

1. Add `evidence_degradation: dict[str, Any] | None = Field(None, description="Layered degradation taxonomy")` to the replay response schema in `backend/src/common/conversation/schemas.py` (alongside existing `conclusion_evidence` field, ~line 335).

2. Add `evidence_degradation: dict[str, Any] | None = None` to `SessionReport` in `backend/src/common/db/schemas.py` (alongside existing `conclusion_evidence` field, ~line 486).

3. In `backend/src/common/conversation/session_evidence.py`, extend `_build_evidence_completeness()` to mirror canonical degradation layer tokens into the returned dict's `degraded_reasons` list. For each layer in `evidence_degradation` where `status == "degraded"`, append the layer's token (e.g. `"retrieval_degraded"`, `"audio_degraded"`, `"enhanced_report_degraded"`) to `degraded_reasons`. Only do this for sales sessions — do NOT overwrite presentation-specific `degraded_reasons`. The method signature stays the same; pass `evidence_degradation` as an additional parameter or derive it inside `_build_evidence_completeness` from the same inputs. Keep existing `missing_fields` logic intact.

4. Add the TS type `EvidenceDegradationLayer` and `EvidenceDegradation` in `web/src/lib/api/types.ts`:
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
   Add `evidence_degradation?: EvidenceDegradation | null` to `SessionEvidenceContract` (~line 1382).
   Add `evidence_degradation?: EvidenceDegradation | null` to `KnowledgeCheckDiagnostics` (~line 1617, alongside the existing `retrieval_facts` and `conclusion_evidence` passthroughs that should already exist from S01).

5. Wire `evidence_degradation` into the replay response in `backend/src/common/conversation/replay.py` — read it from `projection.evidence_degradation` alongside the existing `conclusion_evidence` wiring.

6. Run the existing admin analytics tests to verify the compatibility mirror did not break anything:
   ```
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py -x -q
   ```

7. Run the parity contract tests to confirm the full route-family including the new field:
   ```
   backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py -x -q
   ```

## Must-Haves

- [ ] Pydantic replay schema declares `evidence_degradation` field
- [ ] SessionReport schema declares `evidence_degradation` field
- [ ] `evidence_completeness.degraded_reasons` is populated with canonical layer tokens for degraded sales layers
- [ ] Presentation sessions do NOT get sales degradation tokens in their `degraded_reasons`
- [ ] TS `EvidenceDegradation` type exists and is wired into `SessionEvidenceContract` and `KnowledgeCheckDiagnostics`
- [ ] Existing admin analytics tests pass without changes to their assertions

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py backend/tests/contract/test_conclusion_evidence_parity.py -x -q`

## Inputs

- `backend/src/common/conversation/schemas.py` — replay response Pydantic model
- `backend/src/common/db/schemas.py` — SessionReport schema
- `backend/src/common/conversation/session_evidence.py` — `_build_evidence_completeness()` method to extend with degradation mirror
- `web/src/lib/api/types.ts` — SessionEvidenceContract and KnowledgeCheckDiagnostics interfaces
- `backend/src/common/conversation/replay.py` — replay response wiring

## Expected Output

- `backend/src/common/conversation/schemas.py` — `evidence_degradation` field added to replay schema
- `backend/src/common/db/schemas.py` — `evidence_degradation` field added to SessionReport
- `backend/src/common/conversation/session_evidence.py` — `_build_evidence_completeness()` extended with degradation token mirror
- `web/src/lib/api/types.ts` — `EvidenceDegradation`, `EvidenceDegradationLayer` types and updated `SessionEvidenceContract`, `KnowledgeCheckDiagnostics`
- `backend/tests/unit/common/test_admin_analytics_service.py` — tests pass confirming compatibility mirror works
