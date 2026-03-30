# M010 / S02 — Research

**Date:** 2026-03-28

## Summary

S02 primarily owns **R028** (retrieval / transcript / audio / enhanced-report layered degradation) and supports **R027** by making the new conclusion provenance honest when parts of the evidence chain are missing.

This is a **targeted contract-hardening slice on the existing S01 seam**, not a new UI or route design problem. S01 already proved that `conclusion_evidence` is built once in `SessionEvidenceService.build_projection()` and mirrored unchanged to report, replay, and knowledge-check for completed sales sessions. What S02 needs to add is the missing cross-route degradation vocabulary on top of that seam.

The current degradation state is fragmented:
- `backend/src/common/conversation/session_evidence.py` `_build_evidence_completeness(...)` is still a coarse projection-completeness check for sales (`complete`, `missing_fields`, counts). It has **no layered retrieval/transcript/audio/enhanced-report taxonomy**.
- Presentation already uses a different shape: `_build_presentation_evidence_completeness(...)` carries presentation-only `degraded_reasons` like `missing_page_metadata`.
- Audio degradation exists separately in `build_session_audio_audit(...)` as `audio_audit.summary.degraded_reasons` (`upload_failed`, `segments_pending`).
- Enhanced-report degradation is not in the canonical evidence payload at all; it currently surfaces via `PracticeSession.report_status` / `report_error` and the optional `/practice/sessions/{id}/comprehensive-report` endpoint.
- Knowledge-check currently returns `conclusion_evidence` and `retrieval_facts`, but **does not return `evidence_completeness`**, so overloading only that field cannot satisfy route-family parity.

The safest implementation seam is therefore the one already chosen in D127/D134/D135: **build one additive layered degradation payload on the projection authority seam, then mirror it into knowledge-check via `build_session_runtime_diagnostics(...)`**. Keep existing `evidence_completeness` and route-specific degraded fields backward-compatible rather than trying to rename them into the new taxonomy.

## Recommendation

Implement S02 as **one shared additive degradation field** for completed sales sessions, then mirror compatibility state outward.

Recommended shape:
- Add a new additive field on the projection, e.g. `degradation_detail` / `evidence_degradation`, carrying the four canonical layers:
  - `retrieval_degraded`
  - `transcript_degraded`
  - `audio_degraded`
  - `enhanced_report_degraded`
- Each layer should carry at least:
  - canonical token
  - degraded / ok boolean or status
  - compact explanation string
  - route-safe detail source (existing reason/status only; no new invented truth)

Recommended derivation sources:
- **retrieval layer**: reuse projected `retrieval_facts` / `build_retrieval_facts(...)` truth. Do not rebuild retrieval semantics anywhere else.
- **transcript layer**: for S02, derive from the already-shipped `conclusion_evidence.*.transcript_source.available` signal unless the task explicitly widens S01’s provenance semantics. Today that signal means “scored user-turn evidence exists”, not a first-class transcript-reference object.
- **audio layer**: use the already-shipped `conclusion_evidence.*.audio_source.available` as the minimal cross-route truth, and keep richer audio-specific reasons inside `audio_audit.summary.degraded_reasons` where report/replay already expose them.
- **enhanced-report layer**: derive from persisted backend state (`PracticeSession.report_status` / `report_error`), not from frontend fetch failures or optional endpoint retries.

Recommended compatibility strategy:
- Keep `evidence_completeness` intact.
- For completed projection-backed consumers, mirror the canonical layer tokens into `evidence_completeness.degraded_reasons` so existing analytics/history consumers keep working.
- Keep presentation-only `evidence_completeness.degraded_reasons` semantics separate. Do not overwrite presentation `missing_page_metadata` with sales evidence tokens.

This matches the loaded skill guidance:
- **fastapi-python**: keep route responses additive and model-backed; do not create route-local dictionaries that bypass the schema seam.
- **pydantic**: update response models in the same change as the service logic, or FastAPI/OpenAPI filtering will silently drop the new field.

## Implementation Landscape

### Core backend seam

- `backend/src/common/conversation/session_evidence.py`
  - S01 already established the right authority seam here.
  - `build_conclusion_evidence_bundle(...)` is the existing per-source availability model for `main_issue`, `next_goal`, `claim_truth`.
  - `_build_evidence_completeness(...)` is still sales-only coarse completeness, not layered degradation.
  - `_build_presentation_evidence_completeness(...)` already uses `degraded_reasons`, but for a different presentation-specific meaning.
  - **Natural seam:** add one new builder near `build_projection(...)` and keep all projection-backed surfaces reading it rather than deriving route-local state.

- `backend/src/common/conversation/runtime_diagnostics.py`
  - `build_session_runtime_diagnostics(...)` is already the knowledge-check mirror seam for completed sessions.
  - It already passes through `retrieval_facts` and `conclusion_evidence` from the projection.
  - **Natural seam:** add one more passthrough parameter/field here so knowledge-check speaks the same layered taxonomy as report/replay.

### Route wiring

- `backend/src/common/api/practice.py`
  - Report route already reads projection-backed fields and can expose the new additive field with minimal change.
  - Knowledge-check route already loads projection for completed sales sessions and passes `conclusion_evidence` into `build_session_runtime_diagnostics(...)`.
  - The same route also has access to `session.report_status` / `report_error`, which is the honest backend source for the enhanced-report layer.
  - `build_session_audio_audit(...)` remains the richer audio-specific surface; S02 should consume it, not replace it.

- `backend/src/common/conversation/replay.py`
  - Replay already mirrors `evidence_completeness`, `audio_audit`, and `conclusion_evidence` from the projection.
  - **Natural seam:** replay should only pass through the new field once the projection carries it.

### Response models / contract seam

- `backend/src/common/conversation/schemas.py`
  - Replay response schema currently declares `evidence_completeness`, `audio_audit`, and `conclusion_evidence`.
  - New additive degradation field must be declared here or replay will silently trim it.

- `backend/src/common/db/schemas.py`
  - `SessionReport` schema likewise needs the new field.

- `web/src/lib/api/types.ts`
  - `SessionEvidenceContract` currently includes `evidence_completeness` and `audio_audit`, but **does not declare `conclusion_evidence` at all** even though backend report/replay now return it.
  - `KnowledgeCheckDiagnostics` is stale: it still omits the backend’s already-shipped `retrieval_facts` and `conclusion_evidence` passthroughs.
  - **Planner implication:** S02 should treat TS contract drift as part of the slice, not optional cleanup. If the backend adds the new field and TS types stay stale, S03 will inherit silent drift.

- `web/src/lib/session-evidence.ts`
  - This is the shared wording seam for S03.
  - Today `formatEvidenceCompletenessNote(...)` only formats coarse `missing_fields`, and `formatPresentationDegradedNote(...)` only handles presentation reasons.
  - **Planner implication:** S02 does not need to add final UI, but if it adds canonical tokens, this shared helper is the right place for token-to-copy mapping later. Do not let pages invent route-local wording.

### Compatibility consumers outside the main route family

- `backend/src/common/analytics/admin_analytics_service.py`
  - `_extract_degraded_reasons(...)` only reads `summary.evidence_completeness.degraded_reasons`, then falls back to `missing_fields`.
  - If S02 moves degradation truth to a new field without mirroring, admin degradation analytics will silently stop seeing the new taxonomy.

- `backend/src/common/analytics/history_service.py`
  - History summaries still only persist `evidence_completeness`, not a new degradation field.
  - Not the primary scope of S02, but it is a compatibility constraint if the slice changes degraded token semantics.

## Build Order

1. **Prove the taxonomy shape in parity tests first.**
   Extend `backend/tests/contract/test_conclusion_evidence_parity.py` with failing route-family assertions for the new layered degradation field on:
   - report
   - replay
   - knowledge-check

   Minimum cases:
   - retrieval missing
   - audio missing
   - enhanced-report failed
   - happy-path no degradation

   Transcript-degraded should be added only if the fixture can express it honestly with the current S01 semantics.

2. **Build the shared degradation builder on the projection seam.**
   Add one builder in `backend/src/common/conversation/session_evidence.py` and attach it inside `build_projection(...)` for completed sales sessions.

3. **Mirror the same field through knowledge-check.**
   Thread it into `build_session_runtime_diagnostics(...)` and return it from the knowledge-check payload exactly as report/replay see it.

4. **Update Pydantic response models and TS types in the same task.**
   This repo already has a real failure mode where backend service changes are trimmed or hidden by stale schemas/types.

5. **Add compatibility mirroring only after parity is correct.**
   If admin/history compatibility is part of the slice, mirror canonical layer tokens into `evidence_completeness.degraded_reasons` after the new field exists, not instead of it.

## Verification Approach

Repo-root verification commands for S02 should stay split and runnable without `cd`:

### Backend parity and schema verification
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/integration/test_replay_api.py -q`

### Compatibility verification if `evidence_completeness.degraded_reasons` mirroring changes
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -q`

### Frontend type/helper verification if TS contract files change in S02
- `npm --prefix web test -- --run "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx" "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`

Key proof target for the slice:
- the same completed sales session must expose the same layered degradation contract on report, replay, and knowledge-check
- existing consumers must not lose their old coarse completeness or degraded-reason signals unless intentionally migrated in the same change

## Constraints

- **Keep projection as the only completed-session truth source.** S02 should extend `SessionEvidenceService.build_projection()`, not introduce route-local degradation logic.
- **Preserve the live/completed split in knowledge-check.** Report and replay are completed-session surfaces; knowledge-check also serves live runtime. For live sessions, do not fake projection-backed layered degradation that only exists for completed projections.
- **Do not let enhanced-report optionality overwrite canonical evidence.** `report_status == failed` can mark the enhanced-report layer as degraded, but report/replay canonical conclusions and provenance must still render.
- **Do not reuse presentation degraded semantics for sales.** Presentation `missing_page_metadata` is a different contract and should not be renamed into the sales taxonomy.
- **Response-model drift is part of the implementation risk.** Per the loaded Pydantic/FastAPI rules, schema changes are incomplete until both backend models and frontend types reflect them.

## Common Pitfalls

- **Only updating report/replay `evidence_completeness` and forgetting knowledge-check.** Knowledge-check does not currently return `evidence_completeness`, so this cannot produce route-family parity by itself.
- **Removing or repurposing `evidence_completeness.degraded_reasons` without a mirror.** Admin analytics still depends on that field.
- **Treating “transcript degraded” as a solved concept already.** The current S01 transcript signal is “scored user turns exist”, not a first-class transcript-reference payload.
- **Deriving `enhanced_report_degraded` from page fetch failures.** The report page intentionally treats comprehensive-report as optional and may fail for non-canonical reasons; the backend taxonomy should use persisted session state instead.
- **Adding new fields only in Python.** `web/src/lib/api/types.ts` is already lagging behind the shipped backend contract; S02 will compound that drift if it does not update the TS seam.

## Open Risks

- **Transcript layer semantics are still slightly under-specified.** If the product wants “missing transcript metadata” specifically, S02 may need to widen S01’s provenance builder instead of merely classifying current `transcript_source.available`.
- **Audio layer granularity differs by route.** Report/replay have rich `audio_audit`; knowledge-check only needs compact layer status. The taxonomy should unify the token vocabulary, not force knowledge-check to return segment-level payloads.
- **Enhanced-report layer may be backend-state-complete but UI-state-optional.** Keep those two truths separate so canonical evidence doesn’t flap based on optional endpoint retries.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI response modeling | `fastapi-python` | preinstalled; used for additive route/model guidance |
| Pydantic response/schema validation | `pydantic` | preinstalled; used for response-model drift guidance |
| SQLAlchemy / ORM patterns | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | installed globally during this unit for later slices |
