---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: 锁定 learner shell baseline proof 与剩余风险

记录 remaining responsive/a11y/timezone 风险的 disposition，并补 focused proof，确保 baseline 闭合但不扩 scope。

## Inputs

- `web/src/app`
- `web/src/components`

## Expected Output

- `slice notes`
- `web/src/app/**/*.test.tsx`

## Verification

find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"

## Observability Impact

remaining risks documented
