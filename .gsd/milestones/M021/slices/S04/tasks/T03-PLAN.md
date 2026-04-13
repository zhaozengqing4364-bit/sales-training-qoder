---
estimated_steps: 2
estimated_files: 4
skills_used: []
---

# T03: 把 quality/cost/failure event 读法写回 support 与前端 proof

- 更新 support/runtime、report/replay docs、architecture scan，明确如何读这些事件以及如何区分 degraded / failure / compat。
- 前端如已展示对应降级状态，补 focused assertions，确保不是继续把失败翻译成‘低质量成功’。

## Inputs

- `T02 events`
- `current degraded UI surfaces`

## Expected Output

- `docs/api-contract/support-runtime.md`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" && rg -n "quality|cost|failure|degraded|compat" docs/api-contract/support-runtime.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
