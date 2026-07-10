# 新人路径前置闸门

## Goal

把 `unlock_after_unit_ids` 从旧 `/paths` 投影中的展示性判断，收敛为发布时可校验、Training Journey 可解释、所有后端直接入口不可绕过的统一训练闸门；同一 active revision、同一 learner 在所有读模型和访问入口必须得到一致结论。

## What I Already Know

- 当前 active path revision 已保存 `unlock_after_unit_ids`，但 Training Journey 未完整消费该字段。
- 旧 Path Projection 在 `build_path_payload()` 内自行计算前置完成情况，与 Journey 存在双规则漂移风险。
- 直接材料、录音、测验和 realtime 入口复用 Journey 的 `locked` 结果或旧 Path Projection；只修页面展示不能阻止直接 API 绕过。
- 已有详细实施计划：`docs/superpowers/plans/2026-07-10-newcomer-path-prerequisite-gates.md`。
- 该任务是新人训练 P0/P1 修复总计划的第二项；Readiness 决策完整性已在上一任务完成，Learning Topic Attempt 证据另行处理。
- CodeGraph 目录存在，但当前 linked worktree 没有可用索引；本任务不创建索引，改用源码与调用点扫描。

## Assumptions (Temporary)

- 保留字段名和 revision JSON 结构，不做数据库迁移。
- active asset revision 是运行时唯一有效配置来源；旧 revision 的完成证据不能解锁当前 revision。
- 正常等待前置训练是非终态业务锁定；历史非法 active revision 必须 fail-closed，但 Journey 请求本身不能 500。
- 直接访问锁定资源继续返回既有 404 语义，避免暴露隐藏单元是否存在。

## Open Questions

- 无。

## Requirements (Evolving)

### 发布时配置校验

- 新建纯规则 Module `path_prerequisite_policy.py`，集中引用合法性校验和运行时解锁计算；policy 使用无 HTTP 语义的领域异常，写入边界再映射成稳定 API 错误，避免循环依赖。
- prerequisite 只能指向同一 revision 中更早、已启用、可完成、属于主路径 Module 的 target unit。
- 拒绝空白、重复、未知、同级、后置、停用、跨 Module 重复 target、realtime/无 target unit 和 Learning Topic 来源引用。
- 写入校验失败使用 `[NEWCOMER_PATH_PREREQUISITE_INVALID]`，在保存/发布前阻止非法 revision 生效。
- Pydantic 输入边界同时拒绝 `unlock_after_unit_ids` 中空值和重复值；实际 path-config PUT 稳定映射为 `[NEWCOMER_PATH_PREREQUISITE_INVALID]` / 422，其他 validation 错误不受影响。
- 历史 revision 读取通过显式 validation context 保留非法 prerequisite 原值交给 runtime policy；兼容读取不得放宽新保存请求。

### 运行时统一规则

- `TrainingJourneyService` 从 active revision 复制 `unlock_after_unit_ids`，不得从旧 unit 表或展示结果反推。
- Journey 生成公开 payload 前只计算一次 prerequisite decisions，并复用结果填充 `locked`、`block_reason`、`next_action` 和 diagnostics。
- 未完成前置训练使用 `[NEWCOMER_PREREQUISITE_NOT_COMPLETED]`，用户文案为“请先完成前置训练，再开始本任务。”，保持 `not_started`、非终态。
- 历史非法 active revision 使用 `[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]` 并锁定相关 Module，不抛 KeyError、不忽略 blank/duplicate/未知/停用/歧义/realtime/Learning Topic owner、不返回 500。
- 前置完成证据落到当前 active revision 后，再次读取 Journey 必须立即解锁。
- Audio group 的 prerequisite 按被引用的 target unit 精确判断；同组其他时长档位的完成证据不能代替。
- 已有锁定（含 Readiness/realtime/provider readiness）不得被 prerequisite policy 放宽。

### 读模型与直接访问一致性

- 旧 `/paths` 投影与 Training Journey 共用同一 prerequisite policy，不保留第二套 `completed_unit_ids/missing` 规则。
- 同一 learner、同一 active revision 对齐 unit 后，两套读模型的 `locked` 必须一致。
- 材料文件、录音材料、录音提交、测验和 realtime start 等直接入口必须复用统一锁定结果并 fail-closed。
- 锁定资源保持既有 404 对外语义；解锁后的当前 revision 资源可访问。
- 旧 revision 的通过证据不能解锁当前 revision。
- Learning Topic 保持 `required=false`、`blocks_next=false`，不能成为主路径 prerequisite，也不能被主路径 prerequisite 误锁。

### 治理与契约

- 不为漂移测试 fixture 放宽生产 canonical 校验：`elevator_pitch` 保持 `audio_scoring_group`；需要 `article_exam` 的测试使用 canonical `business_skills`。
- API 契约记录三个稳定错误码及其语义。
- policy、Journey、旧投影、直接访问和 realtime 回归测试加入 `scripts/critical-quality-gate.sh`。
- 无新增第三方依赖、无无关重构、无普通用户界面内部字段泄露。

## Acceptance Criteria (Evolving)

- [x] 非法 prerequisite 引用在 revision 写入校验阶段返回 `[NEWCOMER_PATH_PREREQUISITE_INVALID]`。
- [x] 未完成前置训练时 Journey Module 锁定、action disabled、展示用户语言原因和 `[NEWCOMER_PREREQUISITE_NOT_COMPLETED]`，且不是终态错误。
- [x] 当前 active revision 的前置完成证据写入后，后续 Module 立即解锁。
- [x] 历史非法 active revision 返回锁定和 `[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]`，Journey 请求不 500。
- [x] 历史 blank/duplicate prerequisite 通过 legacy `/paths` 二次投影时也保持 fail-closed，不在 `SalesTrainerPathConfig` 重建时抛 validation 500。
- [x] Audio group 只有被引用 target unit 自身的完成证据可解锁后续 Module。
- [x] Journey 与旧 `/paths` 投影对同一 learner 的锁定结果完全一致。
- [x] 锁定状态下材料、录音、测验和 realtime 直接入口不可绕过，并保持既有 404/拒绝语义。
- [x] 只有当前 active revision 的通过证据可以解锁；旧 revision 证据无效。
- [x] Learning Topic 仍可独立访问，且不能作为主路径 prerequisite。
- [x] 任务定向 Pytest、Ruff、格式、脚本语法通过，API 契约同步更新。
- [ ] 完整 critical quality gate：仍被本任务未修改的 `TrainingJourney` Learning Topic helper 两条 mypy 基线阻塞。

## Definition of Done

- 新增纯 prerequisite policy 及边界、非法配置、有序解锁测试。
- Training Journey 与旧 Path Projection 只消费同一 policy，重复规则删除。
- 直接入口的锁定、解锁、revision 隔离和 Learning Topic 非阻塞路径有回归证据。
- `docs/api-contract/sales-trainer.md`、Trellis executable spec 和 critical gate 与最终实现一致。
- 无 schema migration、无新依赖、无无关重构；风险与回滚路径可解释。

## Expansion Sweep

### Future Evolution

- 未来可增加可视化 dependency graph、发布预览和循环依赖诊断；本任务只支持当前有序线性 path revision 的前置引用。
- 未来可支持多分支路径；当前规则坚持 prerequisite owner 必须更早，避免在没有状态机设计时引入图循环。

### Related Scenarios

- Realtime roleplay 的最终开放仍由 Readiness approve 和 provider readiness 决定；prerequisite 只能增加锁定，不能绕过人工复核。
- Learning Topic Attempt 证据和独立进度语义在后续任务处理，本任务只保证其不参与主路径闸门。

### Failure and Edge Cases

- 空白/重复/未知引用、多个 Module 指向同一 target unit、停用 owner、无 target unit、乱序配置、历史坏 revision、旧 revision 证据、已有锁定叠加。
- Audio group 只完成一个时长档位，但后续 Module 引用同组另一 target unit。
- 运行时非法配置必须对相关 Module fail-closed，并返回稳定可解释诊断。

## Out of Scope

- Readiness 决策权限、幂等、并发或持久化变更。
- Learning Topic Attempt 数据模型和进度统一。
- 路径 UI 重设计、依赖关系编辑器或可视化图。
- 数据库 schema/migration、历史 revision 批量改写。
- 完整 DAG、循环依赖求解或并行分支路径引擎。
- 重构整个 Training Journey、Path Service 或全局访问控制。

## Technical Approach

- 在 `sales_trainer/services` 新建无 IO 的 policy Module，数据结构只表达 Module 顺序、target units、prerequisites、完成和既有锁定。
- revision 写入边界调用引用校验；运行时对历史非法配置使用同一 owner/order 规则 fail-closed。
- Training Journey 先建立所有 Module/完成证据，只对基础 Path Module 一次性应用 policy；同一 `base_module_key` 的 AI Coach 等派生 Module 继承 decision，避免重复 `module_key` 覆盖。
- 旧 Path Projection 不再按 unit level 重算 prerequisite，而是以 Journey 已应用的同一 decision 精确覆盖锁定状态；这同时规避 audio group 多 option 重复 key 和旧 progress revision 漂移。
- 直接入口继续通过 `learner_unit_access`/Journey 或统一 Path Projection 的锁定结果，不新增分散权限判断。

## Decision (ADR-lite)

**Context:** `unlock_after_unit_ids` 当前跨 revision config、Journey、旧 `/paths` 和直接 API 访问，但规则散落或缺失，导致展示锁定不等于后端访问锁定。

**Decision:** 建立单一纯 prerequisite policy，发布时校验新 revision，运行时对历史坏 revision fail-closed；Journey 和旧 Path Projection 共同消费，直接入口复用 Journey/投影锁定结果。依赖只允许指向当前 revision 中更早、已启用、可完成的主路径 target unit，Learning Topic 永不成为 prerequisite。

**Consequences:** 不需要数据迁移，现有合法 revision 兼容；历史非法 active revision 会从“可能被忽略/绕过”变为明确锁定并提示培训负责人修复。系统获得读模型和访问入口一致性，但仍不提供通用 DAG 能力。

## Technical Notes

- 实施计划：`docs/superpowers/plans/2026-07-10-newcomer-path-prerequisite-gates.md`
- 总计划：`docs/superpowers/plans/2026-07-10-newcomer-training-p0-p1-remediation-index.md`
- 配置模型：`backend/src/sales_trainer/services/path_config_models.py`
- Journey：`backend/src/sales_trainer/services/training_journey_service.py`
- 旧投影：`backend/src/sales_trainer/services/path_projection_payloads.py`
- 直接访问：`backend/src/sales_trainer/services/learner_unit_access.py`

## Implementation Plan (Small PRs)

- **PR1 — 规则冻结**：纯 policy、Pydantic 边界、revision 写入校验和非法引用测试。
- **PR2 — Journey 执行**：active revision 字段传递、统一锁定/诊断、完成后解锁和历史坏 revision 回归。
- **PR3 — 旧投影统一**：删除双规则、读模型 parity 和 canonical fixture 修复。
- **PR4 — 防绕过与治理**：材料/录音/测验/realtime 直接访问、revision 隔离、Learning Topic 非阻塞、契约和 release gate。
