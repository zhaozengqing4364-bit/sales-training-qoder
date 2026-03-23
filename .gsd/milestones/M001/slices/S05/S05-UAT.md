# S05: 销售价值表达与异议处理基线 — UAT

**Milestone:** M001
**Written:** 2026-03-23T23:10:00+08:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S05 simultaneously changes StepFun runtime behavior, knowledge-diagnostic surfaces, and web/report copy. Passing only unit/contract tests would not prove that the live session pressures the learner on value/price/competitor/proof topics or that the learner-facing surfaces actually show the new sales semantics.

## Preconditions

- Backend is running locally on `http://localhost:3444` with `ENVIRONMENT=development`.
- Web is running locally on `http://localhost:3445`.
- Dev login works via `POST /api/v1/auth/dev-login`.
- At least one published sales agent has at least one usable persona.
- The selected persona is bound to a knowledge base (or intentionally left without ready hits if you want to observe `miss` / `search_failed` downgrade behavior).
- Use `Realtime 模式（默认推荐）` for the runtime checks below.
- If websocket connection repeatedly closes with `1006` and backend logs mention `python-socks`, install the dependency noted in `.gsd/KNOWLEDGE.md` before judging the slice.

## Smoke Test

1. Login locally.
2. Go to `/training/sales`.
3. Pick a sales agent and persona, keep `Realtime 模式（默认推荐）`, start a session, and click `开始练习` on the overlay.
4. Ask one value-translation question: `我还是没听出来你们的产品到底怎么帮我提升ROI，别只讲功能。`
5. **Expected:** the live practice page shows `实时评分`, five sales dimensions (`价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步`), a sales-specific action card, and `/practice/{sessionId}/knowledge-check` returns a non-empty status/summary instead of a generic blank state.

## Test Cases

### 1. 价值翻译不足会把 live score panel 拉到销售语义

1. Start a new bound sales session.
2. Click `开始练习`.
3. Send or speak: `我还是没听出来你们的产品到底怎么帮我提升ROI，别只讲功能。`
4. Wait for the first `score_update` to render.
5. **Expected:**
   - live panel title remains `实时评分`
   - dimensions are the five S05 sales dimensions, not old `专业度/沟通技巧/销售流程/成交能力`
   - `当前阶段` and `本轮唯一动作` use sales language (for example value translation / benefit framing guidance)
   - `/practice/{sessionId}/knowledge-check` shows the current question in `last_query` or `recent_queries`
   - `knowledge-check.status` is diagnosable (`hit / miss / kb_not_ready / search_failed / not_triggered`), not a silent null state.

### 2. 价格异议会把评分与知识诊断切到异议处理路径

1. Continue the same session after case 1.
2. Send or speak: `如果价格比竞品高，你怎么证明值得我多花这笔预算？`
3. Wait for the next live update.
4. **Expected:**
   - score panel still shows the five S05 sales dimensions
   - stage/action guidance shifts toward objection handling instead of generic talk skills
   - the improvement suggestion mentions evidence, ROI, price justification, or next-step推进，而不是泛化“多沟通”
   - `/practice/{sessionId}/knowledge-check` records the price prompt in `recent_queries` and returns an explicit status/summary.

### 3. 竞品追问会继续沿用同一 retrieval / report fact line

1. Continue the same session.
2. Send or speak: `竞品已经能做类似功能了，你们到底区别在哪？`
3. Wait for the live score update.
4. Open `/practice/{sessionId}/knowledge-check`.
5. **Expected:**
   - the live panel remains on the same five sales dimensions
   - the action card / suggestion text pushes value differentiation or business-result framing
   - `knowledge-check.recent_queries` includes the competitor prompt
   - no second “materials path” appears; the evidence still comes from the same snapshot-backed diagnostics surface.

### 4. 证据 / 案例要求会在 report 中沉淀成销售主问题与下一轮目标

1. Continue the session.
2. Send or speak: `有没有真实客户案例或数据，证明你说的收益不是空话？`
3. End the session.
4. Open `/practice/{sessionId}/report`.
5. **Expected:**
   - report top section is sales-specific: `销售推进结果`, `本场销售主问题`, `下一轮销售目标`
   - the top diagnosis is about value translation / evidence / objection progression, not generic confidence or flow labels
   - the three rollup cards are labeled `价值表达 / 证据与收益 / 异议推进`
   - pass flags are relabeled as `价值翻译达标 / 异议承接达标 / 证据推进达标`
   - `知识库命中检测` shows hit-rate / recent queries / last query tied to the same session
   - if comprehensive report or highlights are unavailable, the page degrades with explicit copy (`综合洞察暂不可用` / `高光片段暂不可用`) while the canonical report body remains usable.

### 5. Canonical report API and page must agree on the same sales facts

1. With the completed session from case 4, call `GET /api/v1/practice/sessions/{sessionId}/report`.
2. Compare the API payload with what the page shows.
3. **Expected:**
   - `overall_score`, `logic_score`, `accuracy_score`, `completeness_score` match the page’s top score + three summary cards
   - `main_issue` and `next_goal` text on the page comes directly from the API payload
   - `pass_flags`, `overall_result`, `evaluable`, and `not_evaluable_reason` match the page state
   - no frontend-only recomputation is needed to explain what the page shows.

## Edge Cases

### 薄证据 / 零轮结束

1. Create a new sales session.
2. End it with zero or one thin turn.
3. Open `/practice/{sessionId}/report`.
4. **Expected:**
   - report shows an explicit non-evaluable downgrade
   - `not_evaluable_reason` is present
   - backend emits `practice_session_evidence_not_evaluable`
   - the page does not fake a “normal” sales diagnosis.

### 知识库未就绪

1. Use a session/persona whose snapshot runtime metrics indicate `kb_not_ready`.
2. Open `/practice/{sessionId}/knowledge-check` and the report page.
3. **Expected:**
   - diagnostics surface `kb_not_ready`
   - summary copy says knowledge docs are not ready yet
   - the user gets a diagnosable status instead of a silent miss.

### 检索失败 / Embedding 服务异常

1. Exercise or simulate a session whose runtime metrics indicate `search_failed`.
2. Open `/practice/{sessionId}/knowledge-check`.
3. **Expected:**
   - status is `search_failed`
   - summary says knowledge retrieval failed and points to KB / Embedding diagnostics
   - the failure is visible without reading raw logs.

### Legacy `score_snapshot.overall` fallback

1. Use a session whose message evidence only carries legacy `score_snapshot.overall`.
2. Read report and replay for that session.
3. **Expected:**
   - canonical `overall_score` is still present
   - `evidence_completeness.legacy_score_key_used` is true
   - report and replay agree on the fallback score instead of drifting.

## Failure Signals

- Live practice page still shows old generic dimensions instead of the five sales dimensions.
- Price / competitor / proof prompts do not alter the action card or stage guidance in sales language.
- `knowledge-check` does not record recent objection/value queries or collapses distinct failure modes into an undifferentiated blank state.
- `/practice/{sessionId}/report` shows old generic labels, missing sales `main_issue` / `next_goal`, or mismatched rollups relative to the API.
- Zero-turn sessions still look “evaluable” without explicit downgrade copy.
- Legacy fallback sessions disagree between report and replay.

## Requirements Proved By This UAT

- R003 — live training now pressures and evaluates product value translation, customer benefit framing, and objection handling instead of generic chatting.
- R011 — the same session facts drive live diagnostics, knowledge-check, and canonical report output in a sales-specific way.

## Not Proven By This UAT

- S06 cross-session trends for supervisors.
- S07 PPT post-session unified review.
- Full S08 release readiness / observability closure for all local-runtime noise modes.
- Optional comprehensive-report enrichment quality; this UAT only requires graceful degradation when enhancement endpoints are unavailable.

## Notes for Tester

- Judge S05 by the canonical surfaces first: live `score_update`, `/practice/{sessionId}/knowledge-check`, and `/practice/{sessionId}/report`.
- Do not fail the slice just because optional comprehensive-report or highlights calls return `404/400/500`, as long as the page degrades explicitly and the unified report contract is correct.
- If local StepFun upstream reconnect noise appears, distinguish between runtime transport noise and sales evidence drift before calling it a regression.
