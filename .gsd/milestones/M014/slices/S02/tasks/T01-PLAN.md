---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: 盘点现有 forgot/reset、profile 修改密码与语速偏好现状

梳理现有 forgot/reset 前后端路径、profile 修改密码入口和语速偏好存储现状，确认哪些是过渡实现，哪些可以沿用。

## Inputs

- `web/src/app/(auth)/*`
- `web/src/app/(dashboard)/profile/page.tsx`
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`

## Expected Output

- `web/src/app/(auth)/*`
- `web/src/app/(dashboard)/profile/page.tsx`
- `backend/src/common/auth/api.py`
- `backend/src/common/auth/service.py`

## Verification

rg -n "forgot|reset|password|speech|rate|window.location" web/src/app/\(auth\) web/src/app/\(dashboard\)/profile backend/src/common/auth

## Observability Impact

current auth/profile seam inventory
