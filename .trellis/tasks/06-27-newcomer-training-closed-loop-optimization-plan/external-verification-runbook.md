# 外部验证与生产回填 Runbook

> 更新时间：2026-07-02 11:20 CST
>
> 用途：当真实第三方凭证或产品/运维决策具备后，按本文执行剩余外部验证。本文不授权生产数据修改；生产回填必须另有批准、dry-run 证据和回滚方案。

## 0. 执行前通用检查

1. 工作树不得混入未解释的生产密钥、生产数据导出或破坏性迁移。
2. 先运行本地 deterministic gate，确认基础闭环未回退：

```bash
PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 bash scripts/critical-quality-gate.sh
```

3. 确认基础证据存在且是 deterministic full gate 通过日志。当前仓库最近一次通过证据为 `2026-07-01 11:52 CST`：

```bash
test -f .sisyphus/evidence/task-9-quality-gate.txt
grep -q "Critical quality gate passed" .sisyphus/evidence/task-9-quality-gate.txt
! grep -q "\[STEPFUN_UPSTREAM_REJECTED\]\\|1 failed\\|Newcomer realtime real provider gate" .sisyphus/evidence/task-9-quality-gate.txt
```

4. 若运行真实 provider gate，必须确认凭证不是占位值：
   - `STEPFUN_API_KEY` 不得为空、`phase4-local-e2e`、`replace-with-stepfun-api-key`。
   - `LLM_API_KEY` / `OPENAI_API_KEY` 不得为空、`change-me`、`test-key`、`local-test-key`、`replace-with-llm-api-key`、`replace-with-openai-api-key`。

5. 运行 StepFun Realtime 前先执行本地预检。预检不会连接 StepFun，也不会输出 key；它只校验 key 是否缺失/占位、Realtime URL 是否为 `wss://`、URL 不含 userinfo 或敏感 query、最终 endpoint 只保留非敏感 query 和 model，以及当前 model 是否在仓库 allowlist 内：

```bash
python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env
```

若输出 `warnings=["model_not_in_public_realtime_docs_confirm_console_authorization"]`，表示当前模型需要在 StepFun 控制台确认已授权；这不是本地 deterministic gate 失败，但不能把真实 provider 计作通过。当前任务默认 `stepaudio-2.5-realtime` 是公开 Realtime model 且已纳入仓库 allowlist；真实 provider gate 仍必须由 StepFun 上游实际通过。

## 1. Realtime StepFun 真实 provider 验证

### 目标

证明新人训练 realtime roleplay 不只在 local deterministic provider 下可用，而是在真实 StepFun provider 下完成：

- learner 从 active path revision Journey 发起 realtime start。
- `/ws/sales` 完成真实 provider session lifecycle。
- Journey outcome 回流。
- admin training-record detail 回放 external binding。

### 必需凭证

- `STEPFUN_API_KEY`
- 可选：`STEPFUN_REALTIME_URL`
  - 开放平台默认：`wss://api.stepfun.com/v1/realtime`
  - Step Plan 订阅：需先在控制台或官方支持确认 Realtime 专用路径，再配置为对应 `wss://api.stepfun.com/step_plan/v1/realtime` 形态的 URL。
- 可选：`STEPFUN_REALTIME_MODEL`
- 可选：`STEPFUN_REALTIME_VOICE`

### 角色分工

- Owner：StepFun 控制台或套餐管理员，负责确认账号、key、Realtime 权限、model 授权和 Step Plan URL。
- Approver：平台/运维负责人，批准把真实 provider gate 作为发布证据。
- Executor：后端负责人，执行预检、强制门禁和证据回写。
- CI secret 管理人：维护 GitHub Actions / 部署环境中的 `STEPFUN_API_KEY`，并确保旧 key 已停用或移除。

### 本地强制执行命令

```bash
CRITICAL_GATE_MODE=newcomer-real-provider \
NEWCOMER_REAL_PROVIDER_NAME=stepfun_realtime \
NEWCOMER_REAL_PROVIDER_REQUIRED=1 \
STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime \
STEPFUN_API_KEY=... \
bash scripts/critical-quality-gate.sh
```

如果该 key 属于 Step Plan 订阅，需先确认 Realtime 专用路径；若控制台/官方支持确认路径为 `/step_plan/v1/realtime`，再传入：

```bash
STEPFUN_REALTIME_URL=wss://api.stepfun.com/step_plan/v1/realtime
```

### 2026-06-28 17:08 CST 复验结果

已按用户提供的本地测试凭证写入忽略文件 `backend/.env` 并复跑强制门禁；仓库受 Git 跟踪文件未写入明文密钥。

执行命令：

```bash
set -a; . backend/.env; set +a
CRITICAL_GATE_MODE=newcomer-real-provider \
NEWCOMER_REAL_PROVIDER_NAME=stepfun_realtime \
NEWCOMER_REAL_PROVIDER_REQUIRED=1 \
bash scripts/critical-quality-gate.sh
```

结果：

- exit code：`1`。
- evidence：`.sisyphus/evidence/newcomer-real-provider-gate.json`。
- `status="failed"`。
- `classification="upstream_auth_rejected"`。
- `provider="stepfun_realtime"`。
- `model="step-audio-2.3"`。
- `realtime_url_configured=true`。
- Playwright trace 中后端 typed error 为 `[STEPFUN_UPSTREAM_REJECTED]`，StepFun 在 WebSocket 握手阶段返回 HTTP 401。

主 Agent 与只读子代理复核结论一致：

- URL 来源：`STEPFUN_REALTIME_URL`，默认 `wss://api.stepfun.com/v1/realtime`。
- model 来源：runtime policy/profile，当前为 `step-audio-2.3`。
- auth 来源：`STEPFUN_API_KEY`，由 `StepFunTransport.connect()` 作为 `Authorization: Bearer <redacted>` 发送。
- 当前失败发生在 `session.update` payload 发送前，因此不是 Journey、权限、active path、前端入口或消息 payload 的闭环问题。
- 当前最可能原因是 StepFun key 无效、账号未开通 Realtime、key 属于 Step Plan 但未使用 `/step_plan/v1/realtime` 路径，或该 key 未授权给当前 realtime model。

为排除单一模型名导致误判，已额外做无音频 WebSocket 握手矩阵探测；`wss://api.stepfun.com/v1/realtime` 下 `step-audio-2.3`、`stepaudio-2.5-realtime`、`step-1o-audio`、`step-audio-2`、`step-audio-2-mini`、`step-audio-r1.1` 均返回 HTTP 401。该结果说明问题不是只由 `step-audio-2.3` 一个模型名触发。

2026-06-29 01:24 CST 复核 StepFun 官方 Realtime API 文档：开放平台 Realtime WebSocket 地址为 `wss://api.stepfun.com/v1/realtime`，鉴权方式为 `Authorization: Bearer $STEPFUN_API_KEY`。Step Plan 文档明确专用 base URL 与开放平台不同，但 Realtime 页面未直接列出 Step Plan WebSocket URL；`wss://api.stepfun.com/step_plan/v1/realtime` 只作为控制台/官方支持确认后的候选覆盖值。当前官方文档公开列出的 Realtime model 包含 `stepaudio-2.5-realtime`、`step-1o-audio`、`step-audio-2`、`step-audio-2-mini`、`step-audio-r1.1`；`step-audio-2.3` 是本任务用户指定模型，因此如果控制台未展示或未授权该模型，应以控制台授权范围为准，或临时用官方列出的可用模型复跑 gate 以区分 model 授权与 key 授权问题。官方文档链接：https://platform.stepfun.com/docs/zh/api-reference/realtime/chat

同次补强已将 `StepFunTransport` 的 endpoint 构造改为结构化追加/替换 `model` query，避免 `STEPFUN_REALTIME_URL` 已带 query 时生成重复 `?`；聚焦验证 `tests/unit/test_stepfun_transport.py`、`test_stepfun_realtime_handler.py`、`test_stepfun_payload_snapshots.py` 共 155 passed，并已进入 2026-06-29 01:45 full critical gate 复验通过。

2026-06-29 01:40 CST 新增本地预检脚本 `scripts/check_stepfun_realtime_prereqs.py`，用于在真实 provider gate 前输出不含密钥的 JSON 诊断：

- `api_key_configured` / `api_key_redacted`：只显示 `<configured>` 或 `<missing>`。
- `endpoint_without_secret`：展示最终 WebSocket endpoint 和 model query，不包含 Authorization header。
- `model_in_public_realtime_docs`：标记当前 model 是否在公开 Realtime 文档列表内。
- `model_in_local_allowlist`：标记当前 model 是否被本仓库 runtime policy / seed / admin 配置允许；它不等同于 StepFun 公开文档支持，`step-audio-2.3` 当前属于用户指定的本地 allowlist 模型，仍需控制台确认 Realtime 授权。
- `step_plan_url`：标记是否使用 `/step_plan/v1/realtime`。
- `errors`：缺 key、占位 key、非 `wss://` URL、URL 无 host 等阻塞项。
- `warnings`：未知或未纳入当前 allowlist 的模型会提示控制台授权确认；本任务当前默认 `step-audio-2.3` 已纳入预检 allowlist，但真实 provider gate 仍需 StepFun 控制台确认 key、账号和 model 的 Realtime 授权。

同次移除了 `StepFunRealtimePolicyMixin` 中残留的旧 `_connect_upstream()` 直连实现，避免未来继承顺序变动绕过 `StepFunTransport` 的 endpoint 构造、401 分类和 session.update 契约。当前上游连接唯一入口由 `StepFunRealtimeConnectionMixin` 委托 `StepFunTransport`。

2026-06-28 17:35 CST 已补齐授权放开后的 `session.update` 固定字段：`backend/src/training_runtime/stepfun_transport.py` 统一输出 `modalities=["text","audio"]`，并通过 `backend/tests/unit/test_stepfun_transport.py`、`backend/tests/unit/test_stepfun_realtime_handler.py`、`backend/tests/unit/test_stepfun_payload_snapshots.py` 固定 payload 形状。该补强不改变当前 401 分类；401 仍发生在发送 `session.update` 之前。

2026-06-29 02:43 CST 按用户明确要求将测试凭证写入 gitignore 的本地 `backend/.env` 后复跑：

- 预检命令 `python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env` 返回 `status="ready"`、`api_key_redacted="<configured>"`、`model="step-audio-2.3"`、`endpoint_without_secret="wss://api.stepfun.com/v1/realtime?model=step-audio-2.3"`。
- 强制门禁 `set -a; . backend/.env; set +a; CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh` 仍执行到 StepFun 上游后返回 HTTP 401 `[STEPFUN_UPSTREAM_REJECTED]`。
- 结论：本地 env 已生效、模型已是 `step-audio-2.3`、密钥未写入受 Git 跟踪文件；剩余失败仍是 StepFun key/账号/model Realtime 授权或 Step Plan 专用路径确认问题。

2026-06-29 03:02 CST 进一步使用同一测试凭证和候选 Step Plan URL 复跑：

- 预检命令 `set -a; . backend/.env; set +a; STEPFUN_REALTIME_URL=wss://api.stepfun.com/step_plan/v1/realtime python3 scripts/check_stepfun_realtime_prereqs.py` 返回 `status="ready"`、`step_plan_url=true`、`model="step-audio-2.3"`，且 endpoint 不含密钥。
- 强制门禁 `set -a; . backend/.env; set +a; STEPFUN_REALTIME_URL=wss://api.stepfun.com/step_plan/v1/realtime CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh` 仍到达 StepFun 上游后返回 HTTP 401 `[STEPFUN_UPSTREAM_REJECTED]`。
- 结论：开放平台 URL 与候选 Step Plan URL 均被同一测试 key/模型组合拒绝；剩余问题更集中在 StepFun key、账号、套餐或 `step-audio-2.3` Realtime 授权范围，而不是本地 URL 拼接或模型默认值未生效。

2026-06-29 06:58 CST 使用当前 gitignored `backend/.env` 复跑：

- 预检命令 `python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env` 返回 `status="ready"`、`model="step-audio-2.3"`、endpoint 不含密钥。
- AI Coach 真实 provider gate 已于 2026-06-29 06:53 CST 通过，`.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json` 为 `status="passed"`、`classification="executed"`、`model="deepseek-chat"`、`provider_response.fallback_used=false`。
- StepFun Realtime 强制门禁再次执行 seed、active path、sales websocket，并到达 StepFun 上游；结果仍为 HTTP 401 `[STEPFUN_UPSTREAM_REJECTED]`，`.sisyphus/evidence/newcomer-real-provider-gate.json` 为 `status="failed"`、`classification="upstream_auth_rejected"`、`model="step-audio-2.3"`。
- 结论：本地 key/model/env 已被真实门禁使用；StepFun 剩余问题仍在 key、账号、套餐、Realtime 权限或 model 授权侧。

2026-06-29 07:45/07:46 CST 使用当前 gitignored `backend/.env` 再次复跑：

- 预检命令 `python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env` 返回 `status="ready"`、`api_key_redacted="<configured>"`、`model="step-audio-2.3"`、endpoint 不含密钥。
- 开放平台 URL `wss://api.stepfun.com/v1/realtime` 的强制门禁执行 seed、active path、sales websocket，并到达 StepFun 上游；结果仍为 HTTP 401 `[STEPFUN_UPSTREAM_REJECTED]`。
- 候选 Step Plan URL `wss://api.stepfun.com/step_plan/v1/realtime` 的强制门禁同样到达 StepFun 上游；结果仍为 HTTP 401 `[STEPFUN_UPSTREAM_REJECTED]`。
- 结论：本地 env、模型、active path、runtime binding、权限 gate 和 WS 链路都已被真实门禁实际使用；剩余阻塞不应再归因为“没写入 key”或“只用了错误 URL”。

2026-06-29 08:25 CST deterministic full gate 复跑通过：

- `backend/.env` 仍为 gitignored 本地文件，`STEPFUN_REALTIME_MODEL=step-audio-2.3` 已生效，测试 key 未进入受 Git 跟踪文件。
- full gate 中 StepFun prereq / transport / realtime handler / payload snapshot 单测已进入后端默认测试集；后端 pytest 子进程会清空 E2E provider 环境，避免 local E2E 配置让 StepFun 单测误走 skip 分支。
- 该 full gate 不替代真实 provider 通过判定；真实 StepFun provider 仍需控制台授权或更换可用 Realtime key 后复跑本节强制门禁。

2026-07-01 11:52 CST deterministic full gate 再次复跑通过：

- 命令：`PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 bash scripts/critical-quality-gate.sh`。
- evidence：`.sisyphus/evidence/task-9-quality-gate.txt`。
- 结果：`Critical quality gate passed`。
- 覆盖：secret scan 461 files、ruff、web typecheck/lint、Vitest 28 files / 258 tests、Playwright smoke 9 passed、Newcomer E2E 11 passed / 1 skipped、presentation Phase 4 E2E 2 passed、sales Phase 4 E2E 1 passed、backend newcomer coverage 42 passed / 48.05%、backend newcomer mypy 8 source files no issues、backend full 501 passed、backend smoke regression 58 passed。
- 该 full gate 覆盖 2026-07-01 `/sales-trainer/units` TrainingJourney 列表过滤和轻量列表响应补强；仍不替代真实 StepFun provider 通过判定。

2026-07-02 10:23 CST 按用户最新提供的 StepFun 测试 key 和指定模型 `step-audio-2.3` 复跑：

- 本地配置：密钥只写入 gitignored `backend/.env`，文件权限保持 `0600`；受 Git 跟踪文件未写入明文密钥。
- 预检命令 `python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env` 返回 `status="ready"`、`api_key_redacted="<configured>"`、`model="step-audio-2.3"`、`realtime_url="wss://api.stepfun.com/v1/realtime"`、`endpoint_without_secret="wss://api.stepfun.com/v1/realtime?model=step-audio-2.3"`，仍提示 `model_not_in_public_realtime_docs_confirm_console_authorization`。
- 第一次强制门禁未使用 `PLAYWRIGHT_SKIP_BROWSER_INSTALL=1`，阻塞在 Playwright Chromium 安装步骤，不能作为 provider 结果。
- 第二次强制门禁 `set -a; . backend/.env; set +a; PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh` 执行到本地 smoke、seed、active path 和 `/ws/sales`，真实 StepFun WebSocket 握手返回 HTTP 404，前端 typed error 为 `[STEPFUN_UPSTREAM_REJECTED]`，trace_id=`54411726d0cf753853f478df4848efde`。
- evidence：`.sisyphus/evidence/newcomer-real-provider-gate.json` 为 `status="failed"`、`mode="newcomer-real-provider"`、`required=true`、`provider="stepfun_realtime"`、`model="step-audio-2.3"`、`classification="upstream_rejected"`；Playwright 失败证据见 `.sisyphus/evidence/task-9-newcomer-real-provider-gate.txt`。
- 结论：当前 key 已被本地真实 provider gate 使用且到达 StepFun 上游；失败已从历史 401 变为 404，更像 Realtime URL 路径、Step Plan 专用路径或 `step-audio-2.3` 模型在该账号下未开放，而不是 active path、Journey、权限、前端入口或本地 key 未生效。
- 同次安全补强：`scripts/check_stepfun_realtime_prereqs.py` 现在会阻断 `STEPFUN_REALTIME_URL` 中的 userinfo 和敏感 query，并在 `realtime_url` / `endpoint_without_secret` 输出中剔除敏感值，避免预检证据二次泄漏。

2026-07-02 11:08 CST 按用户最新要求切换为公开 Realtime model `stepaudio-2.5-realtime` 后复跑：

- 本地配置：`backend/.env` 已更新为 `STEPFUN_REALTIME_MODEL=stepaudio-2.5-realtime`，仍为 gitignored 文件，权限保持 `0600`；受 Git 跟踪文件未写入明文密钥。
- 预检命令 `python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env` 返回 `status="ready"`、`warnings=[]`、`api_key_redacted="<configured>"`、`model="stepaudio-2.5-realtime"`、`model_in_public_realtime_docs=true`、`endpoint_without_secret="wss://api.stepfun.com/v1/realtime?model=stepaudio-2.5-realtime"`。
- 真实 provider gate `PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh` 已完成 WebSocket handshake，并进入 StepFun 会话内错误；不再是 HTTP 401/404 握手拒绝。
- evidence：`.sisyphus/evidence/newcomer-real-provider-gate.json` 为 `status="failed"`、`classification="upstream_api_error"`、`http_status=null`、`provider="stepfun_realtime"`、`model="stepaudio-2.5-realtime"`；Playwright 失败证据中上游错误为 `[STEPFUN_API_ERROR] invalid audio, check your audio format`，trace_id=`f374c23f52ca1ab0987866ef9f4cf0ef`。
- 结论：key、URL 和公开模型已经可完成上游握手；剩余问题从“地址/模型授权”推进为“StepFun 对当前 E2E 测试音频帧、提交格式或 commit 时机判定为 invalid audio”。下一步应对照 StepFun Realtime 音频格式要求检查采样率、编码、base64/PCM 帧、输入事件顺序和 `input_audio_buffer.commit` 策略。

### CI 执行方式

在 `.github/workflows/release-truth-gate.yml` 使用 `workflow_dispatch`：

- 设置 secret：`STEPFUN_API_KEY`。
- 勾选或传入 `require_real_provider=true`。
- 不要启用 `allow_credential_skip`，除非本次明确只做凭证缺失分类验证。

### 通过判定

必须同时满足：

- 命令退出码为 `0`。
- `.sisyphus/evidence/newcomer-real-provider-gate.json` 存在。
- JSON 字段：
  - `status="passed"`
  - `classification="executed"`
  - `required=true`
  - `provider="stepfun_realtime"`
- `.sisyphus/evidence/task-9-newcomer-real-provider-gate.txt` 中包含 newcomer realtime provider gate 的 Playwright 通过记录。

### 不可计作完成的情况

以下只能证明“跳过被记录”，不能证明真实 provider 已执行：

```json
{
  "status": "skipped",
  "classification": "credential_missing"
}
```

只有人工显式设置 `NEWCOMER_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1` 时，缺凭证跳过才允许通过脚本，但仍必须在验收报告中保持“外部凭证待验证”。

### 失败与回滚策略

- 若 gate 仍返回 `[STEPFUN_UPSTREAM_REJECTED]`、HTTP 401 或 HTTP 404，保持 `status="failed"` 和实际 `classification` 记录，不得改写为通过。
- 不得把 local provider deterministic E2E 当成真实 StepFun provider 通过证据。
- 如误配置了 `STEPFUN_REALTIME_URL` / `STEPFUN_REALTIME_MODEL`，先回退到上一次可解释配置，再复跑 `scripts/check_stepfun_realtime_prereqs.py`。
- 如确认 key 被误用或泄漏，先在 StepFun 控制台吊销旧 key，再更新 CI/deploy secret，并复跑本节强制门禁。
- 若业务需要临时关闭真实 provider，只能通过 provider registry / runtime policy 显式禁用，并保留审计记录；不得用前端隐藏入口替代后端 fail-closed。

## 2. AI Coach 真实 LLM provider stream 验证

### 目标

证明 AI Coach 首版必过能力不只在 deterministic stream 下可用，而是在真实 LLM provider 下完成：

- `/newcomer-training/ai-coach/chat/sessions/stream` 无 SSE error。
- 按 `plan_then_wait` 创建可治理会话，再通过 `/messages/stream` 发送学员选择。
- 先证明 `plan_then_wait` 只生成 1 个 `followup_prompt` 且不提前生成 `quiz_card`；再由结构化 learner choice 生成 assistant message 与 governed first-card。
- 冻结 active path/config/prompt snapshot。
- 进入训练记录和可回放详情。

### 必需凭证

- `LLM_API_KEY` 或 `OPENAI_API_KEY`
- 可选：`LLM_PROVIDER`
- 可选：`LLM_BASE_URL`
- 可选：`LLM_MODEL`

### 本地强制执行命令

```bash
CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider \
NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED=1 \
LLM_PROVIDER=openai \
LLM_BASE_URL=https://api.openai.com/v1 \
LLM_MODEL=gpt-4o-mini \
LLM_API_KEY=... \
bash scripts/critical-quality-gate.sh
```

### 2026-06-29 02:43 CST 复验结果

已按用户提供的本地 DeepSeek 测试凭证写入忽略文件 `backend/.env` 并复跑强制门禁；仓库受 Git 跟踪文件未写入明文密钥。

执行命令：

```bash
set -a; . backend/.env; set +a
CRITICAL_GATE_MODE=newcomer-ai-coach-real-provider \
NEWCOMER_AI_COACH_REAL_PROVIDER_REQUIRED=1 \
bash scripts/critical-quality-gate.sh
```

结果：

- exit code：`0`。
- evidence：`.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json`。
- `status="passed"`。
- `classification="executed"`。
- `provider="openai"`。
- `model="deepseek-chat"`。
- `actual_runtime_audit.llm_runtime.source="model_config"`。
- `actual_runtime_audit.llm_runtime.model_config_id` 非空。
- `provider_response.status="received"`。
- `provider_response.fallback_used=false`。
- 证据 JSON 不含明文 `api_key`。

### CI 执行方式

在 `.github/workflows/release-truth-gate.yml` 使用 `workflow_dispatch`：

- 设置 secret：`LLM_API_KEY` 或 `OPENAI_API_KEY`。
- 勾选或传入 `require_ai_coach_real_provider=true`。
- 不要启用 `allow_ai_coach_credential_skip`，除非本次明确只做凭证缺失分类验证。

### 通过判定

必须同时满足：

- 命令退出码为 `0`。
- `.sisyphus/evidence/newcomer-ai-coach-real-provider-gate.json` 存在。
- JSON 字段：
  - `status="passed"`
  - `classification="executed"`
  - `required=true`
  - `provider` 与后端实际解析出的 runtime audit 一致。
  - `actual_runtime_audit.llm_runtime.provider/model_name/base_url` 存在且不包含密钥。
- `.sisyphus/evidence/task-9-newcomer-ai-coach-real-provider-gate.txt` 中包含 `AI Coach real provider stream creates a governed first-card after learner choice` 通过记录。
- `.sisyphus/evidence/newcomer-ai-coach-real-provider-runtime-audit.json` 中包含后端 operation log 投影出的实际 `llm_runtime`。

### 不可计作完成的情况

以下只能证明“跳过被记录”，不能证明真实 LLM provider 已执行：

```json
{
  "status": "skipped",
  "classification": "credential_missing"
}
```

只有人工显式设置 `NEWCOMER_AI_COACH_REAL_PROVIDER_CREDENTIAL_SKIP_ALLOWED=1` 时，缺凭证跳过才允许通过脚本，但仍必须在验收报告中保持“外部凭证待验证”。

## 3. 学员等级真实枚举与来源确认

### 当前状态

- 代码已经把学员等级纳入 `TrainingJourney`、admin journey list、analytics、training-records 明细筛选和 API DTO。
- 当前权威配置项是 `sales_trainer.learner_level.policy`。
- 默认等级为 `unassigned`；配置缺失、停用或非法时必须 fail-visible 回落，并在 DTO 中暴露 `fallback_applied/fallback_reason`。
- 2026-07-02 代理决策：首版发布继续以 `unassigned` 作为唯一生产安全默认；真实等级枚举只能通过 `sales_trainer.learner_level.policy` 发布，不能由前端或跨域字段硬编码；未发布真实策略前，等级仅用于治理占位、诊断、筛选空态和审计一致性，不驱动生产历史重写。
- 当前仓库没有稳定的 `sales_trainer` 权威用户字段可直接作为新人训练学员等级来源；真实枚举和人工/自动来源仍需产品/运营确认。
- 已知候选来源：`curriculum_practice.LearnerProfile.effective_level` / `admin_overridden_level` 已在课程学习域存在，但它不是本轮新人训练等级真源，不能无确认直接复用。原因：
  - 领域边界不同：该字段服务课程学习画像，不承载新人训练 path revision、module unlock、AI Coach 难度或训练记录审计语义。
  - 枚举治理不同：现有课程学习枚举是固定画像口径，不受 `sales_trainer.learner_level.policy` 发布、回滚和诊断治理。
  - 历史语义不同：用当前课程画像静默回填新人训练历史，会破坏 snapshot-first 回放和训练记录可追溯性。
  - 如产品决定复用，必须先写入映射规则、冲突优先级、回滚方案和历史快照策略，再通过业务规则配置中心发布。

### 角色分工

- Decision owner：产品负责人，确认等级枚举、语义、是否影响解锁/AI Coach/实时对练。
- Data owner：运营或数据治理负责人，确认等级来源、映射规则、人工覆盖优先级和历史快照语义。
- Config publisher：有配置发布权限的管理员，负责发布 `sales_trainer.learner_level.policy`。
- Rollback approver：产品和运维共同确认回滚窗口，避免等级规则回退影响正在进行的 Journey。

### 产品/运营必须确认的问题

1. 首版等级枚举是什么，例如 `new`, `standard`, `needs_coaching`，还是继续只使用 `unassigned`？
2. 等级来源是什么：
   - 人工配置；
   - 组织/岗位/部门规则；
   - 训练阶段和通过率自动计算；
   - `curriculum_practice.LearnerProfile.effective_level` / `admin_overridden_level` 映射；
   - 外部 HR/CRM 字段；
   - 上述方式的优先级组合。
3. 等级是否影响模块可见性、解锁顺序、AI Coach 难度、实时对练场景或只用于筛选分析？
4. 谁可以修改等级规则，是否需要二次确认、审批或发布窗口？
5. 旧学员在新等级发布后是否立即重算，还是只对新 Journey 生效？

### 发布前最低验证

未来确认真实枚举后，应通过业务规则配置中心发布，而不是改前端硬编码。发布前至少执行：

```bash
cd backend
.venv/bin/pytest --no-cov \
  tests/unit/common/test_business_rule_config_service.py \
  tests/unit/test_sales_trainer_training_journey_service.py \
  tests/integration/test_newcomer_training_journey_api.py \
  -q
```

发布后至少验证：

- `/api/v1/admin/sales-trainer/journeys?learner_level=<level_key>` 能精确筛选。
- `/api/v1/admin/sales-trainer/journeys/analytics?learner_level=<level_key>` 的 `filters.learner_level` 回显一致。
- 前端 analytics 页的学员等级筛选项来自后端 summaries，不出现前端私造等级。
- 配置回滚后 Journey DTO 出现预期等级或明确 fallback。
- 如有前端管理入口，确认筛选项来自后端 summaries 或配置响应，不出现前端硬编码枚举。
- 执行一次 full gate；新增等级规则若只影响配置，也必须把配置版本、发布时间和回滚版本写入验收文档。

### 回滚策略

- 优先回滚到上一版 `sales_trainer.learner_level.policy`，而不是改代码或改前端枚举。
- 若上一版不可用，回到默认 `unassigned`，并要求 Journey DTO 暴露 `fallback_applied/fallback_reason`。
- 历史训练记录 snapshot 不改写；只允许新 Journey 或新训练记录按新等级规则投影。
- 回滚后复验 admin Journey list、analytics、training-records detail 和 operation logs 的等级展示与筛选。

### 禁止事项

- 禁止在前端页面写死真实学员等级枚举。
- 禁止把角色权限 scope 当作学员等级。
- 禁止在没有回滚方案时把外部 HR/CRM 字段直接写入训练历史。
- 禁止用最新等级规则静默覆盖历史 snapshot。

## 4. 历史生产数据回填决策与执行门槛

### 当前状态

- 已有只读 dead data diagnostics：`GET /api/v1/admin/newcomer-training/path-config/dead-data-diagnostics`。
- 历史展示已采用 snapshot-first。
- 无法可靠回填的旧数据必须标记：
  - `legacy_snapshot_only=true`
  - `regrade_unavailable=true`
- 当前没有授权的生产写入式回填脚本；不得把只读诊断当成自动修复。
- 2026-07-02 代理决策：本分支不实现也不执行生产 `--apply`；正式生产回填必须另起审批窗口，在已批准 dry-run JSON、备份、影响条数、反向脚本和审计 owner 齐备后再实现显式 apply。当前交付只保留 snapshot-first、legacy 标记、只读诊断和导出。

### 角色分工

- Decision owner：产品负责人，确认哪些历史记录允许回填、哪些只能 legacy 标记。
- Data owner：数据库/数据治理负责人，确认 dry-run、影响条数、备份和反向脚本。
- Executor：后端负责人，在另行批准后实现显式 apply 能力；当前脚本无 `--apply`。
- Auditor：运维或审计负责人，核对执行日志、影响条数和回滚证据。

### 生产回填前必须回答的问题

1. 哪些记录允许回填 `path_revision_id/path_revision_no/module_key`？
2. 哪些记录只能保持 `legacy_snapshot_only=true`？
3. 是否允许对历史 prompt/material/paper refs 写入新 lineage 字段？
4. 回填依据是什么：历史 frozen snapshot、created_at 区间、active revision 时间线，还是人工映射表？
5. 失败记录如何处理：跳过、标记 `regrade_unavailable`、还是人工复核？
6. 回滚方式是什么：备份表、反向脚本、事务批次、还是只追加标记不覆盖原字段？

### 最低 dry-run 要求

任何回填执行前必须先运行只读 dry-run，并输出：

- 总扫描条数。
- 可自动回填条数。
- 需人工复核条数。
- 不可回填且将标记 legacy 的条数。
- 每类样例记录 id。
- 预期写入字段列表。
- 不写入明文密钥、token、手机号等敏感信息。

当前仓库已提供只读导出脚本；该脚本没有 `--apply` 能力，不会写入数据库，默认只输出聚合与受限样例，需排查明细时才加 `--include-issues`：

```bash
cd backend
.venv/bin/python scripts/export_newcomer_dead_data_diagnostics.py \
  --dry-run \
  --limit 1000 \
  --material-scan-limit 1000 \
  --sample-limit 5 \
  --output /tmp/newcomer-backfill-preview.json
python -m json.tool /tmp/newcomer-backfill-preview.json >/dev/null
if rg -i "api[_-]?key|authorization|bearer|token|password|phone|mobile|storage_key|original_filename|file_hash|transcript|system_prompt|scoring_template" /tmp/newcomer-backfill-preview.json; then
  echo "sensitive field leaked into dry-run preview" >&2
  exit 1
fi
```

验收口径：

- `mode=dry_run`。
- `mutates_history=false`。
- `summary.total_scanned_records`、`auto_backfill_records`、`manual_review_records`、`legacy_mark_records` 均存在。
- `scan_scope.material_scan_limit`、`materials_total`、`material_versions_total`、`material_inventory_truncated` 均存在；若 `material_inventory_truncated=true`，本次结果只能作为采样预览，正式审批前需调大 `--material-scan-limit` 或分批导出。
- `sample_record_ids` 按 `auto_backfill`、`manual_review`、`legacy_mark` 输出并受 `--sample-limit` 限制。
- `expected_write_fields` 只列出潜在人工审批字段；`auto_backfill=[]` 表示当前没有授权自动回填字段。
- 上述敏感字段检查无命中；命令退出码为 0。

### 正式执行要求

正式执行必须满足：

1. dry-run 结果经产品/运维确认。
2. 有数据库备份或可执行反向脚本。
3. 有批次大小限制。
4. 记录影响条数。
5. 写入审计日志或任务日志。
6. 执行后重新跑：

```bash
PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 bash scripts/critical-quality-gate.sh
```

### 未来 apply 模板

当前仓库没有生产写入式 apply 能力。若未来获批实现，apply runbook 至少需要包含：

- 输入：已审批的 dry-run JSON 路径、审批单号、目标环境、批次大小、执行窗口。
- 备份：备份表名、备份时间、备份行数、备份校验方式。
- 命令：显式 `--apply`、`--dry-run-file`、`--batch-size`、`--operator`、`--approval-id` 参数；无这些参数时脚本必须拒绝写入。
- 对账：apply 影响条数必须与 dry-run 分类一致；差异必须中止并进入人工复核。
- 抽样验收：按记录类型抽样调用 training-record detail、historical material replay、dead data diagnostics。
- 回滚：反向脚本或备份恢复步骤必须先演练；回滚也要记录影响条数和审计日志。

### 禁止事项

- 禁止直接手工修改生产数据库作为默认方案。
- 禁止用最新 active revision 伪造旧历史记录 lineage。
- 禁止在没有 dry-run 和影响条数的情况下批量写入。
- 禁止把无法回填的数据静默跳过；必须显式标记或输出人工复核清单。

## 5. git 历史疑似 secret/token 处置

### 当前状态

- 当前工作树 secret hygiene scan 已通过；最新 2026-07-01 11:52 full gate 中扫描 `461 files`，2026-07-02 新增 StepFun 预检脚本补强后仍需复跑完整 secret hygiene。
- 本地测试密钥只允许存在于 gitignored `backend/.env`，不得写入受 Git 跟踪文件。
- 安全复核发现 git 历史中存在旧 evidence/JWT/API-key 形态记录。当前工作树干净不能抵消历史泄漏风险。
- 2026-07-02 代理决策：不在本开发分支执行 `git filter-repo`、force-push 或历史清理；把历史中可能出现过的凭证按已暴露处理，优先由凭证 owner 轮换/吊销，再由 repository owner 决定是否清史。当前交付只负责工作树不新增明文 secret、证据脱敏和 runbook 固化。

### 处置原则

1. 若仓库曾共享、推送或被多人拉取，按已泄漏处理。
2. 先轮换相关 API/JWT/第三方 provider 凭证，再考虑清理 git 历史。
3. 清理历史会改变提交 hash，必须由仓库维护者统一窗口执行并通知协作者重新克隆。
4. 不得把真实 token 明文粘贴到 issue、PR、聊天记录或验收文档。

### 角色分工

- Security owner：安全负责人，建立受影响凭证清单并确认旧凭证已吊销或失效。
- Repository owner：仓库维护者，决定是否清史、安排冻结窗口、执行或审批 force-push。
- Credential owner：各 provider / CI / 部署环境负责人，完成旧凭证 revoke、环境切换和 smoke 验证。
- Communication owner：项目维护者，通知协作者、fork/PR 作者、部署者和镜像维护者。

### 受影响凭证清单模板

不得在清单中记录明文 secret。清单只允许记录脱敏引用和状态：

```text
credential_type | system | environment | owner | old_status | rotated_at | revoked_at | smoke_evidence_ref | notes
JWT signing secret | backend auth | prod/staging/dev | <owner> | revoked/invalid/unknown | <time> | <time> | <path-or-ticket> | no plaintext
third-party API key | StepFun/DeepSeek/... | prod/staging/dev | <owner> | revoked/invalid/unknown | <time> | <time> | <path-or-ticket> | no plaintext
CI/CD secret | GitHub Actions/deploy | ci | <owner> | rotated | <time> | <time> | <path-or-ticket> | no plaintext
```

完成轮换必须证明：

- 旧凭证已 revoke/disable，不能只新增新 key。
- 生产、CI、开发环境已切换到新凭证并通过最小 smoke。
- provider 控制台、CI secret 设置或运维工单中有脱敏证据。
- 证据只记录 provider、时间、状态、脱敏引用，不记录明文 secret。

### 清史决策矩阵

| 条件 | 默认决策 | 说明 |
|---|---|---|
| 凭证曾有效且仓库已共享/推送 | 必须先轮换/吊销 | 清史不能替代轮换，只能降低继续误传播风险 |
| 仓库公开、存在 fork、release artifact 或镜像 | 倾向清史并通知协作者 | 同时检查 fork、mirror、CI cache、artifact、package registry |
| 所有疑似凭证已确认无效且仓库未共享 | 可记录风险接受，不清史 | 仍需工作树和历史扫描证据 |
| 清史影响未合并工作或长期分支 | 先冻结窗口和迁移计划 | open PR 需基于新历史重开，旧 clone 作废 |

维护者必须记录决策：`保留历史/清理历史`、原因、影响范围、执行窗口、回滚方案和通知范围。

### 建议复核命令

以下命令只用于本地脱敏复核；输出不得直接贴到公开渠道：

```bash
python3 scripts/check_secret_hygiene.py --report .sisyphus/evidence/task-9-secret-scan-report.json
# 历史 patch 检查可能把旧 secret 打到终端；只允许安全负责人在受控终端执行，
# 输出不得进入 issue、PR、聊天记录、录屏或共享日志。
git log --all -p -- .env.example backend/.env.example evidence .github/workflows scripts/check_secret_hygiene.py
```

若团队已有历史 secret scanner，应优先使用可脱敏报告的工具对 all refs/tags 执行扫描；例如在已安装工具且策略允许时，生成本地脱敏 report，不把明文输出到终端或公开渠道。

如果决定清理历史，建议由维护者在独立维护窗口评估：

```bash
# 示例，不得直接照抄执行；必须先备份并确认替换规则。
git filter-repo --path evidence/task-4-http-tokens.env --invert-paths
```

清史执行前必须：

- 创建 bare mirror 备份，并记录备份位置和校验 hash。
- 冻结 push/merge，暂停自动发布。
- 确认 protected branch、tag、release artifact、CI cache、mirror、fork 的处理策略。
- 列出 open PR、长期分支、stash、本地未推送 worktree 的迁移方式。

清史执行后必须：

- force-push 由仓库维护者在维护窗口执行。
- 所有协作者 fresh clone；未合并工作只能用 patch 方式迁移，禁止从旧历史 merge/rebase/cherry-pick。
- open PR 关闭后基于新历史重开。
- 从 fresh clone 对 all refs/tags 执行历史 secret scan，并确认 CI cache/artifact/mirror 不再传播旧对象。

### 完成判定

历史 secret 风险只有在以下事项都有证据时才可从剩余风险中移除：

- 受影响凭证清单完成，旧凭证已 revoke/disable 或确认从未有效。
- 新凭证已部署到生产、CI、开发环境，并完成最小 smoke。
- 清理策略已由维护者记录决策；如不清史，残余传播风险已接受并写入最终报告。
- 如执行清史：fresh clone 后对 all refs/tags 执行历史 secret scan 通过。
- 协作者、fork、mirror、CI cache、artifact 影响已通知并完成确认。
- 所有证据脱敏保存，未在 issue、PR、聊天或报告中记录明文 secret。
- `python3 scripts/check_secret_hygiene.py --report .sisyphus/evidence/task-9-secret-scan-report.json` 通过。
- `audit-closure-matrix.md` 和 `final-verification-report.md` 更新处置证据。

## 6. 回写验收文档

真实 provider 或生产回填完成后，必须同步更新：

- `audit-closure-matrix.md`
- `final-verification-report.md`
- `execution-plan.md` 的 Completion Audit 记录

更新内容至少包括：

- 执行时间。
- 命令。
- 退出码。
- evidence 文件路径。
- `status/classification`。
- 失败原因或 skipped 原因。
- 生产回填影响条数和回滚证据。
- 学员等级枚举/来源决策和发布/回滚证据。
- git 历史 secret 风险处置证据。

## 7. 剩余外部/人工决策登记

本节用于防止把外部阻塞误写成代码未完成。只有下表中的完成判定都有证据后，才能从 `audit-closure-matrix.md` 和 `final-verification-report.md` 移除对应剩余风险。

| 剩余项 | 当前责任方 | 前置条件 | 复跑/验证入口 | 完成判定 | 回滚/退出策略 |
|---|---|---|---|---|---|
| StepFun Realtime 真实 provider 上游拒绝 | StepFun 控制台管理员 / 平台运维；后端 realtime 负责人 | 当前 key、URL 和 `stepaudio-2.5-realtime` 已完成上游握手；需按 StepFun Realtime 音频格式要求确认测试音频帧、采样率、编码和 commit 策略 | `python3 scripts/check_stepfun_realtime_prereqs.py --env-file backend/.env`；随后执行 `PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 CRITICAL_GATE_MODE=newcomer-real-provider NEWCOMER_REAL_PROVIDER_REQUIRED=1 bash scripts/critical-quality-gate.sh` | `newcomer-real-provider-gate.json` 为 `status="passed"`、`classification="executed"`、`provider="stepfun_realtime"`，Playwright provider gate 通过 | 若仍 `invalid audio`，保持 local provider deterministic gate 为发布保护，不把真实 provider 写成已完成；记录 `classification`、trace_id 和上游错误 |
| 学员等级真实枚举与来源 | 产品 / 运营 / 数据治理负责人 | 明确首版枚举、来源优先级、人工/自动规则、历史 snapshot 语义、发布和回滚流程 | 通过业务规则配置中心发布后运行 §3 的 backend tests，并验证 admin Journey list / analytics / training-records 筛选 | Journey DTO、analytics filters、training record detail 和 operation logs 均出现预期等级，配置回滚后出现预期 fallback | 规则发布异常时回滚 `sales_trainer.learner_level.policy`，不得用前端硬编码或直接覆盖历史 snapshot |
| 历史生产数据回填 apply | 产品 / 运维 / 数据库负责人 | 明确允许回填范围、不可回填标记策略、备份或反向脚本、审批窗口和批次大小 | 先执行 §4 dry-run；审批后另行实现显式 apply 脚本或迁移，并执行 full gate | dry-run 和 apply 都有影响条数、样例、审计日志、回滚证据；历史回放不破坏 snapshot-first | apply 失败时按备份/反向脚本回滚；无法可靠回填的数据只标记 legacy，不静默跳过 |
| git 历史疑似 secret/token | 安全负责人 / 仓库维护者 | 确认历史泄漏影响范围；先轮换可能暴露的 API/JWT/第三方凭证；决定保留历史或清史 | `python3 scripts/check_secret_hygiene.py --report .sisyphus/evidence/task-9-secret-scan-report.json`；必要时在维护窗口执行脱敏历史检查和清理 | 凭证已轮换或确认无效；清史策略已决策并通知协作者；工作树 secret scan 通过；验收文档写入处置证据 | 若清史风险高于收益，允许保留历史但必须完成凭证轮换和风险接受记录；不得继续使用疑似暴露凭证 |
