---
id: T04
parent: S02
milestone: M007
provides: []
requires: []
affects: []
key_files: [".artifacts/m007-s02-same-session/session-proof.md", ".gsd/KNOWLEDGE.md", ".gsd/milestones/M007/slices/S02/tasks/T04-SUMMARY.md"]
key_decisions: ["Treat the post-end `status="scoring"` + replay `[SESSION_NOT_COMPLETED]` state as a backend completion drift, not a localhost host/cookie problem, when canonical `/practice/{id}/report` is already readable on the same session.", "Use the learner page’s own websocket connection for localhost text turns once local legacy ASR proved environment-broken; that kept the proof on the shipped route family instead of inventing a side channel."]
patterns_established: []
drill_down_paths: []
observability_surfaces: []
duration: ""
verification_result: "Ran the required backend and web verification suites from repo root; both passed. In browser verification on localhost, proved the learner route could render the stable same-session cue on a real StepFun session, proved replay is blocked before completion, proved the canonical report route is readable while the session is still `scoring`, and proved replay remains blocked afterward because the session never leaves `scoring`."
completed_at: 2026-03-28T08:42:01.522Z
blocker_discovered: true
---

# T04: Captured localhost learner/report proof and documented the scoring-to-replay unlock drift that blocks a full same-session replay close-out.

> Captured localhost learner/report proof and documented the scoring-to-replay unlock drift that blocks a full same-session replay close-out.

## What Happened
---
id: T04
parent: S02
milestone: M007
key_files:
  - .artifacts/m007-s02-same-session/session-proof.md
  - .gsd/KNOWLEDGE.md
  - .gsd/milestones/M007/slices/S02/tasks/T04-SUMMARY.md
key_decisions:
  - Treat the post-end `status="scoring"` + replay `[SESSION_NOT_COMPLETED]` state as a backend completion drift, not a localhost host/cookie problem, when canonical `/practice/{id}/report` is already readable on the same session.
  - Use the learner page’s own websocket connection for localhost text turns once local legacy ASR proved environment-broken; that kept the proof on the shipped route family instead of inventing a side channel.
duration: ""
verification_result: passed
completed_at: 2026-03-28T08:42:01.523Z
blocker_discovered: true
---

# T04: Captured localhost learner/report proof and documented the scoring-to-replay unlock drift that blocks a full same-session replay close-out.

**Captured localhost learner/report proof and documented the scoring-to-replay unlock drift that blocks a full same-session replay close-out.**

## What Happened

Ran the localhost same-session proof on the shipped learner/report/replay route family with frontend and backend aligned on localhost. The first legacy audio attempt showed the browser was sending real audio chunks but local streaming ASR was broken on this machine (`AttributeError: module 'torch' has no attribute '_C'`), so that path could not produce a trustworthy learner cue. I then drove real `text` turns through the learner page’s own websocket connection so the proof stayed on the shipped `/practice/{sessionId}` route. A legacy text session proved the learner cue could render but end-session fell into `[SUMMARY_GENERATION_FAILED] [CONTEXT_NOT_FOUND]`. A fresh `stepfun_realtime` session proved the stable same-session cue on `/practice/{id}`, proved replay stays blocked before completion, and proved `/practice/{id}/report` remains readable while the same session is in `scoring`. The blocker is that the StepFun session never left `scoring`: even after end returned 200, replay remained `[SESSION_NOT_COMPLETED]` while report stayed readable. Backend logs showed `practice_session_evidence_persisted evidence_source=stepfun_message_analysis`, then `report_generation_triggered`, then `report_generation_failed [NO_STAGE_RESULTS]`, followed by successful projection-backed report reads. Wrote the durable proof to `.artifacts/m007-s02-same-session/session-proof.md` and appended the new traps to `.gsd/KNOWLEDGE.md`.

## Verification

Ran the required backend and web verification suites from repo root; both passed. In browser verification on localhost, proved the learner route could render the stable same-session cue on a real StepFun session, proved replay is blocked before completion, proved the canonical report route is readable while the session is still `scoring`, and proved replay remains blocked afterward because the session never leaves `scoring`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py` | 0 | ✅ pass | 9700ms |
| 2 | `npm test -- --run 'web/src/hooks/websocket/message-handlers.test.ts' 'web/src/app/(user)/practice/[sessionId]/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` | 0 | ✅ pass | 10300ms |
| 3 | `browser_assert report route on /practice/3830822a-505d-4db0-a9fd-167e02e20d45/report shows 训练评估报告 + 主张证据状态 + 销售推进结果 + 下一轮销售目标` | 0 | ✅ pass | 0ms |
| 4 | `browser_assert replay route on /practice/3830822a-505d-4db0-a9fd-167e02e20d45/replay still shows [SESSION_NOT_COMPLETED] with Current status: scoring after end lifecycle` | 0 | ✅ pass | 0ms |


## Deviations

Did not use the browser microphone path for the final proof because the local legacy ASR dependency on this machine is broken (`torch._C`), so the raw audio path would only have proven an environment failure. Drove real `text` turns through the page’s existing websocket connection instead.

## Known Issues

A `stepfun_realtime` sales session can currently reach this split state on localhost: canonical `/practice/{id}/report` is readable, but the session remains `status="scoring"` and `/practice/{id}/replay` never unlocks because backend terminal report generation logs `report_generation_failed [NO_STAGE_RESULTS]`.

## Files Created/Modified

- `.artifacts/m007-s02-same-session/session-proof.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/milestones/M007/slices/S02/tasks/T04-SUMMARY.md`


## Deviations
Did not use the browser microphone path for the final proof because the local legacy ASR dependency on this machine is broken (`torch._C`), so the raw audio path would only have proven an environment failure. Drove real `text` turns through the page’s existing websocket connection instead.

## Known Issues
A `stepfun_realtime` sales session can currently reach this split state on localhost: canonical `/practice/{id}/report` is readable, but the session remains `status="scoring"` and `/practice/{id}/replay` never unlocks because backend terminal report generation logs `report_generation_failed [NO_STAGE_RESULTS]`.
