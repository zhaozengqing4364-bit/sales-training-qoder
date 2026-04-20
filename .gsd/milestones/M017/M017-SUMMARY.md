---
id: M017
title: "Realtime contract 与 concurrency proof 收口"
status: complete
completed_at: 2026-04-11T22:22:44.569Z
key_decisions:
  - D197 — Use optimistic compare-and-swap on `PracticeSession.status` and converge stale non-terminal writers to the persisted terminal state instead of introducing row locks.
  - D198 — Keep the lifecycle concurrency contract in focused lifecycle unit/integration tests and use the repo-root pytest command as the durable regression entrypoint.
  - D199 — Keep `use-practice-websocket` as the transport/outbound orchestrator and keep inbound protocol projection in `websocket/message-handlers`.
  - D200 — Treat reconnect as a fresh transport epoch: only the initial handshake may replay queued outbound messages, and interrupt owns queued-outbound/local-backpressure cleanup.
  - D201 — Keep presentation upload/resource-race discovery code-adjacent in `backend/src/presentation_coach/api/presentations.py` and prioritize proving in-place replace before broad lock work.
  - D202 — Use a per-request `get_db` override on a shared file-backed SQLite engine for truthful concurrent presentation replace proofs.
key_files:
  - backend/src/common/db/session_lifecycle.py
  - backend/tests/unit/test_session_lifecycle_service.py
  - backend/tests/integration/test_session_lifecycle_api.py
  - web/src/hooks/use-practice-websocket.ts
  - web/src/hooks/use-practice-websocket.test.ts
  - web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - backend/src/presentation_coach/api/presentations.py
  - backend/tests/contract/test_presentations.py
  - backend/tests/integration/test_presentation_flow.py
  - backend/tests/integration/test_presentation_delete_permissions.py
lessons_learned:
  - In this repository, milestone close-out must compare branch code against `origin/001-ai-practice-system`, not `main`, or the non-`.gsd` diff gate produces a false failure.
  - For this class of concurrency milestone, the trustworthy acceptance bundle is the assembled backend lifecycle + presentation-mutation proof plus the focused web websocket proof; one slice-local green test is not enough.
  - Code-adjacent discovery artifacts are durable only when they stay paired with executable contract tests that separate proved races from still-unproved suspicion.
---

# M017: Realtime contract 与 concurrency proof 收口

**Closed M017 by turning lifecycle, websocket, and presentation-mutation concurrency risks into durable, executable contracts with fresh backend/web verification evidence.**

## What Happened

M017 closed three previously high-risk but under-proved realtime/concurrency seams without broadening into speculative rewrites. S01 turned session lifecycle pause/resume/end races into an explicit backend contract by converging stale non-terminal writers at the `PracticeSession.status` authority seam with optimistic compare-and-swap, while preserving the intentional sales=`scoring` versus presentation=`completed` terminal split. S02 then locked the practice websocket seam so reconnect/backpressure/interrupt behavior now obeys a fresh transport-epoch contract: only the initial handshake may replay queued outbound intent, interrupt owns local cleanup, and the learner shell distinguishes automatic recovery from terminal failure. S03 converted presentation mutation risk from audit suspicion into code-adjacent discovery truth: in-place replace is the first confirmed concurrent-writer race, delete currently exposes a live-session route/policy gap, and upload-new remains an unproved inventory surface rather than a justified lock rollout. Fresh milestone verification reran the assembled backend and web proof bundles, confirmed the core code files still carry no diagnostics, and showed that the milestone shipped real non-`.gsd` code against the repository’s real integration branch (`origin/001-ai-practice-system`).

## Success Criteria Results

## Success criteria verification

This roadmap did not expose a separate `Success Criteria` block in the milestone file; close-out therefore verified the slice-overview `After this` outcomes directly.

- ✅ **Pause/resume/end concurrency behavior is repeatably proved and the state-convergence rule is clear.**
  - Fresh backend verification passed: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_session_lifecycle_service.py backend/tests/integration/test_session_lifecycle_api.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q` → **38 passed**.
  - The lifecycle-focused portion of that bundle covers the S01 proof seam (`backend/tests/unit/test_session_lifecycle_service.py`, `backend/tests/integration/test_session_lifecycle_api.py`) that S01 had previously closed with stale-writer convergence and terminal-state split assertions.
  - Fresh LSP diagnostics on `backend/src/common/db/session_lifecycle.py`, `backend/tests/unit/test_session_lifecycle_service.py`, and `backend/tests/integration/test_session_lifecycle_api.py` returned **No diagnostics**.

- ✅ **Practice websocket reconnect/backpressure/interrupt contract is clear and the focused tests stay green.**
  - Fresh web verification passed: `npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"` → **3 files passed, 33 tests passed**.
  - The passing bundle covers the S02 authority seam for reconnect epoch cleanup, interrupt/backpressure ownership, and learner reconnect guidance.
  - Fresh LSP diagnostics on `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/use-practice-websocket.test.ts`, `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`, and `web/src/app/\(user\)/practice/\[sessionId\]/page.test.tsx` returned **No diagnostics**.

- ✅ **Presentation upload / replace / delete concurrency risk is converted into an evidence-based next-step boundary.**
  - Fresh backend verification passed the S03 discovery/proof seam: `backend/tests/contract/test_presentations.py`, `backend/tests/integration/test_presentation_flow.py`, and `backend/tests/integration/test_presentation_delete_permissions.py` are all included in the same **38 passed** backend bundle above.
  - The route-level discovery artifact remains code-adjacent in `backend/src/presentation_coach/api/presentations.py`, and the passing tests continue to distinguish: replace = confirmed race, delete = confirmed guard/policy gap, upload-new = still inventory-only.
  - Fresh LSP diagnostics on `backend/src/presentation_coach/api/presentations.py`, `backend/tests/contract/test_presentations.py`, `backend/tests/integration/test_presentation_flow.py`, and `backend/tests/integration/test_presentation_delete_permissions.py` returned **No diagnostics**.

## Horizontal checklist
- ℹ️ No separate `Horizontal Checklist` section was present in the roadmap content available to close-out. Nothing additional was left unchecked beyond the verified slice outcomes above.

## Definition of Done Results

## Definition of done verification

- ✅ **All roadmap slices are complete.**
  - `gsd_milestone_status("M017")` shows **3/3 slices complete**: S01 `3/3` tasks done, S02 `3/3`, S03 `3/3`.

- ✅ **All slice summaries exist.**
  - `find .gsd/milestones/M017 -maxdepth 5 \( -name 'S*-SUMMARY.md' -o -name 'T*-SUMMARY.md' -o -name 'M017-ROADMAP.md' -o -name 'M017-SUMMARY.md' \) | sort` confirmed the roadmap plus every slice/task summary source required for close-out:
    - `.gsd/milestones/M017/slices/S01/S01-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S01/tasks/T01-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S01/tasks/T02-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S01/tasks/T03-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S02/S02-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S02/tasks/T01-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S02/tasks/T02-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S02/tasks/T03-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S03/S03-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S03/tasks/T01-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S03/tasks/T02-SUMMARY.md`
    - `.gsd/milestones/M017/slices/S03/tasks/T03-SUMMARY.md`

- ✅ **The milestone shipped real code, not only planning artifacts.**
  - The branch-level diff gate must use this repo’s real integration branch rather than `main`. `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'` returned a non-empty non-`.gsd` diff, so M017 sits on real code changes.

- ✅ **Cross-slice integration points remain coherent.**
  - S01’s lifecycle terminal-state contract stays green in the fresh backend bundle.
  - S02’s reconnect/backpressure/interrupt contract stays green in the fresh web bundle.
  - S03’s discovery proof stays green in the fresh backend bundle and still narrows mitigation scope instead of contradicting S01/S02.
  - Together, the milestone verifies the assembled truth line: backend lifecycle state authority, frontend websocket transport epoch behavior, and presentation mutation discovery boundaries all remain explicit and regression-tested.

## Decision re-evaluation

| Decision | Re-evaluation | Status |
|---|---|---|
| D197 — optimistic compare-and-swap on `PracticeSession.status` with stale-writer convergence to persisted terminal state | Fresh lifecycle proof still passes and no evidence emerged that row locks are required first. | Valid |
| D198 — keep lifecycle concurrency contract in focused unit/integration lifecycle tests | Fresh backend rerun confirmed the focused lifecycle seam remains the durable regression entrypoint. | Valid |
| D199 — keep `use-practice-websocket` as transport/outbound orchestrator and keep inbound projection in `websocket/message-handlers` | Fresh web rerun still proves the boundary works; no new evidence suggests another refactor seam is needed first. | Valid |
| D200 — treat reconnect as a fresh transport epoch and let interrupt own queued-outbound/local-backpressure cleanup | Fresh web rerun still proves stale dead-socket intent is dropped and learner reconnect UX matches transport truth. | Valid |
| D201 — keep presentation mutation discovery code-adjacent and prioritize proving replace before broad lock work | Fresh backend rerun still shows replace as the first confirmed race and no proof justifies upload-wide locking yet. | Valid, revisit after replace serialization lands |
| D202 — use per-request `get_db` override on a shared file-backed SQLite engine for truthful concurrent replace proofs | The passing S03 proof still depends on this truthful concurrency harness; no better narrower harness emerged. | Valid |

## Requirement Outcomes

## Requirement status transitions

- No requirement status transitions were recorded for M017.
- The preloaded milestone context reported **Requirements Advanced: None**, **Requirements Validated: None**, and **Requirements Invalidated or Re-scoped: None**.
- Accordingly, no `gsd_requirement_update` call was needed during close-out.

## Deviations

Milestone close-out intentionally relied on focused backend/web proof bundles and code-adjacent discovery artifacts rather than broad localhost/browser UAT. That was consistent with M017’s goal: close contract and concurrency evidence gaps first, not expand into a new end-to-end feature slice.

## Follow-ups

1. Implement the first concrete mitigation where the evidence is strongest: serialize or CAS-guard presentation in-place replace by `presentation_id`.
2. Decide the presentation delete policy for active sessions explicitly (route-level blocker versus another intentional rule) instead of leaving the current guard gap implicit.
3. Add production-facing telemetry for lifecycle concurrency conflicts and reconnect exhaustion if future milestones need runtime-volume evidence beyond focused proof.
4. Keep the pre-existing presentation-coach timezone mismatch and `Connection._cancel` runtime warning on the watchlist; they did not block M017 close-out but still create verification noise.
