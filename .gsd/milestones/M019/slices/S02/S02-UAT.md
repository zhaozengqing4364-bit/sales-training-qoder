# S02: Practice backend application seam 抽离 — UAT

**Milestone:** M019
**Written:** 2026-04-13T04:09:56.737Z

# S02 UAT — Practice backend application seam 抽离

## Preconditions
1. Repository is at the M019/S02 close-out state.
2. Run all commands from repo root: `/Users/zhaozengqing/github/销售训练qoder`.
3. Backend virtualenv dependencies are installed at `backend/venv`.
4. No local code changes are bypassing the extracted practice services.

## Test Case 1 — Practice route bundle exposes the extracted application seams
**Goal:** confirm the route-facing seam exists and future work does not need to import route-local helpers.

1. Run:
   - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -x -q`
2. Verify the contract suite passes.
3. Inspect the seam inventory via:
   - `rg -n "practice_session_service|practice_report_service|SessionEvidenceService" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/tests/contract/test_practice_evidence_contract.py`

**Expected outcomes**
- The contract suite passes without `ModuleNotFoundError` or missing-seam assertions.
- The architecture scan and contract proof both mention `practice_session_service`, `practice_report_service`, and `SessionEvidenceService`.
- The route-facing bundle remains `common.services.practice_service`, not direct imports from `common/api/practice.py`.

## Test Case 2 — Session creation and lifecycle behavior stay on the current API contract
**Goal:** confirm extracted session services did not change create/lifecycle route behavior.

1. Run:
   - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_session_lifecycle_api.py -x -q`
2. Review lifecycle-related assertions in the output scope.

**Expected outcomes**
- The combined gate passes.
- Session create responses still include the same outward contract fields, including runtime descriptor / snapshot metadata expected by current routes.
- Lifecycle transitions remain valid for the existing API surface.
- Route-level lifecycle observability still emits the established log events used by focused proof (`practice_session_lifecycle_transition_applied`, terminal close handling).

## Test Case 3 — Report, replay, history, and admin stay aligned to the canonical completed-session read model
**Goal:** confirm the extraction did not fork completed-session truth into the route layer.

1. Run:
   - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_session_lifecycle_api.py -x -q`
2. Review the focused evidence-flow assertions.

**Expected outcomes**
- The full gate passes.
- Completed-session report payloads continue to assemble through the extracted practice report service.
- Replay, learner history, and admin completed-session consumers still align with `SessionEvidenceService` rather than rebuilding truth in `practice.py`.
- The focused proof can still observe `SessionEvidenceService.get_projection/build_projection` as the canonical read-model path.

## Test Case 4 — Downstream seam rules are discoverable for future slices
**Goal:** ensure future agents can tell where to land new work.

1. Run:
   - `rg -n "practice_session_service|practice_report_service|SessionEvidenceService" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/api/practice.py backend/tests/contract/test_practice_evidence_contract.py`
2. Read the M019/S02 closure section in the architecture scan.

**Expected outcomes**
- The grep proof succeeds.
- The architecture scan explicitly states:
  - create/lifecycle/runtime descriptor/retry-focus changes belong in `practice_session_service`
  - report/audio flows belong in `practice_report_service`
  - replay/history/admin completed-session truth belongs in `SessionEvidenceService` / existing read-model consumers
- No downstream guidance tells agents to extend `common/api/practice.py` as the default business-logic seam.

## Edge Cases
- If lifecycle tests fail only because expected route log events disappear, treat it as an observability regression caused by logger ownership drifting back to a module-local logger inside the extracted services.
- If report/replay/history/admin payload parity drifts while route tests still pass, treat it as a read-model boundary regression: the likely fix is in `SessionEvidenceService` consumption or service wiring, not a new route-local projection.
- If the architecture-scan grep fails but tests pass, do not close the slice: downstream slices will lose the seam map and are likely to regress back into `practice.py`.

