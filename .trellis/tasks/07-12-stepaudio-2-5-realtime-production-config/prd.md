# StepAudio 2.5 Realtime 生产配置

## Goal

将用户提供的 StepFun API credential 安全配置到本机生产运行配置，使 Sales 与 Presentation 的
`stepfun_realtime` 路径使用官方 `stepaudio-2.5-realtime` WebSocket Provider，并通过现有真实
Provider gate 证明鉴权、建连、会话、Journey outcome 与管理端记录链路可用。

## What I already know

- 用户明确指定 StepAudio 2.5 Realtime，并提供了新的 API credential。
- credential 属敏感信息：只进入 Git ignored 的 `backend/.env`，不得进入 task、日志、测试 fixture、
  shell history、Git diff 或最终回复。
- `backend/.env` 已被 `.gitignore` 排除且权限为 `0600`。
- 官方生产地址为 `wss://api.stepfun.com/v1/realtime`，模型参数为
  `stepaudio-2.5-realtime`，鉴权为 `Authorization: Bearer STEP_API_KEY`。
- 工程已有 `RealtimeProviderPort`、`StepFunRealtimeProvider`、codec、timeout/reconnect/backpressure、
  Grounding、rollout/rollback、Golden contract 和专用真实 Provider gate；不需要新增第二套 Provider。
- 当前 StepFun key 是 placeholder，真实 Provider gate 默认 opt-in 关闭。

## Requirements

- 将 credential 写入 `backend/.env` 的 `STEPFUN_API_KEY`，保持权限 `0600` 且 Git 不跟踪。
- 固定 `STEPFUN_REALTIME_URL=wss://api.stepfun.com/v1/realtime`。
- 固定 `STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime`，值后不得带 inline comment。
- 保持 `DEFAULT_VOICE_MODE=stepfun_realtime`、PCM16、24kHz 和中文转录配置。
- 固定 `STEPFUN_REALTIME_TURN_DETECTION_MODE=manual_commit`，与前端 `audio_end` 提交协议一致；
  `policy` 仅作为回滚到 Profile Server VAD 的路径。
- 默认启用 Provider Port、Grounding Module、Presentation Engine；保留三个 false rollback path。
- 保持自动恢复、有界 cache、timeout、rate/backpressure 与敏感信息脱敏机制。
- 使用现有 prereq/contract/codec 测试做静态验证，再运行一次真实 StepFun provider gate。
- 真实验证证据只能记录 provider/model/状态/分类，不记录 credential、Authorization header 或带敏感
  query 的 URL。

## Acceptance Criteria

- [x] `backend/.env` 权限为 `0600` 且 `git check-ignore` 确认被忽略。
- [x] StepFun credential 存在且非 placeholder；任何输出和 tracked diff 都不包含 credential。
- [x] endpoint、model、format、sample rate、rollout 与 recovery 配置通过安全诊断。
- [x] StepFun prereq、transport、Provider contract、codec 和 realtime selection 聚焦测试全绿。
- [x] 真实 Provider gate 到达官方上游并通过，证据为脱敏 `passed/executed`。
- [x] Ruff/mypy/architecture guard 通过，用户原有 readiness 改动保持未纳入本任务。
- [ ] 配置/验证证据提交、Trellis 任务归档；credential 不提交。

## Definition of Done

- 配置安全、可回滚、可观测；真实上游验证有脱敏证据。
- 不新增依赖、数据库 migration、协议分支或第二套 Provider。
- 文档只记录非敏感配置合同和验证结果。

## Out of Scope

- 部署到远端生产环境或修改云平台 Secret Manager。
- 购买额度、调整 StepFun 账户权限或创建自定义音色。
- 修改用户界面、Prompt、评分规则、数据库或 DeepSeek 配置。

## Decision (ADR-lite)

**Context**：已有完整 StepFun Port 与真实门禁，问题是 credential/环境配置仍为 placeholder。

**Decision**：复用现有 Provider，credential 仅进入 ignored `backend/.env`；tracked 文件只补充必要的
生产配置合同与脱敏验证证据。使用现有 opt-in real-provider gate 做一次真实验证。

**Consequences**：本机运行可使用真实 StepAudio 2.5 Realtime；远端部署仍需在目标环境的 Secret
Manager 注入同名变量。credential 一旦轮换，只需更新 secret，不改代码。

## Research References

- `research/stepfun-official-production-contract.md`
