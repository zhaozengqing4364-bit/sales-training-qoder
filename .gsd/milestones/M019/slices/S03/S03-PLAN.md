# S03: Frontend domain client 与 transport seam 抽离

**Goal:** 把 `web/src/lib/api/client.ts` 与 `web/src/hooks/use-practice-websocket.ts` 收口为清晰的 domain/transport seam，保留现有页面 contract。
**Demo:** After this: `client.ts` 按 domain 拆包、`use-practice-websocket.ts` 保留 transport/orchestration outward contract，前端大文件不再是唯一事实源。

## Must-Haves

- API client 被拆成 domain-level modules/types，不再只有单一 mega file。
- practice websocket hook 的 transport boundary 保持稳定，message handlers / audio / backpressure / reconnect 的职责明确。
- focused web tests 证明 dashboard/auth/practice/report/replay 仍沿现有 contract 工作。

## Proof Level

- This slice proves: integration

## Integration Closure

S03 结束后，前端请求与 practice transport 不再被两个 mega file 独占；M020 auth transport hardening 与 M021 AI runtime surfaces 可以直接落到域模块或 transport seam。

## Verification

- 前端请求失败或 websocket 异常能先归类到 domain client、auth handler、transport orchestration、message handlers 四个层级之一。

## Tasks

- [ ] **T01: 识别前端 domain client 与 transport seam** `est:45m`
  - 盘点 `client.ts` 中的 domain surfaces（auth/dashboard/practice/admin/knowledge/support 等），标出高扇出消费点。
- 盘点 `use-practice-websocket.ts` 当前剩余 transport/orchestration 复杂度，并写清哪些职责已在 `message-handlers.ts` / audio hooks 中。
- 先补一个小型 import/contract inventory，避免拆分后页面改成跨域直连实现。
  - Files: `web/src/lib/api/client.ts`, `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/websocket`, `web/src/lib/api`
  - Verify: rg -n "export const api|normalizeApiErrorPayload|usePracticeWebSocket|MAX_RECONNECT_ATTEMPTS|message-handlers" web/src/lib/api web/src/hooks

- [ ] **T02: 拆分 API client 与 websocket transport helpers** `est:2h`
  - 先按 domain 拆 `client.ts`，保留统一 auth/error/trace seam，再把 outward `api` façade 指回域模块。
- 对 `use-practice-websocket.ts` 继续下沉可下沉的 URL/auth/reconnect/backpressure helper，但保留它作为 outward transport hook，避免页面本地拼 websocket 行为。
- 确保 `authHandler`、trace-context、shared types 仍是唯一 cross-cutting seam。
  - Files: `web/src/lib/api`, `web/src/hooks/use-practice-websocket.ts`, `web/src/hooks/websocket`, `web/src/lib/auth-handler.ts`
  - Verify: npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"

- [ ] **T03: 固定前端拆分后的 contract proof** `est:40m`
  - 更新 shared types / imports / architecture scan，让后续 slices 直接知道该改哪个 domain module、哪个 transport helper、哪个 inbound handler。
- 对 reconnect/backpressure/interrupt 的 focused tests 补齐或重定位，确保拆分没有把 contract 流失到 page-level hacks。
- 记录仍故意保留在 outward hook 中的职责，避免后续继续无依据地拆。
  - Files: `web/src/hooks/use-practice-websocket.test.ts`, `web/src/hooks/use-practice-websocket.ts`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`
  - Verify: npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"

## Files Likely Touched

- web/src/lib/api/client.ts
- web/src/hooks/use-practice-websocket.ts
- web/src/hooks/websocket
- web/src/lib/api
- web/src/lib/auth-handler.ts
- web/src/hooks/use-practice-websocket.test.ts
- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
