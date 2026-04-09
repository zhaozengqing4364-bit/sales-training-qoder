---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T02: 忘记密码前端流程

前端：在登录页添加'忘记密码？'链接，新建 forgot-password 和 reset-password 页面，表单校验完整。

Steps:
1. 登录页 email+password 表单下方添加'忘记密码？'链接
2. 新建 forgot-password 页面：email 输入 → 调用 API → 成功提示
3. 新建 reset-password 页面：token + 新密码 + 确认密码 → 调用 API → 跳转登录
4. 在 api client 添加对应方法
5. 表单校验：密码最小长度 8 位、两次输入一致

## Inputs

- `web/src/app/(auth)/login/page.tsx`
- `web/src/lib/api/client.ts`

## Expected Output

- `web/src/app/(auth)/login/page.tsx`
- `web/src/app/(auth)/forgot-password/page.tsx`
- `web/src/app/(auth)/reset-password/page.tsx`

## Verification

npm --prefix web test -- --run login

## Observability Impact

none
