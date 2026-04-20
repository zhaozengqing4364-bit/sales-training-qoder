---
estimated_steps: 3
estimated_files: 3
skills_used: []
---

# T03: 固定前端拆分后的 contract proof

- 更新 shared types / imports / architecture scan，让后续 slices 直接知道该改哪个 domain module、哪个 transport helper、哪个 inbound handler。
- 对 reconnect/backpressure/interrupt 的 focused tests 补齐或重定位，确保拆分没有把 contract 流失到 page-level hacks。
- 记录仍故意保留在 outward hook 中的职责，避免后续继续无依据地拆。

## Inputs

- `T02 结果`
- `current practice/report/replay pages`

## Expected Output

- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/lib/api`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"
