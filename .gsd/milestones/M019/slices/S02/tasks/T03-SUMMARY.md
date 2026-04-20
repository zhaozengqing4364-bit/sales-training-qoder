---
id: T03
parent: S02
milestone: M019
key_files:
  - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_practice_evidence_flow.py
  - .gsd/DECISIONS.md
  - .codex/loop/state.json
  - .codex/loop/log.md
key_decisions:
  - D214 — keep `practice_session_service`/`practice_report_service` as the practice route-facing seams while preserving `SessionEvidenceService` as the canonical completed-session read model for replay/history/admin consumers.
duration: 
verification_result: passed
completed_at: 2026-04-13T04:03:49.563Z
blocker_discovered: false
---

# T03: Locked the extracted practice seam with canonical read-model proof and downstream consumption guidance.

**Locked the extracted practice seam with canonical read-model proof and downstream consumption guidance.**

## What Happened

I fixed the missing proof around the extracted practice seam instead of changing the already-correct runtime behavior. In `backend/tests/contract/test_practice_evidence_contract.py` I added a seam assertion that the route bundle’s `PracticeReportService` reuses the same `SessionEvidenceService` and `PracticeAudioAuditService` instances exposed by `build_practice_route_services`, plus a documentation proof that the long-lived architecture scan names `practice_session_service`, `practice_report_service`, and the downstream consumption rule. In `backend/tests/integration/test_practice_evidence_flow.py` I added one focused end-to-end flow that creates a completed sales session, computes a baseline `SessionEvidenceService` projection, then verifies `/api/v1/practice/sessions/{id}/report`, `/api/v1/sessions/{id}/replay`, `/api/v1/users/me/history`, and `/api/v1/admin/users/{user_id}/sessions` all stay aligned with that canonical read model. The new integration proof records `SessionEvidenceService.get_projection` and `SessionEvidenceService.build_projection` calls so the test locks not only payload parity but also the intended route-family consumption path. I then updated `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md` with an explicit M019/S02 closure section describing the extracted practice split and a concrete S03/M021 downstream rule: write-side/session orchestration changes belong in `practice_session_service`, practice report/audio route work belongs in `practice_report_service`, and replay/history/admin truth stays on `SessionEvidenceService`/`ReplayService`/`history_service` instead of drifting back into `common/api/practice.py`. Finally, I recorded that boundary as decision D214 and synced the repo-local safe-grow state/log so the next turn resumes from this task rather than the previous slice.

## Verification

I followed a red-first proof flow for the missing documentation seam: the new architecture-scan contract initially failed until the M019/S02 closure section was written back into `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`. After that, the focused contract and integration proof went green, confirming the route bundle reuses the canonical `SessionEvidenceService` read-model seam and that report/history/admin/replay still consume it through their existing route families. I then ran the broader touched-file backend gate across `backend/tests/contract/test_practice_evidence_contract.py` and `backend/tests/integration/test_practice_evidence_flow.py`; it finished 37/37 passing. The exact slice-plan grep verification also passed, surfacing `practice_session_service`, `practice_report_service`, and `SessionEvidenceService` across the architecture scan, `backend/src/common/api/practice.py`, and the updated contract proof. Fresh LSP diagnostics were clean on the two touched Python proof files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py -x -q` | 0 | ✅ pass | 14021ms |
| 2 | `rg -n "practice_session_service|practice_report_service|SessionEvidenceService" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/api/practice.py backend/tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 27ms |

## Deviations

None.

## Known Issues

Pre-existing backend verification still emits pytest-cov "Module src was never imported / No data was collected" warnings plus third-party Python 3.14 deprecation warnings from LangChain/Chroma during the focused pytest gate. The architecture-scan markdown file also has no configured language server, so only the touched Python proof files received LSP diagnostics.

## Files Created/Modified

- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `.gsd/DECISIONS.md`
- `.codex/loop/state.json`
- `.codex/loop/log.md`
