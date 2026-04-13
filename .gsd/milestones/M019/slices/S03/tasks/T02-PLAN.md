---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T02: 拆分 API client 与 websocket transport helpers

- 先按 domain 拆 `client.ts`，保留统一 auth/error/trace seam，再把 outward `api` façade 指回域模块。
- 对 `use-practice-websocket.ts` 继续下沉可下沉的 URL/auth/reconnect/backpressure helper，但保留它作为 outward transport hook，避免页面本地拼 websocket 行为。
- 确保 `authHandler`、trace-context、shared types 仍是唯一 cross-cutting seam。

## Inputs

- `T01 inventory`
- `现有 web tests`

## Expected Output

- `web/src/lib/api/*.ts`
- `web/src/hooks/websocket/*.ts`
- `web/src/lib/api/client.ts`

## Verification

npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
