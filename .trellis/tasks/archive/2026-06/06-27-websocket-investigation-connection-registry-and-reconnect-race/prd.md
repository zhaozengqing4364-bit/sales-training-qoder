# PRD: WebSocket 层调查报告

## 背景

P0 期间 A 阶段架构对齐发现 WebSocket 层的三个风险面:
1. 两个并存的连接注册中心:`ConnectionManager`(`base_handler.py:135`,进程内存,scenario→session→WS)与 `SessionManager`(`session_manager.py`,进程内存,session→handler)。两者各自独立字典,add/remove 不在同一临界区。
2. 重连恢复路径(`base_handler.py:257-273`):从 redis 拉 snapshot 恢复,存在 race 可能。
3. `send_json`(`base_handler.py:106`)静默吞错:`except Exception` 只 log 不传播,被 10 处调用。

初步核查发现:`SessionManager.register_session`/`unregister_session` 在 `base_handler.py` 里**没有调用点**——注册逻辑可能散落在 scenario handler 或 router。这是调查的入口疑点。

## 决策(本任务)

**只调查,不改代码**。产出一份调查报告,覆盖三个风险面的代码事实 + 风险定级 + 是否需要修复的建议。基于报告再决定是否建修复任务(丁方案的"P3 先调查后决策")。

## 调查范围(报告须回答)

### R1. 两个连接注册中心的一致性
- `ConnectionManager` 的 `connect`/`disconnect` 在哪些文件调用?调用时序(accept→register→业务→unregister→close)是否完整?
- `SessionManager` 的 `register_session`/`unregister_session` 在哪些文件调用?还是根本没被调用(死代码)?
- 两者是否会出现"ConnectionManager 注册了但 SessionManager 没注册"或反过来的不一致?在什么场景(异常断开、并发同 session、进程重启)?
- `_close_replaced_websocket`(同 session 新连接踢旧连接)与 SessionManager 的注销是否原子?

### R2. 重连恢复路径的 race
- `handle_connection` 开头的 `existing_state` 检查 + `_restore_session_state` 是否有竞态(两个连接同时进来,都读到 existing_state)?
- 重连恢复与 `ConnectionManager` 的"新连接踢旧连接"逻辑交叉时,旧连接的清理与新连接的恢复是否有序?
- `SessionManager.describe_authority` 声明 connection_registry 在内存(survives_restart=False),session_snapshot 在 redis(survives_restart=True)——进程重启后连接丢但状态在,重连路径能否正确恢复?

### R3. send_json 静默吞错的影响面
- 10 处调用点分布在哪?哪些是"用户可见消息"(断了用户无感)、哪些是"控制消息"(断了影响状态机)?
- 吞错后 handler 是否继续运行(状态机以为消息发出去了)?这是可用性 bug 还是正确性 bug?

### R4. 风险定级与修复建议
- 每个风险面给 🔴阻断/🟡关注/🟢安全 定级
- 对需要修复的,建议"最小契约修复"还是"症状缓解",并说明未触及的入口(AGENTS.md §V.3)

## 范围

### 必做
- 产出 `.trellis/tasks/06-27-websocket-investigation-connection-registry-and-reconnect-race/research/report.md`:覆盖 R1-R4

### 不做(明确边界)
- 不改任何代码(调查报告 only)
- 不建修复任务(看完报告再决定)
- 不查 StepFun upstream 事件路由(upstream.py 2758 行是另一条线,本任务聚焦连接生命周期)

## 验收标准

- [ ] report.md 覆盖 R1-R4 全部问题
- [ ] 每个结论附 `file:line` 证据
- [ ] R4 给出明确"是否需要建修复任务"的建议
- [ ] 报告基于代码事实,不猜测

## 不属于本任务

- WebSocket 修复实现(待报告结论后单独建任务)
- StepFun upstream 事件路由深查
