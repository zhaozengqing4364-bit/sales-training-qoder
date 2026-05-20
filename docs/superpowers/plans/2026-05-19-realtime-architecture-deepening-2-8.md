# 实时架构深化实施计划 (Items 2–8)

> 计划路径：`docs/superpowers/plans/2026-05-19-realtime-architecture-deepening-2-8.md`
> 创建时间：2026-05-19
> 架构主语：`training_runtime`（保持 `StepFunTransport` 为共享 Deep Module）

---

## 一、审计基线 (Audit Baseline)

### Item 1 — StepFunTransport Deep Module（已完成部分）

| 接口 | 状态 | 说明 |
|------|------|------|
| `connect()` | ✅ 已适配 | handler 已委托 transport |
| `close()` | ✅ 已适配 | handler 已委托 transport |
| `send_json()` | ⚠️ 存在但未集成 | handler 仍直接调用 `upstream_ws.send_json()` |
| `check_health()` | ⚠️ 存在但未集成 | handler 未使用统一 ping/pong 检查 |
| `decide_backpressure()` | ⚠️ 存在但未集成 | handler 的 `_send_audio_append()` 内联重复背压逻辑 |

### Items 2–8 现状汇总

| Item | 名称 | 状态 | 关键文件 |
|------|------|------|----------|
| 2 | RealtimeTurnCoordinator | ❌ 未实现 | 无独立模块 |
| 3 | StepFunToolExecutionModule | ❌ 未实现 | 散落在 handler 的 `_tool_*` 方法中 |
| 4 | GroundingDecisionPipeline | ⚠️ 部分存在 | `stepfun_knowledge_helpers.py` 等，但决策管线分散 |
| 5 | SessionControlSeam | ⚠️ 部分存在 | `SessionLifecycleService` 存在，但 handler 内联大量生命周期铺胶代码 |
| 6 | VoiceRuntimeProfile 稳定性策略 | ⚠️ 结构性缺陷 | `VoiceRuntimePolicyService` + `voice_instruction_compiler.py` 存在，但 policy 解析散落在 handler 中 |
| 7 | RealtimeAudioFlowModule | ⚠️ 部分存在 | `stepfun_tts_contracts.py`、`stepfun_asr_fallback.py` 存在，但音频帧管理内联于 handler |
| 8 | StepFunRealtimeHandler 拆分 | ⚠️ 依赖前述 item | 当前单文件 5009 行，是仓库最大文件 |

### 当前代码规模

```
stepfun_realtime_handler.py      5009 行  ← 需拆分
stepfun_realtime_upstream.py     1381 行
stepfun_realtime_feedback.py     1089 行
stepfun_realtime_policy.py        926 行
stepfun_realtime_connection.py    865 行
stepfun_realtime_sales_stage.py   446 行
stepfun_realtime_state.py         148 行
components/ 目录                 多个 helper 文件
training_runtime/stepfun_transport.py  198 行  ← Item 1 成果
```

### 测试基线

```
tests/unit/test_stepfun_transport.py        10 passed
tests/unit/test_stepfun_realtime_handler.py 88 passed
其他 stepfun 测试文件                       11 个文件
```

---

## 二、架构术语定义

| 术语 | 含义 |
|------|------|
| **Module** | 一个 `.py` 文件，单一职责，高内聚。提供清晰的 public Interface |
| **Interface** | Module 对外暴露的函数/类签名。Interface 小而深 → Deep Module |
| **Implementation** | Module 内部的具体实现。对外不可见 |
| **Depth** | Interface 简洁但功能强大。调用者无需了解 Implementation 即可使用 |
| **Seam** | 可替换点。允许在不修改调用方的情况下切换 Implementation |
| **Adapter** | 连接两个 Interface 的薄胶水层。不做业务逻辑 |
| **Leverage** | Module 被复用的次数。高 Leverage = 高价值 |
| **Locality** | 修改某个行为时需要触碰的文件数量。越小越好 |

---

## 三、实施原则

1. **不改 WebRTC**：保持 StepFun 实时 WebSocket 为主路径
2. **不大爆炸重写**：每个 phase 产出可独立合并/回滚的 commit
3. **TDD 先行**：先写测试 → 测试失败 → 实现 → 测试通过
4. **接口优先**：先定义 Module Interface，再迁移 Implementation
5. **保持兼容**：每个 phase 结束时 handler 原有行为不受影响

---

## 四、实施阶段总览

| Phase | 名称 | 预期 commits | 风险 |
|-------|------|-------------|------|
| 0 | 基线验证 | 0（仅验证） | 低 |
| 1 | Item 1 收尾：Transport 接口全集成 | 1 | 低 |
| 2 | Item 2：RealtimeTurnCoordinator | 1 | 中 |
| 3 | Item 3：StepFunToolExecutionModule | 1 | 中 |
| 4 | Item 4：GroundingDecisionPipeline | 2 | 中 |
| 5 | Item 5：SessionControlSeam | 1 | 中 |
| 6 | Item 6：VoiceRuntimeProfile 稳定性策略 | 1 | 中 |
| 7 | Item 7：RealtimeAudioFlowModule | 1 | 中 |
| 8 | Item 8：StepFunRealtimeHandler 拆分 | 2 | 高 |
| 9 | 最终验证波 | 1 | 低 |

---

## 五、Phase 0：基线验证

**目标：** 确认当前测试套件全部通过，建立回滚基线。

### 文件

- 验证范围：全部 stepfun 相关测试 + transport 测试

### 验证命令

```bash
# 1. 运输层单元测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_transport.py -q --no-cov

# 2. handler 单元测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# 3. 所有 stepfun 相关测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# 4. lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/training_runtime/stepfun_transport.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet

# 5. 集成测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/integration/test_emotion_flow.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py -q --no-cov
```

- [ ] **Phase 0-1**：运行 transport 单元测试，确认 `10 passed`
- [ ] **Phase 0-2**：运行 handler 单元测试，确认 `88 passed`
- [ ] **Phase 0-3**：运行所有 stepfun 相关单元测试，全部通过
- [ ] **Phase 0-4**：运行 lint，`All checks passed!`
- [ ] **Phase 0-5**：运行集成测试，全部通过
- [ ] **Phase 0-6**：记录基线到 `notepad/learnings.md`

---

## 六、Phase 1：Item 1 收尾 — Transport 接口全集成

**目标：** 将 handler 中 `send_json`、`check_health`、`decide_backpressure` 的调用全部委托给 `StepFunTransport`。

### Module 设计

```
StepFunTransport (Module, 已存在)
├── connect(api_key, url, model) → WebSocket          Interface
├── close(upstream_ws) → None                          Interface
├── send_json(upstream_ws, payload) → SendResult       Interface ← 本次集成
├── check_health(upstream_ws, timeout) → HealthResult  Interface ← 本次集成
└── decide_backpressure(payload, pending_bytes, policy) → BackpressureResult  Interface ← 本次集成
```

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |
| 修改 | `backend/tests/unit/test_stepfun_transport.py`（补充集成测试） |

### TDD 垂直切片

- [ ] **Phase 1-1**：编写 `test_handler_send_upstream_delegates_to_transport_send_json` —— 失败（handler 未委托）
- [ ] **Phase 1-2**：编写 `test_handler_health_check_delegates_to_transport` —— 失败
- [ ] **Phase 1-3**：编写 `test_handler_audio_backpressure_delegates_to_transport` —— 失败
- [ ] **Phase 1-4**：替换 handler 中 `upstream_ws.send_json()` → `self._stepfun_transport.send_json(upstream_ws, payload)`
- [ ] **Phase 1-5**：替换 handler 中内联 ping/pong → `self._stepfun_transport.check_health(upstream_ws, timeout=...)`
- [ ] **Phase 1-6**：替换 handler 中 `_send_audio_append()` 内背压逻辑 → `self._stepfun_transport.decide_backpressure(...)`
- [ ] **Phase 1-7**：运行运输层测试确认通过
- [ ] **Phase 1-8**：运行 handler 测试确认 `>= 88 passed`
- [ ] **Phase 1-9**：运行 lint
- [ ] **Phase 1-10**：提交 `refactor: integrate transport send_json/check_health/decide_backpressure into handler`

### 验证命令

```bash
# 运输层测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_transport.py -q --no-cov

# handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/training_runtime/stepfun_transport.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

### 风险控制

- 运输层接口已存在且有 10 个测试保护
- 替换是纯委托，不改变业务逻辑
- 若回退，`git revert` 单一 commit 即可恢复

---

## 七、Phase 2：Item 2 — RealtimeTurnCoordinator

**目标：** 从 handler 中抽出对话轮次管理逻辑，形成独立的 `RealtimeTurnCoordinator` Module。

### Module 设计

```
RealtimeTurnCoordinator (新建 Module)
├── start_turn(turn_id) → None                        Interface
├── end_turn(turn_id) → None                          Interface
├── is_speaking() → bool                              Interface
├── get_current_turn() → TurnState | None             Interface
├── on_user_audio_start() → None                      Interface
├── on_user_audio_stop() → None                       Interface
├── on_model_response_start() → None                  Interface
├── on_model_response_done() → None                   Interface
└── reset() → None                                    Interface
```

### 文件

| 操作 | 文件 |
|------|------|
| 新建 | `backend/src/sales_bot/websocket/realtime_turn_coordinator.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 新建 | `backend/tests/unit/test_realtime_turn_coordinator.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片

- [ ] **Phase 2-1**：新建 `test_realtime_turn_coordinator.py`，编写状态机测试
  - `test_start_turn_creates_turn_with_id`
  - `test_end_turn_clears_current_turn`
  - `test_is_speaking_true_during_model_response`
  - `test_is_speaking_false_after_response_done`
  - `test_concurrent_turn_rejected`
  - `test_reset_clears_all_state`
- [ ] **Phase 2-2**：运行测试，全部失败
- [ ] **Phase 2-3**：实现 `RealtimeTurnCoordinator` 类
  - 内部状态：`_current_turn_id`、`_is_user_speaking`、`_is_model_responding`
  - 使用 `asyncio.Lock` 保护并发
- [ ] **Phase 2-4**：运行协调器测试，全部通过
- [ ] **Phase 2-5**：编写 `test_handler_delegates_turn_management_to_coordinator` —— 失败
- [ ] **Phase 2-6**：在 handler `__init__` 中加入 `self._turn_coordinator = RealtimeTurnCoordinator()`
- [ ] **Phase 2-7**：替换 handler 中轮次相关的内联逻辑为协调器委托
- [ ] **Phase 2-8**：运行 handler 测试 + 协调器测试，全部通过
- [ ] **Phase 2-9**：运行 lint
- [ ] **Phase 2-10**：提交 `refactor: extract realtime turn coordinator module`

### 验证命令

```bash
# 协调器测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_realtime_turn_coordinator.py -q --no-cov

# handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/realtime_turn_coordinator.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

---

## 八、Phase 3：Item 3 — StepFunToolExecutionModule

**目标：** 将 handler 中的 tool 执行逻辑（`_tool_search_internal_knowledge`、`_enforce_stepfun_tool_guardrails`、`_build_stepfun_tools_from_policy` 等）抽出为独立 Module。

### Module 设计

```
StepFunToolExecutionModule (新建 Module)
├── build_tools_from_policy(policy, persona) → list[dict]      Interface
├── execute_tool(tool_call, context) → ToolResult              Interface
├── enforce_guardrails(tools, policy) → list[dict]             Interface
├── build_tool_response(tool_call_id, result) → dict           Interface
└── build_tool_error_response(tool_call_id, error) → dict       Interface
```

### 文件

| 操作 | 文件 |
|------|------|
| 新建 | `backend/src/sales_bot/websocket/stepfun_tool_execution.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 新建 | `backend/tests/unit/test_stepfun_tool_execution.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片

- [ ] **Phase 3-1**：新建 `test_stepfun_tool_execution.py`，编写测试
  - `test_build_tools_from_policy_with_knowledge_tool`
  - `test_build_tools_from_policy_without_knowledge_returns_empty`
  - `test_enforce_guardrails_removes_disallowed_tool`
  - `test_execute_tool_search_internal_knowledge`
  - `test_build_tool_response_with_content`
  - `test_build_tool_error_response_with_error_message`
- [ ] **Phase 3-2**：运行测试，全部失败
- [ ] **Phase 3-3**：实现 `StepFunToolExecutionModule`
  - 从 handler 和 `components/stepfun_tool_helpers.py`、`components/stepfun_internal_knowledge_searcher.py` 迁移逻辑
  - 保持对 `KnowledgeService` 的 Seam（通过 factory 注入）
- [ ] **Phase 3-4**：运行工具执行测试，全部通过
- [ ] **Phase 3-5**：编写 `test_handler_delegates_tool_execution_to_module` —— 失败
- [ ] **Phase 3-6**：在 handler 中注入并使用 `StepFunToolExecutionModule`
- [ ] **Phase 3-7**：运行 handler 测试 + 工具执行测试，全部通过
- [ ] **Phase 3-8**：运行 lint
- [ ] **Phase 3-9**：提交 `refactor: extract stepfun tool execution module`

### 验证命令

```bash
# 工具执行测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_tool_execution.py -q --no-cov

# handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/stepfun_tool_execution.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

---

## 九、Phase 4：Item 4 — GroundingDecisionPipeline

**目标：** 将知识库检索决策管线从 handler 和分散的 helper 中收敛为单一 Deep Module。

### Module 设计

```
GroundingDecisionPipeline (新建 Module)
├── evaluate(query, context) → GroundingDecision              Interface
├── retrieve(decision, kb_ids) → KnowledgeRetrievalResult     Interface
├── build_instruction_overlay(decision) → str                 Interface
├── build_blocked_response(decision) → str                    Interface
└── extract_diagnostics(decision, retrieval) → dict             Interface
```

### 当前分散状态

- `stepfun_knowledge_helpers.py` — 知识检索辅助
- `stepfun_internal_knowledge_searcher.py` — 内部知识搜索
- `common/knowledge/kb_lock_guard.py` — KB 锁定守卫
- handler 的 `_evaluate_kb_lock_decision()` / `_maybe_start_kb_lock_warmup()` — 内联逻辑

### 文件

| 操作 | 文件 |
|------|------|
| 新建 | `backend/src/sales_bot/websocket/grounding_decision_pipeline.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 新建 | `backend/tests/unit/test_grounding_decision_pipeline.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |
| 修改 | `backend/tests/unit/test_stepfun_knowledge_helpers.py`（委托测试） |

### TDD 垂直切片 (Part A: Pipeline 本身)

- [ ] **Phase 4-1**：新建 `test_grounding_decision_pipeline.py`，编写管线测试
  - `test_evaluate_returns_retrieve_when_kb_ids_present`
  - `test_evaluate_returns_skip_when_no_kb_ids`
  - `test_evaluate_returns_block_when_answerability_low`
  - `test_retrieve_fetches_from_knowledge_service`
  - `test_build_instruction_overlay_includes_kb_context`
  - `test_build_blocked_response_includes_explanation`
  - `test_extract_diagnostics_includes_confidence_scores`
  - `test_pipeline_end_to_end_retrieve_and_ground`
- [ ] **Phase 4-2**：运行测试，全部失败
- [ ] **Phase 4-3**：实现 `GroundingDecisionPipeline`
  - 接受 `knowledge_service_factory` Seam
  - 整合 `kb_lock_guard` 的三阶段决策（evaluate → retrieve → ground）
- [ ] **Phase 4-4**：运行管线测试，全部通过

### TDD 垂直切片 (Part B: Handler 集成)

- [ ] **Phase 4-5**：编写 `test_handler_delegates_knowledge_grounding_to_pipeline` —— 失败
- [ ] **Phase 4-6**：在 handler 中注入 `GroundingDecisionPipeline`
- [ ] **Phase 4-7**：替换 handler 中的 `_evaluate_kb_lock_decision` 和知识检索逻辑
- [ ] **Phase 4-8**：运行 handler 测试 + 管线测试 + 知识 helper 测试，全部通过
- [ ] **Phase 4-9**：运行 lint
- [ ] **Phase 4-10**：提交 `refactor: extract grounding decision pipeline`
- [ ] **Phase 4-11**：提交 `refactor: integrate grounding pipeline into handler`

### 验证命令

```bash
# 管线测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_grounding_decision_pipeline.py -q --no-cov

# handler + 知识测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py -q --no-cov

# lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/grounding_decision_pipeline.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

---

## 十、Phase 5：Item 5 — SessionControlSeam

**目标：** 将 handler 中 session 生命周期管理（start / pause / resume / end / transition validation）整合为可注入的 Seam。

### Seam 设计

```
SessionControlSeam (Interface / Protocol)
├── start_session(session_id) → SessionState              Interface
├── pause_session(session_id) → SessionState              Interface
├── resume_session(session_id) → SessionState             Interface
├── end_session(session_id) → SessionState                Interface
├── validate_transition(from_state, action) → bool        Interface
└── get_current_state(session_id) → SessionState          Interface
```

### 现状

- `SessionLifecycleService` 已存在（`common/db/session_lifecycle.py`）
- handler 中存在大量生命周期铺胶代码：`_handle_start_command`、`_handle_end_command`、pause/resume 状态切换
- 铺胶代码与 handler 业务逻辑耦合

### 文件

| 操作 | 文件 |
|------|------|
| 新建 | `backend/src/sales_bot/websocket/session_control_adapter.py`（Adapter） |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 新建 | `backend/tests/unit/test_session_control_adapter.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片

- [ ] **Phase 5-1**：新建 `test_session_control_adapter.py`，编写测试
  - `test_start_session_delegates_to_lifecycle_service`
  - `test_end_session_delegates_to_lifecycle_service`
  - `test_validate_transition_allows_valid_sequence`
  - `test_validate_transition_rejects_invalid_sequence`
- [ ] **Phase 5-2**：运行测试，全部失败
- [ ] **Phase 5-3**：实现 `SessionControlAdapter`
  - 封装 `SessionLifecycleService` 调用
  - 提供同步化的 Interface 给 handler
- [ ] **Phase 5-4**：运行适配器测试，全部通过
- [ ] **Phase 5-5**：编写 `test_handler_delegates_session_control_to_adapter` —— 失败
- [ ] **Phase 5-6**：在 handler 中注入 `SessionControlAdapter`
- [ ] **Phase 5-7**：替换 handler 中的 session lifecycle 铺胶代码
- [ ] **Phase 5-8**：运行 handler 测试 + 适配器测试，全部通过
- [ ] **Phase 5-9**：运行 lint
- [ ] **Phase 5-10**：提交 `refactor: extract session control adapter seam`

### 验证命令

```bash
# 适配器测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_session_control_adapter.py -q --no-cov

# handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/session_control_adapter.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

---

## 十一、Phase 6：Item 6 — VoiceRuntimeProfile 稳定性策略

**目标：** 将 VoiceRuntimePolicy 的解析、编译、验证逻辑从 handler 中收敛，引入不变的 policy snapshot 契约。

### 当前问题

- `VoiceRuntimePolicyService` 编译 policy，但 handler 在多处重新解析 policy 字段
- `voice_instruction_compiler.py` 存在但 handler 内联重复 instruction 构建
- policy snapshot 在 handler 中散落为 `_effective_policy` dict，类型不安全

### Seam 设计

```
VoiceRuntimeProfile (新建 Immutable Value Object)
├── voice_mode: str
├── model_name: str
├── voice_name: str
├── temperature: float
├── instructions: str
├── instruction_contract_hash: str
├── knowledge_base_ids: list[str]
├── tool_policy: dict
└── validate() → bool       Interface
```

### 文件

| 操作 | 文件 |
|------|------|
| 新建 | `backend/src/sales_bot/websocket/voice_runtime_profile.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 新建 | `backend/tests/unit/test_voice_runtime_profile.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片

- [x] **Phase 6-1**：新建 `test_voice_runtime_profile.py`，编写测试
  - `test_validate_rejects_empty_instructions`
  - `test_validate_accepts_valid_profile`
  - `test_from_policy_snapshot_parses_all_fields`
  - `test_instruction_contract_hash_is_immutable`
  - `test_equality_by_value_not_identity`
- [x] **Phase 6-2**：运行测试，全部失败
- [x] **Phase 6-3**：实现 `VoiceRuntimeProfile`（`@dataclass(frozen=True)`）
- [x] **Phase 6-4**：运行 profile 测试，全部通过
- [x] **Phase 6-5**：编写 `test_handler_uses_voice_runtime_profile_instead_of_raw_dict` —— 失败
- [x] **Phase 6-6**：替换 handler 中 `_effective_policy` dict 的使用为 `VoiceRuntimeProfile`
- [x] **Phase 6-7**：运行 handler 测试 + profile 测试，全部通过
- [x] **Phase 6-8**：运行 lint
- [ ] **Phase 6-9**：提交 `refactor: introduce immutable voice runtime profile value object`

### 验证命令

```bash
# profile 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_voice_runtime_profile.py -q --no-cov

# handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/voice_runtime_profile.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

---

## 十二、Phase 7：Item 7 — RealtimeAudioFlowModule

**目标：** 将音频帧管理（输入缓冲、输出缓冲、编码/解码、ASR fallback、TTS 契约）从 handler 中抽出。

### Module 设计

```
RealtimeAudioFlowModule (新建 Module)
├── append_input_audio(audio_bytes) → None          Interface
├── get_input_buffer() → bytes                      Interface
├── commit_input_audio() → None                      Interface
├── clear_input_audio() → None                       Interface
├── append_output_audio(audio_bytes) → None          Interface
├── drain_output_audio() → list[bytes]              Interface
├── clear_output_audio() → None                      Interface
└── is_backpressure_applied() → bool                 Interface
```

### 文件

| 操作 | 文件 |
|------|------|
| 新建 | `backend/src/sales_bot/websocket/realtime_audio_flow.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 新建 | `backend/tests/unit/test_realtime_audio_flow.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片

- [x] **Phase 7-1**：新建 `test_realtime_audio_flow.py`，编写测试
  - `test_append_input_audio_adds_to_buffer`
  - `test_commit_input_audio_clears_and_returns`
  - `test_clear_input_audio_empties_buffer`
  - `test_append_output_audio_adds_to_buffer`
  - `test_drain_output_audio_returns_all_and_clears`
  - `test_backpressure_when_buffer_exceeds_threshold`
  - `test_no_backpressure_when_buffer_below_threshold`
  - `test_thread_safety_with_concurrent_appends`
- [x] **Phase 7-2**：运行测试，全部失败
- [x] **Phase 7-3**：实现 `RealtimeAudioFlowModule`
  - 使用 `asyncio.Queue` 或 `collections.deque` + `asyncio.Lock`
  - 集成 transport 的 `decide_backpressure`
- [x] **Phase 7-4**：运行音频流测试，全部通过
- [x] **Phase 7-5**：编写 `test_handler_delegates_audio_flow_to_module` —— 失败
- [x] **Phase 7-6**：在 handler 中注入 `RealtimeAudioFlowModule`
- [x] **Phase 7-7**：替换 handler 中的 `_send_audio_append()`、`_receive_audio_append()`、input/output buffer 管理
- [x] **Phase 7-8**：运行 handler 测试 + 音频流测试，全部通过
- [x] **Phase 7-9**：运行 lint
- [ ] **Phase 7-10**：提交 `refactor: extract realtime audio flow module`

### 验证命令

```bash
# 音频流测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_realtime_audio_flow.py -q --no-cov

# handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/realtime_audio_flow.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

---

## 十三、Phase 8：Item 8 — StepFunRealtimeHandler 拆分

**目标：** 将 5009 行的 handler 拆分为多个内聚模块，handler 本身变为薄编排层。

**前置条件：** Phase 1–7 全部完成（所有子模块已抽出并独立验证）

### 拆分后的目标架构

```
StepFunRealtimeHandler (薄编排层，<800 行)
├── StepFunTransport              ← Item 1 已抽
├── RealtimeTurnCoordinator       ← Item 2 已抽
├── StepFunToolExecutionModule    ← Item 3 已抽
├── GroundingDecisionPipeline     ← Item 4 已抽
├── SessionControlAdapter         ← Item 5 已抽
├── VoiceRuntimeProfile           ← Item 6 已抽 (Value Object)
├── RealtimeAudioFlowModule       ← Item 7 已抽
├── stepfun_realtime_connection   ← 已有独立文件
├── stepfun_realtime_state        ← 已有独立文件
├── stepfun_realtime_upstream     ← 已有独立文件 (部分需重新审视)
├── stepfun_realtime_feedback     ← 已有独立文件
├── stepfun_realtime_policy       ← 已有独立文件
└── stepfun_realtime_sales_stage  ← 已有独立文件
```

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`（大幅缩减） |
| 审查 | `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`（内部逻辑是否需要适配新 Modules） |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py`（更新 mock 路径） |

### TDD 垂直切片 (Part A: 清理 handler)

- [x] **Phase 8-1**：确认所有子模块测试仍然通过
- [x] **Phase 8-2**：从 handler 中移除所有已迁移到子模块的死代码
  - 移除内联的 turn 管理逻辑
  - 移除内联的 tool 执行逻辑
  - 移除内联的知识检索逻辑
  - 移除内联的 session lifecycle 铺胶
  - 移除内联的 policy dict 解析
  - 移除内联的音频缓冲管理
- [x] **Phase 8-3**：运行 handler 测试，确认全部通过且 handler 行数显著减少
- [ ] **Phase 8-4**：提交 `refactor: slim down stepfun realtime handler after module extraction`

### TDD 垂直切片 (Part B: 重新审视 upstream 模块)

- [x] **Phase 8-5**：审查 `stepfun_realtime_upstream.py`（1381 行）是否需要在新的模块架构下重构
- [x] **Phase 8-6**：若 `upstream` 模块中有重复逻辑（如连接管理、事件分发），收敛到对应新 Module
- [x] **Phase 8-7**：运行全量测试
- [ ] **Phase 8-8**：提交 `refactor: align upstream module with new realtime architecture`

### 验证命令

```bash
# 全量 StepFun 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# handler 行数检查
wc -l backend/src/sales_bot/websocket/stepfun_realtime_handler.py

# lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/ --quiet
```

---

## 十四、Phase 9：最终验证波

**目标：** 全量回归验证，确认所有行为未被破坏。

### 验证矩阵

- [x] **Phase 9-1**：所有 StepFun 单元测试
- [x] **Phase 9-2**：所有 training_runtime 单元测试
- [x] **Phase 9-3**：Presentation 单元测试
- [x] **Phase 9-4**：集成测试（emotion flow / reconnect / websocket status）
- [x] **Phase 9-5**：全量单元测试
- [x] **Phase 9-6**：lint 全量
- [x] **Phase 9-7**：type check（mypy）对触及的模块
- [x] **Phase 9-8**：handler 行数报告（目标 <800 行）

### 验证命令

```bash
# 1. StepFun 层
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# 2. Transport 层
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_transport.py -q --no-cov

# 3. Training runtime
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_training_runtime_plugins.py -q --no-cov

# 4. Presentation
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_presentation_stepfun_realtime_handler.py -q --no-cov

# 5. 集成
cd backend && PYTHONPATH=src uv run python -m pytest tests/integration/test_emotion_flow.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py -q --no-cov

# 6. 全量单元
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/ -q --no-cov

# 7. Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/ src/training_runtime/ src/presentation_coach/websocket/ --quiet

# 8. MyPy
cd backend && PYTHONPATH=src uv run python -m mypy src/sales_bot/websocket/ src/training_runtime/ src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py

# 9. Handler 行数
wc -l backend/src/sales_bot/websocket/stepfun_realtime_handler.py
```

---

## 十五、回滚策略

每个 Phase 产出独立 commit。若某 Phase 出现问题：

| Phase | 回滚方式 | 影响范围 |
|-------|----------|----------|
| 0 | 无操作 | 仅验证 |
| 1 | `git revert <commit>` | 恢复 handler 内联 transport 调用 |
| 2–7 | `git revert <commit>` | 恢复对应子模块内联在 handler 中 |
| 8 | `git revert <commit>` | 恢复 handler 为拆分前状态 |
| 9 | 无操作 | 仅验证 |

不采用大爆炸重构，每个 Phase 可独立进退。

---

## 十六、风险矩阵

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 音频帧协议被破坏 | 高 | Phase 7 着重验证音频缓冲行为；集成测试保护端到端流程 |
| handler 拆分导致 import 循环 | 中 | 子模块依赖方向：handler → modules，modules 不反向依赖 handler |
| Session 生命周期状态不一致 | 中 | Phase 5 Adapter 封装 `SessionLifecycleService`，保持其转换逻辑不变 |
| Presentation handler 继承链断裂 | 中 | `PresentationStepFunRealtimeHandler` 继承 `StepFunRealtimeHandler`，每次修改后运行 Presentation 测试 |
| 测试 mock 路径过时 | 低 | 每个 Phase 都包含 handler 测试更新；TDD 先暴露问题 |

---

## 十七、文件变更总览

### 新建文件 (9 个)

```
backend/src/sales_bot/websocket/realtime_turn_coordinator.py
backend/src/sales_bot/websocket/stepfun_tool_execution.py
backend/src/sales_bot/websocket/grounding_decision_pipeline.py
backend/src/sales_bot/websocket/session_control_adapter.py
backend/src/sales_bot/websocket/voice_runtime_profile.py
backend/src/sales_bot/websocket/realtime_audio_flow.py
backend/tests/unit/test_realtime_turn_coordinator.py
backend/tests/unit/test_stepfun_tool_execution.py
backend/tests/unit/test_grounding_decision_pipeline.py
backend/tests/unit/test_session_control_adapter.py
backend/tests/unit/test_voice_runtime_profile.py
backend/tests/unit/test_realtime_audio_flow.py
```

### 修改文件

```
backend/src/sales_bot/websocket/stepfun_realtime_handler.py  （主要修改对象，大幅缩减）
backend/tests/unit/test_stepfun_realtime_handler.py           （更新测试）
backend/tests/unit/test_stepfun_transport.py                   （补充集成测试）
backend/tests/unit/test_stepfun_knowledge_helpers.py           （委托测试）
```

---

## 十八、不可触碰区域

- ❌ `backend/src/curriculum_practice/websocket/router.py`（已有未提交修改）
- ❌ `backend/tests/unit/test_examiner_websocket_router.py`（已有未提交修改）
- ❌ `CONTEXT.md`（已有未提交修改）
- ❌ WebRTC 相关代码
- ❌ `backend/src/sales_bot/websocket/router.py` 的 plugin selection 逻辑（Item 1 已落地）
- ❌ `backend/src/websocket_routes.py` 的 Presentation 路由逻辑（Item 1 已落地）

---

## 十九、提交策略

```
Phase 0:  无 commit
Phase 1:  refactor: integrate transport send_json/check_health/decide_backpressure into handler
Phase 2:  refactor: extract realtime turn coordinator module
Phase 3:  refactor: extract stepfun tool execution module
Phase 4a: refactor: extract grounding decision pipeline
Phase 4b: refactor: integrate grounding pipeline into handler
Phase 5:  refactor: extract session control adapter seam
Phase 6:  refactor: introduce immutable voice runtime profile value object
Phase 7:  refactor: extract realtime audio flow module
Phase 8a: refactor: slim down stepfun realtime handler after module extraction
Phase 8b: refactor: align upstream module with new realtime architecture
Phase 9:  test: verify realtime architecture deepening items 2-8
```

共 **12 个原子 commit**，每个 commit 前都有 focused test command 作为守门。

---

## 二十、最终验收标准

- [ ] `stepfun_realtime_handler.py` ≤ 800 行
- [ ] 所有 6 个新建 Module 都有 dedicated 测试文件，覆盖率 ≥ 80%
- [ ] 全部 98+ handler 测试 + 10 transport 测试仍然通过
- [ ] 集成测试（emotion / reconnect / status contract）全部通过
- [ ] lint 零错误
- [ ] mypy 对触及模块零错误
- [ ] 无新增 import 循环
- [ ] `git status --short` 显示仅预期文件被修改
