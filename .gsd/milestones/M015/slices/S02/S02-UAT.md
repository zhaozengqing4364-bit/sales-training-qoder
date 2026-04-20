# S02: 原生弹窗与 window.location 跳转清理 — UAT

**Milestone:** M015
**Written:** 2026-04-11T18:19:15.547Z

# S02 UAT — 非中断式确认与统一跳转 seam

## Preconditions
- 使用一个可访问 `/admin/*` 与 learner dashboard 的有效账号。
- 系统中至少存在 1 条训练记录、1 个 RAG 配置、1 个 Persona。
- 浏览器允许观察 toast / dialog 行为；若要验证 auth 过期，可在测试环境中让受保护请求返回 401。

## Test Case 1 — `/admin/records` 删除记录必须走共享确认框而不是浏览器原生 confirm
1. 打开 `/admin/records`。
   - 预期：页面正常渲染，列表中可见某条记录（例如“首通销售演练”）。
2. 点击该记录的“删除记录 …”按钮。
   - 预期：出现应用内确认框，标题为“删除训练记录”，文案带上被删记录名称；浏览器没有弹出原生 confirm。
3. 点击取消或关闭确认框。
   - 预期：记录仍保留，未发出删除成功反馈。
4. 再次点击删除，并在确认框中点击“删除”。
   - 预期：删除请求才会触发；成功后显示“删除成功” toast，列表移除该记录。
5. 边界场景：让删除接口返回失败。
   - 预期：页面停留在当前列表，显示失败 toast（如“删除失败”），浏览器没有原生 alert。

## Test Case 2 — `/admin/rag-profiles` 删除确认与迁移入口都必须走应用内 seam
1. 打开 `/admin/rag-profiles`。
   - 预期：能看到现有 RAG 配置列表（例如“标准检索配置”）。
2. 点击“前往检索策略页面”。
   - 预期：应用内导航到 `/admin/retrieval-strategies`，不出现浏览器整页硬跳转感或原生弹窗。
3. 返回 `/admin/rag-profiles` 后，点击某条配置的“删除配置 …”按钮。
   - 预期：出现应用内确认框，标题为“删除 RAG 配置”。
4. 在确认框中点击“删除”。
   - 预期：删除成功 toast 出现，配置从列表移除；全程无浏览器原生 confirm/alert。

## Test Case 3 — `/admin/personas/[id]` 缺字段与保存失败必须留在编辑页并给出 toast
1. 打开任一 Persona 编辑页，例如 `/admin/personas/{personaId}`。
   - 预期：页面可见“当前 Persona 压力模型”等编辑表单内容。
2. 清空“角色名称”等必填字段后点击“保存”。
   - 预期：不会提交更新请求；显示 toast（如“请输入角色名称”）；浏览器没有原生 alert。
3. 恢复合法字段并让保存接口返回失败。
   - 预期：页面仍停留在当前编辑页；显示 toast（如“保存失败: 后端异常”）；不会被强制跳离页面。
4. 使用合法数据再次保存且接口成功。
   - 预期：更新成功后走应用内导航返回 `/admin/personas`；不会依赖浏览器原生跳转或 alert。

## Test Case 4 — Auth 过期与壳层回退必须统一走 `authHandler` / router seam
1. 进入 learner dashboard 任一受保护页面，或 admin shell 页面。
2. 在测试环境中让当前用户请求返回 401（例如让 current-user 请求失效）。
   - 预期：页面仍先走应用内壳层逻辑；出现登录过期提示；随后通过 router seam 跳到 `/login`，而不是立刻触发 `window.location.assign` / `window.location.href` 硬跳转。
3. 在 admin shell 中用一个非 admin 角色访问 admin 页面。
   - 预期：页面使用本地 `router.replace("/")` 回退到首页，而不是触发 auth 过期逻辑或浏览器级重载。
4. 边界场景：auth 过期发生时 router bridge 尚未注册完成。
   - 预期：跳转会在 shared authHandler seam 上等待 navigator 可用后继续完成，而不是丢失重定向或退回浏览器原生 location 行为。

## Exception Audit
1. 运行 `rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src`。
   - 预期：只剩三类已知例外：`web/src/components/ErrorBoundary.tsx`、`web/src/lib/performance.ts`、`web/src/app/admin/error.tsx`。
2. 复核这些例外。
   - 预期：前两者仅用于 URL 诊断采样，后者是明确允许的 admin error fallback reload；业务删除确认、auth redirect 与普通页面导航都不再依赖原生弹窗或硬跳转。
