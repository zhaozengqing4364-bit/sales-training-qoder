---
id: T01
parent: S05
milestone: M003
provides: []
requires: []
affects: []
key_files: ["backend/tests/unit/test_stepfun_realtime_handler.py", "backend/tests/unit/test_stepfun_knowledge_helpers.py", "backend/tests/integration/test_knowledge_flow.py", "backend/tests/contract/test_practice_evidence_contract.py"]
key_decisions: ["Kept the regression expansion on the existing StepFun/runtime/report routes instead of adding a parallel helper-only proof surface.", "Asserted the shipped claim-truth status keys (`weak_evidence`, `evidence_pending`, `evidence_verified`) rather than inventing alias names in tests.", "Used `effectiveness_snapshot.claim_truth` on report/replay as the shared verified-evidence contract seam."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the exact task gate `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py` and it passed with 90/90 tests green. Also checked LSP diagnostics on the four changed Python files; no diagnostics were reported."
completed_at: 2026-03-25T07:30:49.353Z
blocker_discovered: false
---

# T01: Expanded objection-heavy runtime regressions across competitor, implementation-risk, and claim-truth evidence paths

> Expanded objection-heavy runtime regressions across competitor, implementation-risk, and claim-truth evidence paths

## What Happened
---
id: T01
parent: S05
milestone: M003
key_files:
  - backend/tests/unit/test_stepfun_realtime_handler.py
  - backend/tests/unit/test_stepfun_knowledge_helpers.py
  - backend/tests/integration/test_knowledge_flow.py
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - Kept the regression expansion on the existing StepFun/runtime/report routes instead of adding a parallel helper-only proof surface.
  - Asserted the shipped claim-truth status keys (`weak_evidence`, `evidence_pending`, `evidence_verified`) rather than inventing alias names in tests.
  - Used `effectiveness_snapshot.claim_truth` on report/replay as the shared verified-evidence contract seam.
duration: ""
verification_result: passed
completed_at: 2026-03-25T07:30:49.354Z
blocker_discovered: false
---

# T01: Expanded objection-heavy runtime regressions across competitor, implementation-risk, and claim-truth evidence paths

**Expanded objection-heavy runtime regressions across competitor, implementation-risk, and claim-truth evidence paths**

## What Happened

Extended the existing regression surfaces without changing production code. In `backend/tests/unit/test_stepfun_knowledge_helpers.py` I parameterized objection-style retrieval coverage so ROI, price, competitor, and implementation-risk queries all keep the widened top-k, relaxed threshold, and 420-character snippet window. In `backend/tests/unit/test_stepfun_realtime_handler.py` I added a competitor-alternative case that must open a pending objection ledger on the live StepFun feedback path and an implementation-risk case that must close the ledger with `evidence_provided` and promote claim truth to `evidence_verified`. In `backend/tests/integration/test_knowledge_flow.py` I added competitor and implementation-risk personas to prove the current `/api/v1/practice/sessions` entry chain still freezes distinct pressure contracts and keeps those snapshots stable after later persona edits. In `backend/tests/contract/test_practice_evidence_contract.py` I tightened the shared report/replay contract so weak evidence is asserted explicitly and strong ROI proof surfaces the verified claim-truth payload on both routes.

## Verification

Ran the exact task gate `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py` and it passed with 90/90 tests green. Also checked LSP diagnostics on the four changed Python files; no diagnostics were reported.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py tests/integration/test_knowledge_flow.py tests/contract/test_practice_evidence_contract.py` | 0 | ✅ pass | 62500ms |


## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/tests/unit/test_stepfun_realtime_handler.py`
- `backend/tests/unit/test_stepfun_knowledge_helpers.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/contract/test_practice_evidence_contract.py`


## Deviations
None.

## Known Issues
None.
