# S02: 依赖安全、许可证与更新策略基线

**Goal:** 把依赖安全、许可证、更新策略从口头建议变成明确维护流程。
**Demo:** 仓库里有可执行的依赖扫描与升级策略文档/流程。

## Must-Haves

- web/backend 的依赖扫描入口和升级门禁被写成可执行 baseline。
- `npm audit`、`pip_audit` 和 license scan 的前置条件/执行方式清楚记录。
- backend `requirements.txt` 与依赖治理规则的同步要求被明确写进基线。

## Proof Level

- This slice proves: operational

## Integration Closure

S02 把仓库级依赖治理入口、扫描节奏和同步规则落成基线，为后续治理里程碑提供一个无需重新摸索的操作起点。

## Verification

- future agents 可直接从文档/脚本和扫描命令判断当前依赖治理状态，知道哪些 proof 已执行、哪些还需要前置条件。

## Tasks

- [x] **T01: 盘点现有依赖治理入口** `est:25m`
  Why: 先盘清仓库里已经有什么依赖治理入口，才能避免再造一套与现状脱节的流程文档。

Do:
1. 梳理 `web/package.json`、`backend/requirements.txt` 与现有 workflow 中可复用的依赖检查入口。
2. 明确 `npm audit`、`pip_audit`、license scan 的最小执行路径。
3. 标记哪些命令依赖额外前置条件。

Done when: 后续 baseline 文档可以直接引用真实入口和前置条件，而不是泛化建议。
  - Files: `web/package.json`, `backend/requirements.txt`, `.github/workflows/nfr-performance-check.yml`
  - Verify: test -f web/package.json && test -f backend/requirements.txt

- [x] **T02: 形成依赖扫描与升级策略 baseline** `est:35m`
  Why: 只有把扫描节奏、升级门禁和 requirements 同步规则写成 baseline，依赖治理才不再只是口头建议。

Do:
1. 落文档或脚本化流程，定义扫描节奏、升级门禁和 license 检查建议。
2. 明确 backend `requirements.txt` 与依赖源文件的同步规则。
3. 保持流程基于当前真实工具，不引入未接入的外部平台假设。

Done when: 仓库里存在一份可执行的依赖扫描与升级策略 baseline。
  - Files: `docs/*`, `scripts/*`
  - Verify: npm audit --prefix web

- [x] **T03: 补依赖治理 proof 与执行前置说明** `est:20m`
  Why: 依赖治理 proof 必须诚实区分“已经执行过”和“需要前置条件”，否则文档会制造虚假的已验证感。

Do:
1. 在环境具备时跑最小依赖检查 proof。
2. 若环境不具备，明确 `pip_audit` 或 license scan 的前置条件与执行方式。
3. 记录执行前置说明，避免后续 agent 把缺环境误判成产品回归。

Done when: 依赖治理 baseline 既有可执行命令，也有清晰的前置条件说明。
  - Files: `docs/*`
  - Verify: backend/venv/bin/python -m pip_audit

## Files Likely Touched

- web/package.json
- backend/requirements.txt
- .github/workflows/nfr-performance-check.yml
- docs/*
- scripts/*
