---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: 为非中断式交互模式补 proof

回归扫描业务代码，确保 alert/confirm/window.location.assign/href 从业务页面消失，并用 focused tests 锁定删除确认和 auth redirect 行为。

## Inputs

- `web/src/app/admin/personas/[id]/page.test.tsx`
- `web/src/app/(auth)/login/page.test.tsx`

## Expected Output

- `web/src/**/*.test.tsx`

## Verification

rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src && npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"

## Observability Impact

none
