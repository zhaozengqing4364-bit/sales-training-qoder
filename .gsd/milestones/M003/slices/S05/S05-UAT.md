# S05: objection-heavy live proof 与稳定性护栏 — UAT

**Milestone:** M003
**Written:** 2026-03-25T09:55:59.195Z

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S05 is a final-assembly slice, so acceptance needs both contract proof and one honest same-session run across the current admin -> practice -> knowledge-check -> report/replay chain. The backend regression suite proves the route-level contracts; this script proves how the live product surfaces compose, including the places where they degrade instead of staying all green.

## Preconditions

- Backend is running locally on `http://localhost:3444`.
- Web is running locally on `http://localhost:3445`.
- Both surfaces use the same host (`localhost` with `localhost`); do not mix `localhost` and `127.0.0.1`.
- Browser session is dev-logged-in through `http://localhost:3444/api/v1/auth/dev-login`.
- Published sales agent exists: `06abb669-50c2-47b1-a7c3-fd9fca781a79` (`石犀科技问答`).
- Persona exists and remains KB-bound: `4c99d4d0-965b-439b-b746-33d2e1c55073` (`石犀专家`).
- Ready knowledge base exists: `c6dad7ec-4673-4e00-acc1-0de190a88198` (`产品手册`).
- Browser automation uses the real `/practice/{sessionId}` recorder + websocket path with delayed synthetic `getUserMedia` audio. Do not use the websocket `type:"text"` shortcut.

## Smoke Test

1. Open the real practice page for a fresh StepFun sales session created from the updated `石犀专家` persona.
2. Send one objection-heavy turn through the recorder path and wait for the live runtime to respond.
3. End the session and open the canonical report.
4. **Expected:** the practice page shows sales action-card/stage/score updates, and the report shows a same-session evidence line with objection-heavy guidance plus knowledge-hit and claim-truth facts.

## Test Cases

### 1. Admin configuration freezes an explicit objection-heavy pressure contract

1. Open `http://localhost:3445/admin/personas/4c99d4d0-965b-439b-b746-33d2e1c55073` and save an explicit pressure model focused on competitor / ROI / implementation-risk objections.
2. Open `http://localhost:3445/admin/knowledge/c6dad7ec-4673-4e00-acc1-0de190a88198` and run the built-in search diagnostic with `石犀和竞品相比，怎么证明 ROI 和实施价值？`.
3. Create a fresh sales session through the current product flow with the same agent + persona.
4. Inspect the session snapshot through the current runtime/report surfaces.
5. **Expected:** the knowledge admin page reports real hits from the bound KB, and the created session freezes `customer_pressure_source: explicit`, the expected value/objection axes, the KB binding, `require_kb_grounding=true`, and `network_access_mode=off`.

### 2. Live practice runtime keeps the objection-heavy proof gap visible on the same session

1. Open the real `/practice/{sessionId}` page for the new session and click `开始练习`.
2. Feed three turns through the page’s own recorder path: value framing that invites ROI / competitor / implementation objections, a price / competitor / evidence response, and an implementation-risk / pilot-close response.
3. Wait for the live persona to respond after each turn.
4. Observe the runtime coaching surfaces on the same page.
5. **Expected:** the persona keeps forcing ROI/evidence pressure instead of generic small talk; the page updates `当前阶段`, `实时评分`, and the single `本轮唯一动作`; the stage reaches `异议处理`; and the visible coaching still asks for stronger ROI / case / data proof.

### 3. Canonical report stays truthful even when optional layers degrade

1. End the same session from the practice page.
2. Wait for navigation into `/practice/{sessionId}/report`.
3. Review the core report facts and the same-session API payloads from `/api/v1/practice/sessions/{id}/report` and `/api/v1/practice/sessions/{id}/knowledge-check`.
4. **Expected:** the report remains readable and shows the same-session evidence line (`overall_score` around `70.37`, `claim_truth.status=weak_evidence`, `knowledge-check.status=hit`, explicit `customer_pressure_source: explicit`, and the correct sales `main_issue` / `next_goal`), while optional enhanced layers degrade with explicit copy (`综合洞察暂不可用` and `高光片段暂不可用`) instead of hiding the canonical report.

### 4. Replay surfaces the current completed-session gate failure explicitly when scoring never finalizes

1. On that same session, request `/api/v1/sessions/{id}/replay` and `/api/v1/sessions/{id}/highlights`, and open `/practice/{sessionId}/replay` in the browser.
2. Check `/api/v1/practice/sessions/{id}` status and backend logs after end-of-session.
3. **Expected:** if the session remains `status="scoring"`, replay/highlights stay blocked with `[SESSION_NOT_COMPLETED]`, the replay page explicitly shows `统一训练证据不可用`, and backend logs explain the failure with `report_generation_failed [NO_STAGE_RESULTS]` / `no_scoring_context_available` instead of leaving the learner on a blank or ambiguous surface.

## Edge Cases

### Runtime transcription miss under KB lock recovers on the same session

1. Start playback too early after `getUserMedia` resolves so the first turn races the recorder.
2. Then delay playback by about one second and continue on the same session.
3. **Expected:** the first turn can surface the current KB-lock fallback copy (`当前会话已开启知识库强制模式，但本轮语音转写尚未完成...`) with `timeout_proceeded_without_transcription_completion`, but later turns on that same session recover and produce real objection-heavy coaching plus KB-hit evidence.

### Optional report/highlights failure does not erase the canonical evidence line

1. Open the report for the same session after end-of-session processing.
2. Check whether enhanced insights/highlights fail while the canonical report projection succeeds.
3. **Expected:** the page still renders the usable report body and shows explicit fallback copy for the optional layers; the learner should never lose the main score / issue / next-goal / knowledge-hit line because enhanced generation failed.

## Failure Signals

- Persona or session snapshot no longer exposes `customer_pressure_source: explicit` after saving the objection-heavy model.
- Knowledge admin diagnostics stop returning real hit/miss evidence on the bound KB.
- Live practice runtime stops updating stage, score, or the single action-card surface on objection-heavy turns.
- Canonical report no longer shows the same-session claim-truth / knowledge-hit / main-issue / next-goal line when enhanced layers fail.
- Replay becomes a blank or generic failure surface instead of either loading truthful evidence or surfacing the current explicit `[SESSION_NOT_COMPLETED]` gate.
- Learner/admin-visible knowledge statuses collapse back into generic “没命中” semantics.

## Requirements Proved By This UAT

- R010 — proved one real objection-heavy same-session run on the current admin Persona/knowledge -> practice -> knowledge-check -> canonical report chain, and made the remaining replay-blocked scoring acceptance boundary explicit on the accepted proof surfaces.

## Not Proven By This UAT

- Healthy replay/highlights availability for the same objection-heavy session after end-of-session scoring.
- A durable server-side latency metric for this proof path.
- That the current StepFun post-end scoring path always finalizes `scoring -> completed` under live conditions.

## Notes for Tester

- Keep frontend and backend on the same loopback host.
- Use delayed synthetic microphone playback on the real recorder path; immediate playback can create a false transcription-miss degradation.
- Do not replace the recorder path with websocket `type:"text"`; that shortcut hides the live transcription race and weakens the proof.
- Keep the report and replay findings together: on the current product line, canonical report projection is more resilient than the replay/highlight completion gate.
