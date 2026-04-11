---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: 清理业务页面与 hooks 中的散落 console

Why: 只有把高噪声业务页面和 hooks 的散落 console 清掉，S01 才算真正收口，而不是只增加了一个 helper。

Do:
1. 按 T01 的分类结果替换高噪声业务页面和 hooks 中的散落 console。
2. 对允许保留的 instrumentation/dev-only 例外保持最小范围，不扩大例外面。
3. 补 focused proof，锁定“业务页面不再直出 console，但 instrumentation 例外仍允许存在”的边界。

Done when: `rg` 扫描不再在业务页面看到高噪声 console，focused tests 通过，剩余例外都能解释其存在。

## Inputs

- `web/src/**/*.ts`
- `web/src/**/*.tsx`

## Expected Output

- `web/src/**/*.ts`
- `web/src/**/*.tsx`

## Verification

rg -n "console\.(log|error|warn|info)" web/src

## Observability Impact

console 剩余使用点从“散落噪声”变成“可解释例外”。
