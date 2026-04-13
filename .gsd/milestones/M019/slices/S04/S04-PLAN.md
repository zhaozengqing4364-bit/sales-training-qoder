# S04: Release gate / metrics / doc-contract truth line 收口

**Goal:** 让 CI、metrics、frontend error reporting、spec/doc contract 与当前仓库 authority 对齐，形成可复用 release gate。
**Demo:** After this: GitHub Actions、metrics、前端错误上报和 docs/spec contract 至少有一条真实、可检查的 release truth line，而不是只存在零散文件。

## Must-Haves

- workflow 使用与仓库真实一致的依赖安装与 focused verification 命令。
- `/metrics` 或明确替代观测 surface 有可执行检查，frontend error reporting 的 backend 对口路由或显式缺失信号被收口。
- api-spec/openapi/docs-api-contract 与 live route 的漂移有 check 或 inventory，不再全靠人工记忆。

## Proof Level

- This slice proves: final-assembly

## Integration Closure

S04 是 M019 的最终 assembled slice；完成后 M020-M022 可以直接复用 release truth line，而不用再先证明 workflow/metrics/error/doc 是否真的接通。

## Verification

- release 是否可过线不再只看单个 workflow 绿灯，而是看 web/backend/doc/metrics/error-reporting 的 assembled proof。

## Tasks

- [x] **T01: 盘点 release truth line 的真实接通状态** `est:45m`
  - 盘点现有 `.github/workflows`、frontend ErrorBoundary 上报路径、backend metrics helpers、api-spec/openapi/docs-api-contract 之间的真实接通情况。
- 明确哪些是“文件存在但未接通”，哪些已有 live route 或 check。
- 形成 assembled release truth inventory，作为 workflow 设计输入。
  - Files: `.github/workflows`, `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `web/src/components/ErrorBoundary.tsx`, `backend/src/common/monitoring/metrics.py`, `api-spec.md`, `specs/001-ai-practice-system/contracts/openapi.yaml`, `docs/api-contract`
  - Verify: rg -n "analytics/error|metrics|openapi|api-contract|pip install -e|requirements.txt|package-lock" .github/workflows web/src/components/ErrorBoundary.tsx backend/src/common/monitoring/metrics.py api-spec.md specs/001-ai-practice-system/contracts/openapi.yaml docs/api-contract

- [x] **T02: 把 workflow 与观测出口对齐到真实 authority** `est:2h`
  - 新增或拆分 GitHub Actions，让 web/backend focused gates、依赖安装 authority、docs/spec drift check 与 release baseline 一致。
- 为 frontend error reporting 和 metrics surface 做明确收口：要么补对口 route/check，要么让缺失成为显式失败信号而非静默假接通。
- 保持所有验证命令都能从 repo root 直接运行。
  - Files: `.github/workflows`, `backend/src/main.py`, `backend/src/common/api`, `web/src/components/ErrorBoundary.tsx`, `scripts`
  - Verify: rg -n "npm --prefix web|backend/venv/bin/python -m pytest|requirements.txt|package-lock|metrics|analytics/error" .github/workflows && npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" && backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q

- [ ] **T03: 固定 assembled release gate 与 downstream 复用规则** `est:40m`
  - 把 assembled release gate 写入 architecture scan / plan，明确 downstream milestones 默认复用哪些 commands 和 live surfaces。
- 补 doc/spec drift check 或 inventory proof，让后续 agent 能判断 api-spec/openapi/docs-api-contract 是否与 live routes 一致。
- 如 admin 首页仍有 demo stats/假监控数字，至少把其 truthfulness gap 记录为 M022 输入，不让它继续伪装成 release surface。
  - Files: `.gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md`, `.gsd/plans/GSD_PLAN_post-M018-next-wave.md`, `docs/api-contract`, `api-spec.md`
  - Verify: rg -n "release gate|metrics|error reporting|doc contract|repo-root" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md

## Files Likely Touched

- .github/workflows
- .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
- web/src/components/ErrorBoundary.tsx
- backend/src/common/monitoring/metrics.py
- api-spec.md
- specs/001-ai-practice-system/contracts/openapi.yaml
- docs/api-contract
- backend/src/main.py
- backend/src/common/api
- scripts
- .gsd/plans/GSD_PLAN_post-M018-next-wave.md
