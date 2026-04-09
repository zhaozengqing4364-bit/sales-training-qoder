---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: 形成依赖扫描与升级策略 baseline

落文档/脚本化流程：定义扫描节奏、升级门禁、license 检查建议和 backend requirements.txt 同步规则。

## Inputs

- `web/package.json`
- `backend/requirements.txt`
- `.github/workflows/nfr-performance-check.yml`

## Expected Output

- `docs/*`
- `scripts/*`

## Verification

npm audit --prefix web

## Observability Impact

dependency governance baseline created
