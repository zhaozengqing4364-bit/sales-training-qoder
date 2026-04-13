---
id: S02
parent: M019
milestone: M019
provides:
  - A named backend application seam for practice session creation, lifecycle, runtime descriptor, report, audio audit, and audio segment flows.
  - A documented downstream rule for whether future changes belong in `practice_session_service`, `practice_report_service`, or `SessionEvidenceService`.
  - A stable verification bundle that can catch route-contract drift, lifecycle-observability drift, and completed-session read-model drift separately.
requires:
  []
affects:
  - S03
  - S04
  - M021
key_files:
  - backend/src/common/api/practice.py
  - backend/src/common/services/practice_service.py
  - backend/src/common/services/practice_session_service.py
  - backend/src/common/services/practice_report_service.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_practice_evidence_flow.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D212 — introduce `common.services.practice_service` as the first route-facing seam bundle for practice responsibilities.
  - D213 — keep `common.services.practice_service` as a compatibility bundle that composes the new `practice_session_service` and `practice_report_service` modules.
  - D214 — preserve `SessionEvidenceService` as the canonical completed-session read model while the practice route family delegates write/report orchestration through the extracted services.
patterns_established:
  - Route-facing compatibility bundle first, focused application services second.
  - Separate practice write/application seams from completed-session read-model seams.
  - Preserve route-owned structured logger injection when extracting lifecycle orchestration.
observability_surfaces:
  - Focused lifecycle log assertions for `practice_session_lifecycle_transition_applied` and terminal connection-close handling.
  - `backend/tests/integration/test_practice_evidence_flow.py` parity proof on `SessionEvidenceService` consumption across report/replay/history/admin.
  - Architecture-scan seam map in `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` for downstream landing-zone verification.
drill_down_paths:
  - .gsd/milestones/M019/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M019/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M019/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-13T04:09:56.737Z
blocker_discovered: false
---

# S02: Practice backend application seam 抽离

**Extracted practice backend session/report application seams out of `common/api/practice.py` while preserving existing route contracts and the canonical `SessionEvidenceService` completed-session truth line.**

## What Happened

## Delivered
- Introduced a stable route-facing compatibility bundle in `backend/src/common/services/practice_service.py`, then extracted the actual backend application logic into `practice_session_service.py` and `practice_report_service.py`.
- Moved session creation, retry-focus shaping, runtime descriptor assembly, and lifecycle orchestration behind `PracticeSessionCreateService` and `PracticeSessionLifecycleApplicationService` so the route layer can stay focused on auth, request parsing, response shaping, and HTTP status handling.
- Moved report assembly, audio-audit projection, OSS signing/audio-segment registration, and retry-entry shaping behind `PracticeReportService`, `PracticeAudioAuditService`, and `PracticeAudioSegmentService`.
- Kept `common.services.practice_service` as the compatibility seam so downstream work can adopt the new services without importing route-local helpers or re-coupling itself to `backend/src/common/api/practice.py`.
- Locked the completed-session read-model boundary: report routes can use the extracted practice report service, but replay/history/admin still consume the canonical `SessionEvidenceService` projection instead of rebuilding truth from practice-route helpers.

## What This Slice Actually Changed
- `backend/src/common/api/practice.py` is still the HTTP entrypoint, but it no longer needs to own all orchestration logic itself.
- `backend/src/common/services/practice_session_service.py` is now the write-side/application seam for create/lifecycle/runtime-descriptor work.
- `backend/src/common/services/practice_report_service.py` is now the practice-route report/audio seam.
- `backend/src/common/services/practice_service.py` is the route-facing composition seam that wires shared dependencies once.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` now documents the downstream consumption rule so later slices know which seam to extend.

## Patterns Established
- Use a route-facing compatibility bundle first, then peel business orchestration into narrower application services without forcing every consumer to switch imports in one step.
- Keep write-side practice orchestration seams separate from the completed-session read-model seam; `practice_*_service` owns route/application behavior, while `SessionEvidenceService` remains the shared completed-session authority for replay/history/admin.
- When extracting lifecycle logic, inject the route-owned logger into services so focused lifecycle observability proof and existing log-based diagnostics remain stable.

## Downstream Guidance
- If future work changes session create, retry focus, runtime descriptor, or lifecycle orchestration, extend `practice_session_service` and keep `practice_service` as the route-facing bundle.
- If future work changes practice report payloads, audio audit, or audio-segment upload/register/failure flows, extend `practice_report_service`.
- If future work changes replay/history/admin/manager-truth on completed sessions, extend `SessionEvidenceService`, `ReplayService`, or `history_service` instead of rebuilding a projection inside `practice.py`.
- This gives S03 a clean backend seam to pair against frontend domain-client/transport work, and gives later evidence/kernel work a clear rule for staying on the canonical read model.

## Operational Readiness
- **Health signal:** the fresh backend verification bundle is green, architecture-scan seam documentation is grep-discoverable, and all touched Python files are LSP-clean.
- **Failure signal:** regressions will usually show up as one of three failures: route contract tests breaking, lifecycle observability assertions no longer seeing the expected route logger events, or report/replay/history/admin parity drifting away from `SessionEvidenceService`.
- **Recovery procedure:** extend the correct extracted service instead of patching `practice.py`, preserve route logger injection for lifecycle services, then rerun the three slice gates (`practice evidence + lifecycle`, `practice evidence + evidence flow + lifecycle`, and the seam grep proof).
- **Monitoring gaps:** there is still no dedicated runtime metric for “which practice seam handled this change”; boundary enforcement currently depends on focused tests, architecture-scan guidance, and log assertions rather than first-class production metrics.


## Verification

Fresh slice-close verification passed all planned gates from repo root: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_session_lifecycle_api.py -x -q` (44 passed), `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_session_lifecycle_api.py -x -q` (50 passed), and `rg -n "practice_session_service|practice_report_service|SessionEvidenceService" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/api/practice.py backend/tests/contract/test_practice_evidence_contract.py` (matched the documented downstream seam rule). Fresh LSP diagnostics on `backend/src/common/api/practice.py`, `backend/src/common/services/practice_service.py`, `backend/src/common/services/practice_session_service.py`, `backend/src/common/services/practice_report_service.py`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_practice_evidence_flow.py`, and `backend/tests/integration/test_session_lifecycle_api.py` all returned no diagnostics. Test output still showed the pre-existing pytest-cov no-data warning and Python 3.14 async teardown warning, but both gates exited 0 and matched prior known-noise behavior.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None beyond the intentional compatibility-bundle pattern recorded in D213.

## Known Limitations

`backend/src/common/api/practice.py` remains the HTTP entrypoint and still contains legacy helper residue, so the file is smaller in responsibility but not yet small in size. Boundary enforcement is also still test-and-doc driven; there is no production metric that directly proves whether a future change landed on the correct extracted seam.

## Follow-ups

S03 should keep this backend split intact when extracting frontend domain client / transport seams, and S04 should reuse the same focused practice verification bundle as part of the release gate instead of inventing a second backend truth line.

## Files Created/Modified

- `backend/src/common/api/practice.py` — Rewired the route layer to delegate create/lifecycle/report/audio orchestration through extracted practice services while keeping the API surface unchanged.
- `backend/src/common/services/practice_service.py` — Introduced the route-facing compatibility bundle and shared dependency wiring for the extracted practice seams.
- `backend/src/common/services/practice_session_service.py` — Holds session creation, retry-focus shaping, runtime descriptor assembly, and lifecycle application behavior.
- `backend/src/common/services/practice_report_service.py` — Holds report assembly, audio-audit projection, OSS signing/audio-segment flows, and retry-entry composition.
- `backend/tests/contract/test_practice_evidence_contract.py` — Locks the extracted seam inventory plus the canonical SessionEvidenceService read-model contract.
- `backend/tests/integration/test_practice_evidence_flow.py` — Proves report/replay/history/admin remain aligned to the canonical completed-session projection after extraction.
- `backend/tests/integration/test_session_lifecycle_api.py` — Keeps the route-level lifecycle contract and observability proof stable while services are extracted.
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` — Documents the M019/S02 seam split and downstream consumption rule for later slices.
- `.gsd/KNOWLEDGE.md` — Records the logger-injection gotcha and the post-S02 seam-selection rule for future agents.
