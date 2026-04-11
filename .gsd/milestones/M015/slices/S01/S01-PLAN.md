# S01: 前端日志出口统一化

**Goal:** 把前端大量 console.* 调用收口到明确的 debug/observability seam，并区分 dev-only 与 durable error reporting。
**Demo:** 前端业务页面中的 console 输出被统一收口到共享 debug/observability seam。

## Must-Haves

- 业务页面与 hooks 中的散落 console 输出被归类，并迁到共享 debug/observability seam。
- route error surface、业务页面和 hooks 对“允许保留的 instrumentation/dev-only console”有统一边界，不再各自为政。
- focused proof 能同时证明业务页面不再直出高噪声 console，以及共享 debug seam 仍保留必要诊断信号。

## Proof Level

- This slice proves: integration

## Integration Closure

S01 建立共享 debug seam 和例外规则，供 M015/S02 的 dialog/router 清理与 M015/S03 的 learner fallback 直接复用，而不是继续在页面本地决定日志出口。

## Verification

- 前端业务故障会经共享 debug/observability seam 暴露；future agents 可从统一 helper、route error surface 和 focused grep/test gate 判断哪些日志是业务态、哪些是 instrumentation 例外。

## Tasks

- [x] **T01: 盘点并分类前端 console 使用点** `est:30m`
  Why: 先拿到真实 console inventory，避免把 instrumentation/dev-only 输出和业务页面噪声混在一起。

Do:
1. 扫描 `web/src` 下所有 `console.log/error/warn/info` 使用点。
2. 按 `debug-only`、`durable error`、`instrumentation`、`tests` 四类归档。
3. 记录哪些调用应迁到 `web/src/lib/debug.ts`，哪些是允许保留的例外。
4. 明确 route error surface 与业务页面当前的日志分歧。

Done when: 已形成一份可执行的分类结论，后续任务可以按这份分类迁移，而不是再次全仓搜索后现场判断。
  - Files: `web/src/lib/debug.ts`, `web/src/components/ErrorBoundary.tsx`, `web/src/instrumentation.ts`, `web/src/instrumentation-client.ts`
  - Verify: rg -n "console\.(log|error|warn|info)" web/src

- [ ] **T02: 实现 shared debug seam 收口** `est:45m`
  Why: 把业务页面与 route error surface 的日志出口统一到一条 shared seam，避免后续继续在页面本地直出 console。

Do:
1. 扩展或收口 `web/src/lib/debug.ts`，让业务日志与 durable error 通过统一 helper 输出。
2. 把高噪声业务页面与 route `error.tsx`/ErrorBoundary 的日志迁到这条 seam。
3. 保留必要 instrumentation 例外，并让例外边界在代码里可见。
4. 不重写观测体系；只收口当前 audit 命中的高噪声 surface。

Done when: 共享 debug seam 成为业务页面与 route error surface 的默认日志出口，focused 页面测试保持通过。
  - Files: `web/src/lib/debug.ts`, `web/src/components/ErrorBoundary.tsx`, `web/src/app/**/error.tsx`
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"

- [ ] **T03: 清理业务页面与 hooks 中的散落 console** `est:45m`
  Why: 只有把高噪声业务页面和 hooks 的散落 console 清掉，S01 才算真正收口，而不是只增加了一个 helper。

Do:
1. 按 T01 的分类结果替换高噪声业务页面和 hooks 中的散落 console。
2. 对允许保留的 instrumentation/dev-only 例外保持最小范围，不扩大例外面。
3. 补 focused proof，锁定“业务页面不再直出 console，但 instrumentation 例外仍允许存在”的边界。

Done when: `rg` 扫描不再在业务页面看到高噪声 console，focused tests 通过，剩余例外都能解释其存在。
  - Files: `web/src/**/*.ts`, `web/src/**/*.tsx`
  - Verify: rg -n "console\.(log|error|warn|info)" web/src

## Files Likely Touched

- web/src/lib/debug.ts
- web/src/components/ErrorBoundary.tsx
- web/src/instrumentation.ts
- web/src/instrumentation-client.ts
- web/src/app/**/error.tsx
- web/src/**/*.ts
- web/src/**/*.tsx
