---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T01: 盘点现有 forgot/reset、profile 修改密码与语速偏好现状

Why: 先把 forgot/reset、profile 修改密码入口与语速偏好的当前真实表面盘清，避免把已存在能力和过渡实现混为一谈。

Do:
1. 梳理前端 auth 路由、profile 页面和 backend auth API/service 的现状。
2. 标出 forgot/reset 哪些已是正式能力、哪些仍是过渡实现。
3. 定位 profile 中修改密码入口和语速偏好的真实存储/恢复路径。
4. 记录仍在用 `window.location` 或静默容错的点。

Done when: 后续两项任务可以直接按现状差距动手，不需要再次做 auth/profile 范围摸底。

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

形成 auth/profile 当前真实表面清单。
