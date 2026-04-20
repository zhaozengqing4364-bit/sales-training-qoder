---
estimated_steps: 5
estimated_files: 1
skills_used: []
---

# T04: 企业微信按钮处理

将企业微信登录按钮改为 disabled 状态并添加提示，或完全移除。确保视觉上明确标识为不可用。

Steps:
1. 将企业微信按钮改为 disabled
2. 添加 title='即将支持，敬请期待' 提示
3. 视觉上降低对比度表示不可用

## Inputs

- `web/src/app/(auth)/login/page.tsx`

## Expected Output

- `web/src/app/(auth)/login/page.tsx`

## Verification

npm --prefix web test -- --run login

## Observability Impact

none
