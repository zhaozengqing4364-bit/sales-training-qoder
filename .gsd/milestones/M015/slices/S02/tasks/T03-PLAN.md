---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T03: 为非中断式交互模式补 proof

Why: 需要一个长期稳定的 proof，防止以后再次引入原生弹窗和硬跳转。

Do:
1. 回归扫描业务代码中的 `alert/confirm/window.location.assign/href`。
2. 补 focused tests，锁定删除确认和 auth redirect 的非中断式行为。
3. 保持测试关注 shared seam 行为，不把实现细节写死。

Done when: grep gate 和 focused tests 同时通过，且剩余例外可被解释。

## Inputs

- `web/src/**/*.test.tsx`

## Expected Output

- `web/src/**/*.test.tsx`

## Verification

rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src && npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"

## Observability Impact

未来引入原生弹窗/硬跳转会被 grep + focused tests 同时拦住。
