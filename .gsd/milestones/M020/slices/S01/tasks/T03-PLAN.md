---
estimated_steps: 2
estimated_files: 4
skills_used: []
---

# T03: 把 auth authority 写回 contract 与 runbook

- 更新 auth-local/setup/runbook/docs-api-contract，明确正式 transport、兼容 transport、关闭条件和 repo-root 验证命令。
- 确认前端对 session expired / unauthorized 的处理仍走统一 `authHandler`。

## Inputs

- `T02 结果`
- `web auth handling`

## Expected Output

- `docs/setup/auth-local.md`
- `docs/api-contract/websocket.md`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "Authorization|query token|cookie|CSRF|shared password|session expired" docs/setup/auth-local.md docs/api-contract/websocket.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/lib/auth-handler.ts
