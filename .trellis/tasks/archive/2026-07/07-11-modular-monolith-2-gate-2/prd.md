# 模块化单体 2.0 Gate 2：Realtime Session Engine tracer bullet

## Goal

在不改变现有 REST、WebSocket、close code、二进制音频、权限、RuntimeGate、冻结 snapshot、
KB fail-closed、epoch、评分和报告幂等合同的前提下，以 Presentation 为第一个 tracer bullet，
建立显式 Realtime Session Engine 状态与 Scenario Hook 组合缝，证明 Presentation 不再通过
Sales runtime 继承后关闭能力，并为 Gate 3 Provider Port / Grounding 单一权威提供稳定宿主。

## What I already know

- 权威设计、ADR、路线图和当前 Goal 已由用户批准，Gate 2 范围与执行顺序固定。
- Gate 0A–1B 已闭环；唯一关键门禁可作为迁移前行为真相。
- Gate 2 必须交付 Golden Conversation Contract inventory、显式 Connection/Turn/Grounding/Evidence
  state、Engine shell、Presentation tracer bullet、新旧 differential test、Presentation 退出 Sales 状态继承。
- 采用 Strangler / Branch by Abstraction；新旧路径必须有 feature flag 和快速回滚点。
- Goal 明确禁止中途询问；所有可由代码与权威文档推导的问题采用最保守、兼容、可回滚决定，记录
  到本 PRD 与 `implementation-notes.md`。

## Assumptions (confirmed from repository truth)

- Gate 2 只迁移 Presentation；Sales 保持现有默认 runtime，Examiner 不在本 Gate 切换。
- Engine 先拥有显式会话状态、转换不变量、快照和生命周期编排；StepFun wire protocol 与现有
  persistence 暂由兼容 Adapter 执行，不在 Gate 2 提前完成 Provider/Grounding 深化。
- Differential test 以同一 Golden Conversation 输入比较外部事件序列、终态、证据和幂等副作用，
  不要求比较内部对象结构或日志文本。
- 新路径默认启用；`PRESENTATION_REALTIME_ENGINE_ENABLED=false` 是 scenario-wide 快速回滚。
- 兼容 Adapter 可以暂时复用位于 `sales_bot` 的 StepFun Mixin，但 Presentation 生产 façade 不再
  继承它，且 Presentation 模式不得构造 SalesStage/FuzzyDetection/RealtimeScoring 能力。

## Open Questions

- 无用户阻塞问题；实现缝、现有 feature flag 和状态真相通过 CodeGraph/源码研究收敛。

## Functional requirements

- 保持所有外部合同和已冻结运行时不变量。
- 迁移必须通过 server-side scenario feature flag 回滚到旧路径，客户端 voice_mode 不能绕过。
- 不引入真实收费 Provider，不拆微服务，不改变数据库 schema。
- Golden Conversation inventory 必须是 versioned、machine-readable，包含合同 ID、稳定预期与
  自动化 evidence 引用。
- `ConnectionState` 必须集中连接 phase/health/reconnect/epoch/reason；epoch 只能单调递增。
- `TurnState` 必须集中 request/response/stream id、interruption/timeout/completion，并拒绝非法转换。
- `GroundingState` 必须表达 frozen policy reference、decision/mode/diagnostics；Gate 2 不新增缓存。
- `EvidenceState` 必须以 evidence key 去重 transcript/audio/score/flush ack 元数据，不产生第二个
  score/report writer。
- `RealtimeSessionEngine` 必须只依赖中立 DTO/Protocol，通过 `ScenarioTurnHooks` 组合 Presentation。
- 旧 snapshot 缺少 Engine payload 时必须兼容恢复；新 payload 只能是 additive key。
- engine façade 必须实现 SessionManager 所需的 `handle_connection`、`send_message`、`close`、
  `sync_lifecycle_transition`、`get_runtime_diagnostics` 稳定表面。

## State transition invariants

- Connection: `disconnected -> connecting -> connected|degraded -> closing -> disconnected`；
  reconnect 从持久 epoch + 1 开始，旧 snapshot 至少归一为 epoch 1。
- Turn: `idle|completed|interrupted|timed_out -> receiving -> generating -> streaming -> completed`；
  active turn 重入、旧 request id、completion 后追加 response id 都 fail closed。
- Grounding: `empty|ready|blocked|degraded -> preparing -> ready|blocked|degraded`；每次 decision id
  单调替换，结果保留可脱敏 diagnostics。
- Evidence: 同一 `evidence_key` 重放不增加 count；ack 只能确认 pending flush；score snapshot 同一
  id 重放幂等，不同 payload 冲突失败。

## Rollout and rollback

- `true`：plugin 选择 `PresentationRealtimeEngineHandler`；生产对象不是
  `StepFunRealtimeSharedHandler` 子类。
- `false`：plugin 选择 `LegacyPresentationStepFunRealtimeHandler`；外部路由/协议不变。
- 同一 session 只实例化一个 handler；禁止 shadow persistence、双评分、双报告。
- 诊断必须暴露 selected runtime、flag、Engine state version 和 rollback path，但不暴露 token、
  raw prompt 或敏感 transcript。

## Acceptance Criteria

- [x] Golden Conversation Contract inventory 覆盖鉴权、事件序列、音频、失败、snapshot、epoch、
      transcript/evidence/score/report 幂等与 record-only observation。
- [x] 显式 ConnectionState、TurnState、GroundingState、EvidenceState 有可执行状态转换测试。
- [x] RealtimeSessionEngine shell 可由 Presentation Scenario Hooks 组合，不读取 Sales 私有状态。
- [x] Presentation 新旧路径 differential test 对外行为一致。
- [x] feature flag 默认启用 Engine，显式关闭切回兼容路径；切换和回滚均有测试与诊断证据。
- [x] Presentation 生产入口不再构造 Sales runtime 或通过 Sales shared handler 继承后关闭能力。
- [x] pre-Gate-2 snapshot 可恢复；Engine snapshot round-trip 保持 epoch、turn、grounding 和 evidence
      idempotency，且不改变现有 snapshot keys 的语义。
- [x] Sales 默认构造、重连和关键 turn 测试无回归。
- [x] architecture policy 不新增边、不扩大 SCC；如临时边消失，同提交删除 stale exception。

## Definition of Done

- 实现、测试、feature flag、诊断、文档、ADR/路线图和 Trellis 状态一致。
- `critical-quality-gate.sh` 所有非真实 Provider phase 自然 exit 0。
- CodeGraph impact/affected、独立 Trellis check、逻辑提交、task archive 和 journal 完成。
- 工作区只剩已识别的并行 Readiness 用户改动。

## Out of Scope

- Gate 3 的通用 `RealtimeProviderPort`、StepFun codec 重构和 Grounding 缓存收口。
- Gate 4–6 的领域所有权、projection/locality、ORM 拆分和兼容层清理。
- 启用新生产 Provider、真实收费 API、协议或数据库迁移。

## Technical Notes

- Authority: `docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`。
- Decision: `docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`。
- Roadmap: `docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md`。
- Current truth: `research/current-presentation-runtime-and-state.md`。
- Decision/options: `research/golden-contract-and-migration-options.md`。
- Technical approach: composition façade + explicit Engine + compatibility runtime adapter；默认新路径，
  flag 关闭回滚；Gate 3 再完成 Provider/Grounding 中立化。
