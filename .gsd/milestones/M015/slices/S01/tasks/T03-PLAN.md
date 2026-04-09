---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: 清理业务页面与 hooks 中的散落 console

替换高噪声业务页面和 hooks 中的散落 console，补最小 proof，确保保留 instrumentation/dev-only 例外但业务页面不再直出 console。

## Inputs

- `web/src/lib/debug.ts`

## Expected Output

- `web/src/**/*.ts`
- `web/src/**/*.tsx`

## Verification

rg -n "console\.(log|error|warn|info)" web/src

## Observability Impact

none
