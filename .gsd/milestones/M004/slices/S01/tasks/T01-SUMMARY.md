---
id: T01
parent: S01
milestone: M004
key_files:
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/conversation/schemas.py
  - backend/tests/unit/test_replay_service.py
  - backend/tests/integration/test_replay_api.py
  - .gsd/KNOWLEDGE.md
  - .gsd/DECISIONS.md
key_decisions:
  - Derived replay/highlight explanation fields from `SessionEvidenceService` projection instead of building a second truth line in replay handlers.
  - Introduced a nested `learning_evidence` contract for highlighted turns while preserving flat compatibility fields like `sales_stage`, `stage_name`, `context`, and `suggested_response`.
  - Updated the Pydantic response schemas in lockstep with service changes so FastAPI `response_model` serialization would not trim the new fields.
duration: ""
verification_result: passed
completed_at: 2026-03-25T10:42:31.249Z
blocker_discovered: false
---

# T01: Lock replay/highlight learning evidence to the shared session projection with a stable nested contract

**Lock replay/highlight learning evidence to the shared session projection with a stable nested contract**

## What Happened

I started with focused red-green coverage on the replay service and replay API so the new contract had a failing boundary before production changes. The new tests asserted that highlighted replay turns and `/api/v1/sessions/{id}/highlights` expose structured learning evidence tied to the real turn: reason, stage, nearby context, suggested better response, and issue-family linkage.

To make that pass without creating a second scorer, I moved highlight enrichment onto the existing `SessionEvidenceService` projection line. `ReplayService.get_replay_data()` now enriches highlighted replay messages with a nested `learning_evidence` object, and `get_highlights()` now builds its payload from the same projection instead of re-querying highlight rows and stitching context separately. The learning object carries the stable issue family from the session conclusion, optional objection family from transcript metadata, structured stage data, nearby context, linked issue/goal payloads, and the existing suggested-response derivation.

I also extended `SessionEvidenceService.serialize_message()` to carry `stage_name`, because replay/highlight consumers need the display label from the same authority line. Then I updated `backend/src/common/conversation/schemas.py` so FastAPI would actually serialize the new fields; without that, the service could build `stage_name`, `context`, and `learning_evidence` and the response model would still silently drop them. Finally, I recorded the compatibility decision in `.gsd/DECISIONS.md` and appended the response-model filtering gotcha to `.gsd/KNOWLEDGE.md` for downstream slices.

## Verification

Fresh verification: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_replay_service.py backend/tests/integration/test_replay_api.py` passed with 43/43 tests green. This covers the current slice’s backend drift detectors for replay service and replay API. I also ran LSP diagnostics on `backend/src/common/conversation/replay.py`, `backend/src/common/conversation/session_evidence.py`, `backend/src/common/conversation/schemas.py`, `backend/tests/unit/test_replay_service.py`, and `backend/tests/integration/test_replay_api.py`; all returned no diagnostics. The slice’s frontend replay/highlight component checks belong to T02 and were not run in this backend task.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_replay_service.py backend/tests/integration/test_replay_api.py` | 0 | ✅ pass | 5454ms |


## Deviations

Minor local adaptation: `backend/src/common/conversation/api.py` did not need code changes once the replay service and response schemas were aligned, but `backend/src/common/conversation/schemas.py` did need changes so FastAPI would stop filtering the new payload fields. I also updated `.gsd/KNOWLEDGE.md` because the schema-filter behavior is a recurring gotcha for this route family.

## Known Issues

Repo-root focused backend pytest still emits the existing `pytest-cov` warnings (`Module src was never imported` / `No data was collected`) even when the targeted suites pass. The functional verification for this task is green, but the coverage warning noise remains unfixed.

## Files Created/Modified

- `backend/src/common/conversation/replay.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/src/common/conversation/schemas.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/integration/test_replay_api.py`
- `.gsd/KNOWLEDGE.md`
- `.gsd/DECISIONS.md`
