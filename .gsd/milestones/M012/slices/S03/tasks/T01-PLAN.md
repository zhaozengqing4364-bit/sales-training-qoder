---
estimated_steps: 24
estimated_files: 4
skills_used:
  - safe-grow
  - react-best-practices
  - vitest
  - verification-before-completion
---

# T01: 让 learner 壳层个人中心入口和密码动作都落到真实路由

Skills: safe-grow, react-best-practices, vitest, verification-before-completion

把 `/profile` 的可达性收口在现有 learner shell authority seam，而不是额外发明新导航。`web/src/components/layout/sidebar.tsx` 里的用户弹窗目前把“编辑资料”渲染成了无动作按钮；这个任务要把它变成真实的 `/profile` 导航，同时保持 `历史记录` 继续留在 `SidebarContent` 里，不回归 S02 已关闭的问题。`web/src/app/(dashboard)/profile/page.tsx` 里的密码动作则要保持复用 S01 的 forgot/reset 流程：用 truthful copy（例如“通过邮箱重置密码”）和 Next 路由跳转替换 `window.location.href`，但不要新增 authenticated password API。

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `next/link` / `next/navigation` routing | 保持按钮退化成明确可见的 link/button affordance，不能回到静默 dead button。 | 同 error：优先保留明确目标路由。 | 仅导航到受控的 `/profile` 与 `/forgot-password`，绝不拼接不可信 query。 |
| `api.user.getMe()` / 现有 profile 加载流 | 保持当前 loading/error fallback，不因路由改造新增白屏。 | 维持现有 skeleton / 错误文案。 | 缺失用户字段时继续回退到既有 display-name / email fallback。 |

## Load Profile

- **Shared resources**: learner shell render tree 与现有 profile 数据请求；不新增 backend/shared infra。
- **Per-operation cost**: 一次本地路由跳转 + 既有 profile 页面加载，成本与当前页面一致。
- **10x breakpoint**: 首先暴露的问题会是 dead CTA 或错误目标路由，而不是资源耗尽。

## Negative Tests

- **Malformed inputs**: 缺失 `currentUser`、缺失 display name / email 时，sidebar 用户入口与 profile 页面仍保持可达与安全 fallback。
- **Error paths**: profile 页面数据加载失败时仍显示现有错误态，不因为密码 CTA 改造而阻塞页面。
- **Boundary conditions**: expanded / collapsed learner user affordance 都能到 `/profile`；密码 CTA 始终指向 `/forgot-password` 而不是浏览器硬跳转字符串拼接。

## Steps

1. 把 `sidebar.tsx` 里的用户弹窗“编辑资料”改成真实 `/profile` 导航，并补齐 focused tests，确认 `历史记录` 入口仍在共享 nav seam。
2. 在 `profile/page.tsx` 内把密码动作改成 truthful copy + Next 路由导航到 `/forgot-password`，避免 `window.location.href`。
3. 新增/扩展 profile focused Vitest，锁定 learner shell `/profile` 入口与密码 CTA 的真实 route handoff。

## Must-Haves

- [ ] learner shell 用户弹窗不再存在无动作的“编辑资料”按钮。
- [ ] `SidebarContent` 中的 `历史记录` 入口保持不变。
- [ ] profile 页密码 CTA 明确说明通过既有 forgot/reset 流程修改密码。
- [ ] focused tests 直接断言 `/profile` 与 `/forgot-password` 的目标路由。

## Inputs

- `web/src/components/layout/sidebar.tsx`
- `web/src/components/layout/sidebar.test.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/lib/query/auth.ts`

## Expected Output

- `web/src/components/layout/sidebar.tsx`
- `web/src/components/layout/sidebar.test.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/app/(dashboard)/profile/page.test.tsx`

## Verification

npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/app/(dashboard)/profile/page.test.tsx"

## Observability Impact

- Signals added/changed: learner shell 账户 affordance 与 profile 密码 CTA 都暴露明确目标路由。
- How a future agent inspects this: 运行 `sidebar.test.tsx` 与 `profile/page.test.tsx`，检查 `/profile`、`/forgot-password` href / router push 断言。
- Failure state exposed: dead button、错误目标路由、或 `历史记录` nav 回归会被 focused tests 直接指出。
