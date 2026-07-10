# Gate 1A Architecture Guard Baseline

## Current evidence

- `backend/src` 有 13 个目标顶层业务包：`admin`、`agent`、`common`、
  `curriculum_analytics`、`curriculum_practice`、`evaluation`、`presentation_coach`、
  `prompt_templates`、`sales_bot`、`sales_trainer`、`supervisor`、`support`、
  `training_runtime`。
- 2026-07-10 设计审计记录 49 条跨包边；除 `supervisor` 外，12 个包在同一 SCC。
  Gate 0A 之后没有生产 `backend/src` 变更，因此该结构基线仍适用，但实施必须用新
  scanner 再次验证。
- 当前缺少以下 Gate 1A 产物：
  - `backend/scripts/architecture_dependency_guard.py`
  - `backend/tests/unit/test_architecture_dependency_guard.py`
  - `docs/architecture/module-dependency-policy.yaml`
- `scripts/critical-quality-gate.sh` 已运行局部
  `test_runtime_dependency_contract.py` 和 `test_newcomer_training_path_boundary.py`，但没有
  全局 import graph/SCC guard。
- 当前字面量内部 dynamic import 包含：
  - `sales_trainer/services/curriculum_practice_adapter.py` 到 `curriculum_practice`；
  - 其余多数 `importlib.import_module` 指向第三方依赖；
  - `websocket_routes.py`、`sales_bot/websocket/router.py` 和
    `sales_trainer/services/path_service.py` 使用非字面量 plugin path，应继续由 runtime
    plugin contract 测试保护，不由 AST guard 猜测。

## Root problem

现有测试用手写 allowlist 保护少数已知边界，无法回答：

1. 是否出现了任意新的跨包边；
2. 当前大 SCC 是否扩大；
3. 已删除的历史例外是否仍永久留在政策中；
4. 例外是否有所有者、退役条件和到期日。

因此局部 boundary tests 全绿与 12 包 SCC 同时存在并不矛盾。

## Scanner and policy risks

- AST 必须遍历整个语法树；只扫描文件顶部会漏掉 `TYPE_CHECKING` 和函数内 import。
- `ast.ImportFrom.module` 为 `None` 的相对 import 不应误判成跨顶层包；跨包绝对 import
  按第一个模块段归属。
- dynamic import 只有首参为字符串常量且调用为 `import_module`/`__import__` 时计入；
  变量 plugin path 不做静态猜测。
- violations 和 locations 必须排序，避免文件系统遍历顺序造成 CI 抖动。
- stable edge 是目标允许方向，可以暂时不存在；temporary edge 是历史事实，一旦实际边
  消失就必须报告 stale exception。
- SCC 验证必须允许历史 SCC 拆分；任何当前 component 只有在某个 baseline SCC 的子集
  中才允许，包含 `supervisor` 或其他新节点就失败。
- policy 过期判断使用 UTC 日期语义即可；Gate 内不引入时区或第三方日期库。

## Failure probes

- 在临时 `backend/src/sales_bot/_architecture_guard_probe.py` 中加入
  `import supervisor`，应报告 unexpected dependency，并因 supervisor 加入历史 SCC 而
  报告 expanded SCC。
- 删除 probe 后 CLI 必须恢复 0；probe 不得进入 Git。
- 单测应使用 `tmp_path` 覆盖 static/local/typing/literal dynamic import、SCC、缺字段、
  过期、stale exception 和仓库当前 policy。

## Documentation closure

- Gate 0A 原计划的 checkbox 与已归档任务不一致；应在本 Gate 的首个文档提交中补充
  `Status: Completed`、提交/测试证据，并更新路线图状态矩阵。
- 目标设计继续保持“分 Gate 实施”，但应明确 Gate 0A 完成、Gate 1A 当前实施状态，
  避免 Accepted ADR 被误读为物理迁移完成。
