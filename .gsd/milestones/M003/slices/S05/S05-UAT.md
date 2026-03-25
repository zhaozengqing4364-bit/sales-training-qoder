# S05: objection-heavy live proof 与稳定性护栏 — UAT

**Milestone:** M003  
**Written:** 2026-03-25T16:35:57+0800

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S05 needs one honest same-session proof across admin configuration, live practice runtime, canonical report evidence, and replay/fallback behavior. Passing backend tests from T01 proves the contracts; this UAT proves the current localhost product surfaces still compose into one inspectable objection-heavy session, including the places where they degrade instead of staying green.

## Preconditions

- Backend is running locally on `http://localhost:3444`.
- Web is running locally on `http://localhost:3445`.
- **Use the same host on both sides.** For this proof, keep everything on `localhost`; do not mix `localhost` and `127.0.0.1` for the web app and API.
- Browser session is dev-logged-in against `http://localhost:3444/api/v1/auth/dev-login`.
- Published sales agent exists: `06abb669-50c2-47b1-a7c3-fd9fca781a79` (`石犀科技问答`).
- Persona exists and stays KB-bound: `4c99d4d0-965b-439b-b746-33d2e1c55073` (`石犀专家`).
- Knowledge base exists and is ready: `c6dad7ec-4673-4e00-acc1-0de190a88198` (`产品手册`, 3 docs / 319 chunks).
- Local browser automation cannot speak into a real microphone, so this proof uses the **real practice page recorder + websocket path** with a synthetic `getUserMedia` stream backed by local speech clips. This is not the websocket `type:"text"` shortcut.
- Local artifact server for those clips was started on `http://127.0.0.1:8777` with permissive CORS headers and stopped after capture.

## Artifact Paths

- Browser trace: `.artifacts/browser/2026-03-25T07-48-56-629Z-session/m003-s05-t02.trace.zip`
- Browser timeline: `.artifacts/browser/2026-03-25T07-48-56-629Z-session/s05-timeline.json`
- Report-page debug bundle: `.artifacts/browser/2026-03-25T08-32-14-317Z-s05-report`
- Replay-page debug bundle: `.artifacts/browser/2026-03-25T08-31-00-679Z-s05-replay`
- Practice-session screenshots were captured from the live page before end-of-session and from the canonical report page after end-of-session.

## Admin Configuration Baseline

### 1. Persona pressure contract was frozen on the real admin path

Using the live admin surface/backend pair for `石犀专家`, I confirmed the persona remained knowledge-base-bound and then updated its pressure model to an explicit objection-heavy shape before creating the session.

**Frozen runtime facts on the created session** (`ef48ed80-0bfa-4a47-82c7-228ac3d468d2`):

- `voice_policy_snapshot.source.customer_pressure_source == "explicit"`
- `customer_pressure.pressure_direction.sales_focus == "competitor"`
- `customer_pressure.pressure_direction.value_axes == ["ROI", "客户收益", "预算优先级"]`
- `customer_pressure.pressure_direction.objection_axes == ["价格", "竞品替代", "实施风险"]`
- `customer_pressure.follow_up_behavior.question_strategy == "progressive_follow_up"`
- `customer_pressure.follow_up_behavior.revisit_on_evasion == true`
- `customer_pressure.follow_up_behavior.require_evidence == true`
- `knowledge_base_ids == ["c6dad7ec-4673-4e00-acc1-0de190a88198"]`
- `tool_policy.require_kb_grounding == true`
- `network_access_mode == "off"`

### 2. Knowledge admin page proved the KB is actually queryable

On `http://localhost:3445/admin/knowledge/c6dad7ec-4673-4e00-acc1-0de190a88198` I ran the built-in search diagnostic with:

> 石犀和竞品相比，怎么证明 ROI 和实施价值？

**Observed UI result:**

- page showed `搜索诊断`
- page showed `可执行搜索诊断`
- page reported `命中 5 个片段，来自 3 份已就绪文档。`
- top hit came from `石犀常见问题解答.docx`

This established that the same product manuals later referenced by the session were searchable before runtime started.

## Live Same-Session Runtime Proof

### Session under test

- Session ID: `ef48ed80-0bfa-4a47-82c7-228ac3d468d2`
- Practice URL: `http://localhost:3445/practice/ef48ed80-0bfa-4a47-82c7-228ac3d468d2?scenario_type=sales&agent_id=06abb669-50c2-47b1-a7c3-fd9fca781a79&persona_id=4c99d4d0-965b-439b-b746-33d2e1c55073&voice_mode=stepfun_realtime`
- Voice mode: `stepfun_realtime`
- Runtime profile: `46dd04f3-a867-4d77-bf86-609860fa4981`

### Runtime sequence

1. Opened the real practice page.
2. Clicked `开始练习` to unlock audio.
3. Fed three synthetic microphone turns through the page’s own recorder/websocket path:
   - turn 1: value framing + explicit invite for ROI / competitor / implementation-risk objections
   - turn 2: price / competitor / case-evidence response
   - turn 3: implementation-risk containment + pilot close
4. Let the live persona respond between each turn.
5. Ended the same session from the page’s `结束练习` button and waited for the automatic report navigation.

### What the live practice page proved

The current user-facing runtime surfaces behaved like an objection-heavy customer session rather than a helper-only demo:

- The page stayed on the current `/practice/{sessionId}` runtime shell and kept the same session open through multiple turns.
- The live persona repeatedly forced the conversation back to ROI proof instead of accepting generic value claims.
- Realtime surfaces updated on the same page:
  - `本轮唯一动作`
  - `当前阶段` → `异议处理`
  - `实时评分`
  - dimension scores for `价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步`
- The action-card text after the live turns stayed aligned with the objection-heavy goal:
  - `问题`: 客户顾虑出现后，承接与重构回应还不够完整。
  - `替换句`: 先复述价格、竞品或风险顾虑，再给收益与证据回应。
  - `当前仍卡住的证明`: `补上案例、数据或ROI证据，让价值主张更可信。`

### Observed degraded signal on the same runtime path

The **first** recording attempt on the same session hit a real degraded runtime behavior before the later turns succeeded:

- practice page showed the assistant line:  
  `当前会话已开启知识库强制模式，但本轮语音转写尚未完成，无法执行知识检索。请放慢语速并重述问题。`
- backend log recorded:  
  `[GROUNDING_DEBUG] timeout_proceeded_without_transcription_completion`
- this was caused by the synthetic microphone starting playback too early, before the recorder fully latched onto the returned stream.

I kept the same session, delayed synthetic playback by ~1.2s, and the later turns transcribed successfully. This gives a real runtime stability/fallback datapoint instead of a fabricated all-green run.

## Same-Session Canonical Report Proof

After ending the same session, the browser was redirected to:

- `http://localhost:3445/practice/ef48ed80-0bfa-4a47-82c7-228ac3d468d2/report`

### What the report page showed

The report page stayed on the canonical sales evidence contract and surfaced the exact objection-heavy result set from the session:

- `训练评估报告`
- overall score: `70.37` (page rounded to `70`)
- `主张证据状态` → `证据偏弱`
- `销售推进结果` → `销售基线通过`
- `本场销售主问题`:
  - `价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。`
- `下一轮销售目标`:
  - `先用案例、数据或ROI证据支撑主张，再推进下一步。`
- `销售推进基线`:
  - `pass_3min_flow == true`
  - `pass_5turn_defense == true`
  - `pass_4step_structure == false`
- `知识库命中检测`:
  - `已命中`
  - `检索次数 3`
  - `命中问答 3`
  - `命中率 100%`
  - last query was the implementation-risk / pilot-close turn
- `会话策略快照基线` included:
  - `voice_mode: stepfun_realtime`
  - `customer_pressure_source: explicit`
  - `kb_lock_enforcement: kb_required_and_bound`
  - `network_access_enforcement: network_off`

### Canonical API facts for the same session

`GET /api/v1/practice/sessions/ef48ed80-0bfa-4a47-82c7-228ac3d468d2/report`

- `scenario_type == "sales"`
- `overall_score == 70.37`
- `evaluable == true`
- `effectiveness_snapshot.claim_truth.status == "weak_evidence"`
- `main_issue.issue_type == "evidence_gap"`
- `next_goal.goal_type == "evidence_backing"`
- `evidence_completeness.complete == true`
- `evidence_completeness.message_count == 7`
- `evidence_completeness.message_analysis == 3`
- `evidence_completeness.message_scores == 3`
- `evidence_completeness.stage_evidence == 3`
- `voice_policy_snapshot_ref.source.customer_pressure_source == "explicit"`

`GET /api/v1/practice/sessions/ef48ed80-0bfa-4a47-82c7-228ac3d468d2/knowledge-check`

- `status == "hit"`
- `summary == "知识检索已触发并命中知识库"`
- `attempt_count == 3`
- `hit_query_count == 3`
- `hit_rate == 1.0`
- `last_result_count == 5`

## Same-Session Degraded/Fallback Signals

### 1. Optional report layers degraded without hiding the canonical report

The report page stayed readable even though optional enhanced layers were not healthy:

- page showed `综合洞察暂不可用，当前页面仅展示统一训练证据。`
- page showed `高光片段暂不可用，基础评估结果不受影响。`

Backend log for the same session explains why:

- `report_generation_failed` with `error: [NO_STAGE_RESULTS]`
- `no_scoring_context_available` with fallback `[SCORING_CONTEXT_NOT_FOUND] No realtime scoring data available`

Even with that failure, the canonical projection still built successfully:

- `practice_session_evidence_projection_built`
- `practice_session_report_built`

So the current product behavior is: **projection-backed report survives, optional enhanced report/highlights do not**.

### 2. Replay stayed blocked because the session never left `scoring`

This same session did **not** reach a fully completed replay state.

Observed facts:

- `GET /api/v1/practice/sessions/{id}` kept returning `status == "scoring"` for at least 30 seconds after end.
- `GET /api/v1/sessions/{id}/replay` returned `400` with  
  `[SESSION_NOT_COMPLETED] Session must be completed for replay. Current status: scoring`
- `GET /api/v1/sessions/{id}/highlights` returned the same completed-session gate failure.

The replay page surfaced this explicitly instead of going blank:

- browser URL: `http://localhost:3445/practice/ef48ed80-0bfa-4a47-82c7-228ac3d468d2/replay`
- page heading: `统一训练证据不可用`
- page text included:  
  `统一训练证据加载失败：[SESSION_NOT_COMPLETED] Session must be completed for replay. Current status: scoring`

This is an important live finding for T03: on the current product surface, objection-heavy report review is available on the canonical projection line, but replay/highlights remain blocked when the post-end scoring/report generation path cannot finalize.

## Requirements/Acceptance Facts Proved By This UAT

- A real objection-heavy same-session sales run can still be created from the current live `agent + persona + KB` chain and exercised on the current `/practice/{sessionId}` page.
- The runtime can freeze and later display an explicit customer-pressure contract (`customer_pressure_source: explicit`) on the canonical report surface.
- The same session can produce inspectable report evidence, knowledge-hit facts, claim-truth classification, and score-panel/action-card runtime feedback without any sidecar debug app.
- The current release fallback behavior is now explicit and inspectable:
  - early transcription miss → KB-lock fallback line on runtime
  - enhanced report/highlights failure → canonical report still readable
  - replay/highlights blocked while session remains `scoring`

## Not Proven By This UAT

- Healthy replay availability for the same objection-heavy session after end-of-session scoring.
- A fully successful enhanced-report/highlights generation path on this same live session.
- That the post-end scoring pipeline can always transition `scoring -> completed` under current StepFun runtime conditions.

## Release-Relevant Findings For T03

- **Healthy on current path:** practice runtime, canonical report projection, knowledge-check hit evidence, live action-card / score-panel coaching, explicit customer-pressure snapshot.
- **Degraded but still usable:** runtime transcription miss on one turn, enhanced insights unavailable, highlights unavailable.
- **Potential release blocker / at least explicit guardrail input:** same-session replay remained blocked because the session stayed in `scoring` after `report_generation_failed [NO_STAGE_RESULTS]`.

## Notes for Tester

- Do not use the websocket `type:"text"` shortcut for this proof; it bypasses the real recorder path and hides the transcription-race behavior observed above.
- When automating the real practice page with a synthetic mic, delay playback after `getUserMedia` resolves. Immediate playback can create a false `transcription not completed` degradation.
- Keep the report and replay findings together: this session is the current evidence that canonical report projection is more resilient than the replay/highlight completion gate.
