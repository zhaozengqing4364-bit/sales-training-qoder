---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T01: 盘点现有依赖治理入口

Why: 先盘清仓库里已经有什么依赖治理入口，才能避免再造一套与现状脱节的流程文档。

Do:
1. 梳理 `web/package.json`、`backend/requirements.txt` 与现有 workflow 中可复用的依赖检查入口。
2. 明确 `npm audit`、`pip_audit`、license scan 的最小执行路径。
3. 标记哪些命令依赖额外前置条件。

Done when: 后续 baseline 文档可以直接引用真实入口和前置条件，而不是泛化建议。

## Inputs

- `web/package.json`
- `backend/requirements.txt`
- `.github/workflows/nfr-performance-check.yml`

## Expected Output

- `web/package.json`
- `backend/requirements.txt`
- `.github/workflows/nfr-performance-check.yml`

## Verification

test -f web/package.json && test -f backend/requirements.txt

## Observability Impact

形成当前依赖治理入口与前置条件 inventory。
