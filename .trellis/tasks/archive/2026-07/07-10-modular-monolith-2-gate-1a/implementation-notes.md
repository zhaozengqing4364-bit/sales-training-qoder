# Implementation Notes

## Deviations

- `.trellis/spec/backend/index.md` 和 `backend/AGENTS.md` 引用的
  `.kiro/steering/backend-principles.md` 在当前仓库不存在；本切片改用仓库级、
  backend/tests/scripts AGENTS 与已加载 Trellis backend specs 作为约束，不创建替代文件。
- 计划示例只在 violation 中记录文件路径；实现增强为 `path:line`，使新增边失败可直接
  定位，不改变 edge/SCC 语义。
- `stable_edges` 是目标允许方向，实际可暂时不存在；当前 policy 中
  `curriculum_practice -> evaluation` 和 `supervisor -> evaluation` 即为此类目标边。
- trellis-implement 子代理按上游指令不 commit；计划中的两个 commit checkbox 留待主
  agent 独立复核后完成。

## Verification Log

- 2026-07-10：Gate 1A 任务创建；CodeGraph 和文件检查确认 architecture guard、policy、
  单测及 CI 接线均不存在，现有局部边界测试不能阻止全局 SCC 扩张。
- 2026-07-10：Red 1：architecture 单测因
  `ModuleNotFoundError: scripts.architecture_dependency_guard` 失败；Green 1：实现 AST
  collector 后 `1 passed`。覆盖 static、`TYPE_CHECKING`、函数内 import、字面量
  `import_module`/`__import__`，非字面量 plugin path 不推断。
- 2026-07-10：Red 2：Tarjan 测试因缺少 `strongly_connected_components` symbol
  失败；Green 2：确定性 Tarjan 实现后 `2 passed`。
- 2026-07-10：Red 3：repository policy 测试因缺少 `validate_repository` symbol
  失败；Green 3：实现 policy 生命周期和实际 YAML 后 `3 passed`，随后增量补齐必填
  字段、无效/过期日期、stale exception、unexpected edge 和 expanded SCC 回归。
- 2026-07-10：实际 scanner 结果为 49 条跨包边；唯一非单节点 SCC 包含
  `admin, agent, common, curriculum_analytics, curriculum_practice, evaluation,
  presentation_coach, prompt_templates, sales_bot, sales_trainer, support,
  training_runtime`，`supervisor` 为单节点。49 条边全部由 stable 或 temporary policy
  解释。
- 2026-07-10：临时 `sales_bot/_architecture_guard_probe.py` 导入 `supervisor` 时，CLI
  exit 1 并同时报告 `Unexpected dependency sales_bot->supervisor` 与 13 包 expanded
  SCC；通过 `apply_patch` 删除 probe 后 CLI exit 0，文件未残留。
- 2026-07-10：
  `backend/.venv/bin/python -m ruff check scripts/architecture_dependency_guard.py
  tests/unit/test_architecture_dependency_guard.py` → `All checks passed`。
- 2026-07-10：architecture guard + runtime/newcomer/knowledge boundary 聚焦集 →
  `31 passed, 1 warning in 14.94s`；未重复运行 Gate 0B 所属全量 unit+contract。
- 2026-07-10：从 `backend/` 与 repo root 分别运行
  `architecture_dependency_guard.py --check` → exit 0，输出
  `dependency policy satisfied`。
- 2026-07-10：`bash -n scripts/critical-quality-gate.sh` 与 `git diff --check` → exit 0。
- 2026-07-10：CodeGraph sync 后，`impact collect_edges` 只扩散到 guard validation 和
  新 architecture tests；`affected` 为
  `backend/tests/unit/test_architecture_dependency_guard.py`。由于 policy 也保护既有局部
  合同，额外人工选择并运行了 runtime/newcomer/knowledge boundary tests。CodeGraph
  对 `validate_repository` 的同名搜索还返回了无关 recovery script，未形成实际依赖。
- 2026-07-10：独立 Trellis check 发现 current-policy 测试硬编码 `49` 条边和历史
  12 包 SCC，会在依赖边或 SCC 合法收缩时制造失败，与“允许缩小”合同冲突。测试现改为
  只由 `validate_repository()` 判断当前政策是否合法，并新增 synthetic 回归证明 baseline
  SCC 的子集可通过、超集会失败；`49/12` 仅作为本次文档和审计事实保留。
- 2026-07-10：独立复核还发现 synthetic temporary-policy 测试使用真实系统日期，
  `2026-10-31` 后会混入非目标 expiry violation。所有 synthetic policy 验证现固定
  `today=2026-07-10`；current repository test 不固定日期，仍按 UTC 当前日期 fail closed。
- 2026-07-10：补充 relative import 忽略、直接/属性字面量 dynamic import、同一现有
  SCC 内 unexpected edge、invalid YAML、重复/重叠 edge、未知包、重复包和缺失包目录测试。
  Gate 0A 计划顶部被误写成 ``Steps use checkbox (`- [x]`)`` 的说明也已恢复为
  未完成态语法示例；Gate 1A 两个 commit checkbox 仍保持未勾选。
- 2026-07-10：独立 policy 盘点为 13 包、49 条实际边；其中 14 条命中 stable、35 条
  命中 temporary，0 条 unexplained、0 条 stale、0 条 stable/temporary overlap；两个
  允许但当前尚未出现的 stable edge 为 `curriculum_practice -> evaluation` 和
  `supervisor -> evaluation`。唯一非单节点 SCC 仍为批准的 12 包 baseline。
- 2026-07-10：独立故障探针 `sales_bot/_architecture_guard_check_probe.py` 导入
  `supervisor` 后 CLI exit 1，同时报告 unexpected edge（含确定性 `path:line`）和 13 包
  expanded SCC；用 `apply_patch` 删除后，从 repo root、`backend/` 两处运行 CLI 均恢复
  `dependency policy satisfied`，探针无残留。
- 2026-07-10：独立 Gate 1A 复核命令结果：changed-file Ruff `All checks passed`；
  architecture + runtime/newcomer/knowledge boundary pytest 为
  `36 passed, 1 warning in 11.75s`；`bash -n scripts/critical-quality-gate.sh`、
  `git diff --check` 均 exit 0。
- 2026-07-10：直接运行
  `.venv/bin/python -m mypy --config-file pyproject.toml scripts/architecture_dependency_guard.py`
  只报告 PyYAML 缺少 `types-PyYAML` stubs（`import-untyped`）。项目标准 mypy 门禁只面向
  `src/`/指定 newcomer targets，本 Gate 明确不新增第三方依赖且计划没有 scripts mypy
  门禁，因此未用 ignore 注释或新增 stub 依赖伪造通过；残余风险是脚本未受 mypy 覆盖，
  由完整类型标注、Ruff 和 19 个 guard 单测承担。
- 2026-07-10：`trellis-update-spec` 新增
  `.trellis/spec/backend/architecture-fitness.md` 并更新 backend spec index，固化 scanner
  签名、policy schema、exception 生命周期、SCC 只许缩小、synthetic 固定日期、故障
  probe 和回归要求；同时把新 spec 加入 implement/check context。
- 2026-07-10：主代理最终聚焦复核：changed-file Ruff 通过；architecture + retained
  boundary tests 为 `36 passed, 1 warning in 11.98s`；repo/backend 两处 CLI、OpenAPI
  parity、Bash 语法、Trellis context 和 `git diff --check` 均通过。再次创建
  `sales_bot/_architecture_guard_probe.py` 得到 unexpected edge 与 13 包 expanded SCC，
  删除后 CLI 恢复绿色且 probe 无残留。
- 2026-07-10：核心实现提交为 `2e04bd77`（guard、policy、单测）和 `0a1010ff`
  （架构文档与 canonical gate 接线）；Gate 状态文档和 Trellis spec/task 作为后续独立
  文档提交，不混入用户 Readiness 改动。
