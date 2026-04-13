---
estimated_steps: 2
estimated_files: 3
skills_used: []
---

# T02: 把 authority inventory 写进 proof 与文档

- 为关键 runtime/read-side tests 补 inventory assertions 或注释，明确它们锁的是哪条 authority path。
- 在 docs/api-contract 或 analysis 中写清 live path 与 compat path 的 consumer list。

## Inputs

- `T01 inventory`
- `existing tests/docs`

## Expected Output

- `backend/tests/*`
- `docs/api-contract/*`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "live|compat|shadow|retire|authority" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md docs/api-contract backend/tests
