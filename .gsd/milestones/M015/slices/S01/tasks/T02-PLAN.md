---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T02: 实现 shared debug seam 收口

Why: 把业务页面与 route error surface 的日志出口统一到一条 shared seam，避免后续继续在页面本地直出 console。

Do:
1. 扩展或收口 `web/src/lib/debug.ts`，让业务日志与 durable error 通过统一 helper 输出。
2. 把高噪声业务页面与 route `error.tsx`/ErrorBoundary 的日志迁到这条 seam。
3. 保留必要 instrumentation 例外，并让例外边界在代码里可见。
4. 不重写观测体系；只收口当前 audit 命中的高噪声 surface。

Done when: 共享 debug seam 成为业务页面与 route error surface 的默认日志出口，focused 页面测试保持通过。

## Inputs

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- `web/src/app/**/error.tsx`

## Expected Output

- `web/src/lib/debug.ts`
- `web/src/components/ErrorBoundary.tsx`
- `web/src/app/**/error.tsx`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"

## Observability Impact

业务日志与 durable error 通过共享 seam 输出，日志边界更可诊断。
