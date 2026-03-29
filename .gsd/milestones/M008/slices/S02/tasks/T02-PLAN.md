---
estimated_steps: 4
estimated_files: 2
skills_used:
  - pydantic
---

# T02: Attach retrieval_facts into report projection for sales sessions

**Slice:** S02 — knowledge-check 与 report 共用检索真相
**Milestone:** M008

## Description

Wire the shared `build_retrieval_facts(...)` (from T01) into `SessionEvidenceService.build_projection(...)` so that completed sales sessions get `effectiveness_snapshot["retrieval_facts"]` derived from the persisted voice_policy_snapshot. This is a read-time projection overlay — it must not mutate the persisted `session.effectiveness_snapshot` row.

## Steps

1. **Import build_retrieval_facts.** In `backend/src/common/conversation/session_evidence.py`, add an import for `build_retrieval_facts` from `common.conversation.runtime_diagnostics`.

2. **Call build_retrieval_facts in build_projection.** Inside `build_projection(...)`, after the sales alignment overlay is resolved (around the line where `projection_snapshot` is finalized), call `build_retrieval_facts(session.voice_policy_snapshot)` and, if the result is not None, overlay it:
   ```python
   retrieval_facts = build_retrieval_facts(getattr(session, "voice_policy_snapshot", None))
   if isinstance(retrieval_facts, dict):
       projection_snapshot = {**projection_snapshot, "retrieval_facts": retrieval_facts}
   ```
   This follows the existing pattern where `claim_truth` and `main_issue`/`next_goal` are overlaid as `{**projection_snapshot, key: value}`.

3. **Respect scenario_type.** Only attach retrieval_facts for sales sessions. Presentation sessions already have a separate review path that resets effectiveness_snapshot to None. The existing `resolved_scenario_type` variable in build_projection can gate this.

4. **Write unit tests.** In `backend/tests/unit/test_session_evidence_service.py`, add test methods inside `TestSessionEvidenceService`:
   - `test_get_projection_attaches_retrieval_facts_for_completed_sales_session` — build a session with populated `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts`, run `build_projection`, assert `projection.effectiveness_snapshot["retrieval_facts"]` is present with expected keys.
   - `test_get_projection_does_not_mutate_persisted_effectiveness_snapshot` — same setup, but verify that `session.effectiveness_snapshot` dict does not contain `retrieval_facts` after projection (the overlay is copy-on-write).
   - `test_get_projection_skips_retrieval_facts_when_voice_policy_snapshot_missing` — session with `voice_policy_snapshot=None`, verify no retrieval_facts key in output.
   - Use the existing `SimpleNamespace` session fixture pattern from the file (see lines ~102, ~199, ~269).

## Must-Haves

- [ ] `retrieval_facts` appears in `projection.effectiveness_snapshot` for completed sales sessions with retrieval ledger data
- [ ] The persisted `session.effectiveness_snapshot` dict is NOT mutated (copy-on-write overlay)
- [ ] Presentation sessions do not get retrieval_facts (they have separate review path)
- [ ] Sessions without voice_policy_snapshot gracefully skip retrieval_facts (no error)
- [ ] Unit tests prove the projection attachment and non-mutation properties

## Verification

```bash
cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -v -k 'retrieval_facts'
```

## Inputs

- `backend/src/common/conversation/session_evidence.py` — where build_projection lives
- `backend/src/common/conversation/runtime_diagnostics.py` — T01 output, provides build_retrieval_facts(...)
- `backend/tests/unit/test_session_evidence_service.py` — existing tests to extend

## Expected Output

- `backend/src/common/conversation/session_evidence.py` — import + retrieval_facts overlay in build_projection
- `backend/tests/unit/test_session_evidence_service.py` — new test methods proving retrieval_facts attachment
