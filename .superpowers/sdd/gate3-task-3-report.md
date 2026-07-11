# Gate 3 Task 3 实施报告

## 结果

- 原始实现 commit：`ec7067f0 refactor(realtime): route sessions through provider port`
- Review 修复 commit：`e9df6d8d fix(realtime): enforce provider rollout and event authority`
- Review 2 修复 commit：`cff26400 fix(realtime): verify raw differential and tool authority`
- Review 3 修复 commit：`d9797c88 fix(realtime): close response authority and golden oracle`
- Review 4 修复 commit：`c060c927 fix(realtime): guard raw events before side effects`
- Review 5 修复 commit：本提交 `fix(realtime): correlate provider response authority`
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
  connection epoch 不一致时在任何 persistence/tool/turn side effect 前忽略。Review 4 后 Legacy raw 与
  canonical projection 统一进入同一个 response preflight，在 transcript capture、emotion/thinking、
  persistence、TTS、tool 和 turn side effect 前校验 request/response/stream/call authority；父子 handler
  不再重复 preflight，也不再由子类先调用 transcript hook。
- Review 5 将 response/call wire correlation 收回 Provider Adapter：canonical `response.create` 携带本地
  `request_id/stream_id`，codec 明确不编码这两个本地字段；只有 transport accepted 且 generation 仍 current
  才登记 outstanding authority。真实 `response.created` 只需 wire `response.id`，Adapter 将它与 outstanding
  authority 绑定；后续 response 事件按 `response_id` 或 current response 补全，function item 将
  `call_id` 绑定到同一 authority，sparse function arguments/response.done 再按 call binding 补全。
- correlation 与 lifecycle 共用同一 lock/generation；send failure、send cancellation、stale accepted send、
  mismatched created 均不登记，`response.done`、accepted cancel、invalidate、close、new connect 全部清理。
  Handler 不维护第二份 Port correlation map；既有 `_function_call_authorities` 只消费 Adapter 已补全的业务
  authority。Legacy rollback 仅在真实 raw receive seam 为 created/function item/后续 sparse call 补本地
  authority，直接调用 raw handler 的不可信事件仍 fail closed。
- `response.done` 不再注册从未见过的 call；合法 tool 必须先经过受信 `conversation.item.created` 绑定。
  done 中未知/stale call 只过滤 tool side effect，当前 response 仍会 flush、持久化、结束 turn 并回到
  listening。
- Review 4 用显式 `event class × active authority state` 矩阵统一 Legacy/Port：non-response 正常处理；
  `response.created` 是唯一 bind 入口，进入 shared preflight 前必须已有本地 request/stream authority 与
  wire response ID（Port 由 Adapter 补全，Legacy 由受信 raw receive seam 补全）；无 active 的 unexpected
  created 仅进入既有 KB-lock 安全 cancel；无 active 的完全 sparse
  `response.done` 仅执行 cleanup-only（清 pending follow-up、回 listening），不解析内容或执行 tool；其余
  无 active response-scoped 事件全部拒绝。stale raw assistant transcript 现在在 sink 之前被拒绝。
- handler close 与主连接 lifecycle 采用 shielded cleanup：单次或重复 cancellation 都先完成 Provider
  close、本地 upstream/timing reset、snapshot save 与 manager disconnect，再传播首次
  `CancelledError`；Review 5 补齐 cancel 与普通 cleanup error 同时发生时的优先级：保存 cleanup error 供
  无 cancellation 时安全传播，有 cancellation 时始终传播首次 cancellation，finally 仍复位本地状态。
- Provider closed reason 映射为既有安全 ASR fallback、voice unavailable、idle-timeout recovery、
  401/402/403/429 guidance；UNKNOWN 固定为 `Realtime 服务返回错误`，不恢复 raw Provider message。
- sanitized diagnostics 增加 `provider_port_enabled` 与 `selected_provider_path`；Presentation façade 只
  allowlist 这两个 closed 字段。Presentation 只通过继承的 Sales compatibility adapter 接入，未新增
  `presentation_coach -> training_runtime` 静态 import。
- Golden 已重写为真正的 Engine × Provider 四组合，并新增版本化、独立于生产 projector 的
  `stepfun_raw_conversation_v1.json` 与 `stepfun_raw_conversation_expected_v1.json`。Provider=false 直接把
  同一 raw JSON fixture 送入 Fake raw websocket；Provider=true 通过真实 `StepFunRealtimeProvider` 的
  codec + Adapter correlation 消费同一 raw fixture，不再使用人工 canonical queue。raw fixture 已删除
  人工 request/stream 字段，保留 inventory 允许的真实 response/call shape。两条路径都运行生产
  `_receive_upstream_events()`，覆盖
  ASR delta/final、speech timing/emotion、TTS、thinking、persistence、合法 call binding、tool
  output/follow-up、reconnect、UNKNOWN/error；stale authority 由独立 fail-closed tests 覆盖。独立 expected
  oracle 锁定 ordered downstream/upstream key payload、ASR text、TTS audio/text、status、persistence、tool
  与 reconnect epoch；生产 `_legacy_event_from_provider_event` 被故意损坏时，raw baseline 不受影响且
  differential/expected oracle 均按预期失败。

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

Review 2 Red/Green：

1. raw differential Red：将 Legacy 组合改为 Fake raw websocket 后，真实 receive loop 暴露旧 Golden
   直接调用 canonical handler 的假等价；修正 fixture 为合法共同 wire 序列后，Legacy raw JSON 与
   Provider canonical queue 的 ordered I/O、persistence、tool follow-up、snapshot/reconnect 全量一致。
2. call authority Red：`sparse FUNCTION_ARGUMENTS_DONE` 在空 registry 创建 state 并执行 tool；合法首事件
   没有 authority binding 字段；未绑定的 `response.done` output 仍执行 tool，定向结果 `3 failed`。
   Green 后三项均通过，并由真实 raw/canonical Golden 验证“首事件显式绑定 → sparse delta/done →
   response.done 重放去重 → 单次 tool follow-up”。

Review 3 Red/Green：

1. response.done Red：合法、明确匹配 active response 的 done 首次 call 没有 binding，且包含旧 binding
   call 的 done 会整事件 return，导致 active response、持久化与 listening status 悬挂；pre-bind stale text
   还会越过 canonical boundary。三个定向用例结果 `3 failed, 167 deselected`。Green 后 done 逐 call
   过滤、先完成当前 response，再只执行授权 call；定向 `3 passed`。
2. broader Red：旧测试仍把“matching done 首次 call”视为非法、把携带 stale response ID 且无 active 的
   done 视为可 flush，并在无 active response 时投递 thinking；首次两文件回归为
   `3 failed, 194 passed`，首次 14 文件全集为 `1 failed, 321 passed`。更新测试前置 authority 后全集
   `322 passed`。
3. Golden oracle Red：旧 harness 在 Legacy 分支直接调用生产 `_legacy_event_from_provider_event`，两腿共享
   projector，无法构造独立 corruption oracle。Green 后 fixture 不 import projector；独立 mutation probe
   修改生产 projector 时 raw 结果仍通过 expected oracle，而 canonical 结果被 differential 和 expected
   oracle 同时捕获。

Review 4 Red/Green：

1. shared preflight Red：stale raw `response.audio_transcript.done` 会先进入子类
   `TurnTranscriptCapture.on_upstream_event` 并 dispatch sink，之后父类才拒绝；回归直接观察到 captured
   payload 非空。Green 后 `_handle_upstream_event` 成为单一 template method，preflight 每事件恰好一次，
   transcript before/after hooks 只在 accepted 事件上运行。
2. created authority Red：Legacy raw `response.created` 只比 response ID，stale/missing request_id 或
   stream_id 仍绑定 active；canonical created 也允许缺失两项 authority。Green 后 raw/canonical 共用精确
   authority 规则，冲突或缺失字段均不能 bind。
3. no-active matrix Red：canonical sparse done 被 blanket reject，pending follow-up 悬挂；canonical
   unexpected created 无法进入 KB-lock cancel；Legacy sparse thinking 又被过宽放行。三个定向用例结果
   `3 failed, 169 deselected`，Green 为 `3 passed`；三文件定向回归 `220 passed`。

Review 5 Red/Green：

1. canonical authority Red：带本地 `request_id/stream_id` 的 `CREATE_RESPONSE` 在 DTO closed-field 校验时
   直接报 `provider_command_data_field_unknown:request_id`；Green 后 codec wire 仍只有标准
   `response.create.response`，Adapter 在 accepted send 后登记本地 authority。
2. real sparse wire Red：`response.created` 只有 `response.id` 时无法绑定，后续 sparse text/function item/
   arguments/done 无 authority；Green 后同一 generation 内补全 request/response/stream，call 只由 function
   item 注册，done 后 late sparse call 不再补全。failed/cancelled/stale send、mismatched created、accepted
   cancel 均由独立测试证明不产生或会清除 correlation。
3. done 首注册 Red：旧测试允许 matching `response.done` 首次注册并执行未见 call；Green 后该 call 被过滤，
   合法 Golden 流程通过先到达的 sparse `conversation.item.created(function_call)` 绑定，并且 tool 恰好执行
   一次。
4. close 组合 Red：outer cancellation 后 cleanup task 抛普通错误时，普通错误越过首次 cancellation；Green
   后首次 `CancelledError("first-cancel")` 优先传播，本地 socket/timing 状态仍在 finally 复位。

## 最终验证

Brief 全量 pytest（14 个 unit/integration 文件）：

```text
324 passed, 1 warning in 13.74s
```

Review 5 的 Task 1/2 Provider 合同 + Task 3 全集（18 个文件）：

```text
608 passed, 1 warning in 14.81s
```

CodeGraph affected 全集（20 个 contract/e2e/integration/unit 文件）：

```text
797 passed, 1 warning in 43.34s
```

Review 5 CodeGraph affected 55 个文件重新收集 `1136 items`，使用 repo 标准
`python -m pytest -c pyproject.toml -o addopts=--import-mode=importlib --no-cov` 跑完，exit 0。

其中 payload snapshots 独立复核：

```text
11 passed, 1 warning in 2.14s
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
- `codegraph sync .`：Review 5 修改后的索引同步完成。
- `_connect_upstream --depth 3`：18 affected symbols；覆盖 connect、refresh、recovery、binary/text input
  及两个 session payload snapshots。
- `_using_provider_port --depth 3`：50 affected symbols；覆盖 send/receive/health/backpressure/close、
  response/tool/audio 与 Sales/Presentation 调用链。
- `_close_upstream --depth 3`：21 affected symbols；覆盖主 lifecycle、refresh/recovery 与取消测试。
- `_handle_provider_event --depth 3`：9 affected symbols；覆盖 canonical queue 与 stale authority tests。
- `_preflight_upstream_event`：24 affected symbols；覆盖 raw/canonical matrix、transcript sink、created bind、
  cleanup-only done、thinking/emotion/persistence/tool 前置 authority。
- `_handle_upstream_event`：34 affected symbols；覆盖 receive loop、Sales/Presentation handlers、Golden raw/
  canonical drivers 与 response/transcript/tool consumers。
- `_authorize_function_call_event --depth 3`：18 affected symbols；覆盖 Provider/Legacy 首事件注册、
  sparse delta/done、response.done、tool execution 与 reconnect reset。
- Review 5 `_send_upstream --depth 3`：51 affected symbols；覆盖本地 create authority 注入、
  response/audio/tool/interrupt/lifecycle、Sales、Presentation Golden 与 rollback。
- Review 5 `_receive_upstream_events --depth 3`：8 affected symbols；覆盖 Port Adapter 与 Legacy 受信 raw
  correlation seam。
- Review 5 `_close_upstream --depth 3`：23 affected symbols；覆盖 cleanup error × cancellation 组合。
- Review 5 changed-source affected：55 个 test files / 1136 collected items，exit 0。
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
