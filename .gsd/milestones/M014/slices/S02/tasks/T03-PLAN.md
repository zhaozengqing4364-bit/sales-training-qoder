---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: 闭合 profile 修改密码与语速偏好体验

收口前端 auth/profile 体验：profile 内改为正式修改密码路径，去掉 window.location 跳转；语速偏好接到真实存储或明确隐藏/移除；补 focused tests。

## Inputs

- `web/src/app/(auth)/*`
- `web/src/app/(dashboard)/profile/page.tsx`
- `backend/src/common/auth/api.py`

## Expected Output

- `web/src/app/(auth)/*`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(auth)/login/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx"

## Observability Impact

profile settings 保存/失败状态可见
