---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 实现 shared debug seam 收口

扩展或收口 shared debug/observability helper，把业务页面与 route error surface 的日志出口统一到这条 seam；保留必要 instrumentation 例外。

## Inputs

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`

## Expected Output

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- `web/src/app/**/error.tsx`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"

## Observability Impact

前端 durable error 出口统一
