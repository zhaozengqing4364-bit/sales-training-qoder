---
estimated_steps: 2
estimated_files: 3
skills_used: []
---

# T03: 把 prompt authority 写回文档与管理面说明

- 更新 prompt docs、architecture scan 与 admin-facing guidance，说明哪个 surface 改模板会影响哪些 live path。
- 为后续 S03 canonical evaluation kernel 标明 compiled prompt 的 authority entry。

## Inputs

- `T02 outputs`
- `prompt admin surfaces`

## Expected Output

- `docs/api-contract/*`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "compiled prompt|template source|guardrail|missing var|base_url" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/prompt_templates
