---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T02: 收口 confirm/dialog/router/auth-handler 交互模式

替换删除确认与业务跳转：删除操作统一走 modal confirm，auth redirect 统一走 authHandler/router，业务导航改成 router push/replace。保留 ErrorBoundary reload 例外。

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

交互确认与 auth redirect 行为统一
