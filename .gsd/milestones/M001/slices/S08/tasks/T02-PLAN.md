---
estimated_steps: 4
estimated_files: 4
skills_used:
  - safe-grow
  - frontend-audit
  - agent-browser
  - baseline-ui
  - react-best-practices
  - verification-before-completion
---

# T02: 把 `/support/runtime` 升级成 blocking/warning 发布健康面板

**Slice:** S08 — 桌面端发布验收与可观测性收口
**Milestone:** M001

## Description

T01 会把 support runtime API 收成可信的 typed release-health contract，但如果 `web/src/app/(dashboard)/support/runtime/page.tsx` 继续停留在“三张粗粒度卡片 + 原始日志列表”，support/admin 实际仍然看不到哪里阻塞发布、哪些只是 warning、应该优先处理哪类会话。这个任务把 support/runtime 页面升级成 M001 的最终支持面：明确 blocking vs warning，展示 release health summary、typed anomaly list、局部 empty/error state 与只读 refresh 行为，同时保持 support/admin RBAC 边界，不把它变成另一套 learner report 入口。

## Steps

1. 先在 `web/src/app/(dashboard)/support/runtime/page.test.tsx` 写 focused tests，覆盖 success、blocking-heavy、warning-only、空列表、局部加载失败与刷新行为，确保页面的判断逻辑先被锁住。
2. 扩展 `web/src/lib/api/types.ts` 与必要的 `web/src/lib/api/client.ts` typing，让前端消费 T01 的 typed overview/fault contract，而不是继续把 support runtime 当成 `{ completion_rate, failed_or_warning_logs_window }` 这类粗粒度接口。
3. 改造 `web/src/app/(dashboard)/support/runtime/page.tsx`：把顶部摘要改成发布健康卡片（例如 active/scoring、blocking、warning），把 anomaly list 渲染为 typed rows，显示 severity、kind、summary、session/scenario identifiers 与检测时间，并在局部错误/空数据时给出明确只读文案与刷新入口。
4. 用 Vitest 跑 focused page test，确保 support/runtime 页面在 blocking/warning/empty/error 场景下都能稳定表达，不会因为新 contract 失败而整页白屏。

## Must-Haves

- [ ] 页面必须清楚分层 blocking 与 warning，support/admin 不需要读源码或看 raw logs 就能判断“能不能发”。
- [ ] 页面必须消费 T01 的 typed contract，而不是在前端自行发明第二套 severity/kind 推断逻辑。
- [ ] 失败与空状态必须是局部可见、可刷新、只读的；不能因为 support runtime 加载失败把整个 dashboard 壳打挂。
- [ ] 页面不得新增绕过 `_can_read_session(...)` 的 learner report 深链；support 面保持诊断属性，不变成第二个详情页导航入口。

## Verification

- `cd web && npm test -- --run 'src/app/(dashboard)/support/runtime/page.test.tsx'`
- 浏览器人工复核 — 打开本地 `/support/runtime`，确认顶部卡片与 anomaly list 能区分 blocking/warning，空数据与错误文案都局部可见且可点击“刷新”。

## Observability Impact

- Signals added/changed: support runtime UI 把 typed anomaly severity/kind、session/scenario identifiers、detected_at 与 release-health summary 直接暴露给 support/admin，而不是只显示 completion rate/log count。
- How a future agent inspects this: 查看 `web/src/app/(dashboard)/support/runtime/page.test.tsx` 的场景覆盖，然后在浏览器打开 `/support/runtime` 对照 `/api/v1/support/runtime/overview` 与 `/api/v1/support/runtime/faults` 响应。
- Failure state exposed: support runtime API 失败、无 anomaly、warning-only、blocking-heavy 都有各自可见页面状态；不会再被压缩成同一种“异常日志数字”。

## Inputs

- `backend/src/support/api/runtime_status.py` — T01 输出的 typed support runtime contract，前端必须严格跟随这个后端 truth line。
- `web/src/lib/api/types.ts` — 当前 support runtime 类型还停留在 coarse count 结构。
- `web/src/lib/api/client.ts` — support runtime fetch helpers，可能需要随新 contract 调整 typing。
- `web/src/app/(dashboard)/support/runtime/page.tsx` — 当前只有粗粒度卡片和原始故障列表的页面实现。

## Expected Output

- `web/src/lib/api/types.ts` — 支持 typed release-health overview 与 anomaly item 的前端类型。
- `web/src/lib/api/client.ts` — 与新 support runtime contract 对齐的 API client typing。
- `web/src/app/(dashboard)/support/runtime/page.tsx` — blocking/warning 分层的发布健康面板。
- `web/src/app/(dashboard)/support/runtime/page.test.tsx` — 锁住 success/empty/error/blocking/warning 页面行为的 focused test。
