---
estimated_steps: 3
estimated_files: 4
skills_used:
  - safe-grow
  - fastapi-python
  - test-driven-development
  - verification-before-completion
---

# T02: Persist retrieval ledger entries through the runtime-metrics path

**Slice:** S01 — 会话检索账本落库
**Milestone:** M008

## Description

Once T01 defines normalized ledger events, wire them through the existing runtime-metrics persistence path so one retrieval attempt becomes one bounded snapshot update. The executor should load `safe-grow`, `fastapi-python`, `test-driven-development`, and `verification-before-completion` before coding. Preserve copy-on-write snapshot semantics and the current warning-only failure surface.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `persist_runtime_metrics_to_session(...)` | leave the previous snapshot intact and fail the focused regression instead of mutating in place | treat as incomplete persistence and keep the old snapshot visible | reject invalid runtime metrics rather than half-writing the session row |
| `StepFunRealtimeHandler._record_knowledge_runtime_metric(...)` | preserve the existing warning path and fail the new regression if ledger events are dropped | keep the preexisting persistence cadence; do not add loops or retries | normalize malformed event payloads before commit or reject them cleanly |

## Load Profile

- **Shared resources**: async DB session, `practice_sessions.voice_policy_snapshot` JSON field, and deep-copy/merge work.
- **Per-operation cost**: one bounded ledger append plus the existing snapshot merge/commit.
- **10x breakpoint**: deep-copy churn or repeated commit amplification if persistence is no longer one-write-per-event.

## Negative Tests

- **Malformed inputs**: missing runtime metrics or malformed ledger state should fail safely without mutating the original snapshot.
- **Error paths**: handler-level failure paths must still preserve `last_status`/`last_error` while writing a bounded ledger entry when possible.
- **Boundary conditions**: repeated persistence keeps the ledger capped and preserves copy-on-write snapshot semantics.

## Steps

1. Extend `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py` so runtime-metric merges carry the bounded ledger into `practice_sessions.voice_policy_snapshot` without mutating the original snapshot object.
2. Update `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` to pass the richer ledger-event payload through `_record_knowledge_runtime_metric(...)` while keeping the current warning-only failure surface.
3. Add focused unit coverage proving copy-on-write persistence, capped repeated writes, and handler-level persistence for hit and failure paths.

## Must-Haves

- [ ] Snapshot persistence remains copy-on-write.
- [ ] Existing flat metrics stay readable after ledger writes.
- [ ] One retrieval attempt still maps to one bounded snapshot update, not a second persistence channel.

## Verification

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_runtime_metrics_helpers.py backend/tests/unit/test_stepfun_realtime_handler.py`
- Inspect test assertions to confirm the original snapshot object is unchanged while the persisted copy carries the bounded ledger.

## Observability Impact

- Signals added/changed: persisted session snapshots now retain the bounded retrieval ledger alongside the existing last-status/last-error counters.
- How a future agent inspects this: read one `PracticeSession.voice_policy_snapshot` row or rerun the persistence-focused unit pack.
- Failure state exposed: whether ledger events survive merge/commit and whether the original snapshot object was mutated in place.

## Inputs

- `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py` — current merge/commit seam for runtime metrics.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — current handler callback that records retrieval metrics.
- `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py` — T01 ledger-event helpers consumed by the persistence layer.
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — T01 search outcomes emitting ledger events.
- `backend/tests/unit/test_stepfun_runtime_metrics_helpers.py` — current persistence-helper coverage.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — current handler persistence coverage.

## Expected Output

- `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py` — ledger-aware runtime-metrics persistence.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — handler callback passing bounded ledger events through the existing persistence path.
- `backend/tests/unit/test_stepfun_runtime_metrics_helpers.py` — persistence regressions for copy-on-write and ledger caps.
- `backend/tests/unit/test_stepfun_realtime_handler.py` — handler regressions for hit/failure ledger persistence.
