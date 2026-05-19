# StepFun Runtime Seams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 深化 StepFun realtime 的运行时 seam：抽出共享 `StepFunTransport` Module、让 `ScenarioTrainingPlugin` 参与运行时选择、并为少量高价值协作者引入构造函数注入。

**Architecture:** 保持 `training_scenario_runtime` 这一主语不变。新增一个深的 transport Module 负责 StepFun 上游连接与 session.update payload 组装；让 `ScenarioTrainingPlugin` 只负责运行时 handler 选择，不扩展成通用生命周期框架；在 handler 内仅引入少数 factory seam 来提升测试 Locality。这样能提高 Depth、Seam、Leverage 与 Locality，同时不引入更大的抽象层。

**Tech Stack:** Python 3.11, FastAPI WebSocket, SQLAlchemy 2.0 async, pytest, pytest-asyncio, ruff, mypy, StepFun Realtime WebSocket.

---

## File Structure

- Create: `backend/src/training_runtime/stepfun_transport.py`
  - Owns StepFun transport concerns only：上游 WebSocket connect、session.update payload 组装、安全 close、local provider 选择。
  - 不拥有 Sales / Presentation 业务行为、评分、证据、prompt policy、scenario 生命周期。

- Modify: `backend/src/training_runtime/plugins.py`
  - 为 `ScenarioTrainingPlugin` 增加一个小的 runtime handler selection seam。
  - 保持现有生命周期接口不变，不升级成 universal framework。

- Modify: `backend/src/training_runtime/__init__.py`
  - 导出新增 transport / selection 类型。

- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
  - Delegation 到 `StepFunTransport`。
  - 接受 `db_session_factory` 与 `knowledge_service_factory` 这两个窄 factory seam。

- Modify: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
  - 仅 forward 少量协作者 factories，保留 Presentation 本地语义。

- Modify: `backend/src/sales_bot/websocket/router.py`
  - 用 plugin selection seam 构建 Sales StepFun handler。

- Modify: `backend/src/websocket_routes.py`
  - 用 plugin selection seam 构建 Presentation handler。

- Modify: `backend/tests/unit/test_training_runtime_plugins.py`
  - 运行时选择 seam 的 contract tests。

- Modify: `backend/tests/unit/test_main_presentation_ws_runtime.py`
  - Presentation route 的 plugin selection contract tests。

- Modify: `backend/tests/unit/test_stepfun_realtime_handler.py`
  - transport delegation + constructor injection tests。

- Modify: `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
  - Presentation factory forwarding tests。

- Modify: `backend/tests/integration/test_emotion_flow.py`
  - 保持 StepFun 行为未回退的集成守门。

- Modify: `backend/tests/integration/test_sales_realtime_reconnect_flow.py`
  - 保持 Sales reconnect contract 的集成守门。

- Modify: `backend/tests/integration/test_websocket_status_contract.py`
  - 保持 WebSocket 状态契约不变。

---

## Assumptions

- `PracticeSessionService` 在本计划中指 `backend/src/common/services/practice_session_service.py` 及其对 runtime descriptor / session creation 的协作。
- Sales 仍保持 StepFun-only。
- Presentation 仍支持 legacy 与 `stepfun_realtime`。
- 当前 dirty working tree 中的这些文件不属于本计划，不能触碰：
  - `backend/src/curriculum_practice/websocket/router.py`
  - `backend/tests/unit/test_examiner_websocket_router.py`
  - `CONTEXT.md`

---

## Task Order

1. 先做 plugin runtime selection seam。
2. 再抽 shared `StepFunTransport` Module。
3. 最后加 limited constructor factory injection。

这个顺序最稳：先把“谁选择谁”变成显式 contract，再切 transport Implementation，最后收敛测试 Locality。

---

## Task 1: Add Runtime Handler Selection To ScenarioTrainingPlugin

**Files:**
- Modify: `backend/src/training_runtime/plugins.py`
- Modify: `backend/src/training_runtime/__init__.py`
- Test: `backend/tests/unit/test_training_runtime_plugins.py`

- [ ] **Step 1: Write failing plugin selection tests**

Add these tests to `backend/tests/unit/test_training_runtime_plugins.py`:

```python
def test_should_select_sales_stepfun_runtime_handler_through_plugin_seam() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="sales-session",
        scenario_type="sales",
        voice_mode="legacy",
    )
    plugin = get_scenario_plugin("sales")

    selection = plugin.select_runtime_handler(descriptor)

    assert selection.scenario_type == "sales"
    assert selection.runtime_mode == "stepfun_realtime"
    assert selection.websocket_route == "/ws/sales/{session_id}"
    assert selection.handler_factory_path == "sales_bot.websocket.stepfun_realtime_handler"
    assert selection.handler_factory_name == "create_stepfun_realtime_handler"


def test_should_select_presentation_runtime_handler_through_plugin_seam() -> None:
    plugin = get_scenario_plugin("presentation")
    legacy_descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-legacy",
        scenario_type="presentation",
        voice_mode="legacy",
    )
    stepfun_descriptor = TrainingRuntimeDescriptor(
        session_id="presentation-stepfun",
        scenario_type="presentation",
        voice_mode="stepfun_realtime",
    )

    legacy_selection = plugin.select_runtime_handler(legacy_descriptor)
    stepfun_selection = plugin.select_runtime_handler(stepfun_descriptor)

    assert legacy_selection.scenario_type == "presentation"
    assert legacy_selection.runtime_mode == "legacy"
    assert legacy_selection.websocket_route == "/ws/presentation/{session_id}"
    assert legacy_selection.handler_factory_path == "presentation_coach.websocket.presentation_handler"
    assert legacy_selection.handler_factory_name == "PresentationWebSocketHandler"

    assert stepfun_selection.scenario_type == "presentation"
    assert stepfun_selection.runtime_mode == "stepfun_realtime"
    assert stepfun_selection.websocket_route == "/ws/presentation/{session_id}"
    assert stepfun_selection.handler_factory_path == (
        "presentation_coach.websocket.presentation_stepfun_realtime_handler"
    )
    assert stepfun_selection.handler_factory_name == "PresentationStepFunRealtimeHandler"
```

- [ ] **Step 2: Run tests and verify failure**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_training_runtime_plugins.py::test_should_select_sales_stepfun_runtime_handler_through_plugin_seam tests/unit/test_training_runtime_plugins.py::test_should_select_presentation_runtime_handler_through_plugin_seam -q
```

Expected: fails with `AttributeError` mentioning `select_runtime_handler`.

- [ ] **Step 3: Add the runtime selection dataclass and Protocol method**

In `backend/src/training_runtime/plugins.py`, add:

```python
@dataclass(frozen=True)
class ScenarioRuntimeHandlerSelection:
    """Concrete runtime handler construction seam for one scenario session."""

    scenario_type: str
    runtime_mode: str
    websocket_route: str
    handler_factory_path: str
    handler_factory_name: str
```

Add this method to `ScenarioTrainingPlugin`:

```python
def select_runtime_handler(
    self,
    descriptor: TrainingRuntimeDescriptor,
) -> ScenarioRuntimeHandlerSelection: ...
```

- [ ] **Step 4: Implement Sales selection**

Add this method to `SalesScenarioPlugin`:

```python
def select_runtime_handler(
    self,
    descriptor: TrainingRuntimeDescriptor,
) -> ScenarioRuntimeHandlerSelection:
    return ScenarioRuntimeHandlerSelection(
        scenario_type=self.scenario_type,
        runtime_mode=self._runtime_mode,
        websocket_route="/ws/sales/{session_id}",
        handler_factory_path="sales_bot.websocket.stepfun_realtime_handler",
        handler_factory_name="create_stepfun_realtime_handler",
    )
```

- [ ] **Step 5: Implement Presentation selection**

Add this method to `PresentationScenarioPlugin`:

```python
def select_runtime_handler(
    self,
    descriptor: TrainingRuntimeDescriptor,
) -> ScenarioRuntimeHandlerSelection:
    runtime_mode = self._runtime_mode(descriptor)
    if runtime_mode == "stepfun_realtime":
        return ScenarioRuntimeHandlerSelection(
            scenario_type=self.scenario_type,
            runtime_mode=runtime_mode,
            websocket_route="/ws/presentation/{session_id}",
            handler_factory_path=(
                "presentation_coach.websocket.presentation_stepfun_realtime_handler"
            ),
            handler_factory_name="PresentationStepFunRealtimeHandler",
        )

    return ScenarioRuntimeHandlerSelection(
        scenario_type=self.scenario_type,
        runtime_mode=runtime_mode,
        websocket_route="/ws/presentation/{session_id}",
        handler_factory_path="presentation_coach.websocket.presentation_handler",
        handler_factory_name="PresentationWebSocketHandler",
    )
```

- [ ] **Step 6: Export the new type**

In `backend/src/training_runtime/__init__.py`, import and add `ScenarioRuntimeHandlerSelection` to `__all__`.

- [ ] **Step 7: Run plugin tests**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_training_runtime_plugins.py -q
```

Expected: all tests in `test_training_runtime_plugins.py` pass.

- [ ] **Step 8: Commit**

```bash
git add backend/src/training_runtime/plugins.py backend/src/training_runtime/__init__.py backend/tests/unit/test_training_runtime_plugins.py
git commit -m "refactor: add scenario runtime handler selection seam"
```

**Risk Control:** 只加新 Interface，不改既有 route 行为。若发生回退，原有 route branching 仍可工作。

**Rollback Point:** Commit `refactor: add scenario runtime handler selection seam`。

---

## Task 2: Route Presentation Handler Construction Through Plugin Selection

**Files:**
- Modify: `backend/src/websocket_routes.py`
- Test: `backend/tests/unit/test_main_presentation_ws_runtime.py`

- [ ] **Step 1: Add a failing route test**

Add this test to `backend/tests/unit/test_main_presentation_ws_runtime.py`:

```python
@pytest.mark.asyncio
async def test_presentation_ws_runtime_selection_uses_plugin_seam() -> None:
    session_id = str(uuid.uuid4())
    websocket = MagicMock()
    websocket.headers = {}
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    stepfun_handler = MagicMock()
    stepfun_handler.handle_connection = AsyncMock()

    plugin = MagicMock()
    plugin.select_runtime_handler.return_value = MagicMock(
        scenario_type="presentation",
        runtime_mode="stepfun_realtime",
        websocket_route="/ws/presentation/{session_id}",
        handler_factory_path=(
            "presentation_coach.websocket.presentation_stepfun_realtime_handler"
        ),
        handler_factory_name="PresentationStepFunRealtimeHandler",
    )

    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    with (
        patch(
            "main._resolve_presentation_runtime",
            new=AsyncMock(return_value=("presentation", "stepfun_realtime")),
        ),
        patch(
            "main._is_presentation_kb_lock_unbound_session",
            new=AsyncMock(return_value=False),
        ),
        patch("training_runtime.dispatch_scenario_plugin", return_value=plugin),
        patch(
            "presentation_coach.websocket.presentation_stepfun_realtime_handler.PresentationStepFunRealtimeHandler",
            return_value=stepfun_handler,
        ),
        patch(
            "common.websocket.session_manager.get_session_manager",
            return_value=session_manager,
        ),
        patch("common.auth.service.verify_token", return_value={"sub": "user-123"}),
    ):
        await main._handle_presentation_websocket(
            websocket=websocket,
            session_id=session_id,
            token="query-token",
            voice_mode="legacy",
        )

    plugin.select_runtime_handler.assert_called_once()
    session_manager.register_session.assert_awaited_once_with(
        session_id,
        stepfun_handler,
        user_id="user-123",
    )
```

- [ ] **Step 2: Run the focused test and verify failure**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_main_presentation_ws_runtime.py::test_presentation_ws_runtime_selection_uses_plugin_seam -q
```

Expected: fails because `_handle_presentation_websocket` still branches directly on `effective_voice_mode`.

- [ ] **Step 3: Add a narrow handler instantiation helper**

In `backend/src/websocket_routes.py`, add imports:

```python
from importlib import import_module

from training_runtime import TrainingRuntimeDescriptor, dispatch_scenario_plugin
```

Add helper:

```python
def _instantiate_runtime_handler(selection: Any) -> Any:
    module = import_module(selection.handler_factory_path)
    factory = getattr(module, selection.handler_factory_name)
    return factory()
```

- [ ] **Step 4: Replace Presentation direct branching with plugin selection**

Replace:

```python
handler: Any
if effective_voice_mode == "stepfun_realtime":
    handler = PresentationStepFunRealtimeHandler()
else:
    handler = PresentationWebSocketHandler()
```

with:

```python
descriptor = TrainingRuntimeDescriptor(
    session_id=resolved_session_id,
    scenario_type="presentation",
    voice_mode=effective_voice_mode,
)
selection = dispatch_scenario_plugin(descriptor).select_runtime_handler(descriptor)
handler = _instantiate_runtime_handler(selection)
```

- [ ] **Step 5: Run Presentation routing tests**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_main_presentation_ws_runtime.py -q
```

Expected: all tests in `test_main_presentation_ws_runtime.py` pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/websocket_routes.py backend/tests/unit/test_main_presentation_ws_runtime.py
git commit -m "refactor: route presentation websocket through runtime plugin seam"
```

**Risk Control:** 保持 `_resolve_presentation_runtime()`、auth、owner check、KB lock 检查不变；plugin 只管 handler construction selection。

**Rollback Point:** Commit `refactor: route presentation websocket through runtime plugin seam`。

---

## Task 3: Route Sales Handler Construction Through Plugin Selection

**Files:**
- Modify: `backend/src/sales_bot/websocket/router.py`
- Test: `backend/tests/unit/test_training_runtime_plugins.py`

- [ ] **Step 1: Add a Sales route construction test**

If no dedicated router unit test exists, add this contract guard to `backend/tests/unit/test_training_runtime_plugins.py`:

```python
def test_sales_runtime_selection_points_to_existing_factory() -> None:
    descriptor = TrainingRuntimeDescriptor(
        session_id="sales-session",
        scenario_type="sales",
        voice_mode="stepfun_realtime",
    )
    selection = get_scenario_plugin("sales").select_runtime_handler(descriptor)

    module = __import__(selection.handler_factory_path, fromlist=[selection.handler_factory_name])
    factory = getattr(module, selection.handler_factory_name)

    assert callable(factory)
```

- [ ] **Step 2: Run focused test**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_training_runtime_plugins.py::test_sales_runtime_selection_points_to_existing_factory -q
```

Expected: `1 passed` after Task 1 exists.

- [ ] **Step 3: Update Sales router to use selection**

In `backend/src/sales_bot/websocket/router.py`, import:

```python
from importlib import import_module

from training_runtime import TrainingRuntimeDescriptor, dispatch_scenario_plugin
```

Add helper:

```python
def _instantiate_runtime_handler(selection: Any) -> Any:
    module = import_module(selection.handler_factory_path)
    factory = getattr(module, selection.handler_factory_name)
    return factory()
```

Replace:

```python
handler = create_stepfun_realtime_handler()
```

inside `_handle_stepfun_realtime_connection()` with:

```python
descriptor = TrainingRuntimeDescriptor(
    session_id=session_id,
    scenario_type="sales",
    voice_mode="stepfun_realtime",
)
selection = dispatch_scenario_plugin(descriptor).select_runtime_handler(descriptor)
handler = _instantiate_runtime_handler(selection)
```

- [ ] **Step 4: Run Sales and plugin tests**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_training_runtime_plugins.py tests/integration/test_sales_realtime_reconnect_flow.py -q
```

Expected: plugin tests pass, reconnect integration tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/sales_bot/websocket/router.py backend/tests/unit/test_training_runtime_plugins.py
git commit -m "refactor: route sales websocket through runtime plugin seam"
```

**Risk Control:** 不削弱 Sales StepFun-only checks；这里只改 construction Locality。

**Rollback Point:** Commit `refactor: route sales websocket through runtime plugin seam`。

---

## Task 4: Extract Shared StepFunTransport Module

**Files:**
- Create: `backend/src/training_runtime/stepfun_transport.py`
- Modify: `backend/src/training_runtime/__init__.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Test: `backend/tests/unit/test_stepfun_realtime_handler.py`

- [ ] **Step 1: Write failing transport payload test**

Add this test to `backend/tests/unit/test_stepfun_realtime_handler.py`:

```python
def test_stepfun_transport_builds_session_update_payload_with_transcription_and_tools():
    from training_runtime.stepfun_transport import StepFunSessionConfig, build_stepfun_session_update_payload

    payload = build_stepfun_session_update_payload(
        config=StepFunSessionConfig(
            api_key="secret",
            url="wss://api.stepfun.com/v1/realtime",
            model="step-audio-2",
            voice="qingchunshaonv",
            temperature=0.7,
            input_audio_format="pcm16",
            output_audio_format="pcm16",
            input_transcription_enabled=True,
            input_transcription_language="zh",
            input_transcription_model="",
            instructions="Be concise.",
        ),
        selected_voice="qingchunshaonv",
        turn_detection={"type": "server_vad"},
        tools=[{"type": "function", "name": "search_internal_knowledge"}],
    )

    assert payload == {
        "type": "session.update",
        "session": {
            "voice": "qingchunshaonv",
            "temperature": 0.7,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": {"type": "server_vad"},
            "input_audio_transcription": {"language": "zh"},
            "instructions": "Be concise.",
            "tools": [{"type": "function", "name": "search_internal_knowledge"}],
        },
    }
```

- [ ] **Step 2: Run focused test and verify failure**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_stepfun_realtime_handler.py::test_stepfun_transport_builds_session_update_payload_with_transcription_and_tools -q
```

Expected: fails with `ModuleNotFoundError: No module named 'training_runtime.stepfun_transport'`.

- [ ] **Step 3: Create `StepFunTransport` Module**

Create `backend/src/training_runtime/stepfun_transport.py`:

```python
"""Shared StepFun realtime transport module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import websockets

from sales_bot.websocket.components.local_stepfun_provider import (
    Phase4LocalStepFunProvider,
    should_use_phase4_local_provider,
)


@dataclass(frozen=True, slots=True)
class StepFunSessionConfig:
    api_key: str
    url: str
    model: str
    voice: str
    temperature: float
    input_audio_format: str
    output_audio_format: str
    input_transcription_enabled: bool
    input_transcription_language: str
    input_transcription_model: str
    instructions: str


def build_stepfun_session_update_payload(
    *,
    config: StepFunSessionConfig,
    selected_voice: str,
    turn_detection: dict[str, Any] | None,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    session_payload: dict[str, Any] = {
        "type": "session.update",
        "session": {
            "voice": selected_voice,
            "temperature": config.temperature,
            "input_audio_format": config.input_audio_format,
            "output_audio_format": config.output_audio_format,
            "turn_detection": turn_detection,
        },
    }
    if config.input_transcription_enabled:
        input_audio_transcription: dict[str, Any] = {}
        if config.input_transcription_language:
            input_audio_transcription["language"] = config.input_transcription_language
        if config.input_transcription_model:
            input_audio_transcription["model"] = config.input_transcription_model
        if input_audio_transcription:
            session_payload["session"]["input_audio_transcription"] = input_audio_transcription
    if config.instructions:
        session_payload["session"]["instructions"] = config.instructions
    if tools:
        session_payload["session"]["tools"] = tools
    return session_payload


class StepFunTransport:
    """Deep transport Module for StepFun realtime upstream connections."""

    async def connect(self, config: StepFunSessionConfig) -> Any:
        if should_use_phase4_local_provider():
            return Phase4LocalStepFunProvider.from_env()

        query = urlencode({"model": config.model})
        endpoint = f"{config.url}?{query}"
        headers = {"Authorization": f"Bearer {config.api_key}"}
        return await websockets.connect(endpoint, additional_headers=headers)

    async def close(self, upstream_ws: Any | None) -> None:
        if upstream_ws is None:
            return
        try:
            await upstream_ws.close()
        except (RuntimeError, ValueError, OSError):
            return
```

- [ ] **Step 4: Export transport types**

In `backend/src/training_runtime/__init__.py`, export:

```python
from .stepfun_transport import (
    StepFunSessionConfig,
    StepFunTransport,
    build_stepfun_session_update_payload,
)
```

Add these names to `__all__`.

- [ ] **Step 5: Run payload test**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_stepfun_realtime_handler.py::test_stepfun_transport_builds_session_update_payload_with_transcription_and_tools -q
```

Expected: `1 passed`.

- [ ] **Step 6: Add handler delegation test**

Add this test to `backend/tests/unit/test_stepfun_realtime_handler.py`:

```python
@pytest.mark.asyncio
async def test_connect_upstream_delegates_connection_to_shared_stepfun_transport():
    connected_ws = AsyncMock()
    transport = MagicMock()
    transport.connect = AsyncMock(return_value=connected_ws)

    handler = StepFunRealtimeHandler(stepfun_transport=transport)
    handler._effective_policy = {"turn_detection": "server_vad"}
    handler._curriculum_snapshot = None
    handler._send_upstream = AsyncMock()
    handler._ensure_upstream_keepalive_task = MagicMock()
    handler._maybe_start_kb_lock_warmup = AsyncMock()
    handler._build_stepfun_tools_from_policy = MagicMock(return_value=[])
    handler._enforce_stepfun_tool_guardrails = MagicMock(return_value=[])

    await handler._connect_upstream()

    transport.connect.assert_awaited_once()
    assert handler.upstream_ws is connected_ws
    handler._send_upstream.assert_awaited_once()
    payload = handler._send_upstream.await_args.args[0]
    assert payload["type"] == "session.update"
    assert payload["session"]["voice"] == handler._stepfun_voice
```

- [ ] **Step 7: Run delegation test and verify failure**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_stepfun_realtime_handler.py::test_connect_upstream_delegates_connection_to_shared_stepfun_transport -q
```

Expected: fails because `StepFunRealtimeHandler.__init__()` does not accept `stepfun_transport`.

- [ ] **Step 8: Inject transport into handler and delegate connect**

In `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, import:

```python
from training_runtime.stepfun_transport import (
    StepFunSessionConfig,
    StepFunTransport,
    build_stepfun_session_update_payload,
)
```

Change constructor signature:

```python
def __init__(self, *, stepfun_transport: StepFunTransport | None = None) -> None:
```

Set:

```python
self._stepfun_transport = stepfun_transport or StepFunTransport()
```

Add helper:

```python
def _build_stepfun_session_config(self) -> StepFunSessionConfig:
    return StepFunSessionConfig(
        api_key=self._stepfun_api_key,
        url=self._stepfun_url,
        model=self._stepfun_model,
        voice=self._stepfun_voice,
        temperature=self._stepfun_temperature,
        input_audio_format=self._stepfun_input_audio_format,
        output_audio_format=self._stepfun_output_audio_format,
        input_transcription_enabled=self._stepfun_input_transcription_enabled,
        input_transcription_language=self._stepfun_input_transcription_language,
        input_transcription_model=self._stepfun_input_transcription_model,
        instructions=self._stepfun_instructions,
    )
```

In `_connect_upstream()`, replace direct local provider and `websockets.connect()` logic with:

```python
config = self._build_stepfun_session_config()
self.upstream_ws = await self._stepfun_transport.connect(config)
now = asyncio.get_running_loop().time()
self._upstream_connected_at = now
self._upstream_last_activity_at = now
self._last_upstream_event_type = ""
```

Keep tool preparation and selected voice logic in the handler, then replace manual `session_payload` construction with:

```python
session_payload = build_stepfun_session_update_payload(
    config=config,
    selected_voice=selected_voice,
    turn_detection=turn_detection_value,
    tools=tools,
)
```

- [ ] **Step 9: Delegate close**

In `_close_upstream()`, replace direct close try/except with:

```python
await self._stepfun_transport.close(self.upstream_ws)
self.upstream_ws = None
self._upstream_connected_at = 0.0
self._upstream_last_activity_at = 0.0
```

- [ ] **Step 10: Run focused StepFun tests**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_stepfun_realtime_handler.py::test_stepfun_transport_builds_session_update_payload_with_transcription_and_tools tests/unit/test_stepfun_realtime_handler.py::test_connect_upstream_delegates_connection_to_shared_stepfun_transport -q
```

Expected: `2 passed`.

- [ ] **Step 11: Commit**

```bash
git add backend/src/training_runtime/stepfun_transport.py backend/src/training_runtime/__init__.py backend/src/sales_bot/websocket/stepfun_realtime_handler.py backend/tests/unit/test_stepfun_realtime_handler.py
git commit -m "refactor: extract shared stepfun transport module"
```

**Risk Control:** 新 Module 只拥有 transport。若 StepFun 行为回退，可回滚此 commit，direct connection logic 立刻恢复。

**Rollback Point:** Commit `refactor: extract shared stepfun transport module`。

---

## Task 5: Add Limited Constructor Injection For DB And Knowledge Factories

**Files:**
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- Test: `backend/tests/unit/test_stepfun_realtime_handler.py`
- Test: `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`

- [ ] **Step 1: Add failing injection test for KB dictionary merge**

Add to `backend/tests/unit/test_stepfun_realtime_handler.py`:

```python
@pytest.mark.asyncio
async def test_load_effective_policy_uses_injected_db_and_knowledge_factories_without_monkeypatch():
    handler_session = SimpleNamespace(
        session_id="session-dictionary",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        voice_policy_snapshot={
            "voice_mode": "stepfun_realtime",
            "runtime_profile_id": "profile-dict",
            "model_name": "step-audio-2",
            "voice_name": "qingchunshaonv",
            "temperature": 0.7,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "output_sample_rate": 24000,
            "instructions": "dictionary merge instructions",
            "instruction_contract_hash": "hash-dictionary",
            "knowledge_base_ids": ["kb-dict-1"],
            "tool_policy": {
                "transcript_normalization_enabled": True,
                "transcript_normalization_lexicon": [],
            },
        },
        voice_mode="stepfun_realtime",
        voice_runtime_profile_id="profile-dict",
    )

    class DummyResult:
        def scalar_one_or_none(self):
            return handler_session

    class DummyDb:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, _stmt):
            return DummyResult()

    dummy_db = DummyDb()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return dummy_db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def active_dictionary_lexicon(self, kb_ids):
            assert kb_ids == ["kb-dict-1"]
            return [
                {
                    "canonical_term": "石犀科技",
                    "aliases": ["实习科技"],
                    "scope": "knowledge_base:kb-dict-1",
                }
            ]

    handler = StepFunRealtimeHandler(
        db_session_factory=DummyDbSessionContext,
        knowledge_service_factory=DummyKnowledgeService,
    )
    handler.session_id = "session-dictionary"
    handler._refresh_sales_stage_runtime_config = AsyncMock()
    handler._enforce_tool_policy_guardrails = MagicMock(return_value=False)
    handler._ensure_knowledge_runtime_metrics = MagicMock()

    await handler._load_effective_policy()

    assert handler._effective_policy["tool_policy"]["transcript_normalization_lexicon"][0]["canonical_term"] == "石犀科技"
    dummy_db.commit.assert_awaited()
```

- [ ] **Step 2: Run test and verify failure**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_stepfun_realtime_handler.py::test_load_effective_policy_uses_injected_db_and_knowledge_factories_without_monkeypatch -q
```

Expected: fails because `StepFunRealtimeHandler.__init__()` does not accept `db_session_factory` or `knowledge_service_factory`.

- [ ] **Step 3: Add constructor arguments**

In `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, add imports:

```python
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
```

Change constructor signature to:

```python
def __init__(
    self,
    *,
    stepfun_transport: StepFunTransport | None = None,
    db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = AsyncSessionLocal,
    knowledge_service_factory: Callable[[AsyncSession], KnowledgeService] = KnowledgeService,
) -> None:
```

Set:

```python
self._db_session_factory = db_session_factory
self._knowledge_service_factory = knowledge_service_factory
```

- [ ] **Step 4: Replace targeted DB and knowledge construction**

Replace these high-value occurrences only:

```python
async with AsyncSessionLocal() as db:
```

with:

```python
async with self._db_session_factory() as db:
```

inside:
- `_load_effective_policy()`
- `_persist_runtime_metrics_to_session()`
- `_maybe_start_kb_lock_warmup()`
- `_load_emotion_log_into_feedback_context()`

Replace:

```python
KnowledgeService(db)
```

with:

```python
self._knowledge_service_factory(db)
```

inside:
- `_merge_kb_dictionary_into_effective_policy()`
- `_maybe_start_kb_lock_warmup()`

Replace in `_tool_search_internal_knowledge()`:

```python
session_factory=AsyncSessionLocal,
knowledge_service_cls=KnowledgeService,
```

with:

```python
session_factory=self._db_session_factory,
knowledge_service_cls=self._knowledge_service_factory,
```

- [ ] **Step 5: Preserve factory defaults**

Keep `create_stepfun_realtime_handler()` as:

```python
def create_stepfun_realtime_handler() -> StepFunRealtimeHandler:
    """Factory for router registration."""
    return StepFunRealtimeHandler()
```

- [ ] **Step 6: Add Presentation constructor forwarding test**

Add to `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`:

```python
def test_presentation_stepfun_handler_forwards_collaborator_factories():
    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

    handler = PresentationStepFunRealtimeHandler(
        db_session_factory=DummyDbSessionContext,
        knowledge_service_factory=DummyKnowledgeService,
    )

    assert handler._db_session_factory is DummyDbSessionContext
    assert handler._knowledge_service_factory is DummyKnowledgeService
    assert handler.session_scenario_type == "presentation"
```

- [ ] **Step 7: Update Presentation constructor**

In `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`, change constructor to:

```python
def __init__(
    self,
    *,
    db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = AsyncSessionLocal,
    knowledge_service_factory: Callable[[AsyncSession], KnowledgeService] = KnowledgeService,
    stepfun_transport: StepFunTransport | None = None,
) -> None:
    super().__init__(
        stepfun_transport=stepfun_transport,
        db_session_factory=db_session_factory,
        knowledge_service_factory=knowledge_service_factory,
    )
```

Add needed imports:

```python
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from common.knowledge.service import KnowledgeService
from training_runtime.stepfun_transport import StepFunTransport
```

- [ ] **Step 8: Run injection tests**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_stepfun_realtime_handler.py::test_load_effective_policy_uses_injected_db_and_knowledge_factories_without_monkeypatch tests/unit/test_presentation_stepfun_realtime_handler.py::test_presentation_stepfun_handler_forwards_collaborator_factories -q
```

Expected: `2 passed`.

- [ ] **Step 9: Commit**

```bash
git add backend/src/sales_bot/websocket/stepfun_realtime_handler.py backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_presentation_stepfun_realtime_handler.py
git commit -m "refactor: inject stepfun handler collaborator factories"
```

**Risk Control:** 只注入两个 factory + transport，不引入 container / service locator / broader collaborator bag。

**Rollback Point:** Commit `refactor: inject stepfun handler collaborator factories`。

---

## Task 6: Final Verification Gate

**Files:**
- Verify only.

- [ ] **Step 1: Run focused unit tests**

Run from `backend/`:

```bash
python -m pytest tests/unit/test_training_runtime_plugins.py tests/unit/test_main_presentation_ws_runtime.py tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_handler.py -q
```

Expected: all selected unit tests pass.

- [ ] **Step 2: Run focused integration tests**

Run from `backend/`:

```bash
python -m pytest tests/integration/test_emotion_flow.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py -q
```

Expected: all selected integration tests pass.

- [ ] **Step 3: Run lint**

Run from `backend/`:

```bash
python -m ruff check src tests/unit/test_training_runtime_plugins.py tests/unit/test_main_presentation_ws_runtime.py tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_handler.py
```

Expected: exit code `0`.

- [ ] **Step 4: Run type checks on touched runtime modules**

Run from `backend/`:

```bash
python -m mypy src/training_runtime src/sales_bot/websocket/stepfun_realtime_handler.py src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py src/websocket_routes.py src/sales_bot/websocket/router.py
```

Expected: exit code `0`.

- [ ] **Step 5: Run full backend test suite**

Run from `backend/`:

```bash
python -m pytest
```

Expected: test suite passes and coverage remains at or above the configured `48%` threshold.

- [ ] **Step 6: Inspect working tree**

Run from repo root:

```bash
git status --short
```

Expected: only intentional implementation files are changed. Pre-existing dirty files remain untouched unless they were explicitly part of a completed task.

---

## Atomic Commit Strategy

- Commit 1: `refactor: add scenario runtime handler selection seam`
- Commit 2: `refactor: route presentation websocket through runtime plugin seam`
- Commit 3: `refactor: route sales websocket through runtime plugin seam`
- Commit 4: `refactor: extract shared stepfun transport module`
- Commit 5: `refactor: inject stepfun handler collaborator factories`
- Commit 6: `test: verify stepfun runtime seams`

每个 commit 进入下一个任务前都必须先通过对应的 focused test command。

---

## Option Coverage

- Option 1B: Covered by Task 4. `StepFunTransport` 成为共享深 Module，替代 handler 内联 transport Implementation。
- Option 2B: Covered by Tasks 1 through 3. `ScenarioTrainingPlugin` 成为 runtime handler selection Seam，但不膨胀成 universal lifecycle framework。
- Option 3B: Covered by Task 5. 仅为 `db_session_factory`、`knowledge_service_factory` 与 transport 引入窄 constructor seam。

---

## Self-Review Checklist

- [ ] Spec coverage: 每个选定 option 都至少映射到一个 task。
- [ ] File paths: 每个 task 都写了精确路径。
- [ ] Test names: 每个新增测试都有精确名字。
- [ ] Commands: 每个 task 都写了精确命令和预期结果。
- [ ] Placeholder scan: 计划中没有占位标记、延后实现标记、或模糊“补测试”措辞。
- [ ] Signature consistency: `select_runtime_handler()`、`ScenarioRuntimeHandlerSelection`、`StepFunSessionConfig`、`StepFunTransport`、`db_session_factory`、`knowledge_service_factory` 在全文中命名一致。
- [ ] Scope control: 没有添加依赖，没有创建 universal runtime framework，没有把所有 scenario 都迁入 plugin，没有触碰 dirty working tree 的无关文件。
