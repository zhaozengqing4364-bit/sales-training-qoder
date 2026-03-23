# M001/S04 — Research

**Date:** 2026-03-23

## Summary

S04 owns **R004**: 管理员更新公司标准 PPT / 产品资料后，**下一次新建训练**必须吃到新材料，而且链路上要有可诊断证据。现有代码已经不是从零开始：销售链路的“产品资料”事实源已经收口到**角色中心的知识库绑定**，会在 `create_session` 时通过 `VoiceRuntimePolicyService.resolve_effective_policy(...)` 冻结进 `PracticeSession.voice_policy_snapshot`，训练后又能通过 `/practice/sessions/{id}/knowledge-check` 把是否真正触发检索、是否命中、是否因为 KB 未 ready 被阻断暴露给报告页。PPT 链路则是另一条独立事实线：上传/解析后的 `Presentation` / `Page` / `RequiredTalkingPoint` / `ForbiddenWord` 在运行时由 `PresentationCoachService.get_current_page_requirements(...)` **按页实时读取**，所以“下一次训练吃到新 PPT 内容”本质上取决于管理员更新的是同一份 presentation/page 数据，还是重新上传出一个新的 `presentation_id`。

因此，这个 slice 更像**双链路收口与证明**，不是新建知识系统。建议把 S04 拆成两条可验证子链：**(1) 销售知识库更新 → 新 sales session snapshot → runtime retrieval → report diagnostics**；**(2) PPT 材料更新 → 新 presentation session / 页面上下文读取 → 用户页可见最新页内容与规则**。优先复用现有权威面，不要把遗留的并行 API 再做大：销售侧以 persona policy + runtime snapshot 为准，PPT 侧以 `/presentations` + `PresentationCoachService` 为准。

## Recommendation

采用**“证明现有权威链路 + 补齐缺失管理/诊断入口”**的做法，而不是新增一套材料版本体系。

1. **销售资料链路**：把 `persona_policy.knowledge_base_ids` → `VoiceRuntimePolicyService.resolve_effective_policy(...)` → `PracticeSession.voice_policy_snapshot` → `search_internal_knowledge(...)` 运行时指标 → `/practice/sessions/{id}/knowledge-check` 当成唯一事实线。若 S04 需要用户/管理员能看出“更新是否生效”，优先补**新会话创建后的快照证据**和**命中/未命中/未就绪**诊断，不要再引入 agent 级知识库回退写路径。
2. **PPT 链路**：把 `backend/src/presentation_coach/api/presentations.py` 和 `PresentationCoachService.get_current_page_requirements(...)` 当成权威面。当前代码天然支持“**同一 presentation_id 下页内容/要点/禁忌词被改后，下一次训练读到新值**”；但如果产品要求的是“**替换同一份标准 PPT 文件且保留稳定身份**”，现有上传路径还不满足，因为重新上传会生成新的 `presentation_id`。这需要先明确是只证明“编辑现有页面元数据立即生效”，还是要真正做“版本替换/回滚”。
3. **执行策略**：先把两条链路的**可证明边界**固定住，再决定 UI 只补最小缺口：知识库详情页目前只有 upload/preview/delete，没有 reprocess/search 入口；PPT 管理页有上传与页面编辑，但没有“替换当前标准版本”的稳定语义。按 `safe-grow` 和项目 AGENTS 规则，应先做最小直接变更、一次只推进一个真实用户问题。

## Implementation Landscape

### Key Files

- `backend/src/agent/services/persona_policy.py` — 角色中心的规范化入口；把 `system_prompt`、`knowledge_base_ids`、`tool_policy` 收敛成 persona policy，是销售资料绑定的上游事实源。
- `backend/src/agent/services/persona_service.py` — persona CRUD 会把 `persona_policy` 与 legacy 字段同步；如果 S04 需要补“知识库绑定是否持久化/是否漂移”的验证，这里是写入口。
- `web/src/app/admin/personas/[id]/page.tsx` — 当前**唯一用户可操作的知识库绑定 UI**；Agent 页面已经明确提示“知识库归属迁移到角色中心”，所以销售材料配置必须从这里继续扩，不应回到 agent 级入口。
- `backend/src/sales_bot/services/voice_runtime_policy.py` — **销售链路最关键的权威翻译层**：把 persona 绑定的 KB、tool policy、runtime profile 编译成 session effective policy，并自动在有 KB 绑定时强制 `kb_only` / `require_kb_grounding`。
- `backend/src/common/api/practice.py` — `create_session` 会把 effective policy 冻结到 `PracticeSession.voice_policy_snapshot`；`/practice/sessions/{id}/knowledge-check` 会把 KB 绑定数、attempt/hit/hit_rate、kb_not_ready、kb_lock 状态等诊断对外暴露。S04 的“下一次新建训练生效”证明必须经过这里。
- `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py` — 实际执行 `search_internal_knowledge`，并区分 `missing_query` / `no_kb_bound` / `kb_not_ready` / `search_failed` / `hit|miss`；是 report diagnostics 的运行时来源。
- `backend/src/sales_bot/websocket/components/stepfun_helpers.py` — 把 knowledge retrieval 指标写回 `runtime_metrics.knowledge_retrieval`；S04 如需新增诊断字段，应沿用这里，不要新开一套统计结构。
- `backend/src/common/knowledge/api.py` — KB CRUD / upload / preview / search / **reprocess** API。注意：后端已有 `POST /admin/knowledge/{kb_id}/documents/{doc_id}/reprocess`，但前端尚未暴露。
- `backend/src/common/knowledge/service.py` — KB 检索与 ready gating 的核心：`search_multiple(...)` 只检索 `status=ready && chunk_count>0` 的文档；`get_search_health(...)` / `_get_ready_document_ids_by_kb(...)` / keyword fallback 让“已上传但未 ready”为可诊断状态。
- `web/src/app/admin/knowledge/[id]/page.tsx` — KB 文档管理 UI。目前只有 upload/preview/delete，能展示 failed 文本错误，但**没有 reprocess/search 诊断入口**；前端 `accept` 还停留在 `.pdf,.docx,.txt,.md`，未跟上后端已支持的 `xlsx/xls`。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 用户端已消费 `/knowledge-check` 并展示“绑定知识库 / 检索次数 / 命中问答 / 命中率 / 最近检索问题”；销售链路的 slice-close 证明面已经在这里。
- `backend/src/presentation_coach/api/presentations.py` — 当前 web 实际在用的 PPT 上传/列表/详情/页面/缩略图 API。上传会创建新的 `Presentation` 记录并把 `status` 走完 `processing -> ready|failed`。
- `web/src/app/admin/presentations/page.tsx` — 管理端 PPT 列表/上传页；注意它调用的是 `api.presentations.*`（`/presentations`），**不是** legacy 的 `api.adminPresentations.*`。
- `web/src/app/admin/presentations/[id]/page.tsx` — 管理端编辑页，可直接维护页面 talking points / forbidden words；如果 S04 的 PPT 证明选择“编辑现有 presentation/page 元数据后下一次训练生效”，这里就是主要入口。
- `backend/src/presentation_coach/services/coach_service.py` — Presentation runtime 的权威读模型；`get_current_page_requirements(...)` 每次按 `session.presentation_id + current page` 读取 `Page.ocr_extracted_text`、确认过的 `RequiredTalkingPoint`、`ForbiddenWord`。这意味着**更新现有页数据后，新 session 会自然读取最新值**。
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx` — 用户创建 presentation 练习时会显式选择 `presentation_id`；如果管理员重新上传形成新 presentation 记录，用户必须重新选中它，系统不会自动替换旧标准版。
- `backend/src/common/ppt/version_manager.py` — 已存在但未接线的版本管理器；若 S04 需要“同一标准 PPT 的替换/回滚”语义，这是最自然的 seam，但当前没有任何 API/UI 调用它。
- `backend/src/admin/api/admin.py` — 旧的 admin PPT API，和当前 `/presentations` 平行存在。S04 规划应避免继续扩这条支线，除非明确要做统一迁移。

### Build Order

1. **先固定每条链路的权威面，不做并行扩张。**
   - 销售资料：`persona policy -> voice runtime policy -> session snapshot -> knowledge-check`。
   - PPT 材料：`/presentations -> Page / TalkingPoint / ForbiddenWord -> coach_service.get_current_page_requirements()`。
   - 这一步直接决定 planner 不应该把工时浪费在 `backend/src/admin/api/admin.py` 或 agent-level KB 写入口上。

2. **先证明 sales 知识库“更新后下一次新 session 生效”。**
   - 这是 R004 最直接、现成度最高的子链。
   - 先验证 persona 绑定 KB、KB 文档 ready、创建新 session 后 snapshot 中 `knowledge_base_ids` 存在、训练后 report `knowledge-check` 能看到 hit/miss/not_ready。
   - 若缺口存在，优先补 admin KB reprocess/diagnostics，而不是重写 retrieval。

3. **再明确 PPT 的“更新”语义。**
   - 如果 slice 只要求“管理员编辑当前标准 PPT 的页内容/讲解点/禁忌词，下一次训练立即生效”，现有 `get_current_page_requirements(...)` 已经接近满足，只需要证明与补测试。
   - 如果 slice 要求“替换整份标准 PPT 文件且无需用户重新选 presentation_id”，则当前实现缺少稳定版本别名，必须单独规划基于 `version_manager` 的 replace/version seam。

4. **最后补最小 UI 缺口与回归测试。**
   - KB 页：reprocess、search/ready 诊断、类型 accept/copy 对齐后端。
   - PPT 页：必要时补“当前标准版 / 版本替换 / 最新可用版”信息，但避免大规模重做管理台。

### Verification Approach

**Backend focused**

- `cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/unit/common/test_knowledge_service_fallback.py tests/unit/common/test_knowledge_service_preview_fallback.py tests/unit/test_stepfun_internal_knowledge_searcher.py tests/unit/test_voice_runtime_policy_service.py`
  - 覆盖 KB upload/list/search/reprocess、ready gating、keyword fallback、persona KB 锁策略。
- 若做 PPT 链路证明，新增或扩充：
  - `backend/tests/contract/test_presentations.py`
  - `backend/tests/integration/test_presentation_flow.py`
  - 重点不是 WebSocket 全流程，而是“更新后的 `Page/RequiredTalkingPoint/ForbiddenWord` 被新 session 读取”。

**Frontend focused**

- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
  - 已覆盖 report 对 unified evidence / knowledge-check 的稳定消费。
- 如果补 admin KB/PPT 入口，新增对应页面测试，重点锁定：失败文档 reprocess CTA、diagnostic copy、presentation update selector / replace copy。

**Observable proof**

- 销售链：
  1. 管理员在 persona 详情页绑定知识库。
  2. 管理员上传/更新文档并等到 `ready`，或对 failed/pending 文档执行 reprocess。
  3. 新建 sales session。
  4. 训练后 report 页“知识库命中检测”显示新的 KB 绑定数、attempt/hit 状态、最近检索 query；旧 session 不应被回写成新材料快照。
- PPT 链：
  1. 管理员修改现有 presentation 的 page text / talking points / forbidden words，或明确替换版本。
  2. 新建 presentation session。
  3. runtime 读取到的 page context 与管理员最新修改一致，而不是沿用旧会话缓存。

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| 销售材料如何绑定进下一次训练 | `VoiceRuntimePolicyService.resolve_effective_policy(...)` + `PracticeSession.voice_policy_snapshot` | 这是现有权威写入口，report diagnostics 也围绕它工作；另起一套材料注入会造成快照与报告漂移。 |
| 如何判断 KB 更新是否真正参与训练 | `/practice/sessions/{id}/knowledge-check` + `stepfun_helpers.update_knowledge_runtime_metrics(...)` | 已有 hit/miss/not_ready/search_failed 指标面，不需要重新设计会后诊断协议。 |
| PPT 训练时如何拿最新页内容/规则 | `PresentationCoachService.get_current_page_requirements(...)` | 它已经直接查 `Page` / `RequiredTalkingPoint` / `ForbiddenWord`，天然支持“下一次训练读当前 DB 最新值”。 |
| KB 失败文档如何恢复 | `POST /admin/knowledge/{kb_id}/documents/{doc_id}/reprocess` | 后端已实现重处理，不应再新增平行恢复 API；优先补前端入口即可。 |
| 若必须做 PPT 替换/回滚 | `backend/src/common/ppt/version_manager.py` | 现有但未接线，比重新发明“标准 PPT 版本表”更适合做最小扩展。 |

## Constraints

- **遵循项目最小改动原则**：根据仓库 `AGENTS.md` 与 `safe-grow`，S04 应只推进“更新后下一次训练生效”这一个真实问题，避免顺手整理整套知识/PPT 架构。
- **Sales session snapshot 是 immutable 的**：`voice_policy_snapshot` 在 `create_session` 时冻结，因此“材料更新生效”的证明必须基于**新 session**，不是修改中的旧 session。
- **PPT runtime 不是 snapshot-based**：presentation 页内容在运行时按 `presentation_id + page_number` 即时查询；若要支持稳定标准版替换，当前缺的是版本身份层，不是读取层。
- **Admin KB UI 与 backend 能力已发生偏差**：前端 accept/copy 仍停留在 PDF/DOCX/TXT/MD，但 backend 已支持 `xlsx/xls`；若 slice 触碰上传入口，前后端必须同步。
- **UI 变更要遵守已加载 skill 规则**：`baseline-ui` 要求最小 diff、错误贴近动作位置；`accessibility` 要求 icon-only controls 具备可读名称；`verification-before-completion` 要求所有“已生效”声明必须有 fresh command/runtime evidence 支撑。

## Common Pitfalls

- **改错 PPT API 面** — `web/src/app/admin/presentations/*` 目前实际走的是 `api.presentations`（`/presentations`），不是 `api.adminPresentations`（`/admin/presentations`）。如果只改 legacy admin API，用户可见链路不会变。
- **把 KB 重新绑回 agent 级** — agent 详情页已经明确“知识库归属迁移到角色中心”。继续扩 agent-level KB 会重新制造 persona/agent 漂移。
- **把“上传成功”当成“可检索”** — `KnowledgeService.search_multiple(...)` 只检索 `status=ready && chunk_count>0` 的文档；`pending/processing/failed` 只能算“已提交”，不能算“已生效”。
- **用当前报告证明更新已生效** — 旧 sales session 的 `voice_policy_snapshot` 不会随管理员更新而改变；必须新建 session 才能证明下一次训练吃到新材料。
- **把“重新上传 PPT”误当成“替换标准版”** — 当前上传会创建新的 `presentation_id`；如果用户仍选择旧 presentation，训练仍会读旧材料。除非明确接线 version/alias，否则只能证明“新上传的 presentation 可被下一次训练选用”。

## Open Risks

- **“标准 PPT 更新”语义仍需在规划时锁定** — 如果目标只是“编辑现有 `presentation_id` 下的页面内容/要点/禁忌词后，下一次训练生效”，现有 `PresentationCoachService` 已有天然支撑；如果目标是“替换同一标准 PPT 且不要求用户重新选 `presentation_id`”，当前实现缺稳定版本别名或 replace 入口，必须单独规划。
- **KB 管理端的恢复能力可能是 slice 验收前置** — 后端已有 `reprocess`，但前端知识库详情页还没有入口；如果执行时继续碰到 embedding 配置/额度问题，不把恢复动作暴露出来，管理员很难真正把“更新即生效”走通。
- **PPT API 双轨仍有误用风险** — 仓库同时存在 `/presentations` 与 `/admin/presentations`；当前用户与管理页主要走前者。若执行时误扩 legacy admin API，容易造成“代码改了但真实链路没变”的假进展。

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| React / Next.js admin & report surfaces | installed: `react-best-practices`, `vercel-react-best-practices`, `baseline-ui`, `accessibility`, `best-practices` | available |
| FastAPI backend APIs | `wshobson/agents@fastapi-templates` | discovered via `npx skills find "fastapi"` |
| ChromaDB knowledge retrieval | `kimasplund/claude_cognitive_reasoning@chromadb-integration-skills` | discovered via `npx skills find "chromadb"` |
| python-pptx / PPT handling | `vamseeachanta/workspace-hub@python-pptx` | discovered via `npx skills find "python-pptx"` |
