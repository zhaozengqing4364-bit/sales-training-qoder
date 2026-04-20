---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T03: 补依赖治理 proof 与执行前置说明

Why: 依赖治理 proof 必须诚实区分“已经执行过”和“需要前置条件”，否则文档会制造虚假的已验证感。

Do:
1. 在环境具备时跑最小依赖检查 proof。
2. 若环境不具备，明确 `pip_audit` 或 license scan 的前置条件与执行方式。
3. 记录执行前置说明，避免后续 agent 把缺环境误判成产品回归。

Done when: 依赖治理 baseline 既有可执行命令，也有清晰的前置条件说明。

## Inputs

- `docs/*`
- `backend/requirements.txt`

## Expected Output

- `docs/*`

## Verification

backend/venv/bin/python -m pip_audit

## Observability Impact

依赖治理是否已执行/为什么未执行可被后续 agent 直接理解。
