# Implementation Notes

## Deviations

- Trellis 子代理运行 `task.py current --source` 返回 `Current task: (none)`；这是任务指针
  隔离的已知平台限制。按主代理确认，以显式任务目录
  `.trellis/tasks/07-10-modular-monolith-2-gate-0a` 为权威继续，没有扩大范围。
- 计划假设 FastAPI WebSocket `_EffectiveRouteContext.path` 包含有效路径；当前框架实际
  返回空字符串，路径只存在于 `original_route.path`。测试层 Adapter 因而对 HTTP 继续
  读取 effective context，对 WebSocket 从 `original_route` 读取路径；没有修改生产路由。
- 计划包含逐变更包 commit，但主代理明确要求共享工作区不 commit、不 push；本实现只
  留下工作区变更，交由主代理统一复核和提交。
- `.trellis/spec/backend/index.md` 引用的 `.kiro/steering/backend-principles.md` 在当前仓库
  不存在；已读取并遵循现存的 `backend/AGENTS.md`、子目录 AGENTS、API contract 与全部
  `implement.jsonl` 规范，没有自行创建缺失规范。

## Verification Log

- 2026-07-10：开发前基线已记录于 `research/platform-contract-root-causes.md`。
- 2026-07-10：Realtime Red：reconnect 因 fake token 关闭 4401，transcript capture 因后台
  task 尚未调度读取空列表；同一聚焦命令为 `2 failed`。注入合法身份 payload 并用
  `asyncio.Event` 建立 happens-before 后为 `2 passed`。
- 2026-07-10：Contributor Red：顺序运行
  `test_sales_trainer_phase2_contract.py` → `test_sessions.py` 复现
  `[RUNTIME_POLICY_RESOLVER_NOT_REGISTERED]`。改为 production bootstrap 的 autouse 恢复后，
  bootstrap + 两个 contract 文件为 `31 passed`。
- 2026-07-10：Route Red：route integrity + app factory 聚焦集为 `6 failed, 2 passed`；加入
  测试局部 effective-route Adapter 后，结构型合同为 `7 passed`。OpenAPI 漂移留到生成
  合同切片处理。
- 2026-07-10：OpenAPI generator Red：生成器单测以
  `ModuleNotFoundError: scripts.generate_openapi_contract` 失败；最小实现后为 `2 passed`。
  committed/runtime 均为 491 paths，runtime-only=0、committed-only=0，`--check` 返回 0。
- 2026-07-10：Gate 0A 无服务聚焦总回归：`53 passed, 1 warning`。
- 2026-07-10：聚焦 Ruff：`All checks passed!`；
  `bash -n scripts/critical-quality-gate.sh` 返回 0；`git diff --check` 返回 0。
- 2026-07-10：全量 `tests/unit tests/contract -q --no-cov`：
  `2579 passed, 15 failed, 1 skipped, 74 warnings`（359.14s）。Gate 0A 的 route、app-factory、
  contributor、OpenAPI、reconnect、transcript capture 失败簇均为 0；剩余 15 项均属于已
  登记 Gate 0B：audio/record lineage、Sales Trainer projection/permission/service fixtures、
  secret hygiene evidence、PPT forbidden-word serialization。
- 2026-07-10：未运行完整 `critical-quality-gate.sh`，因为它还包含已登记 Gate 0B/0C 的
  Web/Vitest/全栈服务门禁；本切片已验证新增目标、OpenAPI check、Ruff 与 Bash 语法。
- 2026-07-10：独立 `trellis-check` 未发现实现层阻塞 finding；删除 context JSONL 中遗留的
  `_example` 模板行后，context 校验为 implement 8/check 7。Spec 更新后加入新合同，最终为
  implement 9/check 8，`task.py validate` 通过。
- 2026-07-10：最终主代理复核：Gate 0A 聚焦集 `53 passed, 1 warning`；changed-file Ruff、
  OpenAPI `--check`、Bash 语法、`git diff --check` 全部通过。两次独立生成与 committed
  OpenAPI 的 SHA256 均为 `a2eecd64a0e23e03fd1c20e5c45e8bf1a5188654d817f151019dfe2b30b11015`。
- 2026-07-10：`trellis-update-spec` 判断存在可复用的跨层合同，新增
  `.trellis/spec/backend/platform-contract-truth.md`，并更新 backend spec index。合同覆盖
  production contributor bootstrap、effective route context、runtime-generated OpenAPI 与
  release gate 的签名、错误矩阵、用例和测试要求。

## Residual Risks

- 仓库现有 critical mypy 子集仍在未改动的
  `training_journey_service.py:2794-2795` 存在 2 个 `no-any-return`；不是本切片引入。
- 单独 mypy 检查新生成脚本会受仓库未安装 `types-PyYAML` 及 follow-import 类型信息影响；
  该脚本不在当前 mypy scope，运行时、Ruff 和聚焦测试均已通过。
- 全量 unit+contract 仍有 15 个 Gate 0B 失败；完整 Web/服务型 critical gate 未运行。
