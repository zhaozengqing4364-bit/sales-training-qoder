---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 定位 password reset 正式化的最窄接入点

盘点当前 forgot/reset 路径中的 runtime DDL、token 生命周期、email 发送与 rate limit 现状，确认正式模型和 migration 的最窄接入点。

## Inputs

- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`
- `backend/src/common/db/models.py`

## Expected Output

- `auth seam inventory`

## Verification

rg -n "CREATE TABLE IF NOT EXISTS|reset|forgot|token|email" backend/src/common/auth backend/src/common/db/models.py

## Observability Impact

current auth recovery seam inventory
