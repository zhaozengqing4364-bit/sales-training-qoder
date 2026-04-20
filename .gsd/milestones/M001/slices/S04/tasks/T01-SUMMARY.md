---
id: T01
parent: S04
milestone: M001
provides:
  - 管理员可在知识库详情页完成 xlsx/xls 上传、failed/pending 文档重试与搜索诊断，并且 sales session 的知识快照/diagnostics 有回归证明
key_files:
  - backend/src/common/knowledge/api.py
  - backend/src/common/api/practice.py
  - backend/tests/integration/test_knowledge_api.py
  - backend/tests/integration/test_knowledge_upload_persistence.py
  - backend/tests/integration/test_knowledge_flow.py
  - web/src/app/admin/knowledge/[id]/page.tsx
  - web/src/app/admin/knowledge/[id]/page.test.tsx
  - web/src/lib/api/types.ts
key_decisions:
  - 将 admin knowledge search 的基础设施失败映射为 503，而非 404，避免把 Embedding/检索故障伪装成“知识库不存在”
  - 将 /practice/sessions/{id}/knowledge-check 扩成可显式区分 search_failed 与 no_knowledge_base，供 admin/report 统一诊断面消费
patterns_established:
  - 通过 persona 绑定变更 -> 新建 session -> voice_policy_snapshot.knowledge_base_ids 的集成测试证明“只对下一次新建会话生效”
  - 在 admin 知识库页把文档状态、失败原因、重试动作和搜索诊断放在同一现场完成排障
observability_surfaces:
  - /api/v1/admin/knowledge/{id}/search
  - /api/v1/admin/knowledge/{id}/documents/{docId}/reprocess
  - /api/v1/practice/sessions/{id}/knowledge-check
  - web/src/app/admin/knowledge/[id]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
duration: 2h
verification_result: passed
completed_at: 2026-03-23T17:11:00+08:00
blocker_discovered: false
---

# T01: 补齐知识库更新诊断并证明新 sales session 吃到最新产品资料

**Added admin KB retry/search diagnostics plus snapshot-aware knowledge-check status coverage.**

## What Happened

我按任务计划先走了 TDD：

1. 在 `backend/tests/integration/test_knowledge_api.py` 补了 admin search 故障语义与 document reprocess 回归，锁住：
   - admin search 结果仍返回 `total`
   - 检索基础设施异常返回 `503`
   - failed / pending 文档都能重新提交处理
   - ready 文档不会被错误地回退重跑
2. 在 `backend/tests/integration/test_knowledge_upload_persistence.py` 增补了 `xls` 上传可见性回归，和既有 `xlsx` 一起锁住前后端支持范围。
3. 将原本占位的 `backend/tests/integration/test_knowledge_flow.py` 改成真实集成证明，覆盖：
   - persona 的 `knowledge_base_ids` 变更只影响**下一次新建** sales session
   - 旧 session 的 `voice_policy_snapshot.knowledge_base_ids` 不会被回写
   - `/practice/sessions/{id}/knowledge-check` 可区分 `hit` / `miss` / `kb_not_ready` / `search_failed`
4. 在前端 `web/src/app/admin/knowledge/[id]/page.tsx` 接上了缺失能力：
   - 上传 accept 扩到 `xlsx/xls`
   - failed / pending 文档显示“重试处理”
   - 页面内新增“搜索诊断”面板，直接显示 ready / not_ready / failed 语义与命中证据
   - 就地贴近文档展示失败原因，而不是靠刷新猜状态
5. 顺手把 report 页对 `search_failed` 的 badge/状态文案补齐，保证知识诊断消费面不会把检索失败误显示成普通 miss。

## Verification

已完成本任务要求的目标验证：

- backend targeted integration suites 通过，覆盖 admin search / reprocess / xlsx-xls upload / snapshot freeze / knowledge-check status 分类
- web targeted page test 通过，覆盖 xlsx/xls 上传入口、failed 文档重试按钮、搜索诊断结果展示

本 slice 的 presentation 相关 contract/integration/browser 检查属于 T02 范围，未在本任务执行。

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/integration/test_knowledge_flow.py` | 0 | ✅ pass | 4.82s |
| 2 | `cd web && npm test -- --run 'src/app/admin/knowledge/[id]/page.test.tsx'` | 0 | ✅ pass | 1.71s |

## Diagnostics

后续 agent 可通过以下面检查本任务交付是否仍然成立：

- Admin 自助排障面：`web/src/app/admin/knowledge/[id]/page.tsx`
  - 文档 `status / chunk_count / error_message`
  - failed/pending 的重试按钮
  - 搜索诊断输入、命中结果、not_ready / failed 文案
- Runtime 诊断权威输出：`GET /api/v1/practice/sessions/{id}/knowledge-check`
  - `status`
  - `summary`
  - `knowledge_base_ids`
  - `attempt_count / hit_query_count / hit_rate / recent_queries`
  - `last_status / last_error`
- Report 消费面：`web/src/app/(user)/practice/[sessionId]/report/page.tsx`
  - `search_failed` 不再被误折叠成 miss

## Deviations

- 计划的输出面主要聚焦 admin 知识库页，但我额外同步了 `web/src/app/(user)/practice/[sessionId]/report/page.tsx` 与 `web/src/lib/api/types.ts` 的 `search_failed` 状态消费，避免后续浏览器验证时 report 面把新的诊断状态显示错位。

## Known Issues

- 本任务未执行 slice-level manual/browser review；该人工链路与 presentation 侧验证将在 T02/最终 slice 验证时一起完成。

## Files Created/Modified

- `backend/src/common/knowledge/api.py` — 为 admin/internal knowledge search 增加按错误类型映射的 HTTP 语义（尤其是 `503 search unavailable`）
- `backend/src/common/api/practice.py` — 让 `knowledge-check` 明确输出 `no_knowledge_base` 与 `search_failed`
- `backend/tests/integration/test_knowledge_api.py` — 增补 admin search 异常语义与 reprocess 合同测试
- `backend/tests/integration/test_knowledge_upload_persistence.py` — 增补 `xls` 上传持久化回归
- `backend/tests/integration/test_knowledge_flow.py` — 重写为真实的 snapshot-freeze / diagnostics 集成证明
- `web/src/app/admin/knowledge/[id]/page.tsx` — 接入 xlsx/xls 上传、重试处理与搜索诊断面板
- `web/src/app/admin/knowledge/[id]/page.test.tsx` — 新增 focused UI tests
- `web/src/lib/api/types.ts` — 对齐 `search_failed` 与 document error typing
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 对齐新 knowledge-check 状态展示
