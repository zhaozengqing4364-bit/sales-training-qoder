---
estimated_steps: 3
estimated_files: 2
skills_used:
  - pydantic
---

# T03: Make knowledge-check reuse projected retrieval_facts for completed sessions

**Slice:** S02 — knowledge-check 与 report 共用检索真相
**Milestone:** M008

## Description

Extend `build_session_runtime_diagnostics(...)` so that when `projection_effectiveness_snapshot` already contains `retrieval_facts` (i.e., the knowledge-check route has resolved a completed-session projection), the diagnostics response includes that same `retrieval_facts` payload as a top-level field. This is the parity seam — both routes now share the same retrieval truth.

## Steps

1. **Read retrieval_facts from projection_effectiveness_snapshot.** In `build_session_runtime_diagnostics(...)`, after the existing `projection_effectiveness_snapshot` is resolved (around line 273 in the current file), extract:
   ```python
   retrieval_facts = None
   if isinstance(projection_effectiveness_snapshot, dict):
       retrieval_facts = projection_effectiveness_snapshot.get("retrieval_facts")
   ```
   Only use the projected retrieval_facts; do NOT recompute it from the live snapshot. This preserves the single-source-of-truth property.

2. **Add retrieval_facts to the diagnostics output dict.** Add a `"retrieval_facts": retrieval_facts` key to the return dict of `build_session_runtime_diagnostics(...)`. Place it after the existing `upstream_unstable` field. When `retrieval_facts` is None (live sessions, non-sales sessions, or sessions without retrieval data), the field will be `None` — this is intentional and backward-compatible.

3. **Write unit tests.** In `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py`, add tests:
   - `test_diagnostics_reuses_projection_retrieval_facts_for_completed_session` — call `build_session_runtime_diagnostics(...)` with `projection_effectiveness_snapshot={"retrieval_facts": {...}}`, assert the output contains the same retrieval_facts dict at the top level.
   - `test_diagnostics_returns_none_retrieval_facts_for_live_session` — call with `live_runtime_active=True` and no projection_effectiveness_snapshot, assert `retrieval_facts` is None.
   - `test_diagnostics_preserves_backward_compatible_fields_with_retrieval_facts` — verify that existing fields (status, summary, last_query, recent_queries, etc.) are still present and correct when retrieval_facts is also present.
   - `test_diagnostics_ignores_retrieval_facts_in_projection_for_live_session` — even if projection_effectiveness_snapshot contains retrieval_facts, a live session should return retrieval_facts=None (live session truth comes from live handler, not projection).

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| projection_effectiveness_snapshot | retrieval_facts = None, all existing fields still work | N/A (no async) | retrieval_facts = None, all existing fields still work |

## Must-Haves

- [ ] Diagnostics output dict has a top-level `retrieval_facts` field
- [ ] When `projection_effectiveness_snapshot` contains `retrieval_facts`, it is passed through verbatim (not recomputed)
- [ ] Live sessions (live_runtime_active=True) return `retrieval_facts=None` even if projection is available
- [ ] All existing backward-compatible fields (status, summary, last_*, recent_queries, etc.) remain unchanged
- [ ] Unit tests prove reuse, live-session isolation, and backward compatibility

## Verification

```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -v -k 'retrieval_facts'
```

## Inputs

- `backend/src/common/conversation/runtime_diagnostics.py` — T01 output with build_retrieval_facts, current diagnostics function
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py` — existing tests to extend

## Expected Output

- `backend/src/common/conversation/runtime_diagnostics.py` — retrieval_facts passthrough in diagnostics output
- `backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py` — new tests proving parity reuse
