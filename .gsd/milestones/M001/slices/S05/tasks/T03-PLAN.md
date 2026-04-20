---
estimated_steps: 4
estimated_files: 6
skills_used:
  - safe-grow
  - test-driven-development
  - react-best-practices
  - vercel-react-best-practices
  - baseline-ui
  - accessibility
  - fixing-accessibility
  - best-practices
  - agent-browser
  - verification-before-completion
---

# T03: 对齐 live/report 消费面并补端到端销售语义回归证明

**Slice:** S05 — 销售价值表达与异议处理基线
**Milestone:** M001

## Description

这个任务把新的销售语义真正露给用户看，并补上 slice 级端到端证明。S05 的后台如果已经写入新维度，但 `web/src/components/practice/ScorePanel.tsx` 和 report 页面仍显示旧 generic 标签，用户会继续误以为系统在练“沟通分”，而不是价值表达 / 异议处理。因此这里要用 focused tests 驱动最小 UI 改动：live score panel 和 report 总览卡直接显示销售基线，同时 comprehensive report/highlights 继续保持可缺失增强层。最后再补一条 backend integration proof，证明 report API 给前端的就是新的语义，而不是客户端自己拼出来的。

## Steps

1. 先在新增的 `web/src/components/practice/ScorePanel.test.tsx`、现有 `web/src/hooks/websocket/message-handlers.test.ts`、`web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` 以及新增的 `backend/tests/integration/test_sales_value_training_flow.py` 写 failing tests，喂入新的 `score_update` / report payload，锁住销售维度名、未知维度 fallback、report 顶部 3 张卡语义与 `main_issue` / `next_goal` 的呈现。
2. 在 `web/src/components/practice/ScorePanel.tsx` 更新 icon / color / label 映射，优先支持新的销售维度（价值表达、客户收益连接、证据使用、异议处理、推进下一步），同时保留对未知维度和旧 payload 的安全 fallback，避免 live panel 因 vocabulary 变化直接空白。
3. 在 `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 把顶部 3 张总览卡与相关说明文案改成 sales rollup 语义，并继续把 comprehensive report / highlights 当作可缺失增强层；不要新增客户端评分逻辑，只消费统一 report contract。
4. 跑 backend integration + web focused suites；如需 browser spot-check，只验证本地 report 页面和 live score panel 是否展示新语义，不额外扩展无关训练流程。

## Must-Haves

- [ ] `web/src/components/practice/ScorePanel.tsx` 必须直接显示新的销售维度，并对未知维度 / 旧 payload 保持可见 fallback，不能因为 vocabulary 升级导致 UI 空白或崩掉。
- [ ] `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 必须把顶部 3 张卡和主问题 / 下一轮目标的可读文案切换成销售价值 / 异议语义，但仍只信统一 report contract，不得在前端重新拼分或依赖 comprehensive report 成功。

## Verification

- `cd backend && pytest tests/integration/test_sales_value_training_flow.py`
- `cd web && npm test -- --run 'src/components/practice/ScorePanel.test.tsx' 'src/hooks/websocket/message-handlers.test.ts' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`

## Inputs

- `backend/src/common/api/practice.py` — T01 已改写的 report contract 与 session rollup 透传面，T03 的 integration proof 必须直接消费它。
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — T01 已落地的 realtime score/effectiveness 写入面，供端到端 proof 对齐。
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — T02 已收口的客户追问契约，供 final proof 对齐 slice 目标而不是只看 UI label。
- `web/src/components/practice/ScorePanel.tsx` — 当前只硬编码 generic 维度映射。
- `web/src/hooks/websocket/message-handlers.test.ts` — websocket state normalization 的 focused regression suite。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 当前 report 顶部 3 张卡仍是 generic `逻辑性 / 准确性 / 完整性` 标签。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 当前锁住 unified evidence contract 与 enhancement degradation。
- `backend/tests/contract/test_practice_evidence_contract.py` — 统一 report contract 的读侧保证，供新增 integration proof 对齐。

## Expected Output

- `backend/tests/integration/test_sales_value_training_flow.py` — 证明 report API 会把新的 sales-specific rollup、`main_issue` 和 `next_goal` 透传到消费面。
- `web/src/components/practice/ScorePanel.tsx` — 显示新的销售维度并保留安全 fallback。
- `web/src/components/practice/ScorePanel.test.tsx` — 锁住新维度 icon / label / fallback 的 focused UI tests。
- `web/src/hooks/websocket/message-handlers.test.ts` — 锁住新 `score_update.dimension_scores` 词汇进入前端状态的回归测试。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 顶部 3 张总览卡与说明文案切换到 sales rollup 语义，同时继续只消费 unified report contract。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 锁住 report 页面在 unified contract 下展示新的销售语义并保持 enhancement degradation 行为。

## Observability Impact

- 变更后的显式信号：`score_update.dimension_scores` 必须在前端 state 与 `ScorePanel` 上保留新的销售维度词汇；report 页面必须直接显示 unified report contract 返回的 `logic_score / accuracy_score / completeness_score`、`main_issue`、`next_goal` 销售语义，而不是客户端重算。
- 后续 agent 的检查入口：`web/src/components/practice/ScorePanel.tsx` 与 `web/src/hooks/websocket/message-handlers.ts` 用于确认 live 维度如何归一化和 fallback；`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 与 `backend/tests/integration/test_sales_value_training_flow.py` 用于确认顶部 3 张卡和问题/目标文案是否直接来自 API contract。
- 新暴露的失败状态：未知 `dimension_scores` 词汇时 `ScorePanel` 仍应显示可见 fallback 标签；comprehensive report/highlights 缺失时 report 页面仍需保留销售总览卡与降级文案；integration proof 失败时可直接定位是 report contract 未透传 sales rollup、还是前端消费面仍停留在旧 generic label。
