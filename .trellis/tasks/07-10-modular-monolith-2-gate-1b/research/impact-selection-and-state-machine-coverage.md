# Gate 1B：影响测试选择与关键状态机覆盖审计

> 审计日期：2026-07-10
> 性质：只读研究；本文件不代表已经修改门禁、测试或生产代码。
> 审计范围：changed-path、Git diff base、CodeGraph `affected` / `impact`、后端 integration 与前端 Playwright 选择，以及“持久化进度 → 路径解锁”、录音、会话生命周期、Realtime 重连等关键状态机覆盖。

## 1. 结论先行

Gate 1B 值得做，而且会直接提升未来扩展能力；但正确方向不是“让 CodeGraph 决定跑哪些测试”，而是建立一套**保守、可解释、失败时自动扩大范围**的单一门禁：

1. 后端 `unit + contract` 与前端完整 Vitest 应自动发现并作为代码变更的稳定底座，不再维护固定文件清单。
2. changed-path + CodeGraph 只用于扩展选择较慢的 backend integration/backend e2e/Playwright；不能成为唯一真相。
3. Git 比较基线、删除/重命名文件、CodeGraph 索引健康、空选择与 JSON 解析都必须 fail closed：无法证明“无需测试”时，运行完整的可选择测试族。
4. `codegraph impact` 适合生成审计证据和人工复核，不适合作为自动 runner 的主要输入；`codegraph affected` 才能返回测试路径，但其 exit code 与 `--json` 都不足以证明成功。
5. 当前唯一门禁没有执行若干已经存在的关键状态机测试；更重要的是，“真实持久化进度经过 `SalesTrainerPathService` 解锁下一关”目前没有跨层证明。
6. 录音状态机存在一个真实的集成缝隙：hook 的测试演示了 `requesting_permission` 防重，但页面的权限请求分支没有调用 `beginTransition("requesting_permission")`，因此待决权限请求期间仍可能重复触发。
7. 当前覆盖率只能证明语句覆盖的低全局阈值；后端没有 branch coverage，前端只有全局 25% branches，均不能保护关键状态机。

推荐将 Gate 1B 设计为：

```text
可信 diff base
  -> 变更路径归一化（含 D/R、staged/unstaged/untracked）
  -> 永久底座：全量 backend unit+contract + 全量 Vitest
  -> 直接变更测试 + CodeGraph affected（按测试族分别查询）
  -> 确定性路径策略补全 integration/E2E
  -> 核心/跨切面/工具异常触发 full fallback
  -> changed executable lines + 关键状态机 branch/scenario gate
  -> 写入同一份 quality-gate evidence
```

## 2. 现状证据

### 2.1 唯一门禁仍是固定清单，不是自动发现

权威入口是 `scripts/critical-quality-gate.sh`，符合 `scripts/AGENTS.md` 的“不得新增第二套质量门禁”约束，但它当前维护的是静态数组：

| 测试族 | 仓库现有文件数 | 当前门禁行为 | 结论 |
|---|---:|---|---|
| backend unit | 273 | 与 contract/integration 混在 58 个固定 backend target 中 | 不是全量、不是自动发现 |
| backend contract | 27 | 只列出少量固定文件 | 不是全量 |
| backend integration | 93 | 固定选择一部分 | 无 changed-path 选择 |
| backend e2e | 2 | 无独立、明确的选择策略 | 边界模糊 |
| web Vitest | 209 | 固定 29 个 target | 漏掉大量已有测试 |
| Playwright | 7 | 固定运行 smoke、closed-loop、presentation、sales 4 个 spec | 未运行 admin、learner、audit 3 个 spec |

固定清单直接漏掉的关键测试包括：

- `web/src/app/(user)/practice/[sessionId]/use-recording-state-machine.test.ts`
- `web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts`
- `web/src/hooks/use-practice-websocket.test.ts`
- `web/src/hooks/use-practice-websocket.presentation-flow.test.ts`
- `backend/tests/unit/test_session_lifecycle_service.py`
- `backend/tests/unit/test_session_control_adapter.py`
- `backend/tests/integration/test_session_lifecycle_api.py`

门禁当前会运行 `test_sales_realtime_reconnect_flow.py`、`test_stepfun_realtime_handler.py` 和 `test_session_runtime_authority.py`，所以不是“Realtime 完全无覆盖”，而是**状态机证明被静态清单割裂**：重连 happy path 在，生命周期转换矩阵和前端状态机却不在。

### 2.2 当前没有 changed-path、diff base 或 CodeGraph runner

`critical-quality-gate.sh` 中没有：

- `git diff` / `git merge-base`；
- `GITHUB_BASE_REF`、PR base SHA、push before SHA；
- `codegraph affected` / `codegraph impact`；
- 按变更路径动态生成 pytest/Vitest/Playwright targets；
- changed-line coverage。

`.github/workflows/release-truth-gate.yml` 使用默认 `actions/checkout@v4`，没有配置 `fetch-depth`。默认浅克隆不能保证 PR base、push before 或 merge-base 对象可用。工作流也没有安装 CodeGraph CLI；本机 CLI 位于用户目录 `/home/dev/.local/bin/codegraph`，版本为 1.2.0，并非仓库依赖。

更关键的是，仓库只跟踪 `.codegraph/.gitignore`，约 114 MB 的 `.codegraph/codegraph.db` 被忽略。也就是说，干净 GitHub runner 即使碰巧有 CLI，也没有可用索引。

## 3. Git diff base 审计

### 3.1 为什么不能使用 `HEAD^`

当前审计分支的事实可以说明风险：

- `HEAD` 相对 `origin/main` 是 61 个提交；
- `origin/main...HEAD` 有 567 个变更路径；
- `HEAD^` 只代表最后一个提交。

如果门禁用 `HEAD^`，多提交 PR 会系统性漏测。如果本地一律和 `origin/main` 比，又可能在有正确 upstream 的长期分支上过度选择。因此 base 必须由运行上下文决定，而不是写死。

### 3.2 推荐的 base/head 优先级

| 场景 | base | head | diff 语义 |
|---|---|---|---|
| 显式调用 | `QUALITY_GATE_BASE_SHA` | `QUALITY_GATE_HEAD_SHA` 或 `HEAD` | 调用者权威，先验证对象存在 |
| GitHub PR | `github.event.pull_request.base.sha` | `github.event.pull_request.head.sha` | `base...head`，以共同祖先到 PR head 为变更集合 |
| GitHub push | `github.event.before` | `github.event.after` | `before..after`，精确表示本次 push；全零 before 视为新分支特殊情况 |
| 本地有 upstream | `git merge-base HEAD @{upstream}` | `HEAD` | base 到 HEAD，并合并工作区变更 |
| 本地无 upstream | 显式配置的目标分支 merge-base | `HEAD` | 不应静默猜测多个候选分支 |
| schedule/manual/release full | 无 | `HEAD` | 不做缩小选择，直接 full |

CI 应采用 `fetch-depth: 0`，或显式 fetch base/head 两个 SHA。若 base 对象不存在、merge-base 失败、push before 是全零且无法计算新分支基线，必须记录原因并进入 full fallback，不能退化为 `HEAD^`。

### 3.3 变更路径必须包含工作区和删除/重命名

本地运行应合并四类路径：

1. `base...HEAD` 的已提交变更；
2. `git diff` 的 unstaged 变更；
3. `git diff --cached` 的 staged 变更；
4. `git ls-files --others --exclude-standard` 的 untracked 文件。

应使用 NUL 分隔读取 Git 输出，并保留 `D`、`R` 状态。不能使用只保留 `ACMR` 的过滤：

- 删除源文件时，当前 CodeGraph 索引中可能已经没有节点；
- 重命名只传新路径会失去旧依赖语义；
- 删除测试也必须触发同测试族或领域的补偿回归。

对于 `D/R`，最安全的 Gate 1B 策略是：路径策略至少扩大到对应领域；无法从当前索引恢复旧依赖时，对该测试族 full fallback。

## 4. CodeGraph CLI 的真实输出与 exit semantics

本仓库索引审计时为：1,961 files、37,252 nodes、110,508 edges，`pendingChanges` 为 0。以下均为本机 CodeGraph 1.2.0 实测，不应把这些行为当成未来版本的永久契约，因此版本必须固定并加 contract test。

| 调用 | exit | stdout | 风险 |
|---|---:|---|---|
| `codegraph affected --json`（无路径） | 0 | ANSI 装饰的人类提示，不是 JSON | `--json` 不保证 JSON |
| `codegraph affected --json does/not/exist.py` | 0 | 合法 JSON，`affectedTests=[]` | 不存在路径不被视为失败 |
| `codegraph impact --json DefinitelyMissingSymbol` | 0 | ANSI 人类提示，不是 JSON | exit 0 不能证明 symbol 存在 |
| `codegraph status --json /tmp/no-index` | 0 | 合法 JSON，`initialized:false` | status exit 0 不能证明索引可用 |
| 无索引目录执行 `affected` | 1 | stderr 错误 | 这是少数明确失败情况 |
| 有效 `affected --json <path>` | 0 | 合法 JSON | 仍需校验 schema、路径存在、结果分类 |
| `affected --stdin` + 换行路径 | 0 | 正常识别多路径 | stdin 协议是 one-per-line |
| `affected --stdin` + NUL 路径 | 0 | 把全部字节当成一个路径，空选择 | 不能直接接 `git diff -z` |

还观察到一个重要语义：`--filter` 不是对默认结果做简单后过滤。对 `path_service.py`：

- 默认 `affected` 返回 28 个后端测试；
- 使用 `--filter 'backend/tests/integration/**'` 后，返回的 integration 集合还出现了默认结果没有的 `test_admin_business_rules_api.py`、`test_admin_users_api.py` 等文件。

因此必须**按测试族分别调用** `affected --filter`，不能先调用一次默认查询再按字符串分类，也不能假设默认结果是所有 filter 结果的超集。

### 4.1 `affected` 的有效能力与边界

有效例子：

- `path_service.py` 能找到 path contract、path integration 和多个 path unit tests；
- `use-recording-state-machine.ts` 能找到其 hook test 与 `page.test.tsx`；
- `stepfun_realtime_state.py` 能找到 reconnect integration、websocket contract 和 StepFun unit tests。

边界例子：

- `use-practice-websocket.ts` 使用 `--filter 'web/tests/e2e/**'` 返回空集合；Playwright 通过浏览器与 HTTP/WS 黑盒调用，不一定 import 生产模块。
- `session_lifecycle.py` 最终只找到 `newcomer-training-closed-loop.spec.ts`，却没有选择明显相关的 `sales-phase4.spec.ts`、`presentation-phase4.spec.ts` 或 smoke；而 traversal 已达到 1,037 个 dependents。
- 广泛共享的 `session_lifecycle.py` 按 integration filter 几乎扩散到全 integration 套件，说明跨切面源文件本来就应 full fallback，而不是人为截断图深度。
- 未过滤结果可能包含 `backend/tests/conftest.py`、fixtures、evaluation/performance 文件和跨语言测试；runner 必须按严格可执行文件模式分类，不能把返回值原样交给 pytest。

### 4.2 推荐的解析契约

选择器必须同时满足以下条件才接受 CodeGraph 结果：

1. `command -v codegraph` 成功，版本等于仓库固定版本；
2. `codegraph status --json` 可解析，且 `initialized === true`；
3. 索引 sync 后 `pendingChanges` 为空、`worktreeMismatch` 为 null；
4. stdout 不含 ANSI，且整体是单个 JSON object；
5. `changedFiles`、`affectedTests` 是字符串数组，`totalDependentsTraversed` 是非负数；
6. 每个返回测试路径都在仓库内、真实存在、匹配允许的测试文件模式；
7. 输入中的生产代码路径不存在或结果为空时，由路径策略判断是否允许；默认不允许静默空选择。

任一条件不满足：在 evidence 中写入 `codegraph_status=invalid` 和 `fallback_reason`，运行完整 integration/backend-e2e/Playwright 可选择测试族。正确性不能依赖一个未固定、未安装、未建索引的本地工具。

`codegraph impact` 需要单个 symbol；同名 symbol、删除 symbol、未找到 symbol 都不适合作为自动 runner 输入。建议仅对核心改动生成 impact evidence，帮助人工确认 blast radius；测试执行仍以 `affected + path policy + fallback` 为准。

## 5. 推荐的自动测试选择架构

### 5.1 三层真相，而不是单一图算法

#### 层 A：不可缩小的稳定底座

对任何代码/配置/依赖变更：

- 自动发现并运行全部 `backend/tests/unit/**/test_*.py`；
- 自动发现并运行全部 `backend/tests/contract/**/test_*.py`；
- 运行完整 Vitest（配置本身已经排除 `web/tests/e2e/**`）；
- 继续全量执行 Ruff、架构依赖守卫、OpenAPI parity、TypeScript、lint。

这一步直接消除固定清单衰减。测试新增后无需记得手工登记，符合“让结构承载知识，而不是依赖个人记忆”。

#### 层 B：慢测试的保守选择

integration/E2E 的候选集合是以下并集：

1. 直接被修改或新增的测试文件；
2. CodeGraph 对每个测试族单独执行 `affected --filter` 的结果；
3. 确定性 changed-path policy 的结果；
4. 核心回归清单（少量业务关键情景，不是大量固定单测清单）。

必须去重并按稳定顺序输出，每个测试带 selection reason，例如：

```json
{
  "test": "web/tests/e2e/newcomer-training-closed-loop.spec.ts",
  "reasons": [
    "path-policy:sales-trainer-progress",
    "codegraph:backend/src/common/db/session_lifecycle.py"
  ]
}
```

#### 层 C：full fallback / full truth

以下任一条件触发完整慢测试族：

- schedule、manual full、main/release push；
- CodeGraph 不可用、索引不健康、JSON 无效；
- base/head 不可信；
- 删除/重命名无法映射；
- 修改测试基础设施、全局 fixtures、runner/config、依赖/lockfile、迁移、app factory、认证授权、公共 DB 生命周期、共享 WebSocket transport；
- changed source 非空，但图与路径策略共同得到空测试集合；
- 单个核心源文件影响图爆炸到接近全测试族。

### 5.2 最小确定性路径策略

| changed path | 至少补入 |
|---|---|
| `backend/src/sales_trainer/services/path_*`、audio/quiz progress | path/journey integration + newcomer admin/learner/closed-loop Playwright |
| `backend/src/sales_bot/websocket/**`、`backend/src/common/db/session_lifecycle.py` | session lifecycle API、reconnect flow、websocket contract + sales/presentation/newcomer relevant E2E；公共 lifecycle 直接 full integration |
| `web/src/hooks/use-practice-websocket*`、practice session 页面/hooks | 对应 Vitest 已由全量底座覆盖；补 sales/presentation/newcomer Playwright |
| backend API/schema/OpenAPI | 对应 contract/integration；公共 API client/router 变化补 smoke |
| auth/permission/middleware/app factory | 全 contract + 全 integration + smoke，并至少覆盖对象级权限 E2E |
| `web/tests/e2e/*.spec.ts` | 直接运行该 spec |
| Playwright config/global setup/fixtures、smoke stack scripts | 全 Playwright |
| pytest config/conftest/shared fixtures、requirements/pyproject | 全 backend 测试族 |
| Vitest config/setup、package/lockfile | 全 Vitest；若浏览器运行时也受影响则全 Playwright |

路径策略应是小型、显式、可测试的数据表，不应散落在 shell `if` 中。CodeGraph 负责发现普通依赖，policy 负责补齐动态调用、HTTP/WS 黑盒、删除文件和跨切面边界。

### 5.3 运行路径与前缀

CodeGraph 返回 repo-relative 路径；实际 runner 在子目录执行时必须显式转换：

- `backend/tests/...` → 在 `backend/` 中运行时去掉 `backend/`；
- `web/src/...test.ts`、`web/tests/e2e/...` → 在 `web/` 中运行时去掉 `web/`；
- 不匹配已知前缀的结果拒绝执行并触发 fallback。

避免通过 shell 字符串拼接命令；路径必须使用数组传参，保留空格、括号和 `[sessionId]` 等字符。

## 6. 关键状态机覆盖审计

### 6.1 持久化进度 → `SalesTrainerPathService` 解锁：当前缺少跨层证明

生产链路为：

```text
SalesTrainerPathService.list_paths_for_user
  -> active_projection
  -> load_latest_quiz_progress / load_latest_audio_progress（真实 DB）
  -> build_path_payload（完成规则、依赖解锁）
  -> TrainingJourneyService visibility 二次覆盖
  -> learner path payload
```

现有 `test_should_project_sales_trainer_path_with_unlock_progress` 只直接调用 `build_path_payload` 并手工构造 `UnitProgress`。它证明 projector 的一个 happy path，但没有证明：

- quiz/audio submission 与 score 真实写入后能被 progress loader 读取；
- 最新记录选择、outer join、`Decimal`/nullable 字段转换正确；
- active revision 中的 unit identity 与 submission identity 对齐；
- `SalesTrainerPathService` 的 journey visibility 二次处理不会把已解锁关卡再次锁住；
- 新 AsyncSession/重新读取后仍能解锁，而不是依赖内存对象。

全仓只发现少量 `SalesTrainerPathService(...).list_paths_for_user(...)` 调用，分别覆盖无 active revision、配置发布/回滚、placeholder、learner-level visibility、audio group 展开等；没有一个测试在真实提交/评分后再次调用 path service 并断言下一关从 `locked` 变为 `available`。

#### 必须新增的 canonical integration proof

建议一个测试贯穿：

1. 发布含两个真实单元的 active path，第二关依赖第一关；
2. 第一次读取 path：第一关 available、第二关 locked；
3. 通过真实 application service 持久化第一关 attempt/submission/score；
4. commit，换一个 AsyncSession 再调用 `SalesTrainerPathService.list_paths_for_user`；
5. 断言第一关 completed、第二关 available、`current_level_id`/`next_level_id` 指向第二关；
6. 同时断言 result lineage、path revision、用户隔离和 journey visibility；
7. 至少覆盖 quiz 与 audio 两种 progress loader，或把共享契约参数化。

#### 一个尚未决定的业务语义风险

`load_latest_quiz_progress` 和 `load_latest_audio_progress` 都按时间倒序后，每个 unit 只保留“最新一条”。这意味着：用户已经通过后再次重练但失败，最新失败记录可能让已完成关卡重新变成未完成，并重新锁住后续关卡。

这不应由测试作者猜测。Gate 1B 实施前必须明确：

- 完成是否单调（once completed, remains completed）；
- regrade 是否允许撤销完成；
- path revision 变化时历史完成如何映射；
- “最新尝试”与“最佳/最后一次通过”分别用于展示还是解锁。

这是领域规则，不只是覆盖率问题。未决前应增加 characterization test，防止未来重构悄悄改变行为。

### 6.2 前端录音状态机：分支测试存在，但生产集成遗漏权限防重

`use-recording-state-machine.ts` 的意图优先级为：

1. transition 非 idle → `blocked/transitioning`；
2. connection 非 connected → `blocked/connection`；
3. session 非 in_progress → `blocked/session_status`；
4. lifecycle pending → `blocked/lifecycle`；
5. 已录音 → stop；
6. permission false → request_permission；
7. 其他 → start。

现有 3 个 hook tests 已覆盖：

- `starting` 期间拒绝重复 begin，end 后恢复；
- permission false 返回 request_permission；
- connection/session/lifecycle 三种 blocked reason。

明显缺口：

- `isRecording=true` 的 stop 分支；
- `hasPermission=null` 的 start 分支；
- 多个 blocker 同时存在时的优先级；
- props rerender 后 `inputRef` 与同步 `currentIntent` 一致；
- stopping/requesting_permission 的并发行为；
- start/stop/requestPermission reject 后是否必然回到 idle，并给用户可见错误。

更重要的是，页面 `page.tsx` 的 start/stop 分支调用了 `beginTransition`，但 `request_permission` 分支直接执行异步 `requestPermission()`，没有 `beginTransition("requesting_permission")` 和 `finally/endTransition()`。hook test 中虽然手动测试了该 transition，生产调用点却没有使用它。

现有页面测试只证明“权限拒绝完成后可以立刻再次点击”，没有使用 pending Promise 证明“双击只发起一次权限请求”。这应列为 P1 修复与回归测试：

- 第一次点击后保持 permission Promise pending；
- 第二次点击不再调用 requestPermission；
- Promise settled 后 transition 回 idle；
- 拒绝后下一次点击仍可重试；
- 授权成功只启动一次录音和一次 continuous upload。

### 6.3 后端会话生命周期：已有良好骨架，但门禁和 branch gate 没有承接

`SessionLifecycleService.transition` 已把 start/pause/resume/end、幂等和非法转换集中在一个模块，并采用 optimistic compare-and-swap 处理 stale writer。现有测试质量比固定门禁体现出来的更好：

- unit：start、pause/resume、pause idempotent、sales end→scoring、presentation end→completed、非法 resume、terminal race convergence；
- integration API：完整 start/pause/resume/end、非法转换、权限、REST→live handler 同步、end idempotent、终态后台完成；
- Realtime integration：断线保存 turn state、重连恢复、继续第三轮、end 后 snapshot cleanup。

问题有三层：

1. `test_session_lifecycle_service.py`、`test_session_control_adapter.py`、`test_session_lifecycle_api.py` 不在当前固定门禁；
2. backend coverage 配置没有 branch coverage，无法证明转换矩阵分支；
3. concurrency helper 仍有未形成显式矩阵的路径，如无 session id、CAS row missing、persisted state missing、非终态冲突 retry/no-retry、未知 action。

建议把生命周期测试定义为**少量永久 critical scenario set**，即使 CodeGraph 未选择也执行：

- 每个 action 的 valid / idempotent / invalid；
- sales 与 presentation 的不同 terminal status；
- stale writer 输给 terminal writer；
- 非 terminal CAS conflict 的单次重试与最终收敛；
- REST lifecycle 同步 live handler；
- websocket reconnect 恢复与 terminal cleanup。

### 6.4 Realtime/recording 状态并不是一个状态机，而是三个相邻状态权威

当前实际存在三个层次：

```text
浏览器 transport/reconnect epoch
  -> 页面 recording transition + MediaRecorder permission/start/stop
  -> 后端 SessionLifecycleService + StepFun snapshot/reconnect state
```

每层都有单测，但跨层 invariants 需要明确：

- 未 connected / 未 in_progress / pause pending 时不得发送录音；
- reconnect 后只有服务端恢复为 in_progress 才恢复 audio send；
- stale socket/interrupt/close 不能污染新 epoch；
- paused/scoring/completed 不能被旧客户端事件重新推进；
- terminal transition 后 snapshot 必须删除；
- snapshot missing/corrupt/store failure 必须按 required/optional policy 明确降级；
- start/pause/resume/end 重复请求必须幂等且可审计。

前端 `use-practice-websocket.test.ts` 已覆盖异常 close、retry exhaustion、retry reset、backpressure、pause gating、reconnected 恢复、stale close/interrupt 等大量分支；但它不在当前门禁。后端 reconnect integration 则只有一个完整 happy path。建议保留该 tracer bullet，同时为 missing/corrupt snapshot、paused/terminal reconnect 和 state-store failure 各增加一个边界情景，而不是试图给巨大的 StepFun handler 追求形式化 100% 分支率。

## 7. 覆盖率门禁设计

### 7.1 当前覆盖率不能证明状态机

后端 `pyproject.toml` 当前为：

- `--cov=src`；
- statement `--cov-fail-under=48`；
- 没有 `--cov-branch`。

现有 `.coverage` 通过 coverage.py 7.15.0 导出的 metadata 明确显示 `branch_coverage: false`。专项 newcomer coverage gate 也是 statement threshold 45。

前端 Vitest 的全局 thresholds 是：lines/functions/statements 30%、branches 25%。低全局阈值可以被大量简单文件稀释，不能保护 118 行的录音状态机。

### 7.2 推荐双层指标

1. **Changed executable line coverage**：使用与选择器相同的 base/head，解析 `git diff --unified=0` 新行范围，与 coverage JSON/V8 location map 的可执行行相交。删除行不进入分母，纯注释/空行不进入分母。
2. **关键状态机 branch/scenario coverage**：对少量核心模块单独设强约束，不用全局数字替代业务矩阵。

建议初始标准：

| 范围 | 建议门槛 |
|---|---|
| 新增/修改的可执行行 | >= 90%，关键状态机 changed branches 100% |
| `use-recording-state-machine.ts` | branches/functions 100% |
| path completion/unlock projector + progress loaders | branch >= 95%，canonical persisted unlock scenario 必过 |
| `SessionLifecycleService.transition` 决策区 | transition matrix 全覆盖；changed branches 100% |
| 大型 StepFun handler | 不强求文件级 100%；以关键 reconnect/terminal scenarios + changed lines 约束 |

后端可在同一次 pytest 中开启 `--cov-branch` 并生成 JSON，避免重复运行。前端使用现有 V8 `coverage-final.json`/summary location 数据即可实现 changed-line 检查，不必为了第一版立即引入新依赖。

所有阈值都应先跑 baseline 并记录债务，再渐进提高；但关键状态机新增分支从第一天起不能豁免。

## 8. Gate 1B 实施顺序与验收标准

### 阶段 1：先建立可信输入

1. CI checkout 提供完整 base/head history；工作流显式传 PR/push SHA。
2. 在唯一 `critical-quality-gate.sh` 内接入 selection helper，不新增第二门禁。
3. Git path collector 支持 committed/staged/unstaged/untracked/D/R，并有 shell/fixture contract tests。
4. 对 base missing、new branch、detached HEAD、无 upstream、docs-only 建立明确结果。

### 阶段 2：消除静态清单衰减

1. backend unit+contract 自动发现并全量执行。
2. Vitest 不带固定 target，执行完整 suite。
3. 直接变更测试始终执行。
4. 删除当前固定清单中重复职责，保留极小的 critical scenario set。

### 阶段 3：接入 CodeGraph，但默认保守

1. 固定 CLI 版本并定义安装/缓存/index/sync 策略；在 CI 没准备好前不得宣称 CodeGraph gate 已启用。
2. 为 status、affected JSON、无文件、missing path、missing symbol、无索引、ANSI 输出写 contract tests。
3. 按 backend integration、backend e2e、Playwright 分别执行 filter 查询。
4. 加 deterministic path policy 和 full fallback；CodeGraph 异常永远扩大测试，不缩小。
5. evidence 记录 base/head、changed paths、索引版本/健康、每个 selected test 的理由、fallback 原因。

### 阶段 4：补关键业务证明

1. 新增“真实持久化进度 → 新 AsyncSession → `SalesTrainerPathService` 解锁”integration test。
2. 决定“通过后重练失败是否重新锁关”的领域语义并固化 characterization test/ADR。
3. 修复并测试 permission pending 防重集成缝隙。
4. 把生命周期 unit/API/reconnect critical scenarios 纳入永久集合。
5. 增加 missing/corrupt snapshot、paused/terminal reconnect、store failure 边界情景。

### 阶段 5：changed-line 与 branch gate

1. 后端开启 branch data，前端输出 location-level V8 数据。
2. 用同一 diff base 计算 changed executable lines。
3. 对录音、路径解锁、生命周期决策区执行强 branch/scenario gate。
4. 先 baseline、再提高全局覆盖率，不允许通过降低阈值解决失败。

### 完成判定

Gate 1B 只有同时满足以下条件才算完成：

- 新增 unit/contract/Vitest 文件无需修改清单即可进入门禁；
- 多提交 PR 不会退化为 `HEAD^`；浅克隆/base 缺失会显眼失败或 full fallback；
- 删除/重命名、dirty/untracked 本地变更不会静默漏选；
- CodeGraph 缺失、未初始化、过期、返回 ANSI/空/非法 JSON 时不可能得到“0 tests passed”；
- Playwright 黑盒依赖由 path policy 补齐；
- selection evidence 能回答“为什么跑/为什么没跑这个测试”；
- persisted unlock canonical proof、permission pending 防重、生命周期 critical matrix 均进入权威门禁；
- backend branch data 与 changed-line coverage 可复现；
- schedule/main/release 仍有完整慢测试真相，不把选择算法当作绝对正确。

## 9. 风险排序

| 优先级 | 风险 | 后果 | 处理 |
|---|---|---|---|
| P0 | CI 无 CodeGraph CLI/索引，却把空选择当成功 | 大范围漏测 | 未健康即 full fallback；另设工具健康检查 |
| P0 | 使用错误 diff base 或忽略 D/R | 多提交 PR、删除模块漏测 | event SHA + merge-base + NUL/name-status |
| P1 | persisted progress→path unlock 无跨层测试 | 路径可在投影单测绿时生产不解锁 | canonical DB/service integration proof |
| P1 | permission transition 测了但生产没接线 | pending 权限请求重复触发 | 页面接入 transition + deferred Promise 回归 |
| P1 | 生命周期核心测试存在但不在门禁 | 状态转换回归无法阻断发布 | full unit + critical API scenario set |
| P1 | E2E 依赖 CodeGraph import 图 | HTTP/WS 黑盒漏选 | 确定性路径策略 + full truth |
| P2 | 只有低全局 statement/branch 阈值 | 状态机新分支无测试也可通过 | changed lines + critical branch/scenario gate |
| P2 | `impact`/`affected` schema 与版本未固定 | 工具升级后 selector 静默漂移 | pin version + CLI contract tests + evidence |

最终判断：**修复有意义，且优先级高**。收益不只是节省 CI 时间，而是把“哪些测试保护哪些业务状态”从人的记忆迁移到可执行、可审计的架构规则中。真正应避免的是为了追求智能选择而制造新的不透明单点；Gate 1B 必须以完整底座、显式策略和失败时扩大范围来约束 CodeGraph。
