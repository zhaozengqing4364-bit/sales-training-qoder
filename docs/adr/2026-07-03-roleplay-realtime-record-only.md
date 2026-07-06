# ADR-2026-07-03：StepFun Roleplay Realtime Record-Only 合规策略

## Status

Accepted.

## 背景

StepAudio 2.5 realtime 对练的首要目标是保持 learner 语音链路稳定、可恢复、可审计。此前 Roleplay Contract 治理中曾保留过同步 blocking regenerate 的设想；后续 observation sidecar 已把角色一致性检查移出 WebSocket 主链路，但仍需要明确 StepFun roleplay compliance 的全局行为边界，避免旧 cancel/regenerate/repair audio 路径被隐藏配置重新打开。

## 决策

1. StepFun roleplay compliance 全局固定为 `record_only`。该语义适用于 heuristic evaluator、可选 LLM evaluator、capture sink、observation storage、admin 读取和 analytics 聚合。
2. current turn 的 `main_chain_effect` 必须为 `"none"`。任何 compliance signal 都不得取消当前上游响应、关闭 WebSocket、阻断音频输出、同步重生成回复、repair/re-synthesize audio、修改 `PracticeSession` 状态或改变本轮 learner 可见反馈。
3. next-turn soft steering 允许存在，但只能作为非阻断、可审计的下一轮提示建议。它必须记录 source observation、`session_id`、`turn_index`、`signal_key`、建议摘要、`trace_id` 和是否被下一轮指令编译消费；生成、写库或消费失败都不得升级为阻断。
4. 旧同步 `cancel_current_turn`、`regenerate_current_turn`、`repair_audio` 动作正式退役。它们只能作为历史字段或诊断对象出现，不能作为新运行时动作。
5. 不允许通过隐藏环境变量、未登记 feature flag、私有 policy 字段或 admin 未公开配置恢复阻断、中断、同步重生成或音频修复能力。
6. 若未来产品确需恢复阻断/中断/同步修复，必须另起 ADR，明确状态机、用户体验、错误码、权限、审计、可观测性、回滚、灰度和测试矩阵；不能把本 ADR 或 observation sidecar 解释为授权。

## 备选方案

- 同步 cancel/regenerate/repair audio：能尝试即时压制角色漂移，但会破坏 realtime 音频连续性，且失败时容易造成重复播报、状态错乱和不可审计的用户体验，本轮拒绝。
- 隐藏开关保留阻断能力：便于临时恢复，但会让契约、权限、审计和前端行为分叉，且难以确认生产到底处于 record-only 还是 blocking，本轮拒绝。
- 全部关闭合规检查：最小运行风险，但失去后台复盘、问题定位和后续改进依据，本轮拒绝。
- record-only + next-turn soft steering：采用。当前 turn 保持零主链路影响，下一轮只允许可审计软提示。

## 取舍

该决策牺牲了实时纠偏能力，换取语音链路稳定性、失败可分类和后台可复盘。角色漂移不再被同步阻断，而是进入 observation、analytics、人工复核或后续发布前治理。

next-turn soft steering 只解决轻量方向校正，不承担安全底线或状态修复职责；它失败时系统仍应继续对练并保留诊断。

## 影响

- API 契约：`docs/api-contract/sales-trainer.md` 中 `roleplay_observation_v1` 暴露 `compliance_mode="record_only"` 和 `main_chain_effect="none"`；soft steering 只作为 observation/audit signal。
- 运行时契约：`docs/api-contract/voice-runtime.md` 明确 StepFun roleplay compliance 不能取消、重生成、修复音频或关闭连接。
- 权限：不新增 learner 或 admin 权限；admin 只能读取 observation 和 analytics，不获得实时阻断操作。
- 数据：observation 仍是 append-only sidecar；旧动作字段只可作为历史诊断，不得作为新动作写入。
- 可观测性：soft steering 必须带 `trace_id/session_id/turn_index/source`，消费与否必须可追踪。
- 安全：secret、Authorization、Cookie、JWT、StepFun raw event、完整 prompt 和完整上游 payload 仍不得进入 observation、日志或 API 响应。

## 回滚

关闭 observation sink 或隐藏 admin 读取入口可以停止新增/展示 record-only 证据，但不得恢复旧同步阻断动作。

如未来需要恢复阻断、中断或同步修复，回滚路径不是打开隐藏配置，而是新增 ADR 并配套实现显式状态机、权限、审计、灰度、回滚和测试。
