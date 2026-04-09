---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 盘点现有依赖治理入口

梳理当前 web/package.json、backend/requirements.txt 与现有 workflow 中可复用的依赖检查入口，明确 npm audit / pip audit / license scan 的最小流程。

## Inputs

- `web/package.json`
- `backend/requirements.txt`
- `.github/workflows/nfr-performance-check.yml`

## Expected Output

- `dependency governance notes`

## Verification

test -f web/package.json && test -f backend/requirements.txt

## Observability Impact

dependency scan entrypoints inventory
