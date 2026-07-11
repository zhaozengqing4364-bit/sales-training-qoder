# Gate 3 Task 3 实施报告

## 结果

- 原始实现 commit：`ec7067f0 refactor(realtime): route sessions through provider port`
- Review 修复 commit：`fix(realtime): enforce provider rollout and event authority`
- 风险等级：P1（共享 Sales/Presentation realtime 生产 Provider 路径默认切换；保留 server-only
  Legacy 回滚）。
- 严格只完成 Task 3：未实现 Grounding Module/单 cache（Task 4+），未调用真实收费 Provider，未改
  schema、REST、前端或 readiness。
- 用户并行修改
  `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md` 未读取、未修改、未暂存、未提交。

## 本次完成

- `REALTIME_PROVIDER_PORT_ENABLED` 默认 `true`，支持大小写/空格归一后的
  `true/1/yes/on` 与 `false/0/no/off`；未知值 fail-safe 选择 Legacy `false`，operator warning 仅
  记录 flag 名称与 fallback，不记录原始值。
- `StepFunRealtimeSharedHandler` 构造时读取一次并冻结选择；环境变量随后改变不会影响当前 session。
  `false` 不构造 Provider；`true` 在首次 connect 构造且仅构造一个注入的 `provider_factory` 结果，
  reconnect 复用同一对象，不 shadow/double connect。
- frozen rollout choice 与连接状态已彻底分离：`_using_provider_port()` 只返回构造时选择。选择 Port 后，
  connect 失败、socket marker 为空或 cleanup 期间的 send/receive/health/backpressure/close 均不会回落
  Legacy；失败 connect 已构造的 Provider 仍由 `Provider.close()` 收口 backlog/owned connection。
- 默认路径通过 `RealtimeProviderPort.connect/send/receive/check_health/decide_backpressure/close`；
  `connect` 使用 frozen voice profile/model/audio/transcription/tools 构造
  `RealtimeProviderSessionConfig`，`session.update` 只由 Adapter 发送一次。
- 既有 `_send_upstream` 作为兼容 façade，把 7 类既有 outbound payload 收敛为 closed
  `ProviderCommand`；既有 `_handle_upstream_event` 的副作用链保持不变，Port receive 先消费
  `ProviderEvent`，再只投影 allowlisted compatibility fields。
- canonical projection 覆盖 ASR delta/final、speech timing、response text/audio/transcript、thinking、
  function arguments、normalized response.done function outputs、typed error/unknown。event epoch 与当前
  connection epoch 不一致时在任何 persistence/tool/turn side effect 前忽略。Review 后 canonical boundary
  还会在投影前复用 handler 的 `_active_response` 与 `_function_call_states`，校验同 epoch 的
  request/response/stream/call authority；stale text/audio/thinking/done/function args/tool output 不会进入
  persistence、TTS 或 tool chain。
- handler close 与主连接 lifecycle 采用 shielded cleanup：单次或重复 cancellation 都先完成 Provider
  close、本地 upstream/timing reset、snapshot save 与 manager disconnect，再传播首次
  `CancelledError`；清理步骤发生普通错误时仍继续尝试其余步骤并上抛首个错误。
- Provider closed reason 映射为既有安全 ASR fallback、voice unavailable、idle-timeout recovery、
  401/402/403/429 guidance；UNKNOWN 固定为 `Realtime 服务返回错误`，不恢复 raw Provider message。
- sanitized diagnostics 增加 `provider_port_enabled` 与 `selected_provider_path`；Presentation façade 只
  allowlist 这两个 closed 字段。Presentation 只通过继承的 Sales compatibility adapter 接入，未新增
  `presentation_coach -> training_runtime` 静态 import。
- Golden 已重写为真正的 Engine × Provider 四组合。Provider=true 使用 canonical Fake queue 和真实
  `_receive_upstream_events()`；覆盖 ASR delta/final、speech timing/emotion、TTS、thinking、persistence、
  tool output/follow-up、reconnect、UNKNOWN/error 以及 stale epoch/request/response/stream/call。
  四组合逐项比较 ordered downstream/upstream、snapshot/persistence、reconnect epoch、tool follow-up
  与 Engine single-writer terminal state；mutation probes 仍保留。

## TDD 证据

初始 Red：

```text
.venv/bin/python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib \
  tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_upstream.py \
  tests/unit/test_presentation_realtime_engine_handler.py \
  tests/unit/test_training_runtime_plugins.py -q
```

结果：`12 failed, 199 passed, 1 warning`。失败精确来自缺少 default-on flag、normalized
truthy/falsy/unknown fallback、`provider_factory`、frozen selection 与 canonical receive 路由。

Green 后同一四文件范围：`226 passed, 1 warning`。

CodeGraph affected 补跑发现两个 session-update snapshot 仍 monkeypatch 旧 `_send_upstream` seam，初次
结果 `2 failed, 9 passed`；测试改为捕获 Adapter 实际调用的 `StepFunTransport.send_json` 后
`11 passed, 1 warning`，并继续锁定 frozen snapshot allowlist 与 curriculum dossier payload。

Review Changes Required Red/Green：

1. 路径/连接状态 Red：connect 失败后 `_using_provider_port()` 返回 `False`，定向测试在
   `assert False is True` 失败；Green 后 connect/send/health/backpressure/close 全部证明无 Legacy 调用。
2. cancellation Red：第二次 cancel 中断 `_close_upstream()`，`_save_session_state` await count 为 0；
   Green 后 handler close 与完整 `handle_connection` 两层测试均证明重复 cancel 后 close/save/disconnect
   完成且首次 cancellation 被传播。
3. authority Red：新增 stale request/response/stream/call 参数化用例与前两项 review 测试合跑为
   `8 failed`；Green 为 `8 passed`，随后增加 `response.done` stale tool call 回归，定向共
   `8 passed`（1 canonical consume + 7 authority cases）。
4. 2×2 Golden Red：首次真实四组合 differential 在 ordered `session.update` nested canonical mapping
   上失败；修正 Fake Provider 的递归 closed DTO 投影后四组合 Golden 与 mutation tests 全绿。

## 最终验证

Brief 全量 pytest（14 个 unit/integration 文件，Review 后新增 10 个回归 case）：

```text
316 passed, 1 warning in 13.00s
```

CodeGraph affected payload snapshots：

```text
11 passed, 1 warning in 2.24s
```

其余质量门禁：

```text
Ruff: All checks passed!
mypy src: Success: no issues found in 632 source files
architecture_dependency_guard.py --check: [architecture] dependency policy satisfied
git diff --check: exit 0
```

唯一 warning 是既有 passlib 对 Python `crypt` 的弃用提示；本 Task 未过滤或升级全局依赖。

## CodeGraph 影响分析

- 开发前 `codegraph explore/node` 定位 shared handler connect、raw receive/router、send、keepalive、
  backpressure、recovery、Presentation adapter/Engine 与 persistence/tool/emotion/thinking consumers。
- `codegraph sync .`：同步 12 个 changed files。
- `_connect_upstream --depth 3`：18 affected symbols；覆盖 connect、refresh、recovery、binary/text input
  及两个 session payload snapshots。
- `_using_provider_port --depth 3`：50 affected symbols；覆盖 send/receive/health/backpressure/close、
  response/tool/audio 与 Sales/Presentation 调用链。
- `_close_upstream --depth 3`：21 affected symbols；覆盖主 lifecycle、refresh/recovery 与取消测试。
- `_handle_provider_event --depth 3`：9 affected symbols；覆盖 canonical queue 与 stale authority tests。
- `_receive_upstream_events --depth 3`：7 affected symbols；由 canonical Fake Provider receive 与真实
  Golden conversation 覆盖。
- `_send_upstream --depth 3`：48 affected symbols；覆盖 response/audio/tool/interrupt/lifecycle、Sales、
  Presentation evidence、payload snapshots 与 Golden mutation tests。
- architecture guard 证明未新增未治理 edge；Presentation subtree静态 `training_runtime` import 搜索为空。

## 假设、兼容性与回滚

- Provider 对象在首次 upstream connect 才创建，而选择 boolean 在 handler construction 冻结。原因是
  既有 handler 允许在 API key admission 前构造，并需要先向用户返回安全 missing-key 错误；对象仍只
  创建一次且 reconnect 复用。
- Legacy `false` 保留原 `StepFunTransport` connect/raw recv/json/router/send/health/backpressure/close
  路径；没有 shadow Provider、双连接、双事件或双 persistence writer。
- 本 Task 未运行完整 canonical quality gate或真实 credential/network/model authorization；前者属于
  Gate 3 最终 closure，后者明确超出授权。当前验证覆盖全部 Task 3 brief 和 CodeGraph affected tests。
- 快速运行时回滚：设置 `REALTIME_PROVIDER_PORT_ENABLED=false` 后新建 session；已建 session 选择不变。
  代码回滚：revert 本 Task commit。无数据库或持久化格式迁移。
