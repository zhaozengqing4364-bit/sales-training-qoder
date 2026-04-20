---
estimated_steps: 7
estimated_files: 6
skills_used: []
---

# T02: 收口 confirm/dialog/router/auth-handler 交互模式

Why: 真正的收口点在于把删除确认、auth redirect 和业务导航都接到统一模式，而不是只删掉 API 调用字面量。

Do:
1. 删除操作统一走 modal/dialog confirm。
2. auth redirect 统一走 authHandler/router。
3. 普通业务导航改成 router push/replace。
4. 保留 ErrorBoundary reload 等明确允许的例外，不做过度清理。

Done when: 高风险业务页面不再依赖原生弹窗或硬跳转，focused UI proof 通过。

## Inputs

- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/components/layout/*`
- `web/src/lib/auth-handler.ts`

## Expected Output

- `web/src/app/admin/records/page.tsx`
- `web/src/app/admin/rag-profiles/page.tsx`
- `web/src/app/admin/personas/[id]/page.tsx`
- `web/src/app/(dashboard)/profile/page.tsx`
- `web/src/components/layout/*`
- `web/src/lib/auth-handler.ts`

## Verification

npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"

## Observability Impact

删除确认与 auth redirect 经统一 seam 执行，页面状态更可追踪。
