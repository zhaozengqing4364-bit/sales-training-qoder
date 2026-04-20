---
id: T02
parent: S02
milestone: M019
key_files:
  - backend/src/common/services/practice_session_service.py
  - backend/src/common/services/practice_report_service.py
  - backend/src/common/services/practice_service.py
  - backend/src/common/services/__init__.py
  - backend/src/common/api/practice.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D213 — keep `common.services.practice_service` as a compatibility bundle that composes the new `practice_session_service` and `practice_report_service` modules while routes delegate through those focused services.
duration: 
verification_result: mixed
completed_at: 2026-04-13T03:51:15.781Z
blocker_discovered: false
---

# T02: Extracted practice session/report application services and rewired practice routes to delegate create, lifecycle, report, and audio-segment orchestration without changing the existing API contracts.

**Extracted practice session/report application services and rewired practice routes to delegate create, lifecycle, report, and audio-segment orchestration without changing the existing API contracts.**

## What Happened

I started red-first by adding a focused contract that required the practice route bundle to expose extracted `practice_session_service` and `practice_report_service` seams; the proof failed with `ModuleNotFoundError`, confirming the route-facing seam did not exist yet. I then added `backend/src/common/services/practice_session_service.py` to own session creation, retry-focus shaping, runtime descriptor assembly, lifecycle orchestration, and lifecycle response shaping, plus `backend/src/common/services/practice_report_service.py` to own report assembly, audio-audit projection, OSS signing/audio-segment persistence, and retry-entry reuse. `backend/src/common/services/practice_service.py` was reduced to a compatibility bundle that composes the new services, and `backend/src/common/services/__init__.py` now re-exports the expanded seam surface. After that, I rewired `backend/src/common/api/practice.py` so the route handlers delegate session creation, lifecycle transitions, terminal report building, projection-backed report reads, and audio upload/register/failure flows through the extracted services while keeping auth checks, request parsing, response envelopes, and HTTP codes in the route layer. The first full gate exposed one real regression: lifecycle logs moved onto a module-local logger, so the existing route-level observability proof stopped seeing `practice_session_lifecycle_transition_applied` and `practice_session_terminal_connection_close`. I fixed that by injecting the route logger into the extracted session services from `_practice_services(db)` instead of changing the outward logging contract, then reran the failing lifecycle proof and the full gate to green.

## Verification

Red-first contract proof failed exactly because the new extracted modules did not exist yet, then passed once the services and bundle fields were added. LSP diagnostics stayed clean on the new session/report service modules, the compatibility bundle, and the rewired route file. A targeted lifecycle proof then confirmed the logger-injection fix preserved the existing route-level lifecycle observability contract, and the task’s required verification command finished 47/47 green across the practice evidence contract suite, evidence-flow integration suite, and session lifecycle API suite.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k "exposes_extracted_session_and_report_services" -x -q` | 1 | ❌ fail | 5560ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k "exposes_extracted_session_and_report_services" -x -q` | 0 | ✅ pass | 3500ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_session_lifecycle_api.py -k "idempotent_and_logs_unified_terminal_context" -x -q` | 0 | ✅ pass | 3840ms |
| 4 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_session_lifecycle_api.py -x -q` | 0 | ✅ pass | 14120ms |

## Deviations

Kept `common.services.practice_service` as the route-facing compatibility bundle instead of making routes import the new session/report modules directly. This preserves the T01 seam and lets downstream work adopt the extracted modules incrementally behind one stable import surface.

## Known Issues

The final backend gate still emits the pre-existing pytest-cov `Module src was never imported` / `No data was collected` warnings plus the Python 3.14 `_pytest/unraisableexception.py` runtime warning about `Connection._cancel` never awaited during async teardown. These warnings were already present in this area and did not block the green verification result.

## Files Created/Modified

- `backend/src/common/services/practice_session_service.py`
- `backend/src/common/services/practice_report_service.py`
- `backend/src/common/services/practice_service.py`
- `backend/src/common/services/__init__.py`
- `backend/src/common/api/practice.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `.gsd/KNOWLEDGE.md`
