---
estimated_steps: 3
estimated_files: 7
skills_used: []
---

# T01: 盘点 release truth line 的真实接通状态

- 盘点现有 `.github/workflows`、frontend ErrorBoundary 上报路径、backend metrics helpers、api-spec/openapi/docs-api-contract 之间的真实接通情况。
- 明确哪些是“文件存在但未接通”，哪些已有 live route 或 check。
- 形成 assembled release truth inventory，作为 workflow 设计输入。

## Inputs

- `current workflow`
- `ErrorBoundary`
- `metrics helpers`
- `api/spec docs`

## Expected Output

- `.github/workflows/*.yml`
- `web/src/components/ErrorBoundary.tsx`
- `backend/src/common/monitoring/metrics.py`
- `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`

## Verification

rg -n "analytics/error|metrics|openapi|api-contract|pip install -e|requirements.txt|package-lock" .github/workflows web/src/components/ErrorBoundary.tsx backend/src/common/monitoring/metrics.py api-spec.md specs/001-ai-practice-system/contracts/openapi.yaml docs/api-contract
