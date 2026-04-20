---
estimated_steps: 4
estimated_files: 8
skills_used:
  - safe-grow
  - test-driven-development
  - agent-browser
  - react-best-practices
  - vercel-react-best-practices
  - baseline-ui
  - accessibility
  - best-practices
  - verification-before-completion
---

# T01: 补齐知识库更新诊断并证明新 sales session 吃到最新产品资料

**Slice:** S04 — 知识库更新即生效链路
**Milestone:** M001

## Description

这个任务只解决 R004 的“产品资料”半条链：管理员必须能在系统里自己上传、恢复、诊断知识库文档，而不是依赖命令行或猜测状态；同时要把 sales 侧“下一次新建 session 才吃到新资料、旧 session 不回写”的权威线锁成可执行证据。不要把知识库重新绑回 agent 级入口，不要新增平行检索协议，始终沿用 `persona_policy -> VoiceRuntimePolicyService -> PracticeSession.voice_policy_snapshot -> /knowledge-check`。

## Steps

1. 先在 `backend/tests/integration/test_knowledge_api.py` 和 `backend/tests/integration/test_knowledge_upload_persistence.py` 写/补 failing tests，锁住 admin search、document reprocess，以及 `xlsx/xls` 上传与 follow-up list/search 合同；必要时再最小修改 `backend/src/common/knowledge/api.py`。
2. 扩展 `backend/tests/integration/test_knowledge_flow.py`，证明 persona 绑定的 KB 在上传/重试后只影响**下一次新建** sales session，并且 `/practice/sessions/{id}/knowledge-check` 能区分 `hit`、`miss`、`kb_not_ready`、`search_failed` 等状态。
3. 在 `web/src/lib/api/client.ts` / `web/src/lib/api/types.ts` 和 `web/src/app/admin/knowledge/[id]/page.tsx` 接入这些合同：上传 accept 文案与 backend 对齐、failed/pending 文档出现就地重试按钮、提供搜索诊断面板、把错误和 ready/not_ready 状态贴近对应文档或搜索动作展示。
4. 用 `web/src/app/admin/knowledge/[id]/page.test.tsx` 先补 failing UI tests，再完成实现并跑完 backend + web targeted suites；如需要 browser 验证，只验证 admin 知识库页与现有 report knowledge-check 诊断面，不重做无关训练流程。

## Must-Haves

- [ ] `web/src/app/admin/knowledge/[id]/page.tsx` 必须允许管理员上传 `xlsx/xls`、对 failed/pending 文档执行 reprocess，并直接在页面上看到 ready/not_ready/失败原因与搜索结果，而不是只能刷新猜状态。
- [ ] backend tests 必须证明新 sales session 会冻结当时的 `knowledge_base_ids` 与检索诊断，而旧 session 继续保留旧快照；“更新后即生效”只对下一次新建会话成立，不能通过回写旧 session 伪造。

## Verification

- `cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/integration/test_knowledge_flow.py`
- `cd web && npm test -- --run 'src/app/admin/knowledge/[id]/page.test.tsx'`

## Observability Impact

- Signals added/changed: admin knowledge search/reprocess 响应、文档 `status/error_message/chunk_count`、`/practice/sessions/{id}/knowledge-check` 的 `status/summary/hit_rate/recent_queries`。
- How a future agent inspects this: 打开 `web/src/app/admin/knowledge/[id]/page.tsx`、调用 `GET /practice/sessions/{id}/knowledge-check`、查看对应 integration/UI tests 的断言。
- Failure state exposed: 文档 reprocess 被拒绝的状态原因、KB 未 ready / search_failed / miss 的知识诊断、以及上传类型不一致时的前后端回归失败。

## Inputs

- `backend/src/common/knowledge/api.py` — 已有 admin search 与 reprocess API，但前端尚未真正接线全部能力。
- `backend/src/common/api/practice.py` — `/practice/sessions/{id}/knowledge-check` 是 sales 材料生效诊断的权威输出。
- `backend/src/sales_bot/services/voice_runtime_policy.py` — persona 绑定 KB 如何编译进 effective policy 的唯一入口。
- `backend/tests/integration/test_knowledge_api.py` — 现有 admin/internal knowledge search 合同测试。
- `backend/tests/integration/test_knowledge_upload_persistence.py` — 已有上传后列表可见性与 `xlsx` 覆盖，可扩成 admin 资料更新回归。
- `backend/tests/integration/test_knowledge_flow.py` — 目前多为占位/skip，适合收口成“下一次新建 session 生效”的集成证明。
- `web/src/lib/api/client.ts` — admin knowledge client 已有 search/reprocess 方法，但页面未充分使用。
- `web/src/lib/api/types.ts` — admin knowledge 文档与搜索类型定义。
- `web/src/app/admin/knowledge/[id]/page.tsx` — 当前只有 upload / preview / delete，没有自助恢复与搜索诊断。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 现有 knowledge-check 消费面，可作为 runtime proof 参考，不应被此任务重构。

## Expected Output

- `backend/src/common/knowledge/api.py` — admin knowledge upload/search/reprocess 合同与错误语义与前端需求对齐。
- `backend/tests/integration/test_knowledge_api.py` — 锁住 admin search/reprocess 合同与异常语义。
- `backend/tests/integration/test_knowledge_upload_persistence.py` — 锁住 `xlsx/xls` 上传与 follow-up 可见性。
- `backend/tests/integration/test_knowledge_flow.py` — 证明 persona 绑定 KB 只在下一次新建 sales session 生效，并能通过 `/knowledge-check` 诊断。
- `web/src/lib/api/client.ts` — admin knowledge 页面所需 search/reprocess 客户端调用收口。
- `web/src/lib/api/types.ts` — admin knowledge 诊断与文档类型对齐新的 UI 消费。
- `web/src/app/admin/knowledge/[id]/page.tsx` — 出现就地重试、搜索诊断、ready/not_ready/失败文案与 `xlsx/xls` 上传入口。
- `web/src/app/admin/knowledge/[id]/page.test.tsx` — 覆盖上传类型、重试按钮、搜索诊断与失败态文案的 focused tests。
