# S01: Live AI authority inventory

**Goal:** 先把 live AI authority 弄清：哪些链路真实在线，哪些只是遗留兼容或影子路径。
**Demo:** After this: 项目中每条 AI/runtime/prompt/score/report 路径都有 live/compat/shadow/retire 标签，后续统一工作不会再基于误判开刀。

## Must-Haves

- StepFun realtime、legacy evaluation/report、PromptTemplateService、knowledge-answer、voice instruction compiler 的当前职责被标成 live/compat/shadow/retire。
- architecture scan 与 milestone context 可以直接回答‘现在真正在线的 AI 主链是什么’。
- downstream slices 不再直接基于过时 assumptions 改代码。

## Proof Level

- This slice proves: contract

## Integration Closure

S01 结束后，后续 prompt/evaluation/kernel 工作都有同一张 live/compat/shadow inventory 可依赖，不再误把 legacy 文件名当 runtime authority。

## Verification

- 排障与规划可直接引用 live/compat 标签；新的 agent 不必重新猜哪个 handler/service 才是真主链。

## Tasks

- [ ] **T01: 盘点 live/compat/shadow AI 路径** `est:1h`
  - 沿 `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`、`evaluation/services/*`、`prompt_templates/*`、`common/ai/*`、knowledge-answer 路径盘点 live/compat/shadow responsibilities。
- 对每条路径记录：入口、调用者、输出消费者、是否当前真实在线。
- 把 inventory 写入 architecture scan 和 milestone context。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `backend/src/evaluation/services`, `backend/src/prompt_templates`, `backend/src/common/knowledge_engine`
  - Verify: rg -n "PromptTemplateService|generate_report|evaluate\(|stepfun|knowledge_answer|voice_instruction|compiled" backend/src/sales_bot backend/src/evaluation backend/src/prompt_templates backend/src/common backend/src/presentation_coach

- [ ] **T02: 把 authority inventory 写进 proof 与文档** `est:40m`
  - 为关键 runtime/read-side tests 补 inventory assertions 或注释，明确它们锁的是哪条 authority path。
- 在 docs/api-contract 或 analysis 中写清 live path 与 compat path 的 consumer list。
  - Files: `backend/tests`, `docs/api-contract`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - Verify: rg -n "live|compat|shadow|retire|authority" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md docs/api-contract backend/tests

- [ ] **T03: 输出 live/compat/retire 输入矩阵** `est:30m`
  - 从 inventory 中筛出必须保留、可兼容、应退役的路径，形成 S02-S04 的输入矩阵。
- 明确不能在本 milestone 中一次性粗暴删除的 legacy consumers。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`
  - Verify: rg -n "must keep|compat|retire candidate|consumer" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md

## Files Likely Touched

- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- backend/src/sales_bot/websocket/stepfun_realtime_handler.py
- backend/src/evaluation/services
- backend/src/prompt_templates
- backend/src/common/knowledge_engine
- backend/tests
- docs/api-contract
- .gsd/plans/GSD_PLAN_post-M018-next-wave.md
