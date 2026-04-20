# S04: 知识库更新即生效链路 — UAT

**Milestone:** M001
**Written:** 2026-03-23T19:07:30+08:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: S04 同时覆盖 admin 自助维护、session snapshot/diagnostics、presentation replace blocker 和 user entry 材料可见性；需要自动化证明 contract，也需要本地页面与 API 联动的活体检查。

## Preconditions

- 本地 backend 运行在 `http://localhost:3444`，web 运行在 `http://localhost:3445`。
- 使用 `POST http://localhost:3444/api/v1/auth/dev-login` 登录到本地开发账号；当前 closure 使用的是 admin 身份 `repair@example.com`。
- 当前种子数据中可直接复用以下对象：
  - 知识库：`7295703d-d400-4289-baef-62598051ffe7`（名称：`测试知识库`）
  - ready standard presentation：`20706b4b-bb22-484a-8f2f-8ecacc43bb3b`（名称：`石犀`，当前 `v1 / ready / 36 pages`）
  - presentation agent：`7199854c-3921-4d9f-9833-fe99ca209c59`（名称：`ppt训练`）
  - sales agent：`dee4a877-2f19-47f4-a326-954f2ab554d5`（名称：`语言的魅力`）
  - sales persona：`5ff0c27e-ea3d-4f4a-9cfe-eae1946feff2`（名称：`挑剔型客户`）
- 若要复现实测中的 replace blocker，可使用本地文件 `/Users/zhaozengqing/github/销售训练qoder/backend/data/ppts/5d63f1d6-1bf5-41b9-81ff-8a8827679225.pptx` 作为上传样本。

## Smoke Test

- 打开 `http://localhost:3445/admin/knowledge/7295703d-d400-4289-baef-62598051ffe7`，确认页面同时出现 `测试知识库`、`搜索诊断`、`文档列表` 三个区块；再打开 `http://localhost:3445/admin/presentations/20706b4b-bb22-484a-8f2f-8ecacc43bb3b`，确认头部出现 `版本 v1` 与 `原位替换标准PPT`。

## Test Cases

### 1. Admin 知识库详情页可直接做搜索诊断

1. 登录后打开 `http://localhost:3445/admin/knowledge/7295703d-d400-4289-baef-62598051ffe7`。
2. 确认页面头部显示 `1 个文档 · 1 个分块`，文档列表中的 `销售技巧指南` 状态为 `已就绪`。
3. 在 `知识库搜索诊断` 输入框中输入：`端到端 测试`。
4. 点击 `执行诊断`。
5. **Expected:** 页面不会跳离当前详情页；搜索面板给出显式结果文案（本次 closure 实测为 `未命中结果。请尝试更具体的问题，或先确认最新文档已处理完成。`），并保持 ready 文档状态可见。

### 2. 新建 sales session 会冻结知识库绑定并可通过 knowledge-check 读到

1. 保持开发登录状态，调用 `POST http://localhost:3444/api/v1/practice/sessions`，请求体：
   ```json
   {
     "scenario_type": "sales",
     "agent_id": "dee4a877-2f19-47f4-a326-954f2ab554d5",
     "persona_id": "5ff0c27e-ea3d-4f4a-9cfe-eae1946feff2"
   }
   ```
2. 记录返回的 `session_id`（本次 closure 实测为 `662543a2-07d0-4d8c-a1f0-1feffc05c23b`），并检查响应里的 `voice_policy_snapshot.knowledge_base_ids`。
3. 调用 `GET http://localhost:3444/api/v1/practice/sessions/<session_id>/knowledge-check`。
4. **Expected:** 创建会话返回 `201`；`voice_policy_snapshot.knowledge_base_ids` 非空，且 `knowledge-check` 返回相同的 `knowledge_base_ids`、`kb_bound=true` 与结构化状态字段。本次 closure 在未说话前的实测值为 `status=not_triggered`、`summary=本次对话尚未触发知识检索`。
5. （可选清理）调用 `POST /api/v1/practice/sessions/<session_id>/lifecycle` 依次发送 `{"action":"start"}` 与 `{"action":"end"}`，避免额外留下长期 `preparing` 会话。

### 3. 标准 PPT replace 在 active session 存在时会被明确阻断

1. 登录后打开 `http://localhost:3445/admin/presentations/20706b4b-bb22-484a-8f2f-8ecacc43bb3b`。
2. 确认头部显示 `石犀`、`可用`、`36 页`、`版本 v1`。
3. 在 `原位替换标准PPT` 区块选择文件 `/Users/zhaozengqing/github/销售训练qoder/backend/data/ppts/5d63f1d6-1bf5-41b9-81ff-8a8827679225.pptx`。
4. 点击 `替换标准PPT`。
5. **Expected:** 页面停留在当前详情页并显示阻断文案 `当前有进行中的演练正在使用该标准PPT，请结束后再替换。`；网络面中 `POST /api/v1/presentations/20706b4b-bb22-484a-8f2f-8ecacc43bb3b/replace` 返回 `409`，payload 带有 `error=[PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]` 和 `details.active_session_count`。

### 4. 用户入口能看到标准 PPT 的当前版本与材料状态

1. 打开 `http://localhost:3445/agents/7199854c-3921-4d9f-9833-fe99ca209c59`。
2. 在 `选择演练PPT` 区块查看下拉或选项列表。
3. 找到 `石犀（v1 · 可用 · 36 页）` 这一项并选中。
4. 检查该区块下方摘要卡。
5. **Expected:** 页面显式展示 `当前版本：v1`、`材料状态：可用`、`页数：36 页`；用户无需追新 `presentation_id`，即可从旧入口看到当前 deck 的最新版本信息。

## Edge Cases

### failed / pending 知识文档可在 UI 内重试

1. 准备一个 `failed` 或 `pending` 的知识文档（如果当前种子数据没有，可先通过后端测试夹具或临时上传制造该状态）。
2. 打开对应的 `/admin/knowledge/<kbId>` 页面。
3. 找到该文档旁边的 `重试处理` 按钮并点击。
4. **Expected:** 页面就地显示重新提交处理后的状态变化；不会要求管理员改用命令行或直接改数据库。

### unoccupied ready deck 的成功 replace 会刷新后续会话材料

1. 准备一份没有被非终态会话占用的 ready standard presentation。
2. 在 `/admin/presentations/<id>` 成功上传替换文件，等待状态回到 `ready`，并记下新 `version_number`。
3. 从对应 `/agents/<agentId>` 页面新建下一次 presentation 练习。
4. **Expected:** `presentation_id` 保持不变，但用户入口显示更新后的 `version_number / status / total_pages`，下一次新建 session 读取的是替换后的页面内容、要点与禁忌词。

## Failure Signals

- `/admin/knowledge/[id]` 看不到 `搜索诊断`、ready/not-ready 文案、失败原因或 `重试处理` 按钮。
- 新建 sales session 的返回值里没有 `voice_policy_snapshot.knowledge_base_ids`，或 `/knowledge-check` 不再暴露 `status / summary / recent_queries / last_error` 等结构化字段。
- presentation replace 在 active session 存在时静默成功，或只报泛化错误而没有 `409 + blocker payload`。
- `/agents/[agentId]` 不再显示 `v{version} · {status} · {pages}`，导致用户必须追踪新的 `presentation_id` 才知道哪份材料生效。
- 浏览器里 replace blocker 明明触发，但页面没有就地显示阻断文案，只能靠网络面猜测。

## Not Proven By This UAT

- 本 closure 没有在浏览器里强制完成一次“无占用 ready deck 的成功 destructive replace”；成功路径由 backend contract / integration tests 证明。
- 本 closure 没有重新跑完整多轮 sales 对话，把 `knowledge-check` 从 `not_triggered` 驱动到 `hit` / `miss` / `search_failed`；这些状态转换由 `backend/tests/integration/test_knowledge_flow.py` 证明。
- 本 UAT 只证明 S04 为 S07 提供了最新 PPT 材料输入面，不证明 PPT 会后统一复盘本身已经可用。

## Notes for Tester

- 本地 `20706b4b-bb22-484a-8f2f-8ecacc43bb3b` 这份 deck 当前会触发大量 thumbnail `404` 噪声；只要 `version/status` 与 replace blocker 合同正常，不要把这些 thumbnail 404 误判为 S04 主回归。
- 如果 backend 启动时出现 `redis package is required for SessionStateService`，先修复本地 Python 依赖再继续做浏览器 UAT；否则会把环境问题误看成 slice 回归。
- 若后续 auto verifier 再次报告 `pytest ... file not found` 或 `cd ../web` 失败，优先检查 task-level verify artifact 是否又被错误拆成独立命令。
