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

---

## 二十一、第一波回顾与第二波审计基线

### 第一波成就

第一波 Phase 0-9 已于 2026-05-20 完成并验证：

| 指标 | 数值 |
|------|------|
| StepFun 测试 | 209 passed |
| 新模块集合测试 | 55 passed |
| Integration 测试 | 21 passed |
| 全量单元测试 | 1583 passed |
| Handler 行数 | 5021 → 4225（减少 796 行） |
| Mypy 触及模块 | 零错误 |
| 新建 Module 文件 | 6 个 |
| 新建测试文件 | 6 个 |

### 未达标项

- **Handler 行数 4225，距离 <800 目标仍远**。根因：upstream mixin 中的方法与 handler override 存在行为差异，不能靠删除 override 伪装达标。
- 第一波各 Phase 采用 strangler slice 策略：在 handler 中埋入 Module 调用点，但完整行为迁移未完成。

### 第二波审计结论（基于三份后台审计综合）

**Oracle 策略调整**：不再继续单纯抽函数降行数。改为按四类运行时责任 Seam 深化：

1. **Policy Seam**：`VoiceRuntimeProfile` 仍是装饰性值对象，handler 仍在多处绕过 profile 直接读 `_effective_policy` dict。需将 instruction 编译、policy 解析、contract hash 验证收敛到 profile 内。
2. **Tool/Search/Grounding Seam**：`StepFunToolExecutionModule` 未吃下完整 tool routing（重复 tool_call 判定、grounding lookup 触发、tool response cache）。`GroundingDecisionPipeline` 的 `retrieve` / `warmup` / `cache` / `diagnostics` 路径在 handler 中未被充分使用。
3. **Audio Seam**：`RealtimeAudioFlowModule` 输出音频缓冲已测试覆盖，但 handler TTS 输出路径未接入，仍在 handler 内联管理输出 buffer。
4. **Upstream/Handler Residual**：`stepfun_realtime_upstream.py` 中存在大量与 handler override 行为差异的方法（transport、turn coordinator、tool execution、audio flow 四个维度共约 13 个差异方法）。必须先把 canonical behavior 移入深 Module，再逐一删除 wrapper。

**Module Gap 清单**：

| Module | 第一波状态 | 第二波需深化 |
|--------|-----------|-------------|
| `VoiceRuntimeProfile` | 不可变值对象，但 handler 仍绕过它读 raw dict | 收敛 instruction 编译 / policy 解析 / hash 验证 |
| `StepFunToolExecutionModule` | tool build / guardrail / execute，但 routing / cache / grounding 缺失 | 补全 tool_call routing / response cache / grounding trigger |
| `GroundingDecisionPipeline` | evaluate 路径使用，retrieve / warmup / cache / diagnostics 未充分用 | 激活全链路 retrieve → warmup → cache → diagnostics |
| `RealtimeAudioFlowModule` | 输入音频缓冲 + 背压，输出缓冲已测试但未接入 handler | 接入 handler TTS 输出路径 |
| `SessionControlAdapter` | 浅接口，仅封装 `SessionLifecycleService.transition` | 加状态验证 / transition 前后钩子 / 错误恢复 |
| `RealtimeTurnCoordinator` | strangler 埋点，user audio / model response 语义未完全接入 | 补全状态机语义 |
| `stepfun_realtime_handler.py` | 4225 行，大量 override 与 mixin 行为差异 | 逐对齐后安全删除 |

---

## 二十二、第二波实施原则

1. **不再抽函数降行数**：每阶段目标是让 Module 变深，Interface 变有力，不是让 handler 变短。
2. **先深后删**：先把 canonical behavior 迁入深 Module（含测试），验证行为一致，再删除 handler 中对应 override。
3. **四类 Seam 并行可行**：Policy / Tool-Grounding / Audio / Upstream 四个 Seam 的深化相互独立，可被不同 Atlas 并行执行。
4. **测试不变更前端契约**：保持 StepFun payload / frontend WebSocket event shape / binary audio protocol 不变。
5. **每个 Phase 产出独立可回滚 commit**，保持第一波的回滚粒度传统。

---

## 二十三、第二波 Phase 总览

| Phase | 名称 | Seam | 预期 commits | 风险 | 优先级 |
|-------|------|------|-------------|------|--------|
| 10 | VoiceRuntimeProfile → True Policy Deep Module | Policy | 2 | 低 | P0 |
| 11 | StepFunToolExecutionModule 路由/缓存深化 | Tool/Grounding | 2 | 中 | P0 |
| 12 | GroundingDecisionPipeline 全链路激活 | Grounding | 2 | 中 | P1 |
| 13 | RealtimeAudioFlowModule 输出流接入 | Audio | 1 | 中 | P1 |
| 14 | SessionControlAdapter 接口深化 | Session | 1 | 低 | P1 |
| 15 | RealtimeTurnCoordinator 语义补全 | Turn | 1 | 中 | P2 |
| 16 | Handler Residual 安全对齐 | Upstream | 3 | 高 | P2 |
| 17 | 最终验证波 2 | 全局 | 1 | 低 | P3 |

优先级说明：P0 = 低风险高收益先行，P1 = 中等风险逐次推进，P2 = 依赖前置 Phase 完成后执行。

---

## 二十四、Phase 10：VoiceRuntimeProfile → True Policy Deep Module

**目标：** 将 `VoiceRuntimeProfile` 从"装饰性不可变值对象"深化为 Policy Seam 的唯一权威数据源。收敛 instruction 编译、policy 字段解析、contract hash 验证进 profile Module。Handler 不再绕过 profile 直接读 `_effective_policy` dict。

### 当前问题

- `VoiceRuntimeProfile` 已是 `@dataclass(frozen=True)`，但只承载 model / voice / temperature / instructions / hash 字段。
- `voice_instruction_compiler.py` 存在但 handler 内联重复 instruction 构建。
- Handler 在多处（response.create、session.update、policy snapshot 构建）直接读 `_effective_policy` dict 的 `model` / `voice` / `temperature` / `instructions` 字段，完全绕过 profile。
- `contract_hash` 在 profile 中存在但未在 handler 路径中用作校验。

### Module 深化设计

```
VoiceRuntimeProfile (Deepened Module)
├── 构造接口
│   ├── from_policy_snapshot(snapshot: dict) → VoiceRuntimeProfile    Interface (已有)
│   └── from_effective_policy(policy: dict, compiler: ...) → VoiceRuntimeProfile  Interface (新增)
├── 查询接口
│   ├── voice_mode: str                                              Interface (已有)
│   ├── model_name: str                                              Interface (已有)
│   ├── voice_name: str                                              Interface (已有)
│   ├── temperature: float                                           Interface (已有)
│   ├── instructions: str                                            Interface (已有)
│   ├── instruction_contract_hash: str                               Interface (已有)
│   ├── knowledge_base_ids: list[str]                                Interface (已有)
│   ├── tool_policy: FrozenDict                                      Interface (已有)
│   └── connection_health: str                                       Interface (已有)
├── 编译接口（从 voice_instruction_compiler 收敛）
│   ├── compile_instructions(persona, stage, config) → str           Interface (新增)
│   └── verify_contract_hash(instructions, expected_hash) → bool     Interface (新增)
├── 校验接口
│   ├── validate() → bool                                            Interface (已有)
│   ├── validate_instruction_contract() → ContractValidationResult   Interface (新增)
│   └── diff_with(other: VoiceRuntimeProfile) → ProfileDiff          Interface (新增)
└── 稳定性接口
    └── connection_health: str (healthy / degraded / recovering)      Interface (已有)
```

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/voice_runtime_profile.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 修改 | `backend/tests/unit/test_voice_runtime_profile.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片 (Part A: Profile 深化)

- [x] **Phase 10-1**：编写 `test_compile_instructions_includes_persona_and_stage` —— 验证 profile 可从 persona + stage + config 编译完整 instruction 字符串
- [x] **Phase 10-2**：编写 `test_verify_contract_hash_detects_tampering` —— 验证 hash 校验可检测 instruction 篡改
- [x] **Phase 10-3**：编写 `test_validate_instruction_contract_rejects_empty_or_malformed` —— 验证合约级校验
- [x] **Phase 10-4**：编写 `test_diff_with_detects_field_changes` —— 验证 profile diff 可识别任意字段变更
- [x] **Phase 10-5**：运行 profile 测试，确认新增测试失败（待实现）
- [x] **Phase 10-6**：实现 `compile_instructions` / `verify_contract_hash` / `validate_instruction_contract` / `diff_with`
  - `compile_instructions` 从 `voice_instruction_compiler.py` 迁移逻辑，直接收敛进 profile 文件
  - `verify_contract_hash` 用 hashlib 比对 instruction 文本与预期 hash
  - `diff_with` 返回 `ProfileDiff` 命名元组，列出变更字段名与新/旧值
- [x] **Phase 10-7**：运行 profile 测试，确认 `>= 11 passed`（原 7 + 新 4）

### TDD 垂直切片 (Part B: Handler 替换 raw dict 读写)

- [x] **Phase 10-8**：编写 `test_handler_reads_voice_config_from_profile_not_raw_policy_dict` —— 验证 handler 的 model / voice / temperature 读取走 profile
- [x] **Phase 10-9**：编写 `test_handler_instruction_contract_verified_via_profile` —— 验证 handler 的 instruction 构建/校验走 profile
- [x] **Phase 10-10**：替换 handler 中所有直接读 `_effective_policy['model']` / `_effective_policy['voice']` / `_effective_policy['temperature']` / `_effective_policy['instructions']` 的路径，改为 `self._voice_runtime_profile.model_name` 等
  - 重点位置：`_build_session_update()`、`response.create` 事件构建、policy snapshot 分发
  - 保留 `_effective_policy` dict 作为向后兼容回落（标记 `# deprecated: use VoiceRuntimeProfile`）
- [x] **Phase 10-11**：handler 中 instruction 构建改为 `self._voice_runtime_profile.compile_instructions(persona, stage, config)`
- [x] **Phase 10-12**：运行 handler 测试 + profile 测试，确认全部通过
- [x] **Phase 10-13**：运行 lint
- [ ] **Phase 10-14**：提交 `refactor: deepen VoiceRuntimeProfile with instruction compilation and contract verification`
- [ ] **Phase 10-15**：提交 `refactor: route handler voice config reads through VoiceRuntimeProfile`

### 验证命令

```bash
# Profile 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_voice_runtime_profile.py -q --no-cov

# Handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# 全量 StepFun 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/voice_runtime_profile.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

### 验收标准

- Handler 中不再存在 `self._effective_policy['model']` / `self._effective_policy['voice']` / `self._effective_policy['temperature']` / `self._effective_policy['instructions']` 直接字段访问（允许 `_effective_policy` dict 整体传递场景）
- `VoiceRuntimeProfile` 新增 `compile_instructions` / `verify_contract_hash` / `validate_instruction_contract` / `diff_with` 四个接口，均有对应测试
- handler 测试全量通过，无行为回归
- 前端 event shape 不变

### 风险控制

- Policy 字段读取是高频路径，替换时逐字段 grep 确认所有引用点
- `_effective_policy` dict 保留回落，若 profile 路径异常可快速恢复
- `diff_with` 仅用于测试/诊断，不引入生产路径性能开销

---

## 二十五、Phase 11：StepFunToolExecutionModule 路由/缓存深化

**目标：** 将 handler 中散落的 tool_call 路由决策（重复 tool_call 判定、grounding lookup 触发）和 tool response 缓存逻辑迁移入 `StepFunToolExecutionModule`。

### 当前问题

- `StepFunToolExecutionModule` 已覆盖 `build_tools_from_policy`、`enforce_guardrails`、`execute_tool`、`build_tool_response`、`build_tool_error_response`。
- 但以下能力仍在 handler 中内联：
  - **重复 tool_call 判定**：同一 turn 内对相同 (tool_name, arguments_hash) 的 tool_call 做去重判断
  - **Grounding lookup 触发**：tool_call 为 search 类型时触发 `GroundingDecisionPipeline.retrieve`
  - **Tool response cache**：对相同 query 的搜索结果做短期缓存，避免重复 KB 查询
  - **Tool execution diagnostics**：聚合 tool 调用耗时、成功/失败计数、grounding hit rate

### Module 深化设计

```
StepFunToolExecutionModule (Deepened)
├── 已有接口（不变）
│   ├── build_tools_from_policy(policy, persona) → list[dict]
│   ├── execute_tool(tool_call, context) → ToolResult
│   ├── enforce_guardrails(tools, policy) → list[dict]
│   ├── build_tool_response(tool_call_id, result) → dict
│   └── build_tool_error_response(tool_call_id, error) → dict
├── 新增接口
│   ├── decide_tool_routing(tool_call, turn_context) → ToolRoutingDecision  Interface (新增)
│   ├── get_cached_result(query_hash) → ToolResult | None               Interface (新增)
│   ├── cache_result(query_hash, result, ttl_seconds) → None            Interface (新增)
│   └── collect_diagnostics() → ToolExecutionDiagnostics                Interface (新增)
```

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/stepfun_tool_execution.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 修改 | `backend/tests/unit/test_stepfun_tool_execution.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片 (Part A: 路由/缓存能力)

- [x] **Phase 11-1**：编写 `test_decide_tool_routing_returns_skip_for_duplicate_call` —— 同一 turn 内相同 (tool_name, args) 的去重
- [x] **Phase 11-2**：编写 `test_decide_tool_routing_returns_execute_for_new_call` —— 首次 tool_call 正常路由
- [x] **Phase 11-3**：编写 `test_decide_tool_routing_triggers_grounding_for_search_tool` —— search 类型触发 grounding
- [x] **Phase 11-4**：编写 `test_cache_result_stores_and_retrieves` —— 缓存存取
- [x] **Phase 11-5**：编写 `test_cache_result_expires_after_ttl` —— TTL 过期
- [x] **Phase 11-6**：编写 `test_collect_diagnostics_aggregates_call_stats` —— 诊断聚合
- [x] **Phase 11-7**：运行工具执行测试，确认新增测试失败
- [x] **Phase 11-8**：实现 `decide_tool_routing` / `get_cached_result` / `cache_result` / `collect_diagnostics`
  - `decide_tool_routing` 内部维护 per-turn `_call_registry: dict[str, set[str]]`，按 turn_id 分组记录已处理的 (tool_name, args_hash)
  - `get_cached_result` / `cache_result` 使用简单 dict + TTL（`time.monotonic()`），缓存 key = `hashlib.sha256(query.encode()).hexdigest()`
  - `collect_diagnostics` 返回 `ToolExecutionDiagnostics`（total_calls, cache_hits, grounding_triggers, errors）
- [x] **Phase 11-9**：运行工具执行测试，确认 `11 passed`（以当前测试基线为准）

### TDD 垂直切片 (Part B: Handler 接入)

- [x] **Phase 11-10**：编写 `test_handler_routes_tool_call_through_module_decide` —— 验证 handler 调用 `decide_tool_routing`
- [x] **Phase 11-11**：编写 `test_handler_uses_module_cache_for_repeated_searches` —— 验证重复搜索走缓存
- [x] **Phase 11-12**：替换 handler 中 tool_call 处理路径：
  - `_handle_function_call_output` 前调用 `self._tool_execution.decide_tool_routing(tool_call, turn_context)`
  - 对 search 类型 tool_call，routing 记录 grounding trigger；`GroundingDecisionPipeline.retrieve` 全链路接入留给 Phase 12
  - 搜索结果写入 `self._tool_execution.cache_result(query_hash, result, ttl=300)`
- [x] **Phase 11-13**：运行 handler 测试 + 工具执行测试，全部通过
- [x] **Phase 11-14**：运行 lint
- [ ] **Phase 11-15**：提交 `refactor: add tool routing/cache/diagnostics to StepFunToolExecutionModule`
- [ ] **Phase 11-16**：提交 `refactor: route handler tool calls through module routing and cache`

### 验证命令

```bash
# 工具执行测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_tool_execution.py -q --no-cov

# Handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# 全量 StepFun
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/stepfun_tool_execution.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

### 验收标准

- `StepFunToolExecutionModule` 具备完整的 tool routing（去重 + grounding 触发）、结果缓存（TTL 过期）、调用诊断能力
- Handler 中的 tool_call 决策不再内联重复判定逻辑
- 原有 tool execution 行为无回归

### 风险控制

- 缓存 TTL 设为 300s，避免长期缓存导致过时搜索结果
- `_call_registry` 在 turn 结束时清理，不跨 turn 泄漏
- 若缓存引入行为差异，可通过 feature flag 关闭（`_tool_execution._cache_enabled = False`）

---

## 二十六、Phase 12：GroundingDecisionPipeline 全链路激活

**目标：** 激活第一波未使用的 `retrieve` / `warmup` / `cache` / `diagnostics` 路径，让 `GroundingDecisionPipeline` 成为真正的全链路 grounding 决策 Module。

### 当前问题

- Phase 4 已将 `evaluate` / `build_instruction_overlay` / `build_blocked_response` / `extract_diagnostics` 接入 handler。
- 但以下路径仅存在于 Module Interface 中，handler 未实际调用：
  - `retrieve(decision, kb_ids)`：KB 检索委托已定义但 handler 绕过了它
  - `warmup(kb_ids)`：KB 预热触发未在任何 handler 路径中使用
  - `cache` 语义：管线内的检索结果缓存未启用
  - `diagnostics` 用法：`extract_diagnostics` 只用于测试，handler 未在生产路径收集

### Module 深化设计（Interface 不变，Implementation 补全）

```
GroundingDecisionPipeline (保持不变 Interface，深化 Implementation)
├── evaluate(query, context) → GroundingDecision              Interface (不变)
├── retrieve(decision, kb_ids) → KnowledgeRetrievalResult     Interface (不变，补全调用链)
├── warmup(kb_ids) → WarmupResult                             Interface (新增调用点)
├── build_instruction_overlay(decision) → str                 Interface (不变)
├── build_blocked_response(decision) → str                    Interface (不变)
├── extract_diagnostics(decision, retrieval) → dict           Interface (不变，激活收集)
└── get_cache_stats() → CacheStats                            Interface (新增)
```

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/grounding_decision_pipeline.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 修改 | `backend/tests/unit/test_grounding_decision_pipeline.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片 (Part A: 补全 Implementation)

- [ ] **Phase 12-1**：编写 `test_retrieve_caches_result_and_hits_on_second_call` —— 验证 retrieve 内部缓存行为
- [ ] **Phase 12-2**：编写 `test_warmup_preloads_kb_index` —— 验证 warmup 触发 KB 索引预加载
- [ ] **Phase 12-3**：编写 `test_get_cache_stats_returns_hit_rate` —— 验证缓存命中率统计
- [ ] **Phase 12-4**：运行管线测试，确认新增测试失败
- [ ] **Phase 12-5**：实现 retrieve 内部缓存（复用 Phase 11 的 TTL 缓存模式）、warmup 委托、CacheStats 聚合
- [ ] **Phase 12-6**：运行管线测试，确认 `>= 10 passed`（原 5 + 新 3，另有既存测试）

### TDD 垂直切片 (Part B: Handler 全链路接入)

- [ ] **Phase 12-7**：编写 `test_handler_triggers_pipeline_warmup_on_session_start` —— 验证 session start 时触发 warmup
- [ ] **Phase 12-8**：编写 `test_handler_uses_pipeline_retrieve_instead_of_direct_kb_call` —— 验证 handler 走管线 retrieve
- [ ] **Phase 12-9**：编写 `test_handler_collects_grounding_diagnostics_into_session_metrics` —— 验证 diagnostic 收集
- [ ] **Phase 12-10**：在 handler session start 路径（`_handle_start_command` 或政策加载完成后）调用 `self._grounding_pipeline.warmup(kb_ids)`
- [ ] **Phase 12-11**：替换 handler 中直接 KB 检索调用为 `self._grounding_pipeline.retrieve(decision, kb_ids)`
- [ ] **Phase 12-12**：在 session end / turn end 路径收集 `extract_diagnostics` 到 session metrics
- [ ] **Phase 12-13**：运行 handler 测试 + 管线测试 + knowledge helpers 测试，全部通过
- [ ] **Phase 12-14**：运行 lint
- [ ] **Phase 12-15**：提交 `refactor: activate retrieve/warmup/cache path in GroundingDecisionPipeline`
- [ ] **Phase 12-16**：提交 `refactor: route handler KB operations through full grounding pipeline`

### 验证命令

```bash
# 管线测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_grounding_decision_pipeline.py -q --no-cov

# Handler + Knowledge
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py tests/unit/test_stepfun_knowledge_helpers.py -q --no-cov

# 全量 StepFun
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/grounding_decision_pipeline.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

### 验收标准

- `GroundingDecisionPipeline` 的 `retrieve` / `warmup` / `extract_diagnostics` 均在 handler 生产路径中被调用
- 管线内部启用检索结果缓存，可通过 `get_cache_stats` 查看命中率
- handler 不再直接调用 KB service（全部通过管线）

### 风险控制

- warmup 在 session start 时异步触发，不阻塞 session 就绪
- retrieve 缓存与 Phase 11 tool cache 隔离，各自独立 TTL
- 原有 KB lock guard / answerability 语义不受影响

---

## 二十七、Phase 13：RealtimeAudioFlowModule 输出流接入

**目标：** 将 handler TTS 输出路径接入 `RealtimeAudioFlowModule` 的输出音频缓冲，消除 handler 内联输出 buffer 管理。

### 当前问题

- Phase 7 已将输入音频缓冲与背压移入 `RealtimeAudioFlowModule`。
- 输出音频缓冲（`append_output_audio` / `drain_output_audio` / `clear_output`）已在模块内实现并测试覆盖。
- 但 handler 的 TTS 输出路径（`_send_tts_audio_chunk` / `_flush_tts_buffer`）仍在 handler 内联管理输出 buffer，未使用 module。

### Module 接口（不变，仅接入）

```
RealtimeAudioFlowModule
├── 输入侧（已接入 Phase 7）
│   ├── append_input_audio(audio_bytes)
│   ├── commit_input_audio()
│   ├── clear_input_audio()
│   └── pending_input_audio_bytes() → int
├── 输出侧（本次接入）
│   ├── append_output_audio(audio_bytes)      Interface (已有，接入 handler)
│   ├── drain_output_audio() → list[bytes]    Interface (已有，接入 handler)
│   ├── clear_output_audio()                   Interface (已有，接入 handler)
│   └── pending_output_audio_bytes() → int    Interface (新增)
└── 背压（已接入 Phase 7）
    └── is_backpressure_applied() → bool
```

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/realtime_audio_flow.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 修改 | `backend/tests/unit/test_realtime_audio_flow.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片

- [x] **Phase 13-1**：编写 `test_pending_output_audio_bytes_returns_correct_count` —— 输出 pending 字节计数
- [x] **Phase 13-2**：实现 `pending_output_audio_bytes`（与输入侧对称）
- [x] **Phase 13-3**：编写 `test_handler_appends_tts_output_to_audio_flow_module` —— 验证 handler TTS 输出走 module
- [x] **Phase 13-4**：编写 `test_handler_drains_output_from_module_for_frontend` —— 验证 drain 行为
- [x] **Phase 13-5**：编写 `test_handler_clears_output_on_session_end` —— 验证 session end 清理
- [x] **Phase 13-6**：运行测试，确认新增测试失败
- [x] **Phase 13-7**：替换 handler 中 `_send_tts_audio_chunk` / `_flush_tts_buffer` 的输出 buffer 操作为 `self._audio_flow.append_output_audio` / `self._audio_flow.drain_output_audio`
- [x] **Phase 13-8**：替换 handler session end / reset 中的输出清理为 `self._audio_flow.clear_output_audio`
- [x] **Phase 13-9**：运行音频流测试 + handler 测试，全部通过
- [x] **Phase 13-10**：运行 lint
- [ ] **Phase 13-11**：提交 `refactor: connect handler TTS output path to RealtimeAudioFlowModule`

### 验证命令

```bash
# 音频流测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_realtime_audio_flow.py -q --no-cov

# Handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# 全量 StepFun
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/realtime_audio_flow.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

### 验收标准

- Handler 中不存在独立的输出音频 buffer 变量（list / deque），全部委托给 `_audio_flow`
- `tts_chunk` / `tts_audio` 前端 event shape 不变
- 输出音频 drain 语义与替换前一致（全部取出并清空）

### 风险控制

- 输出音频是低频率路径（TTS chunk 间隔 > 100ms），替换风险低
- 前端 event 序列化格式不变，集成测试保护端到端
- 若异常，`git revert` 单 commit 恢复

---

## 二十八、Phase 14：SessionControlAdapter 接口深化

**目标：** 将 `SessionControlAdapter` 从浅封装深化为具备状态验证、transition 前后钩子、错误恢复能力的 Seam。

### 当前问题

- `SessionControlAdapter` 目前仅封装 `SessionLifecycleService.transition` 的单次调用。
- 接口浅：调用者仍需自行理解 transition 的 pre-condition / post-condition / error mode。
- 缺少以下 Deep Module 特征：
  - **状态预验证**：transition 前检查当前状态是否允许目标动作
  - **Transition 钩子**：pre-transition hook（记录意图）/ post-transition hook（记录结果）
  - **错误恢复**：transition 失败后的补偿动作（如回滚到前一状态）
  - **幂等性**：重复 transition 请求的安全处理

### Adapter 深化设计

```
SessionControlAdapter (Deepened)
├── transition(session_id, action, payload) → TransitionResult    Interface (深化)
├── validate_transition(session_id, action) → bool                Interface (新增)
├── get_transition_history(session_id) → list[TransitionRecord]   Interface (新增)
├── recover_last_failed(session_id) → TransitionResult | None     Interface (新增)
└── is_idempotent(session_id, action, payload) → bool             Interface (新增)
```

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/session_control_adapter.py` |
| 修改 | `backend/tests/unit/test_session_control_adapter.py` |

### TDD 垂直切片

- [x] **Phase 14-1**：编写 `test_validate_transition_rejects_pause_when_idle` —— 空闲状态拒绝 pause
- [x] **Phase 14-2**：编写 `test_validate_transition_allows_pause_when_running` —— 运行中允许 pause
- [x] **Phase 14-3**：编写 `test_transition_history_tracks_all_actions` —— 历史记录完整
- [x] **Phase 14-4**：编写 `test_recover_last_failed_rolls_back_state` —— 失败恢复
- [x] **Phase 14-5**：编写 `test_is_idempotent_true_for_duplicate_transition` —— 幂等检测
- [x] **Phase 14-6**：运行适配器测试，确认新增测试失败
- [x] **Phase 14-7**：实现 `validate_transition`（内部状态表驱动）、`get_transition_history`（内存环形 buffer）、`recover_last_failed`（记录前一状态用于回滚）、`is_idempotent`（基于 action+payload hash）
- [x] **Phase 14-8**：运行适配器测试，确认 `>= 12 passed`（原 4 + 新 5 + 既存）
- [x] **Phase 14-9**：运行 lint
- [ ] **Phase 14-10**：提交 `refactor: deepen SessionControlAdapter with validation/history/recovery`

### 验证命令

```bash
# 适配器测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_session_control_adapter.py -q --no-cov

# Handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/session_control_adapter.py --quiet
```

### 验收标准

- `SessionControlAdapter` 具备 transition 前验证、历史追踪、失败恢复、幂等检测四个新能力
- Handler 中的 session 控制路径无需修改（Adapter 接口向后兼容）
- 原有 `SessionLifecycleService.transition` 委托语义不变

### 风险控制

- 状态验证表基于现有 `SessionLifecycleService` 的状态枚举构建，不引入新状态定义
- `recover_last_failed` 仅在显式调用时触发，不自动执行
- 历史记录使用固定大小环形 buffer（max 100 条），无内存泄漏风险

---

## 二十九、Phase 15：RealtimeTurnCoordinator 语义补全

**目标：** 将第一波的 strangler 埋点升级为完整的 turn 状态机，补全 user audio / model response 语义。

### 当前问题

- Phase 2 仅在 response.create / response.flush / response.reset 三个点埋入协调器调用。
- 以下语义未接入：
  - `on_user_audio_start` / `on_user_audio_stop`：用户开始/停止说话时更新 turn 状态
  - `on_model_response_start` / `on_model_response_done`：模型响应生命周期
  - turn conflict resolution：用户打断模型输出时的冲突处理
  - turn timeout：超时未收到用户音频的自动 turn end

### Module 深化设计

```
RealtimeTurnCoordinator (Deepened)
├── 已有（strangler 埋点）
│   ├── start_turn(turn_id)
│   ├── end_turn(turn_id)
│   ├── is_speaking() → bool
│   └── get_current_turn() → TurnState | None
├── 本次补全
│   ├── on_user_audio_start() → TurnEventResult             Interface (激活)
│   ├── on_user_audio_stop() → TurnEventResult              Interface (激活)
│   ├── on_model_response_start() → TurnEventResult          Interface (激活)
│   ├── on_model_response_done() → TurnEventResult           Interface (激活)
│   ├── resolve_interruption() → InterruptionDecision        Interface (新增)
│   └── check_turn_timeout() → TurnTimeoutResult             Interface (新增)
```

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/realtime_turn_coordinator.py` |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| 修改 | `backend/tests/unit/test_realtime_turn_coordinator.py` |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py` |

### TDD 垂直切片

- [x] **Phase 15-1**：编写 `test_on_user_audio_start_sets_speaking_flag` —— 用户开始说话
- [x] **Phase 15-2**：编写 `test_on_user_audio_stop_clears_speaking_flag` —— 用户停止说话
- [x] **Phase 15-3**：编写 `test_on_model_response_done_ends_turn` —— 模型响应结束 = turn end
- [x] **Phase 15-4**：编写 `test_resolve_interruption_flags_user_interrupted` —— 用户打断检测
- [x] **Phase 15-5**：编写 `test_check_turn_timeout_returns_expired_after_deadline` —— turn 超时
- [x] **Phase 15-6**：编写 `test_handler_notifies_coordinator_on_user_audio_events` —— handler 音频事件通知协调器
- [x] **Phase 15-7**：编写 `test_handler_checks_interruption_before_model_response` —— handler 响应前检查打断
- [x] **Phase 15-8**：运行测试，确认新增测试失败
- [x] **Phase 15-9**：实现 `on_user_audio_start/stop`、`on_model_response_start/done`、`resolve_interruption`、`check_turn_timeout`
  - `resolve_interruption`：若 `is_speaking` 且 `_is_model_responding`，标记 `user_interrupted=True`，返回 `InterruptionDecision(interrupted=True, action=InterruptionAction.CANCEL_MODEL)`
  - `check_turn_timeout`：`time.monotonic() - _last_user_audio_time > _turn_timeout_seconds` 判定超时
- [x] **Phase 15-10**：在 handler 中接入新语义：
  - `input_audio_buffer.speech_started` → `self._turn_coordinator.on_user_audio_start()`
  - `input_audio_buffer.speech_stopped` / `input_audio_buffer.committed` → `self._turn_coordinator.on_user_audio_stop()`
  - `response.create` 后 → `self._turn_coordinator.on_model_response_start()`
  - `response.done` → `self._turn_coordinator.on_model_response_done()`
  - `response.create` 前 → `self._turn_coordinator.resolve_interruption()`，若 interrupted 则 cancel pending response
- [x] **Phase 15-11**：运行协调器测试 + handler 测试，全部通过
- [x] **Phase 15-12**：运行 lint
- [ ] **Phase 15-13**：提交 `refactor: complete RealtimeTurnCoordinator state machine semantics`

### 验证命令

```bash
# 协调器测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_realtime_turn_coordinator.py -q --no-cov

# Handler 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_handler.py -q --no-cov

# 全量 StepFun
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/realtime_turn_coordinator.py src/sales_bot/websocket/stepfun_realtime_handler.py --quiet
```

### 验收标准

- `RealtimeTurnCoordinator` 的 6 个新接口均有对应 handler 调用点
- 用户打断场景有独立测试覆盖（`test_resolve_interruption_flags_user_interrupted`）
- 原有 turn 行为（Phase 2 strangler）无回归

### 风险控制

- `resolve_interruption` 的 CANCEL_MODEL 动作仅在测试中验证语义，生产路径是否实际 cancel 由 handler 层控制
- `check_turn_timeout` 的 timeout 值可配置（默认 30s），避免误判
- 音频事件通知使用现有 handler callback 机制，不改 StepFun 协议

---

## 三十、Phase 16：Handler Residual 安全对齐

**目标：** 系统分析 `stepfun_realtime_handler.py` 中 handler override 与 upstream mixin 的行为差异，逐方法将 canonical behavior 迁入深 Module，再安全删除 wrapper。目标行数从 4225 降至 <1500。

### 前置条件

Phase 10-15 全部完成（所有 Module 已深化，Interface 稳定）。

### 差异分析方法

Phase 8 已识别 upstream mixin 与 handler override 存在约 13 个行为差异方法，分布在四个维度：

| 维度 | 涉及方法 | 差异性质 | 归宿 Module |
|------|---------|---------|------------|
| Transport | `_send_upstream`, `_check_connection_health` | handler 使用 transport，upstream 仍直接操作 WebSocket | `StepFunTransport` |
| Turn | `_handle_response_create`, `_handle_response_done` | handler 有 turn coordinator 埋点，upstream 无 | `RealtimeTurnCoordinator` |
| Tool | `_handle_function_call_output`, `_build_tools` | handler 委托 tool execution module，upstream 内联 | `StepFunToolExecutionModule` |
| Audio | `_send_audio_append`, `_receive_audio_append` | handler 有背压 + audio flow，upstream 无 | `RealtimeAudioFlowModule` |
| Policy | instruction 构建、voice config 读取 | handler 走 profile，upstream 读 raw dict | `VoiceRuntimeProfile` |

### 对齐策略

对每个差异方法，采用三步安全对齐：

1. **分析差异**：grep 两处实现，diff 对比，确认差异语义
2. **迁入 Module**：把 handler 中的 canonical behavior 移入对应深 Module（若尚未在其中）
3. **统一调用**：handler 和 upstream 都改为委托同一 Module 接口
4. **删除 override**：确认行为一致后删除 handler override

### 文件

| 操作 | 文件 |
|------|------|
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`（大幅缩减） |
| 修改 | `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`（统一委托） |
| 修改 | `backend/tests/unit/test_stepfun_realtime_handler.py`（更新/删除过时 mock） |
| 修改 | `backend/tests/unit/test_stepfun_realtime_upstream.py`（已有文件，补充） |

### TDD 垂直切片 (Part A: Transport 维度对齐)

- [x] **Phase 16-1**：grep `upstream.*send_json\|upstream.*ping\|upstream.*pong` 定位 upstream 中直接操作 WebSocket 的位置
- [x] **Phase 16-2**：编写 `test_upstream_delegates_send_to_transport` —— 验证 upstream 走 transport
- [x] **Phase 16-3**：编写 `test_upstream_delegates_health_check_to_transport` —— 验证 upstream 走 transport
- [x] **Phase 16-4**：在 upstream 中注入 `StepFunTransport`，替换直接 WebSocket 操作为 transport 委托
- [x] **Phase 16-5**：运行 upstream 测试 + handler 测试，确认通过
- [x] **Phase 16-6**：若 handler 的 override 与 upstream 行为一致，删除 handler 中对应 override
- [ ] **Phase 16-7**：提交 `refactor: align upstream transport calls with deep module`

### TDD 垂直切片 (Part B: Policy 维度对齐)

- [x] **Phase 16-8**：grep `upstream.*effective_policy\|upstream.*instructions\|upstream.*voice.*config` 定位 upstream 直接读 policy dict 位置
- [x] **Phase 16-9**：编写 `test_upstream_reads_voice_config_from_profile` —— 验证 upstream 走 VoiceRuntimeProfile
- [x] **Phase 16-10**：在 upstream 中注入 `VoiceRuntimeProfile`，替换 raw dict 读取
- [x] **Phase 16-11**：运行 upstream 测试 + handler 测试，确认通过
- [ ] **Phase 16-12**：删除 handler 中与 upstream 行为一致的 policy override
- [ ] **Phase 16-13**：提交 `refactor: align upstream policy reads with VoiceRuntimeProfile`

### TDD 垂直切片 (Part C: Tool/Audio 维度对齐 + 最终清理)

- [x] **Phase 16-14**：对 Tool 维度（`_handle_function_call_output` / `_build_tools`）重复上述对齐流程
- [x] **Phase 16-15**：对 Audio 维度（`_send_audio_append` / `_receive_audio_append`）重复上述对齐流程
- [x] **Phase 16-16**：全量 runner 回归：`PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py tests/unit/test_stepfun_realtime_upstream.py -q --no-cov`
- [x] **Phase 16-17**：Handler 行数检查：`wc -l backend/src/sales_bot/websocket/stepfun_realtime_handler.py`，目标 <1500
- [ ] **Phase 16-18**：提交 `refactor: complete handler residual alignment, remove redundant overrides`

### 验证命令

```bash
# 全量 StepFun 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# Upstream 测试
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_upstream.py -q --no-cov

# Handler 行数
wc -l backend/src/sales_bot/websocket/stepfun_realtime_handler.py

# Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/ --quiet
```

### 验收标准

- Handler 行数 ≤ 1500（第二轮目标；最终 <800 留待第三波）
- Upstream 中不再存在直接 WebSocket 操作、raw policy dict 读取
- 所有差异方法已对齐，handler 中冗余 override 已安全删除
- 全量 StepFun 测试无回归

### 风险控制

- **绝对禁止直接删除 override**：每删除一个 override 前必须确认 behavior 已 100% 迁入 Module 且测试覆盖
- 每个维度对齐独立 commit，可独立回滚
- 若某 override 差异无法安全消解（如涉及 StepFun 协议边缘行为），标记 `# KEEP: protocol edge case` 保留
- 不强行追求 <800 行；若 Phase 16 后 >1500 但所有合理 override 已保留协议注释，视为成功

---

## 三十一、Phase 17：最终验证波 2

**目标：** 全量回归验证，确认第二波所有 Phase 的正确性。

### 验证矩阵

- [x] **Phase 17-1**：所有 StepFun 单元测试（`test_stepfun_*.py`）— 目标 209+ passed
- [x] **Phase 17-2**：所有新模块测试（6 个 module test 文件）— 目标 55+ passed
- [x] **Phase 17-3**：Upstream 测试 — 全部通过
- [x] **Phase 17-4**：Presentation 测试（`test_presentation_stepfun_realtime_handler.py`）— 全部通过
- [x] **Phase 17-5**：Transport 测试（`test_stepfun_transport.py`）— 全部通过
- [x] **Phase 17-6**：集成测试（emotion flow / reconnect / websocket status）— 全部通过
- [x] **Phase 17-7**：全量单元测试（`tests/unit/`）— 目标 1583+ passed
- [x] **Phase 17-8**：Lint 全量（`ruff check` 对触及目录）
- [x] **Phase 17-9**：Mypy 类型检查（对触及模块）
- [x] **Phase 17-10**：Handler 行数报告（`wc -l stepfun_realtime_handler.py`）
- [x] **Phase 17-11**：文档更新：notepad learnings 记录第二波完成状态

### 验证命令

```bash
# 1. StepFun 全量
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_*.py -q --no-cov

# 2. 新模块集合
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_realtime_turn_coordinator.py tests/unit/test_stepfun_tool_execution.py tests/unit/test_grounding_decision_pipeline.py tests/unit/test_session_control_adapter.py tests/unit/test_voice_runtime_profile.py tests/unit/test_realtime_audio_flow.py -q --no-cov

# 3. Upstream
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_realtime_upstream.py -q --no-cov

# 4. Transport
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_stepfun_transport.py -q --no-cov

# 5. Presentation
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/test_presentation_stepfun_realtime_handler.py -q --no-cov

# 6. 集成
cd backend && PYTHONPATH=src uv run python -m pytest tests/integration/test_emotion_flow.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py -q --no-cov

# 7. 全量单元
cd backend && PYTHONPATH=src uv run python -m pytest tests/unit/ -q --no-cov

# 8. Lint
cd backend && PYTHONPATH=src uv run python -m ruff check src/sales_bot/websocket/ src/training_runtime/ src/presentation_coach/websocket/ --quiet

# 9. Mypy
cd backend && PYTHONPATH=src uv run python -m mypy src/sales_bot/websocket/ src/training_runtime/ src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py

# 10. Handler 行数
wc -l backend/src/sales_bot/websocket/stepfun_realtime_handler.py
```

---

## 三十二、第二波提交策略

```
Phase 10a: refactor: deepen VoiceRuntimeProfile with instruction compilation and contract verification
Phase 10b: refactor: route handler voice config reads through VoiceRuntimeProfile
Phase 11a: refactor: add tool routing/cache/diagnostics to StepFunToolExecutionModule
Phase 11b: refactor: route handler tool calls through module routing and cache
Phase 12a: refactor: activate retrieve/warmup/cache path in GroundingDecisionPipeline
Phase 12b: refactor: route handler KB operations through full grounding pipeline
Phase 13:   refactor: connect handler TTS output path to RealtimeAudioFlowModule
Phase 14:   refactor: deepen SessionControlAdapter with validation/history/recovery
Phase 15:   refactor: complete RealtimeTurnCoordinator state machine semantics
Phase 16a:  refactor: align upstream transport calls with deep module
Phase 16b:  refactor: align upstream policy reads with VoiceRuntimeProfile
Phase 16c:  refactor: complete handler residual alignment, remove redundant overrides
Phase 17:   test: verify realtime architecture deepening wave 2
```

共 **13 个原子 commit**，与第一波粒度一致。

---

## 三十三、第二波文件变更总览

### 修改文件（不新建，深化已有文件）

```
backend/src/sales_bot/websocket/voice_runtime_profile.py        (Phase 10)
backend/src/sales_bot/websocket/stepfun_tool_execution.py       (Phase 11)
backend/src/sales_bot/websocket/grounding_decision_pipeline.py  (Phase 12)
backend/src/sales_bot/websocket/realtime_audio_flow.py           (Phase 13)
backend/src/sales_bot/websocket/session_control_adapter.py       (Phase 14)
backend/src/sales_bot/websocket/realtime_turn_coordinator.py     (Phase 15)
backend/src/sales_bot/websocket/stepfun_realtime_handler.py      (Phase 10-16, 主要缩减对象)
backend/src/sales_bot/websocket/stepfun_realtime_upstream.py     (Phase 16)
backend/tests/unit/test_voice_runtime_profile.py                 (Phase 10)
backend/tests/unit/test_stepfun_tool_execution.py                (Phase 11)
backend/tests/unit/test_grounding_decision_pipeline.py           (Phase 12)
backend/tests/unit/test_realtime_audio_flow.py                   (Phase 13)
backend/tests/unit/test_session_control_adapter.py               (Phase 14)
backend/tests/unit/test_realtime_turn_coordinator.py             (Phase 15)
backend/tests/unit/test_stepfun_realtime_handler.py              (Phase 10-16)
backend/tests/unit/test_stepfun_realtime_upstream.py             (Phase 16)
```

无新建文件，全部为深化已有 Module 和测试。

---

## 三十四、第二波不可触碰区域（与第一波一致）

- ❌ `backend/src/curriculum_practice/websocket/router.py`
- ❌ `backend/tests/unit/test_examiner_websocket_router.py`
- ❌ `CONTEXT.md`
- ❌ WebRTC 相关代码
- ❌ `backend/src/sales_bot/websocket/router.py` 的 plugin selection 逻辑
- ❌ `backend/src/websocket_routes.py` 的 Presentation 路由逻辑
- ❌ StepFun payload 结构 / frontend WebSocket event shape / binary audio protocol

---

## 三十五、第二波最终验收标准

- [x] Handler 行数 ≤ 1500（从 4225 再降 2725 行）
- [x] 所有 6 个 Module 的 Interface 均已深化，具备非装饰性能力
- [x] VoiceRuntimeProfile 为 Policy Seam 唯一权威数据源
- [x] StepFunToolExecutionModule 具备 tool routing / cache / diagnostics
- [x] GroundingDecisionPipeline 全链路（retrieve → warmup → cache → diagnostics）激活
- [x] RealtimeAudioFlowModule 覆盖输入/输出双路径
- [x] SessionControlAdapter 具备 validation / history / recovery
- [x] RealtimeTurnCoordinator 具备完整 turn 状态机
- [x] Upstream 与 handler 委托同一套深 Module，行为一致
- [x] 全量 StepFun 测试 209+ passed
- [x] 新模块测试 55+ passed
- [x] 集成测试 21+ passed
- [x] 全量单元测试 1583+ passed
- [x] Lint 零错误
- [x] Mypy 对触及模块零错误
- [x] 无新增 import 循环

---

## 三十六、第三波展望（不在本次范围）

若第二波完成后 handler 行数 >800，第三波将聚焦：

- Handler 中剩余的 WebSocket 事件分发逻辑收敛到 EventDispatchAdapter
- 混合策略（`StepFunRealtimePolicyMixin` / `StepFunRealtimeConnectionMixin` 等）的深度整合
- Presentation handler（`PresentationStepFunRealtimeHandler`）继承链的进一步精简
- 最终 target：handler ≤ 800 行，达到第一波原始目标
