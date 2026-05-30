# ADR 2026-05-27: Config Asset Center Phase B2 HITL 治理

## Status

**Proposed — 待人工确认。** 本文档是 Epic [#78](https://github.com/zhaozengqing4364-bit/sales-training-qoder/issues/78) / Issue [#106](https://github.com/zhaozengqing4364-bit/sales-training-qoder/issues/106) 的 HITL 产出。在人工确认前**不得**创建 Phase B2 的 `ready-for-agent` implementation ticket，也不得开始 entity-backed write 实现。

## Context

配置资产管理中心（[config-asset-center.md](../architecture/config-asset-center.md) v1.2.1）将 SituationPack 从 `BusinessRuleConfig` ruleset 演进为一等领域资产，分三期落地：

| 阶段 | 写入权威 | 读取权威 | 状态 |
|------|---------|---------|------|
| Phase A | `BusinessRuleConfig` ruleset | Phase A adapter | 已存在 |
| Phase B1 | 仍为 `BusinessRuleConfig` + `ConfigVersion.snapshot_json` | `situation_packs` head projection（#96 切换后） | Wave 4–5 交付中 |
| Phase B2 | `ConfigBundleStorageAdapter` entity-backed write | 同上，写入不再经 ruleset | **未启动，需本 ADR** |

Wave 5 同时交付 Import/Export（#102–#105）与 B1 runtime authority 切换（#96）。这些操作均可能改变生产中的 Roleplay Contract 语义，但当前缺少统一的「何时必须人工审批」契约。ADR [2026-05-26-roleplay-contract-governance.md](./2026-05-26-roleplay-contract-governance.md) 锁定了运行时权威与 ConfigBundle 治理接入，但未定义 Config Asset Center 各操作的人类审批边界。

本 ADR 补齐 HITL 治理：**SituationPack 发布、Import 冲突处置、B1 authority 提升** 的审批时机与标准；并定义 **Phase B2 启动前置条件**（含与 #96 双读稳定门禁的关系）。

## Purpose

1. 明确 Config Asset Center 中 **AFK（可自动化）** 与 **HITL（须人工确认）** 操作的边界。
2. 为 SituationPack publish、Import 冲突、B1 authority promotion 提供可执行的决策标准、回滚路径与审计要求。
3. 锁定 Phase B2（entity-backed write）的启动门禁，避免在 B1 未稳定或缺少 `ConfigBundleStorageAdapter` 契约时提前切换写入权威。

---

## Decision

### 1. HITL 分类原则

| 类别 | 定义 | 典型操作 |
|------|------|---------|
| **AFK** | 机器校验通过即可执行；失败为 Terminal，不静默降级 | draft 保存、validate、dry_run import、双读观测 |
| **HITL-Notify** | 可自动执行，但必须留痕并通知指定角色 | 低风险 publish（见 §2）、`new_version` import 冲突 |
| **HITL-Approve** | 执行前必须有人工显式批准（reason + 确认项） | 高风险 publish、B1 authority 切换、Phase B2 启动、`publish_after_import` 批量发布 |
| **HITL-Block** | 禁止自动路径；仅人工在 Admin UI 逐条处置 | `replace_draft` 覆盖已发布语义、`fail` 策略下的部分成功导入 |

**固定规则**：
- 所有 publish / rollback / authority 切换必须携带非空 `reason` 与 `trace_id`（与现有 ConfigBundle lifecycle 一致）。
- HITL 不能通过「跳过重连式重试」绕过 Terminal 校验；校验失败 = 停止，等人修配置。
- 本 ADR **不引入**新的审批 UI 或工作流引擎；Phase B2 之前 HITL 通过 Admin 操作 + audit log + issue/completion note 证据链实现。

---

### 2. SituationPack 发布 — 何时需要人工审批

SituationPack 生命周期走 ConfigBundle（`bundle_key = roleplay.situation_packs.ruleset`）：draft → validate → preview → **publish** → rollback。

#### 2.1 AFK 路径（无需事前人工批准）

满足**全部**条件时，publish 可由具备 `config_bundle:publish` 权限的管理员直接执行（仍须填写 reason）：

| # | 条件 |
|---|------|
| P-A1 | `validate` 与 `preview` 均已通过，无 blocking reason |
| P-A2 | 变更仅涉及 `label`、`description` 等非语义字段（hasher 对 content_hash 无影响） |
| P-A3 | 该 `code` 已有至少一次 published 历史，且 `relationship_context` / `forbidden_claim_patterns` / `runtime_violation_policy` 与上一 published 版本 hash 一致 |
| P-A4 | 双读开启时，该 pack 在最近 7 日内无 `situation_pack_dual_read_mismatch` 记录 |
| P-A5 | compile preview 中 role_anchor 冲突 gate 无 warning |

#### 2.2 HITL-Approve 路径（发布前须人工确认）

满足**任一**条件时，publish 进入 HITL-Approve；执行 publish 的 completion note 或 audit reason 必须引用确认 checklist（§7）编号：

| # | 触发条件 | 须确认的内容 |
|---|---------|-------------|
| P-H1 | **新 `code` 首次 publish** | 关系阶段语义、禁止声称列表、违规策略、兼容模式 |
| P-H2 | **`relationship_context` 变更**（含 `has_prior_meeting`、`meeting_history_summary` 等） | 与 ADR 2026-05-26 关系上下文底线一致（如 `first_visit` 须 `has_prior_meeting=false`） |
| P-H3 | **`forbidden_claim_patterns` / `forbidden_topic_codes` / `forbidden_stage_codes` 变更** | compile preview 人工审阅；确认不与其他已发布 Persona `role_anchor.must_not` 语义冲突 |
| P-H4 | **`runtime_violation_policy` 或 `conflict_response_strategy` 变更** | 确认 blocking regenerate 仍 ≤1 次（ADR 2026-05-26 Fixed Rules） |
| P-H5 | **存在 active PracticeTemplate 引用该 pack**（published 模板 `situation_pack_code` 或 frozen ref 指向该 code） | 影响面：引用模板数量、是否需模板重发 |
| P-H6 | **双读开启且该 pack 在观察窗口内有 mismatch** | 以 Phase A 为准根因分析完成后再批 |

#### 2.3 Publish 后派生动作（AFK，失败告警）

| 动作 | 行为 | 失败处理 |
|------|------|---------|
| ConfigBundle snapshot 写入 | 不可变版本权威 | Terminal：publish 整体失败 |
| `situation_packs` head projection 同步 | B1 adapter `sync_head_projection()` | **不阻断** publish；告警 + audit event；支持从 snapshot 重建 |
| 双读 hash 对账 | 下一请求周期比对 | mismatch → metric + log；不自动 rollback |

#### 2.4 SituationPack Rollback

| 场景 | 策略 | HITL |
|------|------|------|
| 发布后 compile/runtime 异常 | ConfigBundle `rollback` 到上一 `published` snapshot | HITL-Notify：须 reason；若 P-H5 引用存在则 HITL-Approve |
| projection 与 snapshot 不一致 | 从 snapshot 重建 projection（AFK 修复脚本） | 无需 rollback lifecycle |
| 错误 publish 已冻结进 PracticeTemplate | rollback pack **不** retroactively 改已发布模板 | 须 HITL-Approve 决定是否触发模板重发 |

**审计字段**（ConfigBundle audit + SystemLog）：`action=publish|rollback`、`bundle_key`、`actor_id`、`before_version_id`、`after_version_id`、`reason`、`trace_id`、`affected_pack_codes[]`、`hitl_checklist_refs[]`（若适用）。

---

### 3. Import 冲突 — 何时需要人工审批

Import 协议见 config-asset-center.md §8。默认 `conflict_strategy=new_version`（AFK 安全）。

#### 3.1 按 conflict_strategy 分类

| 策略 | 默认 HITL | 说明 |
|------|----------|------|
| `skip` | AFK | 跳过已存在 natural key；audit 记录 skipped |
| `new_version` | AFK | 创建新 draft，**不**自动 publish |
| `fail` | AFK（单次请求） | 遇冲突整批失败；无部分写入 |
| `replace_draft` | **HITL-Approve** 若目标存在 published 版本 | 仅允许覆盖 draft row；若仅有 published → 等价 `new_version` |

#### 3.2 须 HITL-Approve 的 Import 场景

| # | 场景 | 决策标准 |
|---|------|---------|
| I-H1 | `publish_after_import=true` 且导入含 **SituationPack** 或其他 ConfigBundle-governed 资产 | 须先 dry_run；人工确认 ImportReport + 各资产 preview；reason 引用 export `content_hash` |
| I-H2 | 同一 natural key 的 `content_hash` 与本地 published 不一致，且策略非 `fail` | 须确认「保留本地」或「以导入为准（new_version）」 |
| I-H3 | 导入会改变已发布 PracticeTemplate 依赖拓扑（depends_on 断裂或版本降级） | 须确认模板重绑计划 |
| I-H4 | `replace_draft` 且本地存在同 key draft 由他人编辑中 | 须确认覆盖 |

#### 3.3 Import 冲突 Rollback

Import **无**单事务跨全拓扑回滚。处置原则：

1. **dry_run 优先**：任何 HITL-Approve 导入必须先 dry_run。
2. **部分成功**：ImportReport 列出 `imported` / `skipped` / `failed`；失败项不触发 `publish_after_import` 链式发布。
3. **误导入 published 语义**：对 native-lifecycle 资产走各自 `archive` + 从 export 重新 `new_version`；对 SituationPack 走 ConfigBundle rollback（§2.4）。
4. **审计**：`SystemLog.action=config_asset_import` 已含 `dry_run`、`id_mapping`、`errors`、`trace_id`、`reason`；HITL 批准须追加 `hitl_approver`、`hitl_checklist_refs` 到 operation reason 或 completion note。

---

### 4. B1 Authority Promotion（#96）— 人工提升门禁

#96 将 runtime read authority 从 Phase A adapter 切换到 B1 projection adapter。**这不是 Phase B2**；写入权威仍在 `BusinessRuleConfig`。

#### 4.1 与 #96 双读稳定窗口的关系

| 里程碑 | 条件 | 负责 |
|--------|------|------|
| M1 双读观测开启 | #95 完成；staging `SITUATION_PACK_DUAL_READ=true` | AFK |
| M2 稳定观察窗口 | 连续 **≥14 日历日** 无 `situation_pack_dual_read_mismatch` 告警（生产与 staging 分别计算） | 运维观测 |
| M3 HITL 审批 | 人工审阅 `GET /support/runtime/overview` → `config_asset_center.dual_read`：`mismatch_count`、`last_mismatch`、`sample_mismatches`；projection sync 失败告警为 0 | **HITL-Approve** |
| M4 Authority 切换 | 配置开关：`SITUATION_PACK_RUNTIME_AUTHORITY=b1`（名称以实现为准） | AFK（M3 通过后） |
| M5 回滚就绪 | 保留 Phase A fallback 至少一个 release；开关可瞬时切回 `a` | 固定要求 |

**决策标准（M3 必查）**：

1. M2 窗口内 **零** mismatch（非「低于阈值」）。
2. `sync_head_projection` 失败仅有告警、无未修复的 head/snapshot 长期分叉。
3. 至少一条集成测试路径（curriculum snapshot + direct practice）在 B1 authority 下通过 roleplay contract eval。
4. 生产环境若开启双读，须与 staging 同样满足 M2，**不可**仅用 staging 证据批准生产切换。

#### 4.2 B1 Promotion Rollback

| 触发 | 动作 | HITL |
|------|------|------|
| 切换后 mismatch 或 compile 回归 | 开关切回 Phase A | HITL-Notify（24h 内 postmortem reason） |
| projection 损坏 | 从 ConfigBundle snapshot 重建；**不**切 write authority | AFK |
| 误切换 | 立即切回 + audit | HITL-Notify |

**明确禁止**：因 B1 切换问题而 rollback ConfigBundle published snapshot（除非 pack 内容本身错误，见 §2.4）。

---

### 5. Phase B2 启动前置条件（entity-backed write）

Phase B2 引入 `ConfigBundleStorageAdapter`，使 `situation_packs` 表成为 lifecycle **写入**权威，`BusinessRuleConfig` ruleset 降级为历史只读。

#### 5.1 硬门禁（全部满足才可开 B2 implementation epic）

| # | 前置条件 |
|---|---------|
| B2-1 | 本 ADR Status = **Accepted** |
| B2-2 | B1 authority 在生产已稳定 ≥**4 周**（M4 完成后），且无 authority 回滚 |
| B2-3 | Import/Export（#102–#105）已在 staging 完成 dry_run → import → publish_after_import → 开练 E2E |
| B2-4 | 独立 ADR 或 design note 定义 `ConfigBundleStorageAdapter` 接口（draft/validate/publish/rollback 的 entity-backed 契约）——**不在本 ADR 范围** |
| B2-5 | `EntitySituationPackStorageAdapter` 实现计划通过 eng review，含双写/影子校验方案 |

#### 5.2 Phase B2 切换 HITL

| 操作 | HITL |
|------|------|
| 开启 entity-backed write（feature flag） | HITL-Approve：checklist §7 C10–C12 |
| 停用 `BusinessRuleConfig` ruleset 写入 | HITL-Approve + 迁移 completion note |
| 历史 ruleset 只读归档 | HITL-Notify |

#### 5.3 Phase B2 Rollback

- 写入切回 B1 path（projection + BusinessRuleConfig backing store）。
- 切换窗口内保持双写或影子 hash 对账；**运行时仍只消费 frozen Roleplay Contract**（ADR 2026-05-26 §8）。
- 不得因 B2 回滚修改已创建会话的 snapshot。

---

### 6. 审计与权限汇总

| 操作 | 权限（现有模型） | 审计落点 | reason 必填 |
|------|-----------------|---------|:-----------:|
| SituationPack draft/validate/preview | `config_bundle:write` | ConfigBundleAuditLog | validate/preview 可选；publish 必填 |
| SituationPack publish/rollback | `config_bundle:publish` | ConfigBundleAuditLog | 是 |
| Import / Export | admin import/export 权限 | SystemLog `config_asset_import` / `config_asset_export` | import 必填 |
| B1 authority 开关 | 平台 admin + 变更 reason | SystemLog + 变更 ticket | 是 |
| Phase B2 write flag | 平台 admin | SystemLog + ADR 引用 | 是 |

所有 audit 记录必须含 `trace_id`。HITL-Approve 操作须在 reason 或 completion note 中注明 `hitl_checklist_refs`（如 `C3,C7`）。

---

### 7. Human Confirmation Checklist

在标记 #106 完成并开启 Phase B2 implementation epic 前，须逐项人工确认：

| # | 确认项 | 状态 |
|---|--------|------|
| C1 | SituationPack publish 的 AFK / HITL-Approve 边界（§2.1–2.2）可执行且可审计 | ☐ 待确认 |
| C2 | 新 code 首次 publish 与语义字段变更须 HITL-Approve（P-H1–P-H6） | ☐ 待确认 |
| C3 | Import 默认 `new_version`；`publish_after_import` 与 hash 冲突须 HITL（§3） | ☐ 待确认 |
| C4 | #96 B1 切换须 **14 天零 mismatch** + M3 人工审批（§4.1） | ☐ 待确认 |
| C5 | B1 回滚保留 Phase A fallback，不自动 rollback ConfigBundle snapshot（§4.2） | ☐ 待确认 |
| C6 | Phase B2 五项硬门禁（B2-1–B2-5）合理；B2-4 需单独 design ADR | ☐ 待确认 |
| C7 | 审计字段与 permission 映射与现网一致（§6） | ☐ 待确认 |
| C8 | 与 ADR 2026-05-26 无冲突（frozen contract、无第二套 lifecycle、blocking regenerate ≤1） | ☐ 待确认 |
| C9 | 本文档不包含实现代码，仅为治理 ADR | ☐ 待确认 |
| C10 | （Phase B2 启动时）entity-backed write 双写/影子校验方案已评审 | ☐ 待 B2 前确认 |
| C11 | （Phase B2 启动时）BusinessRuleConfig ruleset 降级计划已评审 | ☐ 待 B2 前确认 |
| C12 | （Phase B2 启动时）生产回滚演练已完成 | ☐ 待 B2 前确认 |

---

## 8. #106 Completion Evidence

截至 2026-05-27，本文仍保持 **Proposed — 待人工确认**。本轮实现只补齐 Phase B1 promotion 的可执行门禁与证据面，不启动 Phase B2，也不创建 Phase B2 `ready-for-agent` implementation placeholder。

已落地的 B1 证据面：

| 证据 | 状态 |
|------|------|
| `SITUATION_PACK_B1_APPROVAL_ID` 环境配置已加入，默认空值；B1 authority 请求必须携带非空 approval id | 已实现 |
| `DualReadPromotionGateService` 会检查 14 日 mismatch 窗口、projection sync 未恢复失败与 approval id | 已实现 |
| `SITUATION_PACK_B1_AUTHORITY=true` 仅代表请求；gate 不通过时运行时强制降级 Phase A | 已实现 |
| `SystemLog.action=situation_pack_dual_read_mismatch` 与 `situation_pack_b1_authority_blocked` 可作为 M2/M3 证据 | 已实现 |
| `GET /support/runtime/overview` 暴露 `promotion_ready`、`blocked_reasons`、`approval_id`、`window_start`、`window_end` | 已实现 |
| Phase B2 implementation ticket | 未创建，等待本 ADR Accepted |

人工待确认项仍以 §7 为准；任何 Phase B2 entity-backed write 工作必须等本 ADR 状态从 Proposed 改为 Accepted 后另行拆分。

---

## Consequences

### Positive

- SituationPack、Import、B1 切换的 HITL 边界可执行，减少 AFK agent 误操作生产语义。
- #96 双读 2 周稳定窗口与 authority 切换绑定，避免过早切 B1。
- Phase B2 启动条件 explicit，防止跳过 `ConfigBundleStorageAdapter` 设计。
- 审计与 rollback 路径统一，符合 ConfigBundle 与 AGENTS.md §III 单一权威原则。

### Negative

- 首次 publish 与语义变更增加人工延迟。
- `publish_after_import` 无法全 AFK，批量部署需排期 HITL。
- Phase B2 额外依赖 B2-4 design ADR，Epic #78 尾部可能再延一轮 HITL。

### Risks

| 风险 | 缓解 |
|------|------|
| HITL 流于形式（reason 空泛） | checklist 编号强制写入 audit；completion note 模板校验 |
| 14 天零 mismatch 过严导致长期不切 B1 | 允许 staging 先切；生产可设独立观察窗；mismatch 须修根因非调阈值 |
| Import 部分成功后状态不一致 | dry_run 强制 + ImportReport 驱动人工决策；禁止 silent publish_after_import |
| Phase B2 与 B1 projection 职责混淆 | 本文 §5 明确 B2 仅改 **写入** authority；读取接口不变 |

---

## Rejected Options

- **全部 publish AFK** — 拒绝；关系史与 forbidden patterns 变更直接影响 Roleplay Contract 语义。
- **B1 切换仅 staging 14 天即批准生产** — 拒绝；生产须独立观察窗（§4.1 M2）。
- **Import 冲突默认 `replace_draft`** — 拒绝；与 config-asset-center.md 默认 `new_version` 不一致且易覆盖 published 语义。
- **Phase B2 与 B1 并行启动** — 拒绝；写入双轨会破坏单一 authority（AGENTS.md §III.1）。
- **无 audit 的 feature flag 切换** — 拒绝；authority 切换必须 reason + trace_id。

---

## Follow-up

1. 人工确认 C1–C9 后，将本 ADR Status 更新为 **Accepted**，关闭 #106。
2. **禁止**在 C1–C9 确认前创建 Phase B2 `ready-for-agent` implementation issues。
3. B2-4 `ConfigBundleStorageAdapter` 契约须单独 design ADR / issue，引用本 ADR §5。
4. #96 completion note 须引用 §4.1 M3 证据（dual_read overview 截图或 JSON、观察窗口起止日期、approver）。
5. #104 `# publish_after_import` 集成测试须覆盖 I-H1 HITL 路径（dry_run 先行、reason 必填）。

---

## References

- [config-asset-center.md](../architecture/config-asset-center.md) v1.2.1 — Phase B1/B2、Import、双读、#96
- [ADR 2026-05-26: Roleplay Contract 治理](./2026-05-26-roleplay-contract-governance.md)
- [ADR 2026-05-11: 架构边界与 HITL 门禁](./2026-05-11-architecture-boundary-domain-contract.md) §6
- Epic [#78](https://github.com/zhaozengqing4364-bit/sales-training-qoder/issues/78)、[#96](https://github.com/zhaozengqing4364-bit/sales-training-qoder/issues/96)、[#106](https://github.com/zhaozengqing4364-bit/sales-training-qoder/issues/106)

---

> **HITL 提示**：本文档是 issue #106 的交付物。请逐项确认 §7 Checklist（C1–C9 为 #106 范围；C10–C12 为 Phase B2 启动时确认）。确认后回复「接受 ADR，可关闭 #106」或指出需调整的条款。**确认前不得开始 Phase B2 实现。**
