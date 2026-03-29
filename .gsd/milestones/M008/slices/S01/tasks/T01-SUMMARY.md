---
id: T01
parent: S01
milestone: M008
provides:
  - A red-first regression net for the provider-neutral retrieval-ledger seam in the helper/searcher layer.
key_files:
  - backend/tests/unit/test_stepfun_knowledge_helpers.py
  - backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
key_decisions:
  - Stayed inside the T01 helper/searcher boundary and drove the ledger shape from failing tests before changing production code.
patterns_established:
  - Recovery should resume from the new focused pytest red: implement the ledger helper in `stepfun_knowledge_helpers.py`, then thread `ledger_event` through `search_internal_knowledge(...)` without widening into T02 persistence work.
observability_surfaces:
  - Focused pytest failure on the helper/searcher pack; no runtime observability surface shipped yet.
duration: ""
verification_result: partial
completed_at: 2026-03-29T23:05:00+08:00
blocker_discovered: false
---

# T01: Started the retrieval-ledger red/green pass, but the production helper/searcher seam is not finished yet.

**Prepared red tests for provider-neutral retrieval-ledger normalization in the helper/searcher layer; production helper/searcher implementation is still unfinished.**

## What Happened

I activated the required skills, read the slice/task plans plus the current helper/searcher/runtime-metrics code, and confirmed the gate failure was not only a missing markdown artifact: T01’s helper/searcher seam still had no retrieval-ledger event helper or ledger-aware callback payload.

I then switched to a red-first pass and updated the two planned focused test files:

- `backend/tests/unit/test_stepfun_knowledge_helpers.py` now expects a `build_knowledge_retrieval_ledger_event(...)` helper plus bounded `recent_attempts` ledger behavior on the metrics side.
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` now expects `search_internal_knowledge(...)` to emit a normalized `ledger_event` for missing-query, no-kb, kb-not-ready, hit, miss, and search-failed outcomes.

The first fresh pytest run failed exactly where the seam is still missing: collection stops because `build_knowledge_retrieval_ledger_event` does not exist yet in `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`. No production helper/searcher code was landed after that red point, so this task is not complete.

## Verification

Ran the task’s focused helper/searcher verification command after writing the red tests. It failed during collection with an import error from `backend/tests/unit/test_stepfun_knowledge_helpers.py`: `cannot import name 'build_knowledge_retrieval_ledger_event' from 'sales_bot.websocket.components.stepfun_knowledge_helpers'`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_knowledge_helpers.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` | 2 | ❌ fail | unknown |

## Diagnostics

Resume from the current red point:

1. Implement `build_knowledge_retrieval_ledger_event(...)` and related normalization helpers in `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`.
2. Add ledger-aware defaults/helpers in `backend/src/sales_bot/websocket/components/stepfun_helpers.py` (`recent_attempts` cap/normalization).
3. Thread `ledger_event` through `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` record-metric calls.
4. Make the minimal compatibility adjustment needed so the live callback seam accepts `ledger_event` without leaking into T02 persistence work yet.
5. Re-run the same focused pytest command until it passes, then proceed to the required task completion flow.

## Deviations

Switched to recovery mode before production edits were finished because the unit hit the hard timeout and the required durable task artifact was still missing.

## Known Issues

- T01 is not complete.
- `backend/tests/unit/test_stepfun_knowledge_helpers.py` currently imports a non-existent helper: `build_knowledge_retrieval_ledger_event`.
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` now expects `ledger_event` in the callback kwargs, but production searcher code still only sends the flat metric fields.

## Files Created/Modified

- `backend/tests/unit/test_stepfun_knowledge_helpers.py` — added red tests for ledger-event normalization and bounded recent-attempt trimming.
- `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py` — rewrote the focused orchestration tests to require truthful `ledger_event` payloads for hit/miss/failure/no-op outcomes.
- `.gsd/milestones/M008/slices/S01/tasks/T01-SUMMARY.md` — recorded the current red state and exact resume steps.
