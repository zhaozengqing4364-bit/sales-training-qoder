# StepAudio 2.5 Realtime 生产验证（脱敏）

日期：2026-07-12 UTC

## 配置安全

- `backend/.env`：mode `0600`，Git ignored。
- credential：已配置、非 placeholder；未进入 tracked diff、测试 fixture、命令参数或本文件。
- endpoint/model：`wss://api.stepfun.com/v1/realtime` / `stepaudio-2.5-realtime`。
- 音频：PCM16、24kHz；中文转录；client-driven `manual_commit`。
- 模块路径：Presentation Engine、Provider Port、Grounding Module 默认开启，均保留 false 回滚。

## 自动化结果

- StepFun prereq：`ready`，0 errors，0 warnings，credential 只显示 `<configured>`。
- 聚焦单元/契约：565 passed；覆盖 prereq、transport、Provider、codec、Sales handler、
  upstream、Presentation Golden 与 runtime selection。
- Ruff：通过。
- mypy：677 source files，0 issues。
- architecture dependency guard：通过。
- secret hygiene scan：通过。

## 真实 Provider 结果

- Gate：`CRITICAL_GATE_MODE=newcomer-real-provider`。
- 状态：`passed`。
- 分类：`executed`。
- Provider/model：`stepfun_realtime` / `stepaudio-2.5-realtime`。
- 已验证：官方上游鉴权与 WebSocket、会话更新、真实音频转录、模型响应、会话结束、Journey
  outcome、管理端记录投影。
- 证据：`.sisyphus/evidence/newcomer-real-provider-gate.json`（ignored、脱敏）。

## 残余边界

- 本次未部署远端环境；目标生产环境仍需由 Secret Manager 注入同名变量。
- 未创建自定义音色；真实门禁已证明当前官方音色配置可用。
