---
estimated_steps: 3
estimated_files: 4
skills_used: []
---

# T01: 识别前端 domain client 与 transport seam

- 盘点 `client.ts` 中的 domain surfaces（auth/dashboard/practice/admin/knowledge/support 等），标出高扇出消费点。
- 盘点 `use-practice-websocket.ts` 当前剩余 transport/orchestration 复杂度，并写清哪些职责已在 `message-handlers.ts` / audio hooks 中。
- 先补一个小型 import/contract inventory，避免拆分后页面改成跨域直连实现。

## Inputs

- `web/src/lib/api/client.ts`
- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/websocket/message-handlers.ts`

## Expected Output

- `web/src/lib/api/client.ts`
- `web/src/hooks/use-practice-websocket.ts`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "export const api|normalizeApiErrorPayload|usePracticeWebSocket|MAX_RECONNECT_ATTEMPTS|message-handlers" web/src/lib/api web/src/hooks
