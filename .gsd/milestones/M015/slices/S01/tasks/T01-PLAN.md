---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: 盘点并分类前端 console 使用点

扫描 web/src 下所有 console.* 使用点，按 debug-only / durable error / instrumentation / tests 分类，明确哪些需要迁到 shared debug seam，哪些是允许例外。

## Inputs

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- `web/src/instrumentation.ts`
- `web/src/instrumentation-client.ts`

## Expected Output

- `web/src/lib/debug.ts`
- `audit console inventory`

## Verification

rg -n "console\.(log|error|warn|info)" web/src

## Observability Impact

console inventory 形成规则清单
