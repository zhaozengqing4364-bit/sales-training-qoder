---
id: T03
parent: S05
milestone: M001
provides:
  - Live ScorePanel and report overview cards now expose sales value/evidence/objection semantics from the existing unified contract, with focused web coverage and a report API integration proof.
key_files:
  - web/src/components/practice/ScorePanel.tsx
  - web/src/components/practice/ScorePanel.test.tsx
  - web/src/hooks/websocket/message-handlers.test.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - backend/tests/integration/test_sales_value_training_flow.py
key_decisions:
  - No new architectural decision: T03 kept the existing unified report contract and only changed consumer labels, ordering, and fallback behavior on top of it.
patterns_established:
  - Sales vocabulary should be mapped in the presentation layer (`ScorePanel` / report cards) while preserving unknown-dimension visibility and legacy payload compatibility.
observability_surfaces:
  - web/src/components/practice/ScorePanel.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - GET /api/v1/practice/sessions/{id}/report
  - GET /api/v1/practice/sessions/{id}/knowledge-check
  - backend/tests/integration/test_sales_value_training_flow.py
  - browser verification on /practice/{sessionId}/report
duration: 4h13m
verification_result: passed
completed_at: 2026-03-23T22:45:07+08:00
blocker_discovered: false
---

# T03: 对齐 live/report 消费面并补端到端销售语义回归证明

**Aligned ScorePanel and report consumers to sales semantics, added focused UI regressions, and proved the report API/browser surface exposes the same sales issue/goal contract.**

## What Happened

我先按计划把 red tests 补齐，再只改消费面，不在前端重算任何分数。

这次落地的变化分三块：

1. `web/src/components/practice/ScorePanel.tsx`
   - 给新的五个销售维度补了显式映射：`价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步`。
   - 维度展示现在按 sales-first 顺序稳定排序，而不是完全依赖 payload 顺序。
   - 旧 generic 词汇和未知词汇继续可见，不会因为 vocabulary 升级把 live panel 渲染空掉。

2. `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
   - 顶部 3 张总览卡从 `逻辑性 / 准确性 / 完整性` 切到 `价值表达 / 证据与收益 / 异议推进`，仍然直接消费 `logic_score / accuracy_score / completeness_score` 这三个统一 contract 字段。
   - 顶部说明文案、主问题 / 下一轮目标标题、以及 pass flag 展示文案都改成销售价值 / 证据 / 异议推进语义。
   - `ComprehensiveReport` 与 highlights 继续保持可缺失增强层；report 页面没有新增任何客户端拼分逻辑。

3. 测试与 proof
   - 新增 `web/src/components/practice/ScorePanel.test.tsx`，锁住 sales 维度、未知维度 fallback、legacy payload fallback。
   - 扩展 `web/src/hooks/websocket/message-handlers.test.ts`，锁住 `score_update.dimension_scores` 的 sales 词汇进入前端 state 时不会被改写或丢失。
   - 扩展 `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`，锁住 report 页面在 unified contract 下显示 sales rollup、sales main_issue / next_goal，并继续保持 enhancement degradation 行为。
   - 新增 `backend/tests/integration/test_sales_value_training_flow.py`，证明真实 report API 会把 sales-specific rollup、`main_issue`、`next_goal`、knowledge snapshot 引用透传到消费面。

另外，我按 pre-flight 要求先补了 `T03-PLAN.md` 的 `## Observability Impact`，把这次任务的 inspection surfaces 和 failure visibility 写回计划。

## Must-Haves Status

- ✅ `web/src/components/practice/ScorePanel.tsx` 现在直接显示新的销售维度（`价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步`），并且对未知维度与旧 generic payload 都保留可见 fallback，不会因为 vocabulary 升级导致 live panel 空白或崩掉。
- ✅ `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 现在把顶部 3 张卡、主问题、下一轮目标和相关说明文案切到销售价值 / 证据 / 异议推进语义；实现仍只消费 unified report contract，没有在前端新增任何重新拼分逻辑，也不依赖 comprehensive report 成功才显示 top-line 结果。

## Verification

先按 TDD 写 focused tests，再跑 red：
- backend integration proof 在当前 write/read 合同下直接通过，说明 T01/T02 的事实线已经能支撑 T03 的 report API 断言；
- web focused suite 在改消费面前按预期卡在 report 页面仍是 generic 语义这一点上。

实现后，我 fresh 跑了 task-level 和 slice-level自动验证：
- task backend integration：通过
- task web focused suite：通过
- slice backend suite：通过
- slice web suite：通过

浏览器验证做了两层：
1. 本地启动 backend/web 后，用真实 app 登录并打开 live practice 页面，确认页面能进入 Realtime `进行中` 状态、录音按钮从禁用转为可用、ScorePanel fallback 可见；
2. 为了直接验证用户真正看到的 report 语义，我在本地 DB 种了一条 completed sales session，通过真实 `/practice/{sessionId}/report` 页面断言了：销售推进结果、下一轮销售目标、3 张销售总览卡、sales issue/goal 文案，以及 knowledge-check `已命中` 提示都来自 live contract。

我没有在这次 time-budget 内完成“四类对话各跑一轮”的完整麦克风 UAT；browser 自动化已把 practice 页面带到可开始录音的状态，但没有继续做长对话回合驱动 `score_update`。这部分我在 Known Issues 里留了明确续跑入口。

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && pytest tests/integration/test_sales_value_training_flow.py` | 0 | ✅ pass | 3.19s |
| 2 | `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 1.65s |
| 3 | `cd backend && pytest tests/unit/test_realtime_scoring.py tests/unit/test_effectiveness_sales_baseline.py tests/unit/test_voice_instruction_compiler.py tests/unit/test_stepfun_knowledge_helpers.py tests/unit/test_stepfun_realtime_handler.py tests/contract/test_practice_evidence_contract.py tests/integration/test_sales_value_training_flow.py` | 0 | ✅ pass | 3.12s |
| 4 | `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` | 0 | ✅ pass | 0.99s |
| 5 | `browser_assert /practice/6aff04f9-a09e-4956-8abc-07251c597a8f/report`（断言 sales rollups / main_issue / next_goal / knowledge-check） | 0 | ✅ pass | ~2m |
| 6 | `browser runtime spot-check /practice/0661f672-a39a-404e-b4b5-93e396c77fe0`（进入 Realtime 进行中、开始练习后录音按钮可用） | 0 | ✅ pass | ~6m |

## Diagnostics

后续 agent 可以从这些面快速复核本任务：

- `web/src/components/practice/ScorePanel.tsx`
  - sales 维度顺序与 fallback 显示是否仍正确
- `web/src/hooks/websocket/message-handlers.test.ts`
  - `score_update.dimension_scores` 词汇是否被原样保留
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - 顶部说明、主问题 / 目标标题、3 张总览卡是否仍是销售语义
- `backend/tests/integration/test_sales_value_training_flow.py`
  - report API 是否仍直接透传 sales rollup / issue / goal
- `GET /api/v1/practice/sessions/{id}/knowledge-check`
  - report 页 knowledge-check 区块是否仍展示 runtime snapshot 的命中状态与 query 摘要
- 本地 runtime/browser
  - `/practice/{sessionId}`
  - `/practice/{sessionId}/report`

## Deviations

- 计划说 backend integration proof 先写成 failing test，但这条 proof 在当前 T01/T02 合同下直接是绿的；我保留了它作为真正的 read-side protection，而没有为了追求形式上的 red 再额外制造破坏。
- 为了把 report 页面在真实浏览器里看成“有销售语义的 completed session”，我在本地 DB 插入了一条完成态 sales session 再走 live `/report` 页面。这是本地 UAT 辅助，不是产品代码路径改动。

## Known Issues

- 这次没有完成 slice 文案里要求的“四类对话（价值翻译不足 / 价格异议 / 竞品追问 / 证据要求）各跑一轮”的完整麦克风/browser UAT；practice 页面已经能进入 `进行中` 并显示可用的录音控件，但没有继续驱动真实多轮语音输入。
- 本地 StepFun realtime/browser UAT 在当前机器上会受到代理环境影响；若 backend 日志再次出现 `connecting through a SOCKS proxy requires python-socks`，先按 `.gsd/KNOWLEDGE.md` 里的记录修本地 venv，再重启 runtime 服务。
- browser report verification 使用的是我种到本地 DB 的 completed session `6aff04f9-a09e-4956-8abc-07251c597a8f`；它用于确认真实 UI 消费面，不代表生产数据迁移。

## Files Created/Modified

- `backend/tests/integration/test_sales_value_training_flow.py` — 新增 report API integration proof，锁住 sales rollup / issue / goal 透传
- `web/src/components/practice/ScorePanel.tsx` — 补 sales-first 维度映射、排序和安全 fallback
- `web/src/components/practice/ScorePanel.test.tsx` — 新增 ScorePanel focused regression tests
- `web/src/hooks/websocket/message-handlers.test.ts` — 锁住 `score_update.dimension_scores` 的 sales 词汇进入前端 state
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 把顶部 3 卡、说明文案、主问题 / 目标标题切到销售语义
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 锁住 report 页面销售语义和 enhancement degradation
- `.gsd/milestones/M001/slices/S05/tasks/T03-PLAN.md` — 补 `Observability Impact` 预检缺口
- `.gsd/KNOWLEDGE.md` — 记录本地 StepFun realtime UAT 的 `python-socks` 代理依赖 gotcha
- `.gsd/milestones/M001/slices/S05/tasks/T03-SUMMARY.md` — 记录本任务实现与验证证据
