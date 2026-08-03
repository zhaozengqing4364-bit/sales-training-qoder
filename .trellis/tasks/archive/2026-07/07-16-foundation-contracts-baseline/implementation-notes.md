# 切片 0 实施记录

## 范围

本切片只冻结合同和文档：未修改业务源码、数据库表、Alembic、运行路由、OpenAPI artifact、Worker、Provider 或 Architecture Guard 实现。

## 代码事实

- `sales_trainer/orchestration/contracts.py` 当前仍是 Phase -> Module -> Activity，并包含 `realtime_roleplay`。
- `EnrollmentRepository.get_or_create()` 会改写旧 revision，`sync_active_path_revision()` 与发布服务会批量移动 active Enrollment。
- `AudioSubmissionService.save_uploaded_file()` 整体读入文件，`create_submission(auto_process=True)` 在请求链路调用转写/评分。
- `common/jobs/persistent_task_contract.py` 明确只有状态合同，没有数据库或 scheduler 实现。
- 当前 question/audio/ASR 等链路仍存在直接 LLM/Provider 构造或调用。

这些是 CodeGraph/源码确认的 Legacy 迁移起点，不被描述成目标能力。

## 已冻结决策

- 首发终点为 `foundation_ready`，不代表真实岗位胜任；Realtime 延期。
- 路径为 PathRevision -> Stage -> ActivityDefinition；五类活动中 Assignment 专指三段异步客户场景录音。
- Cohort/Enrollment 默认冻结已发布 revision；迁移必须显式预览、确认、并发控制、审计和事件。
- AI 只产生初评/证据/建议；正式 Gate 确定性，最终结论人工；无固定 60/70 分。
- PostgreSQL Task/Outbox 为长任务事实权威；Redis/进程队列只加速。
- 模块唯一写权威、11 个状态机、7 个公开事件、权限矩阵、v2 API/ViewModel、迁移矩阵、Guard 设计和测试/SLO 已形成文档合同。

## 偏差与保守处理

- 目标模块尚不存在，因此未把新包写入当前运行时 `module-dependency-policy.yaml`；另建 `newcomer-foundation-guard-policy.yaml`，标明 `design_only_not_enforced`，由 Slice 8 接入并添加失败探针。
- 当前 `sales-trainer.md` 和 2026-07-12/13 ADR 仍用于解释在途 Legacy 行为，已显式标记 Legacy/Superseded，没有伪装成目标权威。
- 生产历史数据迁移不在父任务范围；开发数据使用既有受保护 launch reset。后续计划 artifact 在迁移清单中有明确 Owner/切片/验证/删除时点。
- 工作区包含大量既有改动；本切片未 reset、checkout、commit，也未覆盖无关源码。

## 验证

- `python3 .trellis/scripts/task.py validate <task-dir>`：父任务、Slice 0、Slice 1～8 共 10 个任务全部通过。
- Python 逐行解析上述任务的 `implement.jsonl`/`check.jsonl`：全部为合法 JSONL；10/10 个任务的 `implement.jsonl` 都引用 `docs/newcomer-foundation-contract-index.md`。
- `yaml.safe_load()`：`docs/architecture/newcomer-foundation-guard-policy.yaml` 与现行 `docs/architecture/module-dependency-policy.yaml` 均可解析。
- 自定义 Markdown 相对链接检查：本切片 38 个新建/修改文档、84 个本地链接全部通过，无缺失目标。全库宽扫描另发现 2 个与本切片无关的历史链接缺失（`docs/architecture/config-asset-center.md` 指向带行号的源码字符串、`docs/agents/audit-2026-06/05-database-and-persistence.md` 指向不存在的同目录 `AGENTS.md`）；按最小范围约束仅记录，不修复。
- `python3 backend/scripts/architecture_dependency_guard.py --check`：通过，输出 `[architecture] dependency policy satisfied`；这只证明现行 edge/SCC Policy 仍满足，不代表 Slice 8 的目标 detector/failure probe 已实现。
- `git diff --check`：通过。

独立 `trellis-check` 复核后补齐了：11 个状态机逐机失败/重试/取消/过期/人工路径；API filter/sort allowlist、写审计与精确旧路由清单；转写更正/重评权限；可执行 clean-cut 清单；composition-root/contract-only Guard 规则；两份跨层 code-spec 的 7 节合同；`CONTEXT.md` 共享语言；历史方案状态标记；后续 8 个切片对关键 ADR 的直接引用。复核后重复执行上述最小门禁，结果不变。

未运行后端、前端、E2E、Alembic、OpenAPI 和性能测试：本切片没有修改运行时代码、Schema 或生成 artifact；这些属于后续实现切片的完成门禁。目标 Architecture Guard 的 direct Provider、`.llm`、内存 Task、超大 composition root、源码硬编码规则探针也未执行，因为本切片只冻结 machine-readable Policy，实际 detector 由 Slice 8 实现。
