# S01: 前端日志出口统一化

**Goal:** 把前端大量 console.* 调用收口到明确的 debug/observability seam，并区分 dev-only 与 durable error reporting
**Demo:** After this: 前端业务页面中的 console 输出被统一收口到共享 debug/observability seam

## Tasks
- [ ] **T01: 盘点并分类前端 console 使用点** — 扫描 web/src 下所有 console.* 使用点，按 debug-only / durable error / instrumentation / tests 分类，明确哪些需要迁到 shared debug seam，哪些是允许例外。
  - Estimate: 30m
  - Files: web/src/lib/debug.ts, web/src/components/ErrorBoundary.tsx
  - Verify: rg -n "console\.(log|error|warn|info)" web/src
- [ ] **T02: 实现 shared debug seam 收口** — 扩展或收口 shared debug/observability helper，把业务页面与 route error surface 的日志出口统一到这条 seam；保留必要 instrumentation 例外。
  - Estimate: 45m
  - Files: web/src/lib/debug.ts, web/src/components/ErrorBoundary.tsx, web/src/app/**/error.tsx
  - Verify: npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"
- [ ] **T03: 清理业务页面与 hooks 中的散落 console** — 替换高噪声业务页面和 hooks 中的散落 console，补最小 proof，确保保留 instrumentation/dev-only 例外但业务页面不再直出 console。
  - Estimate: 45m
  - Files: web/src/**/*.ts, web/src/**/*.tsx
  - Verify: rg -n "console\.(log|error|warn|info)" web/src
