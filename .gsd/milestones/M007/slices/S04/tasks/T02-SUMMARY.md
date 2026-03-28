---
id: T02
parent: S04
milestone: M007
provides: []
requires: []
affects: []
key_files: ["backend/tests/contract/test_practice_evidence_contract.py", "backend/tests/integration/test_replay_api.py", "web/src/lib/api/client.ts", "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx", ".gsd/KNOWLEDGE.md"]
key_decisions: ["Assert post-finalization parity against the canonical projection shared by report/replay/highlights instead of hardcoding one expected issue family.", "Map [SESSION_NOT_COMPLETED] to explicit learner-facing replay copy rather than surfacing raw backend text in the blocked replay state."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the exact task-plan verification commands from repo root. The lifecycle boundary command proved the end response still returns status=scoring while background finalization can persist the same session to completed. The contract and integration suites proved report readability during scoring, replay/highlights gating before completion, and parity after finalization. The quoted repo-root Vitest command proved the learner report/replay pages still preserve the blocked-versus-unlocked copy on the shipped route family."
completed_at: 2026-03-28T11:34:25.541Z
blocker_discovered: false
---

# T02: Locked same-session report/replay closure proofs around persisted completion and made the replay page show an explicit scoring-state block message.

> Locked same-session report/replay closure proofs around persisted completion and made the replay page show an explicit scoring-state block message.

## What Happened
---
id: T02
parent: S04
milestone: M007
key_files:
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_replay_api.py
  - web/src/lib/api/client.ts
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Assert post-finalization parity against the canonical projection shared by report/replay/highlights instead of hardcoding one expected issue family.
  - Map [SESSION_NOT_COMPLETED] to explicit learner-facing replay copy rather than surfacing raw backend text in the blocked replay state.
duration: ""
verification_result: passed
completed_at: 2026-03-28T11:34:25.543Z
blocker_discovered: false
---

# T02: Locked same-session report/replay closure proofs around persisted completion and made the replay page show an explicit scoring-state block message.

**Locked same-session report/replay closure proofs around persisted completion and made the replay page show an explicit scoring-state block message.**

## What Happened

Tightened the backend proof surface instead of changing route behavior. The contract test now proves the full same-session truth line: report stays readable while the session is still scoring, replay and highlights stay blocked with [SESSION_NOT_COMPLETED], and after ReportGenerationTrigger persists completion the report, replay, and highlights all agree on the same SessionEvidenceService projection. The replay integration test now also checks report availability during scoring and parity after background finalization on the real fire-and-forget completion path. On the frontend, the API client maps [SESSION_NOT_COMPLETED] to explicit learner-facing copy and the replay page test proves the blocked replay state stays visible instead of leaking raw backend text. During verification I found that once strong ROI evidence promotes claim_truth to evidence_verified, the canonical focus can legitimately shift from an evidence-gap family to next_step_gap, so the locked assertions compare canonical parity and drift from the stale scoring snapshot rather than hardcoding a guessed family.

## Verification

Ran the exact task-plan verification commands from repo root. The lifecycle boundary command proved the end response still returns status=scoring while background finalization can persist the same session to completed. The contract and integration suites proved report readability during scoring, replay/highlights gating before completion, and parity after finalization. The quoted repo-root Vitest command proved the learner report/replay pages still preserve the blocked-versus-unlocked copy on the shipped route family.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_session_lifecycle_api.py -k "report_generation or scoring"` | 0 | ✅ pass | 9200ms |
| 2 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k "same_session or knowledge_check or replay"` | 0 | ✅ pass | 9200ms |
| 3 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_replay_api.py -k "finalization or scoring or replay_unlock"` | 0 | ✅ pass | 17600ms |
| 4 | `npm test -- --run 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 8600ms |


## Deviations

None.

## Known Issues

Focused backend pytest still emits the pre-existing pytest-cov warnings about `Module src was never imported` / `No data was collected`; the commands exited 0 and assertions passed, so coverage configuration was left unchanged in this task.

## Files Created/Modified

- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_replay_api.py`
- `web/src/lib/api/client.ts`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `.gsd/KNOWLEDGE.md`


## Deviations
None.

## Known Issues
Focused backend pytest still emits the pre-existing pytest-cov warnings about `Module src was never imported` / `No data was collected`; the commands exited 0 and assertions passed, so coverage configuration was left unchanged in this task.
