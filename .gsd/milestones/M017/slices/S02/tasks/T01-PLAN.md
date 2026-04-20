---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 识别 websocket hook 的真实职责边界

Why: 先识别 websocket hook 真实职责边界，才能避免“文件大就拆”的假重构。

Do:
1. 盘点 `use-practice-websocket` 当前承载的 reconnect/backpressure/interrupt/binary negotiation 事实。
2. 标出真正需要收口的 seam。
3. 区分复杂度问题与只是职责集中但仍合理的部分。

Done when: 已明确 hook 的真实职责边界，后续实现不会为了拆分而拆分。

## Inputs

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`

## Expected Output

- `web/src/hooks/use-practice-websocket.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`

## Verification

rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts

## Observability Impact

形成 websocket hook 真实职责边界图。
