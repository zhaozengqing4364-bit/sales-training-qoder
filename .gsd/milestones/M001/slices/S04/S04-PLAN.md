# S04: 知识库更新即生效链路

**Goal:** 让管理员更新产品资料或标准 PPT 后，系统既能让他们自己完成上传/恢复/替换，又能在下一次新建训练里读到最新材料，并给出可排障的生效诊断。
**Demo:** 管理员在 `/admin/knowledge/[id]` 上传或修复知识库文档后，下一次新建 sales session 会把当时的 KB 绑定冻结进 `voice_policy_snapshot`，训练后 `/practice/{sessionId}/report` 的知识诊断能显示 hit / miss / kb_not_ready 证据；管理员在 `/admin/presentations/[id]` 原位替换标准 PPT 后，用户仍从原来的 presentation 入口创建新练习，但下一次 presentation session 读取的是同一 `presentation_id` 的最新页内容 / 要点 / 禁忌词，并且 admin / user 侧都能看到版本与状态变化。
**Requirements:** Owns `R004`; supports `R008` by为 S07 提供“最新 PPT 材料”这一权威输入面。

## Must-Haves

- 管理员必须能在 `web/src/app/admin/knowledge/[id]/page.tsx` 自己完成产品资料上传、失败/待处理文档重试、就绪状态判断与搜索诊断；前后端文件类型与恢复能力必须一致，不能再出现 backend 支持 `xlsx/xls` 但前端挡住、或 failed 文档只能靠命令行恢复的情况。
- 销售资料生效证明必须沿用 `persona_policy -> VoiceRuntimePolicyService.resolve_effective_policy(...) -> PracticeSession.voice_policy_snapshot -> /practice/sessions/{id}/knowledge-check` 这一条权威线：更新后的 KB 只影响下一次新建 session，旧 session 不得被回写成新材料。
- 标准 PPT 必须支持“同一 presentation 记录原位替换”，不能继续只能新建 `presentation_id`；替换时要显式暴露 `processing/ready/failed` 与 `version_number`，并避免在进行中的会话里悄悄换页内容。
- 下一次新建 presentation session 必须读取替换或编辑后的 `Page` / `RequiredTalkingPoint` / `ForbiddenWord` 最新数据；任何必须重连的元数据（例如页级要点与禁忌词）都要有显式重建步骤，不能留下旧 page_id 的悬挂数据。

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: yes

## Verification

- `cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/integration/test_knowledge_flow.py`
- `cd backend && pytest tests/contract/test_presentations.py tests/integration/test_presentation_flow.py`
- `cd web && npm test -- --run 'src/app/admin/knowledge/[id]/page.test.tsx' 'src/app/admin/presentations/[id]/page.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx'`
- Manual/browser review — 本地依次完成：在 `/admin/knowledge/[id]` 上传或重试一份产品资料并运行一次搜索诊断；再创建一个新的 sales session，训练后打开 `/practice/{sessionId}/report` 检查知识诊断状态、命中率与最近检索 query。随后在 `/admin/presentations/[id]` 替换标准 PPT 或更新当前页要点/禁忌词，再从 `/agents/[agentId]` 新建 presentation 练习，确认页面版本与练习读取内容都已刷新。
- Failure-path inspection — 用一个 failed/pending 知识文档验证重试按钮与错误文案；在有非终态 presentation session 时触发标准 PPT 替换，确认 admin UI 和 API 明确暴露“被活动会话阻止”而不是静默改写进行中的演练材料。

## Observability / Diagnostics

- Runtime signals: `practice_sessions.voice_policy_snapshot.knowledge_base_ids`、`runtime_metrics.knowledge_retrieval.*`、`/practice/sessions/{id}/knowledge-check` 状态字段、`presentations.status/version_number/total_pages`、presentation replace 阻断错误码与处理日志。
- Inspection surfaces: `web/src/app/admin/knowledge/[id]/page.tsx` 的文档状态/重试/搜索面板、`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 的知识诊断卡、`web/src/app/admin/presentations/[id]/page.tsx` 的版本/替换状态、`web/src/app/(dashboard)/agents/[agentId]/page.tsx` 的演练材料选择器。
- Failure visibility: failed 文档的 `error_message`、kb_not_ready/search_failed/miss 状态、replace 被活动会话阻止的错误、presentation `processing -> failed` 过渡和当前 `version_number`。
- Redaction constraints: 只暴露知识库 ID、命中状态、检索 query 摘要、presentation 版本/页数/状态等非敏感诊断；不得把原始转写、密钥或用户隐私数据写入诊断面。

## Integration Closure

- Upstream surfaces consumed: `backend/src/common/knowledge/api.py`, `backend/src/sales_bot/services/voice_runtime_policy.py`, `backend/src/common/api/practice.py`, `backend/src/presentation_coach/api/presentations.py`, `backend/src/presentation_coach/services/coach_service.py`, `web/src/lib/api/client.ts`, `web/src/app/admin/knowledge/[id]/page.tsx`, `web/src/app/admin/presentations/[id]/page.tsx`, `web/src/app/(dashboard)/agents/[agentId]/page.tsx`.
- New wiring introduced in this slice: admin 知识库详情页调用 search/reprocess 合同并与新建 sales session 生效证明联动；标准 PPT 原位替换入口与 `version_number`/状态可视化接入现有 presentation CRUD 和用户演练选择器。
- What remains before the milestone is truly usable end-to-end: S05 需要消费这条“最新知识材料”输入面来约束销售价值表达；S07 需要在最新 PPT 材料之上输出统一会后复盘。本 slice 完成后，材料更新即生效这条链路本身不再依赖额外手工操作。

## Tasks

- [ ] **T01: 补齐知识库更新诊断并证明新 sales session 吃到最新产品资料** `est:4h`
  - Why: 产品资料这半条链当前最真实的缺口不是“没有知识库”，而是管理员无法自助恢复 failed/pending 文档，也无法在 UI 里判断 ready / miss / kb_not_ready；同时 S04 必须把“下一次新建 session 才吃到新资料、旧 session 快照不回写”这条权威线锁死。
  - Files: `backend/src/common/knowledge/api.py`, `backend/tests/integration/test_knowledge_api.py`, `backend/tests/integration/test_knowledge_upload_persistence.py`, `backend/tests/integration/test_knowledge_flow.py`, `web/src/lib/api/client.ts`, `web/src/lib/api/types.ts`, `web/src/app/admin/knowledge/[id]/page.tsx`, `web/src/app/admin/knowledge/[id]/page.test.tsx`
  - Do: 对齐知识库上传/search/reprocess 的前后端合同，保持 `xlsx/xls` 可上传并复用现有 reprocess API；在知识库详情页增加 failed/pending 文档重试、ready/not_ready 文案与搜索诊断面板；把 backend integration proof 扩到“persona 绑定 KB -> 上传/重试文档 -> 新建 sales session -> `/knowledge-check` 看到最新状态”，并明确旧 session 不被新资料回写。
  - Verify: `cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/integration/test_knowledge_flow.py && cd ../web && npm test -- --run 'src/app/admin/knowledge/[id]/page.test.tsx'`
  - Done when: 管理员能在知识库详情页直接上传/重试/搜索产品资料，且 targeted tests 证明新建 sales session 会冻结当时的 KB 绑定并把 hit / miss / kb_not_ready 诊断暴露到会后检查面。
- [ ] **T02: 实现标准 PPT 原位替换并验证下一次演练读取最新页面** `est:5h`
  - Why: 现有 `/presentations` 上传只会生成新的 `presentation_id`，无法满足“标准 PPT 更新后下一次训练直接生效”；S04 需要把标准 PPT 变成一个稳定身份，同时避免正在进行的演练被后台替换 silently 污染。
  - Files: `backend/src/presentation_coach/api/presentations.py`, `backend/tests/contract/test_presentations.py`, `backend/tests/integration/test_presentation_flow.py`, `web/src/lib/api/client.ts`, `web/src/app/admin/presentations/[id]/page.tsx`, `web/src/app/admin/presentations/[id]/page.test.tsx`, `web/src/app/(dashboard)/agents/[agentId]/page.tsx`, `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx`
  - Do: 在 presentations API 中新增“原位替换同一 standard presentation”的入口，保持 `presentation_id` 稳定、递增 `version_number`、重跑解析/缩略图/页面数据，并在存在非终态 session 时阻止替换；替换时显式清理并重建依赖 page_id 的 coaching 数据，再让 admin 详情页显示版本/状态/替换 CTA，用户演练选择器显示当前版本与材料状态，从而让下一次新建 presentation session 读取最新 `Page` / `RequiredTalkingPoint` / `ForbiddenWord`。
  - Verify: `cd backend && pytest tests/contract/test_presentations.py tests/integration/test_presentation_flow.py && cd ../web && npm test -- --run 'src/app/admin/presentations/[id]/page.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx'`
  - Done when: 管理员可以在同一 presentation 详情页完成标准 PPT 替换并看到版本/状态变化；活跃会话存在时替换会被明确阻止；用户从原有入口新建下一次 presentation 练习时，不需要手工追新 ID 也能读到最新页面内容与规则。

## Files Likely Touched

- `backend/src/common/knowledge/api.py`
- `backend/tests/integration/test_knowledge_api.py`
- `backend/tests/integration/test_knowledge_upload_persistence.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/tests/contract/test_presentations.py`
- `backend/tests/integration/test_presentation_flow.py`
- `web/src/lib/api/client.ts`
- `web/src/lib/api/types.ts`
- `web/src/app/admin/knowledge/[id]/page.tsx`
- `web/src/app/admin/knowledge/[id]/page.test.tsx`
- `web/src/app/admin/presentations/[id]/page.tsx`
- `web/src/app/admin/presentations/[id]/page.test.tsx`
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx`
- `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx`
