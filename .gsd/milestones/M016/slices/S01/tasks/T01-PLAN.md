---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 定位 password reset 正式化的最窄接入点

Why: 先定位当前 forgot/reset 正式化的最窄接入点，避免在 auth seam 上做不必要的扩散式重构。

Do:
1. 盘点 forgot/reset 路径中的 runtime DDL、token 生命周期、email 发送与 rate limit 现状。
2. 找出正式模型、migration 和 email seam 的最小落点。
3. 明确现有登录兼容路径必须保持不变的部分。

Done when: 后续正式化改动有明确接入点，不需要边做边重新判断 auth seam。

## Inputs

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`

## Expected Output

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`

## Verification

rg -n "CREATE TABLE IF NOT EXISTS|reset|forgot|token|email" backend/src/common/auth backend/src/common/db/models.py

## Observability Impact

形成 password reset 正式化接入点和过渡实现清单。
