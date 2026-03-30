---
id: S02
parent: M010
milestone: M010
provides:
  - projection-backed `evidence_degradation` taxonomy with retrieval/transcript/audio/enhanced_report layers on completed sales sessions
  - Cross-route parity: report, replay, and knowledge-check now return the same layered degradation payload
  - Backward-compatible `evidence_completeness.degraded_reasons` mirror for admin/history readers
requires:
  - slice: S01
    provides: shared projection-backed `conclusion_evidence` bundle carried consistently through report, replay, and knowledge-check
affects:
  - S03
key_files:
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/api/practice.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/schemas.py
  - backend/src/common/db/schemas.py
  - backend/tests/contract/test_conclusion_evidence_parity.py
  - backend/tests/unit/test_session_evidence_service.py
  - backend/tests/unit/common/test_admin_analytics_service.py
  - backend/tests/unit/test_history_service_evidence_projection.py
  - web/src/lib/api/types.ts
  - .gsd/KNOWLEDGE.md
  - .gsd/PROJECT.md
key_decisions:
  - `evidence_degradation` is the authoritative M010/S02 contract; `evidence_completeness.degraded_reasons` only mirrors canonical layer tokens for compatibility.
  - The four-layer taxonomy is built once on `SessionEvidenceService.build_projection()` and mirrored to report/replay/knowledge-check instead of being recomputed per route.
  - Replay parity depends on declared schema fields as well as service payload wiring; `ReplayDataResponse` must explicitly include new projection fields or FastAPI/Pydantic will drop them.
  - Presentation sessions keep `evidence_degradation = null`; the taxonomy is sales-only in M010.
patterns_established:
  - Projection-as-authority for cross-route degradation semantics: build on the projection, mirror to diagnostics/routes, lock parity in one dedicated contract module.
  - Compatibility mirror pattern: keep the new explicit field authoritative, but reflect canonical tokens into existing coarse read models for admin/history consumers until they migrate.
observability_surfaces:
  - `projection_evidence_degradation_built` structured log with per-layer status for every projection build
  - `backend/tests/contract/test_conclusion_evidence_parity.py` route-family parity contract for happy-path, retrieval-missing, audio-missing, enhanced-report-failed, and presentation-null scenarios
  - `backend/tests/unit/common/test_admin_analytics_service.py` and `backend/tests/unit/test_history_service_evidence_projection.py` compatibility checks for mirrored degraded reasons
drill_down_paths:
  - .gsd/milestones/M010/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M010/slices/S02/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-30T04:02:17.444Z
blocker_discovered: false
---

# S02: 统一分层降级分类

**Built a single projection-backed four-layer `evidence_degradation` taxonomy for completed sales sessions and proved report, replay, and knowledge-check return the same layered degradation truth while keeping admin/history compatibility readers intact.**

## What Happened

S02 turned the S01 conclusion-evidence seam into a full degradation contract. `SessionEvidenceService.build_projection()` now computes one authoritative four-layer `evidence_degradation` payload for completed sales sessions (`retrieval`, `transcript`, `audio`, `enhanced_report`), with explicit status/token/explanation per layer. Report, replay, and knowledge-check all read that same projection-backed taxonomy; replay parity required closing a real serialization seam by declaring the field on `ReplayDataResponse`, not just adding it in the service payload. The slice also kept older admin/history readers alive by mirroring canonical degraded layer tokens into `evidence_completeness.degraded_reasons` for sales sessions while leaving presentation degraded reasons untouched. Focused parity and compatibility verification now proves the route family agrees on happy-path, retrieval-missing, audio-missing, enhanced-report-failed, and presentation-null scenarios, so the remaining M010 work is learner-facing rendering rather than backend truth recovery.

## Verification

Fresh slice-close verification passed `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/test_session_evidence_service.py -x -q` (47 passed) and `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q` (7 passed). Repo-wide `cd web && npx tsc --noEmit --pretty false` still reports pre-existing unrelated frontend type errors outside this slice's touched files.

## Requirements Advanced

- R028 — Added an explicit four-layer completed-session degradation taxonomy and threaded it consistently through report, replay, and knowledge-check while keeping compatibility readers aligned.

## Requirements Validated

- R028 — Validated by fresh slice-close verification: 47 focused parity/contract/unit tests plus 7 admin/history compatibility tests passed, proving identical layered degradation semantics across report, replay, knowledge-check, admin analytics, and history projection consumers.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Repo-wide `cd web && npx tsc --noEmit --pretty false` still fails on pre-existing unrelated frontend type errors outside this slice's touched files. Backend slice acceptance and compatibility verification passed cleanly, so the slice closes on the backend authority seam while leaving that broader frontend baseline cleanup to later work.

## Known Limitations

`evidence_degradation` remains intentionally `null` for presentation sessions in M010, learner-facing report/replay pages do not yet render the new taxonomy until S03 lands, and admin/history still consume mirrored `evidence_completeness.degraded_reasons` rather than the richer structured taxonomy directly.

## Follow-ups

S03 should render `evidence_degradation` from shared `session-evidence.ts` helpers on report and replay pages without deriving a second taxonomy from local copy or heuristics. A later frontend baseline cleanup should also address the existing unrelated repo-wide `tsc` failures so the new EvidenceDegradation types can live inside a clean type-checking baseline.

## Files Created/Modified

- `backend/src/common/conversation/session_evidence.py` — Added the authoritative four-layer `evidence_degradation` builder and mirrored canonical degraded tokens into sales `evidence_completeness.degraded_reasons` for compatibility.
- `backend/src/common/conversation/runtime_diagnostics.py` — Mirrored projection-backed `evidence_degradation` into knowledge-check diagnostics for completed sales sessions.
- `backend/src/common/api/practice.py` — Exposed `evidence_degradation` on canonical report responses and passed it through the knowledge-check route.
- `backend/src/common/conversation/replay.py` — Added `evidence_degradation` to replay payload generation.
- `backend/src/common/conversation/schemas.py` — Declared `evidence_degradation` on `ReplayDataResponse`, closing the replay serialization seam.
- `backend/src/common/db/schemas.py` — Kept the shared report schema aligned with the new degradation field.
- `backend/tests/contract/test_conclusion_evidence_parity.py` — Extended route-family parity coverage to explicit degradation cases for happy-path, retrieval-missing, audio-missing, enhanced-report-failed, and presentation-null scenarios.
- `backend/tests/unit/test_session_evidence_service.py` — Added unit coverage for taxonomy construction and structured degradation logging.
- `backend/tests/unit/common/test_admin_analytics_service.py` — Updated admin degraded-reason expectations to canonical taxonomy tokens.
- `backend/tests/unit/test_history_service_evidence_projection.py` — Verified history projection compatibility with mirrored degraded reasons.
- `web/src/lib/api/types.ts` — Added `EvidenceDegradationLayer`/`EvidenceDegradation` types and wired `evidence_degradation` into shared API contracts.
- `.gsd/KNOWLEDGE.md` — Recorded the replay-schema seam so future agents check the serializer layer before debugging replay service logic.
- `.gsd/PROJECT.md` — Updated current-state documentation to reflect that M010/S01-S02 backend evidence and degradation contracts are complete and S03 is now the learner-facing rendering step.
