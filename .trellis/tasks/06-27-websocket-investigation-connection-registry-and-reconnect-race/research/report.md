# WebSocket 连接生命周期三风险面调查报告

## 概述

三个风险面**均存在真实代码缺陷**,但严重度不同:`send_json` 静默吞错(R3)与注册中心不一致(R1)、重连 race(R2)均为 **🟡关注**(偶发非阻断,但无原子性保证)。**建议建 P1 修复任务**(非 P0 阻断),聚焦"原子性 + 一致性"契约修复。

---

## R1. 两个连接注册中心的一致性

### R1.1 调用时序(ConnectionManager)

`ConnectionManager.connect/disconnect` 在 `backend/src/common/websocket/base_handler.py:264/311`(基类 `handle_connection` 内)调用,形成 `accept→register→业务→unregister→close` 闭环:
- `connect`(`base_handler.py:63-86`):`websocket.accept()`(L67)→ 加锁写 `active_connections[scenario][session_id]`(L73)→ 踢旧 `_close_replaced_websocket`(L76)→ 发 `connected` ack(L79)
- `disconnect`(`base_handler.py:97-104`):加锁 `pop`(L101),在 `finally`(L311)执行
- `_close_replaced_websocket`(`base_handler.py:88-95`):对旧 ws `close(code=1012)`,**无锁**,仅查 `client_state`

### R1.2 SessionManager 调用点(非死代码)

`register_session`/`unregister_session` 在 **3 个 router** 显式调用,均在 `handle_connection` **之外、之前**:
- `backend/src/websocket_routes.py:188/201`(presentation):`register` → `handle_connection`(L194)→ `finally: unregister`(L201)
- `backend/src/sales_bot/websocket/router.py:459/468`:同构
- `backend/src/curriculum_practice/websocket/router.py:278/289`:同构

**关键时序错位**:`SessionManager.register` 发生在 `handle_connection` 之前,`ConnectionManager.connect` 在 `handle_connection` 内部(L264)。存在窗口:`SessionManager` 已注册 handler,但 `ConnectionManager` 还没注册 ws(此时若另一个同 session 连接进来,`ConnectionManager` 看不到前一个)。

### R1.3 不一致场景

- **异常断开**:`handle_connection` 抛异常 → `finally` 仍跑 `manager.disconnect` + router `finally` 跑 `unregister_session`,**两者都清理**(一致)。
- **并发同 session**:A 连接进行中(`ConnectionManager` 有 A),B 进入同 session:router 先 `register_session(B)`(覆盖 A 的 handler,`session_manager.py:113` 直接赋值),再 `handle_connection(B)` 内 `manager.connect` 覆盖 ws(`base_handler.py:73`),并 `_close_replaced_websocket(A)`。**问题**:`ConnectionManager` 踢 A 的 ws,但 `SessionManager.sessions` 已被 B 覆盖,A 的 router `finally` 异步跑 `unregister_session(session_id)` 会**按 session_id 删,不区分 handler**,误删 B 的注册(`unregister_session` `session_manager.py:135-149` 按 session_id 删,不校验 handler 是否匹配)。**这是真实不一致**。
- **进程重启**:见 R2.3。

### R1.4 原子性

`_close_replaced_websocket`(L88-95,**无锁**)与 `SessionManager.register`(L113,无锁直接 dict 赚值)**非原子**。旧连接被踢后其 router `finally` 异步跑 `unregister_session(session_id)`,可能误删新连接的注册。

---

## R2. 重连恢复路径的 race

### R2.1 竞态存在,无防护

`handle_connection` 开头(`base_handler.py:257-273`):
```python
existing_state = await self.state_service.get_state(session_id)  # L258
is_reconnection = existing_state.is_success and existing_state.value is not None  # L259
...
if existing_state.value is not None and is_reconnection:  # L271
    await self._restore_session_state(existing_state.value)  # L273
```
`state_service.get_state`(`session_state_service.py:280`)从 redis 读,**无锁/无版本号**。两个连接同时进来,都读到 `existing_state=true` → 都走 `_restore_session_state`。`_restore_session_state` 子类覆盖(`stepfun_realtime_handler.py:713`、`presentation_handler.py:236`)写入 handler 内存字段(`turn_count`/`ai_state`/`runtime_state`),无幂等保护。

**StepFun 变体**(`stepfun_realtime_handler.py:802-902`)有额外恢复逻辑(`_load_effective_policy` + `_initialize_curriculum_stage_runtime`),同样无并发锁。

### R2.2 顺序不确定

重连恢复(L273,在 `manager.connect` L264 之后)与"新连接踢旧连接"(L76,在 `manager.connect` 内)交叉:新连接的 `connect` 会踢旧 ws,但旧连接的 `_restore_session_state` 可能尚未完成(异步)。旧连接清理(`finally` L308-312)与新连接恢复**无确定性顺序**。

### R2.3 进程重启残留

`describe_authority`(`session_manager.py:305-321`)明确声明:
- `connection_registry`:`process_memory`,`survives_restart=False`
- `session_snapshot`:`redis_snapshot`,`survives_restart=True`

进程重启后:连接丢(ConnectionManager/SessionManager 均空),但 redis snapshot 在。客户端重连时 `get_state` 返回旧 snapshot → `_restore_session_state` 恢复字段。**风险**:`_restore_session_state` 子类(如 `stepfun_realtime_handler.py:713`)恢复 `turn_count`/`session_status`/`curriculum_stage_runtime`,但**不恢复**上游 StepFun WS 连接(`_connect_upstream` 在 `stepfun_realtime_handler.py:882` 单独建新连接)、不恢复 `message_queue`/`processing_task`(`base_handler.py:267/278` 重建)。状态"半恢复"——业务字段在但运行时上下文是新的,可能导致 turn_count 与实际 StepFun 会话不同步。**未找到证据**表明有版本号校验防止恢复过期 snapshot(`base_handler._create_state_snapshot` L443-447 未写入 version 字段)。

---

## R3. send_json 静默吞错的影响面

### R3.1 调用点分布(grep 全仓,排除测试)

`manager.send_json` 在源码中 **约 35 处**调用(非 prd 所述 10 处,实际更多)。按性质:

| 类别 | 位置示例 | 用户可见? |
|---|---|---|
| 控制消息 | `base_handler.py:79`(connected ack)、`293`(heartbeat)、`344`(backpressure) | 否(协议层) |
| 用户可见消息 | `base_handler.py:424`(send_error)、`481`(reconnected) | 是 |
| 业务消息 | `stepfun_realtime_upstream.py:718/866/900/1470/1506/1687/2329/2389`、`feedback.py:254/296/308/380`、`sales_stage.py:291/408/415/426/433` | 是(AI 回复/评分/反馈) |
| 组件消息 | `components/tts_component.py:142/245/297`、`capability_processor.py:381/405/423/441/459` | 是(TTS/能力) |

### R3.2 吞错后果

`send_json`(`base_handler.py:106-115`):`except Exception` 仅 `logger.error`,**不传播、不返回失败标志**。调用方继续执行,状态机**以为消息已发出**。

- **性质判定**:**可用性 bug + 正确性 bug 混合**。对心跳/backpressure(控制消息)是可用性 bug(用户无感,下次心跳补);对 AI 回复/评分(业务消息)是**正确性 bug**——状态机推进了 `turn_count` 但用户没收到回复,导致后续 turn 错位(与 R2.3 半恢复同源)。

### R3.3 反模式对照

AGENTS.md §VII.6「AI 生成的防御性代码而无契约与测试」——`send_json` 的 `except Exception` 吞错**符合该反模式**:无契约(不声明失败语义)、无重试、无降级指令、调用方无法区分成功失败。属于宪法 §I「可恢复故障用状态条/故障面板非阻塞反馈」的**未完成实现**——应返回 `Result.fail("[WS_SEND_FAILED]")` 让调用方决策。

---

## R4. 风险定级与修复建议

| 风险面 | 定级 | 理由 |
|---|---|---|
| R1 注册中心不一致 | 🟡关注 | 并发同 session 偶发,`unregister_session` 按 id 删可能误删新连接;异常断开路径一致 |
| R2 重连 race | 🟡关注 | 无锁无版本号,双连接同读 existing_state 可双恢复;进程后半恢复是设计已知(见 describe_authority)非 bug |
| R3 send_json 吞错 | 🟡关注 | 控制消息影响小,业务消息导致 turn 错位;35 处调用面广 |

### 修复建议(均未触及 prd 排除的 upstream.py 事件路由深查)

- **R1**:最小契约修复——`unregister_session` 增加 handler 身份校验(对比 `session_info.handler is handler` 再删),避免误删新连接。**未触及入口**:3 个 router 的 `register` 时序错位(注册在 handle_connection 之前)可暂不动,因不影响正确性,仅影响统计窗口。
- **R2**:最小契约修复——`SessionStateSnapshot` 增加 `version`/`connection_epoch` 字段,`_restore_session_state` 校验版本号,过期则跳过恢复。**未触及入口**:`_connect_upstream` 重建上游 WS 不改(设计正确)。
- **R3**:症状缓解优先——`send_json` 返回 `Result[None]`,调用方按消息性质决策(控制消息忽略,业务消息触发状态回滚或重发)。**未触及入口**:`stepfun_realtime_upstream.py` 2758 行事件路由不在本任务范围(prd 明确排除)。

### 是否建修复任务

**是,建议建 P1 修复任务**(非 P0 阻断)。理由:
1. 三个风险面均有真实代码缺陷证据(file:line 已附);
2. 均为偶发非阻断,但并发/重连场景下会导致 turn 错位、连接误删;
3. 修复方案均为"最小契约修复",不涉及大重构;
4. prd 已明确"看完报告再决定是否建修复任务",本报告结论支持建任务。

**优先级排序**:R3 > R1 > R2(R3 影响面最广 35 处调用且修法清晰;R1 修复最简单;R2 涉及 snapshot schema 变更需配套迁移)。

---

## Caveats / Not Found

- 未深查 `stepfun_realtime_upstream.py`(2758 行)内 send_json 调用的具体业务语义(prd 明确排除);
- 未运行并发压测验证 race 实际触发概率,定级基于代码静态分析;
- `SessionStateSnapshot` 是否已有隐式版本字段未完整核查(仅确认 `base_handler._create_state_snapshot` L443-447 未写入 version)。

---

## 关键文件路径(供后续修复任务参考)

- `backend/src/common/websocket/base_handler.py`(ConnectionManager + handle_connection + send_json)
- `backend/src/common/websocket/session_manager.py`(SessionManager + describe_authority)
- `backend/src/common/websocket/session_state_service.py`(redis snapshot)
- `backend/src/websocket_routes.py`(presentation router, L188/201)
- `backend/src/sales_bot/websocket/router.py`(L459/468)
- `backend/src/curriculum_practice/websocket/router.py`(L278/289)
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`(L713/802-902 重连恢复)
