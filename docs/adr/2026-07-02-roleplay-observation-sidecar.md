# ADR-2026-07-02：实时角色一致性旁路观测

## 背景

StepAudio 2.5 realtime 对练需要保持语音链路流畅。角色一致性检查仍需留痕，供后台复盘和人工复核，但不能在 learner 实时会话中阻断、重生成或弹窗。

## 决策

新增 `roleplay_observation_v1` 旁路观测链路，语义固定为 `record_only`（兼容旧称 `observe_only`）：

- StepFun turn transcript capture 只采集安全上下文和最终文本，不采集 thinking、secret、上游密钥或完整内部 payload。
- sales websocket 仅在 `voice_policy_snapshot.external_binding.owner="sales_trainer"` 的 session 上注入 observation sink。
- sink 使用 fire-and-forget 方式运行，独立 DB session 写入 `sales_trainer_roleplay_observations`。
- observation policy 当前冻结在 `voice_policy_snapshot.roleplay_observation_policy`；缺失或非法时回退到 bundled default：`heuristic.enabled=true`、`llm.enabled=false`。
- sink 同步写 `source="heuristic"` observation；若 policy 开启 `llm.enabled=true`，再后台执行 `evaluate_background()` 并写入独立 `source="llm_evaluator"` observation。
- `main_chain_effect="none"`，任何观测、评估、写库或后台读取失败都不得改变 WebSocket 主链路状态。
- 2026-07-03 起，StepFun roleplay compliance 的全局治理语义进一步冻结为 `record_only`，详见 `docs/adr/2026-07-03-roleplay-realtime-record-only.md`：current turn 的 `main_chain_effect` 必须保持 `"none"`；next-turn soft steering 只允许作为非阻断、可审计的下一轮提示建议；旧同步 cancel/regenerate/repair audio 动作正式退役。
- 不得通过隐藏环境变量、未登记 feature flag 或 policy 私有字段恢复阻断、取消当前响应、同步重生成或音频修复。若未来需要恢复阻断/中断/同步修复能力，必须另起 ADR，不能把本 sidecar ADR 当作授权。
- `sales_trainer_roleplay_observations` 是 append-only sidecar，apply migration 只建表/索引/去重约束，不回填历史 turn；rollback migration 只删除 sidecar 表，不改写 `practice_sessions`、TrainingJourney、runtime outcome 或 operation log。
- observation endpoint 必须先通过统一训练记录权限和 department 对象级 scope 确认 `session_id` 可见，再读取 observation；无范围权限时返回 not found 语义，避免泄露 session 存在性。
- 密钥和原始 payload 禁止进入 DB、日志和 API：不得保存 StepFun API key、Authorization/Cookie/JWT、LLM provider key、thinking、完整 prompt、完整上游 request/response；日志只记录 `trace_id/session_id/turn_index/source/error_code` 等脱敏诊断。

## 备选方案

- 同步阻断或重生成：能即时压制角色漂移，但会破坏 StepAudio 2.5 realtime 流畅性，本轮拒绝。
- 只写 runtime snapshot：改动小，但不利于后台按 session/turn 查询和权限隔离。
- 异步队列：更适合高吞吐，但当前仓库没有统一队列可靠投递契约，本轮采用最小独立 DB session sidecar。

## 取舍

选择 sidecar 牺牲了实时纠偏能力，换取稳定的主链路和可审计的后台复盘。heuristic 只产生风险 signal，不给通过/失败结论。

## 影响

- 运行时：只增加 capture sink，不改变 StepFun upstream、turn coordination 或 roleplay blocking policy。
- 数据：新增 append-only observation 行，按 `session_id/source_record_id/turn_index/source/payload_hash` 去重。
- 权限：后台 observation endpoint 复用训练记录查看权限和 department 对象级 scope。
- 安全：secret hygiene 由 capture/evaluator 脱敏、service warning-only 日志和 secret scan 门禁共同约束；真实 provider key 只来自环境变量/密钥管理，不进入 observation 表。
- 前端：训练记录详情页从 admin observation endpoint 读取，失败显示独立错误卡，不影响记录详情。
- 可观测性：sink 和 service 失败只 warning，带 `trace_id/session_id/turn_index`。

## 回滚

- 关闭方式：停止在 sales websocket router 中注入 `transcript_capture_sink`。
- 数据回滚：保留已写 observation 行作为历史审计；如需隐藏，只移除后台读取入口，不需要修改 realtime session。
- 行为回滚：前端可继续依赖训练记录 runtime snapshot fallback；主链路不受 observation 表影响。
