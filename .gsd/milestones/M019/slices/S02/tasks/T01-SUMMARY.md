---
id: T01
parent: S02
milestone: M019
key_files:
  - backend/src/common/services/practice_service.py
  - backend/src/common/api/practice.py
  - backend/src/common/services/__init__.py
  - backend/tests/contract/test_practice_evidence_contract.py
key_decisions:
  - D212 — introduce `common.services.practice_service` as the first route-facing seam bundle for practice create/lifecycle/report/audio/runtime responsibilities, moving low-risk audio/runtime helpers behind it before deeper extraction.
duration: 
verification_result: passed
completed_at: 2026-04-13T03:26:25.631Z
blocker_discovered: false
---

# T01: Added a minimal practice application seam bundle and routed audio/runtime helper wiring through it without changing the existing practice API contracts.

**Added a minimal practice application seam bundle and routed audio/runtime helper wiring through it without changing the existing practice API contracts.**

## What Happened

I started with a red-first contract addition in `backend/tests/contract/test_practice_evidence_contract.py` that required a named practice application seam inventory and a route-facing service bundle. After confirming the expected `ModuleNotFoundError`, I introduced `backend/src/common/services/practice_service.py` with five explicit seam names: session create policy, lifecycle, report read model, audio audit/signing, and runtime descriptor. The new module exposes `PracticeRouteServices`, `PracticeAudioAuditService`, `PracticeRuntimeDescriptorService`, and `build_practice_route_services(db)` so later slice tasks can extract behavior behind stable names instead of continuing to grow `common/api/practice.py` as a single orchestration file. I then updated `backend/src/common/api/practice.py` to delegate low-risk helper logic through the new seam: the shared audio audit builder now delegates to `PracticeAudioAuditService`, session response runtime assembly now delegates to `PracticeRuntimeDescriptorService`, and route/service wiring for lifecycle, evidence projection, runtime policy preview, and OSS signing now flows through `_practice_services(db)`. I also exported the new seam symbols from `backend/src/common/services/__init__.py` so downstream work can import them consistently. Existing outward response shapes, status codes, and route paths were kept unchanged; this task established the boundary surface and proved it with focused seam tests plus the existing report/lifecycle contract suite.

## Verification

First, I ran the new focused seam contract test in red state and saw it fail with `ModuleNotFoundError: No module named 'common.services.practice_service'`, confirming the test was actually locking the intended seam. After implementation, I reran the focused seam tests and they passed, proving the new inventory and bundle are present and wired to the existing lifecycle/evidence/runtime-policy dependencies. I also ran LSP diagnostics on `backend/src/common/services/practice_service.py`, `backend/src/common/services/__init__.py`, and `backend/src/common/api/practice.py`; all reported no diagnostics. Finally, I ran the task’s required verification command covering the full practice evidence contract file and the session lifecycle integration suite; all 41 tests passed, confirming the route contract remained stable while the seam was introduced.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k 'practice_application_service' -x -q` | 0 | ✅ pass | 8782ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_session_lifecycle_api.py -x -q` | 0 | ✅ pass | 13697ms |

## Deviations

Used the existing `backend/src/common/services/` package for the new seam module instead of creating a new top-level `common/*service*.py` location, which keeps the extraction aligned with the repository’s current service layout while still satisfying the planned seam boundary.

## Known Issues

Verification still emits pre-existing pytest-cov `No data was collected` warnings and a Python 3.14 `_pytest/unraisableexception.py` runtime warning about `Connection._cancel` never awaited during the lifecycle suite. These warnings were present in verification output but did not cause test failures, and this task did not change that behavior.

## Files Created/Modified

- `backend/src/common/services/practice_service.py`
- `backend/src/common/api/practice.py`
- `backend/src/common/services/__init__.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
