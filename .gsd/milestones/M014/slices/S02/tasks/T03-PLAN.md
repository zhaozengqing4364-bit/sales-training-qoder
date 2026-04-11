---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T03: 闭合 profile 修改密码与语速偏好体验

Why: profile 修改密码与语速偏好必须落到真实可持续的前端体验，否则 S02 只会留下“后端更正式，但用户还在走假入口”。

Do:
1. 把 profile 中的修改密码动作接到正式路径，移除生硬的 `window.location` 跳转。
2. 把语速偏好接到真实存储/恢复路径；若某项设置无法真实落地，则隐藏或删除。
3. 补 focused tests，覆盖 login/profile 关键路径和偏好保留行为。
4. 保持 learner 文案诚实，不虚构未实现的账号设置能力。

Done when: profile 密码入口与语速偏好形成真实闭环，focused web proof 通过。

## Inputs

- `web/src/app/(auth)/*`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(auth)/login/page.test.tsx`

## Expected Output

- `web/src/app/(auth)/*`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(auth)/login/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx"

## Observability Impact

profile 真实账号维护入口与语速偏好持久化行为可通过 focused UI tests 复查。
