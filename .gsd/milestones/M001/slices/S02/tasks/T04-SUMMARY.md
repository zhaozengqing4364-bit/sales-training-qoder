---
id: T04
parent: S02
milestone: M001
provides:
  - Web report/replay/history pages now consume the unified evidence contract as their baseline fact source, keep comprehensive report/highlights optional, and expose stable degraded states instead of stitching conflicting scores
key_files:
  - web/src/lib/api/types.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/app/(dashboard)/history/page.test.tsx
key_decisions:
  - D016: Web report/replay/history pages only trust the unified evidence contract for baseline facts; comprehensive report and highlights remain optional enhancement layers
patterns_established:
  - Report/replay/history top-line score, evaluability, stage summary, and completeness messaging come directly from the unified evidence contract and are no longer recomputed on the client
  - Comprehensive report/highlights may enrich the page, but their absence is rendered as an explicit degraded hint instead of collapsing baseline evidence or inventing fallback scores
observability_surfaces:
  - `[Report] Loaded unified evidence contract`
  - `[Report] Enhanced report unavailable; keeping unified evidence`
  - `[Replay] Loaded unified evidence contract`
  - `[Replay] Highlights unavailable; keeping unified evidence`
  - `[History] Loaded unified evidence list`
  - `[History] Unified evidence list load failed`
  - `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
  - `web/src/app/(dashboard)/history/page.test.tsx`
duration: 45m
verification_result: passed
completed_at: 2026-03-23T09:34:11+08:00
blocker_discovered: false
---

# T04: 收口报告/回放/历史页面的统一消费面

**Finalized the web evidence-consumer closure so report/replay/history all trust one evidence contract and degrade cleanly when optional enhanced data is missing.**

## What Happened

`web/src/lib/api/types.ts` 明确了统一 evidence 字段：`overall_score`、`evaluable`、`not_evaluable_reason`、`stage_summary`、`evidence_completeness`、`main_issue`、`next_goal`、`pass_flags` 等现在在 report / replay / history 三个页面上有一套共享的前端类型边界。

三个页面的消费面已经收口到这条边界：
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 只把 `api.sessions.getReport()` 返回的 unified evidence contract 当作事实面；`ComprehensiveReport` 只用来补充“综合洞察”，高光和知识库命中也都是附加块，缺失时只显示明确降级提示，不再反过来决定 overall 或 evaluability。
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` 直接消费 `api.sessions.getReplay()` 的 messages / overall / stage summary，不再回退到 `/messages` 去拼另一份消息或分数来源；highlights 只做 enrich，不改变基线事实。
- `web/src/app/(dashboard)/history/page.tsx` 以 `/users/me/history` 的 per-session summary 作为列表事实源，statistics / trends 只做看板与趋势快照，不再覆盖列表里的 overall 或 evaluability 语义；当 analytics snapshot 缺失时，页面保留历史列表并给出“统计看板/趋势快照暂不可用”的单独提示。

前端 focused tests 也已经把三种关键边界锁住：
- report 页展示 unified overall / not-evaluable 文案，并在 comprehensive report / highlights 缺失时稳定降级
- replay 页只信 unified replay payload，不再从 `/messages` 拼接冲突消息或冲突分数
- history 页继续展示 projection-backed score，并把 not-evaluable session 渲染成显式状态，而不是塌成泛化“评分中”

## Verification

Slice-level verification passed fresh in this retry:
- `cd backend && pytest tests/unit/test_stepfun_message_helpers.py tests/unit/test_stepfun_realtime_persistence.py tests/unit/test_sales_message_persistence.py` ✅
- `cd backend && pytest tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` ✅
- `cd backend && pytest tests/unit/test_history_service_evidence_projection.py tests/unit/common/test_analytics_api_normalization.py tests/integration/test_history_evidence_flow.py` ✅
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(dashboard)/history/page.test.tsx'` ✅

Focused browser verification against the running local app:
- Used `/api/v1/auth/dev-login` to establish a local cookie-backed session, then navigated to `http://localhost:3445/history`
- `browser_batch` asserted `url_contains=/history` and heading `训练历史记录` ✅
- `browser_batch` asserted explicit failure UI text `统一训练证据加载失败` and `重试` ✅
- `browser_get_network_logs` / `browser_get_console_logs` confirmed the page-level diagnostics distinguish a unified evidence contract fetch failure from a generic blank state; the live backend returned a 500 because the local dev database is missing `conversation_messages.transcript_metadata`

That browser run did not provide happy-path session data because the local dev database schema is behind the code, but it did verify the required observability/failure-state contract on the real page.

## Diagnostics

后续排查前端消费面先看：
- `web/src/lib/api/types.ts`
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(dashboard)/history/page.tsx`
- 对应三个 `page.test.tsx`

关键诊断面：
- report 页日志：`[Report] Loaded unified evidence contract`、`[Report] Enhanced report unavailable; keeping unified evidence`
- replay 页日志：`[Replay] Loaded unified evidence contract`、`[Replay] Highlights unavailable; keeping unified evidence`
- history 页日志：`[History] Loaded unified evidence list`、`[History] Unified evidence list load failed`
- 降级 UI 文案要区分三类：
  - 统一 evidence contract 获取失败
  - 综合洞察缺失但基础 evidence 可用
  - 高光缺失但基础 evidence 可用

如果后续页面又开始漂分，先看 page tests 是否失守，再确认页面是否重新引入了 `ComprehensiveReport` / `/messages` / trends/stats 对列表卡片分数的覆盖逻辑。

## Deviations

- 真实浏览器 happy-path 数据验证被本地开发库 schema 漂移打断：`conversation_messages.transcript_metadata` 列缺失导致 `/practice/history/statistics` 返回 500。因此本次浏览器验证聚焦在页面级 failure-state / diagnostics，而 happy-path 数据一致性继续由 fresh slice verification 和 focused vitest 证明。

## Known Issues

- 本地开发数据库仍缺少 `conversation_messages.transcript_metadata` 列；如果后续要继续用当前本地库做 history/report/replay 的真实 happy-path 浏览器验证，需要先补 migration。
- `/history` 页面在本地库 schema 漂移下会正确显示“统一训练证据加载失败”，但这属于环境问题，不是本任务的 contract 回归。

## Files Created/Modified

- `web/src/lib/api/types.ts` — 补齐 report/replay/history 共享 evidence contract 与 history/replay 相关字段类型
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 只信 unified report evidence，并把 comprehensive report / highlights / knowledge-check 降为可缺失增强层
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — 只消费 unified replay payload，不再从 `/messages` 拼接冲突消息或分数
- `web/src/app/(dashboard)/history/page.tsx` — 以 `/users/me/history` summary 作为列表事实源，把 stats/trends 降为看板/快照并区分 contract failure vs analytics degradation
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 锁住 unified overall/not-evaluable 展示与 enhanced/highlights 缺失时的稳定降级
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — 锁住 replay 页面不再回退 `/messages` 拼接冲突事实
- `web/src/app/(dashboard)/history/page.test.tsx` — 锁住 history 列表使用 projection-backed score，并显式渲染 not-evaluable session
- `.gsd/DECISIONS.md` — 追加 D016，记录前端只信 unified evidence contract、增强内容只作可缺失补充
- `.gsd/milestones/M001/slices/S02/S02-PLAN.md` — 标记 T04 完成
- `.gsd/STATE.md` — 更新 slice 完成态与下一步
- `.codex/loop/state.json` — 把当前 issue 推进到 M001-S02-T04 done 并记录 fresh verification 结果
- `.codex/loop/log.md` — 追加本轮 stabilize 日志
