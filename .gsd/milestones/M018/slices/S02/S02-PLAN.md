# S02: 依赖安全、许可证与更新策略基线

**Goal:** 把依赖安全、许可证、更新策略从口头建议变成明确维护流程
**Demo:** After this: 仓库里有可执行的依赖扫描与升级策略文档/流程

## Tasks
- [ ] **T01: 盘点现有依赖治理入口** — 梳理当前 web/package.json、backend/requirements.txt 与现有 workflow 中可复用的依赖检查入口，明确 npm audit / pip audit / license scan 的最小流程。
  - Estimate: 25m
  - Files: web/package.json, backend/requirements.txt, .github/workflows/nfr-performance-check.yml
  - Verify: test -f web/package.json && test -f backend/requirements.txt
- [ ] **T02: 形成依赖扫描与升级策略 baseline** — 落文档/脚本化流程：定义扫描节奏、升级门禁、license 检查建议和 backend requirements.txt 同步规则。
  - Estimate: 35m
  - Files: docs/*, scripts/*
  - Verify: npm audit --prefix web
- [ ] **T03: 补依赖治理 proof 与执行前置说明** — 如果环境具备，跑最小依赖检查 proof；若不具备，则明确 pip_audit 的前置条件与执行方式，避免伪装已验证。
  - Estimate: 20m
  - Files: docs/*
  - Verify: backend/venv/bin/python -m pip_audit
