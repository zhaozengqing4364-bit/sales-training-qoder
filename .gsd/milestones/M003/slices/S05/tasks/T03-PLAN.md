---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: Write the final stability and acceptance guardrails for M003

Document the stability and acceptance guardrails for M003 on the same business chain: what counts as acceptable latency, which degraded states are still shippable, and which failures block release. Reuse current support/report/runtime evidence, not a separate checklist tool.

## Inputs

- `.gsd/milestones/M003/M003-ROADMAP.md`
- `.gsd/milestones/M003/slices/S05/S05-UAT.md`
- `backend/src/common/api/practice.py`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`

## Guardrail Scope

These guardrails apply only to the current M003 proof line:

1. admin Persona / knowledge configuration
2. `POST /api/v1/practice/sessions`
3. learner `/practice/[sessionId]` runtime
4. `GET /api/v1/practice/sessions/{id}/knowledge-check`
5. `GET /api/v1/practice/sessions/{id}/report`
6. `GET /api/v1/sessions/{id}/replay`

No sidecar checklist, helper-only route, or websocket `type:"text"` shortcut can replace this chain.

## Evidence Basis

Use the same-session proof recorded in `S05-UAT.md` as the release baseline:

- session under proof: `ef48ed80-0bfa-4a47-82c7-228ac3d468d2`
- runtime showed objection-heavy coaching, stage progression, score updates, and KB-grounded responses on the real practice page
- canonical report stayed readable and exposed `overall_score=70.37`, `claim_truth.status=weak_evidence`, and `knowledge-check.status=hit`
- replay/highlights remained blocked because the session stayed `scoring` after `report_generation_failed [NO_STAGE_RESULTS]`

This task does not redefine product behavior. It records what the current product has already proved and where that proof still stops.

## Latency Guardrails

Current proof artifacts expose browser-level timing, not a durable server-side latency metric, so acceptance stays tied to user-visible milestones on the same chain.

### Acceptable latency on the current proof path

- **Admin KB diagnostic:** observed at ~3.1s (`browser_batch` action #12). Treat `<= 5s` as acceptable for the built-in knowledge search diagnostic to return a real hit/miss result.
- **Practice shell load:** observed at ~1.5s (`browser_navigate` action #13). Treat `<= 5s` as acceptable for opening the live `/practice/{sessionId}` shell.
- **Practice start/unlock:** observed at ~0.25s (`browser_batch` action #14). Treat this as expected to feel immediate; if start takes long enough that the page looks frozen, it is outside the acceptable line.
- **Objection-heavy turn completion:** observed at ~5.4s for the first visible runtime update and ~22s-30s for later full-turn objection loops (`browser_batch` actions #15-#19), including audio playback, transcription, model response, and UI refresh. Treat `<= 35s` per full live turn as acceptable **only if** the page stays on the same session shell and either shows updated coaching surfaces or an explicit fallback message.
- **End -> report transition:** observed at ~0.93s (`browser_batch` action #20). Treat `<= 5s` as acceptable for redirecting into the canonical report page once the session is ended.
- **Replay review response:** observed at ~3.2s (`browser_navigate` action #21). Treat `<= 5s` as acceptable for replay to either load or surface an explicit completed-session gate error.

### Latency failures that block acceptance

- runtime waits that exceed the bounds above **and** leave the learner on a blank, frozen, or ambiguous state
- end-of-session waits that never reach either a readable report or an explicit failure line
- replay waits that hang without either playable evidence or the current `SESSION_NOT_COMPLETED` explanation

## Degraded States That Are Still Shippable

These degraded states remain inside the acceptable M003 boundary **if they stay explicit and the same session still yields usable evidence on the canonical line**.

### 1. Runtime transcription fallback before later recovery

Shippable when all of the following are true:

- the practice page explicitly surfaces the KB-lock fallback copy (`当前会话已开启知识库强制模式，但本轮语音转写尚未完成...`)
- backend/runtime diagnostics still expose the underlying reason (`timeout_proceeded_without_transcription_completion`)
- later turns on the **same session** recover and produce real objection handling plus KB-hit evidence

This is a degraded runtime path, not a hidden failure.

### 2. Enhanced report unavailable while canonical report survives

Shippable when all of the following are true:

- `/practice/{sessionId}/report` still loads the projection-backed evidence contract from `backend/src/common/api/practice.py`
- the page still renders the core sales proof line: overall score, claim-truth status, knowledge-check facts, main issue, next goal, and voice-policy snapshot reference
- the UI uses the current explicit fallback copy from `web/src/app/(user)/practice/[sessionId]/report/page.tsx`:
  - `综合洞察暂不可用，当前页面仅展示统一训练证据。`
  - `高光片段暂不可用，基础评估结果不受影响。`
- backend logs still show `practice_session_report_built` even if enhanced generation failed upstream

In other words: optional insights may degrade; the canonical report may not.

### 3. Report-side optional highlights unavailable

Shippable when all of the following are true:

- the report page keeps the learner on a readable evidence surface
- highlight failure does not overwrite or hide the canonical evaluation
- the learner sees the current fallback copy rather than a generic blank section

## Degraded States That Are Not Shippable

These are useful diagnostics, but they fail the final M003 acceptance line.

### 1. Same-session replay blocked because the session stays `scoring`

This is the current live finding from `S05-UAT.md` and it is the main acceptance guardrail for the milestone.

Treat this as **release-blocking** when all of the following occur on the same proof session:

- canonical report is readable
- `GET /api/v1/sessions/{id}/replay` returns `[SESSION_NOT_COMPLETED]`
- `GET /api/v1/sessions/{id}/highlights` is blocked for the same reason
- `GET /api/v1/practice/sessions/{id}` continues to report `status == "scoring"`
- backend shows `report_generation_failed [NO_STAGE_RESULTS]` / `no_scoring_context_available` instead of finalizing the post-end path

Why this blocks release: M003’s accepted proof surfaces explicitly include replay, and S05 is the final-assembly slice that is supposed to prove one real admin -> practice -> report/replay run on current routes. An explicit replay error is good observability, but it is not the same as a successful accepted replay surface.

### 2. Truthful evidence surfaces drifting out of sync

Treat as release-blocking if any same-session proof shows contradiction between:

- runtime objection handling / score panel / action card
- `knowledge-check` status and hit metrics
- canonical report claim-truth / issue / next-goal line
- replay evidence for the same completed session

M003 cannot ship on mixed facts.

### 3. Current live status vocabulary collapsing into generic errors

Treat as release-blocking if the current seven-status vocabulary (`no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, `hit`) stops being visible on the accepted learner/admin surfaces and is replaced by generic “没命中” or silent fallback behavior.

## Acceptance Call for M003

### What is accepted right now

- real objection-heavy practice runtime on the shipped learner page
- explicit customer-pressure snapshot frozen from the admin path
- same-session knowledge-hit evidence on the canonical diagnostics/report line
- canonical report readability even when enhanced report/highlights degrade
- explicit runtime and report fallback copy instead of silent failure

### What is still blocked

- final M003 acceptance remains blocked until the same proof chain can leave `scoring` and open replay/highlights as accepted completed-session surfaces on the same objection-heavy session

### Practical release rule

- **Ship runtime + canonical report degradations** only when the learner still gets one truthful, inspectable same-session evidence line.
- **Do not ship M003 as complete** while the real same-session replay path is still blocked by `SESSION_NOT_COMPLETED` after end-of-session scoring/report finalization failure.

## Verification

rg -n "latency|degraded|fallback|block" .gsd/milestones/M003/slices/S05/tasks/T03-PLAN.md
