---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T01: 盘点并分类前端 console 使用点

Why: 先拿到真实 console inventory，避免把 instrumentation/dev-only 输出和业务页面噪声混在一起。

Do:
1. 扫描 `web/src` 下所有 `console.log/error/warn/info` 使用点。
2. 按 `debug-only`、`durable error`、`instrumentation`、`tests` 四类归档。
3. 记录哪些调用应迁到 `web/src/lib/debug.ts`，哪些是允许保留的例外。
4. 明确 route error surface 与业务页面当前的日志分歧。

Done when: 已形成一份可执行的分类结论，后续任务可以按这份分类迁移，而不是再次全仓搜索后现场判断。

## Inputs

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- `web/src/instrumentation.ts`
- `web/src/instrumentation-client.ts`

## Expected Output

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`

## Verification

rg -n "console\.(log|error|warn|info)" web/src

## Observability Impact

建立 console inventory 与共享 debug seam 的例外边界。
