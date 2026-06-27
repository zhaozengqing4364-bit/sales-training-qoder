# PRD: 架构审计修复闭环 — StepFun 运行时拆分 + Config 治理落地 + 测试旅程补齐

> Task: `06-24-stepfun-config`
> 来源: 2026-06-24 架构审计深审（C1/C2/C3 三卡点）
> 状态: Draft (planning)
> Spec 引用: ADR 2026-05-27 (Config Asset B2 HITL), ADR 2026-06-20 (backend runtime boundary ownership), AGENTS.md §IV.5 (真实旅程验证)

---

## 1. 背景与动机

2026-06-24 架构审计下沉到代码级取证，确认三个正在互相放大的卡点：

- **C1 StepFun 运行时单体化**：`sales_bot/websocket/` 14,265 行集中在单一 mixin 体系，`stepfun_realtime_upstream.py` 2755 行 / 40+ async 方法承担 7 类职责；存在 387 行被覆盖的死代码；热路径每轮串行 DB 读写 + 音频 base64 双编解码，直接侵蚀 <300ms 延迟目标。
- **C2 Config Asset Center 治理未落地**：DualRead / B1 权威代码全就绪，但 4 个 feature flag 默认全关、`.env.example` 未声明，14 日双读观测窗从未启动，#78–#106 共 28 个 ready-for-agent 任务堵在出口；legacy direct practice fallback 仍读 live entity，存在历史快照被未来发布污染的窗口。
- **C3 关键旅程自动化验证空心化**：`test_sales_flow.py` / `test_analytics_flow.py` 100% skip，三条 WS 通道零 contract test，覆盖率压线 48.66%，<300ms 无持续验证，release truth gate 绕开重灾区。

三者构成死循环：C1 不敢拆（无测试网）→ C3 补不动（代码太大）→ C2 任务堵着 → 无精力拆 C1。**破局点在 C2 开关（零风险赚时间）+ C1 速效点（降延迟）+ C3 contract（兜底）**。

## 2. 目标

1. **C2 启动并完成 B1 切换**：staging 开双读 → 14 日零 mismatch 观测 → 切 B1 权威；生产后跟。解锁 28 任务出口。
2. **C1 降延迟 + 分阶段拆分**：先删死代码 + disclosure 增量写（速效），再按 Connection→Policy→Grounding→Feedback→UpstreamEvent 顺序拆 5 个 Service。
3. **C3 补三通道 WS contract test**：sales / presentation / examiner 各建 contract test，mock 上游，锁鉴权/admission/消息顺序，给 C1 拆分兜底。

## 3. 非目标（Out of Scope）

- B2 HITL 审批的系统级落地（import/publish 端点加 approval 拦截）→ 另开任务
- Practice Mode 枚举定义、Growth 延迟切片、RagProfile 双轨统一 → 另开任务
- Roleplay Contract 物理迁移到 common 中立边界 → ADR 2026-06-20 已锁方向，本轮不动
- 前端改动（除 contract test 不涉及前端）
- 数据库 schema 新增（situation_packs 表已存在）

## 4. 范围与分阶段交付

### P0 — 破局与零风险速效（本轮立即）

**P0.1 C2 启动双读观测**
- staging 环境变量：`SITUATION_PACK_DUAL_READ=true`、`SITUATION_PACK_READ_ORM=true`
- 生产保持 `false`
- 代码：`backend/src/common/config.py:44-59`（确认默认值与读取）
- 前置：跑 #93 初始 projection 数据迁移（`DEFAULT_ROLEPLAY_SITUATION_PACKS` → `situation_packs` 表）
- 验证：发布一个 pack，`ConfigBundleAuditLog.after_snapshot_json.projection_sync.status == "ok"`，`situation_packs` head row 已更新
- 观测面：`/support/runtime/overview` 的 `config_asset_center.dual_read`，mismatch_count=0
- 文件：`backend/src/curriculum_practice/services/roleplay/dual_read_repository.py`、`dual_read_promotion_gate.py`、`support_runtime_contributor.py`

**P0.2 C1 速效点 A：删死代码**
- 删除 `backend/src/sales_bot/websocket/stepfun_realtime_feedback.py:784-1171` 被 shadow 的 `_prepare_grounding_context`（388 行，下一个方法 `_schedule_response_after_commit` 在 1172）
- 前置：新增 characterization 测试锁住 `upstream.py:236` 的 `_prepare_grounding_context` 为运行时唯一入口（注：现有 `test_prepare_grounding_context_*` 不存在，不可作兜底）
- 验证：characterization 测试确认 MRO 下 `StepFunRealtimeHandler()._prepare_grounding_context` 解析到 upstream 版本；删后 feedback.py 无残留同名方法；现有 `test_stepfun_realtime_feedback.py` 全绿

**P0.3 C1 速效点 B：disclosure state 增量写**
- `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py:1782-1801` `_persist_roleplay_disclosure_state`（SELECT+UPDATE+commit 在 `async with self._db_session_factory()` 事务内，当前无条件执行）
- 改为"在进入事务前增加 state diff 短路"：`next_state == previous_state` 时直接 return，跳过 SELECT+UPDATE+commit。事务边界不变，仅新增进入事务前的 diff 检查
- 验证：新增 characterization 测试断言"一次话术 disclosure 无变化时 DB 写次数=0、有变化时写 1 次"；现有 roleplay compliance 测试全绿

**P0.4 C3 P0：补 `/ws/sales` contract test**
- 新建 `backend/tests/contract/test_sales_websocket_contract.py`
- mock 边界：`Phase4LocalStepFunProvider` 替换真实 StepFun upstream；`RuntimeGate.admit_session` / `verify_token` / `get_session_manager` 注入；SQLite 内存库覆盖 `AsyncSessionLocal`
- 锁定行为：
  - `INVALID_SESSION_ID` → close 4400
  - `RUNTIME_NOT_RUNNABLE` / `LEGACY_SALES_RUNTIME_DISABLED` → close 4413
  - auth 失败 → close 4001，owner mismatch → close 4003
  - 连接成功后收到 `connected`/`status` + `tts_audio` 消息顺序

### P1 — WS 契约补齐 + C1 拆分启动

**P1.1 C3 P1：补 `/ws/presentation` 与 `/ws/curriculum/examiner` contract test**
- 新建 `backend/tests/contract/test_presentation_websocket_contract.py`
- 新建 `backend/tests/contract/test_examiner_websocket_contract.py`
- presentation 锁定：slide/page_context、audio_end → asr_transcript → tts_audio 顺序、损坏 PPT 降级
- examiner 锁定：`CURRICULUM_EXAMINER_ENABLED=false` → 4404、INVALID_SESSION_ID → 4400、auth 4001、owner mismatch 4003、完成会话报告持久化

**P1.2 C1 拆分切口 1：`StepFunRealtimeConnectionService`**
- 先补 characterization 测试：MRO/调用目标、state snapshot round-trip（coach_health/turn_count/roleplay_disclosure_state/emotion_log）、连接 epoch 递增
- 搬迁：`connection.py` 全部 46 方法 + `handler.py:814-993` `handle_connection` + `handler.py:1012-1033` `_connect_upstream` + `handler.py:1087-1093` `_close_upstream`
- 退出标准：单文件 <800 行；connection 行为不变；CI 全绿

### P2 — C1 拆分推进 + C2 B1 切换

**P2.1 C1 拆分切口 2-5**（按依赖顺序）
- 切口 2 `StepFunRealtimePolicyService`：`policy.py:660-780` `_load_effective_policy`、`policy.py:293-525` `_enforce_tool_policy_guardrails`、`policy.py:1180-1351` `_handle_client_text` 等
- 切口 3 `StepFunRealtimeGroundingService`：`upstream.py:236-547` `_prepare_grounding_context`、`upstream.py:1872` `_execute_function_call`、disclosure state 系列、`handler.py:1095-1155` kb_lock_warmup
- 切口 4 `StepFunRealtimeFeedbackService`：`feedback.py:403-674` `_run_realtime_feedback`、emotion/thinking 持久化（含"每轮只读一次 DB"优化）
- 切口 5 `StepFunRealtimeUpstreamEventService`：`upstream.py:1066/1129` 事件路由、transcription/response/audio 处理、`_flush_active_response`、`_forward_audio_delta_chunk`（含消除 base64 双编解码）
- 每切口：先补 characterization 测试 → 搬迁 → 验证 MRO/状态快照/延迟契约/DB 写次数

**P2.2 C2 切 B1 权威**（14 日观测满后）
- 前置：staging 连续 14 日 `mismatch_count==0` 且 `blocked_reasons` 为空
- 人工审批后设 `SITUATION_PACK_B1_APPROVAL_ID=<审批单号>` + `SITUATION_PACK_B1_AUTHORITY=true`
- 记录 `SystemLog.action=situation_pack_b1_authority_promoted`
- staging 验证 7 日后，生产按同流程切
- rollback 预案：`B1_AUTHORITY=false` 即回退；注意 `DualReadPromotionGateService._has_unresolved_projection_sync_failure` 历史失败需标记恢复

## 5. 验收标准（DoD）

- [ ] staging 双读观测连续 14 日 mismatch=0，记录在案
- [ ] B1 权威在 staging 切换成功，生产后跟，rollback 预案就绪
- [ ] `stepfun_realtime_feedback.py` 死代码已删，无 `_prepare_grounding_context` 重复实现
- [ ] disclosure state 增量写生效，characterization 测试验证 DB 写次数
- [ ] 三条 WS 通道 contract test 全部通过，覆盖鉴权/admission/消息顺序
- [ ] C1 五切口拆分完成，单文件 <800 行，热路径延迟 P95 不退化（characterization 测试锁基线）
- [ ] `ruff check` / `mypy` / 相关测试全绿
- [ ] 覆盖率门禁不低于 48%（`pyproject.toml:75` 现状）。提门禁至 55%、治理 `test_sales_flow`/`test_analytics_flow` skip 另开 C3 延伸任务，不纳入本 epic DoD
- [ ] ADR 更新：C1 拆分边界、C2 B1 切换决策回写

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| C1 拆分导致 MRO 行为漂移 | 每切口先补 characterization 测试锁基线；单切口单 PR 可回滚 |
| B1 切换后 projection sync 历史失败卡 gate | 切换前清理 `ConfigBundleAuditLog` 失败记录；rollback flag 即时回退 |
| contract test mock 边界不准 | 复用 `Phase4LocalStepFunProvider`（已在 e2e 验证）；先对齐前端 Playwright 已跑通的消息契约 |
| 拆分暴露隐藏 bug | 控节奏：先 contract（锁行为）→ 再拆；每阶段先 SQLite 内存环境再接 PostgreSQL smoke |
| 14 日观测窗被打断 | mismatch 告警接 on-call；观测中断需重新计时 |

## 7. 回写触发（AGENTS.md §0 强制回写）

- C1 拆分若发现 mixin 边界与 ADR 2026-06-20 冲突 → 回写 ADR
- C2 B1 切换若发现 gate 条件不充分 → 回写 ADR 2026-05-27
- 任何切口拆分后热路径延迟退化 → 暂停拆分，回写本 PRD

## 8. 引用证据

- C1: `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py:236,1207,1782-1801,2359`；`stepfun_realtime_feedback.py:784-1171`（死代码 388 行，下一个方法在 1172）；`stepfun_realtime_state.py`（150+ 字段）
- C2: `backend/src/common/config.py:44-59`；`curriculum_practice/services/roleplay/dual_read_repository.py:31,128`；`dual_read_promotion_gate.py:54,82,119`；`admin/config_bundles/lifecycle.py:320`；`sales_bot/services/voice_runtime_policy.py:1073,1136`；`alembic/versions/20260527_1100_069_situation_packs.py`
- C3: `backend/pyproject.toml:69,75`；`tests/integration/test_sales_flow.py`（6 skip）、`test_analytics_flow.py`（7 skip）；`tests/contract/`（27 文件无 WS 专属）；`scripts/critical-quality-gate.sh:151-172`；`web/tests/e2e/sales-phase4.spec.ts`
